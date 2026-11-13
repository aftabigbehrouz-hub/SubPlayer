package com.behrouz.subplayer

import android.app.Application
import android.content.Intent
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.provider.OpenableColumns
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import com.behrouz.subplayer.asr.VoskEngine
import com.behrouz.subplayer.asr.WhisperEngine
import com.behrouz.subplayer.data.Assets
import com.behrouz.subplayer.data.Downloader
import com.behrouz.subplayer.dict.Dictionary
import com.behrouz.subplayer.dict.Speaker
import com.behrouz.subplayer.dict.Translator
import com.behrouz.subplayer.export.ClipExporter
import com.behrouz.subplayer.subs.Cue
import com.behrouz.subplayer.subs.CueBuilder
import com.behrouz.subplayer.subs.Srt
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

enum class Engine(val title: String, val detail: String) {
    FAST("Fast", "Vosk · quick, lower accuracy, no punctuation"),
    ACCURATE("Accurate", "Whisper Base · ~57 MB · usually faster than the video"),
    BEST("Best", "Whisper Small · ~182 MB · takes about as long as the video")
}

data class Task(val title: String, val message: String, val progress: Int)   // progress -1 = busy

sealed class Sheet {
    data class Word(
        val word: String,
        val sentence: String,
        val loading: Boolean = true,
        val entries: List<Dictionary.Entry> = emptyList(),
        val needDictionary: Boolean = false,
        val onlineEn: String? = null,
        val onlineFa: String? = null,
        val onlineBusy: Boolean = false
    ) : Sheet()

    data class Phrase(
        val text: String,
        val words: List<String>,
        val en: String? = null,
        val fa: String? = null,
        val busy: Boolean = true,
        val error: String? = null,
        val service: String? = null,
        val glosses: Map<String, String> = emptyMap()
    ) : Sheet()

    object Generate : Sheet()
    object Export : Sheet()
}

@androidx.annotation.OptIn(UnstableApi::class)
class AppViewModel(app: Application) : AndroidViewModel(app) {

    private val ctx = app.applicationContext
    private val main = Handler(Looper.getMainLooper())
    val player: ExoPlayer = ExoPlayer.Builder(app).build()
    val speaker = Speaker(app)

    var videoUri by mutableStateOf<Uri?>(null); private set
    var videoName by mutableStateOf(""); private set
    var cues by mutableStateOf<List<Cue>>(emptyList()); private set
    var cueLang by mutableStateOf("de"); private set
    var cueInfo by mutableStateOf(""); private set
    var showSubs by mutableStateOf(true)

    var position by mutableLongStateOf(0L); private set
    var duration by mutableLongStateOf(0L); private set
    var playing by mutableStateOf(false); private set
    var currentCue by mutableIntStateOf(-1); private set

    var pointA by mutableLongStateOf(-1L); private set
    var pointB by mutableLongStateOf(-1L); private set
    var speed by mutableFloatStateOf(1f); private set

    var task by mutableStateOf<Task?>(null); private set
    var message by mutableStateOf<String?>(null)
    var sheet by mutableStateOf<Sheet?>(null)

    // word selection inside the frozen cue
    var selCue by mutableIntStateOf(-1); private set
    var selStart by mutableIntStateOf(-1); private set
    var selEnd by mutableIntStateOf(-1); private set
    var phraseMode by mutableStateOf(false); private set

    var genLang by mutableStateOf("de")
    var genEngine by mutableStateOf(Engine.ACCURATE)
    val whisperSupported = WhisperEngine.cpuSupported()

    private var job: Job? = null
    private var dictionary: Dictionary? = null

    init {
        if (!whisperSupported) genEngine = Engine.FAST
        viewModelScope.launch {
            while (true) {
                position = player.currentPosition
                duration = player.duration.coerceAtLeast(0)
                playing = player.isPlaying
                if (pointA >= 0 && pointB > pointA && position >= pointB) {
                    player.seekTo(pointA); position = pointA
                }
                currentCue = CueBuilder.indexAt(cues, position)
                delay(50)
            }
        }
    }

    private fun ui(block: () -> Unit) = main.post(block)

    // ---------------------------------------------------------------- video

    fun openVideo(uri: Uri) {
        videoUri = uri
        videoName = displayName(uri)
        clearAB()
        clearSelection()
        cues = emptyList(); cueInfo = ""
        for (lang in listOf("de", "en")) {
            val f = srtFile(uri, lang)
            if (f.exists()) {
                cues = Srt.parse(f.readText()); cueLang = lang
                cueInfo = "Saved ${langName(lang)} subtitles"
                break
            }
        }
        player.setMediaItem(MediaItem.fromUri(uri))
        player.prepare()
        player.playWhenReady = true
    }

