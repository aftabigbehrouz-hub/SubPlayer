package com.behrouz.subplayer.learn

/**
 * Word levels (A1…C2) for colouring subtitles — the same lists as the Windows app.
 * English: CEFR-J Vocabulary Profile 1.5 (Tono Laboratory, TUFS) + Octanove Vocabulary Profile C1/C2 (CC BY-SA 4.0).
 * German: no freely licensed CEFR list exists, so the level is an ESTIMATE from how common the base word is
 * (FrequencyWords 2018 by Hermit Dave, from OpenSubtitles, CC BY-SA 4.0): A1 = 1,000 most common base words, A2 < 2,000,
 * B1 < 4,000, B2 < 7,000, C1 < 12,000, rarer = C2. Built by tools/levels/build_levels.py; files in assets/levels-xx.tsv.
 */
class Levels(private val load: (String) -> String?) {

    companion object {
        val NAMES = listOf("", "A1", "A2", "B1", "B2", "C1", "C2")
        val COLORS = longArrayOf(0xFFFFFFFF, 0xFF5BE38F, 0xFF3EF0FF, 0xFF5B8CFF, 0xFFB07CFF, 0xFFFFB347, 0xFFFF5C8A)
        fun source(lang: String) = if (lang == "en") "CEFR-J / Octanove (C1–C2); other words estimated"
                                   else "estimated from word frequency (no official German list exists)"
        private val LETTER = Regex("""[\p{L}]""")

        fun parseTable(text: String): Map<String, Int> {
            val t = HashMap<String, Int>(30_000)
            for (line in text.lineSequence()) {
                val tab = line.indexOf('\t'); if (tab <= 0) continue
                line.substring(tab + 1).trim().toIntOrNull()?.let { t[line.substring(0, tab)] = it }
            }
            return t
        }
    }

    private val tables = HashMap<String, Map<String, Int>>()
    private val cache = HashMap<String, Int>()

    @Synchronized
    fun table(lang: String): Map<String, Int> = tables.getOrPut(lang) { load("levels-$lang.tsv")?.let { parseTable(it) } ?: emptyMap() }

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
        val t = table(lang)
        var lv = t[w] ?: 0
        if (lemmas != null) {
            val rows = runCatching { lemmas(w) }.getOrDefault(emptyList())
            if (rows.isNotEmpty()) {
                val found = rows.mapNotNull { t[it.lowercase()] }.toMutableList()
                if (lv > 0) found.add(lv)
                lv = found.minOrNull() ?: 6
            } else if (lv == 0 && lang == "en" && word.firstOrNull()?.isUpperCase() == true) lv = 0
        }
        synchronized(this) { if (cache.size > 200_000) cache.clear(); cache[key] = lv }
        return lv
    }
}
