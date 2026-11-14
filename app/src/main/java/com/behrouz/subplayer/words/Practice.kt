package com.behrouz.subplayer.words

import android.content.Context
import java.util.Locale
import java.util.TimeZone
import kotlin.random.Random

/** An extra example sentence for a saved word. */
data class Example(val id: Long = 0, val wordId: Long = 0, val de: String, val en: String = "", val fa: String = "", val created: Long = 0,
                   val uid: String = "", val updated: Long = 0)

/** Turns text pasted from ChatGPT, Grok, DWDS, dict.cc … into example sentences. */
object Sentences {

    private val LABEL = Regex("""^\s*(DE|EN|FA|Deutsch|German|English|Englisch|Persian|Persisch|Farsi|فارسی)\s*[:：]\s*""", RegexOption.IGNORE_CASE)
    private val BULLET = Regex("""^\s*(?:[-*•>]+|\d+[.)]|[(]\d+[)])\s*""")
    private val ARABIC = Regex("""[؀-ۿ]""")

    private fun clean(s: String) = s.replace("**", "").replace("__", "").replace(Regex("""^[\s"„“”»«']+|[\s"„“”»«']+$"""), "").trim()

    private fun isPersian(s: String) = ARABIC.containsMatchIn(s)

    /**
     * Accepts
     *   "DE: … | EN: … | FA: …"      (the format the app asks the AI for)
     *   "… | … | …"                   (any 2–3 parts separated by |; Persian found by script)
     *   blocks of "DE: …" / "EN: …" / "FA: …" lines
     *   plain German sentences, one per line (when nothing is labelled)
     */
    /**
     * [primary] = the language being learnt ("de" or "en"). Its sentence goes in Example.de (the "sentence" field),
     * the other language in Example.en (the "translation" field), Persian in fa.
     */
    fun parse(raw: String, max: Int = 12, primary: String = "de"): List<Example> {
        val lines = raw.replace("\r", "").split('\n').map { clean(it.replace(BULLET, "").replace("**", "")) }.filter { it.isNotEmpty() }
        val structured = lines.any { it.contains('|') || LABEL.containsMatchIn(it) }
        val out = ArrayList<Example>()
        if (structured) {
            // label blocks (DE: … / EN: … / FA: … on separate lines) are grouped: a new block starts when a field repeats
            var cur: Example? = null
            fun flush() { cur?.let { if (it.de.isNotEmpty()) out.add(it) }; cur = null }
            for (line in lines) {
                if (line.contains('|')) {
                    flush()
                    val parts = line.split('|').map { clean(clean(it).replace(LABEL, "")) }.filter { it.isNotEmpty() }
                    if (parts.isEmpty()) continue
                    val fa = parts.firstOrNull { isPersian(it) } ?: ""
                    val rest = parts.filter { !isPersian(it) }
                    val de = rest.getOrNull(0) ?: continue
                    if (de.split(' ').size < 2) continue          // header rows like "DE | EN | FA"
                    out.add(Example(de = de, en = rest.getOrNull(1) ?: "", fa = fa))
                } else {
                    val m = LABEL.find(line) ?: continue
                    val label = m.groupValues[1].lowercase(Locale.ROOT)
                    val value = clean(line.substring(m.range.last + 1))
                    if (value.isEmpty()) continue
                    val isDe = label == "de" || label == "deutsch" || label == "german"
                    val isEn = label == "en" || label == "english" || label == "englisch"
                    val field = when {
                        (if (primary == "en") isEn else isDe) -> 0
                        (if (primary == "en") isDe else isEn) -> 1
                        else -> 2
                    }
                    var c = cur ?: Example(de = "")
                    val taken = when (field) { 0 -> c.de.isNotEmpty(); 1 -> c.en.isNotEmpty(); else -> c.fa.isNotEmpty() }
                    if (taken) { flush(); c = Example(de = "") }
                    c = when (field) { 0 -> c.copy(de = value); 1 -> c.copy(en = value); else -> c.copy(fa = value) }
                    cur = c
                }
            }
            flush()
        } else {
            for (line in lines) {
                val t = clean(line)
                if (!isPersian(t) && t.split(' ').size >= 3 && t.last() in ".!?") out.add(Example(de = t))
            }
        }
        return out.distinctBy { it.de.lowercase() }.take(max)
    }
}

/** A gap-fill question: the sentence with the saved word blanked out. */
data class Cloze(val word: SavedWord, val before: String, val answer: String, val after: String, val en: String, val fa: String) {
    val sentence get() = before + answer + after
}

object Practice {

    private val TOKEN = Regex("""[\p{L}][\p{L}\-']*""")

