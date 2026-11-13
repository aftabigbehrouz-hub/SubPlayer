package com.behrouz.subplayer.asr

import android.content.Context
import android.net.Uri
import com.behrouz.subplayer.subs.Cue
import com.behrouz.subplayer.subs.CueBuilder
import com.behrouz.subplayer.subs.TimedWord
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import org.json.JSONObject
import org.vosk.LibVosk
import org.vosk.LogLevel
import org.vosk.Model
import org.vosk.Recognizer
import java.io.File

/** Fast offline recogniser (Vosk / Kaldi). Lower accuracy, no punctuation. */
object VoskEngine {

    private const val RATE = 16_000

    suspend fun transcribe(ctx: Context, uri: Uri, modelDir: File, onProgress: (Int) -> Unit): List<Cue> =
        withContext(Dispatchers.Default) {
            LibVosk.setLogLevel(LogLevel.WARNINGS)
            val words = ArrayList<TimedWord>()
            val model = Model(modelDir.absolutePath)
            try {
                val rec = Recognizer(model, RATE.toFloat())
                try {
                    rec.setWords(true)
                    var last = -1
                    AudioDecoder.decode(
                        ctx = ctx, uri = uri, targetRate = RATE,
                        checkCancelled = { ensureActive() },
                        onDuration = { },
                        onProgress = { p -> if (p != last) { last = p; onProgress(p) } }
                    ) { samples ->
                        val bytes = AudioDecoder.toBytes(samples)
                        if (rec.acceptWaveForm(bytes, bytes.size)) parse(rec.result, words)
                    }
                    parse(rec.finalResult, words)
                } finally {
                    rec.close()
                }
            } finally {
                model.close()
            }
            CueBuilder.fromWords(words)
        }

    private fun parse(json: String, out: MutableList<TimedWord>) {
        val arr = JSONObject(json).optJSONArray("result") ?: return
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            val w = o.optString("word")
            if (w.isNotBlank() && w != "[unk]") out.add(TimedWord(o.getDouble("start"), o.getDouble("end"), w))
        }
    }
}
