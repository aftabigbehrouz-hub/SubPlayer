package com.behrouz.subplayer

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import java.io.BufferedInputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.zip.ZipInputStream

/**
 * Downloads (once) and stores the offline Vosk speech models.
 * Models are free, from https://alphacephei.com/vosk/models
 */
object ModelManager {

    data class SpeechModel(
        val lang: String,      // ISO code used for the subtitle track
        val label: String,     // shown in the language dialog
        val url: String,       // download link (zip)
        val folder: String,    // top folder inside the zip
        val sizeMb: Int        // approximate download size
    )

    val MODELS = listOf(
        SpeechModel(
            lang = "de",
            label = "German (Deutsch)",
            url = "https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip",
            folder = "vosk-model-small-de-0.15",
            sizeMb = 45
        ),
        SpeechModel(
            lang = "en",
            label = "English",
            url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
            folder = "vosk-model-small-en-us-0.15",
            sizeMb = 40
        )
    )

    private fun root(ctx: Context) = File(ctx.filesDir, "models")

    fun isInstalled(ctx: Context, m: SpeechModel): Boolean =
        File(File(root(ctx), m.folder), ".ready").exists()

    /** Returns the model folder, downloading and unpacking it first if needed. */
    suspend fun ensure(
        ctx: Context,
        m: SpeechModel,
        onProgress: (Int, String) -> Unit
    ): File = withContext(Dispatchers.IO) {
        val root = root(ctx).apply { mkdirs() }
        val dir = File(root, m.folder)
        if (File(dir, ".ready").exists()) return@withContext dir

        val part = File(root, "${m.folder}.zip.part")
        download(
            url = m.url,
            dest = part,
            check = { ensureActive() },
            progress = { pct -> onProgress(pct, "Downloading ${m.label} model… $pct%") }
        )

        onProgress(100, "Unpacking model…")
        dir.deleteRecursively()
        unzip(part, root)
        if (!dir.isDirectory) {
            part.delete()
            throw IOException("Model archive did not contain folder ${m.folder}")
        }
        part.delete()
        File(dir, ".ready").writeText("ok")
        dir
    }

    /** Download with resume support (an interrupted download continues next time). */
    private fun download(url: String, dest: File, check: () -> Unit, progress: (Int) -> Unit) {
        val existing = if (dest.exists()) dest.length() else 0L
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 20_000
            readTimeout = 30_000
            if (existing > 0) setRequestProperty("Range", "bytes=$existing-")
        }
        try {
            val code = conn.responseCode
            if (code == 416) return // the .part file is already complete
            if (code != HttpURLConnection.HTTP_OK && code != HttpURLConnection.HTTP_PARTIAL) {
                throw IOException("Download failed (HTTP $code)")
            }
            val append = code == HttpURLConnection.HTTP_PARTIAL
            val len = conn.contentLengthLong
            val total = if (len > 0) (if (append) existing + len else len) else -1L
            var done = if (append) existing else 0L

            conn.inputStream.use { input ->
                FileOutputStream(dest, append).use { out ->
                    val buf = ByteArray(64 * 1024)
                    var last = -1
                    while (true) {
                        check()
                        val r = input.read(buf)
                        if (r < 0) break
                        out.write(buf, 0, r)
                        done += r
                        if (total > 0) {
                            val p = (done * 100 / total).toInt()
                            if (p != last) { last = p; progress(p) }
                        }
                    }
                }
            }
            if (total > 0 && done < total) {
                throw IOException("Download incomplete — tap again, it will resume.")
            }
        } finally {
            conn.disconnect()
        }
    }

    private fun unzip(zip: File, target: File) {
        val rootPath = target.canonicalPath + File.separator
        ZipInputStream(BufferedInputStream(FileInputStream(zip))).use { zis ->
            var e = zis.nextEntry
            while (e != null) {
                val f = File(target, e.name)
                if (!f.canonicalPath.startsWith(rootPath)) throw IOException("Unsafe zip entry: ${e.name}")
                if (e.isDirectory) {
                    f.mkdirs()
                } else {
                    f.parentFile?.mkdirs()
                    FileOutputStream(f).use { zis.copyTo(it) }
                }
                zis.closeEntry()
                e = zis.nextEntry
            }
        }
    }
}
