package com.behrouz.subplayer.learn

import com.behrouz.subplayer.words.Collocation
import com.behrouz.subplayer.words.ExamQuestion

/**
 * Review cards in a pasted AI lesson (same format and rules as the Windows app, questions.py):
 *
 *     ---REVIEW---
 *     Q: Laut dem Video sind die Angriffe zurückgegangen.
 *     O: richtig | falsch
 *     A: falsch
 *     E: „wieder etliche Angriffe …“
 *
 * and collocation lines in a pasted word answer:  KOLL: etliche Male | several times | Ich war etliche Male dort.
 */
object Cards {
    const val MARK = "---REVIEW---"
    private val LINE = Regex("""^\s*(?:\d+[.)]\s*)?(?:\*\*)?(Q|O|A|E|F|L|Frage|Optionen|Antwort|Lösung|Begründung|Question|Options|Answer|Why)(?:\*\*)?\s*[:：]\s*(.*)$""",
        RegexOption.IGNORE_CASE)
    private val KEY = mapOf("q" to "q", "f" to "q", "frage" to "q", "question" to "q", "o" to "o", "optionen" to "o", "options" to "o",
        "a" to "a", "l" to "a", "antwort" to "a", "lösung" to "a", "answer" to "a", "e" to "e", "begründung" to "e", "why" to "e")

    fun kind(opts: List<String>): String {
        val low = opts.map { it.lowercase() }
        return when {
            opts.isEmpty() -> "open"
            low.all { it in setOf("richtig", "falsch", "true", "false") } -> "tf"
            low.any { "sagt dazu nichts" in it || "not given" in it } -> "yn"
            else -> "mc"
        }
    }

    fun options(raw: String): List<String> {
        val r = raw.trim()
        if (r.isEmpty() || r.lowercase() in setOf("-", "—", "(leer)", "leer", "none", "keine")) return emptyList()
        var parts = r.split('|').map { it.trim() }
        if (parts.size == 1) parts = r.split(Regex("""\s+(?=[A-F]\)\s)""")).map { it.trim() }
        return parts.filter { it.isNotEmpty() }
    }

    /** The cards after ---REVIEW--- (or in the whole text, when it is written as Q:/O:/A:/E: cards without the mark). */
    fun parse(text: String, lang: String = "de", videoName: String = "", source: String = ""): List<ExamQuestion> {
        val txt = cleanAi(text)
        val i = txt.lastIndexOf(MARK)
        val body = if (i >= 0) txt.substring(i + MARK.length) else txt
        val out = ArrayList<ExamQuestion>()
        val cur = HashMap<String, String>()
        var last: String? = null
        fun flush() {
            val q = cur["q"]; val a = cur["a"]
            if (!q.isNullOrBlank() && !a.isNullOrBlank()) {
                val opts = options(cur["o"] ?: "")
                out.add(ExamQuestion(question = q.trim(), answer = a.trim(), options = opts, explanation = (cur["e"] ?: "").trim(),
                    kind = kind(opts), lang = lang, videoName = videoName, source = source))
            }
        }
        for (raw in body.replace("\r", "").split('\n')) {
            val line = raw.trim().trimStart('-', '•', '*', ' ')
            val m = LINE.find(line)
            if (m == null) {
                val t = raw.trim()
                if (last != null && t.isNotEmpty() && !t.startsWith("---") && !t.startsWith("===")) cur[last!!] = (cur[last!!] ?: "") + " " + t
                continue
            }
            val k = KEY[m.groupValues[1].lowercase()] ?: continue
            if (k == "q" && !cur["q"].isNullOrBlank()) { flush(); cur.clear() }
            cur[k] = m.groupValues[2].trim()
            last = k
        }
        flush()
        if (i < 0 && out.size < 2) return emptyList()           // a stray "A: …" in a normal lesson is no card set
        return out
    }