    fun togglePlay() {
        if (player.isPlaying) player.pause() else {
            if (player.playbackState == androidx.media3.common.Player.STATE_ENDED) player.seekTo(0)
            player.play()
        }
    }

    fun seekTo(ms: Long) = player.seekTo(ms.coerceIn(0, maxOf(duration, 0)))
    fun skip(deltaMs: Long) = seekTo(player.currentPosition + deltaMs)

    fun prevLine() {
        if (cues.isEmpty()) return skip(-5000)
        val i = CueBuilder.indexBefore(cues, player.currentPosition - 600)
        seekTo(if (i >= 0) cues[i].startMs else 0)
    }

    fun nextLine() {
        if (cues.isEmpty()) return skip(5000)
        val pos = player.currentPosition
        cues.firstOrNull { it.startMs > pos + 100 }?.let { seekTo(it.startMs) }
    }

    fun cycleSpeed() {
        speed = when (speed) { 1f -> 0.75f; 0.75f -> 0.5f; else -> 1f }
        player.setPlaybackSpeed(speed)
    }

    // ------------------------------------------------------------- A-B

    fun setA() { pointA = player.currentPosition; if (pointB in 0..pointA) pointB = -1 }

    fun setB() {
        if (pointA < 0) { message = "Set A first"; return }
        val p = player.currentPosition
        if (p <= pointA + 200) { message = "B must be after A"; return }
        pointB = p; player.seekTo(pointA)
    }

    fun loopLine() {
        val i = if (currentCue >= 0) currentCue else CueBuilder.indexBefore(cues, player.currentPosition)
        if (i < 0) { message = "No subtitle line here"; return }
        pointA = (cues[i].startMs - 150).coerceAtLeast(0)
        pointB = cues[i].endMs + 250
        player.seekTo(pointA); player.play()
    }

    fun clearAB() { pointA = -1; pointB = -1 }

    // ---------------------------------------------------- word selection

    fun onWordTap(cueIndex: Int, wordIndex: Int) {
        player.pause()
        val cue = cues.getOrNull(cueIndex) ?: return
        val words = tokens(cue.text)
        if (phraseMode && selCue == cueIndex && selStart >= 0) {
            selEnd = wordIndex
            phraseMode = false
            val a = minOf(selStart, selEnd); val b = maxOf(selStart, selEnd)
            selStart = a; selEnd = b
            if (a == b) openWord(words[a], cue.text) else openPhrase(words.subList(a, b + 1))
        } else {
            selCue = cueIndex; selStart = wordIndex; selEnd = wordIndex; phraseMode = false
            openWord(words[wordIndex], cue.text)
        }
    }

    fun onWordLongPress(cueIndex: Int, wordIndex: Int) {
        player.pause()
        selCue = cueIndex; selStart = wordIndex; selEnd = wordIndex; phraseMode = true
        message = "Now tap the last word of the phrase"
    }

    fun selectWholeLine(cueIndex: Int) {
        val cue = cues.getOrNull(cueIndex) ?: return
        player.pause()
        val w = tokens(cue.text)
        selCue = cueIndex; selStart = 0; selEnd = w.size - 1; phraseMode = false
        openPhrase(w)
    }

    fun clearSelection() { selCue = -1; selStart = -1; selEnd = -1; phraseMode = false }

    fun closeSheet() {
        sheet = null
        clearSelection()
    }

    fun openWord(raw: String, sentence: String) {
        val word = Dictionary.normalize(raw)
        if (word.isEmpty()) return
        sheet = Sheet.Word(word, sentence)
        viewModelScope.launch {
            val d = dictionaryOrNull()
            if (d == null) {
                update<Sheet.Word> { it.copy(loading = false, needDictionary = true) }
                return@launch
            }
            val res = withContext(Dispatchers.IO) { runCatching { d.lookup(word) }.getOrDefault(emptyList()) }
            update<Sheet.Word> { if (it.word == word) it.copy(loading = false, entries = res) else it }
        }
    }

    fun translateWordOnline() {
        val s = sheet as? Sheet.Word ?: return
        update<Sheet.Word> { it.copy(onlineBusy = true) }
        viewModelScope.launch {
            val en = runCatching { Translator.translate(s.word, "de", "en").text }.getOrElse { "— (${it.message})" }
            val fa = runCatching { Translator.translate(s.word, "de", "fa").text }.getOrElse { "—" }
            update<Sheet.Word> { if (it.word == s.word) it.copy(onlineEn = en, onlineFa = fa, onlineBusy = false) else it }
        }
    }

