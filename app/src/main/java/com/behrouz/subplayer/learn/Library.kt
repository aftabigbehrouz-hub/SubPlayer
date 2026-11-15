package com.behrouz.subplayer.learn

import com.behrouz.subplayer.subs.Cue
import com.behrouz.subplayer.subs.Srt
import java.io.File

/**
 * Your subtitled videos: every subtitle file SubPlayer made or loaded (and the ones synced from your other devices).
 * Used for "where else is this word used?" and the video study screen. A video found in "Continue watching" or in
 * My Words can be opened at the moment the word is said.
 */
object Library {

    data class Item(val file: File, val lang: String, val key: String, val uri: String?, val name: String) {
        fun cues(): List<Cue> = runCatching { Srt.parse(file.readText()) }.getOrDefault(emptyList())
    }

    data class Use(val item: Item, val index: Int, val startMs: Long, val endMs: Long, val text: String, val spans: List<IntRange>)

    data class Word(val shown: String, val count: Int, var level: Int = 0)

    private val OWN = Regex("""^(.*)_([0-9a-f]+)\.(de|en)\.srt$""")
    private val SYNCED = Regex("""^(.*)\.(de|en)\.srt$""")
    val TOKEN = Regex("""[\p{L}][\p{L}\p{N}\-'’]*""")

    /**
     * [videos] = video key (file name without extension, as AppViewModel.videoKey) → (uri, name), from recent videos
     * and saved words. One entry per video and language; SubPlayer's own files win over synced copies.
     */
    fun scan(subsDir: File, syncedDir: File, videos: Map<String, Pair<String, String>>): List<Item> {
        val out = ArrayList<Item>(); val seen = HashSet<String>()
        subsDir.listFiles()?.sortedByDescending { it.lastModified() }?.forEach { f ->
            val m = OWN.matchEntire(f.name) ?: return@forEach
            val key = m.groupValues[1]; val lang = m.groupValues[3]
            if (!seen.add("$key|$lang")) return@forEach
            val v = videos[key]
            out.add(Item(f, lang, key, v?.first, v?.second ?: key))
        }
        syncedDir.listFiles()?.forEach { f ->
            val m = SYNCED.matchEntire(f.name) ?: return@forEach
            val key = m.groupValues[1]; val lang = m.groupValues[2]
            if (!seen.add("$key|$lang")) return@forEach
            val v = videos[key]
            out.add(Item(f, lang, key, v?.first, v?.second ?: key))
        }
        return out
    }

    /** Every subtitle line in [lang] containing one of [forms] (or the phrase); (uses, files searched). */
    fun findUses(word: String, lang: String, items: List<Item>, forms: Set<String>, limit: Int = 300,
                 cancelled: () -> Boolean = { false }): Pair<List<Use>, Int> {
        val phrase = word.trim().contains(' ')
        val p = word.trim().lowercase()
        val out = ArrayList<Use>(); var n = 0
        for (it in items) {
            if (it.lang != lang) continue
            if (cancelled()) break
            n++
            it.cues().forEachIndexed { k, c ->
                val low = c.text.lowercase()
                val spans = if (phrase) {
                    val i = low.replace('\n', ' ').indexOf(p); if (i >= 0) listOf(i until i + p.length) else emptyList()
                } else TOKEN.findAll(c.text).filter { m -> m.value.lowercase().trim('\'', '’', '-') in forms }.map { m -> m.range }.toList()
                if (spans.isNotEmpty()) {
                    out.add(Use(it, k, c.startMs, c.endMs, c.text, spans))
                    if (out.size >= limit) return out to n
                }
            }
        }
        return out to n
    }

    /**
     * The words of a video's text, most frequent first. A capital letter at the start of a line or sentence doesn't make
     * a German word a noun: such words count as lowercase unless they only ever appear capitalised mid-sentence.
     */
    fun vocabulary(cues: List<Cue>, lang: String): List<Word> {
        val counts = LinkedHashMap<String, Int>()
        val lowerSeen = HashSet<String>(); val midCapital = HashSet<String>()
        for (c in cues) {
            var prevEnd = true
            for (m in TOKEN.findAll(c.text)) {
                val t = m.value.trim('\'', '’', '-')
                val before = c.text.substring(0, m.range.first).trimEnd()
                val start = prevEnd || before.isEmpty() || before.last() in ".!?:…\"„“»«"
                prevEnd = false
                if (t.length < 2) continue
                val k = t.lowercase()
                counts[k] = (counts[k] ?: 0) + 1
                if (t.first().isLowerCase()) lowerSeen.add(k) else if (!start) midCapital.add(k)
            }
        }
        return counts.map { (k, n) ->
            val shown = if (k in midCapital && k !in lowerSeen) k.replaceFirstChar { it.uppercase() } else k
            Word(shown, n)
        }.sortedWith(compareBy<Word>({ -it.count }, { it.shown.lowercase() }))
    }

    /** First line where the word appears (to save it with its sentence and moment). */
    fun firstLine(cues: List<Cue>, word: String): Int {
        val w = word.lowercase()
        return cues.indexOfFirst { c -> TOKEN.findAll(c.text).any { it.value.lowercase().trim('\'', '’', '-') == w } }
    }
}