    /** Is the answer the right one? Same text, the same letter (A / B), or the answer's words inside the option. */
    fun isAnswer(option: String, answer: String): Boolean {
        val o = option.lowercase().split(Regex("\\s+")).joinToString(" ")
        val a = answer.lowercase().split(Regex("\\s+")).joinToString(" ")
        if (a.isBlank()) return false
        if (o == a) return true
        val lo = Regex("""^\(?([a-f])[).:]""").find(o)
        val la = Regex("""^\(?([a-f])(?:[).:]|$)""").find(a)
        if (lo != null && la != null) return lo.groupValues[1] == la.groupValues[1]
        fun strip(t: String) = t.replace(Regex("""^\(?[a-f][).:]\s*"""), "").trim(' ', '.')
        return strip(o) == strip(a) || (strip(a).length > 3 && strip(o).contains(strip(a)))
    }

    private val COLL = Regex("""^\s*(?:[-*•]\s*)?(?:\*\*)?(KOLL|COLL|Kollokation|Collocation)(?:\*\*)?\s*[:：]\s*(.*)$""", RegexOption.IGNORE_CASE)

    private val HEADER_WORDS = setOf("german", "deutsch", "english", "englisch", "persian", "persisch", "farsi", "فارسی", "collocation",
        "collocations", "kollokation", "kollokationen", "meaning", "bedeutung", "example", "examples", "beispiel", "beispielsatz",
        "translation", "übersetzung", "phrase", "ausdruck", "word", "wort", "sentence", "satz", "#", "nr", "no")
    private val PERSIAN = Regex("[؀-ۿ]")
    private val LABEL = Regex("""^\s*(DE|EN|FA|Deutsch|German|English|Englisch|Persian|Persisch|Farsi|فارسی)\s*[:：]\s*""", RegexOption.IGNORE_CASE)

    private fun clean(s: String) = s.replace("**", "").replace("__", "").trim().trim('"', '„', '“', '”', '»', '«', '\'').trim()

    /** A table header cell such as "German collocation" or "English". */
    fun isHeader(cell: String): Boolean {
        val ws = cell.split(Regex("\\s+")).map { it.trim('*', ':', '(', ')').lowercase() }.filter { it.isNotEmpty() }
        return ws.isNotEmpty() && ws.all { it in HEADER_WORDS }
    }

    /**
     * An answer copied from ChatGPT & co. as it should be: HTML entities (&#x20; for a space) decoded, the backslash some copy
     * buttons put at the end of every line removed, markdown escapes (\\* \\_ \\#) undone, ``` fences dropped.
     * Same as the Windows app (practice.clean_ai).
     */
    fun cleanAi(text: String): String {
        var t = text.replace("\r", "").replace('\u00a0', ' ')
        t = Regex("&#x([0-9a-fA-F]+);").replace(t) { m -> m.groupValues[1].toInt(16).toChar().toString() }
        t = Regex("&#([0-9]+);").replace(t) { m -> m.groupValues[1].toInt().toChar().toString() }
        t = t.replace("&quot;", "\"").replace("&apos;", "'").replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
            .replace("&nbsp;", " ").replace("&amp;", "&")
        t = Regex("""\\[ \t]*$""", RegexOption.MULTILINE).replace(t, "")
        t = Regex("""\\([*_#>\[\]()`~|-])""").replace(t) { it.groupValues[1] }
        t = Regex("""^\s*```[\w-]*\s*$""", RegexOption.MULTILINE).replace(t, "")
        return t.trim()
    }

