package com.behrouz.subplayer.export

import android.content.ContentValues
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.effect.BitmapOverlay
import androidx.media3.effect.OverlayEffect
import androidx.media3.effect.OverlaySettings
import androidx.media3.effect.TextureOverlay
import androidx.media3.transformer.Composition
import androidx.media3.transformer.EditedMediaItem
import androidx.media3.transformer.Effects
import androidx.media3.transformer.ExportException
import androidx.media3.transformer.ExportResult
import androidx.media3.transformer.ProgressHolder
import androidx.media3.transformer.Transformer
import com.behrouz.subplayer.subs.Cue
import com.behrouz.subplayer.subs.CueBuilder
import com.google.common.collect.ImmutableList
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Saves the A-B part of a video as a new MP4 in Movies/SubPlayer, optionally with the
 * subtitles drawn into the picture (burnt in). Uses Android's Media3 Transformer.
 */
@androidx.annotation.OptIn(UnstableApi::class)
object ClipExporter {

    suspend fun export(
        ctx: Context,
        video: Uri,
        videoName: String,
        startMs: Long,
        endMs: Long,
        cues: List<Cue>,
        burnSubtitles: Boolean,
        onProgress: (Int) -> Unit
    ): String {
        val width = withContext(Dispatchers.IO) { displayWidth(ctx, video) }
        val tmp = File(ctx.cacheDir, "clip_${System.currentTimeMillis()}.mp4")

        val item = MediaItem.Builder()
            .setUri(video)
            .setClippingConfiguration(
                MediaItem.ClippingConfiguration.Builder()
                    .setStartPositionMs(startMs)
                    .setEndPositionMs(endMs)
                    .build()
            ).build()

        val videoEffects = if (burnSubtitles && cues.isNotEmpty()) {
            val overlay: TextureOverlay = SubtitleOverlay(cues, startMs, endMs, width)
            listOf(OverlayEffect(ImmutableList.of(overlay)))
        } else emptyList()

        val edited = EditedMediaItem.Builder(item)
            .setEffects(Effects(emptyList(), videoEffects))
            .build()

        withContext(Dispatchers.Main) { runTransformer(ctx, edited, tmp, onProgress) }

        val name = buildName(videoName, startMs, endMs)
        return withContext(Dispatchers.IO) {
            try { saveToMovies(ctx, tmp, name) } finally { tmp.delete() }
        }
    }

    private suspend fun runTransformer(ctx: Context, edited: EditedMediaItem, out: File, onProgress: (Int) -> Unit) =
        suspendCancellableCoroutine { cont ->
            val handler = Handler(Looper.getMainLooper())
            val holder = ProgressHolder()
            lateinit var transformer: Transformer
            val poll = object : Runnable {
                override fun run() {
                    if (transformer.getProgress(holder) == Transformer.PROGRESS_STATE_AVAILABLE) onProgress(holder.progress)
                    handler.postDelayed(this, 300)
                }
            }
            transformer = Transformer.Builder(ctx)
                .setVideoMimeType(MimeTypes.VIDEO_H264)
                .setAudioMimeType(MimeTypes.AUDIO_AAC)
                .addListener(object : Transformer.Listener {
                    override fun onCompleted(composition: Composition, exportResult: ExportResult) {
                        handler.removeCallbacks(poll)
                        if (cont.isActive) cont.resume(Unit)
                    }

                    override fun onError(composition: Composition, exportResult: ExportResult, exportException: ExportException) {
                        handler.removeCallbacks(poll)
                        if (cont.isActive) cont.resumeWithException(IOException("Export failed: ${exportException.message}", exportException))
                    }
                })
                .build()
            cont.invokeOnCancellation {
                handler.post {
                    handler.removeCallbacks(poll)
                    transformer.cancel()
                    out.delete()
                }
            }
            transformer.start(edited, out.absolutePath)
            handler.post(poll)
        }

    private fun buildName(videoName: String, a: Long, b: Long): String {
        fun t(ms: Long) = "%02d-%02d".format(ms / 60000, (ms / 1000) % 60)
        val base = videoName.substringBeforeLast('.').replace(Regex("[^\\p{L}\\p{N}_-]+"), "_").take(40)
        return "${base}_${t(a)}_to_${t(b)}.mp4"
    }

