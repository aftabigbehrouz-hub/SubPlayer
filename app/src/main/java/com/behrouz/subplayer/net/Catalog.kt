package com.behrouz.subplayer.net

import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.Callable
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * Discover — programmes that may be downloaded, the same sources as the Windows app:
 *  German: the public MediathekViewWeb catalogue (the open film list of the MediathekView program) of ARD, ZDF, 3sat,
 *          Arte, DW, KiKA, phoenix and the regional stations — every entry is a plain MP4 the broadcaster offers itself,
 *          often with the broadcaster's own subtitles.
 *  English: VOA Learning English (US government work, public domain; an archive since VOA stopped in March 2025),
 *          the NASA video library (public domain, usually with English subtitles) and podcasts the broadcasters publish
 *          for download (BBC Learning English 6 Minute English/Grammar/Vocabulary, BBC World Service, PBS, TED, NPR).
 */
object Catalog {

    data class Film(
        val channel: String, val topic: String, val title: String, val description: String,
        val timestamp: Long, val duration: Int, val urlWebsite: String, val urlSubtitle: String, val urlVideo: String,
        val audio: Boolean = false
    ) {
        val hasSubtitles get() = urlSubtitle.isNotEmpty()
        val length: String get() {
            if (duration <= 0) return ""
            val m = duration / 60
            return if (m >= 60) "${m / 60} h %02d min".format(m % 60) else if (m > 0) "$m min" else "$duration s"
        }
        val date: String get() = if (timestamp > 0) SimpleDateFormat("dd.MM.yyyy", Locale.GERMANY).format(Date(timestamp * 1000)) else ""
        val label: String get() = CHANNELS.entries.firstOrNull { it.value.equals(channel, true) }?.key ?: channel
        /** The link given to the importer: the file itself when known, otherwise the page. */
        val link: String get() = urlVideo.ifEmpty { urlWebsite }
    }

    data class Shelf(val title: String, val level: String, val why: String,
                     val text: String = "", val topic: String = "", val channels: List<String> = emptyList(),
                     val minSec: Int = 60, val maxSec: Int = 0,
                     val voaFeed: String = "", val podcast: String = "", val nasa: String = "")

    private const val API = "https://mediathekviewweb.de/api/query"
    private const val VOA = "https://learningenglish.voanews.com"
    private const val NASA = "https://images-api.nasa.gov"
    private const val UA = "SubPlayer (language-learning video player; Android)"

    val CHANNELS = linkedMapOf("ARD" to "ARD", "ZDF" to "ZDF", "3sat" to "3Sat", "Arte" to "ARTE.DE", "DW" to "DW", "KiKA" to "KiKA",
        "phoenix" to "PHOENIX", "BR" to "BR", "SWR" to "SWR", "WDR" to "WDR", "NDR" to "NDR", "MDR" to "MDR", "HR" to "HR",
        "RBB" to "RBB", "ORF" to "ORF", "SRF" to "SRF")

    val GERMAN = listOf(
        Shelf("logo! — news for kids", "A2–B1", "Today's news in short, simple sentences", topic = "logo!", channels = listOf("ZDF"), minSec = 120, maxSec = 1200),
        Shelf("Die Sendung mit der Maus", "A2–B1", "How things work, explained slowly and clearly", topic = "Die Sendung mit der Maus"),
        Shelf("Kinder & Wissen", "A2–B1", "Checker, pur+, Wissen macht Ah! — clear explanations", text = "Checker", channels = listOf("KiKA"), minSec = 300),
        Shelf("tagesschau — the news", "B1", "Short news programmes, several times a day", topic = "tagesschau", channels = listOf("ARD"), maxSec = 1200),
        Shelf("Terra X", "B1–B2", "History, nature and science with a narrator", topic = "Terra X", channels = listOf("ZDF")),
        Shelf("Quarks", "B2", "Science questions of everyday life", topic = "Quarks", channels = listOf("WDR")),
        Shelf("WISO — money & consumers", "B2–C1", "Prices, contracts, taxes and jobs", topic = "WISO", channels = listOf("ZDF")),
        Shelf("3sat Wissenschaft", "B2–C1", "Science documentaries — real, natural German", topic = "Wissenschaftsdoku", channels = listOf("3sat"), minSec = 900),
        Shelf("ARTE auf Deutsch", "B2–C1", "Culture, society and history from ARTE", channels = listOf("Arte"), minSec = 600)
    )

