package com.behrouz.subplayer

import android.content.Context
import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.PI
import kotlin.math.exp
import kotlin.math.floor
import kotlin.math.roundToInt

/**
 * Decodes the audio track of a video with Android's built-in MediaCodec and
 * streams it out as 16-bit little-endian mono PCM at [targetRate] Hz
 * (Vosk needs 16 000 Hz mono). Nothing is written to disk.
 */
object AudioDecoder {

    fun decode(
        ctx: Context,
        uri: Uri,
        targetRate: Int,
        checkCancelled: () -> Unit,
        onProgress: (Int) -> Unit,
        sink: (ByteArray, Int) -> Unit
    ) {
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        try {
            extractor.setDataSource(ctx, uri, null)

            var track = -1
            var format: MediaFormat? = null
            for (i in 0 until extractor.trackCount) {
                val f = extractor.getTrackFormat(i)
                val mime = f.getString(MediaFormat.KEY_MIME) ?: continue
                if (mime.startsWith("audio/")) { track = i; format = f; break }
            }
            if (track < 0 || format == null) throw IllegalStateException("This video has no audio track.")
            extractor.selectTrack(track)

            val mime = format.getString(MediaFormat.KEY_MIME)!!
            val durationUs = if (format.containsKey(MediaFormat.KEY_DURATION)) format.getLong(MediaFormat.KEY_DURATION) else 0L
            var srcRate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
            var channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT).coerceAtLeast(1)
            var isFloat = false
            var resampler = Resampler(srcRate, targetRate)

            val c = try {
                MediaCodec.createDecoderByType(mime)
            } catch (e: Exception) {
                throw IllegalStateException("This phone cannot decode the audio format ($mime).")
            }
            codec = c
            c.configure(format, null, null, 0)
            c.start()

            val info = MediaCodec.BufferInfo()
            var inputDone = false
            var outputDone = false

            while (!outputDone) {
                checkCancelled()

                if (!inputDone) {
                    val inIdx = c.dequeueInputBuffer(10_000)
                    if (inIdx >= 0) {
                        val buf = c.getInputBuffer(inIdx)!!
                        val size = extractor.readSampleData(buf, 0)
                        if (size < 0) {
                            c.queueInputBuffer(inIdx, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            c.queueInputBuffer(inIdx, 0, size, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                    }
                }

                val outIdx = c.dequeueOutputBuffer(info, 10_000)
                if (outIdx == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    val of = c.outputFormat
                    val r = of.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                    if (r != srcRate) { srcRate = r; resampler = Resampler(srcRate, targetRate) }
                    channels = of.getInteger(MediaFormat.KEY_CHANNEL_COUNT).coerceAtLeast(1)
                    isFloat = of.containsKey(MediaFormat.KEY_PCM_ENCODING) &&
                        of.getInteger(MediaFormat.KEY_PCM_ENCODING) == AudioFormat.ENCODING_PCM_FLOAT
                } else if (outIdx >= 0) {
                    if (info.size > 0) {
                        val ob = c.getOutputBuffer(outIdx)!!
                        ob.position(info.offset)
                        ob.limit(info.offset + info.size)
                        val mono = toMono(ob.slice().order(ByteOrder.nativeOrder()), channels, isFloat)
                        val out = resampler.process(mono)
                        if (out.isNotEmpty()) {
                            val bytes = toBytes(out)
                            sink(bytes, bytes.size)
                        }
                        if (durationUs > 0) {
                            onProgress(((info.presentationTimeUs * 100) / durationUs).toInt().coerceIn(0, 99))
                        }
                    }
                    c.releaseOutputBuffer(outIdx, false)
                    if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) outputDone = true
                }
            }
            onProgress(100)
        } finally {
            try { codec?.stop() } catch (_: Exception) { }
            try { codec?.release() } catch (_: Exception) { }
            extractor.release()
        }
    }

    /** Averages all channels into one. Handles 16-bit and float PCM output. */
    private fun toMono(buf: ByteBuffer, ch: Int, isFloat: Boolean): ShortArray {
        return if (isFloat) {
            val fb = buf.asFloatBuffer()
            val frames = fb.remaining() / ch
            ShortArray(frames) { i ->
                var s = 0f
                for (c in 0 until ch) s += fb.get(i * ch + c)
                (s / ch * 32767f).coerceIn(-32768f, 32767f).toInt().toShort()
            }
        } else {
            val sb = buf.asShortBuffer()
            val frames = sb.remaining() / ch
            ShortArray(frames) { i ->
                var s = 0
                for (c in 0 until ch) s += sb.get(i * ch + c)
                (s / ch).toShort()
            }
        }
    }

    private fun toBytes(s: ShortArray): ByteArray {
        val b = ByteArray(s.size * 2)
        for (i in s.indices) {
            val v = s[i].toInt()
            b[2 * i] = (v and 0xFF).toByte()
            b[2 * i + 1] = ((v shr 8) and 0xFF).toByte()
        }
        return b
    }

    /**
     * Streaming sample-rate converter: 2-pole low-pass (anti-alias) followed by
     * linear interpolation. Keeps state between buffers so there are no clicks.
     */
    class Resampler(src: Int, dst: Int) {
        private val step = src.toDouble() / dst
        private val alpha: Double =
            if (src > dst) 1.0 - exp(-2.0 * PI * (0.45 * dst) / src) else 1.0
        private var lp1 = 0.0
        private var lp2 = 0.0
        private var t = 0.0      // read position relative to current buffer (may be in [-1,0))
        private var prev = 0.0   // last filtered sample of previous buffer

        fun process(input: ShortArray): ShortArray {
            val n = input.size
            if (n == 0) return ShortArray(0)

            val x = DoubleArray(n)
            for (i in 0 until n) {
                lp1 += alpha * (input[i] - lp1)
                lp2 += alpha * (lp1 - lp2)
                x[i] = lp2
            }

            val out = ShortArray(((n + 1 - t) / step).toInt() + 2)
            var count = 0
            while (t < n - 1 && count < out.size) {
                val idx = floor(t).toInt()
                val frac = t - idx
                val a = if (idx < 0) prev else x[idx]
                val b = x[idx + 1]
                out[count++] = (a + (b - a) * frac).roundToInt().coerceIn(-32768, 32767).toShort()
                t += step
            }
            t -= n
            prev = x[n - 1]
            return out.copyOf(count)
        }
    }
}
