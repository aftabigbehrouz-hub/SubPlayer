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
import com.behrouz.subplayer.licence.Licence
import com.behrouz.subplayer.words.Cloze
import com.behrouz.subplayer.words.Example
import com.behrouz.subplayer.words.Practice
import com.behrouz.subplayer.words.Progress
import com.behrouz.subplayer.words.Recents
import com.behrouz.subplayer.words.Sentences
import com.behrouz.subplayer.words.Reminder
import com.behrouz.subplayer.words.SavedWord
import com.behrouz.subplayer.words.Srs
import com.behrouz.subplayer.words.WordStore
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
        val onlineBusy: Boolean = false,
        val cueStart: Long = -1,
        val cueEnd: Long = -1,
        val saved: Boolean = false
    ) : Sheet()

    data class Phrase(
        val text: String,
        val words: List<String>,
        val en: String? = null,
        val fa: String? = null,
        val busy: Boolean = true,
        val error: String? = null,
        val service: String? = null,
        val glosses: Map<String, String> = emptyMap(),
        val sentence: String = "",
        val cueStart: Long = -1,
        val cueEnd: Long = -1,
        val saved: Boolean = false
    ) : Sheet()

    object Generate : Sheet()
    object Export : Sheet()
    data class AddSentences(val wordId: Long, val title: String, val initial: String) : Sheet()
    object SubFile : Sheet()
    object Help : Sheet()
    object Settings : Sheet()
    object Videos : Sheet()
}

enum class Screen { PLAYER, WORDS, REVIEW, PRACTICE }

enum class PracticeMode(val title: String, val explain: String) {
    GAPS("Fill the gap", "A sentence with one of your words missing. Choose or type it."),
    DICTATION("Dictation", "Hear the line from the video and type what you hear. Every word is checked."),
    ARTICLES("der · die · das", "Your saved nouns: pick the right article.")
}

sealed class Question {
    data class Gap(val cloze: Cloze, val choices: List<String>) : Question()
    data class Dictation(val word: SavedWord) : Question()
    data class Article(val word: SavedWord) : Question()
}

