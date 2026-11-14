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

    private fun query(key: String): List<Entry> {
        val out = ArrayList<Entry>()
        db.rawQuery(
            "SELECT e.lemma,e.pos,e.gender,e.ipa,e.hyph,e.audio,e.data FROM lookup l " +
                "JOIN entry e ON e.id=l.id WHERE l.key=? LIMIT 40", arrayOf(key)
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
