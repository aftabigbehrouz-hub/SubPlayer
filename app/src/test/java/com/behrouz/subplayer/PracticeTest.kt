package com.behrouz.subplayer

import com.behrouz.subplayer.words.Practice
import com.behrouz.subplayer.words.SavedWord
import com.behrouz.subplayer.words.Sentences
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.random.Random

class PracticeTest {

    private fun w(text: String, lemma: String = text) = SavedWord(text = text, lemma = lemma, sentence = "", videoUri = "v",
        videoName = "v", startMs = 0, endMs = 1, created = 0, due = 0)

    @Test fun parsesTheAppFormat() {
        val ai = """
            Here are three example sentences:
            1. **DE:** Ich stehe jeden Morgen um sechs Uhr auf. | **EN:** I get up at six every morning. | **FA:** من هر روز ساعت شش بیدار می‌شوم.
            2. DE: Steh bitte auf! | EN: Please stand up! | FA: لطفاً بلند شو!
            3. DE: Wann bist du heute aufgestanden? | EN: When did you get up today? | FA: امروز کی بیدار شدی؟
        """.trimIndent()
        val e = Sentences.parse(ai)
        assertEquals(3, e.size)
        assertEquals("Ich stehe jeden Morgen um sechs Uhr auf.", e[0].de)
        assertEquals("I get up at six every morning.", e[0].en)
        assertEquals("من هر روز ساعت شش بیدار می‌شوم.", e[0].fa)
    }

    @Test fun parsesLabelledBlocksAndTables() {
        val blocks = "DE: Er geht nach Hause.\nEN: He goes home.\nFA: او به خانه می‌رود.\n\nDE: Wir gehen ins Kino.\nEN: We go to the cinema."
        val b = Sentences.parse(blocks)
        assertEquals(2, b.size); assertEquals("He goes home.", b[0].en); assertEquals("او به خانه می‌رود.", b[0].fa); assertEquals("", b[1].fa)
        val table = "| DE | EN | FA |\n|---|---|---|\n| Das Haus ist alt. | The house is old. | خانه قدیمی است. |"
        val t = Sentences.parse(table)
        assertEquals(1, t.size); assertEquals("Das Haus ist alt.", t[0].de); assertEquals("خانه قدیمی است.", t[0].fa)
    }

    @Test fun plainGermanLines() {
        val e = Sentences.parse("Beispiele:\nDer Zug kommt pünktlich an.\nIch warte am Bahnhof.\nok")
        assertEquals(listOf("Der Zug kommt pünktlich an.", "Ich warte am Bahnhof."), e.map { it.de })
    }

    @Test fun clozeFindsInflectedForms() {
        val c = Practice.cloze(w("aufgestanden", "aufstehen"), "Wann bist du heute aufgestanden?")!!
        assertEquals("aufgestanden", c.answer); assertEquals("Wann bist du heute ", c.before); assertEquals("?", c.after)
        val c2 = Practice.cloze(w("Häuser", "Haus"), "Das Haus ist alt.")!!
        assertEquals("Haus", c2.answer)
        val c3 = Practice.cloze(w("gehen"), "Wir gingen gestern.")   // strong past form: not guessable by stem
        assertNull(c3)
        val c4 = Practice.cloze(w("zum Bahnhof"), "Ich muss zum Bahnhof.")!!
        assertEquals("zum Bahnhof", c4.answer)
    }

    @Test fun choicesAndLenientAnswers() {
        val ch = Practice.choices("Haus", listOf("Zug", "Brot", "haus", "Fenster", "zum Bahnhof"), Random(1))
        assertEquals(4, ch.size); assertTrue("Haus" in ch); assertTrue(ch.none { it == "haus" || it == "zum Bahnhof" })
        assertTrue(Practice.choices("Haus", listOf("Zug"), Random(1)).isEmpty())
        assertTrue(Practice.same("Strasse", "Straße")); assertTrue(Practice.same("fuer", "für")); assertTrue(Practice.same(" Haus! ", "haus"))
    }

    @Test fun dictationMarksWords() {
        val (marks, score) = Practice.dictation("Ich bin heute früh aufgestanden.", "ich bin heute frueh aufgestandn")
        assertEquals(listOf(true, true, true, true, false), marks.map { it.ok })
        assertEquals(80, score)
    }
}
