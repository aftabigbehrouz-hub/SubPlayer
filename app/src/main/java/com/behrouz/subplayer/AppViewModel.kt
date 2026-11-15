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
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import com.behrouz.subplayer.asr.OnlineEngine
import com.behrouz.subplayer.asr.VoskEngine
import com.behrouz.subplayer.net.AppLinks
import com.behrouz.subplayer.net.LinkImporter
import com.behrouz.subplayer.asr.WhisperEngine
import com.behrouz.subplayer.data.Assets
import com.behrouz.subplayer.data.Downloader
import com.behrouz.subplayer.dict.Dictionary
import com.behrouz.subplayer.dict.Speaker
import com.behrouz.subplayer.dict.Translator
import com.behrouz.subplayer.export.ClipExporter
import com.behrouz.subplayer.licence.Licence
import com.behrouz.subplayer.learn.Levels
import com.behrouz.subplayer.learn.Library
import com.behrouz.subplayer.net.Catalog
import com.behrouz.subplayer.sync.GistSync
import com.behrouz.subplayer.sync.SSub
import com.behrouz.subplayer.sync.SyncDoc
import com.behrouz.subplayer.sync.SyncMerge
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
    BEST("Best", "Whisper Small · ~182 MB · takes about as long as the video"),
    ONLINE("Online", "Whisper large-v3 · fastest & most accurate · needs internet and an API key")
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
        val saved: Boolean = false,
        val lang: String = "de"
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
        val saved: Boolean = false,
        val lang: String = "de"
    ) : Sheet()

    object Generate : Sheet()
    object Export : Sheet()
    data class AddSentences(val wordId: Long, val title: String, val initial: String) : Sheet()
    object SubFile : Sheet()
    data class Link(val initial: String) : Sheet()
    object Help : Sheet()
    object Settings : Sheet()
    object Videos : Sheet()
    // 2.7
    data class Uses(val word: String, val lang: String, val busy: Boolean = true, val uses: List<com.behrouz.subplayer.learn.Library.Use> = emptyList(),
                    val files: Int = 0, val note: String = "") : Sheet()
    data class EditCue(val index: Int) : Sheet()
    object Transcript : Sheet()
    object PlayerOptions : Sheet()
    data class FilmInfo(val film: com.behrouz.subplayer.net.Catalog.Film) : Sheet()
    object WordsExport : Sheet()
}

enum class Screen { PLAYER, WORDS, REVIEW, PRACTICE, DISCOVER, STUDY }

enum class PracticeMode(val title: String, val explain: String, val fromVideo: Boolean = false) {
    GAPS("Fill the gap", "A sentence with one of your words missing. Choose or type it."),
    DICTATION("Dictation", "Hear the line from the video and type what you hear. Every word is checked."),
    ARTICLES("der · die · das", "Your saved nouns: pick the right article."),
    TEXT_GAPS("Gaps from the video", "Lines of this video with a word of your level missing.", true),
    TEXT_DICTATION("Dictation from the video", "Lines of this video: listen and type.", true)
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
    private val dictionaries = HashMap<String, Dictionary>()

    /** Language of the words being watched: English subtitles use the English dictionary. */
    fun wordLang() = if (cueLang == "en") "en" else "de"

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
    /** A–B / loop line: 0 = repeat until stopped, otherwise play on after this many times. */
    var loopTimes by mutableIntStateOf(0)
    private var loopsDone = 0

    // ---- Google Play subscription (play build) — a no-op in the direct build
    val playStore = com.behrouz.subplayer.store.PlayStore(app)

    // ---- licence (direct build)
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
    var onlineProvider by mutableStateOf(runCatching { OnlineEngine.Provider.valueOf(uiPrefs.getString("online_provider", "GROQ")!!) }
        .getOrDefault(OnlineEngine.Provider.GROQ)); private set
    var onlineKey by mutableStateOf(uiPrefs.getString("online_key_" + onlineProvider.name, "") ?: ""); private set

