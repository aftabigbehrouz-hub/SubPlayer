package com.behrouz.subplayer.dict

import android.database.sqlite.SQLiteDatabase
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** Offline German dictionary built from Wiktionary (see tools/build_dict.py). */
class Dictionary(file: File) {

    data class Sense(val de: String, val examples: List<String>)

    data class Entry(
        val lemma: String,
        val pos: String,
        val posDe: String,
        val article: String,       // der / die / das for nouns
        val ipa: String,
        val hyphenation: String,
        val audioUrl: String,
        val senses: List<Sense>,
        val english: List<String>, // English meanings
        val persian: List<String>, // direct Persian translations
        val persianViaEnglish: List<String>,
        val synonyms: List<String>,
        val german: List<String> = emptyList(),   // English dictionary: German translations
        val lang: String = "de"
    )

    private val db: SQLiteDatabase =
        SQLiteDatabase.openDatabase(file.absolutePath, null, SQLiteDatabase.OPEN_READONLY)

    fun close() = db.close()

    /** Looks up a word as it appears in a subtitle (inflected forms map to their base word). */
    fun lookup(raw: String): List<Entry> {
        val word = normalize(raw)
        if (word.isEmpty()) return emptyList()
        val candidates = linkedSetOf(word.lowercase())
        // contractions: geht's -> geht, gibt's -> gibt
        if (word.endsWith("'s") || word.endsWith("’s")) candidates.add(word.dropLast(2).lowercase())
        if (word.contains('-')) candidates.add(word.substringAfterLast('-').lowercase())
        // English: possessive and contractions (Tom's, didn't → did)
        if (word.endsWith("'s") || word.endsWith("’s")) candidates.add(word.dropLast(2).lowercase())
        if (word.endsWith("n't")) candidates.add(word.dropLast(3).lowercase())

        for (key in candidates) {
            val list = query(key)
            if (list.isNotEmpty()) return rank(list, word)
        }
        return emptyList()
    }

    // ------------------------------------------------------------------ trustworthy links only
    // The dictionary file links every word form to its base word. Conjugation tables also left links that are no forms:
    // the helper verbs of compound tenses ("gebracht worden sein" → sein, haben, werden, worden, gewesen under ~13,000
    // verbs), "sie", reflexive pronouns, and the particle of separable verbs ("bringt mit" → mit). A key that many
    // entries share is therefore trusted only for the entry it names (or a pronoun); two true forms are kept by hand.
    // (The same rules as the Windows app: dictionary.py.)
    private val linkCount = HashMap<String, Int>()

    @Synchronized
    fun links(key: String): Int = linkCount.getOrPut(key) {
        if (linkCount.size > 50_000) linkCount.clear()
        db.rawQuery("SELECT count(*) FROM (SELECT 1 FROM lookup WHERE key=? LIMIT 60)", arrayOf(key)).use { c -> if (c.moveToFirst()) c.getInt(0) else 0 }
    }

    /** SQL condition + arguments selecting the entries a key truly belongs to. */
    private fun trusted(key: String): Pair<String, Array<String>> {
        val n = links(key)
        if (n <= SHARED) return "l.key=?" to arrayOf(key)
        val bad = if (n > POPULAR) NOT_A_FORM else listOf("verb")
        val variants = listOf(key, key.replaceFirstChar { it.uppercase() }, key.uppercase()).distinct()
        val extra = KEEP.filter { it.second == key }.map { it.first }
        val sql = "l.key=? AND (e.lemma IN (${variants.joinToString(",") { "?" }}) OR e.pos NOT IN (${bad.joinToString(",") { "?" }})" +
            (if (extra.isNotEmpty()) " OR (e.pos='verb' AND e.lemma IN (${extra.joinToString(",") { "?" }}))" else "") + ")"
        return sql to (listOf(key) + variants + bad + extra).toTypedArray()
    }

    /** Base words (lemmas) of a word form, names and abbreviations left out (for word levels). */
    fun lemmasFor(key: String): List<String> {
        val out = LinkedHashSet<String>()
        val (where, args) = trusted(key.lowercase())
        db.rawQuery("SELECT e.lemma FROM lookup l JOIN entry e ON e.id=l.id WHERE $where " +
            "AND e.pos NOT IN ('name','abbrev','symbol','letter','character') LIMIT 60", args).use { c ->
            while (c.moveToNext()) c.getString(0)?.let { out.add(it) }
        }
        return out.toList()
    }

    /** [base] word, its one-word [forms], and the [split] forms of a separable verb as (verb form, particle). */
    data class Forms(val base: String, val forms: Set<String>, val split: Set<Pair<String, String>>)

    /** gehen → geht, ging, gegangen …;  mitbringen → mitbringt, mitgebracht … and (bringt, mit), (brachte, mit) … */
    fun formsOf(raw: String): Forms {
        val w = normalize(raw).lowercase()
        val forms = linkedSetOf(w)
        val split = LinkedHashSet<Pair<String, String>>()
        if (w.isEmpty()) return Forms(w, forms, split)
        val top = runCatching { lookup(raw).firstOrNull { it.pos != "name" } }.getOrNull() ?: return Forms(w, forms, split)
        val base = top.lemma
        val bl = base.lowercase()
        forms.add(bl)
        runCatching {
            val ids = ArrayList<Long>()
            db.rawQuery("SELECT id FROM entry WHERE lemma=? AND pos=?", arrayOf(base, top.pos)).use { c -> while (c.moveToNext()) ids.add(c.getLong(0)) }
            if (ids.isEmpty()) return@runCatching
            val keys = LinkedHashSet<String>()
            db.rawQuery("SELECT DISTINCT key FROM lookup WHERE id IN (${ids.joinToString(",")})", emptyArray()).use { c ->
                while (c.moveToNext()) c.getString(0)?.lowercase()?.let { if (it.isNotEmpty()) keys.add(it) }
            }
            val (f, s) = pickForms(bl, w, keys) { links(it) }
            forms.addAll(f); split.addAll(s)
        }
        return Forms(base, forms, split)
    }

