package com.behrouz.subplayer.learn

import com.behrouz.subplayer.subs.Cue

/**
 * AI lessons from a whole video: the ready question for ChatGPT / Gemini / DeepSeek / Grok — a text at A2, B1, B2 or C1
 * that retells the video, its key words and structures, exercises and the answers. The same question as the Windows app
 * (lessons.py). The pasted answers are kept per video and level by the app.
 */
object Lessons {
    val LEVELS = listOf("A2", "B1", "B2", "C1")
    val EXAMS = listOf("TestDaF", "IELTS")
    val ALL = LEVELS + EXAMS

    /** The exam that fits the video's language: TestDaF for German, IELTS for English. */
    fun examFor(lang: String) = if (lang == "en") "IELTS" else "TestDaF"

    // generated from the Windows app's lessons.exam_prompt (tools: same wording in both apps); §EX§ = language of the explanations
    private val EXAM_TEXT = mapOf(
        "IELTS" to "You are an experienced IELTS Academic examiner and teacher. I am preparing for IELTS (target band 7+) with an English video. Build a complete practice set on the WHOLE video below — its topic, arguments, facts and language.\n\n1. VOCABULARY FOR IELTS\n   a) 20 words and expressions FROM THE VIDEO that are most useful for band 7+ (use the B2–C2 words listed below where they fit): word family (noun / verb / adjective / adverb), 2 typical collocations, the meaning in §EX§, and the sentence from the video.\n   b) TOPIC VOCABULARY: 15 further words and collocations that are NOT in the video but are very likely to appear in future videos and in IELTS reading, listening and writing on this topic, each with meaning and one example.\n2. LISTENING (the video is the recording; do not quote the answers in the questions)\n   Part A — note completion: 8 gaps, NO MORE THAN TWO WORDS AND/OR A NUMBER.\n   Part B — 5 multiple-choice questions (A–C).\n   Part C — matching: 5 statements to the people / options / parts of the video they belong to.\n3. READING — write an academic passage of about 600 words on the topic of the video (new text, IELTS style, with paragraphs A–F), then 13 questions: 5 TRUE / FALSE / NOT GIVEN, 4 matching headings to paragraphs, 4 summary completion with words from the passage.\n4. WRITING\n   Task 1 (150 words): a chart or table on the topic with numbers you invent — say clearly that the data are invented for practice — and the usual instruction.\n   Task 2 (250 words): an essay question on the topic (opinion, discuss both views, or problem–solution).\n   Then: a band-7 checklist (task response, coherence, lexical resource, grammar) and 10 useful linking phrases.\n5. SPEAKING — Part 1: 4 questions · Part 2: a cue card with 4 prompts · Part 3: 5 discussion questions; plus 8 useful phrases for giving and supporting opinions.\n6. ANSWERS — after a line “---ANSWERS---”: all answers of Listening and Reading (with the sentence that proves each one), and a short band-8 model answer for Writing Task 2.\n\nWrite everything in English, except the meanings and short explanations, which are in §EX§. Plain text with clear headings, no tables.\n\n",
        "TestDaF" to "You are an experienced TestDaF examiner and German teacher. I am preparing for the (digital) TestDaF, aiming at TDN 4–5 (B2–C1), with a German video. Build a complete practice set on the WHOLE video below — its topic, arguments, facts and language.\n\n1. WORTSCHATZ FÜR DEN TESTDAF\n   a) 20 Wörter und Ausdrücke AUS DEM VIDEO, die für TestDaF-Texte (Hochschule, Wissenschaft, Gesellschaft, Umwelt, Arbeit) am wichtigsten sind (nimm die B2–C2-Wörter unten, wo sie passen): Artikel und Plural bzw. Präteritum und Perfekt, typische Nomen-Verb-Verbindungen und Präpositionen, die Bedeutung auf §EX§ und den Satz aus dem Video.\n   b) THEMENWORTSCHATZ: 15 weitere Wörter und Wendungen, die NICHT im Video vorkommen, aber in künftigen Videos und in TestDaF-Lese- und Hörtexten zu diesem Thema sehr wahrscheinlich sind — mit Bedeutung und einem Beispiel.\n2. HÖREN (das Video ist der Hörtext; die Lösungen nicht in den Aufgaben verraten)\n   Aufgabe 1 — 8 Notizen mit Lücken zu den wichtigsten Informationen (Stichworte).\n   Aufgabe 2 — 8 Aussagen: richtig oder falsch?\n   Aufgabe 3 — 5 Fragen mit kurzen Antworten (Meinungen, Gründe, Folgen).\n3. LESEN — schreibe einen neuen wissenschaftsnahen Text von etwa 450 Wörtern zum Thema des Videos (Absätze A–E), dann 10 Aufgaben: 4 Zuordnungen von Überschriften zu Absätzen, 3 Multiple-Choice-Fragen, 3 Aussagen mit „Ja / Nein / Text sagt dazu nichts“.\n4. SCHREIBEN — eine TestDaF-Schreibaufgabe zum Thema: eine kleine Grafik oder Tabelle mit erfundenen Zahlen (sag deutlich, dass die Zahlen zur Übung erfunden sind), zwei Positionen; ich soll die Grafik beschreiben, die Positionen vergleichen und begründet Stellung nehmen (mindestens 250 Wörter). Dazu 12 Redemittel für Grafikbeschreibung und Argumentation.\n5. SPRECHEN — 4 Aufgaben wie im TestDaF: (1) eine Situation beschreiben / Auskunft geben, (2) Optionen vergleichen und eine Empfehlung geben, (3) zu einer These Stellung nehmen, (4) Hypothesen zu einer Entwicklung bilden — jeweils mit Vorbereitungs- und Sprechzeit und 6 passenden Redemitteln.\n6. LÖSUNGEN — nach einer Zeile „---LÖSUNGEN---“: alle Lösungen zu Hören und Lesen (mit dem Satz, der sie belegt), dazu ein kurzer Mustertext auf Niveau TDN 5 für Schreiben und was ihn zu TDN 5 macht.\n\nSchreibe alles auf Deutsch, nur die Bedeutungen und kurzen Erklärungen auf §EX§. Klarer Text mit Überschriften, keine Tabellen.\n\n",
    )

