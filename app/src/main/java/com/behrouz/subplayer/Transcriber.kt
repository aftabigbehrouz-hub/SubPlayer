package com.behrouz.subplayer

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import org.json.JSONObject
import org.vosk.LibVosk
import org.vosk.LogLevel
import org.vosk.Model
import org.vosk.Recognizer
import java.io.File

/** Runs the offline Vosk recogniser over the video's audio and returns timed words. */
object Transcriber {

    data class Word(val start: Double, val end: Double, val text: String)

    private const val RATE = 16_000

    suspend fun transcribe(
        ctx: Context,
        uri: Uri,
        modelDir: File,
        onProgress: (Int) -> Unit
    ): List<Word> = withContext(Dispatchers.Default) {
        LibVosk.setLogLevel(LogLevel.WARNINGS)
        val words = ArrayList<Word>()
        val model = Model(modelDir.absolutePath)
        try {
            val rec = Recognizer(model, RATE.toFloat())
            try {
                rec.setWords(true)
                var lastPct = -1
                AudioDecoder.decode(
                    ctx = ctx,
                    uri = uri,
                    targetRate = RATE,
                    checkCancelled = { ensureActive() },
                    onProgress = { p -> if (p != lastPct) { lastPct = p; onProgress(p) } }
                ) { bytes, len ->
                    if (rec.acceptWaveForm(bytes, len)) parse(rec.result, words)
                }
                parse(rec.finalResult, words)
            } finally {
                rec.close()
            }
        } finally {
            model.close()
        }
        words
    }

    /** Vosk JSON: {"result":[{"conf":1.0,"start":0.81,"end":1.2,"word":"hallo"},...],"text":"..."} */
    private fun parse(json: String, out: MutableList<Word>) {
        val arr = JSONObject(json).optJSONArray("result") ?: return
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            val w = o.optString("word")
            if (w.isNotBlank() && w != "[unk]") {
                out.add(Word(o.getDouble("start"), o.getDouble("end"), w))
            }
        }
    }
}
