package com.behrouz.subplayer.data

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
import java.security.MessageDigest
import java.util.zip.ZipInputStream
import kotlin.coroutines.cancellation.CancellationException

/**
 * Everything the app downloads (once). Files are served from this app's own GitHub
 * release ("data-v1"); the original site is the fallback. Every file is checked
 * against its SHA-256 fingerprint, so a corrupted or tampered file is rejected.
 */
object Assets {
    private const val BASE = "https://github.com/aftabigbehrouz-hub/SubPlayer/releases/download/data-v1/"

    data class Asset(
        val id: String,
        val label: String,
        val file: String,
        val sizeMb: Int,
        val sha256: String,
        val fallbackUrl: String?,
        val unzipInto: String? = null,   // folder to extract into (zip assets)
        val result: String = file        // path of the ready file/folder under the asset root
    ) {
        val url get() = BASE + file
    }

    val VOSK_DE = Asset(
        "vosk-de", "German speech model (fast)", "vosk-model-small-de-0.15.zip", 45,
        "b7e53c90b1f0a38456f4cd62b366ecd58803cd97cd42b06438e2c131713d5e43", "https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip",
        unzipInto = "", result = "vosk-model-small-de-0.15")
    val VOSK_EN = Asset(
        "vosk-en", "English speech model (fast)", "vosk-model-small-en-us-0.15.zip", 40,
        "30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498", "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
        unzipInto = "", result = "vosk-model-small-en-us-0.15")
    val WHISPER_BASE = Asset(
        "whisper-base", "Whisper Base", "ggml-base-q5_1.bin", 57,
        "422f1ae452ade6f30a004d7e5c6a43195e4433bc370bf23fac9cc591f01a8898", "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin")
    val WHISPER_SMALL = Asset(
        "whisper-small", "Whisper Small", "ggml-small-q5_1.bin", 182,
        "ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb", "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small-q5_1.bin")
    val VAD = Asset(
        "vad", "Voice detector", "ggml-silero-v5.1.2.bin", 1,
        "29940d98d42b91fbd05ce489f3ecf7c72f0a42f027e4875919a28fb4c04ea2cf", "https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v5.1.2.bin")
    val DICT_DE = Asset(
        "dict-de", "German dictionary", "dict-de-v1.zip", DICT_MB,
        "SHA_DICT", null, unzipInto = "dict", result = "dict/dict.db")
}

private const val DICT_MB = 0 // replaced with the real size at build time

object Downloader {

    fun root(ctx: Context) = File(ctx.filesDir, "assets").apply { mkdirs() }

    fun target(ctx: Context, a: Assets.Asset) = File(root(ctx), a.result)

    fun isReady(ctx: Context, a: Assets.Asset) =
        File(root(ctx), "${a.id}.ok").exists() && target(ctx, a).exists()

    /** Returns the ready file/folder, downloading + verifying + unpacking it if needed. */
    suspend fun ensure(ctx: Context, a: Assets.Asset, onProgress: (Int) -> Unit): File =
        withContext(Dispatchers.IO) {
            val root = root(ctx)
            val target = target(ctx, a)
            if (isReady(ctx, a)) return@withContext target

            val part = File(root, a.file + ".part")
            var error: Exception? = null
            for (u in listOfNotNull(a.url, a.fallbackUrl)) {
                try {
                    download(u, part, { ensureActive() }, onProgress)
                    error = null
                    break
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    error = e
                }
            }
            error?.let { throw IOException("Download failed: ${it.message}", it) }

            if (!sha256(part).equals(a.sha256, ignoreCase = true)) {
                part.delete()
                throw IOException("${a.label}: downloaded file failed the security check (checksum mismatch). Please try again.")
            }

            if (a.unzipInto != null) {
                val dest = File(root, a.unzipInto)
                target.deleteRecursively()
                unzip(part, dest)
                part.delete()
                if (!target.exists()) throw IOException("${a.label}: archive did not contain ${a.result}")
            } else {
                target.delete()
                if (!part.renameTo(target)) throw IOException("Could not save ${a.file}")
            }
            File(root, "${a.id}.ok").writeText("ok")
            target
        }

    private fun download(url: String, dest: File, check: () -> Unit, progress: (Int) -> Unit) {
        val existing = if (dest.exists()) dest.length() else 0L
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 20_000
            readTimeout = 30_000
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", "SubPlayer")
            if (existing > 0) setRequestProperty("Range", "bytes=$existing-")
        }
        try {
            val code = conn.responseCode
            if (code == 416) return
            if (code != HttpURLConnection.HTTP_OK && code != HttpURLConnection.HTTP_PARTIAL) throw IOException("HTTP $code")
            val append = code == HttpURLConnection.HTTP_PARTIAL
            val len = conn.contentLengthLong
            val total = if (len > 0) (if (append) existing + len else len) else -1L
            var done = if (append) existing else 0L
            conn.inputStream.use { input ->
                FileOutputStream(dest, append).use { out ->
                    val buf = ByteArray(128 * 1024)
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
            if (total > 0 && done < total) throw IOException("connection interrupted (will resume)")
        } finally {
            conn.disconnect()
        }
    }

    private fun sha256(f: File): String {
        val md = MessageDigest.getInstance("SHA-256")
        FileInputStream(f).use { input ->
            val buf = ByteArray(256 * 1024)
            while (true) {
                val r = input.read(buf)
                if (r < 0) break
                md.update(buf, 0, r)
            }
        }
        return md.digest().joinToString("") { "%02x".format(it) }
    }

    private fun unzip(zip: File, target: File) {
        target.mkdirs()
        val rootPath = target.canonicalPath + File.separator
        ZipInputStream(BufferedInputStream(FileInputStream(zip))).use { zis ->
            var e = zis.nextEntry
            while (e != null) {
                val f = File(target, e.name)
                if (!f.canonicalPath.startsWith(rootPath)) throw IOException("Unsafe zip entry: ${e.name}")
                if (e.isDirectory) f.mkdirs() else {
                    f.parentFile?.mkdirs()
                    FileOutputStream(f).use { zis.copyTo(it) }
                }
                zis.closeEntry()
                e = zis.nextEntry
            }
        }
    }
}