    /** A TestDaF (German) or IELTS Academic (English) practice set built on the whole video. */
    fun examPrompt(exam: String, name: String, cues: List<Cue>, myWords: List<String>, explain: String = "en", examWords: List<String> = emptyList()): String {
        val ex = EXPLAIN[explain] ?: "English"
        var text = transcript(cues)
        val cut = text.length > MAX_TRANSCRIPT
        if (cut) text = text.take(MAX_TRANSCRIPT).substringBeforeLast(' ') + " …"
        val mine = myWords.map { it.trim() }.filter { it.isNotEmpty() }.distinct().joinToString(", ").take(1200)
        val found = examWords.map { it.trim() }.filter { it.isNotEmpty() }.distinct().joinToString(", ").take(1500)
        val sb = StringBuilder(EXAM_TEXT.getValue(exam).replace("§EX§", ex))
        if (found.isNotEmpty()) sb.append("B2–C2 words in this video (from the CEFR word lists): ").append(found).append("\n\n")
        if (mine.isNotEmpty()) sb.append("Words I have already saved from this video: ").append(mine).append("\n\n")
        sb.append("Video: ").append(name).append(if (cut) " (the transcript is long — only its first part is given)" else "").append('\n')
        sb.append("TRANSCRIPT (").append(if (exam == "IELTS") "English" else "German").append("):\n").append(text)
        return sb.toString()
    }
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

    fun prompt(level: String, lang: String, name: String, cues: List<Cue>, myWords: List<String>, explain: String = "en",
               examWords: List<String> = emptyList()): String {
        if (level in EXAMS) return examPrompt(level, name, cues, myWords, explain, examWords)
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