    private fun query(key: String): List<Entry> {
        val out = ArrayList<Entry>()
        val (where, args) = trusted(key)
        db.rawQuery(
            "SELECT e.lemma,e.pos,e.gender,e.ipa,e.hyph,e.audio,e.data FROM lookup l " +
                "JOIN entry e ON e.id=l.id WHERE $where LIMIT 60", args
        ).use { c ->
            while (c.moveToNext()) {
                val d = JSONObject(c.getString(6))
                out.add(
                    Entry(
                        lemma = c.getString(0),
                        pos = c.getString(1),
                        posDe = d.optString("posDe"),
                        article = c.getString(2) ?: "",
                        ipa = c.getString(3) ?: "",
                        hyphenation = c.getString(4) ?: "",
                        audioUrl = c.getString(5) ?: "",
                        senses = d.optJSONArray("senses").objects().map {
                            Sense(it.optString("de"), it.optJSONArray("ex").strings())
                        },
                        english = d.optJSONArray("enGloss").strings().ifEmpty { d.optJSONArray("en").strings() },
                        persian = d.optJSONArray("fa").strings(),
                        persianViaEnglish = d.optJSONArray("faVia").strings(),
                        synonyms = d.optJSONArray("syn").strings(),
                        german = d.optJSONArray("deTr").strings(),
                        lang = d.optString("lang", "de")
                    )
                )
            }
        }
        return out
    }

    /**
     * Most useful entry first: exact spelling, has English/Persian (common words do),
     * nouns for capitalised words; names last.
     */
    private fun rank(list: List<Entry>, word: String): List<Entry> {
        val capital = word.firstOrNull()?.isUpperCase() == true
        fun score(e: Entry): Int {
            var s = 0
            if (e.lemma == word) s += 3 else if (e.lemma.equals(word, ignoreCase = true)) s += 2
            if (e.english.isNotEmpty()) s += 2
            if (e.persian.isNotEmpty()) s += 2 else if (e.persianViaEnglish.isNotEmpty()) s += 1
            if (e.german.isNotEmpty()) s += 1
            if (capital == (e.pos == "noun")) s += 1
            if (e.pos == "name") s -= 6
            return s
        }
        return list.distinctBy { it.lemma + "|" + it.pos }
            .sortedWith(compareByDescending<Entry> { score(it) }.thenByDescending { it.senses.size })
            .take(3)
    }

    companion object {
        const val POPULAR = 25                  // a word card looks at up to this many entries of a key before filtering
        const val SHARED = 5                    // a real word form belongs to at most this many base words
        val KEEP = listOf("sein" to "gewesen", "werden" to "worden")
        val NOT_A_FORM = listOf("verb", "adj", "suffix", "num")

        /** Which of an entry's lookup [keys] are real forms of the base word [bl] ([links] = how many entries share a key). */
        fun pickForms(bl: String, w: String, keys: Set<String>, links: (String) -> Int): Pair<Set<String>, Set<Pair<String, String>>> {
            val forms = LinkedHashSet<String>(); val split = LinkedHashSet<Pair<String, String>>()
            val particles = keys.filter { it.count { ch -> ch == ' ' } == 1 }.map { it.substringAfter(' ') }.toSet()
            for (k in keys) {
                if (' ' in k) {
                    val a = k.substringBefore(' '); val b = k.substringAfter(' ')
                    if (' ' !in b && bl.startsWith(b) && a.length >= 2 && a.all { it.isLetter() }) split.add(a to b)   // "bringt mit" of mitbringen
                    continue
                }
                if (k == bl || k == w) continue
                if (k.length < 2 || k.none { it.isLetter() } || !k.all { it.isLetter() || it in "-'’" }) continue      // "…", "%ig", single letters
                if (k in particles && bl.startsWith(k)) continue                                                         // the particle alone is not a form
                if (links(k) > SHARED && (bl to k) !in KEEP) continue                                                    // helper verbs, pronouns, other verbs' base words
                forms.add(k)
            }
            return forms to split
        }

        private val EDGE = Regex("""^[\p{Punct}„“”‚‘’«»–—…\s]+|[\p{Punct}„“”‚‘’«»–—…\s]+$""")

        fun normalize(raw: String): String {
            var w = raw.trim()
            val keepApos = w.endsWith("'s") || w.endsWith("’s")
            w = w.replace(EDGE, "")
            if (keepApos && !w.endsWith("s")) w += "'s"
            return w
        }

        private fun JSONArray?.strings(): List<String> =
            if (this == null) emptyList() else (0 until length()).map { getString(it) }.filter { it.isNotBlank() }

        private fun JSONArray?.objects(): List<JSONObject> =
            if (this == null) emptyList() else (0 until length()).map { getJSONObject(it) }
    }
}
