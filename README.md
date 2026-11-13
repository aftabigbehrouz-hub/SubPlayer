# SubPlayer 2.4 — learn German with your own videos

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

Open https://github.com/aftabigbehrouz-hub/SubPlayer/releases/tag/latest in Chrome on the phone,
tap **SubPlayer.apk**, then open it and tap **Install**.
Needs Android 7+ on a 64‑bit phone. Whisper needs an ARMv8.2 processor (phones from ~2018 on); older phones get the Fast engine only.

## First use (each download happens once)

| What | Size | When |
|---|---|---|
| Fast speech model (German) | 45 MB | first time you choose *Fast* |
| Whisper Base | 57 MB | first time you choose *Accurate* |
| Whisper Small | 182 MB | first time you choose *Best* |
| Voice detector (for Whisper) | 1 MB | with the first Whisper model |
| German dictionary | 38 MB (≈130 MB unpacked) | first word you tap |

All files come from this repository's **data-v1** release (reachable wherever GitHub is), with the original
site as a fallback. The app checks every file's SHA‑256 fingerprint and refuses a corrupted or altered file.

## Everyday use

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
- **Checks on every build:** 28 unit tests — sentence joining across lines, long-line splitting, MP4 discovery on pages; — sentence parsing (AI answers, tables, plain lines), gap creation for
  inflected words, dictation marking, lenient answers (ae/oe/ue, ss); — subtitle reading, writing, grouping, timing, line lookup; activation codes made by
  the PC tool are accepted only on their phone, tampered codes rejected; review scheduling (intervals, Again, counts).

## Selling SubPlayer — 10-day trial + activation codes

**Trial.** A new install works fully for **10 days**. The top bar shows *Free trial · N days left — Buy* (gold, pink in
the last 3 days). One day before the end, and when it ends, the phone gets a notification. After 10 days the app shows
*Your free trial has ended* with a **Message @Bgilone on Telegram** button: it opens your Telegram chat and copies the
buyer's device code so they just paste it. Turning the phone's date back doesn't extend the trial (more than a day back =
trial ended). Reinstalling the app or clearing its data does restart the trial — an offline app can't fully prevent that.

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
app/src/main/cpp/        whisper.cpp build + JNI bridge
app/src/test/            unit tests
tools/                   dictionary builder + its test
licence-tool/            make_activation_code.py (owner's PC tool)
.github/workflows/       build-apk.yml (signed app), data.yml (dictionary + model mirror)
```

Dictionary data: Wiktionary, CC BY-SA 4.0. Whisper models: MIT. Vosk models: Apache 2.0.
