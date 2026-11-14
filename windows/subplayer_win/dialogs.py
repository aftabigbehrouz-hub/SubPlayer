"""Dialogs: activation, settings (licence, sync, online, models), make subtitles, add sentences, help."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QComboBox, QDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QRadioButton, QScrollArea, QTextBrowser, QVBoxLayout, QWidget)

from . import asr, downloads, licence, practice, sync, theme


def hint(text) -> QLabel:
    l = QLabel(text, objectName="hint", wordWrap=True)
    return l


def section(title) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame(objectName="card")
    v = QVBoxLayout(f)
    t = QLabel(title)
    t.setStyleSheet(f"font-weight:700;font-size:12pt;color:{theme.CYAN}")
    v.addWidget(t)
    return f, v


def ask_language(parent, question) -> str | None:
    item, ok = QInputDialog.getItem(parent, "Language", question, ["German", "English"], 0, False)
    return {"German": "de", "English": "en"}[item] if ok else None


class ActivationDialog(QDialog):
    def __init__(self, main, ended=False):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("SubPlayer — activate")
        self.setMinimumWidth(560)
        v = QVBoxLayout(self)
        t = QLabel("Your free trial has ended" if ended else "Buy / activate SubPlayer", objectName="title")
        v.addWidget(t)
        v.addWidget(hint(f"To keep using SubPlayer, send a message to @{licence.SELLER_TELEGRAM} on Telegram with this PC's "
                         "device code. You receive an activation code made for this PC only."))
        row = QHBoxLayout()
        code = QLabel(main.lic.device)
        code.setStyleSheet(f"font-size:20pt;font-weight:800;color:{theme.GOLD};letter-spacing:2px")
        row.addWidget(code)
        cp = QPushButton("Copy")
        cp.clicked.connect(lambda: QGuiApplication.clipboard().setText(main.lic.device))
        row.addWidget(cp)
        tg = QPushButton(f"Message @{licence.SELLER_TELEGRAM} on Telegram")
        tg.setProperty("accent", True)
        tg.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(f"https://t.me/{licence.SELLER_TELEGRAM}")))
        row.addWidget(tg)
        v.addLayout(row)
        self.field = QPlainTextEdit(placeholderText="Paste the activation code here")
        self.field.setFixedHeight(90)
        v.addWidget(self.field)
        self.err = hint("")
        v.addWidget(self.err)
        b = QPushButton("Activate")
        b.setProperty("accent", True)
        b.clicked.connect(self.activate)
        v.addWidget(b)

    def activate(self):
        name = self.main.lic.activate(self.field.toPlainText())
        if name is None:
            self.err.setText("That code is not valid for this PC (device code " + self.main.lic.device + ").")
            return
        self.main.msg(f"Activated — licensed to {name}. Thank you!")
        self.accept()


class GenerateDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("Make subtitles")
        self.setMinimumWidth(560)
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Make subtitles", objectName="title"))
        v.addWidget(hint("Spoken language"))
        self.lang_box = QComboBox()
        self.lang_box.addItems(["German", "English"])
        self.lang_box.setCurrentIndex(1 if main.settings.get("sub_lang") == "en" else 0)
        v.addWidget(self.lang_box)
        self.radios = {}
        engines = [
            ("base", f"Fast — Whisper Base on this PC ({downloads.FW_BASE.size_mb} MB, once)", "Quick; good for clear speech."),
            ("small", f"Accurate — Whisper Small on this PC ({downloads.FW_SMALL.size_mb} MB, once)", "Recommended. About real time on a normal laptop."),
            ("turbo", f"Best — Whisper Large-v3 Turbo on this PC (≈{downloads.FW_TURBO.size_mb // 100 / 10:g} GB, once)",
             "Most accurate offline. Fast with an NVIDIA graphics card, slow on CPU only."),
            ("online", "Online — Groq / OpenAI (your API key, Settings)", "Fastest and very accurate. Audio is sent to the provider; needs internet."),
        ]
        cur = main.settings.get("engine", "small")
        for key, label, tip in engines:
            r = QRadioButton(label)
            r.setChecked(key == cur)
            self.radios[key] = r
            v.addWidget(r)
            v.addWidget(hint("      " + tip))
        row = QHBoxLayout()
        row.addStretch(1)
        c = QPushButton("Cancel")
        c.clicked.connect(self.reject)
        s = QPushButton("Start")
        s.setProperty("accent", True)
        s.clicked.connect(self.go)
        row.addWidget(c)
        row.addWidget(s)
        v.addLayout(row)

    def go(self):
        self.lang = "en" if self.lang_box.currentIndex() == 1 else "de"
        self.engine = next(k for k, r in self.radios.items() if r.isChecked())
        self.main.settings["engine"] = self.engine
        self.main.save_settings()
        self.accept()


class AddSentencesDialog(QDialog):
    def __init__(self, main, word):
        super().__init__(main)
        self.main, self.word = main, word
        self.setWindowTitle("Add sentences")
        self.setMinimumSize(640, 420)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(f"Add sentences to „{word.text}“", objectName="title"))
        fmt = "EN: … | DE: … | FA: …" if word.lang == "en" else "DE: … | EN: … | FA: …"
        v.addWidget(hint(f"Paste the answer from ChatGPT, Grok, DWDS or dict.cc. Lines like  {fmt}  are read with their "
                         "translations; plain sentences work too. They then appear in review and practice."))
        self.text = QPlainTextEdit()
        self.text.setPlainText(QGuiApplication.clipboard().text()[:4000])
        v.addWidget(self.text, 1)
        self.info = hint("")
        v.addWidget(self.info)
        b = QPushButton("Add")
        b.setProperty("accent", True)
        b.clicked.connect(self.add)
        v.addWidget(b)

    def add(self):
        items = practice.parse_sentences(self.text.toPlainText(), primary=self.word.lang)
        if not items:
            self.info.setText("No sentences found. Each line should look like the format above.")
            return
        n = self.main.store.add_examples(self.word.id, items)
        self.main.after_change()
        self.main.msg("Those sentences are already saved" if n == 0 else f"{n} sentence(s) added — they appear in review and practice")
        self.accept()


class SettingsDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        s = main.settings
        self.setWindowTitle("Settings")
        self.setMinimumSize(640, 720)
        outer = QVBoxLayout(self)
        area = QScrollArea(widgetResizable=True)
        inner = QWidget(objectName="page")
        v = QVBoxLayout(inner)
        area.setWidget(inner)
        outer.addWidget(area)
        v.addWidget(QLabel("Settings", objectName="title"))

        # licence
        f, lv = section("Licence")
        holder = main.lic.holder
        if holder:
            lv.addWidget(hint(f"Licensed to {holder} · device code {main.lic.device}"))
        else:
            left = main.lic.check_trial()
            lv.addWidget(hint(f"Free trial · {left} of {licence.TRIAL_DAYS} days left · device code {main.lic.device}"))
            b = QPushButton("Buy / activate")
            b.setProperty("accent", True)
            b.clicked.connect(lambda: ActivationDialog(main).exec())
            lv.addWidget(b)
        v.addWidget(f)

        # sync
        f, sv = section("Sync (Windows ↔ phone)")
        sv.addWidget(hint("Your words, added sentences, review boxes, streak and subtitles are kept in ONE private gist on your own "
                          "GitHub account. Use the same token here and in the phone app (Settings › Sync). The newest change wins; "
                          "deletions travel too. Videos are not uploaded — keep the same file name on both devices."))
        self.token = QLineEdit(s.get("sync_token", ""), placeholderText="GitHub token (only the 'gist' box ticked)", echoMode=QLineEdit.Password)
        sv.addWidget(self.token)
        row = QHBoxLayout()
        b1 = QPushButton("Save token")
        b1.clicked.connect(self.save_token)
        b2 = QPushButton("Sync now")
        b2.clicked.connect(lambda: main.sync_now())
        b3 = QPushButton("Get a token ↗")
        b3.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(sync.TOKEN_PAGE)))
        for b in (b1, b2, b3):
            row.addWidget(b)
        sv.addLayout(row)
        self.sync_status = hint(s.get("sync_status", "Not set up"))
        sv.addWidget(self.sync_status)
        v.addWidget(f)

        # online transcription
        f, ov = section("Online transcription")
        ov.addWidget(hint("Fastest and most accurate (Whisper large-v3 on the provider's servers). Needs internet and your own API "
                          "key — Groq has a free tier. The audio is sent to the provider; from some countries a VPN is needed."))
        self.prov = QComboBox()
        for p in asr.PROVIDERS.values():
            self.prov.addItem(p.title, p.id)
        self.prov.setCurrentIndex(max(0, self.prov.findData(s.get("online_provider", "GROQ"))))
        self.prov.currentIndexChanged.connect(self._load_key)
        ov.addWidget(self.prov)
        self.key = QLineEdit(echoMode=QLineEdit.Password, placeholderText="API key")
        ov.addWidget(self.key)
        row = QHBoxLayout()
        b = QPushButton("Save key")
        b.clicked.connect(self.save_key)
        k = QPushButton("Get a key ↗")
        k.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(asr.PROVIDERS[self.prov.currentData()].key_page)))
        row.addWidget(b)
        row.addWidget(k)
        ov.addLayout(row)
        self._load_key()
        v.addWidget(f)

        # downloads
        f, dv = section("Downloads")
        for a in (downloads.DICT_DE, downloads.DICT_EN, downloads.FW_BASE, downloads.FW_SMALL, downloads.FW_TURBO):
            r = QHBoxLayout()
            r.addWidget(QLabel(f"{a.label} · {a.size_mb} MB"), 1)
            if downloads.is_ready(a):
                r.addWidget(hint("✓ ready"))
            else:
                b = QPushButton("Download")
                b.clicked.connect(lambda _=False, x=a: (main.download_asset(x), self.accept()))
                r.addWidget(b)
            dv.addLayout(r)
        dv.addWidget(hint("Files are stored in " + str(downloads.root())))
        v.addWidget(f)

        f, av = section("About")
        av.addWidget(hint("SubPlayer for Windows · speech recognition: Whisper (OpenAI) via faster-whisper · dictionaries: German and "
                          "English Wiktionary via kaikki.org (CC BY-SA 4.0) · sentence translation: Google Translate / MyMemory (online)."))
        v.addWidget(f)
        v.addStretch(1)

    def save_token(self):
        t = self.token.text().strip()
        if t != self.main.settings.get("sync_token", ""):
            self.main.settings["sync_token"] = t
            self.main.settings.pop("gist_id", None)
            self.main.save_settings()
        if t:
            self.main.sync_now()
            self.sync_status.setText("Syncing…")
        else:
            self.sync_status.setText("Not set up")

    def _load_key(self):
        self.key.setText(self.main.settings.get("online_key_" + self.prov.currentData(), ""))

    def save_key(self):
        p = self.prov.currentData()
        self.main.settings["online_provider"] = p
        self.main.settings["online_key_" + p] = self.key.text().strip()
        self.main.save_settings()
        self.main.msg("API key saved on this PC")


HELP = [
    ("Open a video", "📂 Open (Ctrl+O), or drag a video onto SubPlayer.exe. 🕘 Recent continues where you stopped."),
    ("Make subtitles", "💬 Subtitles ▸ language ▸ quality. Offline Whisper runs on your PC (the model downloads once); "
                       "Online uses your Groq/OpenAI key and is the fastest. Subtitles are saved and reload next time. "
                       "Already have subtitles? 📄 Subtitle file ▸ Load."),
    ("Click a word", "Pause and click any word in the subtitle: the word card on the right shows article, IPA, meanings with "
                     "examples, English (or German for English words), Persian, the voice (also slow) and a real recording. "
                     "Lines are joined into the complete sentence."),
    ("English videos", "Make English subtitles or load an English .srt: clicking a word opens the English dictionary (19 MB, once): "
                       "IPA, English definitions with examples, German and Persian. Cambridge replaces DWDS."),
    ("Phrases & sentences", "Shift+click the first word, then Shift+click the last word: phrase translation + each word. "
                            "Ctrl+click a word: the whole sentence. Translation needs internet."),
    ("Save & review", "☆ Save keeps the word, meaning, sentence and the exact video moment. 🎓 Review plays the moment; "
                      "Space shows the meaning, then Got it (1, 2, 4, 7, 15, 30, 60 days) or Again (10 minutes)."),
    ("Learn more", "Learn more ▾: ChatGPT and Grok open with a ready question (3 example sentences with translations). Copy the "
                   "answer and use ＋ Add sentences — review then shows a different sentence each time."),
    ("Practice", "🧩 Practice: Fill the gap, Dictation (hear the video line, type it) and der·die·das. Answers count for your 🔥 streak."),
    ("Repeat like VLC", "A = loop start, B = loop end (keys A and B); ✕ or Esc stops. ⟲ Loop line repeats the current subtitle. "
                        "↑/↓ previous/next line, ←/→ 5 seconds, Space play/pause, F full screen, 1× ▸ 0.75× ▸ 0.5× slower."),
    ("Sync with the phone", "Settings ▸ Sync: “Get a token ↗”, sign in to GitHub, create a token with only “gist” ticked, paste it "
                            "here and in the phone app. Syncs on start, a little after each change, when you come back to the "
                            "window, on close and with ⟳ Sync. Keep the same video file names on both devices."),
    ("Voices", "Speaking uses Windows voices. For German: Windows Settings ▸ Time & language ▸ Speech ▸ Add voices ▸ Deutsch."),
    ("Offline & privacy", "Offline subtitles, dictionaries, review and practice work without internet. Your videos never leave your PC."),
]


class HelpDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.setWindowTitle("Help")
        self.setMinimumSize(700, 640)
        v = QVBoxLayout(self)
        t = QTextBrowser()
        t.setHtml("".join(f"<h3 style='color:{theme.CYAN};margin-bottom:2px'>{a}</h3><p style='margin-top:0'>{b}</p>" for a, b in HELP))
        v.addWidget(t)
