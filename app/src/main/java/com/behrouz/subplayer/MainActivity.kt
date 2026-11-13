package com.behrouz.subplayer

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.OpenableColumns
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.media3.ui.SubtitleView
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.util.Locale

@androidx.annotation.OptIn(UnstableApi::class)
class MainActivity : AppCompatActivity() {

    private lateinit var player: ExoPlayer
    private lateinit var playerView: PlayerView
    private lateinit var statusText: TextView
    private lateinit var progress: ProgressBar
    private lateinit var btnOpen: Button
    private lateinit var btnSubs: Button
    private lateinit var btnLoadSrt: Button
    private lateinit var abLabel: TextView

    private var videoUri: Uri? = null
    private var subtitleUri: Uri? = null
    private var subtitleLang = "de"

    // A-B repeat points in milliseconds (-1 = not set)
    private var pointA = -1L
    private var pointB = -1L

    private var job: Job? = null
    private val handler = Handler(Looper.getMainLooper())

    /** Checks 25x per second: when playback reaches B, jump back to A (like VLC). */
    private val abLoop = object : Runnable {
        override fun run() {
            if (pointA >= 0 && pointB > pointA && player.currentPosition >= pointB) {
                player.seekTo(pointA)
            }
            handler.postDelayed(this, 40)
        }
    }

