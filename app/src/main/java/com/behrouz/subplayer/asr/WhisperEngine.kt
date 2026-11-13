package com.behrouz.subplayer.asr

import android.content.Context
import android.net.Uri
import android.os.Build
import com.behrouz.subplayer.subs.Cue
import com.behrouz.subplayer.subs.CueBuilder
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException

/** Native functions implemented in app/src/main/cpp/whisper_jni.cpp */
object WhisperNative {
    external fun open(modelPath: String, vadPath: String?): Long
    external fun close(handle: Long)
    external fun progress(handle: Long): Int
    external fun cancel(handle: Long)
    external fun transcribe(handle: Long, pcm: FloatArray, lang: String, threads: Int, prompt: String?): Array<String>?
}

/** Accurate offline recogniser (OpenAI Whisper via whisper.cpp). Punctuation + capitalisation. */
object WhisperEngine {

    private const val RATE = 16_000
    private const val CHUNK = RATE * 240          // transcribe in ~4-minute pieces
    private const val SEARCH = RATE * 3           // look for a quiet point in the last 3 s

    @Volatile private var loaded = false

    /** The native library is built for ARMv8.2 (fp16 + dot product) phones. */
    fun cpuSupported(): Boolean {
        if (Build.SUPPORTED_ABIS.firstOrNull() != "arm64-v8a") return false
        return try {
            val info = File("/proc/cpuinfo").readText()
            info.contains("asimddp") && (info.contains("asimdhp") || info.contains("fphp"))
        } catch (_: Exception) {
            false
        }
    }

    private fun load() {
        if (!loaded) {
            System.loadLibrary("whisper_jni")
            loaded = true
        }
    }

    suspend fun transcribe(
        ctx: Context,
        uri: Uri,
        model: File,
        vad: File?,
        lang: String,
        onProgress: (Int) -> Unit
    ): List<Cue> = withContext(Dispatchers.Default) {
        load()
        val handle = WhisperNative.open(model.absolutePath, vad?.absolutePath)
        if (handle == 0L) throw IOException("Could not load the Whisper model (file damaged?)")
        val threads = Runtime.getRuntime().availableProcessors().coerceIn(2, 4)
        val segments = ArrayList<Cue>()
        try {
            coroutineScope {
                var totalSamples = 0L
                var chunkStart = 0L           // absolute index (samples) of buf[0]
                var chunkLen = 0              // samples in the piece now being transcribed
                var finished = false
                val buf = FloatArray(CHUNK)
                var n = 0

                // Poll native progress; cancel native work if this coroutine is cancelled.
                val poller = launch {
                    try {
                        while (true) {
                            delay(400)
                            if (totalSamples > 0 && chunkLen > 0) {
                                val p = WhisperNative.progress(handle).coerceIn(0, 100)
                                val done = chunkStart + chunkLen * p / 100
                                onProgress((done * 100 / totalSamples).toInt().coerceIn(0, 99))
                            }
                        }
                    } finally {
                        if (!finished) WhisperNative.cancel(handle)
                    }
                }

                fun runPiece(len: Int) {
                    chunkLen = len
                    val piece = if (len == buf.size) buf.copyOf() else buf.copyOf(len)
                    val prompt = if (lang == "de") "Hallo, wie geht's? Gut, danke." else null
                    val res = WhisperNative.transcribe(handle, piece, lang, threads, prompt)
                        ?: throw CancellationException("cancelled")
                    val offsetMs = chunkStart * 1000 / RATE
                    for (line in res) {
                        val p = line.split('\t', limit = 3)
                        if (p.size < 3) continue
                        val s = p[0].toLongOrNull() ?: continue
                        val e = p[1].toLongOrNull() ?: continue
                        segments.add(Cue(offsetMs + s, offsetMs + e, p[2]))
                    }
                    chunkStart += len
                    chunkLen = 0
                }

                AudioDecoder.decode(
                    ctx = ctx, uri = uri, targetRate = RATE,
                    checkCancelled = { ensureActive() },
                    onDuration = { us -> totalSamples = us * RATE / 1_000_000 },
                    onProgress = { }
                ) { samples ->
                    var i = 0
                    while (i < samples.size) {
                        val take = minOf(samples.size - i, buf.size - n)
                        for (k in 0 until take) buf[n + k] = samples[i + k] / 32768f
                        n += take
                        i += take
                        if (n == buf.size) {
                            val cut = quietPoint(buf, n)
                            runPiece(cut)
                            // move the remainder to the front
                            System.arraycopy(buf, cut, buf, 0, n - cut)
                            n -= cut
                            ensureActive()
                        }
                    }
                }
                if (n > RATE / 4) runPiece(n)
                finished = true
                poller.cancel()
            }
        } finally {
            WhisperNative.close(handle)
        }
        onProgress(100)
        CueBuilder.fromSegments(segments)
    }

    /** Quietest 0.1 s window in the last 3 s, so a word is not cut in half. */
    private fun quietPoint(buf: FloatArray, n: Int): Int {
        val win = RATE / 10
        var best = n
        var bestE = Double.MAX_VALUE
        var i = maxOf(n - SEARCH, n / 2)
        while (i + win <= n) {
            var e = 0.0
            for (k in i until i + win) e += buf[k] * buf[k]
            if (e < bestE) { bestE = e; best = i + win / 2 }
            i += win / 2
        }
        return best
    }
}
