package com.behrouz.subplayer.subs

import kotlin.math.roundToLong

/**
 * Broadcaster subtitles: TTML / EBU-TT-D (ARD, ZDF, 3sat …) as well as .vtt and .srt. Pure Kotlin (no Android XML
 * classes) so it is unit-tested on the computer. Line breaks are kept, colours and styles dropped, and the 10:00:00
 * timecode start that broadcast subtitles often use is removed so the first line lines up with the video.
 */
object Ttml {

    private val ROOT = Regex("""<(?:\w+:)?tt\b([^>]*)>""", RegexOption.IGNORE_CASE)
    private val P = Regex("""<(?:\w+:)?p\b([^>]*)>(.*?)</(?:\w+:)?p\s*>""", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))
    private val BR = Regex("""<(?:\w+:)?br\b[^>]*/?>""", RegexOption.IGNORE_CASE)
    private val TAG = Regex("""<[^>]+>""")
    private val CLOCK = Regex("""^(\d+):(\d{2}):(\d{2})(?:([.,]\d+)|:(\d+(?:\.\d+)?))?$""")
    private val OFFSET = Regex("""^(\d+(?:\.\d+)?)(h|m|s|ms|f|t)$""")

    private fun attr(attrs: String, name: String): String? =
        Regex("""(?:^|\s)(?:\w+:)?$name\s*=\s*["']([^"']*)["']""").find(attrs)?.groupValues?.get(1)

    fun time(v0: String, fps: Double = 25.0, tickRate: Double = 10_000_000.0): Long? {
        val v = v0.trim()
        CLOCK.matchEntire(v)?.let { m ->
            var ms = (m.groupValues[1].toLong() * 3600 + m.groupValues[2].toLong() * 60 + m.groupValues[3].toLong()) * 1000
            if (m.groupValues[4].isNotEmpty()) ms += ("0" + m.groupValues[4].replace(',', '.')).toDouble().times(1000).roundToLong()
            else if (m.groupValues[5].isNotEmpty()) ms += (m.groupValues[5].toDouble() / fps * 1000).roundToLong()
            return ms
        }
        OFFSET.matchEntire(v)?.let { m ->
            val n = m.groupValues[1].toDouble()
            return when (m.groupValues[2]) {
                "h" -> (n * 3_600_000).roundToLong(); "m" -> (n * 60_000).roundToLong(); "s" -> (n * 1000).roundToLong()
                "ms" -> n.roundToLong(); "f" -> (n / fps * 1000).roundToLong(); else -> (n / tickRate * 1000).roundToLong()
            }
        }
        return null
    }

    fun unescape(s: String) = s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"").replace("&apos;", "'")
        .replace("&#39;", "'").replace("&nbsp;", " ").replace(Regex("""&#(\d+);""")) { String(Character.toChars(it.groupValues[1].toInt())) }
        .replace(Regex("""&#x([0-9a-fA-F]+);""")) { String(Character.toChars(it.groupValues[1].toInt(16))) }
        .replace("&amp;", "&")

    fun parse(xml: String): List<Cue> {
        val root = ROOT.find(xml)?.groupValues?.get(1).orEmpty()
        var fps = attr(root, "frameRate")?.toDoubleOrNull() ?: 25.0
        attr(root, "frameRateMultiplier")?.trim()?.split(Regex("\\s+"))?.let { mm ->
            val a = mm.getOrNull(0)?.toDoubleOrNull(); val b = mm.getOrNull(1)?.toDoubleOrNull()
            if (a != null && b != null && b != 0.0) fps *= a / b
        }
        val tick = attr(root, "tickRate")?.toDoubleOrNull() ?: 10_000_000.0
        val out = ArrayList<Cue>()
        for (m in P.findAll(xml)) {
            val a = m.groupValues[1]
            val s = attr(a, "begin")?.let { time(it, fps, tick) } ?: continue
            val e = attr(a, "end")?.let { time(it, fps, tick) } ?: (s + (attr(a, "dur")?.let { time(it, fps, tick) } ?: 3000))
            val body = unescape(m.groupValues[2].replace(BR, "\n").replace(TAG, ""))
                .split('\n').map { it.replace(Regex("\\s+"), " ").trim() }.filter { it.isNotEmpty() }.joinToString("\n")
            if (body.isNotEmpty() && e > s && body.any { it.isLetterOrDigit() }) out.add(Cue(s, e, body))
        }
        out.sortBy { it.startMs }
        if (out.isNotEmpty() && out[0].startMs >= 36_000_000) return out.map { it.copy(startMs = it.startMs - 36_000_000, endMs = it.endMs - 36_000_000) }
        return out
    }

    /** .srt, .vtt or TTML — whatever the text is. */
    fun parseAny(text: String): List<Cue> {
        val t = text.trimStart('﻿', ' ', '\r', '\n', '\t')
        return if (t.startsWith("<")) parse(t) else Srt.parse(text)
    }

    private val DE = "der die das und ist nicht ich sie wir ein eine es auf mit den dem zu von für sich auch noch wie aber oder wenn dass".split(' ').toSet()
    private val EN = "the and is not you we it of to in that for on with this are was be have he she they but or if".split(' ').toSet()

    /** "de" or "en" from the most common little words. */
    fun guessLang(cues: List<Cue>): String {
        val words = Regex("[a-zäöüß]+").findAll(cues.take(200).joinToString(" ") { it.text }.lowercase()).map { it.value }.toList()
        val de = words.count { it in DE }; val en = words.count { it in EN }
        return if (en > de * 1.3) "en" else "de"
    }
}
