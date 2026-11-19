package com.behrouz.subplayer

import com.behrouz.subplayer.learn.Teacher
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class Features210Test {
    @Test fun wordAnswerFromChatGptIsReadAndReadable() {
        val raw = "```json\n{\\\n&#x20; \"meaning\": \"refuse\",\\\n&#x20; \"persian\": \"امتناع کردن\",\\\n&#x20; \"forms\": {\"Präteritum\": \"weigerte\"},\\\n" +
            "&#x20; \"collocations\": [{\"phrase\": \"sich weigern, etwas zu tun\", \"meaning\": \"to refuse to do sth\", \"example\": \"Er weigert sich.\"}],\\\n" +
            "&#x20; \"examples\": [{\"sentence\": \"Ich weigere mich, das zu glauben.\", \"translation\": \"I refuse to believe it.\"}]\\\n}\n```"
        val a = Teacher.readWord(raw, "de", "weigern")
        assertEquals("refuse", a.meaning)
        assertEquals("امتناع کردن", a.persian)
        assertEquals("sich weigern, etwas zu tun", a.collocations.single().phrase)
        assertEquals("Ich weigere mich, das zu glauben.", a.examples.single().de)
        assertTrue(a.readable.contains("Präteritum: weigerte"))
        assertTrue(!a.readable.contains("&#x20;") && !a.readable.contains("{"))
    }

    @Test fun examAnswerBecomesQuestions() {
        val raw = "{\"questions\": [{\"question\": \"Er ___ sich, zu zahlen.\", \"options\": [\"weigert\", \"weigern\"], \"answer\": \"weigert\", \"explanation\": \"3. Person\"}," +
            " {\"question\": \"\", \"answer\": \"x\"}]}"
        val qs = Teacher.readExam(raw, "de", "weigern", "Video")
        assertEquals(1, qs.size)
        assertEquals("mc", qs[0].kind)
        assertEquals("weigern", qs[0].lemma)
    }

    @Test fun checkAnswerIsReadable() {
        val r = Teacher.readCheck("{\"correct\": false, \"corrected\": \"Ich weigere mich.\", \"explanation\": \"reflexive\", \"better\": \"Ich lehne ab.\", \"score\": 6}")
        assertTrue(r.startsWith("✗ Not quite · 6/10"))
        assertTrue("Corrected: Ich weigere mich." in r && "Better: Ich lehne ab." in r)
    }

    @Test fun promptsAskForJson() {
        assertTrue("Answer ONLY with a JSON object" in Teacher.wordPrompt("weigere", "weigern", "Ich weigere mich.", "de", "B1", "en"))
        assertTrue("TestDaF" in Teacher.examPrompt("weigere", "weigern", "", "de", "B2", "fa"))
        assertTrue("Persian" in Teacher.examPrompt("weigere", "weigern", "", "de", "B2", "fa"))
    }
}