    val PODCASTS = listOf(
        Shelf("BBC 6 Minute English", "B1–B2", "Two presenters, one topic, useful words — BBC Learning English (audio)", podcast = "https://podcasts.files.bbci.co.uk/p02pc9tn.rss", channels = listOf("BBC")),
        Shelf("BBC 6 Minute Grammar", "B1", "One grammar point in six minutes (audio)", podcast = "https://podcasts.files.bbci.co.uk/p02pc9wq.rss", channels = listOf("BBC")),
        Shelf("BBC 6 Minute Vocabulary", "B1–B2", "Words and phrases explained (audio)", podcast = "https://podcasts.files.bbci.co.uk/p02pc9xz.rss", channels = listOf("BBC")),
        Shelf("BBC Global News Podcast", "C1", "The world's news from the BBC World Service (audio)", podcast = "https://podcasts.files.bbci.co.uk/p02nq0gn.rss", channels = listOf("BBC")),
        Shelf("BBC Witness History", "B2–C1", "History told by the people who were there (audio)", podcast = "https://podcasts.files.bbci.co.uk/p004t1hd.rss", channels = listOf("BBC")),
        Shelf("BBC The Documentary", "C1", "Documentaries from the World Service (audio)", podcast = "https://podcasts.files.bbci.co.uk/p02nq0lx.rss", channels = listOf("BBC")),
        Shelf("BBC Business Daily", "C1", "Money, work and the economy (audio)", podcast = "https://podcasts.files.bbci.co.uk/p002vsxs.rss", channels = listOf("BBC")),
        Shelf("PBS NewsHour", "C1", "The full US evening news programme (audio)", podcast = "https://www.pbs.org/newshour/feeds/rss/podcasts/show", channels = listOf("PBS")),
        Shelf("TED Talks Daily", "B2–C1", "Ideas worth spreading, one talk a day (audio)", podcast = "https://feeds.feedburner.com/TEDTalks_audio", channels = listOf("TED")),
        Shelf("NPR News Now", "B2–C1", "Five-minute news summary, every hour (audio)", podcast = "https://feeds.npr.org/500005/podcast.xml", channels = listOf("NPR"))
    )

    val ENGLISH = listOf(
        Shelf("English in a Minute", "A2–B1", "One expression explained in a minute (VOA)", voaFeed = "/api/zjk-rl-vomx-tpebpqqo"),
        Shelf("How to Pronounce", "A2–B1", "Sounds of American English, step by step (VOA)", voaFeed = "/api/zpivqol-vomx-tpe_guqi"),
        Shelf("Everyday Grammar Video", "B1", "Grammar in short, real situations (VOA)", voaFeed = "/api/z_riqtl-vomx-tpevtmqr"),
        Shelf("News Words", "B1", "Words from the news, in context (VOA)", voaFeed = "/api/z-k-ql-vomx-tpermqqi"),
        Shelf("VOA60: Watch & Learn", "B1", "Short reports with simple narration (VOA)", voaFeed = "/api/zyk-il-vomx-tpetpqqm"),
        Shelf("NASA — space & science", "B2–C1", "Real English from scientists and engineers, with subtitles", nasa = "Artemis Moon"),
        Shelf("NASA — Earth & climate", "B2–C1", "How our planet works, explained by NASA", nasa = "Earth climate")
    ) + PODCASTS.take(4) + PODCASTS.subList(7, 9)

    // ------------------------------------------------------------------ HTTP

    private fun connect(url: String, post: String? = null): String {
        val c = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 8_000; readTimeout = 25_000
            setRequestProperty("User-Agent", UA)
            if (post != null) {
                requestMethod = "POST"; doOutput = true
                setRequestProperty("Content-Type", "text/plain")
            }
        }
        try {
            if (post != null) c.outputStream.use { it.write(post.toByteArray(Charsets.UTF_8)) }
            if (c.responseCode !in 200..299) throw IOException("HTTP ${c.responseCode}")
            return c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally { c.disconnect() }
    }