    private val pickVideo =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
            if (uri != null) { keepPermission(uri); openVideo(uri) }
        }

    private val pickSrt =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
            if (uri != null) {
                keepPermission(uri)
                subtitleUri = uri
                subtitleLang = "und"
                reloadKeepingPosition()
                status("Subtitle file loaded: ${displayName(uri)}")
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        playerView = findViewById(R.id.playerView)
        statusText = findViewById(R.id.status)
        progress = findViewById(R.id.progress)
        btnOpen = findViewById(R.id.btnOpen)
        btnSubs = findViewById(R.id.btnSubs)
        btnLoadSrt = findViewById(R.id.btnLoadSrt)
        abLabel = findViewById(R.id.abLabel)

        player = ExoPlayer.Builder(this).build()
        playerView.player = player
        playerView.setShowSubtitleButton(true)
        playerView.subtitleView?.setFractionalTextSize(SubtitleView.DEFAULT_TEXT_SIZE_FRACTION * 1.25f)

        btnOpen.setOnClickListener { pickVideo.launch(arrayOf("video/*")) }
        btnSubs.setOnClickListener {
            if (job?.isActive == true) job?.cancel() else chooseLanguage()
        }
        btnLoadSrt.setOnClickListener {
            if (videoUri == null) toast("Open a video first") else pickSrt.launch(arrayOf("*/*"))
        }

        findViewById<Button>(R.id.btnA).setOnClickListener { setA() }
        findViewById<Button>(R.id.btnB).setOnClickListener { setB() }
        findViewById<Button>(R.id.btnABOff).setOnClickListener { clearAB() }

        handler.post(abLoop)
        updateAB()
        status("Open a video to start.")

        handleViewIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleViewIntent(intent)
    }

    private fun handleViewIntent(i: Intent?) {
        if (i?.action == Intent.ACTION_VIEW) i.data?.let { openVideo(it) }
    }

    override fun onStop() {
        super.onStop()
        player.pause()
    }

    override fun onDestroy() {
        handler.removeCallbacks(abLoop)
        job?.cancel()
        player.release()
        super.onDestroy()
    }

    // ---------------------------------------------------------------- video

    private fun openVideo(uri: Uri) {
        videoUri = uri
        clearAB()

        // Auto-load subtitles generated earlier for this video (if any)
        subtitleUri = null
        subtitleLang = "de"
        for (m in ModelManager.MODELS) {
            val f = srtFile(uri, m.lang)
            if (f.exists()) { subtitleUri = Uri.fromFile(f); subtitleLang = m.lang; break }
        }
        loadMedia(0L, true)
        status(
            if (subtitleUri != null) "${displayName(uri)} — saved ${langLabel(subtitleLang)} subtitles loaded."
            else displayName(uri)
        )
    }

    private fun loadMedia(positionMs: Long, play: Boolean) {
        val v = videoUri ?: return
        val builder = MediaItem.Builder().setUri(v)
        subtitleUri?.let { s ->
            builder.setSubtitleConfigurations(
                listOf(
                    MediaItem.SubtitleConfiguration.Builder(s)
                        .setMimeType(MimeTypes.APPLICATION_SUBRIP)
                        .setLanguage(subtitleLang)
                        .setSelectionFlags(C.SELECTION_FLAG_DEFAULT)
                        .build()
                )
            )
        }
        player.trackSelectionParameters = player.trackSelectionParameters.buildUpon()
            .setPreferredTextLanguage(if (subtitleLang == "und") null else subtitleLang)
            .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, false)
            .build()
        player.setMediaItem(builder.build(), positionMs)
        player.prepare()
        player.playWhenReady = play
    }

    private fun reloadKeepingPosition() = loadMedia(player.currentPosition, player.playWhenReady)

    private fun useSrt(file: File, lang: String) {
        subtitleUri = Uri.fromFile(file)
        subtitleLang = lang
        reloadKeepingPosition()
    }

    // ------------------------------------------------------------ subtitles

    private fun chooseLanguage() {
        if (videoUri == null) { toast("Open a video first"); return }
        val models = ModelManager.MODELS
        val labels = models.map { m ->
            m.label + if (ModelManager.isInstalled(this, m)) "   ✓ ready (offline)"
            else "   (download ~${m.sizeMb} MB once)"
        }.toTypedArray()
        AlertDialog.Builder(this)
            .setTitle("Generate subtitles — spoken language")
            .setItems(labels) { _, i -> onLanguageChosen(models[i]) }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun onLanguageChosen(m: ModelManager.SpeechModel) {
        val v = videoUri ?: return
        val existing = srtFile(v, m.lang)
        if (existing.exists()) {
            AlertDialog.Builder(this)
                .setTitle("${m.label} subtitles already exist")
                .setMessage("Show the saved subtitles, or transcribe the video again?")
                .setPositiveButton("Show") { _, _ -> useSrt(existing, m.lang); status("Showing saved subtitles.") }
                .setNegativeButton("Regenerate") { _, _ -> confirmModel(m) }
                .setNeutralButton("Cancel", null)
                .show()
        } else {
            confirmModel(m)
        }
    }

    private fun confirmModel(m: ModelManager.SpeechModel) {
        if (ModelManager.isInstalled(this, m)) { startTranscription(m); return }
        AlertDialog.Builder(this)
            .setTitle("Download speech model")
            .setMessage(
                "The ${m.label} speech-recognition model (~${m.sizeMb} MB) is needed once. " +
                    "After that, subtitles are made offline on your phone.\n\nDownload link:\n${m.url}"
            )
            .setPositiveButton("Download") { _, _ -> startTranscription(m) }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun startTranscription(m: ModelManager.SpeechModel) {
        val v = videoUri ?: return
        job = lifecycleScope.launch {
            setBusy(true)
            try {
                val modelDir = ModelManager.ensure(this@MainActivity, m) { pct, msg ->
                    runOnUiThread { showProgress(pct, msg) }
                }
                showProgress(0, "Transcribing…")
                val words = Transcriber.transcribe(this@MainActivity, v, modelDir) { pct ->
                    runOnUiThread { showProgress(pct, "Transcribing ${m.label}… $pct%  (tap Cancel to stop)") }
                }
                if (words.isEmpty()) {
                    status("No speech was recognised in this video.")
                    return@launch
                }
                val cues = SrtBuilder.cues(words)
                val out = srtFile(v, m.lang)
                withContext(Dispatchers.IO) {
                    out.parentFile?.mkdirs()
                    out.writeText(SrtBuilder.toSrt(cues))
                }
                if (videoUri == v) useSrt(out, m.lang)
                status("Done: ${cues.size} subtitle lines (${words.size} words). Saved as ${out.name}")
            } catch (e: CancellationException) {
                status("Cancelled.")
            } catch (e: Exception) {
                status("Error: ${e.message ?: e.javaClass.simpleName}")
            } finally {
                setBusy(false)
            }
        }
    }

    private fun setBusy(busy: Boolean) {
        btnSubs.text = if (busy) "Cancel" else "Subtitles"
        btnOpen.isEnabled = !busy
        btnLoadSrt.isEnabled = !busy
        progress.visibility = if (busy) View.VISIBLE else View.GONE
        if (busy) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    private fun showProgress(pct: Int, msg: String) {
        progress.progress = pct
        statusText.text = msg
    }

    /** Subtitles are saved in Android/data/com.behrouz.subplayer/files/subtitles/ */
    private fun srtFile(uri: Uri, lang: String): File {
        val dir = File(getExternalFilesDir(null) ?: filesDir, "subtitles")
        val base = displayName(uri).substringBeforeLast('.')
            .replace(Regex("[^\\p{L}\\p{N}._-]+"), "_").take(60)
        val key = Integer.toHexString(uri.toString().hashCode())
        return File(dir, "${base}_$key.$lang.srt")
    }

    // ------------------------------------------------------------ A-B repeat

    private fun setA() {
        if (videoUri == null) return
        pointA = player.currentPosition
        if (pointB in 0..pointA) pointB = -1
        updateAB()
    }

    private fun setB() {
        if (videoUri == null) return
        if (pointA < 0) { toast("Set A first"); return }
        val pos = player.currentPosition
        if (pos <= pointA + 200) { toast("B must be after A"); return }
        pointB = pos
        player.seekTo(pointA)
        updateAB()
    }

    private fun clearAB() {
        pointA = -1
        pointB = -1
        updateAB()
    }

    private fun updateAB() {
        abLabel.text = when {
            pointA >= 0 && pointB > pointA -> "Repeat ${fmt(pointA)} → ${fmt(pointB)}"
            pointA >= 0 -> "A = ${fmt(pointA)}  (now set B)"
            else -> "A-B repeat off"
        }
    }

    private fun fmt(ms: Long): String {
        val totalTenths = ms / 100
        val tenths = totalTenths % 10
        val totalSec = totalTenths / 10
        return String.format(Locale.US, "%d:%02d.%d", totalSec / 60, totalSec % 60, tenths)
    }

    // --------------------------------------------------------------- helpers

    private fun keepPermission(uri: Uri) {
        try {
            contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        } catch (_: Exception) { }
    }

    private fun displayName(uri: Uri): String {
        try {
            contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
                if (c.moveToFirst()) c.getString(0)?.let { return it }
            }
        } catch (_: Exception) { }
        return uri.lastPathSegment ?: "video"
    }

    private fun langLabel(lang: String) =
        ModelManager.MODELS.firstOrNull { it.lang == lang }?.label ?: "custom"

    private fun status(msg: String) { statusText.text = msg }

    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
}
