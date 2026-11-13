package com.behrouz.subplayer

import java.util.Locale
import kotlin.math.roundToLong

/**
 * Groups timed words into subtitle lines and writes standard .srt text.
 *
 * Rules for starting a new subtitle line:
 *  - a pause longer than MAX_GAP seconds between words, or
 *  - the line would last longer than MAX_DURATION seconds, or
 *  - the line would exceed MAX_CHARS characters (wrapped onto 2 rows of ~42).
 * Each line is then held MIN_HOLD seconds after its last word (and at least
 * MIN_SHOW seconds in total) so it can be read — but never into the next line.
 */
object SrtBuilder {

    data class Cue(val start: Double, var end: Double, val text: String)

    private const val MAX_GAP = 0.8
    private const val MAX_DURATION = 5.0
    private const val MAX_CHARS = 80
    private const val ROW_CHARS = 42
    private const val MIN_HOLD = 0.3
    private const val MIN_SHOW = 1.0
    private const val SEPARATION = 0.05

    fun cues(words: List<Transcriber.Word>): List<Cue> {
        val cues = ArrayList<Cue>()
        val cur = ArrayList<Transcriber.Word>()

        fun flush() {
            if (cur.isEmpty()) return
            val text = cur.joinToString(" ") { it.text }
                .replaceFirstChar { it.titlecase(Locale.GERMAN) }
            cues.add(Cue(cur.first().start, cur.last().end, wrap(text)))
            cur.clear()
        }

        for (w in words.sortedBy { it.start }) {
            if (cur.isNotEmpty()) {
                val len = cur.sumOf { it.text.length + 1 } + w.text.length
                if (w.start - cur.last().end > MAX_GAP ||
                    w.end - cur.first().start > MAX_DURATION ||
                    len > MAX_CHARS
                ) flush()
            }
            cur.add(w)
        }
        flush()

        for (i in cues.indices) {
            val nextStart = if (i + 1 < cues.size) cues[i + 1].start else Double.MAX_VALUE
            val wanted = maxOf(cues[i].end + MIN_HOLD, cues[i].start + MIN_SHOW)
            cues[i].end = minOf(wanted, nextStart - SEPARATION).coerceAtLeast(cues[i].end)
        }
        return cues
    }

    fun toSrt(cues: List<Cue>): String {
        val sb = StringBuilder()
        cues.forEachIndexed { i, c ->
            sb.append(i + 1).append('\n')
            sb.append(ts(c.start)).append(" --> ").append(ts(c.end)).append('\n')
            sb.append(c.text).append("\n\n")
        }
        return sb.toString()
    }

    /** Splits a long line into two rows at the space closest to the middle. */
    private fun wrap(text: String): String {
        if (text.length <= ROW_CHARS) return text
        val mid = text.length / 2
        var best = -1
        for (d in 0..mid) {
            if (mid + d < text.length && text[mid + d] == ' ') { best = mid + d; break }
            if (mid - d >= 0 && text[mid - d] == ' ') { best = mid - d; break }
        }
        return if (best <= 0) text else text.substring(0, best) + "\n" + text.substring(best + 1)
    }

    /** Seconds -> "HH:MM:SS,mmm" */
    private fun ts(sec: Double): String {
        val totalMs = (sec.coerceAtLeast(0.0) * 1000).roundToLong()
        val h = totalMs / 3_600_000
        val m = (totalMs / 60_000) % 60
        val s = (totalMs / 1000) % 60
        val ms = totalMs % 1000
        return String.format(Locale.US, "%02d:%02d:%02d,%03d", h, m, s, ms)
    }
}
