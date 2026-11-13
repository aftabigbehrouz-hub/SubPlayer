package com.behrouz.subplayer.subs

import java.util.Locale
import kotlin.math.roundToLong

/** One subtitle line. Times in milliseconds. */
data class Cue(val startMs: Long, val endMs: Long, val text: String)

/** A recognised word with its time (seconds), as returned by Vosk. */
data class TimedWord(val start: Double, val end: Double, val text: String)

object Srt {

    private val TIME = Regex("""(?:(\d+):)?(\d{1,2}):(\d{2})[,.](\d{1,3})""")
    private val TAGS = Regex("""<[^>]+>|\{\\[^}]*\}""")

    /** Reads .srt (and simple .vtt) text. */
    fun parse(raw: String): List<Cue> {
        val text = raw.removePrefix("﻿").replace("\r\n", "\n").replace('\r', '\n')
        val out = ArrayList<Cue>()
        val lines = text.split('\n')
        var i = 0
        while (i < lines.size) {
            val line = lines[i]
            if (line.contains("-->")) {
                val parts = line.split("-->")
                val s = time(parts[0])
                val e = time(parts.getOrElse(1) { "" })
                val body = StringBuilder()
                i++
                while (i < lines.size && lines[i].isNotBlank()) {
                    if (body.isNotEmpty()) body.append('\n')
                    body.append(lines[i].replace(TAGS, "").trim())
                    i++
                }
                if (s != null && e != null && body.isNotBlank()) out.add(Cue(s, maxOf(e, s + 200), body.toString()))
            } else {
                i++
            }
        }
        return out.sortedBy { it.startMs }
    }

    private fun time(s: String): Long? {
        val m = TIME.find(s) ?: return null
        val h = m.groupValues[1].ifEmpty { "0" }.toLong()
        val mi = m.groupValues[2].toLong()
        val se = m.groupValues[3].toLong()
        val ms = m.groupValues[4].padEnd(3, '0').toLong()
        return ((h * 60 + mi) * 60 + se) * 1000 + ms
    }

    fun write(cues: List<Cue>): String {
        val sb = StringBuilder()
        cues.forEachIndexed { i, c ->
            sb.append(i + 1).append('\n')
                .append(ts(c.startMs)).append(" --> ").append(ts(c.endMs)).append('\n')
                .append(c.text).append("\n\n")
        }
        return sb.toString()
    }

    private fun ts(ms0: Long): String {
        val ms = ms0.coerceAtLeast(0)
        return String.format(Locale.US, "%02d:%02d:%02d,%03d",
            ms / 3_600_000, (ms / 60_000) % 60, (ms / 1000) % 60, ms % 1000)
    }
}

object CueBuilder {

    private const val MAX_GAP = 0.8
    private const val MAX_DURATION = 5.0
    private const val MAX_CHARS = 80
    private const val ROW_CHARS = 42

    /** Vosk words -> subtitle lines (pause > 0.8 s, > 5 s or > 80 chars starts a new line). */
    fun fromWords(words: List<TimedWord>): List<Cue> {
        val cues = ArrayList<Cue>()
        val cur = ArrayList<TimedWord>()
        fun flush() {
            if (cur.isEmpty()) return
            val text = cur.joinToString(" ") { it.text }.replaceFirstChar { it.titlecase(Locale.GERMAN) }
            cues.add(Cue((cur.first().start * 1000).roundToLong(), (cur.last().end * 1000).roundToLong(), wrap(text)))
            cur.clear()
        }
        for (w in words.sortedBy { it.start }) {
            if (cur.isNotEmpty()) {
                val len = cur.sumOf { it.text.length + 1 } + w.text.length
                if (w.start - cur.last().end > MAX_GAP || w.end - cur.first().start > MAX_DURATION || len > MAX_CHARS) flush()
            }
            cur.add(w)
        }
        flush()
        return polish(cues)
    }

    /** Whisper segments: drop known hallucinations / non-speech, then tidy timing. */
    fun fromSegments(segs: List<Cue>): List<Cue> {
        val cleaned = segs.mapNotNull { c ->
            val t = c.text.trim()
            when {
                t.isEmpty() -> null
                NON_SPEECH.matches(t) -> null
                HALLUCINATION.containsMatchIn(t) -> null
                c.endMs <= c.startMs -> null
                else -> Cue(c.startMs, c.endMs, wrap(t))
            }
        }
        return polish(cleaned)
    }

    private val NON_SPEECH = Regex("""^[\s\[\(\*♪♫#.…-]*(Musik|Music|Applaus|Lachen|Gelächter|Stille|Geräusche?|Untertitel)?[\s\]\)\*♪♫#.…-]*$""", RegexOption.IGNORE_CASE)
    private val HALLUCINATION = Regex(
        """Untertitel (im Auftrag|der Amara|von |erstellt)|Amara\.org|Copyright|www\.|Untertitelung|SWR \d{4}|ZDF für funk|Abonnier""",
        RegexOption.IGNORE_CASE)

    /** Minimum 1 s on screen, held 0.3 s after speech, never overlapping the next line. */
    fun polish(cues: List<Cue>): List<Cue> {
        val s = cues.sortedBy { it.startMs }
        return s.mapIndexed { i, c ->
            val next = if (i + 1 < s.size) s[i + 1].startMs else Long.MAX_VALUE
            val wanted = maxOf(c.endMs + 300, c.startMs + 1000)
            c.copy(endMs = minOf(wanted, next - 50).coerceAtLeast(c.endMs.coerceAtMost(next)))
        }
    }

    fun wrap(text: String): String {
        val t = text.replace('\n', ' ').replace(Regex("\\s+"), " ").trim()
        if (t.length <= ROW_CHARS) return t
        val mid = t.length / 2
        for (d in 0..mid) {
            if (mid + d < t.length && t[mid + d] == ' ') return t.substring(0, mid + d) + "\n" + t.substring(mid + d + 1)
            if (mid - d > 0 && t[mid - d] == ' ') return t.substring(0, mid - d) + "\n" + t.substring(mid - d + 1)
        }
        return t
    }

    /** Index of the cue showing at [posMs], or -1 (binary search; cues sorted by start). */
    fun indexAt(cues: List<Cue>, posMs: Long): Int {
        var lo = 0
        var hi = cues.size - 1
        var found = -1
        while (lo <= hi) {
            val mid = (lo + hi) ushr 1
            if (cues[mid].startMs <= posMs) { found = mid; lo = mid + 1 } else hi = mid - 1
        }
        return if (found >= 0 && posMs < cues[found].endMs) found else -1
    }

    /** Index of the last cue starting at or before [posMs] (for previous/next navigation). */
    fun indexBefore(cues: List<Cue>, posMs: Long): Int {
        var lo = 0
        var hi = cues.size - 1
        var found = -1
        while (lo <= hi) {
            val mid = (lo + hi) ushr 1
            if (cues[mid].startMs <= posMs) { found = mid; lo = mid + 1 } else hi = mid - 1
        }
        return found
    }
}
