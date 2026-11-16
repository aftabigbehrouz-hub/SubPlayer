package com.behrouz.subplayer.learn

/**
 * Word levels (A1…C2) for colouring subtitles — the same lists as the Windows app.
 * English: CEFR-J Vocabulary Profile 1.5 (Tono Laboratory, TUFS) + Octanove Vocabulary Profile C1/C2 (CC BY-SA 4.0).
 * German: the WordFeather list (Goethe/telc-oriented, CC0 version of 6 June 2026) for 2,557 words; for the rest the level is an ESTIMATE from how common the base word is
 * (FrequencyWords 2018 by Hermit Dave, from OpenSubtitles, CC BY-SA 4.0): A1 = 1,000 most common base words, A2 < 2,000,
 * B1 < 4,000, B2 < 7,000, C1 < 12,000, rarer = C2. Built by tools/levels/build_levels.py; files in assets/levels-xx.tsv.
 */
class Levels(private val load: (String) -> String?) {

    companion object {
        val NAMES = listOf("", "A1", "A2", "B1", "B2", "C1", "C2")
        val COLORS = longArrayOf(0xFFFFFFFF, 0xFF5BE38F, 0xFF3EF0FF, 0xFF5B8CFF, 0xFFB07CFF, 0xFFFFB347, 0xFFFF5C8A)
        fun source(lang: String) = if (lang == "en") "CEFR-J / Octanove (C1–C2); other words estimated"
                                   else "WordFeather list (Goethe/telc-oriented) for 2,557 words; others estimated from frequency"
        private val LETTER = Regex("""[\p{L}]""")

        /** "word<TAB>level" or "word<TAB>level<TAB>L" (L = from a published list). Listed words are stored as level + 10. */
        fun parseTable(text: String): Map<String, Int> {
            val t = HashMap<String, Int>(30_000)
            for (line in text.lineSequence()) {
                val p = line.split('\t'); if (p.size < 2 || p[0].isEmpty()) continue
                val lv = p[1].trim().toIntOrNull() ?: continue
                t[p[0]] = if (p.getOrNull(2)?.trim() == "L") lv + 10 else lv
            }
            return t
        }
    }

    private val tables = HashMap<String, Map<String, Int>>()
    private val cache = HashMap<String, Int>()

    @Synchronized
    private fun raw(lang: String): Map<String, Int> = tables.getOrPut(lang) { load("levels-$lang.tsv")?.let { parseTable(it) } ?: emptyMap() }

    private fun Map<String, Int>.lv(w: String): Int? = this[w]?.let { if (it > 10) it - 10 else it }

    /** True when the level of this base word comes from a published list, not from the frequency estimate. */
    fun listed(lemma: String, lang: String): Boolean = (raw(lang)[lemma.trim().lowercase()] ?: 0) > 10

    /**
     * 1..6, or 0 for names, numbers and unknown words. [lemmas] gives the dictionary base words of a word form
     * (null = no dictionary): the level is the lowest level of any base word ("mich" → ich = A1), and a word the
     * dictionary knows but no list has counts as C2.
     */
    fun level(word: String, lang: String, lemmas: ((String) -> List<String>)? = null): Int {
        val w = word.trim().lowercase().trim('\'', '’', '-')
        if (w.isEmpty() || !LETTER.containsMatchIn(w)) return 0
        val key = "$lang|$w"
        synchronized(this) { cache[key]?.let { return it } }
        val t = raw(lang)
        var lv = t.lv(w) ?: 0
        if (lemmas != null) {
            val rows = runCatching { lemmas(w) }.getOrDefault(emptyList())
            if (rows.isNotEmpty()) {
                val found = rows.mapNotNull { t.lv(it.lowercase()) }.toMutableList()
                if (lv > 0) found.add(lv)
                lv = found.minOrNull() ?: 6
            } else if (lv == 0 && lang == "en" && word.firstOrNull()?.isUpperCase() == true) lv = 0
        }
        synchronized(this) { if (cache.size > 200_000) cache.clear(); cache[key] = lv }
        return lv
    }
}
