"""Settings ▸ Voice ▸ Piper voices: browse every voice of the Piper catalogue, hear it, download / remove it, and choose
the voice that reads each language. Piper only reads words, sentences and translations when you ask (🔊) — the video
keeps its own sound and its actors' voices."""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QMessageBox, QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout)

from . import downloads, paths, piper_catalog as pc, theme, voice

# a short sentence to hear a downloaded voice with (a voice without one reads its language's name)
SAMPLES = {
    "de": "Guten Tag! Ich lerne gern mit Videos.", "en": "Hello! I like learning with videos.",
    "fr": "Bonjour ! J'aime apprendre avec des vidéos.", "es": "¡Hola! Me gusta aprender con vídeos.",
    "it": "Ciao! Mi piace imparare con i video.", "nl": "Hallo! Ik leer graag met video's.",
    "pt": "Olá! Eu gosto de aprender com vídeos.", "ru": "Привет! Я люблю учиться по видео.",
    "pl": "Cześć! Lubię uczyć się z filmów.", "tr": "Merhaba! Videolarla öğrenmeyi seviyorum.",
    "fa": "سلام! من دوست دارم با ویدیو یاد بگیرم.", "ar": "مرحبا! أحب التعلم بالفيديو.",
    "uk": "Привіт! Я люблю вчитися з відео.", "sv": "Hej! Jag gillar att lära mig med videor.",
    "da": "Hej! Jeg kan godt lide at lære med videoer.", "no": "Hei! Jeg liker å lære med videoer.",
    "fi": "Hei! Opin mielelläni videoiden avulla.", "cs": "Ahoj! Rád se učím s videi.", "el": "Γεια! Μου αρέσει να μαθαίνω με βίντεο.",
    "hu": "Szia! Szeretek videókból tanulni.", "ro": "Salut! Îmi place să învăț cu videoclipuri.", "zh": "你好！我喜欢用视频学习。",
}
COLS = ("Language", "Voice", "Quality", "Speakers", "Size", "")


def _mb(n: int) -> str:
    return f"{n / 1_000_000:.0f} MB" if n >= 1_000_000 else f"{max(1, n // 1000)} kB"


class _Bus(QObject):
    catalogue = Signal(object)            # (voices, fetched_at, from_copy) or an error text
    progress = Signal(str, int, int)      # key, done, total
    finished = Signal(str, str)           # key, error ("" = ok, "cancelled")
    licence = Signal(str, str)            # key, licence text
    sample = Signal(str, str)             # key, audio file ("" = none)