    private fun saveToMovies(ctx: Context, file: File, name: String): String {
        if (Build.VERSION.SDK_INT >= 29) {
            val values = ContentValues().apply {
                put(MediaStore.Video.Media.DISPLAY_NAME, name)
                put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
                put(MediaStore.Video.Media.RELATIVE_PATH, Environment.DIRECTORY_MOVIES + "/SubPlayer")
                put(MediaStore.Video.Media.IS_PENDING, 1)
            }
            val r = ctx.contentResolver
            val uri = r.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, values)
                ?: throw IOException("Could not create the video file")
            r.openOutputStream(uri)?.use { out -> file.inputStream().use { it.copyTo(out) } }
                ?: throw IOException("Could not write the video file")
            values.clear()
            values.put(MediaStore.Video.Media.IS_PENDING, 0)
            r.update(uri, values, null, null)
            return "Movies/SubPlayer/$name"
        } else {
            // Android 7-9: app-specific Movies folder (no storage permission needed)
            val dir = File(ctx.getExternalFilesDir(Environment.DIRECTORY_MOVIES), "SubPlayer").apply { mkdirs() }
            val dest = File(dir, name)
            file.copyTo(dest, overwrite = true)
            return dest.absolutePath
        }
    }

    /** Width of the picture as displayed (rotation taken into account). */
    private fun displayWidth(ctx: Context, uri: Uri): Int {
        val r = MediaMetadataRetriever()
        return try {
            r.setDataSource(ctx, uri)
            val w = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)?.toIntOrNull() ?: 1280
            val h = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)?.toIntOrNull() ?: 720
            val rot = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_ROTATION)?.toIntOrNull() ?: 0
            if (rot == 90 || rot == 270) h else w
        } catch (_: Exception) {
            1280
        } finally {
            r.release()
        }
    }

    /** Draws the subtitle showing at each frame into a bitmap placed near the bottom. */
    private class SubtitleOverlay(
        cues: List<Cue>,
        private val clipStartMs: Long,
        clipEndMs: Long,
        private val frameWidth: Int
    ) : BitmapOverlay() {

        private val cues = cues.filter { it.endMs > clipStartMs && it.startMs < clipEndMs }
        private val empty = Bitmap.createBitmap(2, 2, Bitmap.Config.ARGB_8888)
        private var cachedIndex = -2
        private var cached: Bitmap = empty
        private var offsetMs: Long? = null
        private val settings = OverlaySettings.Builder()
            .setBackgroundFrameAnchor(0f, -0.9f)   // near the bottom edge
            .setOverlayFrameAnchor(0f, -1f)        // bottom-centre of the subtitle box
            .build()

        override fun getOverlaySettings(presentationTimeUs: Long): OverlaySettings = settings

        override fun getBitmap(presentationTimeUs: Long): Bitmap {
            val ptsMs = presentationTimeUs / 1000
            // Frames arrive either relative to the clip start or in original time: detect once.
            val off = offsetMs ?: (if (ptsMs + 1000 < clipStartMs) clipStartMs else 0L).also { offsetMs = it }
            val t = ptsMs + off
            val idx = CueBuilder.indexAt(cues, t)
            if (idx != cachedIndex) {
                cachedIndex = idx
                cached = if (idx < 0) empty else render(cues[idx].text)
            }
            return cached
        }

        private fun render(text: String): Bitmap {
            val textSize = (frameWidth / 26f).coerceAtLeast(18f)
            val paint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
                color = Color.WHITE
                this.textSize = textSize
                typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD)
            }
            val maxW = (frameWidth * 0.9f).toInt()
            val layout = StaticLayout.Builder.obtain(text, 0, text.length, paint, maxW)
                .setAlignment(Layout.Alignment.ALIGN_CENTER)
                .build()
            var lineW = 0f
            for (i in 0 until layout.lineCount) lineW = maxOf(lineW, layout.getLineWidth(i))
            val pad = textSize * 0.4f
            val bw = (lineW + pad * 2).toInt().coerceAtLeast(4)
            val bh = (layout.height + pad * 2).toInt().coerceAtLeast(4)
            val bmp = Bitmap.createBitmap(bw, bh, Bitmap.Config.ARGB_8888)
            val c = Canvas(bmp)
            val bg = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.argb(170, 0, 0, 0) }
            c.drawRoundRect(RectF(0f, 0f, bw.toFloat(), bh.toFloat()), pad, pad, bg)
            c.save()
            c.translate(pad - (maxW - lineW) / 2f, pad)
            layout.draw(c)
            c.restore()
            return bmp
        }
    }
}