    /** A JSON answer (the teacher's format): its collocations and example sentences, or null if the text is not JSON. */
    fun fromJson(raw: String, lang: String, lemma: String): Pair<List<Collocation>, List<com.behrouz.subplayer.words.Example>>? {
        val t = cleanAi(raw)
        val a = t.indexOf('{'); val b = t.lastIndexOf('}')
        if (a < 0 || b <= a) return null
        val o = runCatching { org.json.JSONObject(t.substring(a, b + 1)) }.getOrNull() ?: return null
        val cols = ArrayList<Collocation>()
        o.optJSONArray("collocations")?.let { arr ->
            for (i in 0 until arr.length()) {
                val x = arr.opt(i)
                if (x is org.json.JSONObject) {
                    val ph = x.optString("phrase").trim()
                    if (ph.isNotEmpty()) cols.add(Collocation(lang = lang, lemma = lemma, phrase = ph, meaning = x.optString("meaning"), example = x.optString("example")))
                } else if (x is String && x.isNotBlank()) cols.add(Collocation(lang = lang, lemma = lemma, phrase = x.trim()))
            }
        }
        val ex = ArrayList<com.behrouz.subplayer.words.Example>()
        o.optJSONArray("examples")?.let { arr ->
            for (i in 0 until arr.length()) {
                val x = arr.optJSONObject(i) ?: continue
                val de = x.optString("sentence").trim()
                if (de.isNotEmpty()) ex.add(com.behrouz.subplayer.words.Example(de = de, en = x.optString("translation"), fa = x.optString("persian")))
            }
        }
        return cols to ex
    }

    /** Lines left by an escaped paste in earlier versions ({\\, &#x20; "meaning": …) — not real collocations. */
    fun isBroken(phrase: String): Boolean =
        Regex("""(&#x?[0-9a-f]+;|^[{}\[\],\\]+$|"\s*:|\\$)""", RegexOption.IGNORE_CASE).containsMatchIn(phrase)

    /** A collocation, not a sentence: at most 5 words and no full stop / ! / ? at the end. */
    fun isPhrase(t: String): Boolean {
        val s = t.trim()
        return s.isNotEmpty() && s.split(Regex("\\s+")).size <= 5 && s.last() !in ".!?…" && !PERSIAN.containsMatchIn(s)
    }

    /**
     * Collocations in a pasted answer — "KOLL: phrase | meaning | example" lines, and table rows whose first cell is a short
     * phrase (ChatGPT often answers with a table) — and the rest of the text (the sentences). Headers and separators are dropped.
     * Same rules as the Windows app (practice.split_collocations).
     */
    fun collocations(raw: String, lang: String, lemma: String): Pair<List<Collocation>, String> {
        val out = ArrayList<Collocation>()
        val rest = StringBuilder()
        for (line in raw.replace("\r", "").split('\n')) {
            val m = COLL.find(line)
            if (m != null) {
                val parts = m.groupValues[2].split('|').map { clean(it) }
                if (parts.firstOrNull().isNullOrBlank()) continue
                out.add(Collocation(lang = lang, lemma = lemma, phrase = parts[0], meaning = parts.getOrElse(1) { "" }, example = parts.getOrElse(2) { "" }))
                continue
            }
            val st = line.trim().replace(Regex("""^(?:[-*•>]+|\d+[.)])\s*"""), "")
            if ('|' in st) {
                val cells = st.trim().trim('|').split('|').map { clean(clean(it).replace(LABEL, "")) }.filter { it.isNotEmpty() }
                if (cells.isEmpty() || cells.all { c -> c.all { it in "-:= " } }) continue          // |---|---|
                if (cells.filter { !PERSIAN.containsMatchIn(it) }.all { isHeader(it) }) continue    // the header row
                if (isPhrase(cells[0])) {
                    val others = cells.drop(1)
                    val fa = others.firstOrNull { PERSIAN.containsMatchIn(it) } ?: ""
                    val ex = others.firstOrNull { !PERSIAN.containsMatchIn(it) && it.split(' ').size >= 3 && it.last() in ".!?" } ?: ""
                    val mean = others.firstOrNull { !PERSIAN.containsMatchIn(it) && it != ex } ?: ""
                    out.add(Collocation(lang = lang, lemma = lemma, phrase = cells[0], meaning = listOf(mean, fa).filter { it.isNotEmpty() }.joinToString(" · "), example = ex))
                    continue
                }
            }
            rest.append(line).append('\n')
        }
        return out to rest.toString()
    }
}
