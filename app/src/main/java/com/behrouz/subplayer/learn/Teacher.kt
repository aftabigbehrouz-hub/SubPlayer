package com.behrouz.subplayer.learn

import com.behrouz.subplayer.words.Collocation
import com.behrouz.subplayer.words.Example
import com.behrouz.subplayer.words.ExamQuestion
import org.json.JSONArray
import org.json.JSONObject

/**
 * The teacher's questions for ChatGPT, Gemini, DeepSeek, Grok, GapGPT … — the same questions the Windows teacher asks
 * (ollama.py word_prompt / sentence_prompt / check_prompt / ask_prompt, questions.py teacher_prompt) — and the reading of
 * their answers. On the phone there is no Ollama: the question goes to the AI app or website, the answer comes back by Paste.
 */
object Teacher {
    enum class Mode(val title: String) { WORD("Word"), SENTENCE("Sentence"), CHECK("Check mine"), ASK("Ask"), EXAM("TestDaF") }

    private fun target(lang: String) = if (lang == "en") "English" else "German"
    private fun ex(explain: String) = Lessons.EXPLAIN[explain] ?: "English"

    private fun intro(lang: String, explain: String): String {
        val exam = if (lang == "en") "IELTS" else "Goethe, telc and TestDaF"
        return "You are an experienced, warm ${target(lang)} teacher who prepares adults for $exam exams. Your learner speaks " +
            "Persian and English. Explain in ${ex(explain)}; every example sentence is natural, correct, everyday ${target(lang)}. " +
            "Be precise and brief. Never invent words or meanings — if unsure, leave the field empty.\n\n"
    }

    fun wordPrompt(word: String, lemma: String, sentence: String, lang: String, level: String, explain: String): String {
        val t = target(lang); val e = ex(explain)
        val forms = if (lang != "en") "for a noun: article and plural; for a verb: Präteritum, Perfekt (with haben/sein) and the case it takes; " +
            "for an adjective: comparative" else "word family (noun / verb / adjective / adverb) and irregular forms"
        return intro(lang, explain) +
            "The $t word „$word“ (base form: ${lemma.ifBlank { word }})" + (if (sentence.isNotBlank()) " appears in this line of a video:\n„${sentence.replace('\n', ' ')}“\n" else ".\n") +
            "The learner's level is $level.\n\n" +
            "Answer ONLY with a JSON object with these keys:\n" +
            "  \"meaning\": the meaning of the word IN THIS LINE, in $e (one short sentence),\n" +
            "  \"persian\": the meaning in Persian (a few words),\n" +
            "  \"forms\": $forms,\n" +
            "  \"collocations\": 8 typical collocations of the base form (verb + noun, adjective + noun, noun + preposition, fixed " +
            "expressions — the combinations native speakers really use), each as {\"phrase\": \"...\", \"meaning\": \"... in $e\", " +
            "\"example\": \"a short $t sentence\"},\n" +
            "  \"examples\": 5 new $t example sentences at level $level, in different everyday situations, using the collocations, " +
            "each as {\"sentence\": \"...\", \"translation\": \"... in $e\", \"persian\": \"... in Persian\"},\n" +
            "  \"grammar\": the preposition or case the word goes with, or another grammar point it brings (one line, may be empty),\n" +
            "  \"synonyms\": up to 4 synonyms or near-synonyms, with the difference in a few words,\n" +
            "  \"opposite\": an antonym if there is a natural one, else empty,\n" +
            "  \"tip\": one memory tip or the typical mistake learners make with this word, in $e."
    }

