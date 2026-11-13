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
    val sentence: String,           // the subtitle line
    val videoUri: String,
    val videoName: String,
    val startMs: Long,
    val endMs: Long,
    val created: Long,
    val reviews: Int = 0,           // how many times reviewed
    val correct: Int = 0,           // how many of those were "Got it"
    val box: Int = 0,               // Leitner box 0..7
    val due: Long,                  // next review time
    val lastReview: Long = 0
)

/**
 * Spaced repetition (Leitner boxes). "Got it" moves a word up one box, so it comes back
 * after a longer gap: 1, 2, 4, 7, 15, 30, 60 days. "Again" sends it back to box 0
 * (shown again in 10 minutes).
 */
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

class WordStore(ctx: Context) : SQLiteOpenHelper(ctx, "words.db", null, 1) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE words(
                id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, lemma TEXT, article TEXT, ipa TEXT,
                english TEXT, persian TEXT, sentence TEXT, video_uri TEXT, video_name TEXT,
                start_ms INTEGER, end_ms INTEGER, created INTEGER, reviews INTEGER, correct INTEGER,
                box INTEGER, due INTEGER, last_review INTEGER)"""
        )
        db.execSQL("CREATE INDEX words_due ON words(due)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {}

    fun all(): List<SavedWord> = query("SELECT * FROM words ORDER BY due ASC, id DESC", emptyArray())

    fun dueCount(now: Long): Int =
        readableDatabase.rawQuery("SELECT COUNT(*) FROM words WHERE due <= ?", arrayOf(now.toString())).use {
            if (it.moveToFirst()) it.getInt(0) else 0
        }

    fun due(now: Long): List<SavedWord> =
        query("SELECT * FROM words WHERE due <= ? ORDER BY box ASC, due ASC", arrayOf(now.toString()))

    /** Same text from the same line is saved only once. */
    fun find(text: String, videoUri: String, startMs: Long): SavedWord? =
        query("SELECT * FROM words WHERE lower(text)=lower(?) AND video_uri=? AND start_ms=? LIMIT 1",
            arrayOf(text, videoUri, startMs.toString())).firstOrNull()

    fun insert(w: SavedWord): Long = writableDatabase.insert("words", null, values(w))

    fun update(w: SavedWord) {
        writableDatabase.update("words", values(w), "id=?", arrayOf(w.id.toString()))
    }

    fun delete(id: Long) {
        writableDatabase.delete("words", "id=?", arrayOf(id.toString()))
    }

    private fun values(w: SavedWord) = ContentValues().apply {
        put("text", w.text); put("lemma", w.lemma); put("article", w.article); put("ipa", w.ipa)
        put("english", w.english); put("persian", w.persian); put("sentence", w.sentence)
        put("video_uri", w.videoUri); put("video_name", w.videoName)
        put("start_ms", w.startMs); put("end_ms", w.endMs); put("created", w.created)
        put("reviews", w.reviews); put("correct", w.correct); put("box", w.box)
        put("due", w.due); put("last_review", w.lastReview)
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
            box = l("box").toInt(), due = l("due"), lastReview = l("last_review")
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
