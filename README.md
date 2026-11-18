# SubPlayer — learn German (and English) with your own videos · Android 2.8 + Windows 2.6

**New in Windows 2.6**
- **My Words, newest first:** the list is in the order you saved the words (today's at the top) — with every filter.
- **One entry per word:** saving a word that is already in My Words (from another line or video) no longer makes a second
  entry — the new line is added to its sentences. Words you had saved twice are joined once, on the first start of 2.6
  (the most reviewed copy stays with its progress; the others' sentences move to it; a copy of the word database is kept as
  *words-before-2.6.db* in the data folder).
- **Four panels for a word** (right side of My Words): **Video** (the picture of the moment — click it to play the moment right
  there), **Dictionary** (forms, IPA, English, Persian, meanings with examples), **Sentences** (the video line and every
  added sentence, 🔊 and ✕), **Collocations** (from the teacher, with their examples). Click a panel's title or ⤢ to make
  it big; ✕ brings the four back.
- **The teacher's collocations are kept:** *＋ Add sentences & collocations to my word* saves the example sentences for
  review and practice and the collocations (phrase, meaning, example) in the Collocations panel. Collocations the teacher
  wrote before 2.6 are taken over from its memory for words you have saved.
- **TestDaF / IELTS questions in Review:** the teacher has a fifth tab, *TestDaF questions* (*IELTS* for English): Ollama writes
  exam-style questions on the word (multiple choice, Ja / Nein / Text sagt dazu nichts, gaps, the right collocation) —
  *＋ Add the questions to Review*. Study this video ▸ AI lesson ▸ TestDaF / IELTS now asks the assistant to end with review
  cards (after a line ---REVIEW---); when the answer is pasted, its cards go into Review by themselves. *To Review* does it
  by hand, and for a lesson pasted earlier Ollama turns its questions into cards. In Review, click the answer (or press
  1–4); the right one turns green, then Got it / Again as with words.
- **Review starts with the least reviewed:** words (and questions) you have reviewed least come first; a word you have seen
  many times waits until the end.
- **Pause each line goes on by itself:** it stops at the end of each sentence (a very long one: after each part), shows the whole
  sentence with every word clickable, waits, then plays on. Right-click the button for how long it waits: as long as the
  sentence took (1.5–8 s, the default), 2 / 4 / 6 / 10 s, or until Space. Click a word to stay; Space goes on at once.
  (Before, it could stop again at the same line after Space.)
- **Translations of whole sentences:** the translation line (and *Translate all*) translates the sentence a line belongs to,
  not the piece the subtitle cut it into — the same sentence translation stands under each of its lines. Translations saved
  before are joined per sentence.
- **Download queue:** Discover and links no longer refuse a second download — it waits its turn. *⬇ Downloads* in the status
  bar shows the one running, the ones waiting (move up, download next, remove) and the finished ones (open). A download that
  finishes while you watch doesn't take the screen away.
- **The video keeps playing:** opening My Words, Discover, Study or Practice no longer pauses it — it goes on in a small window
  (play/pause, ±5 s, the current subtitle, ⤢ back to the player, ✕ pauses). The teacher is a normal window now: it can be
  minimised or put beside the video, and the video doesn't stop when it opens.
- Collocations and exam questions stay on this PC (they are not part of the phone sync yet).
- **Portable:** make a folder named **SubPlayer data** next to SubPlayer.exe and SubPlayer keeps everything there (words,
  settings, subtitles, lessons, dictionaries, speech models) instead of in %APPDATA%\SubPlayer — copy your old
  %APPDATA%\SubPlayer into it once, and the whole SubPlayer folder can go on a flash drive or to another PC.
- **windows/pack/SubPlayer-Pack.bat** (put it next to SubPlayer.exe): packs SubPlayer onto a flash drive — for yourself
  (with all your data) or for someone else (program, dictionaries, Whisper and Ollama models only) — and installs it on the
  new PC from there.

**New in Windows 2.5 — a private AI teacher on your own PC (Ollama)**
- **Word card ▸ Teacher** (and *Learn more ▸ Teacher on this PC*) asks a language model that runs on your PC — free, no API
  key, nothing leaves the computer, works offline once the model is downloaded. Four tabs:
  - **Word & collocations:** the meaning *in this line*, forms (article/plural · Präteritum/Perfekt/case), **8 collocations**
    (verb + noun, adjective + noun, noun + preposition, fixed expressions) each with an example, **5 new example sentences at
    your level** (A2–C1) with translations, the preposition/case it takes, synonyms with the difference, an opposite and the
    typical learner mistake. 🔊 reads a sentence aloud. **＋ Add the example sentences to my word** puts them (and the
    collocation examples) into review and practice. Answers are kept, so the same word opens instantly next time.
  - **Explain the line:** translation, sentence structure (verb position, cases, separable verbs, tense), useful expressions
    and three new sentences on the same pattern.
  - **Check my sentence:** write your own sentence with the word — it is corrected with the rule behind the mistake, a score
    and a more natural version; the corrected sentence is added to the word so it comes back in review.
  - **Ask the teacher:** any question about the word, the line or the video (“Is it formal?”, “Give me a dialogue with it”).
  - Explanations in English, فارسی or Deutsch; level and language are remembered.
- **Study this video ▸ AI lesson ▸ Ollama (this PC)** writes the A2–C1 lesson or the TestDaF / IELTS set from the whole
  transcript straight into the box (press again to stop); it is saved with the video like a pasted one.
- **Set-up (Settings ▸ Local AI teacher):** 1. download Ollama from <https://ollama.com/download> and install it (it then runs in
  the system tray), 2. *Check*, 3. *Download suggested model*, 4. use it. The suggestion follows the PC's memory:
  **gemma3:4b** (3.3 GB, 8 GB RAM) · **qwen3:8b** (5.2 GB, 12 GB) · **gemma3:12b** (8.1 GB, 16 GB — best balance) ·
  mistral-small3.2 (15 GB, 32 GB). Embedding/OCR models are ignored; old English-only ones (phi, starling) get a warning.
