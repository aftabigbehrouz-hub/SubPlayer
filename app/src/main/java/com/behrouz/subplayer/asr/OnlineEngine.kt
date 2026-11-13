package com.behrouz.subplayer.asr

import android.content.Context
import android.net.Uri
import com.behrouz.subplayer.subs.Cue
import com.behrouz.subplayer.subs.CueBuilder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/**
 * Online transcription with Whisper large-v3 (Groq) or whisper-1 (OpenAI), using the user's own API key.
 * The audio is decoded on the phone to 16 kHz mono and uploaded as WAV pieces of at most 10 minutes
 * (~19 MB, under the 25 MB free-tier limit), each cut at a quiet moment.
 */
object OnlineEngine {

    enum class Provider(val title: String, val url: String, val model: String, val keyPage: String) {
        GROQ("Groq · Whisper large-v3", "https://api.groq.com/openai/v1/audio/transcriptions", "whisper-large-v3",
            "https://console.groq.com/keys"),
        OPENAI("OpenAI · Whisper", "https://api.openai.com/v1/audio/transcriptions", "whisper-1",
            "https://platform.openai.com/api-keys")
    }

    private const val RATE = 16_000
    private const val PIECE = RATE * 600          // 10 minutes
    private const val SEARCH = RATE * 4

    suspend fun transcribe(
        ctx: Context, uri: Uri, provider: Provider, apiKey: String, lang: String,
        onProgress: (Int, String) -> Unit
    ): List<Cue> = withContext(Dispatchers.IO) {
        if (apiKey.isBlank()) throw IOException("No API key — add it in Settings › Online transcription")
        val cues = ArrayList<Cue>()
        var total = 0L
        var start = 0L                      // absolute sample index of buf[0]
        val buf = ShortArray(PIECE)
        var n = 0
        var pieces = 0

        fun send(len: Int) {
            pieces++
            val done = (start * 100 / maxOf(total, 1)).toInt()
            onProgress(done, "Uploading part $pieces to ${provider.title.substringBefore(" ·")}…")
            val wav = wav(buf, len)
            val segs = upload(provider, apiKey, lang, wav)
            val offset = start * 1000 / RATE
            for (s in segs) cues.add(Cue(offset + s.startMs, offset + s.endMs, s.text))
            start += len
        }

        AudioDecoder.decode(
            ctx, uri, RATE,
            checkCancelled = { ensureActive() },
            onDuration = { us -> total = us * RATE / 1_000_000 },
            onProgress = { }
        ) { samples ->
            var i = 0
            while (i < samples.size) {
                val take = minOf(samples.size - i, buf.size - n)
                System.arraycopy(samples, i, buf, n, take)
                n += take; i += take
                if (n == buf.size) {
                    val cut = quietPoint(buf, n)
                    send(cut)
                    System.arraycopy(buf, cut, buf, 0, n - cut)
                    n -= cut
                    ensureActive()
                }
            }
            if (total > 0) onProgress(((start + n) * 100 / total).toInt().coerceIn(0, 99), "Reading the audio…")
        }
        if (n > RATE / 2) send(n)
        onProgress(100, "Done")
        CueBuilder.splitLong(CueBuilder.fromSegments(cues))
    }

    private fun quietPoint(buf: ShortArray, n: Int): Int {
        val win = RATE / 10
        var best = n; var bestE = Long.MAX_VALUE
        var i = maxOf(n - SEARCH, n / 2)
        while (i + win <= n) {
            var e = 0L
            for (k in i until i + win) e += buf[k].toLong() * buf[k]
            if (e < bestE) { bestE = e; best = i + win / 2 }
            i += win / 2
        }
        return best
    }

    /** 16-bit mono PCM WAV. */
    fun wav(samples: ShortArray, len: Int): ByteArray {
        val data = len * 2
        val out = ByteArrayOutputStream(44 + data)
        fun le32(v: Int) { out.write(v and 0xFF); out.write((v shr 8) and 0xFF); out.write((v shr 16) and 0xFF); out.write((v shr 24) and 0xFF) }
        fun le16(v: Int) { out.write(v and 0xFF); out.write((v shr 8) and 0xFF) }
        out.write("RIFF".toByteArray()); le32(36 + data); out.write("WAVE".toByteArray())
        out.write("fmt ".toByteArray()); le32(16); le16(1); le16(1); le32(RATE); le32(RATE * 2); le16(2); le16(16)
        out.write("data".toByteArray()); le32(data)
        val b = ByteArray(data)
        for (k in 0 until len) { val v = samples[k].toInt(); b[2 * k] = (v and 0xFF).toByte(); b[2 * k + 1] = ((v shr 8) and 0xFF).toByte() }
        out.write(b)
        return out.toByteArray()
    }

    private data class Seg(val startMs: Long, val endMs: Long, val text: String)

    private fun upload(p: Provider, key: String, lang: String, wav: ByteArray): List<Seg> {
        val boundary = "----SubPlayer" + System.nanoTime()
        val conn = (URL(p.url).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"; doOutput = true
            connectTimeout = 30_000; readTimeout = 300_000
            setRequestProperty("Authorization", "Bearer ${key.trim()}")
            setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
            setChunkedStreamingMode(64 * 1024)
        }
        try {
            DataOutputStream(conn.outputStream).use { o ->
                fun field(name: String, value: String) {
                    o.writeBytes("--$boundary\r\nContent-Disposition: form-data; name=\"$name\"\r\n\r\n")
                    o.write(value.toByteArray(Charsets.UTF_8)); o.writeBytes("\r\n")
                }
                field("model", p.model)
                field("language", lang)
                field("response_format", "verbose_json")
                field("temperature", "0")
                o.writeBytes("--$boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\nContent-Type: audio/wav\r\n\r\n")
                o.write(wav)
                o.writeBytes("\r\n--$boundary--\r\n")
            }
            val code = conn.responseCode
            val body = (if (code in 200..299) conn.inputStream else conn.errorStream)?.bufferedReader()?.use { it.readText() } ?: ""
            if (code !in 200..299) {
                val msg = runCatching { JSONObject(body).getJSONObject("error").optString("message") }.getOrNull()
                throw IOException(when (code) {
                    401 -> "API key not accepted (${p.title})"
                    403 -> "Access refused by ${p.title} — from some countries a VPN is needed"
                    413 -> "Audio part too large for your plan"
                    429 -> "Rate limit reached — wait a minute and try again"
                    else -> "HTTP $code"
                } + (msg?.let { ": $it" } ?: ""))
            }
            val json = JSONObject(body)
            val arr = json.optJSONArray("segments") ?: return listOf(Seg(0, 1000, json.optString("text")))
            return (0 until arr.length()).map { i ->
                val s = arr.getJSONObject(i)
                Seg((s.getDouble("start") * 1000).toLong(), (s.getDouble("end") * 1000).toLong(), s.optString("text").trim())
            }
        } finally {
            conn.disconnect()
        }
    }
}
