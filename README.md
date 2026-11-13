# SubPlayer — video player with offline German subtitles + A‑B repeat

What it does (nothing more):
1. **Plays videos** (MP4, MKV, WebM, 3GP… anything ExoPlayer supports).
2. **Generates German subtitles** from the video's speech, on the phone, offline.
   The speech model (~45 MB) is downloaded once inside the app — the download link
   is shown in the app before downloading. English is also offered.
3. **A‑B repeat** like VLC: press **A** at the start, **B** at the end; that part loops
   until you press **A‑B off**.

It also auto-reloads subtitles you generated earlier and can load any `.srt` file.

---

## 1. Get the APK — option A: Android Studio (recommended)

1. Install **Android Studio** (free): https://developer.android.com/studio
2. Unzip `SubPlayer.zip` → **File ▸ Open** → choose the `SubPlayer` folder.
3. Wait for "Gradle sync" to finish (first time downloads ~1 GB of tools; needs internet).
   If it asks to install an SDK platform (Android 14 / API 34), click **Install**.
4. Plug in your phone with **USB debugging** on (Settings ▸ About ▸ tap *Build number* 7×,
   then Developer options ▸ USB debugging) and press ▶ **Run** — or
   **Build ▸ Build App Bundle(s)/APK(s) ▸ Build APK(s)** and copy
   `app/build/outputs/apk/debug/app-debug.apk` to the phone and open it
   (allow "Install unknown apps").

## 1. Get the APK — option B: GitHub (no Android Studio)

1. Create a new (private) repository on GitHub and upload the contents of the `SubPlayer` folder
   (including the hidden `.github` folder).
2. Open the **Actions** tab → the *Build APK* run starts automatically (~5 min).
3. When it's green, open the run → **Artifacts ▸ SubPlayer-apk** → download, unzip, install on the phone.

---

## 2. How to use

| Step | Action |
|---|---|
| Open | **Open video** → pick a file (or "Open with ▸ SubPlayer" from a file manager). |
| Subtitles | **Subtitles** → choose **German (Deutsch)**. First time: confirm the model download (link shown). Then it transcribes — progress shows in %. Keep the app open; **Cancel** stops it. |
| Show/hide | Use the **CC** button in the player controls. |
| Saved | Subtitles are saved to `Android/data/com.behrouz.subplayer/files/subtitles/<video>_<id>.de.srt` and load automatically the next time you open the same video. |
| Own .srt | **Load .srt** → pick any subtitle file. |
| Repeat | **A** = loop start, **B** = loop end (it jumps back to A at once), **A‑B off** = stop looping. Press A again to move the start. |

## 3. How the subtitles are made (method)

1. **Audio extraction** — Android's built‑in decoder (MediaCodec) decodes the video's audio track in memory.
2. **Conversion** — all channels are averaged to mono, low‑pass filtered and resampled to **16 000 Hz**
   (what the speech model needs). Checked: 10 s of 48 kHz / 44.1 kHz / 22.05 kHz audio → exactly 160 000 samples,
   so subtitle times do not drift (see `verify/verify_output.txt`).
3. **Speech recognition** — **Vosk** (Kaldi), model `vosk-model-small-de-0.15`, returns each word with start/end time.
4. **Subtitle lines** — words are grouped into a new line when there is a pause > 0.8 s, the line would be > 5 s,
   or > 80 characters (wrapped to 2 rows of ~42). Each line stays 0.3 s after its last word (min 1 s on screen)
   but never overlaps the next line.

**Speed:** on a modern phone roughly 2–5× faster than real time (a 10‑min video ≈ 2–5 min).

**Accuracy notes (small model):** clear speech works well; music, noise or several speakers reduce accuracy.
Output is lower‑case without punctuation (the first letter of each line is capitalised); German nouns stay lower‑case.
Subtitles are in the **spoken** language (German speech → German text); it does not translate.

## 4. Changing / adding a model

Models are listed in `ModelManager.kt` (`MODELS`). Any Vosk model zip from
https://alphacephei.com/vosk/models can be added (url, top folder name, size).
Larger German models are more accurate but very large (1.9 GB+), so the small one is the default.

## 5. Project files

```
SubPlayer/
├─ app/src/main/java/com/behrouz/subplayer/
│  ├─ MainActivity.kt   player, buttons, A‑B repeat, subtitle loading
│  ├─ ModelManager.kt   model list, download (resumable) + unzip
│  ├─ AudioDecoder.kt   video audio → 16 kHz mono PCM
│  ├─ Transcriber.kt    Vosk speech recognition → timed words
│  └─ SrtBuilder.kt     timed words → .srt
├─ app/src/main/res/    layout, theme, icon
├─ app/build.gradle.kts dependencies (Media3 ExoPlayer, Vosk)
├─ .github/workflows/build-apk.yml   optional cloud build
└─ verify/              Python check of the resampling + subtitle-timing maths
```

Requirements: Android 7.0 (API 24) or newer.