- The ChatGPT word question now asks for 6 collocations as well.

**New in Windows 2.4 and Android 2.8**
- **TestDaF and IELTS practice from the whole video** (Study this video ▸ AI lesson ▸ *TestDaF* for German videos, *IELTS* for
  English ones). The question holds the whole transcript, the video's B2–C2 words (from the level lists) and your saved
  words. ChatGPT / Gemini / DeepSeek / Grok writes: exam vocabulary from the video **plus topic words likely in future videos
  and exam texts**, listening tasks on the video, a new reading text with exam-style questions (TestDaF: Zuordnung, MC,
  Ja/Nein/Text sagt dazu nichts · IELTS: True/False/Not Given, headings, summary), writing with a chart (invented, marked
  as practice data) and an essay, speaking tasks, and the answers. Kept with the video like the level lessons.
- **Words of the translation line can be learnt:** under an English video with the German translation on, tap/click a German
  word — its German card opens, and Save keeps it with the translated sentence and the video moment (and the other way round).
- **Real German levels for 2,557 words** from the WordFeather list (Goethe/telc-oriented; the version of 6 June 2026, which
  was released under CC0 — later versions are non-commercial and are not used). 1,163 frequency estimates were replaced
  (*Wetter* B1 → A1, *Großeltern* B2 → A1, *Bilanz* C1 → B2). Cards show "A1 (Goethe/telc word list)" or "≈B1 (estimated)".
- **Phone: downloads keep running in the background** — and so do transcribing and "translate all": a notification shows the
  progress while you use another app or the screen is off. A dropped connection continues from where it stopped (up to 12
  times). Not in the Google Play version, which has no downloads.
- Word lists checked but not used: *CEFR Mega Dataset* (no licence — all rights reserved — and its levels are automatic
  estimates), current *WordFeather* (CC BY-NC: no paid apps), *Einlang* and *LingvoBerry* (terms could not be verified).

**Windows 2.3 and Android 2.7.1**

- **"Where else is it used?" finds the right lines.** The dictionary file hangs the helper verbs of the compound tenses
  (*sein, haben, werden, worden, gewesen*), the polite *Sie*, reflexive pronouns and the particles of separable verbs under
  thousands of verbs — so a search for *bringen* also listed every line with *haben* or *worden*. Now only real forms of a
  word count (bringen → bringe, bringst, bringt, brachte, gebracht …), taken from the dictionary; no new download is needed.
  - Separable verbs are found split as well: *mitbringen* → "Bringst du das Buch **mit**?" (but not "bringt *mit dem Auto*").
  - Windows: the list shows each line with the word highlighted, the forms that were found with their counts (click a form to
    see only its lines), and plays the moment on double-click. The title names the base word.
- **Word cards for those words are right again:** tapping *worden* opens *werden*, *gewesen* → *sein*, *haben* → *haben*
  (they used to open an arbitrary verb such as *abbeten*). Word levels use the same rule; 12 of 24,388 German levels changed.
- **Word card (Windows):** a *Formen* list of the word's forms, and a hint when the word you clicked belongs to a separable
  verb in that sentence ("↪ part of mitbringen (bringst … mit)").
