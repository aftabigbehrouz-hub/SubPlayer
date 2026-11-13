package com.behrouz.subplayer.net

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL

/**
 * Opens video links: a direct .mp4/.webm link, or a web page that offers an MP4 file (Tagesschau and many
 * news / public-broadcaster pages). The video is downloaded to Movies/SubPlayer so it can be watched offline
 * and transcribed. Services whose terms forbid downloading (YouTube, Instagram, TikTok, Netflix…) are refused.
 */
object LinkImporter {

    private val REFUSED = listOf("youtube.com", "youtu.be", "instagram.com", "tiktok.com", "facebook.com", "fb.watch",
        "netflix.com", "x.com", "twitter.com", "disneyplus.com", "primevideo.com", "joyn.de")

    fun refusedReason(url: String): String? {
        val host = runCatching { Uri.parse(url.trim()).host.orEmpty().lowercase() }.getOrDefault("")
        val hit = REFUSED.firstOrNull { host == it || host.endsWith(".$it") } ?: return null
        return "SubPlayer can't download from ${hit.substringBefore('.').replaceFirstChar { it.uppercase() }}: its terms don't allow it. " +
            "Videos already on your phone open with the folder button or “Open with ▸ SubPlayer”."
    }

    data class Found(val videoUrl: String, val title: String)

    private val DIRECT = Regex("""\.(mp4|m4v|webm|mov)(\?.*)?$""", RegexOption.IGNORE_CASE)
    private val VIDEO_URL = Regex("""https?://[^"'\s<>\\]+\.(?:mp4|m4v|webm)(?:\?[^"'\s<>\\]*)?(?=["'\s<>\\]|$)""", RegexOption.IGNORE_CASE)
    private val TITLE = Regex("""<title[^>]*>(.*?)</title>""", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))
    private val OG_TITLE = Regex("""<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)""", RegexOption.IGNORE_CASE)

    /** Finds the video file behind a link (pure: no download). */
    suspend fun resolve(url: String): Found = withContext(Dispatchers.IO) {
        val u = url.trim()
        if (!u.startsWith("http://") && !u.startsWith("https://")) throw IOException("That doesn't look like a web link")
        if (DIRECT.containsMatchIn(Uri.parse(u).path.orEmpty() + (Uri.parse(u).query?.let { "?$it" } ?: ""))) {
            return@withContext Found(u, Uri.parse(u).lastPathSegment?.substringBeforeLast('.') ?: "video")
        }
        val html = fetchText(u, 5_000_000)
        findInPage(html) ?: throw IOException("No downloadable video found on that page")
    }

    /** Picks the best MP4 in a page (Tagesschau names qualities webs < webm < webl < webxl < webxxl). */
    fun findInPage(html: String): Found? {
        val text = html.replace("\\/", "/").replace("\\u002F", "/").replace("&amp;", "&")
        val urls = VIDEO_URL.findAll(text).map { it.value }.distinct().toList()
        if (urls.isEmpty()) return null
        val best = urls.maxByOrNull { score(it) }!!
        val title = (OG_TITLE.find(html)?.groupValues?.get(1) ?: TITLE.find(html)?.groupValues?.get(1) ?: "video")
            .replace(Regex("<[^>]+>"), "").replace("&amp;", "&").replace("&#039;", "'").replace("&quot;", "\"").trim()
        return Found(best, title)
    }

    /** Medium quality first: good on a phone, smaller download. */
    fun score(u: String): Int {
        val l = u.lowercase()
        var s = when {
            ".webl." in l -> 60
            ".webxl." in l -> 55
            ".webm." in l && "h264" in l -> 50
            ".webxxl." in l -> 40
            ".webs." in l -> 30
            else -> 45
        }
        if ("h264" in l) s += 3
        if (l.contains("trailer") || l.contains("teaser")) s -= 20
        return s
    }

    private fun open(url: String): HttpURLConnection {
        var current = url
        repeat(5) {
            val c = (URL(current).openConnection() as HttpURLConnection).apply {
                connectTimeout = 20_000; readTimeout = 60_000; instanceFollowRedirects = false
                setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14) SubPlayer")
            }
            val code = c.responseCode
            if (code in 300..399) {
                val loc = c.getHeaderField("Location") ?: throw IOException("Redirect without location")
                current = URL(URL(current), loc).toString(); c.disconnect()
            } else if (code in 200..299) return c
            else { c.disconnect(); throw IOException("The site answered HTTP $code") }
        }
        throw IOException("Too many redirects")
    }

    private fun fetchText(url: String, max: Int): String {
        val c = open(url)
        try {
            val bytes = c.inputStream.use { input ->
                val out = java.io.ByteArrayOutputStream(); val buf = ByteArray(64 * 1024)
                while (out.size() < max) { val r = input.read(buf); if (r < 0) break; out.write(buf, 0, r) }
                out.toByteArray()
            }
            return String(bytes, Charsets.UTF_8)
        } finally { c.disconnect() }
    }

    /** Downloads the video into Movies/SubPlayer and returns its Uri. */
    suspend fun download(ctx: Context, f: Found, check: () -> Unit, progress: (Int, Long) -> Unit): Uri = withContext(Dispatchers.IO) {
        val name = f.title.replace(Regex("[^\\p{L}\\p{N} ._-]+"), " ").replace(Regex("\\s+"), " ").trim().take(70).ifEmpty { "video" } + ".mp4"
        val c = open(f.videoUrl)
        val total = c.contentLengthLong
        var uri: Uri? = null
        var file: File? = null
        try {
            val out: OutputStream = if (Build.VERSION.SDK_INT >= 29) {
                val v = ContentValues().apply {
                    put(MediaStore.Video.Media.DISPLAY_NAME, name)
                    put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
                    put(MediaStore.Video.Media.RELATIVE_PATH, Environment.DIRECTORY_MOVIES + "/SubPlayer")
                    put(MediaStore.Video.Media.IS_PENDING, 1)
                }
                uri = ctx.contentResolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, v) ?: throw IOException("Could not create the video file")
                ctx.contentResolver.openOutputStream(uri!!) ?: throw IOException("Could not write the video file")
            } else {
                val dir = File(ctx.getExternalFilesDir(Environment.DIRECTORY_MOVIES), "SubPlayer").apply { mkdirs() }
                file = File(dir, name); file!!.outputStream()
            }
            out.use { o ->
                c.inputStream.use { input ->
                    val buf = ByteArray(256 * 1024); var done = 0L; var last = -1
                    while (true) {
                        check()
                        val r = input.read(buf); if (r < 0) break
                        o.write(buf, 0, r); done += r
                        val p = if (total > 0) (done * 100 / total).toInt() else -1
                        if (p != last) { last = p; progress(p, done) }
                    }
                }
            }
            if (Build.VERSION.SDK_INT >= 29) {
                ctx.contentResolver.update(uri!!, ContentValues().apply { put(MediaStore.Video.Media.IS_PENDING, 0) }, null, null)
                uri!!
            } else Uri.fromFile(file)
        } catch (e: Throwable) {
            uri?.let { runCatching { ctx.contentResolver.delete(it, null, null) } }
            file?.delete()
            throw e
        } finally { c.disconnect() }
    }
}
