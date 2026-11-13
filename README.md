# SubPlayer 2.0 — learn German with your own videos

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
17,000 more get Persian through their main English meaning (shown as *via English*, with the English word
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
- **Checks on every build:** unit tests for subtitle reading, writing, grouping, timing and line lookup.

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
  MainActivity.kt        window, file pickers, full screen
  AppViewModel.kt        player, A‑B, selection, tasks (subtitles, downloads, export)
  ui/PlayerScreen.kt     main screen, tappable subtitles, controls
  ui/Sheets.kt           word card, phrase card, subtitle options, export dialog
  ui/Theme.kt            colours, icons
  asr/                   audio decoding, Vosk, Whisper (Kotlin side)
  dict/                  offline dictionary, online translator, pronunciation
  export/ClipExporter.kt A‑B clip with burnt‑in subtitles
  subs/Subtitles.kt      subtitle model, .srt/.vtt reader/writer, timing rules
  data/Downloads.kt      downloads with resume + SHA‑256 check
app/src/main/cpp/        whisper.cpp build + JNI bridge
app/src/test/            unit tests
tools/                   dictionary builder + its test
.github/workflows/       build-apk.yml (signed app), data.yml (dictionary + model mirror)
```

Dictionary data: Wiktionary, CC BY-SA 4.0. Whisper models: MIT. Vosk models: Apache 2.0.