- **Gemini and DeepSeek** beside ChatGPT and Grok in *Learn more*.
- **AI lesson of a video** (Study this video ▸ AI lesson): choose **A2, B1, B2 or C1**; the ready question contains the whole
  text of the video and your saved words and asks for a text at that level, 15 key words, 3 structures, exercises
  (gap-fill, matching, rewriting, questions, writing) and the answers. Paste the answer back: it is **kept with the video,
  one lesson per level** (Windows: *Hide answers* to test yourself, *Save as file*; phone: *Share / save*).
- **Themes (Windows):** Settings ▸ Theme & colours — Nebula, Ocean, Aurora, Forest, Sunset, Rose, Graphite, Midnight, or your
  own colour. The window is rebuilt at once; the video stays where it was.
- The dictionary builder (tools/build_dict.py) no longer creates those wrong links for future dictionary versions.


**Android 2.7** (versionCode 11 — the phone gets the features of Windows 2.1 and 2.2)
- **Word levels in colour** (pill *A1–C2* under the video): A1 green · A2 cyan · B1 blue · B2 violet · C1 orange · C2 pink;
  *⋯ Options* colours only words from a chosen level up. Same lists as Windows (English CEFR-J + Octanove; German estimated
  from word frequency). The word card shows the level too.
- **Translation line** (pill *Translation*): each subtitle's translation into Persian, English or German underneath, made as
  the lines come; **Translate all now** (*⋯ Options*) translates the whole video before watching and keeps it (offline).
- **Where else is it used?** (word and phrase cards, Study, My Words): every line of all your subtitled videos with the word
  or its forms; tap a line to watch that moment.
- **Correct subtitles:** *Edit line* and ✎ in the **Transcript** — text, start/end (± 0.1 s, "= now"), delete, add a line;
  *⋯ Options ▸ Subtitle timing* moves all lines (± 0.25 s / 1 s). Saved with the video and synced.
- **Study video:** the video's words by level and count (tap = card, save with its moment), your words from it, and
  practice from its whole text — gaps at your level, dictation of its lines.
- **My Words:** nouns · verbs · adjectives · phrases · other, by video, a **calendar** of the days you saved words, a
  **picture of the video moment**, **export** to CSV (Excel), text or Anki (share or Download/SubPlayer).
