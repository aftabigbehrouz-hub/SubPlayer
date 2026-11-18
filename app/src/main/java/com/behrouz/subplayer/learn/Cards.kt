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
        val i = text.lastIndexOf(MARK)
        val body = if (i >= 0) text.substring(i + MARK.length) else text
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

    /** Collocation lines (KOLL: phrase | meaning | example) in a pasted answer, and the rest of the text without them. */
    fun collocations(raw: String, lang: String, lemma: String): Pair<List<Collocation>, String> {
        val out = ArrayList<Collocation>()
        val rest = StringBuilder()
        for (line in raw.replace("\r", "").split('\n')) {
            val m = COLL.find(line)
            if (m == null) { rest.append(line).append('\n'); continue }
            val parts = m.groupValues[2].split('|').map { it.trim().trim('*').trim() }
            if (parts.firstOrNull().isNullOrBlank()) continue
            out.add(Collocation(lang = lang, lemma = lemma, phrase = parts[0], meaning = parts.getOrElse(1) { "" }, example = parts.getOrElse(2) { "" }))
        }
        return out to rest.toString()
    }
}