    fun get(url: String) = connect(url)
    private fun enc(s: String) = URLEncoder.encode(s, "UTF-8")

    // ------------------------------------------------------------------ German catalogue

    private fun https(u: String) = if (u.startsWith("http://")) "https://" + u.substring(7) else u

    /** HD/low links are shortened as "<n>|<suffix>" = first n characters of the normal link + suffix. */
    fun full(base: String, v: String): String {
        val m = Regex("""^(\d+)\|(.*)$""").find(v.trim()) ?: return v.trim()
        val n = m.groupValues[1].toInt()
        return if (base.isNotEmpty() && n <= base.length) base.substring(0, n) + m.groupValues[2] else v.trim()
    }

    fun buildQuery(text: String = "", channels: List<String> = emptyList(), topic: String = "", title: String = "",
                   minSec: Int = 0, maxSec: Int = 0, offset: Int = 0, size: Int = 30): String {
        val qs = JSONArray()
        fun q(field: String, v: String) { qs.put(JSONObject().put("fields", JSONArray().put(field)).put("query", v)) }
        if (text.isNotBlank()) qs.put(JSONObject().put("fields", JSONArray().put("title").put("topic")).put("query", text.trim()))
        if (topic.isNotBlank()) q("topic", topic.trim())
        if (title.isNotBlank()) q("title", title.trim())
        for (c in channels) qs.put(JSONObject().put("fields", JSONArray().put("channel")).put("query", (CHANNELS[c] ?: c).lowercase()))
        val o = JSONObject().put("queries", qs).put("sortBy", "timestamp").put("sortOrder", "desc").put("future", false)
            .put("offset", offset).put("size", size)
        if (minSec > 0) o.put("duration_min", minSec)
        if (maxSec > 0) o.put("duration_max", maxSec)
        return o.toString()
    }

    fun parseResponse(json: String): Pair<List<Film>, Int> {
        val o = JSONObject(json)
        if (!o.isNull("err") && o.optString("err").isNotEmpty()) throw IOException("Catalogue error: ${o.optString("err")}")
        val r = o.optJSONObject("result") ?: return emptyList<Film>() to 0
        val arr = r.optJSONArray("results") ?: JSONArray()
        val films = ArrayList<Film>()
        for (i in 0 until arr.length()) {
            val d = arr.getJSONObject(i)
            val base = d.optString("url_video").trim()
            val video = https(base).ifEmpty { https(full(base, d.optString("url_video_hd"))) }
            if (!video.startsWith("http")) continue
            films.add(Film(d.optString("channel"), d.optString("topic").trim(), d.optString("title").trim(), d.optString("description").trim(),
                d.optLong("timestamp"), d.optInt("duration"), d.optString("url_website").trim(), https(d.optString("url_subtitle").trim()), video))
        }
        val total = r.optJSONObject("queryInfo")?.optInt("totalResults", films.size) ?: films.size
        return dedupe(films) to total
    }

    /** The same programme is often listed by several channels (ARD and the regional station) — keep one. */
    fun dedupe(films: List<Film>): List<Film> {
        val seen = HashSet<String>()
        return films.filter { seen.add(it.title.lowercase().replace(Regex("\\W+"), "") + "|" + it.duration / 30) }
    }

    fun searchGerman(text: String = "", channels: List<String> = emptyList(), topic: String = "", title: String = "",
                     minSec: Int = 0, maxSec: Int = 0, offset: Int = 0, size: Int = 30, subtitlesOnly: Boolean = false): Pair<List<Film>, Int> {
        val (films, total) = parseResponse(connect(API, buildQuery(text, channels, topic, title, minSec, maxSec, offset, if (subtitlesOnly) size * 3 else size)))
        return (if (subtitlesOnly) films.filter { it.hasSubtitles }.take(size) else films) to total
    }

    // ------------------------------------------------------------------ English