    init {
        if (!whisperSupported) genEngine = if (VoskEngine.AVAILABLE) Engine.FAST else Engine.ONLINE
        refreshWords()
        recentList = recents.list()
        viewModelScope.launch { delay(1500); if (syncToken.isNotBlank()) syncNow(silent = true) }
        if (licence == null && !com.behrouz.subplayer.BuildConfig.STORE_BILLING) {
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
                    } else if (loopTimes > 0 && ++loopsDone >= loopTimes) {
                        loopsDone = 0; pointA = -1; pointB = -1          // repeated often enough: play on
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

    fun openVideo(uri: Uri, resume: Boolean = true, preferLang: String? = null) {
        rememberPosition()
        videoUri = uri
        videoName = displayName(uri)
        clearAB()
        clearSelection()
        cues = emptyList(); cueInfo = ""
        for (lang in (listOfNotNull(preferLang) + listOf("de", "en")).distinct()) {
            val f = srtFile(uri, lang)
            if (f.exists()) {
                cues = Srt.parse(f.readText()); cueLang = lang
                cueInfo = "Saved ${langName(lang)} subtitles"
                break
            }
        }
        if (cues.isEmpty()) {
            // subtitles made on another device for a video with the same file name
            val key = videoKey(videoName)
            for (lang in listOf("de", "en")) {
                val f = File(syncedSubsDir(), "$key.$lang.srt")
                if (f.exists()) {
                    cues = Srt.parse(f.readText()); cueLang = lang
                    runCatching { srtFile(uri, lang).also { it.parentFile?.mkdirs() }.writeText(f.readText()) }
                    cueInfo = "${langName(lang)} subtitles from your other device"
                    break
                }
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
        changeSpeed(when (speed) { 1f -> 0.75f; 0.75f -> 0.5f; else -> 1f })
    }

    fun changeSpeed(v: Float) { speed = v; player.setPlaybackSpeed(v) }

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

    fun clearAB() { pointA = -1; pointB = -1; shadowResumeAt = 0; shadowWaiting = false; loopsDone = 0 }

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
            val (sent, cs, ce) = sentenceAround(cueIndex)
            if (a == b) openWord(words[a], sent, cs, ce) else openPhrase(words.subList(a, b + 1), sent, cs, ce)
        } else {
            selCue = cueIndex; selStart = wordIndex; selEnd = wordIndex; phraseMode = false
            val (sent, cs, ce) = sentenceAround(cueIndex)
            openWord(words[wordIndex], sent, cs, ce)
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
        val (sent, cs, ce) = sentenceAround(cueIndex)
        openPhrase(tokens(sent), sent, cs, ce)     // the complete sentence, even across lines
    }

    fun clearSelection() { selCue = -1; selStart = -1; selEnd = -1; phraseMode = false }

    fun closeSheet() {
        sheet = null
        clearSelection()
    }

    fun openWord(raw: String, sentence: String, cueStart: Long = -1, cueEnd: Long = -1, lang: String? = null) {
        val word = Dictionary.normalize(raw)
        if (word.isEmpty()) return
        val prev = sheet
        val (cs, ce, sent) = if (cueStart >= 0) Triple(cueStart, cueEnd, sentence) else when (prev) {
            is Sheet.Word -> Triple(prev.cueStart, prev.cueEnd, prev.sentence)
            is Sheet.Phrase -> Triple(prev.cueStart, prev.cueEnd, prev.sentence)
            else -> Triple(-1L, -1L, sentence)
        }
        val l = lang ?: (prev as? Sheet.Word)?.lang?.takeIf { cueStart < 0 } ?: (prev as? Sheet.Phrase)?.lang?.takeIf { cueStart < 0 } ?: wordLang()
        sheet = Sheet.Word(word, sent, cueStart = cs, cueEnd = ce, saved = isSaved(word, cs), lang = l)
        viewModelScope.launch {
            val d = dictionaryOrNull(l)
            var res = if (d == null) emptyList() else withContext(Dispatchers.IO) { runCatching { d.lookup(word) }.getOrDefault(emptyList()) }
            var used = l
            // not found: try the other language's dictionary (e.g. an English word in German subtitles)
            if (res.isEmpty()) {
                val other = if (l == "en") "de" else "en"
                dictionaryOrNull(other)?.let { o ->
                    val r2 = withContext(Dispatchers.IO) { runCatching { o.lookup(word) }.getOrDefault(emptyList()) }
                    if (r2.isNotEmpty()) { res = r2; used = other }
                }
            }
            update<Sheet.Word> {
                if (it.word != word) it
                else if (d == null && res.isEmpty()) it.copy(loading = false, needDictionary = true)
                else it.copy(loading = false, entries = res, lang = used)
            }
        }
    }

    fun translateWordOnline() {
        val s = sheet as? Sheet.Word ?: return
        update<Sheet.Word> { it.copy(onlineBusy = true) }
        viewModelScope.launch {
            val target = if (s.lang == "en") "de" else "en"
            val en = runCatching { Translator.translate(s.word, s.lang, target).text }.getOrElse { "— (${it.message})" }
            val fa = runCatching { Translator.translate(s.word, s.lang, "fa").text }.getOrElse { "—" }
            update<Sheet.Word> { if (it.word == s.word) it.copy(onlineEn = en, onlineFa = fa, onlineBusy = false) else it }
        }
    }

    private fun openPhrase(words: List<String>, sentence: String, cueStart: Long, cueEnd: Long) {
        val text = words.joinToString(" ")
        val clean = words.map { Dictionary.normalize(it) }.filter { it.isNotEmpty() }
        val lang = wordLang()
        sheet = Sheet.Phrase(text, clean, sentence = sentence, cueStart = cueStart, cueEnd = cueEnd,
            saved = isSaved(text, cueStart), lang = lang)
        viewModelScope.launch {
            // word-by-word glosses from the offline dictionary
            dictionaryOrNull(lang)?.let { d ->
                val g = withContext(Dispatchers.IO) {
                    clean.associateWith { w ->
                        runCatching { d.lookup(w).firstOrNull()?.let { e -> e.english.firstOrNull() ?: e.german.firstOrNull()?.let { g -> "DE: $g" } ?: e.senses.firstOrNull()?.de ?: "" } }
                            .getOrNull().orEmpty().take(60)
                    }
                }
                update<Sheet.Phrase> { if (it.text == text) it.copy(glosses = g) else it }
            }
        }
        viewModelScope.launch {
            try {
                // English subtitles → German + Persian; German subtitles → English + Persian
                val en = Translator.translate(text, lang, if (lang == "en") "de" else "en")
                val fa = Translator.translate(text, lang, "fa")
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

    private fun dictAsset(lang: String) = if (lang == "en") Assets.DICT_EN else Assets.DICT_DE

    fun dictionaryReady(lang: String = "de") = Downloader.isReady(ctx, dictAsset(lang))

    fun dictSizeMb(lang: String) = dictAsset(lang).sizeMb

    fun downloadDictionary(lang: String = "de") {
        if (job?.isActive == true) { message = "Please wait for the current task"; return }
        val a = dictAsset(lang)
        job = viewModelScope.launch {
            task = Task("Dictionary", "Downloading ${a.label}…", 0)
            try {
                Downloader.ensure(ctx, a) { p -> ui { task = Task("Dictionary", "Downloading ${a.label}… $p%", p) } }
                message = "${a.label} ready — works offline"
                (sheet as? Sheet.Word)?.let { openWord(it.word, it.sentence, lang = lang) }
            } catch (e: CancellationException) {
                message = "Cancelled"
            } catch (e: Exception) {
                message = "Download failed — " + describe(e)
            } finally {
                task = null
            }
        }
    }

    private suspend fun dictionaryOrNull(lang: String = "de"): Dictionary? {
        dictionaries[lang]?.let { return it }
        if (!dictionaryReady(lang)) return null
        return withContext(Dispatchers.IO) {
            runCatching { Dictionary(Downloader.target(ctx, dictAsset(lang))) }.getOrNull()
        }?.also { dictionaries[lang] = it }
    }

    fun speak(text: String, slow: Boolean = false, lang: String = wordLang()) {
        if (!speaker.speak(text, slow, lang)) {
            message = "No ${if (lang == "en") "English" else "German"} voice installed. Open Android Settings › Text-to-speech and add it."
        }
    }

    fun playRecording(url: String) {
        player.pause()
        speaker.playRecording(url) { err -> ui { message = err } }
    }

    /** DWDS for German words, Cambridge for English ones. */
    fun openDwds(word: String, lang: String = "de") {
        val url = if (lang == "en") "https://dictionary.cambridge.org/dictionary/english/" + Uri.encode(word.lowercase())
        else "https://www.dwds.de/wb/" + Uri.encode(word)
        val i = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        runCatching { ctx.startActivity(i) }.onFailure { message = "No browser found" }
    }

    // ----------------------------------------------------- subtitles

    fun loadSrt(uri: Uri) {
        try {
            val text = ctx.contentResolver.openInputStream(uri)?.use { it.readBytes().toString(Charsets.UTF_8) } ?: ""
            val parsed = com.behrouz.subplayer.subs.Ttml.parseAny(text)
            if (parsed.isEmpty()) { message = "No subtitles found in that file"; return }
            val lang = com.behrouz.subplayer.subs.Ttml.guessLang(parsed)
            cues = parsed; cueLang = lang; cueInfo = "Loaded ${displayName(uri)}"
            // kept with the video, so it is there next time and appears in "where else is this word used"
            videoUri?.let { v -> runCatching { srtFile(v, lang).also { it.parentFile?.mkdirs() }.writeText(Srt.write(parsed)) }; scheduleSync() }
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
                    Engine.ONLINE -> {
                        if (onlineKey.isBlank()) throw IllegalStateException("Add your API key first: Settings › Online transcription")
                        OnlineEngine.transcribe(ctx, uri, onlineProvider, onlineKey, lang) { p, msg ->
                            ui { task = Task(title, "$msg $p%", p) }
                        }
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
                    scheduleSync()
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

    fun refreshWordsAndSync() { refreshWords(); scheduleSync() }

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
                val meaning = if (e != null && e.lang == "en")
                    listOfNotNull(e.senses.firstOrNull()?.de, e.german.take(2).joinToString(", ").takeIf { it.isNotEmpty() }?.let { "DE: $it" }).joinToString("  ·  ")
                    else e?.english?.take(2)?.joinToString("; ")
                SavedWord(
                    lang = e?.lang ?: s.lang,
                    text = s.word, lemma = e?.lemma ?: s.word, article = e?.article ?: "", ipa = e?.ipa ?: "",
                    english = meaning ?: s.onlineEn.orEmpty(),
                    persian = (e?.persian?.takeIf { it.isNotEmpty() } ?: e?.persianViaEnglish)?.take(3)?.joinToString("، ")
                        ?: s.onlineFa.orEmpty(),
                    sentence = s.sentence, videoUri = u.toString(), videoName = videoName,
                    startMs = s.cueStart.coerceAtLeast(0), endMs = maxOf(s.cueEnd, s.cueStart + 2000),
                    created = now, due = now
                )
            }
            is Sheet.Phrase -> SavedWord(
                lang = s.lang,
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
        refreshWordsAndSync()
        when (val s = sheet) {
            is Sheet.Word -> sheet = s.copy(saved = existing == null)
            is Sheet.Phrase -> sheet = s.copy(saved = existing == null)
            else -> {}
        }
    }

    fun isKnownWord(token: String) = key(token) in savedKeys

    fun deleteWord(w: SavedWord) { store.delete(w.id); refreshWordsAndSync() }

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
        refreshWordsAndSync()
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



    // ------------------------------------------------------ sync (private GitHub gist)

    var syncToken by mutableStateOf(uiPrefs.getString("sync_token", "") ?: ""); private set
    var syncStatus by mutableStateOf(uiPrefs.getString("sync_status", "Not set up") ?: "Not set up"); private set
    var syncing by mutableStateOf(false); private set
    private var syncJob: Job? = null
    private var lastSync = 0L

    fun saveSyncToken(t: String) {
        syncToken = t.trim()
        uiPrefs.edit().putString("sync_token", syncToken).remove("gist_id").apply()
        if (syncToken.isNotEmpty()) syncNow() else { syncStatus = "Not set up"; uiPrefs.edit().putString("sync_status", syncStatus).apply() }
    }

    private fun localSubs(): Map<String, SSub> {
        val out = HashMap<String, SSub>()
        val re = Regex("""^(.*)_([0-9a-f]+)\.(de|en|und)\.srt$""")
        fun add(key: String, lang: String, f: File) {
            val k = "$key|$lang"
            if ((out[k]?.updated ?: -1) < f.lastModified()) out[k] = SSub(key, lang, f.readText(), f.lastModified())
        }
        subsDir().listFiles()?.forEach { f -> re.find(f.name)?.let { m -> add(m.groupValues[1], m.groupValues[3], f) } }
        syncedSubsDir().listFiles()?.forEach { f ->
            val n = f.name.removeSuffix(".srt"); val lang = n.substringAfterLast('.'); add(n.substringBeforeLast('.'), lang, f)
        }
        return out
    }

    private fun localDoc(): SyncDoc {
        val (ws, es) = store.exportSync()
        val (st, day, today) = progress.raw
        return SyncDoc(ws.associateBy { it.uid }, es.associateBy { it.uid }, store.tombstones(), localSubs(), st, day, today)
    }

    private fun applySubs(d: SyncDoc) {
        val dir = syncedSubsDir().apply { mkdirs() }
        val local = localSubs()
        for ((k, sub) in d.subs) {
            if ((local[k]?.updated ?: -1) >= sub.updated) continue
            val f = File(dir, "${sub.key}.${sub.lang}.srt")
            f.writeText(sub.srt); f.setLastModified(sub.updated)
        }
    }

    /** Pull → merge → apply → push. Newest change wins; deletions travel too. */
    fun syncNow(silent: Boolean = false) {
        if (syncToken.isBlank()) { if (!silent) message = "Add a GitHub token first (Settings › Sync)"; return }
        if (syncing) return
        syncing = true
        syncStatus = "Syncing…"
        viewModelScope.launch {
            try {
                val n = withContext(Dispatchers.IO) {
                    val g = GistSync(syncToken)
                    var id = uiPrefs.getString("gist_id", null) ?: g.find()
                    val remoteText = if (id != null) g.read(id) else ""
                    val remote = SyncMerge.fromJson(remoteText)
                    val merged = SyncMerge.merge(localDoc(), remote)
                    store.applySync(merged) { name -> recents.list().firstOrNull { it.name.equals(name, ignoreCase = true) }?.uri ?: "" }
                    applySubs(merged)
                    progress.setRaw(merged.streak, merged.lastDay, merged.today)
                    val json = SyncMerge.toJson(merged)
                    if (id == null) id = g.create(json) else if (json != remoteText) g.write(id, json)
                    uiPrefs.edit().putString("gist_id", id).apply()
                    merged.words.size
                }
                refreshWords()
                streak = progress.streak; todayCount = progress.todayCount
                lastSync = System.currentTimeMillis()
                syncStatus = "Synced " + java.text.SimpleDateFormat("d MMM HH:mm", java.util.Locale.US).format(java.util.Date()) + " · $n words"
                if (!silent) message = "Synced ✓ — $n words"
            } catch (e: Exception) {
                syncStatus = "Sync failed: " + (e.message ?: e.javaClass.simpleName)
                if (!silent) message = syncStatus
            } finally {
                syncing = false
                uiPrefs.edit().putString("sync_status", syncStatus).apply()
            }
        }
    }

    /** Sync a little after a change (several quick changes → one sync). */
    fun scheduleSync() {
        if (syncToken.isBlank()) return
        syncJob?.cancel()
        syncJob = viewModelScope.launch { delay(20_000); syncNow(silent = true) }
    }

    fun syncOnResume() {
        if (syncToken.isNotBlank() && System.currentTimeMillis() - lastSync > 120_000) syncNow(silent = true)
    }

    // ------------------------------------------------------ complete sentences

    /** The full sentence around a subtitle line (joined across lines), with its start and end time. */
    fun sentenceAround(cueIndex: Int): Triple<String, Long, Long> {
        val r = CueBuilder.sentenceRange(cues, cueIndex)
        return Triple(CueBuilder.sentenceText(cues, r), cues[r.first].startMs, cues[r.last].endMs)
    }

    /** From a word card: translate the complete sentence it came from. */
    fun openSentenceOfSheet() {
        val s = sheet as? Sheet.Word ?: return
        if (s.sentence.isBlank()) return
        openPhrase(tokens(s.sentence), s.sentence, s.cueStart, s.cueEnd)
    }

    // ------------------------------------------------------ links & sharing

    fun openLinkSheet() {
        val clip = clipboardText().trim()
        sheet = Sheet.Link(if (clip.startsWith("http")) clip else "")
    }

    /** Downloads the video behind a link (Tagesschau page or direct .mp4) and opens it. */
    fun importLink(raw: String) {
        val url = Regex("""https?://\S+""").find(raw)?.value ?: run { message = "No web link found"; return }
        LinkImporter.refusedReason(url)?.let { message = it; return }
        if (job?.isActive == true) { message = "Please wait for the current task"; return }
        sheet = null
        job = viewModelScope.launch {
            task = Task("Video link", "Looking for the video…", -1)
            try {
                val found = LinkImporter.resolve(url)
                downloadFound(found)
            } catch (e: CancellationException) {
                message = "Cancelled"
            } catch (e: Throwable) {
                message = "Link failed — " + describe(e)
            } finally {
                task = null
            }
        }
    }

    private suspend fun downloadFound(found: LinkImporter.Found) {
        if (Regex("""\.m3u8(\?|$)""", RegexOption.IGNORE_CASE).containsMatchIn(found.videoUrl))
            throw java.io.IOException("This programme is offered only as a stream, which the phone app can't save (the Windows app can).")
        task = Task("Downloading", found.title, 0)
        val uri = LinkImporter.download(ctx, found, { }) { p, bytes ->
            ui { task = Task("Downloading", "${found.title} · ${bytes / 1_048_576} MB" + if (p >= 0) " · $p%" else "", p) }
        }
        // the broadcaster's own subtitles (ARD, ZDF, NASA …) come along when it has them
        var got = 0
        if (found.subtitleUrl.isNotEmpty()) {
            task = Task("Subtitles", "Getting the broadcaster's subtitles…", -1)
            LinkImporter.subtitles(found.subtitleUrl)?.let { list ->
                val lang = com.behrouz.subplayer.subs.Ttml.guessLang(list)
                withContext(Dispatchers.IO) { srtFile(uri, lang).also { it.parentFile?.mkdirs() }.writeText(Srt.write(list)) }
                got = list.size
            }
        }
        openVideo(uri, resume = false)
        val where = if (found.audio) "Music/SubPlayer" else "Movies/SubPlayer"
        if (got > 0) { message = "Saved to $where — with the broadcaster's subtitles ($got lines)"; scheduleSync() }
        else { message = "Saved to $where — tap Subtitles to transcribe it"; sheet = Sheet.Generate }
    }

    /** Something was shared to SubPlayer: a video file or text containing a link. */
    fun handleShared(i: Intent) {
        val stream = if (android.os.Build.VERSION.SDK_INT >= 33) i.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
                     else @Suppress("DEPRECATION") i.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
        if (stream != null && ((i.type ?: "").startsWith("video") || (i.type ?: "").startsWith("audio"))) { openVideo(stream); return }
        val text = i.getStringExtra(Intent.EXTRA_TEXT) ?: return
        if (!com.behrouz.subplayer.BuildConfig.PLAY && Regex("""https?://\S+""").containsMatchIn(text)) sheet = Sheet.Link(text)
    }

    // ------------------------------------------------------ online transcription settings

    fun setOnline(provider: OnlineEngine.Provider, key: String) {
        onlineProvider = provider
        onlineKey = key.trim()
        uiPrefs.edit().putString("online_provider", provider.name).putString("online_key_" + provider.name, onlineKey).apply()
    }

    fun switchProvider(p: OnlineEngine.Provider) {
        onlineProvider = p
        onlineKey = uiPrefs.getString("online_key_" + p.name, "") ?: ""
        uiPrefs.edit().putString("online_provider", p.name).apply()
    }

    fun openUrl(url: String) {
        runCatching { ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
            .onFailure { message = "No browser found" }
    }

    // ------------------------------------------------------ learn more

    enum class Source { CHATGPT, GROK, DWDS, DICTCC, CAMBRIDGE, OTHER }

    private fun aiPrompt(word: String, sentence: String, lang: String = wordLang()) = if (lang == "en")
        "Explain the English word “$word”" + (if (sentence.isNotBlank()) " as used in: “${sentence.replace('\n', ' ')}”" else "") + ".\n" +
            "1) Meaning in simple English, plus the German and the Persian translation.\n" +
            "2) IPA (UK and US), word forms, and common collocations.\n" +
            "3) Exactly 3 natural example sentences of everyday English, one per line, in this format:\n" +
            "EN: … | DE: … | FA: …"
    else
        "Explain the German word „$word“" + (if (sentence.isNotBlank()) " as used in: „${sentence.replace('\n', ' ')}“" else "") + ".\n" +
            "1) Meaning in English and in Persian.\n" +
            "2) IPA; for nouns article and plural, for verbs Präteritum and Perfekt.\n" +
            "3) Exactly 3 natural example sentences (Beispielsätze) of everyday German, one per line, in this format:\n" +
            "DE: … | EN: … | FA: …"

    /** Opens ChatGPT / Grok with a ready question, or DWDS / dict.cc for the word. */
    fun learnMore(source: Source, word: String, sentence: String, lang: String = wordLang()) {
        val w = word.trim()
        fun aiPrompt(word: String, sentence: String) = this@AppViewModel.aiPrompt(word, sentence, lang)
        // installed apps first
        when (source) {
            Source.CHATGPT, Source.GROK -> {
                val pkg = if (source == Source.CHATGPT) AppLinks.CHATGPT else AppLinks.GROK
                if (AppLinks.installed(ctx, pkg) && AppLinks.sendText(ctx, pkg, aiPrompt(w, sentence))) {
                    android.widget.Toast.makeText(ctx, "Question placed in the app — tap send. Then copy the 3 sentences back " +
                        "and tap “Add sentences”.", android.widget.Toast.LENGTH_LONG).show()
                    return
                }
            }
            Source.DICTCC -> {
                val pkg = AppLinks.DICTCC.firstOrNull { AppLinks.installed(ctx, it) }
                if (pkg != null && (AppLinks.lookUp(ctx, pkg, w) || AppLinks.sendText(ctx, pkg, w))) return
            }
            Source.OTHER -> {
                if (!AppLinks.lookUp(ctx, null, w)) AppLinks.sendText(ctx, null, w)
                return
            }
            Source.DWDS, Source.CAMBRIDGE -> {}
        }
        val url = when (source) {
            Source.CHATGPT -> "https://chatgpt.com/?q=" + Uri.encode(aiPrompt(w, sentence))
            Source.GROK -> "https://grok.com/?q=" + Uri.encode(aiPrompt(w, sentence))
            Source.DWDS -> "https://www.dwds.de/wb/" + Uri.encode(w)
            Source.DICTCC -> "https://www.dict.cc/?s=" + Uri.encode(w)
            Source.CAMBRIDGE -> "https://dictionary.cambridge.org/dictionary/english/" + Uri.encode(w.lowercase())
            Source.OTHER -> return
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
        val lang = words.firstOrNull { it.id == wordId }?.lang ?: "de"
        val list = Sentences.parse(raw, primary = lang)
        if (list.isEmpty()) { message = "No sentences found. Each line should look like: DE: … | EN: … | FA: …"; return }
        val n = store.addExamples(wordId, list)
        refreshWordsAndSync()
        sheet = null
        message = if (n == 0) "Those sentences are already saved" else "$n sentence${if (n == 1) "" else "s"} added — they'll appear in review and practice"
    }

    fun deleteExample(e: Example) { store.deleteExample(e.id); refreshWordsAndSync() }

    /** All sentences for a word: the video line first, then added examples (sentence, en, fa). */
    fun sentencesOf(w: SavedWord): List<Example> =
        listOf(Example(wordId = w.id, de = w.sentence.replace('\n', ' '), en = "", fa = "")) + (wordExamples[w.id] ?: emptyList())

    // ------------------------------------------------------ practice

    private fun recordProgress() {
        progress.record(); streak = progress.streak; todayCount = progress.todayCount
        scheduleSync()
    }

    fun openPractice() { practiceMode = null; feedback = null; screen = Screen.PRACTICE }

    fun available(mode: PracticeMode): Int = when (mode) {
        PracticeMode.GAPS -> words.count { w -> sentencesOf(w).any { Practice.cloze(w, it.de) != null } }
        PracticeMode.DICTATION -> words.count { it.sentence.isNotBlank() && it.endMs > it.startMs }
        PracticeMode.ARTICLES -> words.count { it.lang == "de" && it.article in setOf("der", "die", "das") }
        PracticeMode.TEXT_GAPS, PracticeMode.TEXT_DICTATION -> 0
    }

    fun startPractice(mode: PracticeMode) {
        if (mode.fromVideo) { startTextPractice(mode); return }
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
            PracticeMode.ARTICLES -> pool.filter { it.lang == "de" && it.article in setOf("der", "die", "das") }.map { Question.Article(it) }
            PracticeMode.TEXT_GAPS, PracticeMode.TEXT_DICTATION -> emptyList()
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

    fun endPractice() {
        val back = practiceMode?.fromVideo == true
        clearAB(); player.pause(); practiceMode = null; feedback = null
        if (back) screen = Screen.STUDY
    }

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

    // ======================================================================= 2.7
    // Word levels, translation line, "where else is this word used", subtitle editing, Discover, study screen,
    // My Words categories / calendar / snapshots / export — the features of the Windows app.

    // ---- word levels (A1…C2 colours in the subtitles)
    val levels = Levels { name -> runCatching { ctx.assets.open(name).bufferedReader(Charsets.UTF_8).use { it.readText() } }.getOrNull() }
    var showLevels by mutableStateOf(uiPrefs.getBoolean("levels", false)); private set
    var minLevel by mutableIntStateOf(uiPrefs.getInt("min_level", 1)); private set
    var wordLevels by mutableStateOf<Map<String, Int>>(emptyMap()); private set
    private var levelJob: Job? = null

    fun toggleLevels() {
        showLevels = !showLevels
        uiPrefs.edit().putBoolean("levels", showLevels).apply()
        if (showLevels) {
            computeLevels()
            message = if (dictionaryReady(wordLang())) "Word levels on: A1 green · A2 cyan · B1 blue · B2 violet · C1 orange · C2 pink"
                      else "Word levels on. Download the ${langName(wordLang())} dictionary for better levels of word forms (ging → gehen)"
        }
    }

    fun chooseMinLevel(l: Int) { minLevel = l.coerceIn(1, 6); uiPrefs.edit().putInt("min_level", minLevel).apply() }

    /** Level 1..6 of a subtitle token, 0 = no colour (names, numbers, below the chosen level, or levels off). */
    fun levelOf(token: String): Int {
        if (!showLevels) return 0
        val lv = wordLevels[Dictionary.normalize(token).lowercase()] ?: 0
        return if (lv >= minLevel) lv else 0
    }

    private fun lemmaFn(d: Dictionary?): ((String) -> List<String>)? = d?.let { dd -> { w: String -> dd.lemmasFor(w) } }

    private fun computeLevels() {
        levelJob?.cancel()
        val list = cues; val lang = wordLang()
        if (list.isEmpty()) { wordLevels = emptyMap(); return }
        levelJob = viewModelScope.launch {
            val d = dictionaryOrNull(lang)
            val map = withContext(Dispatchers.Default) {
                val out = HashMap<String, Int>()
                for (c in list) for (t in tokens(c.text)) {
                    val w = Dictionary.normalize(t); val k = w.lowercase()
                    if (k.isEmpty() || k in out) continue
                    out[k] = levels.level(w, lang, lemmaFn(d))
                }
                out
            }
            wordLevels = map
        }
    }

    // ---- translation line under the subtitles, and the whole file translated before watching
    var showTranslation by mutableStateOf(uiPrefs.getBoolean("tr_line", false)); private set
    var trTarget by mutableStateOf(uiPrefs.getString("tr_target", "fa") ?: "fa"); private set
    var trLines by mutableStateOf<List<String>>(emptyList()); private set
    var trAllDone by mutableStateOf(false); private set
    val liveTr = mutableStateMapOf<Int, String>()
    private val liveAsked = HashSet<Int>()

    fun langLabel(code: String) = when (code) { "fa" -> "فارسی"; "en" -> "English"; else -> "Deutsch" }

    /** The translation language actually used (never the language of the subtitles themselves). */
    fun trLang(): String = if (trTarget == cueLangOrDe()) (if (cueLangOrDe() == "en") "de" else "en") else trTarget

    private fun trFile(): File? {
        val u = videoUri ?: return null
        val f = srtFile(u, cueLangOrDe())
        return File(f.parentFile, f.name.removeSuffix(".srt") + ".tr-${trLang()}.srt")
    }

    fun translationFor(i: Int): String? = trLines.getOrNull(i)?.takeIf { it.isNotBlank() } ?: liveTr[i]

    fun toggleTranslation() {
        showTranslation = !showTranslation
        uiPrefs.edit().putBoolean("tr_line", showTranslation).apply()
        if (showTranslation) {
            loadTranslations()
            if (!trAllDone && cues.isNotEmpty()) message = "Each line is translated as it comes (needs internet). ⋯ Options › Translate all for the whole video at once."
        }
    }

    fun setTranslationTarget(t: String) {
        trTarget = t; uiPrefs.edit().putString("tr_target", t).apply()
        loadTranslations()
    }

    private fun loadTranslations() {
        liveTr.clear(); liveAsked.clear()
        val f = trFile(); val list = cues
        if (f == null || !f.exists() || list.isEmpty()) { trLines = emptyList(); trAllDone = false; return }
        val tr = runCatching { Srt.parse(f.readText()) }.getOrDefault(emptyList())
        trLines = list.map { c -> CueBuilder.indexAt(tr, (c.startMs + c.endMs) / 2).let { k -> if (k >= 0) tr[k].text else "" } }
        trAllDone = trLines.count { it.isNotBlank() } * 10 >= list.size * 9
    }

    private fun writeTranslations(f: File?, list: List<Cue>, lines: List<String>) {
        if (f == null) return
        runCatching {
            f.parentFile?.mkdirs()
            f.writeText(Srt.write(list.mapIndexedNotNull { i, c -> lines.getOrNull(i)?.takeIf { it.isNotBlank() }?.let { Cue(c.startMs, c.endMs, it) } }))
        }
    }

    /** The line on screen is translated on the fly when the whole file isn't translated yet. */
    fun ensureTranslation(i: Int) {
        if (!showTranslation || i !in cues.indices || translationFor(i) != null || !liveAsked.add(i)) return
        val text = cues[i].text.replace('\n', ' '); val from = cueLangOrDe(); val to = trLang()
        viewModelScope.launch {
            runCatching { Translator.translate(text, from, to).text }
                .onSuccess { if (cues.getOrNull(i)?.text?.replace('\n', ' ') == text) liveTr[i] = it }
                .onFailure { liveAsked.remove(i) }
        }
    }

    fun translateAll() {
        if (cues.isEmpty()) { message = "No subtitles to translate yet — tap Subtitles first"; return }
        if (job?.isActive == true) { message = "Please wait for the current task"; return }
        val list = cues; val from = cueLangOrDe(); val to = trLang(); val uri = videoUri; val f = trFile()
        sheet = null
        job = viewModelScope.launch {
            val title = "Translating subtitles → ${langLabel(to)}"
            task = Task(title, "0 / ${list.size} lines", 0)
            try {
                val out = Translator.translateLines(list.map { it.text }, from, to) { n ->
                    ui { task = Task(title, "$n / ${list.size} lines", n * 100 / list.size) }
                }
                withContext(Dispatchers.IO) { writeTranslations(f, list, out) }
                if (videoUri == uri) {
                    loadTranslations()
                    if (!showTranslation) { showTranslation = true; uiPrefs.edit().putBoolean("tr_line", true).apply() }
                }
                message = "${list.size} lines translated — shown under each line, also offline (switch off in ⋯ Options)"
            } catch (e: CancellationException) {
                message = "Cancelled"
            } catch (e: Exception) {
                message = "Translation failed (needs internet) — " + describe(e)
            } finally {
                task = null
            }
        }
    }

    fun deleteTranslation() {
        trFile()?.delete(); loadTranslations(); message = "Saved translation removed"
    }

    // ---- your library: where else is a word used?
    private fun videoMap(): Map<String, Pair<String, String>> {
        val m = HashMap<String, Pair<String, String>>()
        words.forEach { w -> if (w.videoUri.isNotEmpty()) m[videoKey(w.videoName)] = w.videoUri to w.videoName }
        recents.list().forEach { r -> m[videoKey(r.name)] = r.uri to r.name }
        return m
    }

    fun library(): List<Library.Item> = Library.scan(subsDir(), syncedSubsDir(), videoMap())

    private var usesJob: Job? = null

    fun openUses(word: String, lang: String = wordLang()) {
        val w = Dictionary.normalize(word).ifEmpty { word.trim() }
        if (w.isEmpty()) return
        player.pause()
        sheet = Sheet.Uses(w, lang)
        usesJob?.cancel()
        usesJob = viewModelScope.launch {
            val d = if (w.contains(' ')) null else dictionaryOrNull(lang)
            val (uses, n) = withContext(Dispatchers.IO) {
                val forms = if (w.contains(' ')) setOf(w.lowercase()) else d?.formsOf(w) ?: setOf(w.lowercase())
                Library.findUses(w, lang, library(), forms)
            }
            update<Sheet.Uses> {
                if (it.word != w) it else it.copy(busy = false, uses = uses, files = n,
                    note = if (d == null && !w.contains(' ')) "Only this exact form. With the ${langName(lang)} dictionary other forms are found too (geht, ging, gegangen …)." else "")
            }
        }
    }

    fun canOpen(u: Library.Use): Boolean = u.item.uri?.let { canRead(Uri.parse(it)) } ?: false

    fun openUse(u: Library.Use) {
        val uri = u.item.uri?.let { Uri.parse(it) }
        if (uri == null || !canRead(uri)) {
            message = "“${u.item.name}” isn't among your recent videos on this phone — open it once with the folder button, then it plays from here."
            return
        }
        sheet = null
        if (videoUri?.toString() != uri.toString() || cueLang != u.item.lang) openVideo(uri, resume = false, preferLang = u.item.lang)
        screen = Screen.PLAYER
        loopsDone = 0
        pointA = (u.startMs - 200).coerceAtLeast(0); pointB = u.endMs + 300
        player.seekTo(pointA); player.play()
    }

    // ---- editing subtitles (when something was transcribed wrongly)
    private fun applyCues(list: List<Cue>, tr: List<String>) {
        val u = videoUri ?: return
        val f = trFile()
        if (f != null && (f.exists() || tr.any { it.isNotBlank() })) writeTranslations(f, list, tr)
        runCatching { srtFile(u, cueLangOrDe()).also { it.parentFile?.mkdirs() }.writeText(Srt.write(list)) }
            .onFailure { message = "Could not save the subtitles — " + describe(it) }
        clearSelection()
        cues = list
        scheduleSync()
    }

    private fun trCopy() = cues.indices.map { trLines.getOrNull(it) ?: "" }.toMutableList()

    fun saveCue(i: Int, text: String, startMs: Long, endMs: Long) {
        val t = text.lines().map { it.trim() }.filter { it.isNotEmpty() }.joinToString("\n")
        if (i !in cues.indices) return
        if (t.isEmpty()) { deleteCue(i); return }
        if (endMs <= startMs) { message = "The end must be after the start"; return }
        val list = cues.toMutableList(); val tr = trCopy()
        if (list[i].text != t) tr[i] = ""
        list[i] = Cue(startMs.coerceAtLeast(0), endMs, t)
        val order = list.indices.sortedBy { list[it].startMs }
        applyCues(order.map { list[it] }, order.map { tr[it] })
        sheet = null
        message = "Line saved"
    }

    fun deleteCue(i: Int) {
        if (i !in cues.indices) return
        val list = cues.toMutableList(); val tr = trCopy()
        list.removeAt(i); tr.removeAt(i)
        applyCues(list, tr)
        sheet = null
        message = "Line deleted"
    }

    fun insertCueAfter(i: Int) {
        if (i !in cues.indices) return
        val c = cues[i]; val next = cues.getOrNull(i + 1)
        val s = c.endMs + 100; val e = next?.let { minOf(it.startMs - 100, s + 3000) } ?: (s + 2500)
        if (e - s < 300) { message = "No room after this line — shorten it first"; return }
        val list = cues.toMutableList(); val tr = trCopy()
        list.add(i + 1, Cue(s, e, "…")); tr.add(i + 1, "")
        applyCues(list, tr)
        sheet = Sheet.EditCue(i + 1)
    }

    /** Moves every line earlier (negative) or later — for subtitles that don't match the picture. */
    fun shiftAll(deltaMs: Long) {
        if (cues.isEmpty()) return
        applyCues(cues.map { it.copy(startMs = (it.startMs + deltaMs).coerceAtLeast(0), endMs = (it.endMs + deltaMs).coerceAtLeast(100)) }, trCopy())
        message = "All lines ${if (deltaMs > 0) "later" else "earlier"} by %.1f s".format(java.util.Locale.US, kotlin.math.abs(deltaMs) / 1000.0)
    }

    /** The line to edit: the selected one, the one on screen, or the last one before now. */
    fun editCurrentLine() {
        val i = listOf(selCue, currentCue, heldCue).firstOrNull { it in cues.indices } ?: CueBuilder.indexBefore(cues, player.currentPosition)
        if (i !in cues.indices) { message = "No subtitle line here"; return }
        player.pause()
        sheet = Sheet.EditCue(i)
    }

    fun playCue(i: Int) {
        val c = cues.getOrNull(i) ?: return
        loopsDone = 0
        pointA = (c.startMs - 150).coerceAtLeast(0); pointB = c.endMs + 250
        player.seekTo(pointA); player.play()
    }

    // ---- study screen of the video: its words by level, your words from it, practice from its whole text
    var studyWords by mutableStateOf<List<Library.Word>>(emptyList()); private set
    var studyBusy by mutableStateOf(false); private set
    var textMinLevel by mutableIntStateOf(uiPrefs.getInt("text_level", 3))

    fun openStudy() {
        if (cues.isEmpty()) { message = "This video has no subtitles yet — tap Subtitles first"; return }
        player.pause()
        screen = Screen.STUDY
        studyBusy = true
        val list = cues; val lang = wordLang()
        viewModelScope.launch {
            val d = dictionaryOrNull(lang)
            studyWords = withContext(Dispatchers.Default) {
                Library.vocabulary(list, lang).onEach { it.level = levels.level(it.shown, lang, lemmaFn(d)) }
            }
            studyBusy = false
        }
    }

    /** Opens the word card at the first line where the word is said (to save it with its sentence and moment). */
    fun studyWordCard(word: String) {
        val i = Library.firstLine(cues, word)
        if (i < 0) return
        val (sent, cs, ce) = sentenceAround(i)
        selCue = i
        openWord(word, sent, cs, ce)
    }

    fun videoWords(): List<SavedWord> = words.filter { it.videoUri == videoUri?.toString() }

    fun startTextPractice(mode: PracticeMode, minLevel: Int = textMinLevel) {
        val u = videoUri?.toString() ?: return
        if (studyBusy) { message = "One moment — the words of the video are being sorted"; return }
        textMinLevel = minLevel; uiPrefs.edit().putInt("text_level", minLevel).apply()
        val list = cues; val lang = wordLang()
        val rnd = kotlin.random.Random(System.currentTimeMillis())
        val lv = studyWords.associate { it.shown.lowercase() to it.level }
        fun fake(text: String, c: Cue) = SavedWord(id = -1, text = text, lemma = text, sentence = c.text.replace('\n', ' '), videoUri = u,
            videoName = videoName, startMs = c.startMs, endMs = c.endMs, created = 0, due = 0, lang = lang)
        val qs: List<Question> = when (mode) {
            PracticeMode.TEXT_GAPS -> {
                val pool = studyWords.filter { it.level >= minLevel }.map { it.shown }
                list.shuffled(rnd).mapNotNull { c ->
                    val cands = Library.TOKEN.findAll(c.text).map { it.value.trim('\'', '’', '-') }
                        .filter { t -> t.length >= 3 && (lv[t.lowercase()] ?: 0) >= minLevel }.toList()
                    val w = cands.randomOrNull(rnd) ?: return@mapNotNull null
                    val fw = fake(w, c)
                    Practice.cloze(fw, fw.sentence)?.let { cl -> Question.Gap(cl, Practice.choices(cl.answer, pool, rnd)) }
                }.take(10)
            }
            PracticeMode.TEXT_DICTATION -> list.filter { it.text.split(Regex("\\s+")).size in 3..16 }.shuffled(rnd).take(10)
                .map { Question.Dictation(fake(it.text.replace('\n', ' '), it)) }
            else -> emptyList()
        }
        if (qs.isEmpty()) {
            message = if (mode == PracticeMode.TEXT_GAPS) "No ${Levels.NAMES[minLevel]}+ words in this video — choose a lower level" else "No lines to practise"
            return
        }
        questions = qs; qIndex = 0; feedback = null; practiceScore = 0; practiceMode = mode
        screen = Screen.PRACTICE
        prepareQuestion()
    }

    // ---- My Words: categories, calendar, video snapshots, export
    var wordPos by mutableStateOf<Map<Long, String>>(emptyMap()); private set
    /** The words the My Words list shows now (its filters), for Export. */
    var exportList: List<SavedWord> = emptyList()

    /** Phrases · Nouns · Verbs · Adjectives · Other (word type from the dictionary when it is downloaded). */
    fun category(w: SavedWord): String {
        if (w.text.trim().contains(' ')) return "Phrases"
        if (w.article.isNotEmpty()) return "Nouns"
        return when (wordPos[w.id]) {
            "noun", "name" -> "Nouns"
            "verb" -> "Verbs"
            "adj" -> "Adjectives"
            null -> {
                val l = w.lemma.ifEmpty { w.text }
                when {
                    w.lang == "de" && l.firstOrNull()?.isUpperCase() == true -> "Nouns"
                    w.lang == "de" && (l.endsWith("en") || l.endsWith("ern") || l.endsWith("eln")) -> "Verbs"
                    else -> "Other"
                }
            }
            else -> "Other"
        }
    }

    fun loadWordInfo() {
        viewModelScope.launch {
            val out = HashMap(wordPos)
            for (lang in listOf("de", "en")) {
                val d = dictionaryOrNull(lang) ?: continue
                val todo = words.filter { it.lang == lang && it.id !in out && !it.text.contains(' ') }
                if (todo.isEmpty()) continue
                withContext(Dispatchers.IO) {
                    for (w in todo) runCatching { d.lookup(w.lemma.ifEmpty { w.text }).firstOrNull()?.pos }.getOrNull()?.let { out[w.id] = it }
                }
            }
            wordPos = out
        }
    }

    private val snapFails = HashSet<String>()

    /** A small picture of the video at the moment the word is said (made once, kept in the app's folder). */
    suspend fun snapshot(w: SavedWord): File? = withContext(Dispatchers.IO) {
        val f = File(ctx.filesDir, "snaps/${w.uid}.jpg")
        if (f.exists()) return@withContext f
        if (w.videoUri.isEmpty() || synchronized(snapFails) { w.uid in snapFails }) return@withContext null
        val r = android.media.MediaMetadataRetriever()
        try {
            r.setDataSource(ctx, Uri.parse(w.videoUri))
            val t = (w.startMs + w.endMs) / 2 * 1000
            val bmp = (if (android.os.Build.VERSION.SDK_INT >= 27) r.getScaledFrameAtTime(t, android.media.MediaMetadataRetriever.OPTION_CLOSEST_SYNC, 360, 360)
                       else r.getFrameAtTime(t, android.media.MediaMetadataRetriever.OPTION_CLOSEST_SYNC)) ?: throw java.io.IOException("no picture")
            val out = if (bmp.width > 400) android.graphics.Bitmap.createScaledBitmap(bmp, 360, (360L * bmp.height / bmp.width).toInt().coerceAtLeast(1), true) else bmp
            f.parentFile?.mkdirs()
            f.outputStream().use { out.compress(android.graphics.Bitmap.CompressFormat.JPEG, 82, it) }
            f
        } catch (e: Exception) {
            synchronized(snapFails) { snapFails.add(w.uid) }
            null
        } finally {
            runCatching { r.release() }
        }
    }

    private fun csv(v: Any?) = "\"" + v.toString().replace("\"", "\"\"").replace('\n', ' ') + "\""

    /** CSV (Excel), plain text, or Anki (tab-separated, front/back) of the given words. */
    fun wordsExport(format: String, list: List<SavedWord>): Triple<String, String, String> {
        val df = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.US)
        return when (format) {
            "csv" -> Triple("SubPlayer-words.csv", "text/csv", "﻿" + (listOf(listOf("Word", "Base form", "Article", "Type", "Meaning", "Persian",
                "Sentence", "Video", "Time", "Saved on", "Reviews").joinToString(";") { csv(it) }) + list.map { w ->
                listOf(w.text, w.lemma, w.article, category(w), w.english, w.persian, w.sentence, w.videoName,
                    com.behrouz.subplayer.ui.fmt(w.startMs), df.format(java.util.Date(w.created)), w.reviews).joinToString(";") { csv(it) }
            }).joinToString("\r\n") + "\r\n")
            "anki" -> Triple("SubPlayer-anki.txt", "text/plain", "#separator:tab\n#html:false\n" + list.joinToString("\n") { w ->
                val front = ((if (w.article.isNotEmpty()) w.article + " " else "") + w.lemma.ifEmpty { w.text } + " — " + w.sentence).replace('\t', ' ').replace('\n', ' ')
                val back = listOf(w.english, w.persian).filter { it.isNotBlank() }.joinToString(" · ").replace('\t', ' ').replace('\n', ' ')
                "$front\t$back"
            } + "\n")
            else -> Triple("SubPlayer-words.txt", "text/plain", list.joinToString("\n\n") { w ->
                listOfNotNull(
                    (if (w.article.isNotEmpty()) w.article + " " else "") + w.lemma.ifEmpty { w.text } + (if (w.lemma.isNotEmpty() && w.lemma != w.text) "  (${w.text})" else ""),
                    w.english.takeIf { it.isNotBlank() }, w.persian.takeIf { it.isNotBlank() },
                    "„${w.sentence.replace('\n', ' ')}“", "${w.videoName} · ${com.behrouz.subplayer.ui.fmt(w.startMs)} · ${df.format(java.util.Date(w.created))}"
                ).joinToString("\n")
            } + "\n")
        }
    }

    fun shareWords(format: String, list: List<SavedWord>) {
        if (list.isEmpty()) { message = "No words to export"; return }
        val (name, mime, text) = wordsExport(format, list)
        try {
            val dir = File(ctx.cacheDir, "share").apply { mkdirs() }
            val f = File(dir, name); f.writeText(text)
            val uri = androidx.core.content.FileProvider.getUriForFile(ctx, ctx.packageName + ".files", f)
            val send = Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM, uri).putExtra(Intent.EXTRA_SUBJECT, "SubPlayer words")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            ctx.startActivity(Intent.createChooser(send, "Export words").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION))
        } catch (e: Exception) {
            message = "Could not export — " + describe(e)
        }
    }

    fun saveWordsToDownloads(format: String, list: List<SavedWord>) {
        if (list.isEmpty()) { message = "No words to export"; return }
        val (name, mime, text) = wordsExport(format, list)
        message = try { "Saved to " + saveToDownloads(name, mime, text.toByteArray(Charsets.UTF_8)) } catch (e: Exception) { "Could not save — " + describe(e) }
    }

    private fun saveToDownloads(name: String, mime: String, bytes: ByteArray): String =
        if (android.os.Build.VERSION.SDK_INT >= 29) {
            val values = android.content.ContentValues().apply {
                put(android.provider.MediaStore.Downloads.DISPLAY_NAME, name)
                put(android.provider.MediaStore.Downloads.MIME_TYPE, mime)
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

    // ---- Discover: programmes to download (German broadcasters, VOA, NASA, podcasts)
    var discoverLang by mutableStateOf(uiPrefs.getString("discover_lang", "de") ?: "de"); private set
    val shelfFilms = mutableStateMapOf<String, List<Catalog.Film>>()
    val shelfErrors = mutableStateMapOf<String, String>()
    var searchResults by mutableStateOf<List<Catalog.Film>?>(null); private set
    var searchBusy by mutableStateOf(false); private set
    var searchError by mutableStateOf(""); private set
    var discoverQuery by mutableStateOf("")
    var subsOnly by mutableStateOf(false)
    private var searchJob: Job? = null

    fun shelves() = if (discoverLang == "en") Catalog.ENGLISH else Catalog.GERMAN

    fun openDiscover() {
        player.pause()
        screen = Screen.DISCOVER
        loadShelves()
    }

    fun setDiscoverLanguage(l: String) {
        if (l == discoverLang) return
        discoverLang = l; uiPrefs.edit().putString("discover_lang", l).apply()
        searchResults = null; searchError = ""
        loadShelves()
    }

    private fun netError(e: Throwable): String = when (generateSequence(e) { it.cause }.last()) {
        is java.net.UnknownHostException -> "No internet connection"
        is java.net.SocketTimeoutException -> "The site didn't answer in time"
        else -> e.message ?: e.javaClass.simpleName
    }

    fun loadShelves(force: Boolean = false) {
        for (sh in shelves()) {
            if (!force && shelfFilms.containsKey(sh.title)) continue
            shelfErrors.remove(sh.title)
            viewModelScope.launch {
                runCatching { withContext(Dispatchers.IO) { Catalog.shelfFilms(sh, 10) } }
                    .onSuccess { shelfFilms[sh.title] = it }
                    .onFailure { shelfErrors[sh.title] = netError(it) }
            }
        }
    }

    fun searchDiscover() {
        val q = discoverQuery.trim()
        if (q.isEmpty()) { searchResults = null; return }
        searchJob?.cancel()
        searchBusy = true; searchError = ""
        val lang = discoverLang; val subs = subsOnly
        searchJob = viewModelScope.launch {
            try {
                searchResults = withContext(Dispatchers.IO) {
                    if (lang == "en") Catalog.searchEnglish(q, 30) else Catalog.searchGerman(text = q, size = 40, subtitlesOnly = subs).first
                }
            } catch (e: CancellationException) { throw e } catch (e: Exception) {
                searchError = netError(e); searchResults = emptyList()
            } finally { searchBusy = false }
        }
    }

    fun importFilm(f: Catalog.Film) {
        if (job?.isActive == true) { message = "Please wait for the current task"; return }
        sheet = null
        screen = Screen.PLAYER
        job = viewModelScope.launch {
            task = Task("Getting the programme", f.title, -1)
            try {
                val found = if (f.urlVideo.isNotEmpty()) LinkImporter.fromFilm(f) else LinkImporter.resolve(f.urlWebsite)
                downloadFound(found)
            } catch (e: CancellationException) {
                message = "Cancelled"
            } catch (e: Throwable) {
                message = "Download failed — " + describe(e)
            } finally {
                task = null
            }
        }
    }

    // ---- audio files (podcasts) have no picture
    var audioOnly by mutableStateOf(false); private set

    init {
        player.addListener(object : androidx.media3.common.Player.Listener {
            override fun onTracksChanged(tracks: androidx.media3.common.Tracks) {
                audioOnly = !tracks.isEmpty && !tracks.containsType(androidx.media3.common.C.TRACK_TYPE_VIDEO)
            }
        })
        // new subtitles (opened, made, loaded, edited): their saved translation and word levels
        viewModelScope.launch {
            androidx.compose.runtime.snapshotFlow { cues to cueLang }.collect {
                loadTranslations()
                if (showLevels) computeLevels() else wordLevels = emptyMap()
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

    /** Same key on every device for the same video file name (used to sync subtitles). */
    fun videoKey(name: String) = name.substringBeforeLast('.').replace(Regex("[^\\p{L}\\p{N}._-]+"), "_").take(60)

    private fun subsDir() = File(ctx.getExternalFilesDir(null) ?: ctx.filesDir, "subtitles")
    private fun syncedSubsDir() = File(ctx.filesDir, "synced_subs")

    private fun srtFile(uri: Uri, lang: String): File {
        val dir = subsDir()
        val base = videoKey(displayName(uri))
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
        playStore.end()
        job?.cancel()
        player.release()
        speaker.shutdown()
        dictionaries.values.forEach { it.close() }
    }
}
