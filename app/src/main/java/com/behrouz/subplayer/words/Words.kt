package com.behrouz.subplayer.words

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

/** A saved word or phrase, with the video moment it came from. */
data class SavedWord(
    val id: Long = 0,
    val text: String,               // as selected in the subtitle ("ging", "auf jeden Fall")
    val lemma: String,              // dictionary base form ("gehen"), or the text for phrases
    val article: String = "",
    val ipa: String = "",
    val english: String = "",
    val persian: String = "",
    val sentence: String,           // the complete sentence it came from
    val videoUri: String,
    val videoName: String,
    val startMs: Long,
    val endMs: Long,
    val created: Long,
    val reviews: Int = 0,           // how many times reviewed
    val correct: Int = 0,           // how many of those were "Got it"
    val box: Int = 0,               // Leitner box 0..7
    val due: Long,                  // next review time
    val lastReview: Long = 0,
    val lang: String = "de",        // language of the word (de / en)
    val uid: String = java.util.UUID.randomUUID().toString(),   // same id on every synced device
    val updated: Long = System.currentTimeMillis()
)

object Srs {
    val INTERVAL_DAYS = intArrayOf(0, 1, 2, 4, 7, 15, 30, 60)
    private const val DAY = 24L * 60 * 60 * 1000
    private const val AGAIN_MS = 10L * 60 * 1000

    fun review(w: SavedWord, gotIt: Boolean, now: Long): SavedWord {
        val box = if (gotIt) minOf(w.box + 1, INTERVAL_DAYS.size - 1) else 0
        val due = if (gotIt) now + INTERVAL_DAYS[box] * DAY else now + AGAIN_MS
        return w.copy(
            reviews = w.reviews + 1,
            correct = w.correct + if (gotIt) 1 else 0,
            box = box, due = due, lastReview = now
        )
    }

    /** "today", "in 3 days", … for the list. */
    fun dueLabel(due: Long, now: Long): String {
        val d = due - now
        return when {
            d <= 0 -> "due now"
            d < 60 * 60 * 1000 -> "in ${d / 60000 + 1} min"
            d < DAY -> "in ${d / 3_600_000 + 1} h"
            else -> "in ${(d + DAY / 2) / DAY} days"
        }
    }

    /** 0..1 how well a word is known (for the progress ring). */
    fun strength(w: SavedWord) = w.box / (INTERVAL_DAYS.size - 1f)
}


