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

    /** [subtitleUrl]: the broadcaster's own subtitles (TTML / VTT / SRT), if it has them. [audio]: a podcast episode. */
    data class Found(val videoUrl: String, val title: String, val subtitleUrl: String = "", val audio: Boolean = false)

    private val DIRECT = Regex("""\.(mp4|m4v|webm|mov|mp3|m4a|aac|ogg|opus|wav)(\?.*)?$""", RegexOption.IGNORE_CASE)
    private val AUDIO = Regex("""\.(mp3|m4a|aac|ogg|opus|wav)(\?.*)?$""", RegexOption.IGNORE_CASE)
    private val HLS = Regex("""\.m3u8(\?.*)?$""", RegexOption.IGNORE_CASE)
    private val VIDEO_URL = Regex("""https?://[^"'\s<>\\]+\.(?:mp4|m4v|webm)(?:\?[^"'\s<>\\]*)?(?=["'\s<>\\]|$)""", RegexOption.IGNORE_CASE)
    private val SUB_URL = Regex("""https?://[^"'\s<>\\]+\.(?:vtt|xml|ttml)(?:\?[^"'\s<>\\]*)?(?=["'\s<>\\]|$)""", RegexOption.IGNORE_CASE)
    private val TITLE = Regex("""<title[^>]*>(.*?)</title>""", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))
    private val OG_TITLE = Regex("""<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)""", RegexOption.IGNORE_CASE)
    private val ARTE = Regex("""arte\.tv/(de|fr|en|es|pl|it)/videos/(\d{6}-\d{3}-[A-Z])""", RegexOption.IGNORE_CASE)
    private val ALT_VERSION = Regex("""(audiodeskription|/ad/|_ad_|-ad-|_ad\.|gebaerdensprache|_dgs|klaresprache|klare-sprache|_ks_)""", RegexOption.IGNORE_CASE)

    val BROADCASTERS = listOf("ardmediathek.de", "ard.de", "tagesschau.de", "sportschau.de", "zdf.de", "zdfheute.de", "3sat.de", "arte.tv",
        "dw.com", "kika.de", "phoenix.de", "br.de", "swr.de", "wdr.de", "ndr.de", "mdr.de", "hr.de", "rbb-online.de", "rbb24.de", "sr.de",
        "radiobremen.de", "funk.net", "orf.at", "srf.ch", "zdftivi.de", "planet-wissen.de", "quarks.de")

    private fun host(url: String) = runCatching { java.net.URL(url.trim()).host.lowercase() }.getOrDefault("")
    fun isBroadcaster(url: String) = host(url).let { h -> BROADCASTERS.any { h == it || h.endsWith(".$it") } }
    private fun pathOf(u: String) = runCatching { java.net.URL(u).let { it.path + (it.query?.let { q -> "?$q" } ?: "") } }.getOrDefault(u)
    private fun stem(u: String) = runCatching { java.net.URL(u).path.substringAfterLast('/').substringBeforeLast('.') }.getOrDefault("").ifEmpty { "video" }

    /** Finds the video (or podcast audio) behind a link (no download). */
    suspend fun resolve(url: String): Found = withContext(Dispatchers.IO) {
        val u = url.trim()
        if (!u.startsWith("http://") && !u.startsWith("https://")) throw IOException("That doesn't look like a web link")
        val pq = pathOf(u)
        if (DIRECT.containsMatchIn(pq)) return@withContext Found(u, java.net.URLDecoder.decode(stem(u), "UTF-8"), audio = AUDIO.containsMatchIn(pq))
        if (HLS.containsMatchIn(pq)) throw IOException("That is a live stream (.m3u8). The phone app downloads video files only — the Windows app can save streams.")
        Regex("""images\.nasa\.gov/details/([^/?#]+)""").find(u)?.let { m ->
            val id = java.net.URLDecoder.decode(m.groupValues[1], "UTF-8")
            val (mp4, sub) = Catalog.nasaAsset(id)
            if (mp4.isEmpty()) throw IOException("This NASA item has no video file")
            return@withContext Found(mp4, id, sub)
        }
        ardId(u)?.let { id -> runCatching { ardItem(id) }.getOrElse { e -> if (e is NoVideo) throw e else null }?.let { return@withContext it } }
        val page = fetchText(u, 5_000_000)
        var title = (OG_TITLE.find(page)?.groupValues?.get(1) ?: TITLE.find(page)?.groupValues?.get(1) ?: "")
            .replace(Regex("<[^>]+>"), "").let { com.behrouz.subplayer.subs.Ttml.unescape(it) }.trim()
        if ("{{" in title) title = ""
        val broadcaster = isBroadcaster(u)
        if (broadcaster) Catalog.lookup(u, title, similar = false)?.let { return@withContext fromFilm(it) }
        var found = findInPage(page)
        if (found != null && broadcaster && found.subtitleUrl.isEmpty()) found = found.copy(subtitleUrl = findSubtitle(page))
        if (found == null && broadcaster && title.isNotEmpty()) found = Catalog.lookup(u, title, similar = true)?.let { fromFilm(it) }
        if (found == null && ARTE.containsMatchIn(u))
            throw IOException("Arte offers this programme only as a stream, which the phone app can't save. The Windows app can, or find it in Discover.")
        if (found == null && "youtube.com/iframe_api" in page && ("youtube.com/embed" in page || "voanews.com" in u))
            throw IOException("This lesson is only offered as a YouTube video, which SubPlayer can't download (YouTube's terms forbid it).")
        found ?: throw IOException("No downloadable video found on that page. ARD, ZDF, 3sat, Arte and DW programmes: find them in Discover.")
    }

    fun fromFilm(f: Catalog.Film) = Found(f.urlVideo, if (f.title.contains(f.topic, true)) f.title else "${f.topic} – ${f.title}", f.urlSubtitle, f.audio)

    fun findSubtitle(page: String): String {
        val text = page.replace("\\/", "/").replace("\\u002F", "/").replace("&amp;", "&")
        return SUB_URL.findAll(text).map { it.value }.firstOrNull {
            Regex("(untertitel|subtitle|/ut/|_ut|caption|ebutt|webvtt|\\.vtt)", RegexOption.IGNORE_CASE).containsMatchIn(it) && "sitemap" !in it.lowercase()
        } ?: ""
    }

    /** ARD Mediathek item ids are base64 of "crid://…" (they start with Y3JpZDovL). */
    fun ardId(url: String): String? {
        if (!host(url).endsWith("ardmediathek.de")) return null
        return runCatching { java.net.URL(url).path }.getOrDefault("").split('/').lastOrNull { it.startsWith("Y3JpZDovL") }
    }

    class NoVideo(msg: String) : IOException(msg)

    /** Every (path, value) pair of a JSON tree. */
    private fun walk(o: Any?, path: List<String>, out: MutableList<Pair<List<String>, Any?>>) {
        when (o) {
            is org.json.JSONObject -> o.keys().forEach { k -> walk(o.opt(k), path + k, out) }
            is org.json.JSONArray -> for (i in 0 until o.length()) walk(o.opt(i), path + i.toString(), out)
            else -> out.add(path to o)
        }
    }

    /** ARD Mediathek player data: MP4 files in several sizes (up to 720p preferred) + subtitles. */
    fun ardItem(id: String): Found {
        val data = org.json.JSONObject(fetchText("https://api.ardmediathek.de/page-gateway/pages/ard/item/$id?devicetype=pc&embedded=true", 8_000_000))
        val all = ArrayList<Pair<List<String>, Any?>>(); walk(data, emptyList(), all)
        val mp4 = ArrayList<Pair<String, Int>>(); val subs = ArrayList<String>(); var title = ""
        val height = HashMap<String, Int>()
        for ((path, v) in all) {
            val key = path.lastOrNull() ?: continue
            if (key == "title" && title.isEmpty() && path.size <= 3 && v is String) title = v
            if (key == "forcedLabel" || key == "maxHResolutionPx") {
                // the size beside each file ("HD 720p", or the picture WIDTH, 1280 = 720p) is more reliable than its name
                var node: Any? = data
                for (k in path.dropLast(1)) node = if (node is org.json.JSONArray) node.opt(k.toInt()) else (node as? org.json.JSONObject)?.opt(k)
                val fu = (node as? org.json.JSONObject)?.optString("url").orEmpty().let { if (it.startsWith("//")) "https:$it" else it }
                val h = if (v is String) Regex("(\\d{3,4})p").find(v)?.groupValues?.get(1)?.toInt() ?: 0 else ((v as? Number)?.toInt() ?: 0) * 9 / 16
                if (fu.isNotEmpty() && h > 0) height[fu] = h
            }
            if (v !is String) continue
            var s = v.trim(); if (s.startsWith("//")) s = "https:$s"
            if (!s.startsWith("http")) continue
            val low = s.lowercase().substringBefore('?')
            if (low.endsWith(".mp4")) {
                val m = Regex("(\\d{3,4})p").find(low)
                val m2 = Regex("_(\\d{3,4})x(\\d{3,4})").find(low)
                mp4.add(s to (m2?.groupValues?.get(2)?.toInt() ?: m?.groupValues?.get(1)?.toInt() ?: 0))
            } else if ("subtitle" in path.joinToString("/").lowercase() && (low.endsWith(".vtt") || low.endsWith(".xml") || "ebutt" in low || "webvtt" in low)) subs.add(s)
        }
        val cands = mp4.map { (u, h) -> u to (height[u] ?: h) }.let { c -> c.filter { !ALT_VERSION.containsMatchIn(it.first) }.ifEmpty { c } }
        if (cands.isEmpty()) throw NoVideo("This ARD video isn't available as a file (it may have expired, or be a live stream)")
        val upto = cands.filter { it.second in 1..720 }
        val best = upto.maxByOrNull { it.second }?.first ?: cands.filter { it.second > 720 }.minByOrNull { it.second }?.first ?: cands.maxBy { score(it.first) }.first
        val sub = subs.firstOrNull { it.lowercase().substringBefore('?').endsWith(".vtt") } ?: subs.firstOrNull() ?: ""
        return Found(best, title.ifEmpty { "ARD video" }, sub)
    }

    /** The broadcaster's subtitles (null if missing or unreadable). */
    suspend fun subtitles(url: String): List<com.behrouz.subplayer.subs.Cue>? = withContext(Dispatchers.IO) {
        if (url.isEmpty()) return@withContext null
        runCatching { com.behrouz.subplayer.subs.Ttml.parseAny(fetchText(url, 10_000_000)) }.getOrNull()?.takeIf { it.size >= 3 }
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

    /** Downloads the video into Movies/SubPlayer (podcast audio into Music/SubPlayer) and returns its Uri. */
    suspend fun download(ctx: Context, f: Found, check: () -> Unit, progress: (Int, Long) -> Unit): Uri = withContext(Dispatchers.IO) {
        val ext = if (f.audio) (AUDIO.find(pathOf(f.videoUrl))?.groupValues?.get(1)?.lowercase() ?: "mp3") else "mp4"
        val name = f.title.replace(Regex("[^\\p{L}\\p{N} ._-]+"), " ").replace(Regex("\\s+"), " ").trim().take(70).ifEmpty { "video" } + ".$ext"
        val c = open(f.videoUrl)
        val total = c.contentLengthLong
        var uri: Uri? = null
        var file: File? = null
        try {
            val out: OutputStream = if (Build.VERSION.SDK_INT >= 29) {
                // videos go to Movies/SubPlayer, podcast episodes to Music/SubPlayer
                val v = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, name)
                    put(MediaStore.MediaColumns.MIME_TYPE, if (f.audio) (if (ext == "mp3") "audio/mpeg" else "audio/$ext") else "video/mp4")
                    put(MediaStore.MediaColumns.RELATIVE_PATH, (if (f.audio) Environment.DIRECTORY_MUSIC else Environment.DIRECTORY_MOVIES) + "/SubPlayer")
                    put(MediaStore.MediaColumns.IS_PENDING, 1)
                }
                val coll = if (f.audio) MediaStore.Audio.Media.EXTERNAL_CONTENT_URI else MediaStore.Video.Media.EXTERNAL_CONTENT_URI
                uri = ctx.contentResolver.insert(coll, v) ?: throw IOException("Could not create the file")
                ctx.contentResolver.openOutputStream(uri!!) ?: throw IOException("Could not write the video file")
            } else {
                val dir = File(ctx.getExternalFilesDir(if (f.audio) Environment.DIRECTORY_MUSIC else Environment.DIRECTORY_MOVIES), "SubPlayer").apply { mkdirs() }
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
                ctx.contentResolver.update(uri!!, ContentValues().apply { put(MediaStore.MediaColumns.IS_PENDING, 0) }, null, null)
                uri!!
            } else Uri.fromFile(file)
        } catch (e: Throwable) {
            uri?.let { runCatching { ctx.contentResolver.delete(it, null, null) } }
            file?.delete()
            throw e
        } finally { c.disconnect() }
    }
}
