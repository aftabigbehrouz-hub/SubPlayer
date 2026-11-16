package com.behrouz.subplayer.learn

import com.behrouz.subplayer.subs.Cue

/**
 * AI lessons from a whole video: the ready question for ChatGPT / Gemini / DeepSeek / Grok — a text at A2, B1, B2 or C1
 * that retells the video, its key words and structures, exercises and the answers. The same question as the Windows app
 * (lessons.py). The pasted answers are kept per video and level by the app.
 */
object Lessons {
    val LEVELS = listOf("A2", "B1", "B2", "C1")
    val EXPLAIN = linkedMapOf("en" to "English", "fa" to "Persian (فارسی)", "de" to "German (einfaches Deutsch)")
    const val MAX_TRANSCRIPT = 60_000

    private val WHAT_DE = mapOf(
        "A2" to "very simple: short main clauses, present tense and Perfekt, only everyday words; 150–200 words",
        "B1" to "simple and clear: main clauses with weil / dass / wenn / obwohl, Präteritum of common verbs; 200–260 words",
        "B2" to "natural and connected: relative clauses, passive, Konjunktiv II, linking words (allerdings, dennoch, sowohl … als auch); 260–330 words",
        "C1" to "demanding, as in a quality newspaper: nominal style, participle constructions, Konjunktiv I for reported speech, precise vocabulary; 330–420 words")
    private val WHAT_EN = mapOf(
        "A2" to "very simple: short sentences, present and past simple, only everyday words; 150–200 words",
        "B1" to "simple and clear: because / although / if clauses, common phrasal verbs; 200–260 words",
        "B2" to "natural and connected: relative clauses, passive, conditionals, linking words (however, nevertheless, whereas); 260–330 words",
        "C1" to "demanding, as in a quality newspaper: complex sentences, inversion, nominalisation, precise and idiomatic vocabulary; 330–420 words")

    fun transcript(cues: List<Cue>) = cues.joinToString(" ") { it.text }.replace(Regex("\\s+"), " ").trim()

    fun prompt(level: String, lang: String, name: String, cues: List<Cue>, myWords: List<String>, explain: String = "en"): String {
        val german = lang != "en"
        val target = if (german) "German" else "English"
        val ex = EXPLAIN[explain] ?: "English"
        val what = (if (german) WHAT_DE else WHAT_EN)[level].orEmpty()
        var text = transcript(cues)
        val cut = text.length > MAX_TRANSCRIPT
        if (cut) text = text.take(MAX_TRANSCRIPT).substringBeforeLast(' ') + " …"
        val words = myWords.map { it.trim() }.filter { it.isNotEmpty() }.distinct().joinToString(", ").take(1500)
        var tasks = listOf(
            "TEXT ($level) — Write a new $target text at CEFR level $level that retells the content of the video ($what). " +
                "Use the important words and sentence structures of the transcript, but adapt them strictly to this level. Give it a title.",
            "WORTSCHATZ — The 15 most useful words and expressions from the video for a $level learner" +
                (if (words.isNotEmpty()) " (include the words I am learning, listed below)" else "") + ". For each: " +
                (if (german) "article and plural for nouns, Präteritum and Perfekt for verbs, " else "word forms, ") +
                "the meaning in $ex, and one short example sentence in $target.",
            "STRUKTUREN — The 3 grammar structures of the video that matter most at $level. For each: the sentence from the video " +
                "where it appears, a short explanation in $ex, and 2 new examples.",
            "ÜBUNGEN — exercises that use ONLY the words and structures above:\n" +
                "   A. Lückentext: 10 sentences with one gap each (word bank in mixed order above the sentences).\n" +
                "   B. Zuordnung: match 8 words to their definitions or synonyms.\n" +
                "   C. Umformung: 6 sentences to rewrite with one of the structures (say which).\n" +
                "   D. Fragen zum Text: 5 comprehension questions to answer in full $target sentences.\n" +
                "   E. Schreiben: one writing task (60–120 words at $level) with 5 words from the list that I must use.",
            "LÖSUNGEN — the answers to A–D at the very end, after a line “---LÖSUNGEN---”, so that I can test myself first.")
        if (!german) tasks = tasks.map {
            it.replace("WORTSCHATZ", "VOCABULARY").replace("STRUKTUREN", "STRUCTURES").replace("ÜBUNGEN", "EXERCISES")
                .replace("Lückentext", "Gap-fill").replace("Zuordnung", "Matching").replace("Umformung", "Transformation")
                .replace("Fragen zum Text", "Questions on the text").replace("Schreiben", "Writing").replace("LÖSUNGEN", "ANSWERS")
        }
        val out = ArrayList<String>()
        out += "You are an experienced $target teacher. I am learning $target with a video and want to master its words and " +
            "sentence structures at level $level. Work only from the transcript below."
        out += ""
        tasks.forEachIndexed { i, t -> out += "${i + 1}. $t" }
        out += ""
        out += "Write everything in $target, except the meanings and explanations, which are in $ex. Plain text with clear headings, no tables."
        out += ""
        if (words.isNotEmpty()) { out += "Words I am learning from this video: $words"; out += "" }
        out += "Video: $name" + if (cut) " (the transcript is long — only its first part is given)" else ""
        out += "TRANSCRIPT ($target):"
        out += text
        return out.joinToString("\n")
    }
}
