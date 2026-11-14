package com.behrouz.subplayer

import com.behrouz.subplayer.sync.SExample
import com.behrouz.subplayer.sync.SSub
import com.behrouz.subplayer.sync.SWord
import com.behrouz.subplayer.sync.SyncDoc
import com.behrouz.subplayer.sync.SyncMerge
import com.behrouz.subplayer.words.Sentences
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SyncMergeTest {
    private val now = 1_800_000_000_000L
    private fun w(uid: String, text: String, updated: Long, box: Int = 0, lang: String = "de") =
        SWord(uid, text, text, "", "", "", "", "", "video.mp4", 0, 1000, 1, 0, 0, box, 0, 0, lang, updated)

    @Test fun newestCopyWins() {
        val a = SyncDoc(words = mapOf("1" to w("1", "Haus", 100, box = 2)))
        val b = SyncDoc(words = mapOf("1" to w("1", "Haus", 200, box = 5)))
        assertEquals(5, SyncMerge.merge(a, b, now).words["1"]!!.box)
        assertEquals(5, SyncMerge.merge(b, a, now).words["1"]!!.box)   // order does not matter
    }

    @Test fun wordsFromBothSidesAreKept() {
        val m = SyncMerge.merge(SyncDoc(words = mapOf("1" to w("1", "Haus", 1))), SyncDoc(words = mapOf("2" to w("2", "house", 1, lang = "en"))), now)
        assertEquals(setOf("1", "2"), m.words.keys)
        assertEquals("en", m.words["2"]!!.lang)
    }

    @Test fun deletionBeatsOlderCopyButNotNewerEdit() {
        val deletedOnPhone = SyncDoc(deleted = mapOf("1" to now - 1000))
        val olderOnPc = SyncDoc(words = mapOf("1" to w("1", "Haus", now - 5000)))
        assertFalse("1" in SyncMerge.merge(deletedOnPhone, olderOnPc, now).words)
        val newerOnPc = SyncDoc(words = mapOf("1" to w("1", "Haus", now - 10)))
        assertTrue("1" in SyncMerge.merge(deletedOnPhone, newerOnPc, now).words)
    }

    @Test fun oldTombstonesExpire() {
        val m = SyncMerge.merge(SyncDoc(deleted = mapOf("x" to now - 121L * 86_400_000L, "y" to now - 1)), SyncDoc(), now)
        assertEquals(setOf("y"), m.deleted.keys)
    }

    @Test fun sentencesOfADeletedWordAreDropped() {
        val e = SExample("e1", "1", "Das Haus ist groß.", "", "", 1, 1)
        val a = SyncDoc(examples = mapOf("e1" to e), deleted = mapOf("1" to now - 1))
        val b = SyncDoc(words = mapOf("1" to w("1", "Haus", now - 100)), examples = mapOf("e1" to e))
        val m = SyncMerge.merge(a, b, now)
        assertTrue(m.words.isEmpty()); assertTrue(m.examples.isEmpty())
    }

    @Test fun newerSubtitlesWin() {
        val a = SyncDoc(subs = mapOf("film|de" to SSub("film", "de", "OLD", 1)))
        val b = SyncDoc(subs = mapOf("film|de" to SSub("film", "de", "NEW", 2), "film|en" to SSub("film", "en", "EN", 1)))
        val m = SyncMerge.merge(a, b, now)
        assertEquals("NEW", m.subs["film|de"]!!.srt); assertEquals(2, m.subs.size)
    }

    @Test fun progressLaterDayWinsSameDayTakesLarger() {
        val a = SyncDoc(streak = 4, lastDay = 100, today = 3)
        val b = SyncDoc(streak = 9, lastDay = 99, today = 20)
        val m = SyncMerge.merge(a, b, now)
        assertEquals(Triple(4, 100L, 3), Triple(m.streak, m.lastDay, m.today))
        val c = SyncMerge.merge(SyncDoc(streak = 4, lastDay = 100, today = 3), SyncDoc(streak = 5, lastDay = 100, today = 1), now)
        assertEquals(Triple(5, 100L, 3), Triple(c.streak, c.lastDay, c.today))
    }

    @Test fun jsonRoundTrip() {
        val d = SyncDoc(
            words = mapOf("1" to w("1", "Mädchen", 5), "2" to w("2", "house", 6, lang = "en")),
            examples = mapOf("e" to SExample("e", "1", "Das Mädchen lacht.", "The girl laughs.", "دختر می‌خندد.", 3, 4)),
            deleted = mapOf("z" to 77L),
            subs = mapOf("v|de" to SSub("v", "de", "1\n00:00:00,000 --> 00:00:01,000\nHallo\n", 9)),
            streak = 3, lastDay = 20000, today = 7
        )
        assertEquals(d, SyncMerge.fromJson(SyncMerge.toJson(d)))
        assertEquals(SyncDoc(), SyncMerge.fromJson(""))
    }

    @Test fun englishSentencesKeepEnglishAsTheSentence() {
        val en = Sentences.parse("EN: The house is big. | DE: Das Haus ist groß. | FA: خانه بزرگ است.", primary = "en")
        assertEquals("The house is big.", en[0].de)   // "de" field = sentence in the language being learnt
        assertEquals("Das Haus ist groß.", en[0].en)
        val labels = Sentences.parse("DE: Das Haus ist groß.\nEN: The house is big.\nDE: Ich gehe heim.\nEN: I go home.", primary = "en")
        assertEquals(listOf("The house is big.", "I go home."), labels.map { it.de })
        assertEquals("Das Haus ist groß.", labels[0].en)
    }
}