    private fun clean(t: String) = com.behrouz.subplayer.subs.Ttml.unescape(t.replace("<![CDATA[", "").replace("]]>", "")
        .replace(Regex("<[^>]+>"), " ")).replace(Regex("\\s+"), " ").trim()

    private fun tag(item: String, name: String) =
        Regex("<$name[^>]*>(.*?)</$name>", RegexOption.DOT_MATCHES_ALL).find(item)?.groupValues?.get(1)?.let { clean(it) } ?: ""

    private fun rfc822(s: String): Long = runCatching {
        SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss Z", Locale.US).parse(s.trim())!!.time / 1000
    }.recoverCatching { SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss zzz", Locale.US).parse(s.trim())!!.time / 1000 }.getOrDefault(0)

    private fun items(xml: String) = Regex("<item>(.*?)</item>", RegexOption.DOT_MATCHES_ALL).findAll(xml).map { it.groupValues[1] }

    fun voaFeed(path: String, size: Int = 12): List<Film> = items(get(VOA + path)).take(size).mapNotNull { it ->
        val link = tag(it, "link").ifEmpty { return@mapNotNull null }
        val title = tag(it, "title")
        Film("VOA", Regex("^(.*?):").find(title)?.groupValues?.get(1) ?: "VOA Learning English", title, tag(it, "description").take(600),
            rfc822(tag(it, "pubDate")), 0, link, "", "")
    }.toList()

    fun voaSearch(text: String, size: Int = 20): List<Film> {
        val html = get("$VOA/s?k=${enc(text)}&tab=video")
        val seen = HashSet<String>()
        return Regex("""<a[^>]+href="(/a/[^"]+\.html)"[^>]*>(.*?)</a>""", RegexOption.DOT_MATCHES_ALL).findAll(html).mapNotNull { m ->
            val title = clean(m.groupValues[2]); val link = m.groupValues[1]
            if (title.isEmpty() || !seen.add(link)) null
            else Film("VOA", Regex("^(.*?):").find(title)?.groupValues?.get(1) ?: "VOA Learning English", title, "", 0, 0, VOA + link, "", "")
        }.take(size).toList()
    }

    fun nasaSearch(text: String, size: Int = 20, page: Int = 1): Pair<List<Film>, Int> {
        val col = JSONObject(get("$NASA/search?q=${enc(text)}&media_type=video&page_size=$size&page=$page")).optJSONObject("collection") ?: JSONObject()
        val arr = col.optJSONArray("items") ?: JSONArray()
        val out = ArrayList<Film>()
        for (i in 0 until arr.length()) {
            val d = arr.getJSONObject(i).optJSONArray("data")?.optJSONObject(0) ?: continue
            val id = d.optString("nasa_id")
            if (id.isEmpty()) continue
            val ts = runCatching { SimpleDateFormat("yyyy-MM-dd", Locale.US).parse(d.optString("date_created").take(10))!!.time / 1000 }.getOrDefault(0)
            out.add(Film("NASA", d.optString("center").ifEmpty { "NASA" }, d.optString("title").ifEmpty { id }, clean(d.optString("description")).take(900),
                ts, 0, "https://images.nasa.gov/details/" + enc(id).replace("+", "%20"), "", ""))
        }
        return out to (col.optJSONObject("metadata")?.optInt("total_hits", out.size) ?: out.size)
    }

    /** (mp4 of medium size, .srt or .vtt) of a NASA video. */
    fun nasaAsset(id: String): Pair<String, String> {
        val arr = JSONObject(get("$NASA/asset/" + enc(id).replace("+", "%20"))).optJSONObject("collection")?.optJSONArray("items") ?: JSONArray()
        val hrefs = (0 until arr.length()).map { arr.getJSONObject(it).optString("href").replace("http://", "https://").replace(" ", "%20") }
        val mp4 = listOf("~medium.mp4", "~large.mp4", "~mobile.mp4", "~small.mp4", "~orig.mp4").firstNotNullOfOrNull { suf -> hrefs.firstOrNull { it.endsWith(suf) } } ?: ""
        val sub = hrefs.firstOrNull { it.lowercase().endsWith(".srt") } ?: hrefs.firstOrNull { it.lowercase().endsWith(".vtt") } ?: ""
        return mp4 to sub
    }

    private fun secs(t: String): Int {
        val s = t.trim(); if (s.all { it.isDigit() } && s.isNotEmpty()) return s.toInt()
        return s.split(':').mapNotNull { it.toIntOrNull() }.fold(0) { a, b -> a * 60 + b }
    }

    fun parsePodcast(xml: String, channel: String, size: Int = 15): List<Film> {
        val show = Regex("<channel>.*?<title>(.*?)</title>", RegexOption.DOT_MATCHES_ALL).find(xml)?.groupValues?.get(1)?.let { clean(it) } ?: channel
        return items(xml).mapNotNull { it ->
            val audio = Regex("""<enclosure[^>]*\burl="([^"]+)"""").find(it)?.groupValues?.get(1)?.let { u -> com.behrouz.subplayer.subs.Ttml.unescape(u) }
                ?: return@mapNotNull null
            Film(channel, show, tag(it, "title"), tag(it, "description").take(900), rfc822(tag(it, "pubDate")),
                secs(tag(it, "itunes:duration")), tag(it, "link"), "", audio, audio = true)
        }.take(size).toList()
    }

    private val podcastCache = HashMap<String, Pair<Long, List<Film>>>()

    fun podcastFeed(sh: Shelf, size: Int = 15): List<Film> {
        val now = System.currentTimeMillis()
        synchronized(podcastCache) { podcastCache[sh.podcast]?.let { if (now - it.first < 900_000 && it.second.size >= size) return it.second.take(size) } }
        val f = parsePodcast(get(sh.podcast), sh.channels.firstOrNull() ?: "Podcast", maxOf(size, 60))
        synchronized(podcastCache) { podcastCache[sh.podcast] = now to f }
        return f.take(size)
    }

    fun podcastSearch(text: String, size: Int = 40): List<Film> {
        val pool = Executors.newFixedThreadPool(5)
        try {
            val all = pool.invokeAll(PODCASTS.map { sh -> Callable { runCatching { podcastFeed(sh, 60) }.getOrDefault(emptyList()) } }, 40, TimeUnit.SECONDS)
                .flatMap { runCatching { it.get() }.getOrDefault(emptyList()) }
            val words = text.lowercase().split(Regex("\\s+")).filter { it.isNotEmpty() }
            return all.filter { f -> words.all { w -> (f.title + " " + f.description + " " + f.topic).lowercase().contains(w) } }
                .sortedByDescending { it.timestamp }.take(size)
        } finally { pool.shutdownNow() }
    }

    fun shelfFilms(sh: Shelf, size: Int = 10): List<Film> = when {
        sh.podcast.isNotEmpty() -> podcastFeed(sh, size)
        sh.voaFeed.isNotEmpty() -> voaFeed(sh.voaFeed, size)
        sh.nasa.isNotEmpty() -> nasaSearch(sh.nasa, size).first
        else -> searchGerman(sh.text, sh.channels, sh.topic, "", sh.minSec, sh.maxSec, 0, size).first
    }

    fun searchEnglish(text: String, size: Int = 30): List<Film> {
        val out = ArrayList<Film>()
        runCatching { voaSearch(text, size) }.getOrNull()?.let { out.addAll(it) }
        runCatching { podcastSearch(text, size) }.getOrNull()?.let { out.addAll(it) }
        runCatching { nasaSearch(text, size).first }.getOrNull()?.let { out.addAll(it) }
        return out
    }

    // ------------------------------------------------------------------ find a broadcaster page in the catalogue

    private fun normUrl(u: String) = u.trim().lowercase().replace(Regex("^https?://(www\\.)?"), "").substringBefore('?').substringBefore('#').trimEnd('/')

    private val GENERIC = setOf("video", "videos", "sendungen", "sendung", "dokus", "doku", "dokumentation", "reportagen", "magazine", "filme",
        "serien", "nachrichten", "wissen", "kultur", "gesellschaft", "politik", "panorama", "multimedia", "de", "mediathek", "gespraeche",
        "comedy", "show", "kinder", "page", "p", "programm", "unterhaltung", "verbraucher")

    private fun variants(t: String): List<String> {
        var acc = listOf("")
        for (w in t.split(' ')) {
            val alt = w.replace("ue", "ü").replace("oe", "ö").replace("ae", "ä")
            acc = acc.flatMap { a -> (if (alt == w) listOf(w) else listOf(w, alt)).map { (if (a.isEmpty()) "" else "$a ") + it } }
        }
        return acc.take(4)
    }

    fun urlTopics(pageUrl: String): List<String> {
        val segs = runCatching { URL(pageUrl).path }.getOrDefault("").split('/').filter { it.isNotEmpty() }.dropLast(1)
        val out = ArrayList<String>()
        for (seg in segs) {
            val t = seg.lowercase().replace(Regex("-\\d+$"), "").replace('-', ' ').trim()
            if (t.length < 3 || t in GENERIC || t.all { it.isDigit() }) continue
            for (v in variants(t)) if (v !in out) out.add(v)
        }
        return out.take(6)
    }

    fun titleQueries(pageTitle: String): List<String> {
        var t = if ('|' in pageTitle) pageTitle.replace(Regex("""\s*\|\s*[^|]*$"""), "") else pageTitle
        t = t.replace(Regex("""\b(ZDFmediathek|ARD Mediathek|Mediathek|ZDFheute|ARTE|3sat|KiKA|phoenix|DW)\b\s*$""", RegexOption.IGNORE_CASE), "").trim(' ', '-', '–', '|', ':')
        val out = ArrayList<String>()
        fun add(x: String) {
            val y = x.replace(Regex("""[^\p{L}\p{N}\s]"""), " ").split(Regex("\\s+")).filter { it.isNotEmpty() }.take(7).joinToString(" ")
            if (y.length >= 4 && out.none { it.equals(y, true) }) out.add(y)
        }
        add(t)
        t.split(Regex("""\s+[|–-]\s+|:\s+""")).map { it.trim() }.filter { it.length >= 4 }.sortedByDescending { it.length }.forEach { add(it) }
        return out.take(4)
    }

    /** The catalogue's entry for a broadcaster page (same web address; if [similar], else the closest title). */
    fun lookup(pageUrl: String, pageTitle: String, similar: Boolean): Film? {
        val want = normUrl(pageUrl); val tail = want.substringAfterLast('/')
        fun exact(films: List<Film>) = films.firstOrNull { val u = normUrl(it.urlWebsite); u == want || (tail.length >= 6 && u.substringAfterLast('/') == tail) }
        val pool = ArrayList<Film>()
        for (topic in urlTopics(pageUrl)) {
            val films = runCatching { searchGerman(topic = topic, size = 50).first }.getOrNull() ?: continue
            exact(films)?.let { return it }; pool.addAll(films)
        }
        for (q in titleQueries(pageTitle)) {
            for (byTitle in listOf(true, false)) {
                val films = runCatching { if (byTitle) searchGerman(title = q, size = 50).first else searchGerman(text = q, size = 50).first }.getOrNull() ?: continue
                exact(films)?.let { return it }; pool.addAll(films)
                if (films.isNotEmpty()) break
            }
        }
        if (pool.isEmpty() || !similar || pageTitle.isBlank()) return null
        fun sim(a: String, b: String): Double {
            val A = Regex("\\w+").findAll(a.lowercase()).map { it.value }.toSet(); val B = Regex("\\w+").findAll(b.lowercase()).map { it.value }.toSet()
            return (A intersect B).size.toDouble() / maxOf(1, (A union B).size)
        }
        val host = want.substringBefore('/')
        val same = pool.filter { normUrl(it.urlWebsite).substringBefore('/') == host }.ifEmpty { pool }
        val best = same.maxByOrNull { maxOf(sim(it.title, pageTitle), sim("${it.topic} ${it.title}", pageTitle)) } ?: return null
        return if (maxOf(sim(best.title, pageTitle), sim("${best.topic} ${best.title}", pageTitle)) >= 0.55) best else null
    }
}