class WordStore(ctx: Context) : SQLiteOpenHelper(ctx, "words.db", null, 3) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE words(
                id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, lemma TEXT, article TEXT, ipa TEXT,
                english TEXT, persian TEXT, sentence TEXT, video_uri TEXT, video_name TEXT,
                start_ms INTEGER, end_ms INTEGER, created INTEGER, reviews INTEGER, correct INTEGER,
                box INTEGER, due INTEGER, last_review INTEGER, lang TEXT DEFAULT 'de', uid TEXT, updated INTEGER)"""
        )
        db.execSQL("CREATE INDEX words_due ON words(due)")
        createExamples(db)
        db.execSQL("CREATE TABLE IF NOT EXISTS deleted(uid TEXT PRIMARY KEY, at INTEGER)")
    }

    /** v2: extra example sentences per word (pasted from ChatGPT, Grok, DWDS, dict.cc …). */
    private fun createExamples(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE IF NOT EXISTS examples(id INTEGER PRIMARY KEY AUTOINCREMENT, word_id INTEGER, de TEXT, en TEXT, fa TEXT, created INTEGER, uid TEXT, updated INTEGER)")
        db.execSQL("CREATE INDEX IF NOT EXISTS examples_word ON examples(word_id)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) {
            db.execSQL("CREATE TABLE IF NOT EXISTS examples(id INTEGER PRIMARY KEY AUTOINCREMENT, word_id INTEGER, de TEXT, en TEXT, fa TEXT, created INTEGER)")
            db.execSQL("CREATE INDEX IF NOT EXISTS examples_word ON examples(word_id)")
        }
        if (oldVersion < 3) {   // v3: language + sync ids; saved words are kept
            db.execSQL("ALTER TABLE words ADD COLUMN lang TEXT DEFAULT 'de'")
            db.execSQL("ALTER TABLE words ADD COLUMN uid TEXT")
            db.execSQL("ALTER TABLE words ADD COLUMN updated INTEGER")
            db.execSQL("UPDATE words SET lang='de', uid=lower(hex(randomblob(16))), updated=max(created, last_review)")
            db.execSQL("ALTER TABLE examples ADD COLUMN uid TEXT")
            db.execSQL("ALTER TABLE examples ADD COLUMN updated INTEGER")
            db.execSQL("UPDATE examples SET uid=lower(hex(randomblob(16))), updated=created")
            db.execSQL("CREATE TABLE IF NOT EXISTS deleted(uid TEXT PRIMARY KEY, at INTEGER)")
        }
    }

    fun all(): List<SavedWord> = query("SELECT * FROM words ORDER BY due ASC, id DESC", emptyArray())

    fun dueCount(now: Long): Int =
        readableDatabase.rawQuery("SELECT COUNT(*) FROM words WHERE due <= ?", arrayOf(now.toString())).use {
            if (it.moveToFirst()) it.getInt(0) else 0
        }

    fun due(now: Long): List<SavedWord> =
        query("SELECT * FROM words WHERE due <= ? ORDER BY box ASC, due ASC", arrayOf(now.toString()))

    /** Same text from the same moment is saved only once. */
    fun find(text: String, videoUri: String, startMs: Long): SavedWord? =
        query("SELECT * FROM words WHERE lower(text)=lower(?) AND video_uri=? AND start_ms=? LIMIT 1",
            arrayOf(text, videoUri, startMs.toString())).firstOrNull()

    /** Like [find], but also matches a sentence that starts a little earlier (complete-sentence saving). */
    fun findNear(text: String, videoUri: String, startMs: Long): SavedWord? =
        query("SELECT * FROM words WHERE lower(text)=lower(?) AND video_uri=? AND start_ms BETWEEN ? AND ? LIMIT 1",
            arrayOf(text, videoUri, (startMs - 15000).toString(), (startMs + 15000).toString())).firstOrNull()

    fun insert(w: SavedWord): Long = writableDatabase.insert("words", null, values(w.copy(updated = System.currentTimeMillis())))

    fun update(w: SavedWord) {
        writableDatabase.update("words", values(w.copy(updated = System.currentTimeMillis())), "id=?", arrayOf(w.id.toString()))
    }

    fun delete(id: Long) {
        val w = query("SELECT * FROM words WHERE id=?", arrayOf(id.toString())).firstOrNull() ?: return
        val now = System.currentTimeMillis()
        examples(id).forEach { tombstone(it.uid, now) }
        tombstone(w.uid, now)
        writableDatabase.delete("words", "id=?", arrayOf(id.toString()))
        writableDatabase.delete("examples", "word_id=?", arrayOf(id.toString()))
    }

    private fun tombstone(uid: String, at: Long) {
        if (uid.isEmpty()) return
        writableDatabase.insertWithOnConflict("deleted", null, ContentValues().apply { put("uid", uid); put("at", at) },
            SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun tombstones(): Map<String, Long> {
        val out = HashMap<String, Long>()
        readableDatabase.rawQuery("SELECT uid, at FROM deleted", emptyArray()).use { c -> while (c.moveToNext()) out[c.getString(0)] = c.getLong(1) }
        return out
    }

    fun addExamples(wordId: Long, list: List<Example>): Int {
        val existing = examples(wordId).map { it.de.lowercase() }.toMutableSet()
        var n = 0
        val now = System.currentTimeMillis()
        for (e in list) {
            if (e.de.isBlank() || e.de.lowercase() in existing) continue
            writableDatabase.insert("examples", null, ContentValues().apply {
                put("word_id", wordId); put("de", e.de); put("en", e.en); put("fa", e.fa); put("created", now)
                put("uid", java.util.UUID.randomUUID().toString()); put("updated", now)
            })
            existing.add(e.de.lowercase()); n++
        }
        return n
    }

    private fun readExample(c: Cursor) = Example(
        id = c.getLong(c.getColumnIndexOrThrow("id")), wordId = c.getLong(c.getColumnIndexOrThrow("word_id")),
        de = c.getString(c.getColumnIndexOrThrow("de")) ?: "", en = c.getString(c.getColumnIndexOrThrow("en")) ?: "",
        fa = c.getString(c.getColumnIndexOrThrow("fa")) ?: "", created = c.getLong(c.getColumnIndexOrThrow("created")),
        uid = c.getString(c.getColumnIndexOrThrow("uid")) ?: "", updated = c.getLong(c.getColumnIndexOrThrow("updated"))
    )

    fun examples(wordId: Long): List<Example> {
        val out = ArrayList<Example>()
        readableDatabase.rawQuery("SELECT * FROM examples WHERE word_id=? ORDER BY id", arrayOf(wordId.toString())).use { c ->
            while (c.moveToNext()) out.add(readExample(c))
        }
        return out
    }

    fun allExamples(): Map<Long, List<Example>> {
        val out = HashMap<Long, MutableList<Example>>()
        readableDatabase.rawQuery("SELECT * FROM examples ORDER BY id", emptyArray()).use { c ->
            while (c.moveToNext()) { val e = readExample(c); out.getOrPut(e.wordId) { ArrayList() }.add(e) }
        }
        return out
    }

    fun deleteExample(id: Long) {
        readableDatabase.rawQuery("SELECT uid FROM examples WHERE id=?", arrayOf(id.toString())).use { c ->
            if (c.moveToFirst()) tombstone(c.getString(0) ?: "", System.currentTimeMillis())
        }
        writableDatabase.delete("examples", "id=?", arrayOf(id.toString()))
    }

    // ------------------------------------------------------------------ sync

    fun exportSync(): Pair<List<com.behrouz.subplayer.sync.SWord>, List<com.behrouz.subplayer.sync.SExample>> {
        val words = all()
        val byId = words.associateBy { it.id }
        val ws = words.map { w ->
            com.behrouz.subplayer.sync.SWord(w.uid, w.text, w.lemma, w.article, w.ipa, w.english, w.persian, w.sentence, w.videoName,
                w.startMs, w.endMs, w.created, w.reviews, w.correct, w.box, w.due, w.lastReview, w.lang, w.updated)
        }
        val es = allExamples().values.flatten().mapNotNull { e ->
            val wu = byId[e.wordId]?.uid ?: return@mapNotNull null
            com.behrouz.subplayer.sync.SExample(e.uid, wu, e.de, e.en, e.fa, e.created, e.updated)
        }
        return ws to es
    }

    /** Makes the local database equal to the merged document (keeps local video locations). */
    fun applySync(doc: com.behrouz.subplayer.sync.SyncDoc, resolveVideo: (String) -> String) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            val local = all().associateBy { it.uid }
            // words
            for (w in doc.words.values) {
                val cur = local[w.uid]
                if (cur != null && cur.updated >= w.updated) continue
                val v = ContentValues().apply {
                    put("text", w.text); put("lemma", w.lemma); put("article", w.article); put("ipa", w.ipa)
                    put("english", w.english); put("persian", w.persian); put("sentence", w.sentence)
                    put("video_name", w.videoName); put("start_ms", w.startMs); put("end_ms", w.endMs); put("created", w.created)
                    put("reviews", w.reviews); put("correct", w.correct); put("box", w.box); put("due", w.due)
                    put("last_review", w.lastReview); put("lang", w.lang); put("uid", w.uid); put("updated", w.updated)
                }
                if (cur == null) { v.put("video_uri", resolveVideo(w.videoName)); db.insert("words", null, v) }
                else db.update("words", v, "id=?", arrayOf(cur.id.toString()))
            }
            for ((uid, w) in local) if (uid !in doc.words) db.delete("words", "id=?", arrayOf(w.id.toString()))
            // examples
            val idOf = HashMap<String, Long>()
            db.rawQuery("SELECT id, uid FROM words", emptyArray()).use { c -> while (c.moveToNext()) idOf[c.getString(1) ?: ""] = c.getLong(0) }
            val localEx = HashMap<String, Pair<Long, Long>>()
            db.rawQuery("SELECT id, uid, updated FROM examples", emptyArray()).use { c -> while (c.moveToNext()) localEx[c.getString(1) ?: ""] = c.getLong(0) to c.getLong(2) }
            for (e in doc.examples.values) {
                val wid = idOf[e.wordUid] ?: continue
                val cur = localEx[e.uid]
                if (cur != null && cur.second >= e.updated) continue
                val v = ContentValues().apply {
                    put("word_id", wid); put("de", e.de); put("en", e.en); put("fa", e.fa); put("created", e.created)
                    put("uid", e.uid); put("updated", e.updated)
                }
                if (cur == null) db.insert("examples", null, v) else db.update("examples", v, "id=?", arrayOf(cur.first.toString()))
            }
            for ((uid, p) in localEx) if (uid !in doc.examples) db.delete("examples", "id=?", arrayOf(p.first.toString()))
            // tombstones
            db.delete("deleted", null, null)
            for ((uid, at) in doc.deleted) db.insert("deleted", null, ContentValues().apply { put("uid", uid); put("at", at) })
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
    }

    private fun values(w: SavedWord) = ContentValues().apply {
        put("text", w.text); put("lemma", w.lemma); put("article", w.article); put("ipa", w.ipa)
        put("english", w.english); put("persian", w.persian); put("sentence", w.sentence)
        put("video_uri", w.videoUri); put("video_name", w.videoName)
        put("start_ms", w.startMs); put("end_ms", w.endMs); put("created", w.created)
        put("reviews", w.reviews); put("correct", w.correct); put("box", w.box)
        put("due", w.due); put("last_review", w.lastReview); put("lang", w.lang); put("uid", w.uid); put("updated", w.updated)
    }

    private fun query(sql: String, args: Array<String>): List<SavedWord> {
        val out = ArrayList<SavedWord>()
        readableDatabase.rawQuery(sql, args).use { c -> while (c.moveToNext()) out.add(read(c)) }
        return out
    }

    private fun read(c: Cursor): SavedWord {
        fun s(n: String) = c.getString(c.getColumnIndexOrThrow(n)) ?: ""
        fun l(n: String) = c.getLong(c.getColumnIndexOrThrow(n))
        return SavedWord(
            id = l("id"), text = s("text"), lemma = s("lemma"), article = s("article"), ipa = s("ipa"),
            english = s("english"), persian = s("persian"), sentence = s("sentence"),
            videoUri = s("video_uri"), videoName = s("video_name"), startMs = l("start_ms"), endMs = l("end_ms"),
            created = l("created"), reviews = l("reviews").toInt(), correct = l("correct").toInt(),
            box = l("box").toInt(), due = l("due"), lastReview = l("last_review"),
            lang = s("lang").ifEmpty { "de" }, uid = s("uid"), updated = l("updated")
        )
    }
}

/** Recently opened videos, with the position to resume from. */
class Recents(ctx: Context) {
    data class Item(val uri: String, val name: String, val positionMs: Long, val durationMs: Long, val opened: Long)

    private val prefs = ctx.getSharedPreferences("recents", Context.MODE_PRIVATE)

    fun list(): List<Item> {
        val raw = prefs.getString("items", "") ?: ""
        return raw.split('\n').mapNotNull { line ->
            val f = line.split('\t')
            if (f.size == 5) Item(f[0], f[1], f[2].toLongOrNull() ?: 0, f[3].toLongOrNull() ?: 0, f[4].toLongOrNull() ?: 0) else null
        }
    }

    fun get(uri: String) = list().firstOrNull { it.uri == uri }

    fun put(item: Item) {
        val items = (listOf(item) + list().filter { it.uri != item.uri }).take(12)
        prefs.edit().putString("items", items.joinToString("\n") {
            listOf(it.uri, it.name.replace('\t', ' ').replace('\n', ' '), it.positionMs, it.durationMs, it.opened).joinToString("\t")
        }).apply()
    }

    fun remove(uri: String) {
        val items = list().filter { it.uri != uri }
        prefs.edit().putString("items", items.joinToString("\n") {
            listOf(it.uri, it.name, it.positionMs, it.durationMs, it.opened).joinToString("\t")
        }).apply()
    }
}
