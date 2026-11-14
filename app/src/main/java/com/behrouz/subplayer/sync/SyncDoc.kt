package com.behrouz.subplayer.sync

import org.json.JSONArray
import org.json.JSONObject

/**
 * The document both apps (Android, Windows) keep in a private GitHub gist as "subplayer-sync.json".
 * Merge rules (same in windows/subplayer/sync.py):
 *  - every word / sentence has a uid and an "updated" time; the newer copy wins
 *  - a deletion is a tombstone (uid → time); it wins over copies that are not newer; tombstones expire after 120 days
 *  - subtitles are keyed by video file name (+ language); the newer file wins
 *  - streak/progress: the device that practised on the later day wins; same day → the larger numbers
 */
data class SWord(
    val uid: String, val text: String, val lemma: String, val article: String, val ipa: String,
    val english: String, val persian: String, val sentence: String, val videoName: String,
    val startMs: Long, val endMs: Long, val created: Long, val reviews: Int, val correct: Int,
    val box: Int, val due: Long, val lastReview: Long, val lang: String, val updated: Long
)

data class SExample(val uid: String, val wordUid: String, val de: String, val en: String, val fa: String, val created: Long, val updated: Long)

data class SSub(val key: String, val lang: String, val srt: String, val updated: Long)

data class SyncDoc(
    val words: Map<String, SWord> = emptyMap(),
    val examples: Map<String, SExample> = emptyMap(),
    val deleted: Map<String, Long> = emptyMap(),
    val subs: Map<String, SSub> = emptyMap(),          // map key = "<video key>|<lang>"
    val streak: Int = 0, val lastDay: Long = -10, val today: Int = 0
)

object SyncMerge {
    const val VERSION = 1
    private const val TOMBSTONE_DAYS = 120L

    fun merge(a: SyncDoc, b: SyncDoc, now: Long = System.currentTimeMillis()): SyncDoc {
        val deleted = HashMap<String, Long>()
        for ((k, v) in a.deleted + emptyMap()) deleted[k] = maxOf(v, deleted[k] ?: 0)
        for ((k, v) in b.deleted) deleted[k] = maxOf(v, deleted[k] ?: 0)
        deleted.entries.removeIf { now - it.value > TOMBSTONE_DAYS * 86_400_000L }

        val words = HashMap<String, SWord>()
        for (uid in a.words.keys + b.words.keys) {
            val w = listOfNotNull(a.words[uid], b.words[uid]).maxByOrNull { it.updated } ?: continue
            if ((deleted[uid] ?: -1) >= w.updated) continue
            words[uid] = w
        }
        val examples = HashMap<String, SExample>()
        for (uid in a.examples.keys + b.examples.keys) {
            val e = listOfNotNull(a.examples[uid], b.examples[uid]).maxByOrNull { it.updated } ?: continue
            if ((deleted[uid] ?: -1) >= e.updated) continue
            if (e.wordUid !in words) continue
            examples[uid] = e
        }
        val subs = HashMap<String, SSub>()
        for (k in a.subs.keys + b.subs.keys) {
            subs[k] = listOfNotNull(a.subs[k], b.subs[k]).maxByOrNull { it.updated }!!
        }
        val (streak, lastDay, today) = when {
            a.lastDay > b.lastDay -> Triple(a.streak, a.lastDay, a.today)
            b.lastDay > a.lastDay -> Triple(b.streak, b.lastDay, b.today)
            else -> Triple(maxOf(a.streak, b.streak), a.lastDay, maxOf(a.today, b.today))
        }
        return SyncDoc(words, examples, deleted, subs, streak, lastDay, today)
    }

    fun toJson(d: SyncDoc): String {
        val o = JSONObject()
        o.put("app", "SubPlayer"); o.put("version", VERSION)
        o.put("words", JSONArray().apply {
            d.words.values.sortedBy { it.created }.forEach { w ->
                put(JSONObject().apply {
                    put("uid", w.uid); put("text", w.text); put("lemma", w.lemma); put("article", w.article); put("ipa", w.ipa)
                    put("english", w.english); put("persian", w.persian); put("sentence", w.sentence); put("video_name", w.videoName)
                    put("start_ms", w.startMs); put("end_ms", w.endMs); put("created", w.created); put("reviews", w.reviews)
                    put("correct", w.correct); put("box", w.box); put("due", w.due); put("last_review", w.lastReview)
                    put("lang", w.lang); put("updated", w.updated)
                })
            }
        })
        o.put("examples", JSONArray().apply {
            d.examples.values.sortedBy { it.created }.forEach { e ->
                put(JSONObject().apply {
                    put("uid", e.uid); put("word_uid", e.wordUid); put("de", e.de); put("en", e.en); put("fa", e.fa)
                    put("created", e.created); put("updated", e.updated)
                })
            }
        })
        o.put("deleted", JSONObject().apply { d.deleted.forEach { (k, v) -> put(k, v) } })
        o.put("subtitles", JSONArray().apply {
            d.subs.values.forEach { s -> put(JSONObject().apply { put("key", s.key); put("lang", s.lang); put("srt", s.srt); put("updated", s.updated) }) }
        })
        o.put("progress", JSONObject().apply { put("streak", d.streak); put("last_day", d.lastDay); put("today", d.today) })
        return o.toString()
    }

    fun fromJson(text: String): SyncDoc {
        if (text.isBlank()) return SyncDoc()
        val o = JSONObject(text)
        val words = HashMap<String, SWord>()
        o.optJSONArray("words")?.let { arr ->
            for (i in 0 until arr.length()) {
                val w = arr.getJSONObject(i)
                val uid = w.optString("uid"); if (uid.isEmpty()) continue
                words[uid] = SWord(uid, w.optString("text"), w.optString("lemma"), w.optString("article"), w.optString("ipa"),
                    w.optString("english"), w.optString("persian"), w.optString("sentence"), w.optString("video_name"),
                    w.optLong("start_ms"), w.optLong("end_ms"), w.optLong("created"), w.optInt("reviews"), w.optInt("correct"),
                    w.optInt("box"), w.optLong("due"), w.optLong("last_review"), w.optString("lang", "de"), w.optLong("updated"))
            }
        }
        val examples = HashMap<String, SExample>()
        o.optJSONArray("examples")?.let { arr ->
            for (i in 0 until arr.length()) {
                val e = arr.getJSONObject(i)
                val uid = e.optString("uid"); if (uid.isEmpty()) continue
                examples[uid] = SExample(uid, e.optString("word_uid"), e.optString("de"), e.optString("en"), e.optString("fa"),
                    e.optLong("created"), e.optLong("updated"))
            }
        }
        val deleted = HashMap<String, Long>()
        o.optJSONObject("deleted")?.let { d -> d.keys().forEach { k -> deleted[k] = d.optLong(k) } }
        val subs = HashMap<String, SSub>()
        o.optJSONArray("subtitles")?.let { arr ->
            for (i in 0 until arr.length()) {
                val s = arr.getJSONObject(i)
                val sub = SSub(s.optString("key"), s.optString("lang", "de"), s.optString("srt"), s.optLong("updated"))
                subs[sub.key + "|" + sub.lang] = sub
            }
        }
        val p = o.optJSONObject("progress")
        return SyncDoc(words, examples, deleted, subs, p?.optInt("streak") ?: 0, p?.optLong("last_day", -10) ?: -10, p?.optInt("today") ?: 0)
    }
}