    private fun openPhrase(words: List<String>) {
        val text = words.joinToString(" ")
        val clean = words.map { Dictionary.normalize(it) }.filter { it.isNotEmpty() }
        sheet = Sheet.Phrase(text, clean)
        viewModelScope.launch {
            // word-by-word glosses from the offline dictionary
            dictionaryOrNull()?.let { d ->
                val g = withContext(Dispatchers.IO) {
                    clean.associateWith { w ->
                        runCatching { d.lookup(w).firstOrNull()?.let { e -> e.english.firstOrNull() ?: e.senses.firstOrNull()?.de ?: "" } }
                            .getOrNull().orEmpty().take(60)
                    }
                }
                update<Sheet.Phrase> { if (it.text == text) it.copy(glosses = g) else it }
            }
        }
        viewModelScope.launch {
            try {
                val en = Translator.translate(text, cueLangOrDe(), "en")
                val fa = Translator.translate(text, cueLangOrDe(), "fa")
                update<Sheet.Phrase> { if (it.text == text) it.copy(en = en.text, fa = fa.text, busy = false, service = en.service) else it }
            } catch (e: Exception) {
                update<Sheet.Phrase> {
                    if (it.text == text) it.copy(busy = false, error = "Offline — sentence translation needs internet. Word meanings are shown below.") else it
                }
            }
        }
    }

    private fun cueLangOrDe() = if (cueLang == "en") "en" else "de"

    private inline fun <reified T : Sheet> update(f: (T) -> Sheet) {
        val s = sheet
        if (s is T) sheet = f(s)
    }

    fun dictionaryReady() = Downloader.isReady(ctx, Assets.DICT_DE)

    fun downloadDictionary() {
        if (job?.isActive == true) { message = "Please wait for the current task"; return }
        job = viewModelScope.launch {
            task = Task("Dictionary", "Downloading German dictionary…", 0)
            try {
                Downloader.ensure(ctx, Assets.DICT_DE) { p -> ui { task = Task("Dictionary", "Downloading German dictionary… $p%", p) } }
                message = "Dictionary ready — works offline"
                (sheet as? Sheet.Word)?.let { openWord(it.word, it.sentence) }
            } catch (e: CancellationException) {
                message = "Cancelled"
            } catch (e: Exception) {
                message = "Download failed — " + describe(e)
            } finally {
                task = null
            }
        }
    }

    private suspend fun dictionaryOrNull(): Dictionary? {
        dictionary?.let { return it }
        if (!dictionaryReady()) return null
        return withContext(Dispatchers.IO) {
            runCatching { Dictionary(Downloader.target(ctx, Assets.DICT_DE)) }.getOrNull()
        }?.also { dictionary = it }
    }

    fun speak(text: String, slow: Boolean = false) {
        if (!speaker.speak(text, slow)) {
            message = "No German voice installed. Open Settings › Text-to-speech and add German."
        }
    }

    fun playRecording(url: String) {
        player.pause()
        speaker.playRecording(url) { err -> ui { message = err } }
    }

    fun openDwds(word: String) {
        val i = Intent(Intent.ACTION_VIEW, Uri.parse("https://www.dwds.de/wb/" + Uri.encode(word)))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        runCatching { ctx.startActivity(i) }.onFailure { message = "No browser found" }
    }

    // ----------------------------------------------------- subtitles

    fun loadSrt(uri: Uri) {
        try {
            val text = ctx.contentResolver.openInputStream(uri)?.use { it.readBytes().toString(Charsets.UTF_8) } ?: ""
            val parsed = Srt.parse(text)
            if (parsed.isEmpty()) { message = "No subtitles found in that file"; return }
            cues = parsed; cueLang = "de"; cueInfo = "Loaded ${displayName(uri)}"
            message = "${parsed.size} subtitle lines loaded"
        } catch (e: Exception) {
            message = "Could not read file: ${e.message}"
        }
    }

    fun cancelTask() { job?.cancel() }

