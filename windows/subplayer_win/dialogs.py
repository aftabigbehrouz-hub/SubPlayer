"""Dialogs: activation, settings, make subtitles, add sentences, video link, save clip, intro tour, owner tools, help."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QRadioButton, QScrollArea, QSpinBox, QTextBrowser, QVBoxLayout,
                               QWidget)

from . import asr, downloads, icons, licence, practice, sync, theme
from .cosmos import GradientLabel, Orb

GITHUB = "https://github.com/aftabigbehrouz-hub/SubPlayer"
PRIVACY = GITHUB + "/blob/main/PRIVACY.md"


def title(text, size=20):
    return GradientLabel(text, size, QFont.Black)


def ibtn(*a, **k):
    from .app import ibtn as _ib
    return _ib(*a, **k)


def hint(text) -> QLabel:
    l = QLabel(text, objectName="hint", wordWrap=True)
    return l


def section(title) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame(objectName="card")
    v = QVBoxLayout(f)
    t = QLabel(title.upper())
    t.setStyleSheet(f"font-weight:700;font-size:9.5pt;letter-spacing:2px;color:{theme.CYAN}")
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
        t = title("Your free trial has ended" if ended else "Buy / activate SubPlayer")
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
        v.addWidget(title("Make subtitles"))
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
        v.addWidget(title(f"Add sentences to „{word.text}“", 17))
        fmt = "EN: … | DE: … | FA: …" if word.lang == "en" else "DE: … | EN: … | FA: …"
        v.addWidget(hint(f"Paste the answer from ChatGPT, Gemini, DeepSeek, Grok, DWDS or dict.cc. Lines like  {fmt}  are read with their "
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
        v.addWidget(title("Settings", 22))

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
        tg = ibtn("send", "Questions, buying a licence", lambda: QDesktopServices.openUrl(QUrl(f"https://t.me/{licence.SELLER_TELEGRAM}")),
                  kind="link", text=f" Contact @{licence.SELLER_TELEGRAM} on Telegram", size=15, color=theme.CYAN)
        lv.addWidget(tg)
        v.addWidget(f)

        # owner tools (seller only — needs the private key)
        owner_key = OwnerDialog.stored_key()
        f, ow = section("Owner tools")
        if owner_key:
            ow.addWidget(hint("Create an activation code for a buyer's PC or phone: enter the device code they send you and their name."))
            self.o_dev = QLineEdit(placeholderText="Buyer's device code (XXXXX-XXXXX)")
            self.o_name = QLineEdit(placeholderText="Buyer's name")
            ow.addWidget(self.o_dev)
            ow.addWidget(self.o_name)
            self.o_out = QPlainTextEdit(readOnly=True)
            self.o_out.setFixedHeight(70)
            self.o_out.hide()
            row = QHBoxLayout()
            mk = QPushButton("Create code")
            mk.setProperty("accent", True)
            mk.clicked.connect(lambda: self.make_code(owner_key))
            cp = QPushButton("Copy")
            cp.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.o_out.toPlainText()))
            rm = ibtn("trash", "Remove the owner key from this PC", lambda: (OwnerDialog.forget(), main.msg("Owner key removed from this PC"), self.accept()),
                      kind="", text=" Remove key", size=15, color=theme.MAGENTA)
            for x in (mk, cp, rm):
                row.addWidget(x)
            ow.addWidget(self.o_out)
            ow.addLayout(row)
            v.addWidget(f)
        else:   # buyers never see the seller's tools — only a small link at the very bottom
            f.deleteLater()

        # reminder & look
        f, rv = section("Daily reminder & look")
        rrow = QHBoxLayout()
        self.rem = QCheckBox("Remind me to review at")
        self.rem.setChecked(bool(s.get("reminder_on")))
        self.rem_h = QComboBox()
        self.rem_h.addItems([f"{h:02d}:00" for h in range(24)])
        self.rem_h.setCurrentIndex(int(s.get("reminder_hour", 19)) % 24)
        self.rem_h.setMinimumWidth(110)
        rrow.addWidget(self.rem)
        rrow.addWidget(self.rem_h)
        rrow.addStretch(1)
        rs = QPushButton("Save")
        rs.clicked.connect(self.save_reminder)
        rrow.addWidget(rs)
        rv.addLayout(rrow)
        rv.addWidget(hint("A Windows notification at that hour when words are due — even when SubPlayer is closed."))
        self.motion = QCheckBox("Animated space background (pauses by itself while a video plays)")
        self.motion.setChecked(s.get("motion", True))
        self.motion.toggled.connect(self.set_motion)
        rv.addWidget(self.motion)
        v.addWidget(f)

        # themes & colours
        f, tv = section("Theme & colours")
        tv.addWidget(hint("Choose the look of the whole program. The colours of the word levels (A1–C2), der / die / das and saved "
                          "words stay the same in every theme."))
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.setSpacing(8)
        cur_key, cur_accent = theme.current()
        self.theme_btns = {}
        for n, (key, (name, a1, a2, a3, *_)) in enumerate(theme.THEMES.items()):
            b = QPushButton("  " + name, checkable=True)
            b.setIcon(_swatch(a1, a2, a3))
            b.setIconSize(QSize(46, 18))
            b.setChecked(key == cur_key and not cur_accent)
            b.setStyleSheet("text-align:left; padding:8px 12px")
            b.clicked.connect(lambda _=False, k=key: self.set_theme(k, ""))
            self.theme_btns[key] = b
            grid.addWidget(b, n // 2, n % 2)
        tv.addLayout(grid)
        crow = QHBoxLayout()
        self.accent_b = ibtn("palette", "Pick any colour: buttons, links and highlights take it and its two neighbours on the colour wheel",
                             self.pick_accent, kind="", text=" My own colour…", size=16)
        if cur_accent:
            self.accent_b.setIcon(_swatch(*theme.accents_from(cur_accent)))
            self.accent_b.setIconSize(QSize(46, 18))
            self.accent_b.setText("  My own colour (in use) — change…")
        crow.addWidget(self.accent_b)
        crow.addStretch(1)
        tv.addLayout(crow)
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

        # internet connection (proxy / VPN)
        f, nv = section("Internet connection")
        nv.addWidget(hint("Where internet access is filtered (for example in Iran), run your VPN app and let SubPlayer use it. "
                          "Programmes that only play in Germany need a VPN server in Germany."))
        self.net_mode = QComboBox()
        for key, label in (("system", "Automatic — Windows' proxy settings (most VPN apps set these)"),
                           ("proxy", "Use this proxy — e.g. the local port of v2rayN, Hiddify or Psiphon"),
                           ("direct", "Direct — no proxy")):
            self.net_mode.addItem(label, key)
        self.net_mode.setCurrentIndex(max(0, self.net_mode.findData(s.get("net_mode", "system"))))
        nv.addWidget(self.net_mode)
        prow = QHBoxLayout()
        self.net_kind = QComboBox()
        self.net_kind.addItem("HTTP", "http")
        self.net_kind.addItem("SOCKS5", "socks5")
        self.net_kind.setCurrentIndex(max(0, self.net_kind.findData(s.get("net_kind", "http"))))
        self.net_proxy = QLineEdit(s.get("net_proxy", ""), placeholderText="127.0.0.1:10809")
        prow.addWidget(self.net_kind)
        prow.addWidget(self.net_proxy, 1)
        nv.addLayout(prow)
        nv.addWidget(hint("Typical local ports: v2rayN HTTP 10809 / SOCKS 10808 · Hiddify 12334 · Psiphon: see its settings. "
                          "HTTP is best (video streams need it)."))
        nrow = QHBoxLayout()
        nsave = QPushButton("Save")
        nsave.clicked.connect(self.save_net)
        ntest = QPushButton("Test connection")
        ntest.clicked.connect(self.test_net)
        nrow.addWidget(nsave)
        nrow.addWidget(ntest)
        nrow.addStretch(1)
        nv.addLayout(nrow)
        self.net_status = hint(s.get("net_status", ""))
        nv.addWidget(self.net_status)

        def mode_changed(_=None):
            on = self.net_mode.currentData() == "proxy"
            self.net_kind.setEnabled(on)
            self.net_proxy.setEnabled(on)
        self.net_mode.currentIndexChanged.connect(mode_changed)
        mode_changed()
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
        av.addWidget(hint(f"SubPlayer for Windows {__import__('subplayer_win').VERSION} · speech recognition: Whisper (OpenAI) via "
                          "faster-whisper · dictionaries: German and English Wiktionary via kaikki.org (CC BY-SA 4.0) · pronunciation "
                          "recordings: Wikimedia Commons · sentence translation: Google Translate / MyMemory (online) · Discover: the "
                          "MediathekViewWeb catalogue (MediathekView film list); programmes and their subtitles come straight "
                          "from the broadcasters (ARD, ZDF, 3sat, Arte, DW, KiKA, phoenix…) and remain theirs · English programmes: "
                          "VOA Learning English and NASA (public domain) · word levels: English — CEFR-J Vocabulary Profile 1.5 "
                          "(Tono Laboratory, TUFS) and Octanove Vocabulary Profile C1/C2 (CC BY-SA 4.0); German — estimated from "
                          "FrequencyWords 2018 by Hermit Dave (OpenSubtitles, CC BY-SA 4.0), not an official list · video: FFmpeg "
                          "via PyAV, Qt · Persian font: Vazirmatn (SIL Open Font License)."))
        links = QHBoxLayout()
        for ic, text, url in (("link", " Project page", GITHUB), ("file", " Privacy policy", PRIVACY),
                              ("send", f" @{licence.SELLER_TELEGRAM}", f"https://t.me/{licence.SELLER_TELEGRAM}")):
            links.addWidget(ibtn(ic, url, lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)), kind="link", text=text, size=15, color=theme.CYAN))
        links.addStretch(1)
        av.addLayout(links)
        v.addWidget(f)
        if not owner_key:
            seller = ibtn("key", "For the seller only: create activation codes with the private key",
                          lambda: (OwnerDialog(main).exec(), self.accept()), kind="link", text=" Seller tools", size=13, color=theme.DIM)
            v.addWidget(seller, 0, Qt.AlignRight)
        v.addStretch(1)

    def save_net(self):
        from . import netcfg
        mode = self.net_mode.currentData()
        if mode == "proxy" and not netcfg.valid(self.net_proxy.text()):
            self.net_status.setText("<span style='color:#FF4FD8'>Enter the proxy as address:port, e.g. 127.0.0.1:10809</span>")
            return
        self.main.settings.update(net_mode=mode, net_kind=self.net_kind.currentData(), net_proxy=self.net_proxy.text().strip())
        desc = netcfg.apply(self.main.settings)
        self.main.settings["net_status"] = "Connection: " + desc
        self.main.save_settings()
        self.net_status.setText("Saved — connection: " + desc)

    def test_net(self):
        import threading
        from PySide6.QtCore import QTimer
        self.save_net()
        self.net_status.setText("Testing…")
        box = {}

        def work():
            from . import netcfg
            box["r"] = netcfg.test()
        t = threading.Thread(target=work, daemon=True)
        t.start()

        def poll():
            if t.is_alive():
                QTimer.singleShot(200, poll)
                return
            lines = [f"<span style='color:{'#5BE38F' if ok else '#FF4FD8'}'>{'✓' if ok else '✗'} {name}</span> "
                     f"<span style='color:#9A98B5'>{detail}</span>" for name, ok, detail in box.get("r", [])]
            self.net_status.setText("<br>".join(lines))
        poll()

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

    def make_code(self, key):
        try:
            code = licence.create(key, self.o_dev.text().strip().upper(), self.o_name.text().strip())
        except Exception as e:
            self.o_out.setPlainText("Could not create the code: " + str(e))
        else:
            self.o_out.setPlainText(code)
        self.o_out.show()

    def save_reminder(self):
        from . import reminder
        on, h = self.rem.isChecked(), self.rem_h.currentIndex()
        try:
            msg = reminder.set_reminder(on, h)
        except Exception as e:
            self.main.msg("Reminder: " + str(e), 9000)
            return
        self.main.settings.update(reminder_on=on, reminder_hour=h)
        self.main.save_settings()
        self.main.msg(msg, 8000)

    def set_theme(self, key: str, accent: str):
        m = self.main
        if (key, accent) == theme.current():
            for k, b in self.theme_btns.items():
                b.setChecked(k == key and not accent)
            return
        m.settings["theme"], m.settings["accent"] = key, accent
        m.save_settings()
        self.accept()
        QTimer.singleShot(50, m.restart_ui)              # the window is rebuilt in the new colours; the video stays where it was

    def pick_accent(self):
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QColorDialog
        key, accent = theme.current()
        col = QColorDialog.getColor(QColor(accent or theme.CYAN), self, "Your own colour")
        if col.isValid():
            self.set_theme(key, col.name().upper())

    def set_motion(self, on):
        self.main.settings["motion"] = on
        self.main.save_settings()
        self.main.cosmos.motion = on
        self.main._update_motion()

    def _load_key(self):
        self.key.setText(self.main.settings.get("online_key_" + self.prov.currentData(), ""))

    def save_key(self):
        p = self.prov.currentData()
        self.main.settings["online_provider"] = p
        self.main.settings["online_key_" + p] = self.key.text().strip()
        self.main.save_settings()
        self.main.msg("API key saved on this PC")


HELP = [
    ("Open a video", "Open (Ctrl+O), or drag a video onto the window or onto SubPlayer.exe. Recent and the cards on the welcome "
                     "screen continue where you stopped."),
    ("Discover", "Discover (Ctrl+F): search the free libraries of ARD, ZDF, 3sat, Arte, DW, KiKA, phoenix and the regional "
                 "stations, or start with the suggestions by level (A2 → C1, always the newest episodes). Tick “With subtitles” for "
                 "programmes that bring the broadcaster's own subtitles (CC) — click words straight away, no transcription. "
                 "Download & open saves the programme to Videos\\SubPlayer."),
    ("Video links", "Link (Ctrl+L): paste a page of the ARD Mediathek, ZDF, 3sat, Arte, DW, KiKA, phoenix or Tagesschau, or any "
                    "direct .mp4 / .webm / .m3u8 link. The broadcaster's subtitles come along when it has them. YouTube, Netflix, "
                    "Instagram, TikTok… are refused: their terms don't allow downloading."),
    ("Word levels", "The bars button beside the subtitle (K) colours every word by level: A1 green, A2 cyan, B1 blue, B2 violet, "
                    "C1 orange, C2 pink; saved words are underlined. Right-click it to colour only harder words (e.g. B2+). "
                    "English levels come from the CEFR-J list; German levels are estimated from how common a word is — "
                    "Goethe's and Oxford's own lists are copyrighted."),
    ("Where else?", "On the word card, “Where else is … used in my videos?” lists every line of your subtitled videos with the word "
                    "in any of its forms, taken from the dictionary (bringen → bringt, brachte, gebracht; Haus → Häuser). Separable "
                    "verbs are found split too (mitbringen → “Bringst du das mit?”). Click a form to show only its lines; "
                    "double-click a line to play that moment. The card lists the forms, and tells you when the word you clicked "
                    "belongs to a separable verb in that sentence."),
    ("AI lesson", "Transcript ▸ Study this video ▸ AI lesson: choose A2, B1, B2 or C1 and send the ready question — it contains the "
                  "whole text of the video and your saved words — to ChatGPT, Gemini, DeepSeek or Grok. The assistant writes a text at "
                  "that level, the key words, the structures, exercises (gaps, matching, rewriting, questions, writing) and the "
                  "answers. Copy its answer and press Paste: the lesson is kept with the video, one per level; Hide answers lets you "
                  "test yourself, Save as file makes a text file to print."),
    ("Themes", "Settings ▸ Theme & colours: eight looks (Nebula, Ocean, Aurora, Forest, Sunset, Rose, Graphite, Midnight) or your "
               "own colour. The window is rebuilt at once and your video stays where it was."),
    ("Correct subtitles", "Wrong word in a subtitle? The pencil beside it (E), or right-click a transcript line: fix the text and "
                          "the timing, delete a line or add one. Saved into the video's subtitles; the first version is kept."),
    ("Translate all", "Transcript ▸ Translate all translates every line at once (English or Persian — Aa button) and saves it: "
                      "the translation line then works offline. The translate button beside the subtitle turns it on and off."),
    ("Study a video", "Transcript ▸ Study this video: all its words by level (filter, save with the moment), the words you saved "
                      "from it, and practice with its whole text — gaps at your level and dictation of its lines."),
    ("My Words", "Grouped into phrases, nouns, verbs, adjectives; filter by video; the calendar shows the days you saved words "
                 "(click a day); each word keeps a picture of the video moment; Export makes a CSV (Excel), a text list or an "
                 "Anki file."),
    ("English videos", "Discover ▸ English: VOA Learning English lessons (made for learners) and NASA science videos "
                       "(most with subtitles) — public domain — plus podcasts the broadcasters offer for download: BBC 6 Minute "
                       "English / Grammar / Vocabulary, BBC World Service, PBS NewsHour, TED Talks Daily, NPR. Audio plays with "
                       "a cover; make subtitles and learn as with a video."),
    ("Where are my videos?", "Keep videos anywhere. A saved word remembers its video's place; if you move or rename it, SubPlayer "
                             "looks for the same file name in Videos, Downloads and the folders you opened before (Settings "
                             "doesn't need changing). Downloads from Discover and Link go to Videos\\SubPlayer."),
    ("Only in Germany?", "Some programmes are blocked outside Germany (or Austria/Switzerland) by the broadcaster. From other "
                         "countries use a VPN with a server in Germany: Settings ▸ Internet connection — Automatic works with most "
                         "VPN apps; otherwise enter the VPN app's local proxy port (v2rayN HTTP: 127.0.0.1:10809)."),
    ("Make subtitles", "Subtitles ▸ language ▸ quality. Offline Whisper runs on your PC (the model downloads once); "
                       "Online uses your Groq/OpenAI key and is the fastest. Subtitles are saved and reload next time. "
                       "Already have subtitles? Subtitle file ▸ Load, or drop the .srt on the window."),
    ("Click a word", "Pause and click any word in the subtitle: the word card on the right shows article, IPA, meanings with "
                     "examples, English (or German for English words), Persian, the voice (also slow) and a real recording. "
                     "Lines are joined into the complete sentence."),
    ("English videos", "Make English subtitles or load an English .srt: clicking a word opens the English dictionary (19 MB, once): "
                       "IPA, English definitions with examples, German and Persian. Cambridge replaces DWDS."),
    ("Phrases & sentences", "Shift+click the first word, then Shift+click the last word: phrase translation + each word. "
                            "Ctrl+click a word: the whole sentence. Translation needs internet."),
    ("Save & review", "Save keeps the word, meaning, sentence and the exact video moment. Review plays the moment; "
                      "Space shows the meaning, then Got it (1, 2, 4, 7, 15, 30, 60 days) or Again (10 minutes)."),
    ("Learn more", "Learn more ▾: ChatGPT, Gemini, DeepSeek and Grok open with a ready question (3 example sentences with translations). Copy the "
                   "answer and use ＋ Add sentences — review then shows a different sentence each time."),
    ("Practice", "Practice: Fill the gap, Dictation (hear the video line, type it) and der·die·das. Answers count for your 🔥 streak."),
    ("Repeat like VLC", "A = loop start, B = loop end (keys A and B); × or Esc stops. Loop line (L) repeats the current subtitle. "
                        "∞ / 2× / 3× / 5× (R) sets how often: with Loop line every line plays that often, then the next — "
                        "great for drilling a whole scene. ↑/↓ previous/next line, ←/→ 5 seconds, Space play/pause, F full screen."),
    ("Speed & sound", "The speed button (or [ and ]) goes from 0.5× to 1.5× in small steps. M mutes; the mouse wheel over the "
                      "video changes the volume. Click anywhere on the time bar to jump there."),
    ("Transcript", "Transcript (T, or the list button beside the subtitle): every line of the video; the current one is "
                   "highlighted. Click a line to jump there, double-click to loop it, and search it with the box on top."),
    ("Subtitle tools", "Beside the subtitle: Aa = text size, timing (G earlier, H later — for .srt files that don't match) and the "
                       "translation language; 👁 = listening mode (the text hides while playing and shows when you pause); "
                       "translate = a translation line under each subtitle, in English or Persian (online)."),
    ("Shadowing", "Shadowing (S): the line plays, then SubPlayer pauses about as long as the line so you can say it aloud, then "
                  "plays it again. ↓ goes to the next line. Pause each line stops after every line so you can read and click."),
    ("Save a clip", "Set A and B, then Save clip: the part between them is saved as a new MP4 in Videos\\SubPlayer — "
                    "with the subtitles drawn into the picture, or clean."),
    ("Daily reminder", "Settings ▸ Daily reminder: a Windows notification at your hour when words are due, even when SubPlayer is "
                       "closed (uses Windows' Task Scheduler)."),
    ("Sync with the phone", "Settings ▸ Sync: “Get a token ↗”, sign in to GitHub, create a token with only “gist” ticked, paste it "
                            "here and in the phone app. Syncs on start, a little after each change, when you come back to the "
                            "window, on close and with Sync. Keep the same video file names on both devices."),
    ("Voices", "Speaking uses Windows voices. For German: Windows Settings ▸ Time & language ▸ Speech ▸ Add voices ▸ Deutsch."),
    ("Offline & privacy", "Offline subtitles, dictionaries, review and practice work without internet. Your videos never leave your PC. "
                          "Discover asks the public MediathekViewWeb catalogue for programmes; downloads come straight from the "
                          "broadcasters."),
]


class HelpDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.setWindowTitle("Help")
        self.setMinimumSize(760, 700)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 18, 24, 18)
        top = QHBoxLayout()
        top.addWidget(title("How SubPlayer works", 20))
        top.addStretch(1)
        tour = ibtn("sparkles", "Show the intro tour again", lambda: (self.accept(), main.show_tour()), kind="", text=" Replay the tour", size=16)
        top.addWidget(tour)
        v.addLayout(top)
        t = QTextBrowser()
        t.setHtml("".join(f"<p style='color:{theme.CYAN};font-weight:700;font-size:11.5pt;margin:14px 0 2px 0'>{a}</p>"
                          f"<p style='margin-top:0;line-height:145%;color:{theme.LIGHT}'>{b}</p>" for a, b in HELP))
        v.addWidget(t)


# ==================================================================== new in 2.0
class LinkDialog(QDialog):
    """Paste a web link: broadcaster pages (ARD, ZDF, 3sat, Arte, DW, KiKA, phoenix, Tagesschau) or a direct video / stream."""

    def __init__(self, main):
        super().__init__(main)
        from . import linkimport
        self.url = None
        self.setWindowTitle("Open a video link")
        self.setMinimumWidth(620)
        v = QVBoxLayout(self)
        v.setContentsMargins(26, 20, 26, 20)
        v.addWidget(title("Open a video link"))
        v.addWidget(hint("A page of the ARD Mediathek, ZDF, 3sat, Arte, DW, KiKA, phoenix or Tagesschau — or any direct .mp4 / "
                         ".webm / .m3u8 link. SubPlayer saves the video to Videos\\SubPlayer (so it works offline) and opens it; "
                         "the broadcaster's subtitles come along when it has them."))
        clip = linkimport.first_link(QGuiApplication.clipboard().text()) or ""
        self.field = QLineEdit(clip, placeholderText="https://www.ardmediathek.de/…  ·  zdf.de  ·  arte.tv  ·  dw.com  ·  tagesschau.de")
        self.field.setMinimumHeight(40)
        v.addWidget(self.field)
        self.err = hint("")
        self.err.setStyleSheet(f"color:{theme.MAGENTA}")
        v.addWidget(self.err)
        v.addWidget(QLabel("YouTube, Netflix, Instagram, TikTok and similar are refused: their terms don't allow downloading. "
                           "Can't find a programme's page? Discover (Ctrl+F) searches them all by name.",
                           objectName="small", wordWrap=True))
        row = QHBoxLayout()
        row.addStretch(1)
        c = QPushButton("Cancel")
        c.clicked.connect(self.reject)
        go = ibtn("download", "Download and open", self.go, kind="", text=" Download && open", size=16, color="#FFFFFF")
        go.setProperty("accent", True)
        row.addWidget(c)
        row.addWidget(go)
        v.addLayout(row)
        self.field.returnPressed.connect(self.go)

    def go(self):
        from . import linkimport
        u = linkimport.first_link(self.field.text())
        if not u:
            self.err.setText("That doesn't look like a web link (it should start with https://)")
            return
        why = linkimport.refused_reason(u)
        if why:
            self.err.setText(why)
            return
        self.url = u
        self.accept()


class ExportDialog(QDialog):
    def __init__(self, main, has_subs: bool):
        super().__init__(main)
        from .app import fmt
        self.burn = has_subs
        self.setWindowTitle("Save clip")
        self.setMinimumWidth(560)
        v = QVBoxLayout(self)
        v.setContentsMargins(26, 20, 26, 20)
        v.addWidget(title("Save the A → B clip"))
        v.addWidget(hint(f"{fmt(main.a)} → {fmt(main.b)}  ·  {(main.b - main.a) / 1000:.1f} seconds  ·  saved as MP4 in Videos\\SubPlayer"))
        self.r_burn = QRadioButton("With subtitles drawn into the picture")
        self.r_clean = QRadioButton("Clean video (no subtitles)")
        self.r_burn.setEnabled(has_subs)
        (self.r_burn if has_subs else self.r_clean).setChecked(True)
        v.addWidget(self.r_burn)
        v.addWidget(self.r_clean)
        if not has_subs:
            v.addWidget(QLabel("No subtitles loaded for this video, so the clip is saved clean.", objectName="small"))
        row = QHBoxLayout()
        row.addStretch(1)
        c = QPushButton("Cancel")
        c.clicked.connect(self.reject)
        go = ibtn("scissors", "Save", self.go, kind="", text=" Save clip", size=16, color="#FFFFFF")
        go.setProperty("accent", True)
        row.addWidget(c)
        row.addWidget(go)
        v.addLayout(row)

    def go(self):
        self.burn = self.r_burn.isChecked()
        self.accept()


class OwnerDialog(QDialog):
    """Seller only: paste the private licence key once; it is checked against the key built into SubPlayer."""

    @staticmethod
    def key_file() -> Path:
        from . import paths
        return paths.data_dir() / "owner.key"

    @classmethod
    def stored_key(cls) -> str | None:
        try:
            k = cls.key_file().read_text(encoding="utf-8").strip()
            return k if cls.valid(k) else None
        except Exception:
            return None

    @classmethod
    def forget(cls):
        cls.key_file().unlink(missing_ok=True)

    @staticmethod
    def valid(key: str) -> bool:
        try:
            dev = licence.device_code()
            return licence.verify(licence.create(key, dev, "owner-check"), dev) == "owner-check"
        except Exception:
            return False

    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("Owner tools")
        self.setMinimumWidth(600)
        v = QVBoxLayout(self)
        v.setContentsMargins(26, 20, 26, 20)
        v.addWidget(title("Unlock owner tools"))
        v.addWidget(hint("Paste the contents of SUBPLAYER_LICENCE_PRIVATE_KEY.txt. It is checked against the key built into the app, "
                         "kept only on this PC (never synced) and lets you create activation codes for buyers."))
        self.field = QPlainTextEdit(placeholderText="Private key")
        self.field.setFixedHeight(110)
        v.addWidget(self.field)
        self.err = hint("")
        v.addWidget(self.err)
        b = QPushButton("Unlock")
        b.setProperty("accent", True)
        b.clicked.connect(self.go)
        v.addWidget(b)

    def go(self):
        k = "".join(self.field.toPlainText().split())
        if not self.valid(k):
            self.err.setText("That key doesn't match this app's licence key.")
            return
        self.key_file().write_text(k, encoding="utf-8")
        self.main.msg("Owner tools unlocked on this PC — Settings › Owner tools")
        self.accept()


TOUR = [
    ("film", "Welcome to SubPlayer", "Learn German and English from the videos you already love — films, news, series, your own "
                                    "recordings. Open a file, drop it on the window, or paste a link from ARD, ZDF, Arte or DW."),
    ("compass", "Discover free German TV", "Discover searches ARD, ZDF, 3sat, Arte and DW — news, documentaries, series, kids' "
                                           "shows — with suggestions by level. CC programmes bring real subtitles; one click "
                                           "downloads and opens them."),
    ("captions", "Subtitles in one click", "Subtitles makes them on your PC with Whisper (or online with your key). They're saved "
                                          "and come back next time — and travel to your phone with Sync."),
    ("sparkles", "Tap any word", "Pause and click a word: article, IPA, meanings with examples, English and Persian, the voice and a "
                                 "real recording. Shift+click two words for a phrase, Ctrl+click for the whole sentence."),
    ("repeat", "Loop, shadow, slow down", "A and B loop any part, Loop line repeats a sentence (∞ or 2×/3×/5× per line), "
                                          "Shadowing gives you a pause to say it aloud, the speed goes down to 0.5×. The "
                                          "transcript, listening mode and a translation line help too."),
    ("cards", "Save, review, practise", "Save keeps the word with its exact video moment. Review brings it back at the right time "
                                        "(1, 2, 4, 7, 15, 30, 60 days); Practice has gap-fill, dictation and der·die·das."),
]


class TourDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.setWindowTitle("Welcome")
        self.setFixedSize(640, 560)
        self.k = 0
        v = QVBoxLayout(self)
        v.setContentsMargins(34, 24, 34, 24)
        self.orb = Orb(170)
        v.addWidget(self.orb, 0, Qt.AlignHCenter)
        self.icon = QLabel(alignment=Qt.AlignCenter)
        v.addWidget(self.icon)
        self.head = GradientLabel("", 22, QFont.Black)
        self.head.setAlignment(Qt.AlignHCenter)
        v.addWidget(self.head)
        self.body = QLabel(wordWrap=True, alignment=Qt.AlignHCenter | Qt.AlignTop)
        self.body.setStyleSheet(f"color:{theme.LIGHT};font-size:11.5pt;line-height:150%")
        self.body.setMinimumHeight(96)
        v.addWidget(self.body)
        self.dots = QLabel(alignment=Qt.AlignCenter)
        v.addWidget(self.dots)
        v.addStretch(1)
        row = QHBoxLayout()
        self.skip = QPushButton("Skip")
        self.skip.clicked.connect(self.accept)
        self.back = QPushButton("Back")
        self.back.clicked.connect(lambda: self.step(-1))
        self.next = QPushButton("Next")
        self.next.setProperty("accent", True)
        self.next.clicked.connect(lambda: self.step(1))
        row.addWidget(self.skip)
        row.addStretch(1)
        row.addWidget(self.back)
        row.addWidget(self.next)
        v.addLayout(row)
        self.show_step()

    def step(self, d):
        if self.k + d >= len(TOUR):
            self.accept()
            return
        self.k = max(0, self.k + d)
        self.show_step()

    def show_step(self):
        ic, h, b = TOUR[self.k]
        self.icon.setPixmap(icons.pixmap(ic, theme.CYAN, 30))
        self.head.setText(h)
        self.head.update()
        self.body.setText(b)
        self.dots.setText("  ".join(f"<span style='color:{theme.CYAN if i == self.k else '#3a3660'};font-size:14pt'>●</span>"
                                    for i in range(len(TOUR))))
        self.back.setEnabled(self.k > 0)
        self.next.setText("Let's go" if self.k == len(TOUR) - 1 else "Next")


# ==================================================================== where else is a word used
class UsesDialog(QDialog):
    """Every line in your subtitled videos that uses the word — in any of its forms (bringen: bringt, brachte, gebracht …;
    separable verbs also split: bringt … mit)."""

    def __init__(self, main, word: str, lang: str):
        super().__init__(main)
        import html as _html
        import threading
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QListWidget, QListWidgetItem
        self.main, self.word, self.lang = main, word, lang
        self.setWindowTitle(f"“{word}” in your videos")
        self.resize(860, 660)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 18, 24, 18)
        self.head = title(f"“{word}” in your videos")
        v.addWidget(self.head)
        self.info = hint("Searching your subtitled videos (SubPlayer's subtitles and .srt files next to your videos)…")
        v.addWidget(self.info)
        self.forms = QLabel("")
        self.forms.setWordWrap(True)
        self.forms.setTextFormat(Qt.RichText)
        self.forms.linkActivated.connect(self._pick_form)
        v.addWidget(self.forms)
        self.list = QListWidget()
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.itemDoubleClicked.connect(self.play)
        v.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.only_this = QCheckBox("Only other videos")
        self.only_this.toggled.connect(self._fill)
        row.addWidget(self.only_this)
        row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        self.play_b = ibtn("play", "Play this moment (Enter or double-click)", lambda: self.play(self.list.currentItem()), kind="",
                           text=" Play this moment", size=16, color="#FFFFFF")
        self.play_b.setProperty("accent", True)
        self.play_b.setDefault(True)
        row.addWidget(close)
        row.addWidget(self.play_b)
        v.addLayout(row)
        self.uses, self.files, self.meta, self.form = [], 0, {}, ""
        self._esc = _html.escape
        self._QLI = QListWidgetItem
        box = {}

        def work():
            from . import library, syncer as _syncer
            try:
                items = library.scan(main.settings, _syncer.subs_dir())
                meta = {}
                box["r"] = library.find_uses(word, lang, items, main.dictionary(lang), info=meta)
                box["m"] = meta
            except Exception as e:
                box["e"] = str(e)
        t = threading.Thread(target=work, daemon=True)
        t.start()

        def poll():
            if t.is_alive():
                QTimer.singleShot(150, poll)
                return
            if "e" in box:
                self.info.setText("Search failed: " + box["e"])
                return
            self.uses, self.files = box["r"]
            self.meta = box.get("m") or {}
            base = self.meta.get("base") or word
            self.head.setText(f"“{base}” in your videos")
            self.setWindowTitle(f"“{base}” in your videos")
            self._fill()
        poll()

    def _pick_form(self, f: str):
        self.form = "" if f in ("*", self.form) else f
        self._fill()

    def _fill(self, *_):
        self.list.clear()
        e = self._esc
        uses = [u for u in self.uses if not (self.only_this.isChecked() and u.item.video and u.item.video == self.main.video)]
        found: dict[str, int] = {}
        for u in uses:
            for f in {u.text[a:b].lower() for a, b in u.spans}:
                found[f] = found.get(f, 0) + 1
        searched = self.meta.get("forms") or []
        if self.form and self.form not in found:
            self.form = ""
        if self.form:
            uses = [u for u in uses if any(u.text[a:b].lower() == self.form for a, b in u.spans)]
        vids = len({u.item.srt for u in uses})
        lang = "German" if self.lang == "de" else "English"
        no_dict = self.main.dictionary(self.lang) is None and " " not in self.word
        self.info.setText((f"{len(uses)} line{'s' if len(uses) != 1 else ''} in {vids} video{'s' if vids != 1 else ''} "
                           f"· {self.files} {lang} subtitle files searched. Double-click a line to play that moment."
                           if uses else
                           f"Not found in your subtitled videos ({self.files} {lang} subtitle files searched). Videos you open "
                           "with subtitles are included automatically; .srt files next to videos in Videos, Downloads and recent "
                           "folders too.")
                          + (f" Only this exact form was searched — download the {lang} dictionary to find the other forms too."
                             if no_dict else ""))
        if found:
            chips = [f"<a href='*' style='color:{theme.CYAN if not self.form else theme.DIM};text-decoration:none'>all</a>"]
            for f, n in sorted(found.items(), key=lambda x: (-x[1], x[0])):
                on = f == self.form
                chips.append(f"<a href='{e(f)}' style='color:{theme.GOLD if on else theme.LIGHT};text-decoration:none'>"
                             f"{'<b>' if on else ''}{e(f)}{'</b>' if on else ''}</a><span style='color:{theme.DIM}'> ×{n}</span>")
            missing = [f for f in searched if f not in found and " … " not in f]
            self.forms.setText("<span style='color:%s'>Forms found (click one to show only it): </span>" % theme.DIM + " &nbsp;·&nbsp; ".join(chips)
                               + (f"<br><span style='color:{theme.DIM};font-size:8.5pt'>Also searched, not in your videos: "
                                  f"{e(', '.join(missing[:14]))}{' …' if len(missing) > 14 else ''}</span>" if missing else ""))
        else:
            self.forms.setText(f"<span style='color:{theme.DIM};font-size:8.5pt'>Searched: {e(', '.join(searched[:24]))}"
                               f"{' …' if len(searched) > 24 else ''}</span>" if searched else "")
        width = max(300, self.list.viewport().width() - 44)
        for u in uses:
            parts, last = [], 0
            for a, b in u.spans:
                parts.append(e(u.text[last:a]))
                parts.append(f"<b style='color:{theme.GOLD}'>{e(u.text[a:b])}</b>")
                last = b
            parts.append(e(u.text[last:]))
            mm, ss = divmod(u.start_ms // 1000, 60)
            here = bool(u.item.video)
            lbl = QLabel(f"<span style='color:{theme.CYAN if here else theme.DIM};font-size:9pt'>{e(u.item.name)} &nbsp;·&nbsp; {mm}:{ss:02d}"
                         f"{'' if here else ' &nbsp;· subtitles only — the video is not on this PC'}</span><br>"
                         f"<span style='font-size:11.5pt;color:{theme.LIGHT if here else theme.DIM}'>{' '.join(''.join(parts).split())}</span>")
            lbl.setTextFormat(Qt.RichText)
            lbl.setWordWrap(True)
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            lbl.setContentsMargins(4, 2, 4, 2)
            lbl.setStyleSheet("background: transparent")
            it = self._QLI()
            it.setData(Qt.UserRole, u)
            from PySide6.QtCore import QSize
            it.setSizeHint(QSize(width, lbl.heightForWidth(width) + 30))
            self.list.addItem(it)
            self.list.setItemWidget(it, lbl)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.play_b.setEnabled(bool(self.list.count()))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        from PySide6.QtCore import QSize
        width = max(300, self.list.viewport().width() - 44)
        for i in range(self.list.count()):
            it = self.list.item(i)
            w = self.list.itemWidget(it)
            if w is not None:
                it.setSizeHint(QSize(width, w.heightForWidth(width) + 30))

    def play(self, it):
        if not it:
            return
        u = it.data(Qt.UserRole)
        if not u.item.video:
            self.info.setText("Only the subtitles of that video are on this PC (synced from your phone, or the video was moved). "
                              "Open the video once and it plays from here.")
            return
        self.accept()
        self.main.open_use(u.item.video, u.item.srt, u.start_ms, u.end_ms)


def _swatch(a1: str, a2: str, a3: str):
    """Three colour dots of a theme, as a button icon."""
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
    pm = QPixmap(92, 36)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    for i, col in enumerate((a1, a2, a3)):
        p.setBrush(QColor(col))
        p.drawEllipse(2 + i * 30, 4, 28, 28)
    p.end()
    return QIcon(pm)


# ==================================================================== correct a subtitle line
class CueEditDialog(QDialog):
    def __init__(self, main, i: int):
        super().__init__(main)
        from . import subtitles
        self.main, self.i = main, i
        self.result_action = None
        c = main.cues[i]
        self.prev_end = main.cues[i - 1].end_ms if i > 0 else 0
        self.next_start = main.cues[i + 1].start_ms if i + 1 < len(main.cues) else 10 ** 9
        self.setWindowTitle("Correct the subtitle line")
        self.setMinimumWidth(640)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 18, 24, 18)
        v.addWidget(title("Correct the subtitle line"))
        v.addWidget(hint(f"Line {i + 1} of {len(main.cues)}. Fix the words, and if needed the timing. Saved into this video's "
                         "subtitles (the first version is kept as a backup)."))
        self.text = QPlainTextEdit(c.text)
        self.text.setMinimumHeight(90)
        f = self.text.font()
        f.setPointSize(13)
        self.text.setFont(f)
        v.addWidget(self.text)
        grid = QHBoxLayout()
        self.start = QLineEdit(self._fmt(c.start_ms))
        self.end = QLineEdit(self._fmt(c.end_ms))
        for lab, fld, which in (("Start", self.start, "start"), ("End", self.end, "end")):
            col = QVBoxLayout()
            col.addWidget(QLabel(lab, objectName="small"))
            r = QHBoxLayout()
            r.addWidget(fld)
            for d in (-500, -100, 100, 500):
                b = QPushButton(f"{d / 1000:+.1f}")
                b.setProperty("kind", "chip")
                b.setFixedWidth(52)
                b.clicked.connect(lambda _=False, f_=fld, d_=d: f_.setText(self._fmt(max(0, self._parse(f_.text()) + d_))))
                r.addWidget(b)
            now = QPushButton("now")
            now.setToolTip("The current video position")
            now.setProperty("kind", "chip")
            now.clicked.connect(lambda _=False, f_=fld: f_.setText(self._fmt(max(0, main.cpos()))))
            r.addWidget(now)
            col.addLayout(r)
            grid.addLayout(col)
        v.addLayout(grid)
        self.err = hint("")
        self.err.setStyleSheet(f"color:{theme.MAGENTA}")
        v.addWidget(self.err)
        row = QHBoxLayout()
        listen = ibtn("play", "Play this line", self.listen, kind="", text=" Listen", size=15)
        dele = ibtn("trash", "Delete this line", self.delete, kind="", text=" Delete", size=15, color=theme.MAGENTA)
        add = ibtn("plus", "Add a new line after this one", self.insert, kind="", text=" Add line after", size=15)
        row.addWidget(listen)
        row.addWidget(add)
        row.addWidget(dele)
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setProperty("accent", True)
        save.clicked.connect(self.save)
        row.addWidget(cancel)
        row.addWidget(save)
        v.addLayout(row)
        self._Cue = subtitles.Cue

    @staticmethod
    def _fmt(ms: int) -> str:
        ms = max(0, int(ms))
        h, rem = divmod(ms, 3_600_000)
        m, rem = divmod(rem, 60_000)
        s, ms = divmod(rem, 1000)
        return (f"{h}:" if h else "") + f"{m:02d}:{s:02d}.{ms:03d}"

    @staticmethod
    def _parse(t: str) -> int:
        import re
        m = re.match(r"^\s*(?:(\d+):)?(\d+):(\d+)(?:[.,](\d{1,3}))?\s*$", t)
        if not m:
            raise ValueError("Use minutes:seconds.milliseconds, e.g. 01:23.450")
        h, mi, s, ms = int(m.group(1) or 0), int(m.group(2)), int(m.group(3)), (m.group(4) or "0").ljust(3, "0")
        return ((h * 60 + mi) * 60 + s) * 1000 + int(ms)

    def _read(self):
        try:
            a, b = self._parse(self.start.text()), self._parse(self.end.text())
        except ValueError as e:
            self.err.setText(str(e))
            return None
        t = "\n".join(l.strip() for l in self.text.toPlainText().strip().split("\n") if l.strip())
        if not t:
            self.err.setText("The line is empty — use Delete to remove it")
            return None
        if b <= a:
            self.err.setText("The end must be after the start")
            return None
        return self._Cue(a, b, t)

    def listen(self):
        c = self._read()
        if c:
            m = self.main
            m.a, m.b = c.start_ms + m.sub_offset, c.end_ms + m.sub_offset + 150
            m.player.setPosition(m.a)
            m.player.play()

    def save(self):
        c = self._read()
        if c:
            self.result_action = ("save", c)
            self.accept()

    def delete(self):
        self.result_action = ("delete", None)
        self.accept()

    def insert(self):
        c = self.main.cues[self.i]
        a = c.end_ms + 50
        b = min(a + 2500, self.next_start - 50) if self.next_start < 10 ** 9 else a + 2500
        if b <= a:
            b = a + 1000
        self.result_action = ("insert", self._Cue(a, b, "…"))
        self.accept()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self.main.edit_cue(self.i + 1))
