package com.behrouz.subplayer

import com.behrouz.subplayer.subs.Cue
import com.behrouz.subplayer.subs.CueBuilder
import com.behrouz.subplayer.subs.Srt
import com.behrouz.subplayer.subs.TimedWord
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SubtitlesTest {

    @Test fun srtRoundTrip() {
        val cues = listOf(Cue(500, 1800, "Hallo, wie geht's?"), Cue(3_600_123, 3_602_000, "Mir geht es gut."))
        val back = Srt.parse(Srt.write(cues))
        assertEquals(cues, back)
    }

    @Test fun parsesVttAndTags() {
        val vtt = "WEBVTT\n\n00:01.250 --> 00:02.500\n<i>Guten</i> Tag\n\n01:00:00.000 --> 01:00:01.000\nzwei\nZeilen\n"
        val c = Srt.parse(vtt)
        assertEquals(2, c.size)
        assertEquals(Cue(1250, 2500, "Guten Tag"), c[0])
        assertEquals("zwei\nZeilen", c[1].text)
        assertEquals(3_600_000L, c[1].startMs)
    }

    @Test fun groupsWordsIntoLines() {
        val w = listOf(TimedWord(0.5, 0.8, "hallo"), TimedWord(0.85, 1.2, "wie"), TimedWord(1.25, 1.5, "geht's"),
            TimedWord(3.0, 3.4, "mir"), TimedWord(3.45, 3.9, "geht"), TimedWord(3.95, 4.3, "es"), TimedWord(4.35, 4.8, "gut"))
        val c = CueBuilder.fromWords(w)
        assertEquals(2, c.size)
        assertEquals(Cue(500, 1800, "Hallo wie geht's"), c[0])
        assertEquals(Cue(3000, 5100, "Mir geht es gut"), c[1])
    }

    @Test fun dropsHallucinationsAndNoise() {
        val c = CueBuilder.fromSegments(listOf(
            Cue(0, 2000, " Guten Morgen."), Cue(2000, 4000, "(Musik)"), Cue(4000, 6000, "Untertitel im Auftrag des ZDF, 2021"),
            Cue(6000, 8000, "* Applaus *")))
        assertEquals(listOf("Guten Morgen."), c.map { it.text })
    }

    @Test fun linesNeverOverlap() {
        val c = CueBuilder.polish(listOf(Cue(0, 900, "a"), Cue(950, 1500, "b"), Cue(5000, 5200, "c")))
        for (i in 0 until c.size - 1) assertTrue(c[i].endMs <= c[i + 1].startMs)
        assertEquals(6000L, c[2].endMs)    // short last line held to 1 s minimum... 5000+1000
    }

    @Test fun findsLineAtTime() {
        val c = listOf(Cue(0, 1000, "a"), Cue(2000, 3000, "b"), Cue(4000, 5000, "c"))
        assertEquals(0, CueBuilder.indexAt(c, 500))
        assertEquals(-1, CueBuilder.indexAt(c, 1500))
        assertEquals(1, CueBuilder.indexAt(c, 2000))
        assertEquals(2, CueBuilder.indexAt(c, 4999))
        assertEquals(-1, CueBuilder.indexAt(c, 5000))
        assertEquals(1, CueBuilder.indexBefore(c, 3500))
    }

    @Test fun wrapsLongLineAtMiddleSpace() {
        val t = CueBuilder.wrap("Ich bin heute extra früh aufgestanden, weil ich zum Bahnhof muss")
        val rows = t.split('\n')
        assertEquals(2, rows.size)
        assertTrue(rows.all { it.length <= 42 })
    }
}