/** Result of the current practice answer (null = not answered yet). */
data class Feedback(val correct: Boolean, val detail: String, val marks: List<Practice.Mark> = emptyList())

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

    // ---- navigation / app state
    var screen by mutableStateOf(Screen.PLAYER)
    var controlsVisible by mutableStateOf(true)
    private var lastInteraction = System.currentTimeMillis()

    // ---- saved words + review
    private val store = WordStore(app)
    val recents = Recents(app)
    var words by mutableStateOf<List<SavedWord>>(emptyList()); private set
    var savedKeys by mutableStateOf<Set<String>>(emptySet()); private set
    var dueCount by mutableIntStateOf(0); private set
    var reviewQueue by mutableStateOf<List<SavedWord>>(emptyList()); private set
    var reviewIndex by mutableIntStateOf(0); private set
    var reviewRevealed by mutableStateOf(false); private set
    var reviewDone by mutableIntStateOf(0); private set
    var reviewGot by mutableIntStateOf(0); private set
    var recentList by mutableStateOf<List<Recents.Item>>(emptyList()); private set
    var wordExamples by mutableStateOf<Map<Long, List<Example>>>(emptyMap()); private set

    // ---- practice
    private val progress = Progress(app)
    var streak by mutableIntStateOf(progress.streak); private set
    var todayCount by mutableIntStateOf(progress.todayCount); private set
    var practiceMode by mutableStateOf<PracticeMode?>(null); private set
    var questions by mutableStateOf<List<Question>>(emptyList()); private set
    var qIndex by mutableIntStateOf(0); private set
    var feedback by mutableStateOf<Feedback?>(null); private set
    var practiceScore by mutableIntStateOf(0); private set

    // ---- listening modes
    var autoPause by mutableStateOf(false)
    var shadowing by mutableStateOf(false)
    var shadowWaiting by mutableStateOf(false); private set
    var heldCue by mutableIntStateOf(-1); private set
    private var shadowResumeAt = 0L
    private var lastCueIdx = -1

    // ---- licence
    var licence by mutableStateOf(Licence.current(app)); private set
    val deviceCode: String = Licence.deviceCode(app)
    var isOwner by mutableStateOf(Licence.ownerKey(app) != null); private set
    var trialLeft by mutableIntStateOf(Licence.checkTrial(app)); private set
    var showActivation by mutableStateOf(false)
    val trialEnded get() = licence == null && trialLeft <= 0

    // ---- first-run tour + reminder settings
    private val uiPrefs = app.getSharedPreferences("ui", android.content.Context.MODE_PRIVATE)
    var showTour by mutableStateOf(!uiPrefs.getBoolean("tour_done", false))
    var reminderOn by mutableStateOf(Reminder.enabled(app)); private set
    var reminderHour by mutableIntStateOf(Reminder.hour(app)); private set

    init {
        if (!whisperSupported) genEngine = Engine.FAST
        refreshWords()
        recentList = recents.list()
        if (licence == null) {
            Reminder.scheduleTrial(app, Licence.trialEnd(app))
            if (trialLeft in 1..1) message = "Last day of your free trial — tap the trial badge to buy"
        }
        viewModelScope.launch {
            while (true) {
                position = player.currentPosition
                duration = player.duration.coerceAtLeast(0)
                playing = player.isPlaying
                val nowMs = System.currentTimeMillis()
                // Shadowing: after the loop end, pause so the learner can repeat, then replay
                if (shadowResumeAt > 0 && nowMs >= shadowResumeAt) {
                    shadowResumeAt = 0; shadowWaiting = false
                    if (pointA >= 0) { player.seekTo(pointA); player.play() }
                }
                if (pointA >= 0 && pointB > pointA && position >= pointB && shadowResumeAt == 0L) {
                    if (shadowing) {
                        player.pause(); player.seekTo(pointA); position = pointA
                        shadowResumeAt = nowMs + ((pointB - pointA) * 1.2).toLong() + 600
                        shadowWaiting = true
                    } else {
                        player.seekTo(pointA); position = pointA
                    }
                }
                val idx = CueBuilder.indexAt(cues, position)
                // Pause after each line (keeps the finished line on screen to read and tap)
                if (autoPause && playing && pointB < 0 && lastCueIdx >= 0 && idx != lastCueIdx) {
                    player.pause(); playing = false; heldCue = lastCueIdx
                }
                if (playing && idx >= 0) heldCue = -1
                lastCueIdx = idx
                currentCue = idx
                if (playing && controlsVisible && System.currentTimeMillis() - lastInteraction > 3500) controlsVisible = false
                if (playing && position / 1000 % 5 == 0L && position % 1000 < 60) rememberPosition()
                delay(50)
            }
        }
    }

    private fun ui(block: () -> Unit) = main.post(block)

    // ---------------------------------------------------------------- video

    fun openVideo(uri: Uri, resume: Boolean = true) {
        rememberPosition()
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
        val startAt = if (resume) recents.get(uri.toString())?.positionMs?.takeIf { it > 3000 } ?: 0L else 0L
        player.setMediaItem(MediaItem.fromUri(uri), startAt)
        player.prepare()
        player.playWhenReady = true
        recents.put(Recents.Item(uri.toString(), videoName, startAt, 0, System.currentTimeMillis()))
        recentList = recents.list()
        screen = Screen.PLAYER
        if (startAt > 0) message = "Continuing from ${com.behrouz.subplayer.ui.fmt(startAt)}"
    }

    /** Stores where the user is in the current video (for "continue watching"). */
    fun rememberPosition() {
        val u = videoUri ?: return
        val d = player.duration.coerceAtLeast(0)
        val p = player.currentPosition
        recents.put(Recents.Item(u.toString(), videoName, if (d > 0 && p > d - 5000) 0 else p, d, System.currentTimeMillis()))
        recentList = recents.list()
    }

    fun openRecent(item: Recents.Item) {
        val uri = Uri.parse(item.uri)
        if (!canRead(uri)) {
            message = "That video can no longer be opened (moved or deleted?). Open it again with the folder button."
            recents.remove(item.uri); recentList = recents.list()
            return
        }
        sheet = null
        openVideo(uri)
    }

    private fun canRead(uri: Uri): Boolean = try {
        ctx.contentResolver.openFileDescriptor(uri, "r")?.use { true } ?: false
    } catch (_: Exception) {
        false
    }

    fun touch() { lastInteraction = System.currentTimeMillis(); controlsVisible = true }

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

    fun clearAB() { pointA = -1; pointB = -1; shadowResumeAt = 0; shadowWaiting = false }

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
            if (a == b) openWord(words[a], cue.text, cue.startMs, cue.endMs) else openPhrase(words.subList(a, b + 1), cue.text, cue.startMs, cue.endMs)
        } else {
            selCue = cueIndex; selStart = wordIndex; selEnd = wordIndex; phraseMode = false
            openWord(words[wordIndex], cue.text, cue.startMs, cue.endMs)
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
        openPhrase(w, cue.text, cue.startMs, cue.endMs)
    }

    fun clearSelection() { selCue = -1; selStart = -1; selEnd = -1; phraseMode = false }

    fun closeSheet() {
        sheet = null
        clearSelection()
    }

    fun openWord(raw: String, sentence: String, cueStart: Long = -1, cueEnd: Long = -1) {
        val word = Dictionary.normalize(raw)
        if (word.isEmpty()) return
        val prev = sheet
        val (cs, ce, sent) = if (cueStart >= 0) Triple(cueStart, cueEnd, sentence) else when (prev) {
            is Sheet.Word -> Triple(prev.cueStart, prev.cueEnd, prev.sentence)
            is Sheet.Phrase -> Triple(prev.cueStart, prev.cueEnd, prev.sentence)
            else -> Triple(-1L, -1L, sentence)
        }
        sheet = Sheet.Word(word, sent, cueStart = cs, cueEnd = ce, saved = isSaved(word, cs))
        viewModelScope.launch {
            val d = dictionaryOrNull()
            if (d == null) {
                update<Sheet.Word> { if (it.word == word) it.copy(loading = false, needDictionary = true) else it }
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

    private fun openPhrase(words: List<String>, sentence: String, cueStart: Long, cueEnd: Long) {
        val text = words.joinToString(" ")
        val clean = words.map { Dictionary.normalize(it) }.filter { it.isNotEmpty() }
        sheet = Sheet.Phrase(text, clean, sentence = sentence, cueStart = cueStart, cueEnd = cueEnd,
            saved = isSaved(text, cueStart))
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


    // ------------------------------------------------------ saved words

    private fun key(text: String) = Dictionary.normalize(text).lowercase()

    private fun isSaved(text: String, cueStart: Long): Boolean {
        val u = videoUri?.toString() ?: return false
        return store.find(Dictionary.normalize(text), u, cueStart) != null
    }

    fun refreshWords() {
        val all = store.all()
        words = all
        savedKeys = all.map { key(it.text) }.toSet()
        wordExamples = store.allExamples()
        dueCount = store.dueCount(System.currentTimeMillis())
    }

    /** Saves the word/phrase in the open card, with its sentence and video moment. */
    fun saveFromSheet() {
        val u = videoUri ?: run { message = "Open the video first"; return }
        val now = System.currentTimeMillis()
        val w: SavedWord = when (val s = sheet) {
            is Sheet.Word -> {
                val e = s.entries.firstOrNull()
                SavedWord(
                    text = s.word, lemma = e?.lemma ?: s.word, article = e?.article ?: "", ipa = e?.ipa ?: "",
                    english = e?.english?.take(2)?.joinToString("; ") ?: s.onlineEn.orEmpty(),
                    persian = (e?.persian?.takeIf { it.isNotEmpty() } ?: e?.persianViaEnglish)?.take(3)?.joinToString("، ")
                        ?: s.onlineFa.orEmpty(),
                    sentence = s.sentence, videoUri = u.toString(), videoName = videoName,
                    startMs = s.cueStart.coerceAtLeast(0), endMs = maxOf(s.cueEnd, s.cueStart + 2000),
                    created = now, due = now
                )
            }
            is Sheet.Phrase -> SavedWord(
                text = s.text, lemma = s.text, english = s.en.orEmpty(), persian = s.fa.orEmpty(),
                sentence = s.sentence, videoUri = u.toString(), videoName = videoName,
                startMs = s.cueStart.coerceAtLeast(0), endMs = maxOf(s.cueEnd, s.cueStart + 2000),
                created = now, due = now
            )
            else -> return
        }
        val existing = store.find(w.text, w.videoUri, w.startMs)
        if (existing != null) {
            store.delete(existing.id)
            message = "Removed from My Words"
        } else {
            store.insert(w)
            message = "★ Saved to My Words — it will come up for review"
        }
        refreshWords()
        when (val s = sheet) {
            is Sheet.Word -> sheet = s.copy(saved = existing == null)
            is Sheet.Phrase -> sheet = s.copy(saved = existing == null)
            else -> {}
        }
    }

    fun isKnownWord(token: String) = key(token) in savedKeys

    fun deleteWord(w: SavedWord) { store.delete(w.id); refreshWords() }

    /** Opens the word's video (if needed) and loops the subtitle line it came from. */
    fun playClip(w: SavedWord, stayOnScreen: Boolean = true) {
        val uri = Uri.parse(w.videoUri)
        if (videoUri?.toString() != w.videoUri) {
            if (!canRead(uri)) { message = "The video \"${w.videoName}\" can't be opened any more. Open it once with the folder button."; return }
            val keep = screen
            openVideo(uri, resume = false)
            if (stayOnScreen) screen = keep
        }
        pointA = (w.startMs - 200).coerceAtLeast(0)
        pointB = w.endMs + 300
        player.seekTo(pointA)
        player.play()
    }

    fun startReview() {
        val q = store.due(System.currentTimeMillis()).ifEmpty { store.all().sortedBy { it.due }.take(20) }
        if (q.isEmpty()) { message = "Save some words first: pause, tap a word, then ★ Save"; return }
        reviewQueue = q; reviewIndex = 0; reviewRevealed = false; reviewDone = 0; reviewGot = 0
        screen = Screen.REVIEW
    }

    fun revealAnswer() { reviewRevealed = true }

    fun answer(gotIt: Boolean) {
        val w = reviewQueue.getOrNull(reviewIndex) ?: return
        val updated = Srs.review(w, gotIt, System.currentTimeMillis())
        store.update(updated)
        recordProgress()
        reviewDone++
        if (gotIt) reviewGot++
        // "Again" puts the word back at the end of this session
        if (!gotIt) reviewQueue = reviewQueue + updated
        reviewIndex++
        reviewRevealed = false
        clearAB()
        player.pause()
        refreshWords()
    }

    fun endReview() { clearAB(); player.pause(); screen = Screen.WORDS }

    /** Set when the reminder needs the notification permission first (the activity asks for it). */
    var pendingReminder by mutableStateOf<Pair<Boolean, Int>?>(null)

    fun requestReminder(on: Boolean, hour: Int) {
        if (on && !Reminder.canNotify(ctx)) pendingReminder = on to hour else setReminder(on, hour)
    }

    fun setReminder(on: Boolean, hour: Int) {
        Reminder.set(ctx, on, hour)
        reminderOn = on; reminderHour = hour
        if (on) message = "Daily reminder at %02d:00".format(hour)
    }

    fun finishTour() { showTour = false; uiPrefs.edit().putBoolean("tour_done", true).apply() }


    // ------------------------------------------------------ subtitle file

    private fun srtName() = displayName(videoUri ?: Uri.EMPTY).substringBeforeLast('.')
        .replace(Regex("[^\\p{L}\\p{N}._-]+"), "_").take(60) + ".$cueLang.srt"

    /** Saves the current subtitles as an .srt file in Download/SubPlayer. */
    fun exportSrt() {
        if (cues.isEmpty()) { message = "No subtitles to save yet"; return }
        val name = srtName()
        val bytes = Srt.write(cues).toByteArray(Charsets.UTF_8)
        try {
            val where = if (android.os.Build.VERSION.SDK_INT >= 29) {
                val values = android.content.ContentValues().apply {
                    put(android.provider.MediaStore.Downloads.DISPLAY_NAME, name)
                    put(android.provider.MediaStore.Downloads.MIME_TYPE, "application/x-subrip")
                    put(android.provider.MediaStore.Downloads.RELATIVE_PATH, android.os.Environment.DIRECTORY_DOWNLOADS + "/SubPlayer")
                }
                val uri = ctx.contentResolver.insert(android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                    ?: throw java.io.IOException("could not create the file")
                ctx.contentResolver.openOutputStream(uri)?.use { it.write(bytes) } ?: throw java.io.IOException("could not write")
                "Download/SubPlayer/$name"
            } else {
                val dir = File(ctx.getExternalFilesDir(android.os.Environment.DIRECTORY_DOWNLOADS), "SubPlayer").apply { mkdirs() }
                File(dir, name).writeBytes(bytes)
                File(dir, name).absolutePath
            }
            message = "Saved to $where"
        } catch (e: Exception) {
            message = "Could not save — " + describe(e)
        }
    }

    /** Shares the current subtitles as an .srt file (Telegram, e-mail, Drive …). */
    fun shareSrt() {
        if (cues.isEmpty()) { message = "No subtitles to share yet"; return }
        try {
            val dir = File(ctx.cacheDir, "share").apply { mkdirs() }
            val f = File(dir, srtName()); f.writeText(Srt.write(cues))
            val uri = androidx.core.content.FileProvider.getUriForFile(ctx, ctx.packageName + ".files", f)
            val send = Intent(Intent.ACTION_SEND).setType("application/x-subrip").putExtra(Intent.EXTRA_STREAM, uri)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            ctx.startActivity(Intent.createChooser(send, "Share subtitles").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION))
        } catch (e: Exception) {
            message = "Could not share — " + describe(e)
        }
    }

    // ------------------------------------------------------ learn more

    enum class Source { CHATGPT, GROK, DWDS, DICTCC }

    private fun aiPrompt(word: String, sentence: String) =
        "Explain the German word „$word“" + (if (sentence.isNotBlank()) " as used in: „${sentence.replace('\n', ' ')}“" else "") + ".\n" +
            "1) Meaning in English and in Persian.\n" +
            "2) IPA; for nouns article and plural, for verbs Präteritum and Perfekt.\n" +
            "3) Exactly 3 natural example sentences (Beispielsätze) of everyday German, one per line, in this format:\n" +
            "DE: … | EN: … | FA: …"

    /** Opens ChatGPT / Grok with a ready question, or DWDS / dict.cc for the word. */
    fun learnMore(source: Source, word: String, sentence: String) {
        val w = word.trim()
        val url = when (source) {
            Source.CHATGPT -> "https://chatgpt.com/?q=" + Uri.encode(aiPrompt(w, sentence))
            Source.GROK -> "https://grok.com/?q=" + Uri.encode(aiPrompt(w, sentence))
            Source.DWDS -> "https://www.dwds.de/wb/" + Uri.encode(w)
            Source.DICTCC -> "https://www.dict.cc/?s=" + Uri.encode(w)
        }
        if (source == Source.CHATGPT || source == Source.GROK) {
            val cm = ctx.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
            cm.setPrimaryClip(android.content.ClipData.newPlainText("SubPlayer question", aiPrompt(w, sentence)))
            android.widget.Toast.makeText(ctx, "Question copied too — paste it if the chat opens empty. " +
                "Then copy the 3 sentences back and tap “Add sentences”.", android.widget.Toast.LENGTH_LONG).show()
        }
        runCatching {
            ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }.onFailure { message = "No browser or app found to open it" }
    }

    fun clipboardText(): String {
        val cm = ctx.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
        return cm.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(ctx)?.toString().orEmpty()
    }

    /** Makes sure the word in the open card is saved (without toggling) and returns it. */
    fun ensureSavedFromSheet(): SavedWord? {
        val u = videoUri?.toString() ?: run { message = "Open the video first"; return null }
        val (text, start) = when (val s = sheet) {
            is Sheet.Word -> s.word to s.cueStart.coerceAtLeast(0)
            is Sheet.Phrase -> s.text to s.cueStart.coerceAtLeast(0)
            else -> return null
        }
        store.find(Dictionary.normalize(text), u, start)?.let { return it }
        saveFromSheet()
        return store.find(Dictionary.normalize(text), u, start)
    }

    fun openAddSentences(w: SavedWord) {
        sheet = Sheet.AddSentences(w.id, w.text, clipboardText())
    }

    fun previewSentences(raw: String) = Sentences.parse(raw)

    fun addSentences(wordId: Long, raw: String) {
        val list = Sentences.parse(raw)
        if (list.isEmpty()) { message = "No sentences found. Each line should look like: DE: … | EN: … | FA: …"; return }
        val n = store.addExamples(wordId, list)
        refreshWords()
        sheet = null
        message = if (n == 0) "Those sentences are already saved" else "$n sentence${if (n == 1) "" else "s"} added — they'll appear in review and practice"
    }

    fun deleteExample(e: Example) { store.deleteExample(e.id); refreshWords() }

    /** All sentences for a word: the video line first, then added examples (sentence, en, fa). */
    fun sentencesOf(w: SavedWord): List<Example> =
        listOf(Example(wordId = w.id, de = w.sentence.replace('\n', ' '), en = "", fa = "")) + (wordExamples[w.id] ?: emptyList())

    // ------------------------------------------------------ practice

    private fun recordProgress() {
        progress.record(); streak = progress.streak; todayCount = progress.todayCount
    }

    fun openPractice() { practiceMode = null; feedback = null; screen = Screen.PRACTICE }

    fun available(mode: PracticeMode): Int = when (mode) {
        PracticeMode.GAPS -> words.count { w -> sentencesOf(w).any { Practice.cloze(w, it.de) != null } }
        PracticeMode.DICTATION -> words.count { it.sentence.isNotBlank() && it.endMs > it.startMs }
        PracticeMode.ARTICLES -> words.count { it.article in setOf("der", "die", "das") }
    }

    fun startPractice(mode: PracticeMode) {
        val rnd = kotlin.random.Random(System.currentTimeMillis())
        // weakest and most overdue words first, then a little randomness
        val pool = words.sortedWith(compareBy<SavedWord> { it.box }.thenBy { it.due }).take(30).shuffled(rnd)
        val qs: List<Question> = when (mode) {
            PracticeMode.GAPS -> pool.mapNotNull { w ->
                val opts = sentencesOf(w).shuffled(rnd)
                opts.firstNotNullOfOrNull { e -> Practice.cloze(w, e.de, e.en.ifEmpty { w.english }, e.fa.ifEmpty { w.persian }) }
                    ?.let { c -> Question.Gap(c, Practice.choices(c.answer, words.map { it.text }, rnd)) }
            }
            PracticeMode.DICTATION -> pool.filter { it.sentence.isNotBlank() }.map { Question.Dictation(it) }
            PracticeMode.ARTICLES -> pool.filter { it.article in setOf("der", "die", "das") }.map { Question.Article(it) }
        }.take(10)
        if (qs.isEmpty()) {
            message = when (mode) {
                PracticeMode.ARTICLES -> "Save some nouns first (their article comes from the dictionary)"
                else -> "Save some words first: pause, tap a word, ★ Save"
            }
            return
        }
        questions = qs; qIndex = 0; feedback = null; practiceScore = 0; practiceMode = mode
        prepareQuestion()
    }

    private fun prepareQuestion() {
        clearAB()
        when (val q = questions.getOrNull(qIndex)) {
            is Question.Dictation -> playClip(q.word)
            else -> player.pause()
        }
    }

    fun answerText(input: String) {
        if (feedback != null) return
        when (val q = questions.getOrNull(qIndex)) {
            is Question.Gap -> {
                val ok = Practice.same(input, q.cloze.answer)
                if (ok) practiceScore++
                feedback = Feedback(ok, if (ok) "Richtig!" else "It was: ${q.cloze.answer}")
                recordProgress()
            }
            is Question.Article -> {
                val ok = input == q.word.article
                if (ok) practiceScore++
                feedback = Feedback(ok, "${q.word.article} ${q.word.lemma}")
                recordProgress()
            }
            is Question.Dictation -> {
                val (marks, score) = Practice.dictation(q.word.sentence.replace('\n', ' '), input)
                val ok = score >= 80
                if (ok) practiceScore++
                feedback = Feedback(ok, "$score% of the words correct", marks)
                recordProgress()
            }
            null -> {}
        }
    }

    fun nextQuestion() {
        feedback = null
        qIndex++
        if (qIndex < questions.size) prepareQuestion() else { clearAB(); player.pause() }
    }

    fun endPractice() { clearAB(); player.pause(); practiceMode = null; feedback = null }

    fun replayDictation() {
        (questions.getOrNull(qIndex) as? Question.Dictation)?.let { playClip(it.word) }
    }

    fun toggleShadowing() {
        shadowing = !shadowing
        if (shadowing) {
            autoPause = false
            if (pointA < 0 || pointB <= pointA) loopLine()
            message = "Shadowing: listen, then repeat aloud in the pause"
        } else { shadowResumeAt = 0; shadowWaiting = false }
    }

    fun toggleAutoPause() {
        autoPause = !autoPause
        if (autoPause) { shadowing = false; clearAB(); message = "Pauses after every line — tap words, then ▶ to go on" }
    }

    // ---------------------------------------------------------- licence

    fun activate(code: String): Boolean {
        val h = Licence.activate(ctx, code)
        if (h != null) { licence = h; showActivation = false; message = "Activated for ${h.name} — thank you!" }
        return h != null
    }

    fun becomeOwner(privateKey: String, name: String): Boolean {
        val h = Licence.becomeOwner(ctx, privateKey, name)
        if (h != null) { licence = h; isOwner = true; showActivation = false; message = "Owner tools unlocked on this phone" }
        return h != null
    }

    fun createActivationCode(device: String, buyer: String): String? {
        val key = Licence.ownerKey(ctx) ?: return null
        val d = device.trim().uppercase()
        if (!Regex("[A-Z2-7]{5}-[A-Z2-7]{5}").matches(d)) { message = "Device code looks wrong (format XXXXX-XXXXX)"; return null }
        if (buyer.isBlank()) { message = "Enter the buyer's name"; return null }
        return Licence.create(key, d, buyer)
    }

    /** Re-checks the trial (e.g. when the app comes back to the foreground). */
    fun recheckTrial() { if (licence == null) trialLeft = Licence.checkTrial(ctx) }

    /** Opens the seller's Telegram chat and copies this phone's device code for pasting. */
    fun contactSeller() {
        val cm = ctx.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
        cm.setPrimaryClip(android.content.ClipData.newPlainText("SubPlayer device code", "SubPlayer device code: $deviceCode"))
        android.widget.Toast.makeText(ctx, "Device code copied — paste it in the Telegram chat", android.widget.Toast.LENGTH_LONG).show()
        val tg = Intent(Intent.ACTION_VIEW, Uri.parse("tg://resolve?domain=${Licence.SELLER_TELEGRAM}")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val web = Intent(Intent.ACTION_VIEW, Uri.parse("https://t.me/${Licence.SELLER_TELEGRAM}")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        try { ctx.startActivity(tg) } catch (_: Exception) {
            try { ctx.startActivity(web) } catch (_: Exception) { message = "Install Telegram, or message @${Licence.SELLER_TELEGRAM} from any device" }
        }
    }

    fun forgetOwnerKey() { Licence.forgetOwnerKey(ctx); isOwner = false; message = "Owner key removed from this phone" }

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
        rememberPosition()
        store.close()
        job?.cancel()
        player.release()
        speaker.shutdown()
        dictionary?.close()
    }
}