- **Discover** (compass icon; not in the Google Play version): German broadcasters (ARD, ZDF, 3sat, Arte, DW, KiKA,
  phoenix, regional) with suggestions by level, search and *only with subtitles*; English — VOA Learning English, NASA
  videos, and podcasts of BBC Learning English, BBC World Service, PBS, TED and NPR (audio → Music/SubPlayer). The
  broadcaster's own subtitles come along. Links of ARD Mediathek, ZDF, 3sat, DW, KiKA, phoenix and NASA pages open too.
  (Streams such as Arte's .m3u8 need the Windows app.)
- **Player:** speed 0.5 – 1.5× in steps, repeat ∞ / 2× / 3× / 5× / 10×, audio files (podcasts) play with a cover,
  **Space** = play/pause and ← → = 5 s on a keyboard.
- Release builds are now started by hand (Actions ▸ Build APK) after `android-check` (every push) and
  `android-emulator` (the app on an Android 14 emulator, screenshots of every new screen) have passed.


**2.6**
- **Google Play version** (`SubPlayer-GooglePlay.aab`, package `com.behrouz.subplayer.play`): yearly subscription with a
  10-day free trial through Google Play Billing (Billing Library 8.3). Same features, minus the Vosk "Fast" engine and
  video-link downloads. No activation codes or Telegram in that version (Play rules). Step-by-step publishing guide,
  listing texts (EN/DE), graphics and form answers are in [`play-store/`](play-store/PLAY-STORE-GUIDE.md).
- **Cafe Bazaar and Myket versions** (`SubPlayer-CafeBazaar.apk`, `SubPlayer-Myket.apk`): 10-day free trial in the app,
  then a yearly subscription paid through the store (Myket's official billing library, which also supports Bazaar).
  Paste the stores' public keys into `store-keys.properties` and the build makes them with payment switched on. Guide,
  Persian listing and toman pricing are in [`iran-stores/`](iran-stores/IRAN-STORES-GUIDE.md).
- **Test copies for your phone** (release `test-copies`): `SubPlayer-TEST-Bazaar.apk`, `-Myket.apk`, `-Play.apk` show up as
  "SubPlayer Bazaar", "SubPlayer Myket" and "SubPlayer Play" and have their own package names (`….test`), so they install
  next to your normal app and next to later store installs. Bazaar/Myket copies run their 10-day trial with everything
  unlocked. The Play copy only shows the Google Play subscription screen, because Google's payment works only for apps
  installed from Google Play. Never upload the test copies to a store.
- All Android versions now target **Android 16 (API 36)**, as Google Play requires, and the speech engine is built for
  **16 KB memory pages**. The build refuses a Play bundle with any library that isn't aligned.
- [Privacy policy](PRIVACY.md) and [terms of use](TERMS.md) (fill in your name, address and e-mail before publishing).


**Windows 2.2**
- **Word levels in colour** (bars button beside the subtitle, K): A1 green · A2 cyan · B1 blue · B2 violet · C1 orange ·
  C2 pink; saved words underlined; right-click to colour only harder words. English: CEFR-J + Octanove C1/C2 lists;
  German: estimated from word frequency (no free official list exists — Goethe's and Oxford's are copyrighted).
- **Where else is this word used?** (word card): every line in all your subtitled videos with the word or its forms
  (gehen → geht, ging, gegangen) — double-click plays that moment.
- **Translate all** (Transcript): the whole subtitle in English or Persian at once, saved — the translation line then
  works offline and switches on/off with its button.
- **Correct subtitles** (pencil beside the subtitle, E, or right-click a transcript line): text, timing, delete, add a
  line; the first version is kept as a backup.
- **Study this video** (Transcript): all its words by level with counts, the words you saved from it, practice with its
  whole text (gaps at your level, dictation of its lines).
- **My Words:** phrases · nouns · verbs · adjectives · others, filter by video, a **calendar** of the days you saved
  words, a **picture of the video moment** for every word, **export** to CSV (Excel), text or Anki.
- **Discover ▸ English:** VOA Learning English (English in a Minute, How to Pronounce, Everyday Grammar, News Words,
  VOA60) and NASA science videos (most with subtitles) — public domain; **podcasts** (audio) the broadcasters offer for
  download: BBC Learning English (6 Minute English / Grammar / Vocabulary), BBC World Service (Global News, Witness
  History, The Documentary, Business Daily), PBS NewsHour, TED Talks Daily, NPR News Now. Audio files play with a cover
  and get subtitles like videos. (BBC's *videos* can't be downloaded — its player doesn't allow it.)
- **Review ▸ Play the moment** now plays the clip inside the review card; videos that were moved are found by their file
  name in Videos, Downloads and folders you opened before.
- **Space** pauses and plays everywhere, even after clicking a button.

**Windows 2.1**
- **Discover** (Ctrl+F): search the free libraries of **ARD, ZDF, 3sat, Arte, DW, KiKA, phoenix** and the regional
  stations, filter by channel, length and **“With subtitles”**, or start with **suggestions by level** (logo!, Die Sendung
  mit der Maus, Checker, tagesschau, Terra X, Quarks, WISO, 3sat science, ARTE — always the newest episodes).
  *Download & open* saves the programme to Videos\SubPlayer (quality: normal / HD / small).
- **The broadcasters' own subtitles** come along (ARD, ZDF, 3sat, KiKA, Arte): no transcription needed — click words at once.
- **Link** now opens pages of the ARD Mediathek, ZDF/ZDFheute, 3sat, Arte, DW, KiKA, phoenix and Tagesschau, and HLS
  streams (.m3u8) — copied into an MP4 without re-encoding, with the normal German sound (not *Klare Sprache*).
- **Player:** clickable **transcript** (T) with search · subtitle **size** and **timing** (G earlier / H later, saved per
  video) · **listening mode** (text hidden while playing) · **translation line** under each subtitle in English or
  Persian (online) · **repeat count** ∞/2×/3×/5× (with Loop line: every line N times, then the next) · speed 0.5–1.5× in
  small steps ([ and ]) · **volume** and mute (M, mouse wheel on the video) · click anywhere on the time bar.
- **Internet connection** (Settings): Windows' proxy settings, your VPN app's local proxy (e.g. v2rayN 127.0.0.1:10809)
  or direct — with *Test connection*. Programmes that only play in Germany need a VPN server in Germany.
- YouTube, Instagram, TikTok, Netflix… stay refused: their terms forbid downloading, and in Germany getting around their
  download protection is not allowed (§ 95a UrhG; OLG Hamburg 2024).

**Windows 2.0**
- **New look:** a living space backdrop (stars, nebula, aurora; pauses by itself while a video plays or in Settings),
  glass panels, a side rail (Player · My Words · Review · Practice · Sync · Settings · Help), crisp line icons, Persian
  shown in the Vazirmatn font, a dark title bar and dark menus everywhere (the white *Recent* list is fixed).
- **Same features as the phone:** **video links** (Tagesschau pages and direct .mp4/.webm, saved to Videos\SubPlayer),
  **Save clip** (A‑B part as MP4, with or without the subtitles drawn in), **shadowing** and **pause after each line**,
  drag & drop of videos and .srt files, an intro tour, the due‑word badge, and the seller's code tools hidden from buyers.

**2.5**
- **English words too:** in English subtitles a tapped word opens the **English dictionary** (English Wiktionary,
  131 124 entries, 19 MB): IPA, English definitions with examples, **German translations** (63 587 words) and Persian
  (11 173 words). *Cambridge* replaces DWDS, and ChatGPT/Grok ask for English sentences with German and Persian.
  English words are saved, reviewed and practised like the German ones (🇬🇧 in My Words).
- **Windows app** with the same learning features (player + A‑B/loop line, offline or online subtitles, word card with both
  dictionaries, My Words, review, practice, activation + 10‑day trial).
- **Sync phone ↔ PC** through one private GitHub gist on your own account: words, added sentences, review progress,
  streak and subtitles. Newest change wins; deletions travel too.


- **Subtitles made on your phone, offline:** Fast (Vosk), Accurate (Whisper Base) or Best (Whisper Small).
  Whisper adds punctuation and correct German capitalisation.
- **Tap any word** in the subtitle → card with article (der/die/das), IPA, German meanings with
  examples, English, Persian, pronunciation (phone voice, slow voice, or real recording) and a DWDS link.
  Inflected forms find their base word (*ging → gehen*, *Häuser → Haus*).
- **Long-press a word, then tap another** → the whole phrase is translated (English + Persian, online),
  with each word's meaning listed. **Double-tap** a word to translate the whole line.
- **Repeat:** A / B like VLC, or **Loop line** to repeat the current subtitle; ⏮ ⏭ jump line by line;
  speed 1× / 0.75× / 0.5×.
- **Save clip:** the A–B part is saved as a new video in *Movies/SubPlayer*, with subtitles burnt in.
- **My Words (★):** save any word or phrase with its meaning, sentence and video moment. Review shows the
  sentence, plays the moment in the video, then reveals the meaning; *Got it* / *Again* schedules the next review
  (1 → 2 → 4 → 7 → 15 → 30 → 60 days, or 10 minutes). Each word shows how many times it was reviewed.
  Optional daily reminder. Saved words glow gold in the subtitles.
- **Video links:** paste a **Tagesschau** video page or a direct **.mp4/.webm** link (or *Share ▸ SubPlayer* from the
  Tagesschau app / browser). The best MP4 is found, downloaded to *Movies/SubPlayer*, opened, ready for subtitles.
  YouTube, Instagram, TikTok and streaming services are not downloaded (their terms forbid it).
- **Online transcription:** quality *Online* uses Whisper large-v3 on Groq (free tier available) or OpenAI's whisper-1 with
  your own API key (Settings ▸ Online transcription). Much faster and more accurate than on the phone; audio is sent in
  16 kHz pieces of at most 10 minutes. Needs internet (a VPN from some countries).
- **Complete sentences:** subtitle lines that split a sentence are joined — saving a word keeps the whole sentence and
  its whole clip; double-tap translates the whole sentence; the word card shows it with *Translate whole sentence*.
- **Learn more:** every word card and saved word has **ChatGPT** and **Grok** (they open with a ready question asking
  for the meaning, forms and **3 Beispielsätze with English and Persian**), **DWDS** and **dict.cc** — installed apps are used when present (ChatGPT/Grok get the question pre-filled,
  dict.cc looks the word up); **Other app…** lists every dictionary or translator on the phone. Copy the answer,
  tap **＋ Add sentences**, and the sentences join the word (lines like `DE: … | EN: … | FA: …` keep their translations).
  Review shows a different sentence each time.
- **Practice (My Words ▸ Practice):** *Fill the gap* (your sentences with the word missing — choose or type),
  *Dictation* (hear the video line, type it, each word marked right/wrong), *der · die · das* for saved nouns.
  Daily 🔥 streak.
- **Listening modes:** *Pause each line* (stops after every subtitle so you can read and tap) and *🎙 Shadowing*
  (plays the line, pauses for you to repeat it aloud, plays it again).
- **Subtitle file:** save the subtitles to *Download/SubPlayer/…srt* or share them (Telegram, e-mail …); load .srt/.vtt.
- **Full screen:** button or just turn the phone sideways; tap = show/hide controls, double-tap left/right = ±5 s.
- **Videos:** folder icon opens another video at any time; the clock icon lists recent videos and resumes them.
- **Free trial:** 10 days with everything unlocked, then an activation code is needed (see *Selling SubPlayer*).

---

## Install

**Phone:** open https://github.com/aftabigbehrouz-hub/SubPlayer/releases/tag/latest in Chrome on the phone,
tap **SubPlayer.apk**, then open it and tap **Install** (it updates 2.4 in place; your words are kept).
Needs Android 7+ on a 64‑bit phone. Whisper needs an ARMv8.2 processor (phones from ~2018 on); older phones get the Fast engine only.

**Windows 10/11 (64‑bit):** open https://github.com/aftabigbehrouz-hub/SubPlayer/releases/tag/windows, download
**SubPlayer-Windows.zip**, right‑click ▸ *Extract All*, open the **SubPlayer** folder and double‑click **SubPlayer.exe**.
Windows SmartScreen may say “Windows protected your PC” (the app is not code‑signed with a paid certificate):
*More info ▸ Run anyway*. Optional check: the SHA‑256 of the zip is in **SubPlayer-Windows.sha256** next to it
(PowerShell: `Get-FileHash SubPlayer-Windows.zip`). For a German voice: Windows Settings ▸ Time & language ▸ Speech ▸
*Add voices* ▸ Deutsch.

## Sync phone ↔ PC (once, 3 minutes)

1. On either device: **Settings ▸ Sync ▸ Get a token ↗** (opens GitHub). Sign in, keep the note “SubPlayer sync”,
   choose an expiry (e.g. *No expiration* or 1 year), make sure **only “gist”** is ticked, **Generate token**, copy it.
2. Paste it in **Settings ▸ Sync** on the phone (*Save token*) and in the Windows app (*Save token*).
3. Done. It syncs when the app starts, ~20 s after each change, when you come back to the app, when the PC app closes,
   and with **Sync now** / **⟳ Sync**. Everything lives in one *secret* gist called “SubPlayer sync (private)”.
- **Videos are not uploaded.** Copy the video file to the other device with the **same file name**: its subtitles then
  load automatically and *Play in video* finds the moment.
- The token can only read/write your gists — nothing else on your account. Revoke it any time on GitHub
  (Settings ▸ Developer settings ▸ Tokens). Each buyer uses their own GitHub account and token.

## First use (each download happens once)

| What | Size | When |
|---|---|---|
| Fast speech model (German) | 45 MB | first time you choose *Fast* |
| Whisper Base | 57 MB | first time you choose *Accurate* |
| Whisper Small | 182 MB | first time you choose *Best* |
| Voice detector (for Whisper) | 1 MB | with the first Whisper model |
| German dictionary | 38 MB (≈130 MB unpacked) | first German word you tap |
| English dictionary | 19 MB (≈60 MB unpacked) | first English word you tap |

**Windows downloads** (also once, from the same release, SHA‑256 checked): German dictionary 38 MB, English dictionary
19 MB, and the speech model you choose — *Fast* Whisper Base ≈148 MB, *Accurate* Whisper Small ≈486 MB,
*Best* Whisper Large‑v3 Turbo ≈1.6 GB (fast with an NVIDIA card, slow on CPU only). *Online* needs no model.

All files come from this repository's **data-v1** release (reachable wherever GitHub is), with the original
site as a fallback. The app checks every file's SHA‑256 fingerprint and refuses a corrupted or altered file.

## Everyday use on Windows

*Open* a video → *Subtitles* → language and quality → *Start* (progress at the bottom, *Cancel* stops).
Pause and **click a word** — the word card is on the right. **Shift+click** first and last word = phrase,
**Ctrl+click** = whole sentence. Keys: Space play/pause, ←/→ 5 s, ↑/↓ previous/next line, **A**/**B** loop, **L** loop line,
Esc stop loop, **S** shadowing, **R** repeat count, **T** transcript, **V** listening mode, Ctrl+T translation line, **G/H** subtitle timing, **[ ]** speed, **M** mute, Ctrl+ +/− subtitle size, F / F11 full screen, Ctrl+O open, **Ctrl+L video link**, **Ctrl+F Discover**, Ctrl+G subtitles, F1 help.
*Link* opens a Tagesschau page or a direct .mp4/.webm link; *Save clip* (after A and B) saves that part as MP4.
*My Words*, *Review* (Space = show meaning, then Got it / Again) and *Practice* are in the side rail.

## Everyday use on the phone

1. **Open video** (folder icon) — or “Open with ▸ SubPlayer” from a file manager.
2. **Subtitles** → choose language and quality → **Start**. Keep the app open while it works; *Cancel* stops it.
   The subtitles are saved and reload automatically next time.
3. **Pause** (tap the picture) → **tap a word**. Long‑press a word and tap the last word of a phrase to translate a phrase.
4. **A** at the start, **B** at the end → it loops. **Loop line** loops the current subtitle. ✕ stops looping.
5. **Save clip** (after A and B) → tick *Burn subtitles* → **Save**.

## What works offline / online

| Feature | Offline | Online extra |
|---|---|---|
| Subtitles (all engines) | ✓ | – |
| Word card: IPA, meanings, examples, English, Persian | ✓ (after dictionary download) | – |
| Pronunciation | ✓ phone voice (install *German* in Settings › Text‑to‑speech if missing) | real recording (Wikimedia) |
| DWDS | – | opens dwds.de |
| Phrase / sentence translation | word‑by‑word meanings | full sentence (Google Translate, fallback MyMemory) |
| Clip export | ✓ | – |
| AI teacher on this PC (Ollama, Windows) | ✓ once Ollama and a model are installed | model download from ollama.com |

**About Persian:** about 4,400 words have a Persian translation written for them in German Wiktionary; about
16,400 more get Persian through their main English meaning (shown as *via English*, with the English word
in brackets so you can judge it). Rare words may have English only.

---

## How it is built (method)

- **Speech → text.** The audio track is decoded on the phone (Android MediaCodec), mixed to mono and resampled to
  16 kHz (a 10 s check gives exactly 160 000 samples, so no timing drift). *Whisper* (OpenAI, run by
  whisper.cpp v1.9.5, compiled from source in this project) transcribes ~4‑minute pieces cut at quiet moments,
  skipping silence with the Silero voice detector; known Whisper “hallucinations” on silence
  (e.g. “Untertitel im Auftrag des ZDF”) and “(Musik)” lines are removed. *Vosk* gives word times that are
  grouped into lines (new line after a 0.8 s pause, 5 s or 80 characters).
- **Subtitle timing.** Each line stays at least 1 s and 0.3 s past its last word, never overlapping the next.
- **Dictionary** (`tools/build_dict.py`, run by GitHub Actions) merges three Wiktionary extracts from kaikki.org:
  German Wiktionary (IPA, meanings, examples, audio, inflected forms, direct English/Persian), English
  Wiktionary's German section (English meanings, *ging → gehen* links) and English Wiktionary's English words
  (Persian translations, matched by part of speech and by the English meaning that fits). Result: 205 606
  entries, 183 924 with IPA, 138 271 with examples, 129 149 with English. The build log tests 32 everyday words.
- **Clip export** uses Media3 Transformer: the clip is cut from A to B and each subtitle is drawn as an image
  on the frames it belongs to.
- **Sync** (`sync/SyncDoc.kt`, `windows/subplayer_win/sync.py`): every word and sentence has a permanent id and a
  last‑changed time; merging keeps the newer copy, a deletion leaves a dated marker that beats older copies (kept 120 days),
  subtitles are matched by video file name, and the streak takes the device that practised on the later day. Both apps
  write the identical JSON; 9 Android and 5 Windows tests check the rules (including two simulated devices syncing
  through one gist: save → review → delete).
- **Windows app** (`windows/`): Python + Qt (PySide6) player; subtitles by faster‑whisper (Whisper on CTranslate2,
  voice detector built in) or online; the same dictionary files, word database layout, review steps and activation
  check as the phone. Built by `.github/workflows/windows.yml` with PyInstaller; the build runs the tests and starts
  the packaged SubPlayer.exe in a self‑test before publishing.
- **Checks on every build:** 54 Android unit tests (+ 58 Windows tests) — exam sets (TestDaF / IELTS, same question in both apps), listed vs. estimated levels; — only real word forms (helper verbs, particles), separable verbs, AI-lesson question and keeping, themes; — broadcaster subtitles (TTML/VTT, 10:00:00 offset), word levels (lowest base word, rare = C2), where-else across videos incl. forms, a video's vocabulary, catalogue and podcast parsing, time fields; — sentence joining across lines, long-line splitting, MP4 discovery on pages; — sentence parsing (AI answers, tables, plain lines), gap creation for
  inflected words, dictation marking, lenient answers (ae/oe/ue, ss); — subtitle reading, writing, grouping, timing, line lookup; activation codes made by
  the PC tool are accepted only on their phone, tampered codes rejected; review scheduling (intervals, Again, counts).

## Selling SubPlayer — 10-day trial + activation codes

**Trial.** A new install works fully for **10 days**. The top bar shows *Free trial · N days left — Buy* (gold, pink in
the last 3 days). One day before the end, and when it ends, the phone gets a notification. After 10 days the app shows
*Your free trial has ended* with a **Message @Bgilone on Telegram** button: it opens your Telegram chat and copies the
buyer's device code so they just paste it. Turning the phone's date back doesn't extend the trial (more than a day back =
trial ended). Reinstalling the app or clearing its data does restart the trial — an offline app can't fully prevent that.

**Windows buyers** work the same way: the PC shows its own device code (from Windows' machine id) on the activation window
and in Settings; create the code with *Owner tools* on your phone or the PC tool below. A PC and a phone are separate
devices (each needs its own code) — you decide whether one purchase includes both.

Every phone shows a **device code** (e.g. `K3QF7-MZ2PA`) on the activation screen. The code you create from it
works **only on that phone**, so a code passed on to someone else is useless.

**Your own phone (once):** on the activation screen tap *I'm the owner*, enter your name and paste the contents of
`SUBPLAYER_LICENCE_PRIVATE_KEY.txt`. The app checks the key against the public key built into it, stores it only on
your phone, and unlocks **Settings (⋮) › Owner tools**.

**For a buyer:** they send you their device code → *Owner tools* → enter the code and their name → *Create code* →
*Share* it to them → they paste it and tap *Activate*.
On a PC instead: `pip install cryptography`, then
`python licence-tool/make_activation_code.py SUBPLAYER_LICENCE_PRIVATE_KEY.txt K3QF7-MZ2PA "Buyer Name"`.

How it works: the activation code is the text `SP1|device|name` signed with your private key (ECDSA P‑256).
The app holds only the public key, so it can check codes but nobody can create them without your key file.
Keep that file private and backed up. A factory reset of the buyer's phone changes its device code (send a new code).

Before selling, note: (1) the activation stops casual sharing, but a determined person could modify an APK;
(2) sentence translation uses Google Translate's free public endpoint, which is not licensed for commercial apps —
switch to a paid translation API before selling widely; (3) the dictionary is Wiktionary data (CC BY-SA 4.0): keep the
attribution shown in the app; Whisper (MIT), whisper.cpp (MIT), Vosk (Apache 2.0) and Media3 (Apache 2.0) allow
commercial use with their notices.

## Security

- Releases are signed with Behrouz's private key (certificate SHA‑256
  `7F:8C:8B:67:6B:35:AA:71:B7:05:F5:B0:72:C5:21:BE:DD:00:FF:B2:0F:68:CE:4A:95:98:38:82:B4:C9:CC:88`), kept only in
  encrypted GitHub secrets. Android refuses any update signed with another key. The build refuses to publish
  without the key or with a different certificate.
- Builds run only for the owner's commits; build tools and whisper.cpp are pinned to exact commits.
- Downloaded models and the dictionary are verified by SHA‑256 before use.
- The installed app never changes by itself.

## Project files

```
app/src/main/java/com/behrouz/subplayer/
  MainActivity.kt        window, file pickers, full screen, activation gate, permissions
  AppViewModel.kt        player, A‑B, selection, saved words, review, recents, licence, tasks
  ui/PlayerScreen.kt     home, main screen, full-screen controls, tappable subtitles
  ui/WordsScreen.kt      My Words list, review flashcards
  ui/Sheets.kt           word card, phrase card, subtitle options, export dialog
  ui/Extras.kt           help guide, intro tour, recent videos, settings/owner tools, activation screen
  ui/Theme.kt            colours, icons, aurora background, glass panels
  words/                 saved words (SQLite), review schedule, recents, daily reminder
  licence/               device code, activation code check/creation
  asr/                   audio decoding, Vosk, Whisper (Kotlin side)
  dict/                  offline dictionary, online translator, pronunciation
  export/ClipExporter.kt A‑B clip with burnt‑in subtitles
  subs/Subtitles.kt      subtitle model, .srt/.vtt reader/writer, timing rules
  data/Downloads.kt      downloads with resume + SHA‑256 check
  sync/                  sync document, merge rules, GitHub gist client
app/src/main/cpp/        whisper.cpp build + JNI bridge
app/src/test/            unit tests
tools/                   German dictionary builder + its test;  tools/en/ English dictionary builder + test
windows/                 Windows app: subplayer_win/ (app.py window, pages.py words/review/practice, dialogs.py,
                         asr.py, dictionary.py, store.py, sync.py, syncer.py, licence.py …), tests/, run.py
licence-tool/            make_activation_code.py (owner's PC tool)
.github/workflows/       build-apk.yml (signed app), data.yml (German dictionary + model mirror), data-en.yml (English
                         dictionary), data-win.yml (Windows speech-model mirror), windows.yml (Windows app)
```

Dictionary data: Wiktionary, CC BY-SA 4.0. Whisper models: MIT. Vosk models: Apache 2.0. faster-whisper / CTranslate2: MIT. Qt for Python (PySide6): LGPL v3 (the Windows app ships Qt as separate DLLs, which the LGPL allows).