    fun sentencePrompt(sentence: String, lang: String, explain: String, level: String): String =
        intro(lang, explain) +
            "Explain this ${target(lang)} sentence from a video for a learner at level $level:\n„${sentence.replace('\n', ' ')}“\n\n" +
            "In ${ex(explain)}, with short headings:\n" +
            "1. Translation (natural).\n" +
            "2. Structure: the parts of the sentence, where the verb(s) stand and why" +
            (if (lang != "en") ", cases (Nominativ / Akkusativ / Dativ / Genitiv) of the noun groups, separable verbs, tense and mood"
             else ", tense and aspect, phrasal verbs, clause types") + ".\n" +
            "3. Words and expressions worth learning in it (with meaning).\n" +
            "4. Three new ${target(lang)} sentences built on the same pattern, each with its translation.\n" +
            "Plain text, no tables."

    fun checkPrompt(word: String, attempt: String, lang: String, explain: String, level: String): String =
        intro(lang, explain) +
            "A learner at level $level wrote this ${target(lang)} sentence to practise the word „$word“:\n„$attempt“\n\n" +
            "Answer ONLY with a JSON object:\n" +
            "  \"correct\": true or false (true only if it is fully correct and natural),\n" +
            "  \"corrected\": the corrected sentence (the same if it was correct),\n" +
            "  \"explanation\": in ${ex(explain)}, what was wrong and the rule behind it — or why it is good (2–4 short sentences),\n" +
            "  \"better\": one more natural or more advanced way to say it in ${target(lang)},\n" +
            "  \"score\": a number from 1 to 10."

    fun askPrompt(question: String, word: String, sentence: String, video: String, lang: String, explain: String, level: String): String {
        val ctx = listOfNotNull(word.takeIf { it.isNotBlank() }?.let { "the word „$it“" },
            sentence.takeIf { it.isNotBlank() }?.let { "this line: „${it.replace('\n', ' ')}“" },
            video.takeIf { it.isNotBlank() }?.let { "from the video “$it”" })
        return "My ${target(lang)} level is $level. " + (if (ctx.isNotEmpty()) "We are looking at " + ctx.joinToString(", ") + ".\n" else "") +
            "My question: $question\n\nAnswer in ${ex(explain)}, with ${target(lang)} examples where they help."
    }

    fun examPrompt(word: String, lemma: String, sentence: String, lang: String, level: String, explain: String, n: Int = 6): String {
        val exam = if (lang == "en") "IELTS Academic" else "TestDaF"
        val kinds = if (lang == "en") "multiple choice (A–D), TRUE / FALSE / NOT GIVEN on a 2–3 sentence text, gap-fill, and choosing the right " +
            "collocation or word form" else "Multiple Choice (A–D), Ja / Nein / Text sagt dazu nichts zu einem kurzen Text von 2–3 Sätzen, " +
            "Lückentext und die richtige Kollokation, Präposition oder Form"
        return "Write $n $exam-style practice questions in ${target(lang)} at level $level that test the word „${lemma.ifBlank { word }}“" +
            (if (sentence.isNotBlank()) " (as in this line: „${sentence.replace('\n', ' ')}“)" else "") + ".\n" +
            "Mix these kinds: $kinds. Put any short text the question needs into the question itself.\n" +
            "Answer ONLY with a JSON object: {\"questions\": [ {\"question\": \"...\", \"options\": [\"...\", \"...\"] (empty list for an " +
            "open question), \"answer\": \"the correct option or answer, exactly as written in options\", " +
            "\"explanation\": \"why, in ${ex(explain)}, one or two sentences\"} ]}"
    }

    /** The first {...} of a (cleaned) answer as JSON, or null. */
    fun json(raw: String): JSONObject? {
        val t = Cards.cleanAi(raw)
        val a = t.indexOf('{'); val b = t.lastIndexOf('}')
        if (a < 0 || b <= a) return null
        return runCatching { JSONObject(t.substring(a, b + 1)) }.getOrNull()
    }

    private fun str(v: Any?): String = when (v) {
        null, JSONObject.NULL -> ""
        is JSONArray -> (0 until v.length()).map { str(v.opt(it)) }.filter { it.isNotBlank() }.joinToString(" · ")
        is JSONObject -> v.keys().asSequence().map { k -> "$k: ${str(v.opt(k))}" }.joinToString(" · ")
        else -> v.toString().trim()
    }