class PiperVoicesDialog(QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent or main)
        self.main = main
        self.setWindowTitle("Piper voices — offline voices for reading aloud")
        self.resize(1080, 700)
        self.voices: list[pc.PiperVoice] = []
        self.shown: list[pc.PiperVoice] = []
        self.jobs: dict[str, dict] = {}                # key → {"cancel": bool}
        self.licences: dict[str, str] = {}
        self.bus = _Bus()
        self.bus.catalogue.connect(self._got_catalogue)
        self.bus.progress.connect(self._progress)
        self.bus.finished.connect(self._finished)
        self.bus.licence.connect(self._got_licence)
        self.bus.sample.connect(self._got_sample)
        v = QVBoxLayout(self)
        intro = QLabel("Every voice of the Piper project, in all its languages and qualities. Download only the voices you want "
                       "(each 20–120 MB); they work without internet afterwards. Piper reads words, sentences and translations "
                       "when you press 🔊 — the video always keeps its own sound and the actors' real voices.",
                       objectName="hint", wordWrap=True)
        v.addWidget(intro)
        row = QHBoxLayout()
        self.find = QLineEdit(placeholderText="Find a voice, language or country …")
        self.find.textChanged.connect(self.refresh)
        row.addWidget(self.find, 2)
        self.lang = QComboBox()
        self.lang.setMinimumContentsLength(22)
        self.lang.currentIndexChanged.connect(self.refresh)
        row.addWidget(self.lang, 1)
        self.quality = QComboBox()
        self.quality.addItem("All qualities", "")
        for q in pc.QUALITIES:
            self.quality.addItem(pc.QUALITY_NAME[q], q)
        self.quality.setToolTip("x-low / low: small and fast · medium: good · high: the most natural, larger")
        self.quality.currentIndexChanged.connect(self.refresh)
        row.addWidget(self.quality)
        self.only_have = QCheckBox("Downloaded only")
        self.only_have.toggled.connect(self.refresh)
        row.addWidget(self.only_have)
        self.reload_b = QPushButton("↻ Update list")
        self.reload_b.setToolTip("Read the current voice list from the Piper project again")
        self.reload_b.clicked.connect(lambda: self.load(True))
        row.addWidget(self.reload_b)
        v.addLayout(row)
        self.state = QLabel("", objectName="small", wordWrap=True)
        v.addWidget(self.state)

        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, len(COLS)):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.show_voice)
        self.table.doubleClicked.connect(lambda *_: self.preview())
        v.addWidget(self.table, 3)

        self.info = QTextBrowser(openExternalLinks=True)
        self.info.setMaximumHeight(118)
        v.addWidget(self.info)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        v.addWidget(self.bar)
        b = QHBoxLayout()
        self.play_b = QPushButton("▶ Listen")
        self.play_b.setToolTip("Hear this voice: the Piper project's sample (online), or a sentence read by the downloaded voice")
        self.play_b.clicked.connect(self.preview)
        self.get_b = QPushButton("⬇ Download")
        self.get_b.setProperty("accent", True)
        self.get_b.clicked.connect(self.download)
        self.stop_b = QPushButton("✕ Cancel download")
        self.stop_b.clicked.connect(self.cancel)
        self.use_b = QPushButton("★ Use for …")
        self.use_b.setToolTip("This voice reads this language from now on (with Piper chosen in Settings ▸ Voice)")
        self.use_b.clicked.connect(self.use)
        self.del_b = QPushButton("🗑 Remove")
        self.del_b.clicked.connect(self.remove)
        for w in (self.play_b, self.get_b, self.stop_b, self.use_b, self.del_b):
            b.addWidget(w)
        b.addStretch(1)
        self.defaults = QLabel("", objectName="small")
        b.addWidget(self.defaults)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        b.addWidget(close)
        v.addLayout(b)
        self.show_voice()
        self.load(False)

    # ------------------------------------------------------------------ catalogue
    def load(self, refresh: bool):
        """The saved list at once (offline too), then the current one from upstream."""
        if not refresh:
            cached = pc.cached_catalogue()
            if cached:
                self._got_catalogue((cached, pc._cache_file().stat().st_mtime, True))
        self.reload_b.setEnabled(False)
        self.state.setText(self.state.text() + ("  ·  " if self.state.text() else "") + "Reading the current voice list …")

        def run():
            try:
                self.bus.catalogue.emit(pc.fetch_catalogue())
            except Exception as e:  # noqa: BLE001
                self.bus.catalogue.emit(f"{e}")
        threading.Thread(target=run, daemon=True).start()

    def _got_catalogue(self, res):
        self.reload_b.setEnabled(True)
        if isinstance(res, str):
            have = pc.installed_models()
            self.state.setText(("The voice list could not be read (no internet?) — " + res[:160]
                                + (f". Your {len(have)} downloaded voice(s) still work." if have else ".")) if not self.voices
                               else "Offline — showing the list saved " + self._when(pc._cache_file().stat().st_mtime))
            if not self.voices and have:                   # offline, first time: the downloaded voices from their files
                self.voices = [pc.PiperVoice(key=k, name=k.split("-")[1] if "-" in k else k, family=pc.voice_family(k),
                                             code=k.split("-")[0], language=k.split("-")[0], language_native="", country="",
                                             quality=k.rsplit("-", 1)[-1], files={}) for k in have]
                self._fill_langs()
                self.refresh()
            return
        voices, when, from_copy = res
        self.voices = voices
        langs = len({x.family for x in voices})
        self.state.setText(f"{len(voices)} voices in {langs} languages · "
                           + ("saved list from " + self._when(when) + " (offline)" if from_copy else "current list from the Piper project")
                           + f" · {len(pc.installed_models())} downloaded · stored in {pc.voice_root()}")
        self._fill_langs()
        self.refresh()

    @staticmethod
    def _when(t: float) -> str:
        return time.strftime("%d.%m.%Y %H:%M", time.localtime(t))

    def _fill_langs(self):
        cur = self.lang.currentData() if self.lang.count() else None
        self.lang.blockSignals(True)
        self.lang.clear()
        self.lang.addItem("All languages", "")
        fams: dict[str, tuple[str, int]] = {}
        for x in self.voices:
            name = x.language or x.family
            fams[x.family] = (name + (f" · {x.language_native}" if x.language_native and x.language_native != name else ""),
                              fams.get(x.family, ("", 0))[1] + 1)
        for fam, (name, n) in sorted(fams.items(), key=lambda kv: kv[1][0].lower()):
            self.lang.addItem(f"{name} ({n})", fam)
        i = self.lang.findData(cur if cur is not None else self._home_lang())
        self.lang.setCurrentIndex(max(0, i))
        self.lang.blockSignals(False)

    def _home_lang(self) -> str:
        """The language of the video in the player (German by default)."""
        return getattr(self.main, "cue_lang", "") or "de"

    def refresh(self, *_):
        have = pc.installed_models()
        t = self.find.text().strip().lower()
        fam, q = self.lang.currentData() or "", self.quality.currentData() or ""
        self.shown = [x for x in self.voices
                      if (not fam or x.family == fam) and (not q or x.quality == q) and (not self.only_have.isChecked() or x.key in have)
                      and (not t or t in " ".join((x.key, x.name, x.language, x.language_native, x.country, x.code)).lower())]
        sel = self.current().key if self.current() else ""
        self.table.setRowCount(len(self.shown))
        defaults = self._defaults()
        for r, x in enumerate(self.shown):
            status = ("★ reads " + (x.language or x.family) if defaults.get(x.family) == x.key else "✓ downloaded") if x.key in have else (
                "downloading …" if x.key in self.jobs else "")
            cells = (f"{x.language or x.family} — {x.country or x.code}" + (f"  ·  {x.language_native}" if x.language_native else ""),
                     x.name, pc.QUALITY_NAME.get(x.quality, x.quality), str(x.num_speakers),
                     _mb(x.size_bytes) if x.size_bytes else "", status)
            for c, txt in enumerate(cells):
                it = QTableWidgetItem(txt)
                if c == 5 and x.key in have:
                    it.setForeground(QColor(theme.GOLD if "★" in txt else "#5BE38F"))
                self.table.setItem(r, c, it)
        if sel:
            for r, x in enumerate(self.shown):
                if x.key == sel:
                    self.table.selectRow(r)
                    break
        self._show_defaults()
        self.show_voice()

    def current(self) -> pc.PiperVoice | None:
        r = self.table.currentRow()
        return self.shown[r] if 0 <= r < len(self.shown) and self.table.selectedItems() else None

    # ------------------------------------------------------------------ the chosen voice
    def _defaults(self) -> dict[str, str]:
        s = self.main.settings
        return {k[len("voice_piper_"):]: v for k, v in s.items() if k.startswith("voice_piper_") and v}

    def _show_defaults(self):
        d = self._defaults()
        parts = [f"{fam}: {key.split('-')[1] if '-' in key else key}" for fam, key in sorted(d.items())]
        self.defaults.setText("Reads with: " + (", ".join(parts) if parts else "the voices that came with Piper (Thorsten, Lessac)"))

    def show_voice(self):
        x = self.current()
        have = x is not None and pc.model_path(x.key) is not None
        busy = x is not None and x.key in self.jobs
        self.play_b.setEnabled(x is not None)
        self.get_b.setVisible(x is not None and not have and not busy)
        self.get_b.setText(f"⬇ Download ({_mb(x.size_bytes)})" if x and x.size_bytes else "⬇ Download")
        self.stop_b.setVisible(busy)
        self.del_b.setVisible(have)
        self.use_b.setVisible(have)
        if x:
            lang = x.language or x.family
            chosen = self._defaults().get(x.family) == x.key
            self.use_b.setText(f"★ Reads {lang}" if chosen else f"★ Use for {lang}")
            self.use_b.setEnabled(not chosen)
            lic = self.licences.get(x.key)
            if lic is None and x.files:
                self.licences[x.key] = ""
                self._fetch_licence(x)
            self.info.setHtml(
                f"<b style='color:{theme.CYAN}'>{x.name}</b> · {x.language} ({x.country}) · <code>{x.code}</code> · "
                f"{pc.QUALITY_NAME.get(x.quality, x.quality)} quality · {x.num_speakers} speaker(s)"
                + (f" · {_mb(x.size_bytes)}" if x.size_bytes else "")
                + f"<br><span style='color:{theme.DIM}'>Key <code>{x.key}</code>"
                + (f" · on this PC: {pc.model_path(x.key).parent}" if have else " · not downloaded") + "</span>"
                + f"<br>Licence: <b>{lic or ('reading the model card …' if x.files else 'see the model card')}</b>"
                + (f" · <a href='{pc.BASE.replace('/resolve/main', '/blob/main')}/{x.card_rel}' style='color:{theme.CYAN}'>model card</a>"
                   if x.card_rel else "")
                + f"<br><span style='color:{theme.DIM}'>Voices of the Piper project (github.com/OHF-Voice/piper1-gpl, voices from "
                  "huggingface.co/rhasspy/piper-voices). Each keeps the licence of the dataset it was trained on — check it "
                  "before sharing audio made with it.</span>")
        else:
            self.info.setHtml(f"<span style='color:{theme.DIM}'>Choose a voice. ▶ Listen (or double-click) hears it before "
                              "you download it.</span>")

    def _fetch_licence(self, x: pc.PiperVoice):
        def run():
            try:
                card = pc.card_text(x)
                self.bus.licence.emit(x.key, pc.licence_of(card) or "named in the model card")
            except Exception:  # noqa: BLE001
                self.bus.licence.emit(x.key, "")
        threading.Thread(target=run, daemon=True).start()

    def _got_licence(self, key, text):
        self.licences[key] = text or "see the model card"
        if self.current() and self.current().key == key:
            self.show_voice()

    # ------------------------------------------------------------------ listen
    def preview(self):
        x = self.current()
        if not x:
            return
        self.play_b.setEnabled(False)
        self.play_b.setText("▶ …")
        installed = pc.model_path(x.key)

        def run():
            f = ""
            try:
                if installed and downloads.is_ready(voice.PIPER):
                    text = SAMPLES.get(x.family) or x.language_native or x.language or x.name
                    f = str(voice.piper_file(text, x.family, model=(f"{x.key}@{installed.stat().st_size}", installed)))
                else:
                    f = self._sample_file(x)
            except Exception:  # noqa: BLE001
                try:
                    f = self._sample_file(x)
                except Exception:  # noqa: BLE001
                    f = ""
            self.bus.sample.emit(x.key, f)
        threading.Thread(target=run, daemon=True).start()

    @staticmethod
    def _sample_file(x: pc.PiperVoice) -> str:
        """The Piper project's own sample of the voice, kept in the speech folder."""
        import hashlib
        import requests
        f = paths.sub_dir("speech") / ("sample-" + hashlib.sha1(x.key.encode()).hexdigest()[:16] + ".mp3")
        if f.exists() and f.stat().st_size > 1000:
            return str(f)
        r = requests.get(x.sample_url, timeout=(10, 30))
        r.raise_for_status()
        if len(r.content) < 1000 or b"<html" in r.content[:200].lower():
            raise IOError("no sample")
        f.write_bytes(r.content)
        return str(f)

    def _got_sample(self, key, f):
        self.play_b.setEnabled(True)
        self.play_b.setText("▶ Listen")
        if f:
            self.main._play_speech(f)
        else:
            x = next((v for v in self.voices if v.key == key), None)
            self.main.msg("No sample of this voice could be played — no internet, or the Piper project has no sample of it. "
                          "Download it to hear it read a sentence." if x and not pc.model_path(key) else
                          "The voice could not read the sample (it may need a newer Piper) — try another voice", 9000)

    # ------------------------------------------------------------------ download / remove / choose
    def download(self):
        x = self.current()
        if not x or x.key in self.jobs or not x.files:
            return
        job = {"cancel": False}
        self.jobs[x.key] = job
        self.bar.setVisible(True)
        self.bar.setValue(0)
        self.refresh()

        def run():
            try:
                if not downloads.is_ready(voice.PIPER):            # the engine (22 MB) comes first, once
                    downloads.ensure(voice.PIPER, lambda d, t: self.bus.progress.emit("Piper engine", d, t), lambda: job["cancel"])
                pc.install(x, lambda d, t: self.bus.progress.emit(x.key, d, t), lambda: job["cancel"])
                self.bus.finished.emit(x.key, "")
            except InterruptedError:
                self.bus.finished.emit(x.key, "cancelled")
            except Exception as e:  # noqa: BLE001
                self.bus.finished.emit(x.key, f"{e.__class__.__name__}: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _progress(self, key, done, total):
        self.bar.setMaximum(1000)
        self.bar.setValue(int(1000 * done / max(total, 1)))
        self.bar.setFormat(f"{key}: {done // 1_000_000} of {max(total, 1) // 1_000_000} MB")

    def cancel(self):
        x = self.current()
        if x and x.key in self.jobs:
            self.jobs[x.key]["cancel"] = True
            self.stop_b.setEnabled(False)

    def _finished(self, key, err):
        self.jobs.pop(key, None)
        self.stop_b.setEnabled(True)
        self.bar.setVisible(bool(self.jobs))
        x = next((v for v in self.voices if v.key == key), None)
        if not err:
            self.main.msg(f"Voice {key} downloaded ✓ — ★ Use for {x.language if x else 'its language'} to read with it", 9000)
            if x and not self._defaults().get(x.family) and x.family not in voice.PIPER_VOICES:
                self._set_default(x)                       # the first voice of a new language reads it
        elif err == "cancelled":
            self.main.msg(f"Download of {key} cancelled — nothing was kept", 6000)
        else:
            QMessageBox.warning(self, "Piper voice", f"{key} could not be downloaded:\n\n{err}\n\nNothing half-finished was kept.")
        self.refresh()

    def use(self):
        x = self.current()
        if x and pc.model_path(x.key):
            self._set_default(x)
            if self.main.settings.get("voice_engine", "edge") != "piper" and QMessageBox.question(
                    self, "Piper voices", f"{x.name} now reads {x.language or x.family} with Piper.\n\nRead words and sentences with "
                    "Piper (offline) from now on? (Settings ▸ Voice — Microsoft's online voices stay available there)") == QMessageBox.Yes:
                self.main.settings["voice_engine"] = "piper"
                self.main.save_settings()
            self.refresh()

    def _set_default(self, x: pc.PiperVoice):
        self.main.settings[f"voice_piper_{x.family}"] = x.key
        self.main.save_settings()

    def remove(self):
        x = self.current()
        if not x or not pc.model_path(x.key):
            return
        if QMessageBox.question(self, "Remove voice", f"Delete the voice {x.key} from this PC? You can download it again later.") != QMessageBox.Yes:
            return
        pc.remove(x.key)
        if self._defaults().get(x.family) == x.key:          # it read this language: back to the voice that came with Piper
            self.main.settings.pop(f"voice_piper_{x.family}", None)
            self.main.save_settings()
        self.main.msg(f"Voice {x.key} removed", 6000)
        self.refresh()

    def closeEvent(self, e):
        for j in self.jobs.values():                          # a download still running is cancelled with the window
            j["cancel"] = True
        super().closeEvent(e)