    fun generate() {
        val uri = videoUri ?: run { message = "Open a video first"; return }
        if (job?.isActive == true) { message = "Please wait for the current task"; return }
        val lang = genLang
        val engine = genEngine
        sheet = null
        job = viewModelScope.launch {
            val title = "${langName(lang)} subtitles · ${engine.title}"
            task = Task(title, "Preparing…", -1)
            fun dl(a: Assets.Asset): suspend () -> File = {
                Downloader.ensure(ctx, a) { p -> ui { task = Task(title, "Downloading ${a.label}… $p%", p) } }
            }
            try {
                val result = when (engine) {
                    Engine.FAST -> {
                        val model = dl(if (lang == "de") Assets.VOSK_DE else Assets.VOSK_EN)()
                        task = Task(title, "Transcribing…", 0)
                        VoskEngine.transcribe(ctx, uri, model) { p -> ui { task = Task(title, "Transcribing… $p%", p) } }
                    }
                    Engine.ACCURATE, Engine.BEST -> {
                        val model = dl(if (engine == Engine.BEST) Assets.WHISPER_SMALL else Assets.WHISPER_BASE)()
                        val vad = dl(Assets.VAD)()
                        task = Task(title, "Transcribing…", 0)
                        WhisperEngine.transcribe(ctx, uri, model, vad, lang) { p ->
                            ui { task = Task(title, "Transcribing… $p%  (keep the app open)", p) }
                        }
                    }
                }
                if (result.isEmpty()) {
                    message = "No speech was recognised"
                } else {
                    val f = srtFile(uri, lang)
                    withContext(Dispatchers.IO) { f.parentFile?.mkdirs(); f.writeText(Srt.write(result)) }
                    if (videoUri == uri) {
                        cues = result; cueLang = lang
                        cueInfo = "${langName(lang)} · ${engine.title}"
                    }
                    message = "Done: ${result.size} subtitle lines"
                }
            } catch (e: CancellationException) {
                message = "Cancelled"
            } catch (e: Throwable) {
                message = "Subtitles failed — " + describe(e)
            } finally {
                task = null
            }
        }
    }

    fun assetReady(a: Assets.Asset) = Downloader.isReady(ctx, a)

    // --------------------------------------------------------- export

    fun export(burn: Boolean) {
        val uri = videoUri ?: return
        if (pointA < 0 || pointB <= pointA) { message = "Set A and B first"; return }
        if (job?.isActive == true) { message = "Please wait for the current task"; return }
        sheet = null
        val a = pointA; val b = pointB
        job = viewModelScope.launch {
            task = Task("Saving clip", "Preparing…", -1)
            try {
                val where = ClipExporter.export(ctx, uri, videoName, a, b, cues, burn) { p ->
                    task = Task("Saving clip", "Encoding… $p%", p)
                }
                message = "Saved to $where"
            } catch (e: CancellationException) {
                message = "Cancelled"
            } catch (e: Throwable) {
                message = "Saving the clip failed — " + describe(e)
            } finally {
                task = null
            }
        }
    }

    // --------------------------------------------------------- helpers

    /** Readable error: what went wrong, the underlying cause, and where in the app. */
    private fun describe(e: Throwable): String {
        android.util.Log.e("SubPlayer", "task failed", e)
        val root = generateSequence(e) { it.cause }.last()
        val where = e.stackTrace.firstOrNull { it.className.startsWith("com.behrouz") }
            ?: root.stackTrace.firstOrNull { it.className.startsWith("com.behrouz") }
        val main = e.message ?: e.javaClass.simpleName
        val cause = if (root !== e) " · cause: ${root.javaClass.simpleName}${root.message?.let { ": $it" } ?: ""}" else ""
        val at = where?.let { " · at ${it.fileName}:${it.lineNumber}" } ?: ""
        return main + cause + at
    }

    fun tokens(text: String): List<String> = text.split(Regex("\\s+")).filter { it.isNotBlank() }

    private fun srtFile(uri: Uri, lang: String): File {
        val dir = File(ctx.getExternalFilesDir(null) ?: ctx.filesDir, "subtitles")
        val base = displayName(uri).substringBeforeLast('.').replace(Regex("[^\\p{L}\\p{N}._-]+"), "_").take(60)
        return File(dir, "${base}_${Integer.toHexString(uri.toString().hashCode())}.$lang.srt")
    }

    fun displayName(uri: Uri): String {
        try {
            ctx.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
                if (c.moveToFirst()) c.getString(0)?.let { return it }
            }
        } catch (_: Exception) { }
        return uri.lastPathSegment ?: "video"
    }

    fun langName(l: String) = if (l == "en") "English" else "German"

    override fun onCleared() {
        job?.cancel()
        player.release()
        speaker.shutdown()
        dictionary?.close()
    }
}