    /** What a word answer gives: meaning, Persian, collocations, examples — and a readable text of the whole answer. */
    data class WordAnswer(val meaning: String, val persian: String, val collocations: List<Collocation>, val examples: List<Example>, val readable: String)

    fun readWord(raw: String, lang: String, lemma: String): WordAnswer {
        val o = json(raw)
        if (o == null) {                       // not JSON: KOLL lines / tables and DE: … | EN: … lines
            val (cols, rest) = Cards.collocations(Cards.cleanAi(raw), lang, lemma)
            val ex = com.behrouz.subplayer.words.Sentences.parse(rest, primary = lang)
            return WordAnswer("", "", cols, ex, Cards.cleanAi(raw))
        }
        val (cols, ex) = Cards.fromJson(raw, lang, lemma) ?: (emptyList<Collocation>() to emptyList())
        val sb = StringBuilder()
        fun line(label: String, key: String) { str(o.opt(key)).takeIf { it.isNotBlank() }?.let { sb.append("$label: $it\n") } }
        line("Meaning", "meaning"); line("Persian", "persian"); line("Forms", "forms"); line("Grammar", "grammar")
        line("Synonyms", "synonyms"); line("Opposite", "opposite"); line("Tip", "tip")
        if (cols.isNotEmpty()) {
            sb.append("\nCollocations\n")
            cols.forEach { c -> sb.append("• ${c.phrase}" + (if (c.meaning.isNotBlank()) " — ${c.meaning}" else "") + "\n" +
                (if (c.example.isNotBlank()) "   ${c.example}\n" else "")) }
        }
        if (ex.isNotEmpty()) {
            sb.append("\nSentences\n")
            ex.forEach { e -> sb.append("• ${e.de}\n" + (if (e.en.isNotBlank()) "   ${e.en}\n" else "") + (if (e.fa.isNotBlank()) "   ${e.fa}\n" else "")) }
        }
        return WordAnswer(str(o.opt("meaning")), str(o.opt("persian")), cols, ex, sb.toString().trim())
    }

    fun readCheck(raw: String): String {
        val o = json(raw) ?: return Cards.cleanAi(raw)
        val ok = o.optBoolean("correct", false)
        return listOfNotNull(
            (if (ok) "✓ Correct" else "✗ Not quite") + (o.opt("score")?.let { s -> str(s).takeIf { it.isNotBlank() }?.let { " · $it/10" } } ?: ""),
            str(o.opt("corrected")).takeIf { it.isNotBlank() && !ok }?.let { "Corrected: $it" },
            str(o.opt("explanation")).takeIf { it.isNotBlank() },
            str(o.opt("better")).takeIf { it.isNotBlank() }?.let { "Better: $it" }
        ).joinToString("\n\n")
    }

    /** Exam questions of an answer: the JSON format, or ---REVIEW--- / Q: lines (Cards.parse). */
    fun readExam(raw: String, lang: String, lemma: String, video: String): List<ExamQuestion> {
        val o = json(raw)
        val arr = o?.optJSONArray("questions")
        if (arr != null) {
            val out = ArrayList<ExamQuestion>()
            for (i in 0 until arr.length()) {
                val x = arr.optJSONObject(i) ?: continue
                val q = str(x.opt("question")); val a = str(x.opt("answer"))
                if (q.isBlank() || a.isBlank()) continue
                val opts = x.optJSONArray("options")?.let { oa -> (0 until oa.length()).map { str(oa.opt(it)) }.filter { it.isNotBlank() } } ?: emptyList()
                out.add(ExamQuestion(question = q, answer = a, options = opts, explanation = str(x.opt("explanation")), kind = Cards.kind(opts),
                    lang = lang, lemma = lemma, videoName = video, source = "teacher"))
            }
            return out
        }
        return Cards.parse(raw, lang, video, "teacher").map { it.copy(lemma = it.lemma.ifBlank { lemma }) }
    }
}