    /** Blanks the word (or its inflected form) in [sentence]; null if it can't be found. */
    fun cloze(w: SavedWord, sentence: String, en: String = "", fa: String = ""): Cloze? {
        if (sentence.isBlank()) return null
        // phrases: find the whole phrase
        if (w.text.contains(' ')) {
            val i = sentence.indexOf(w.text, ignoreCase = true)
            return if (i < 0) null else Cloze(w, sentence.substring(0, i), sentence.substring(i, i + w.text.length), sentence.substring(i + w.text.length), en, fa)
        }
        val tokens = TOKEN.findAll(sentence).toList()
        fun pick(test: (String) -> Boolean) = tokens.firstOrNull { test(it.value.lowercase()) }
        val text = w.text.lowercase()
        val lemma = w.lemma.lowercase()
        val stem = (if (lemma.length >= text.length) lemma else text).let { it.take(maxOf(4, it.length - 3)) }
        val m = pick { it == text } ?: pick { it == lemma } ?: pick { it.length >= 4 && it.startsWith(stem) } ?: return null
        return Cloze(w, sentence.substring(0, m.range.first), m.value, sentence.substring(m.range.last + 1), en, fa)
    }

    /** 4 answer choices (correct + 3 others from the pool), or empty = type the answer. */
    fun choices(answer: String, pool: List<String>, rnd: Random): List<String> {
        val others = pool.map { it.trim() }.filter { it.isNotEmpty() && !it.equals(answer, ignoreCase = true) && !it.contains(' ') }
            .distinctBy { it.lowercase() }.shuffled(rnd).take(3)
        if (others.size < 3) return emptyList()
        return (others + answer).shuffled(rnd)
    }

    /** Lenient comparison: case, punctuation, ß/ss and ae/oe/ue for umlauts don't matter. */
    fun normalize(s: String) = s.lowercase(Locale.GERMAN).trim()
        .replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
        .replace(Regex("""[^\p{L}\p{N} ]"""), "").replace(Regex("\\s+"), " ")

    fun same(a: String, b: String) = normalize(a) == normalize(b)

    data class Mark(val word: String, val ok: Boolean)

    /** Dictation: marks each expected word as heard correctly or not (longest common subsequence). */
    fun dictation(expected: String, typed: String): Pair<List<Mark>, Int> {
        val e = expected.split(Regex("\\s+")).filter { it.isNotBlank() }
        val t = typed.split(Regex("\\s+")).filter { it.isNotBlank() }.map { normalize(it) }
        val en = e.map { normalize(it) }
        val dp = Array(e.size + 1) { IntArray(t.size + 1) }
        for (i in e.indices.reversed()) for (j in t.indices.reversed())
            dp[i][j] = if (en[i] == t[j] && en[i].isNotEmpty()) dp[i + 1][j + 1] + 1 else maxOf(dp[i + 1][j], dp[i][j + 1])
        val ok = BooleanArray(e.size)
        var i = 0; var j = 0
        while (i < e.size && j < t.size) {
            when {
                en[i] == t[j] && en[i].isNotEmpty() -> { ok[i] = true; i++; j++ }
                dp[i + 1][j] >= dp[i][j + 1] -> i++
                else -> j++
            }
        }
        val marks = e.mapIndexed { k, w -> Mark(w, ok[k] || en[k].isEmpty()) }
        val score = if (e.isEmpty()) 0 else marks.count { it.ok } * 100 / e.size
        return marks to score
    }
}

/** Daily streak and today's practice count. */
class Progress(ctx: Context) {
    private val p = ctx.getSharedPreferences("progress", Context.MODE_PRIVATE)

    private fun today(now: Long = System.currentTimeMillis()): Long {
        val off = TimeZone.getDefault().getOffset(now)
        return (now + off) / 86_400_000L
    }

    val streak: Int get() {
        val last = p.getLong("last_day", -10)
        val s = p.getInt("streak", 0)
        return if (last >= today() - 1) s else 0
    }

    val todayCount: Int get() = if (p.getLong("last_day", -10) == today()) p.getInt("today", 0) else 0

    val raw: Triple<Int, Long, Int> get() = Triple(p.getInt("streak", 0), p.getLong("last_day", -10), p.getInt("today", 0))

    fun setRaw(streak: Int, lastDay: Long, today: Int) {
        p.edit().putInt("streak", streak).putLong("last_day", lastDay).putInt("today", today).apply()
    }

    /** Call for every answered review or practice question. */
    fun record() {
        val d = today()
        val last = p.getLong("last_day", -10)
        val streak = when (last) { d -> p.getInt("streak", 1); d - 1 -> p.getInt("streak", 0) + 1; else -> 1 }
        val count = if (last == d) p.getInt("today", 0) + 1 else 1
        p.edit().putLong("last_day", d).putInt("streak", streak).putInt("today", count).apply()
    }
}
