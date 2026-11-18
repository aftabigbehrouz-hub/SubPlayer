package com.behrouz.subplayer

import com.behrouz.subplayer.learn.Cards
import com.behrouz.subplayer.learn.Lessons
import com.behrouz.subplayer.subs.Cue
import com.behrouz.subplayer.subs.CueBuilder
import com.behrouz.subplayer.words.WordStore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Version 2.9 (same rules as Windows 2.6): one entry per word, review cards from lessons, collocations, sentences. */
class Features29Test {

    private val lesson = "HÖREN\n1. …\n---LÖSUNGEN---\n1 falsch\n\n" + Cards.MARK + "\n" +
        "Q: Laut dem Video sind die Angriffe auf Schiffe zurückgegangen.\nO: richtig | falsch\nA: falsch\nE: „Aktuell gibt es wieder etliche Angriffe …“\n\n" +
        "Q: Was bedeutet „etliche“?\nO: A) keine | B) mehrere | C) alle\nA: B\nE: etliche = einige, mehrere\n\n" +
        "2. Q: Text A: … Der Autor hält die Lage für stabil.\nO: Ja | Nein | Text sagt dazu nichts\nA: Text sagt dazu nichts\nE: Darüber steht nichts\n\n" +
        "Q: Wie heißt die Meerenge, durch die viel Öl transportiert\nwird?\nO:\nA: die Straße von Hormuz\nE: Zeile 2\n"

    @Test fun lessonCardsAreRead() {
        val qs = Cards.parse(lesson, "de", "v.mp4", "lesson:TestDaF")
        assertEquals(4, qs.size)
        assertEquals(listOf("tf", "mc", "yn", "open"), qs.map { it.kind })
        assertEquals(listOf("A) keine", "B) mehrere", "C) alle"), qs[1].options)
        assertTrue(qs[3].question.endsWith("transportiert wird?"))
        assertEquals("v.mp4", qs[0].videoName)
    }

    @Test fun aNormalLessonHasNoCards() {
        assertTrue(Cards.parse("TEXT\nA: Das ist ein Satz.\nLÖSUNGEN 1a 2b").isEmpty())
    }

    @Test fun examPromptAsksForCards() {
        val c = listOf(Cue(0, 1000, "Hallo zusammen."))
        assertTrue(Cards.MARK in Lessons.prompt("TestDaF", "de", "v.mp4", c, emptyList()))
        assertTrue(Cards.MARK in Lessons.prompt("IELTS", "en", "v.mp4", c, emptyList()))
        assertFalse(Cards.MARK in Lessons.prompt("B1", "de", "v.mp4", c, emptyList()))
    }

    @Test fun answersAreMatched() {
        assertTrue(Cards.isAnswer("B) mehrere", "B"))
        assertTrue(Cards.isAnswer("B) mehrere", "b) mehrere"))
        assertTrue(Cards.isAnswer("B) mehrere", "mehrere"))
        assertFalse(Cards.isAnswer("A) keine", "B"))
        assertTrue(Cards.isAnswer("falsch", "Falsch"))
        assertFalse(Cards.isAnswer("richtig", "falsch"))
        assertFalse(Cards.isAnswer("Nein", "Text sagt dazu nichts"))
    }

    @Test fun collocationLinesAreSeparated() {
        val raw = "1) Meaning: several\nKOLL: etliche Male | several times | Ich war etliche Male dort.\n- **KOLL:** etliche Stunden | several hours\n" +
            "DE: Es gab etliche Touristen. | EN: There were a few tourists. | FA: چند گردشگر بودند."
        val (cols, rest) = Cards.collocations(raw, "de", "etliche")
        assertEquals(listOf("etliche Male", "etliche Stunden"), cols.map { it.phrase })
        assertEquals("Ich war etliche Male dort.", cols[0].example)
        assertFalse("KOLL" in rest)
        assertTrue("Touristen" in rest)
    }

    @Test fun collocationTablesAreSeparated() {
        val raw = "| German collocation | English | Persian |\n|---|---|---|\n| weitestgehend wiederhergestellt | largely restored | تا حد زیادی بازسازی شده |\n" +
            "| **weitestgehend abgeschlossen** | largely completed | تا حد زیادی تکمیل شده |\n" +
            "DE: Die Systeme laufen weitestgehend wieder. | EN: The systems are largely running again. | FA: سیستم‌ها دوباره کار می‌کنند."
        val (cols, rest) = Cards.collocations(raw, "de", "weitestgehend")
        assertEquals(listOf("weitestgehend wiederhergestellt", "weitestgehend abgeschlossen"), cols.map { it.phrase })
        assertFalse("German collocation" in rest)
        assertTrue("Die Systeme laufen" in rest)
        assertTrue(Cards.isHeader("German collocation")); assertFalse(Cards.isPhrase("Die Systeme laufen weitestgehend wieder."))
    }

        @Test fun sameWordKey() {
        assertEquals(WordStore.wordKey("zuzuspitzen", "zuspitzen", "de"), WordStore.wordKey("spitzt", "zuspitzen", "de"))
        assertFalse(WordStore.wordKey("zuzuspitzen", "zuspitzen", "de") == WordStore.wordKey("zuzuspitzen", "zuspitzen", "en"))
        assertEquals(WordStore.wordKey("auf jeden Fall", "auf jeden Fall", "de"), WordStore.wordKey("Auf  jeden fall", "", "de"))
    }

    @Test fun linesAreGroupedIntoSentences() {
        val cs = listOf(Cue(0, 1000, "Aktuell gibt es wieder"), Cue(1000, 2000, "etliche Angriffe auf Schiffe"), Cue(2000, 3000, "in der Straße von Hormuz."),
            Cue(3100, 4000, "Gut.")) + (0 until 8).map { Cue(5000L + it * 1000, 5900L + it * 1000, "teil $it") } + listOf(Cue(14000, 15000, "Ende."))
        val r = CueBuilder.sentenceRanges(cs)
        assertEquals(listOf(0..2, 0..2, 0..2, 3..3), r.take(4))
        assertEquals(List(5) { 4..8 } + List(4) { 9..12 }, r.drop(4))
        assertEquals(cs.indices.toList(), r.distinct().flatMap { it.toList() })
        val plain = listOf(Cue(0, 1000, "eins"), Cue(1000, 2000, "zwei"), Cue(2000, 3000, "drei"))
        assertEquals(listOf(0..0, 1..1, 2..2), CueBuilder.sentenceRanges(plain))
    }
}
