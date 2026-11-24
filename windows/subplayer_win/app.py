"""SubPlayer for Windows — main window: player, clickable subtitles, word card, My Words, review, practice."""
from __future__ import annotations

import html
import json
import os
import re
import sys
import threading
import time
import urllib.parse
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QCursor, QDesktopServices, QFont, QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QMenu, QMessageBox, QProgressBar, QPushButton, QSizePolicy, QSlider,
                               QStackedWidget, QStyle, QTextBrowser, QToolButton, QVBoxLayout, QWidget)

from . import VERSION, downloads, icons, licence, paths, subtitles, syncer, theme, translate
from .cosmos import Cosmos, GradientLabel, Orb
from .dictionary import Dictionary, clean_example, normalize
from .store import Example, Progress, SavedWord, WordStore, now_ms

SETTINGS = paths.data_dir() / "settings.json"
VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".mp3", ".m4a", ".wav"}


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def fmt(ms: int) -> str:
    s = max(0, int(ms)) // 1000
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


class Bus(QObject):
    """Signals used to hand results from background threads to the window."""
    progress = Signal(float, str)
    done = Signal(str, object)        # kind, payload
    failed = Signal(str, str)         # kind, message


def ibtn(name, tip, fn=None, checkable=False, size=20, kind="icon", text="", color=None, active=None):
    color, active = color or theme.LIGHT, active or theme.CYAN
    b = QPushButton(text, toolTip=tip, checkable=checkable)
    b.setIcon(icons.icon(name, color, size, active=active))
    b.setIconSize(QSize(size, size))
    b.setProperty("kind", kind)
    b.setCursor(Qt.PointingHandCursor)
    if fn:
        b.clicked.connect(fn)
    return b


class JumpSlider(QSlider):
    """A seek bar that jumps straight to where you click (instead of moving a page at a time)."""

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.maximum() > self.minimum():
            x = e.position().x() if hasattr(e, "position") else e.x()
            v = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), int(x), self.width())
            self.setValue(v)
            self.sliderMoved.emit(v)
        super().mousePressEvent(e)


SPEEDS = (0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.0, 1.1, 1.25, 1.5)
from .levels import COLORS as LV_COLORS, NAMES as LV_NAMES   # noqa: E402
SUB_SIZES = {"Small": 16, "Medium": 21, "Large": 26, "Extra large": 32}
REPEATS = (0, 2, 3, 5)                      # 0 = until you stop it


class RecentCard(QFrame):
    """A recent video on the welcome screen: name, how far you got, one click to continue."""

    def __init__(self, r: dict, on_open):
        super().__init__(objectName="recent")
        self.setCursor(Qt.PointingHandCursor)
        self.on_open, self.path = on_open, r["path"]
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(6)
        top = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("film", theme.CYAN, 18))
        top.addWidget(ic)
        name = QLabel(r["name"])
        name.setStyleSheet("font-weight:600")
        name.setMaximumWidth(260)
        name.setText(name.fontMetrics().elidedText(r["name"], Qt.ElideMiddle, 250))
        top.addWidget(name, 1)
        v.addLayout(top)
        dur, pos = r.get("dur", 0) or 0, r.get("pos", 0) or 0
        bar = QProgressBar(maximum=1000, value=int(1000 * pos / dur) if dur else 0, textVisible=False)
        bar.setFixedHeight(5)
        v.addWidget(bar)
        v.addWidget(QLabel(f"Continue at {fmt(pos)}" + (f"  ·  {fmt(dur)}" if dur else ""), objectName="small"))

    def mousePressEvent(self, e):
        self.on_open(self.path)


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"SubPlayer {VERSION}")
        self.setWindowIcon(icons.app_icon())
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        self.settings = load_settings()
        from . import netcfg
        netcfg.apply(self.settings)
        self.store = WordStore()
        self._merged = self._upgrade_words()
        self._colfixed = self._fix_pasted_collocations()
        self._broken = self._remove_broken_collocations()
        self.progress = Progress()
        self.lic = licence.LicenceState()
        self.bus = Bus()
        self.bus.progress.connect(self._on_progress)
        self.bus.done.connect(self._on_done)
        self.bus.failed.connect(self._on_failed)
        self.dicts: dict[str, Dictionary] = {}
        self.cues: list[subtitles.Cue] = []
        self.cue_lang = "de"
        self.video: str | None = None
        self.video_name = ""
        self.a = self.b = -1
        self.loop_line = False
        self.pause_each = False
        self.shadowing = False
        self.shadow_resume = 0.0
        self.held_cue = -1
        self.pe_last = -1                                    # Pause each line: the line it last stopped after
        self.pe_resume = 0.0                                 # … and when it goes on by itself (time.monotonic)
        self.dl_queue: list = []                             # downloads waiting their turn: (kind, fn, cancellable, label)
        self.dl_done: list = []                              # finished downloads from the queue: (title, path)
        self._dl_queued = False                              # the running download came from the queue
        self._units_key, self._units = None, []
        self.mini = None                                     # the small video window while another page is open
        self.sub_offset = 0                                  # ms; + = subtitles appear later (G / H)
        from .levels import Levels
        self.levels = Levels()
        self.hide_text = False                               # listening mode
        self.show_tr = False                                 # translation line under the subtitle
        self.tr_cache: dict = {}
        self.tr_pending: set = set()
        self.repeat_n = 0                                    # 0 = loop until stopped
        self.repeat_done = 0
        self._tr_idx = -1
        self._tr_scrolled_at = 0.0
        self._tr_auto = False
        self.phrase_start: tuple[int, int] | None = None     # (cue, token) of a Shift+click
        self.card: dict | None = None                        # what the word card shows
        self.busy = None
        self.cancel = False
        self.panel_open = True
        self.page = "player"
        self._playing = None
        self.sync_timer = QTimer(self, singleShot=True, interval=20_000, timeout=lambda: self.sync_now(silent=True))
        self.last_sync = 0.0
        self.setAcceptDrops(True)
        self._build()
        self.tts = None
        QTimer.singleShot(300, self._startup)

    def _upgrade_words(self) -> int:
        """Once (2.6): the same word saved twice becomes one entry, and the collocations the teacher wrote before are kept
        with the words. A copy of the word database is kept first (words-before-2.6.db)."""
        if self.settings.get("upgraded_26"):
            return 0
        n = 0
        try:
            import shutil
            db = paths.data_dir() / "words.db"
            bak = paths.data_dir() / "words-before-2.6.db"
            if db.exists() and not bak.exists():
                self.store.db.commit()
                shutil.copy2(db, bak)
            n = self.store.merge_duplicates()
            from . import ollama
            from .teacher import collocations_of
            saved = {WordStore.word_key(w.text, w.lemma, w.lang) for w in self.store.all()}
            for k, d in ollama.Cache().d.items():
                parts = k.split("|")
                if len(parts) >= 5 and isinstance(d, dict) and (parts[1], parts[2]) in saved:
                    self.store.add_collocations(parts[1], parts[2], collocations_of(d))
        except Exception as e:
            print("word upgrade:", e)
        self.settings["upgraded_26"] = True
        self.save_settings()
        return n

    def _fix_pasted_collocations(self) -> int:
        """Once (2.6.1): collocations that a pasted AI table put among the sentences (short phrases with the word, no full stop)
        move to the word's collocations; table headers such as "German collocation | English" are removed."""
        if self.settings.get("colfix_261"):
            return 0
        from . import practice
        n = 0
        try:
            for w in self.store.all():
                base = (w.lemma or w.text).lower()
                for e in self.store.examples(w.id):
                    if practice.is_header(e.de):
                        self.store.delete_example(e.id)
                        n += 1
                    elif practice.is_phrase(e.de) and (base in e.de.lower() or w.text.lower() in e.de.lower()):
                        self.store.add_collocations(w.lang, w.lemma or w.text,
                                                    [{"phrase": e.de, "meaning": " · ".join(x for x in (e.en, e.fa) if x), "example": ""}])
                        self.store.delete_example(e.id)
                        n += 1
        except Exception as ex:
            print("collocation fix:", ex)
        self.settings["colfix_261"] = True
        self.save_settings()
        return n

    def _remove_broken_collocations(self) -> int:
        """Once (2.6.2): "collocations" that were really lines of a JSON answer pasted with escapes ({\\, &#x20; "meaning": …)
        are removed — paste the answer again, it is read properly now."""
        if self.settings.get("colfix_262"):
            return 0
        n = 0
        try:
            rows = self.store.db.execute("SELECT id, phrase FROM collocations").fetchall()
            bad = [r["id"] for r in rows if re.search(r'(&#x?[0-9a-f]+;|^[{}\[\],\\]+$|"\s*:|\\$|^\s*"[\w ]+"\s*:)', r["phrase"] or "", re.I)]
            for cid in bad:
                self.store.delete_collocation(cid)
            n = len(bad)
        except Exception as e:
            log_error("collocation clean-up", e)
        self.settings["colfix_262"] = True
        self.save_settings()
        return n

    # ================================================================== layout
    def _build(self):
        self.setStyleSheet(theme.QSS)
        self.cosmos = Cosmos()
        self.cosmos.motion = self.settings.get("motion", True)
        self.setCentralWidget(self.cosmos)
        root = QHBoxLayout(self.cosmos)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._rail())

        body = QWidget(objectName="clear")
        bl = QHBoxLayout(body)
        bl.setContentsMargins(16, 14, 16, 12)
        bl.setSpacing(14)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._player_page())
        from .discover import DiscoverPage
        from .pages import PracticePage, ReviewPage, WordsPage
        self.words_page = WordsPage(self)
        self.review_page = ReviewPage(self)
        self.practice_page = PracticePage(self)
        self.discover_page = DiscoverPage(self)
        from .study import StudyPage
        self.study_page = StudyPage(self)
        for p in (self.words_page, self.review_page, self.practice_page, self.discover_page, self.study_page):
            self.stack.addWidget(p)
        bl.addWidget(self.stack, 1)
        bl.addWidget(self._panel())
        root.addWidget(body, 1)

        self.prog = QProgressBar(maximumWidth=260, visible=False)
        self.queue_btn = QPushButton("", visible=False, toolTip="Downloads: the one running, the ones waiting, the finished ones")
        self.queue_btn.setProperty("kind", "chip")
        self.queue_btn.clicked.connect(self.queue_menu)
        self.statusBar().addPermanentWidget(self.queue_btn)
        self.cancel_btn = QPushButton("Cancel", visible=False)
        self.cancel_btn.setProperty("kind", "chip")
        self.cancel_btn.clicked.connect(self._cancel_task)
        self.statusBar().addPermanentWidget(self.prog)
        self.statusBar().addPermanentWidget(self.cancel_btn)
        self.statusBar().setSizeGripEnabled(False)
        self.show_page("player")

    def _rail(self) -> QFrame:
        rail = QFrame(objectName="rail")
        rail.setFixedWidth(92)
        v = QVBoxLayout(rail)
        v.setContentsMargins(10, 16, 10, 14)
        v.setSpacing(6)
        logo = QLabel()
        logo.setPixmap(icons.app_icon().pixmap(46, 46))
        logo.setAlignment(Qt.AlignCenter)
        logo.setToolTip(f"SubPlayer {VERSION}")
        v.addWidget(logo)
        name = QLabel("SubPlayer", objectName="railName", alignment=Qt.AlignCenter)
        v.addWidget(name)
        v.addSpacing(14)

        def nav(icon, label, tip, fn, checkable=True):
            b = QToolButton(text=label, toolTip=tip, checkable=checkable)
            b.setIcon(icons.icon(icon, theme.DIM, 24, active="#FFFFFF"))
            b.setIconSize(QSize(24, 24))
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setProperty("kind", "nav")
            b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setMinimumHeight(62)
            b.clicked.connect(fn)
            v.addWidget(b)
            return b

        self.nav = {}
        for key, ic, label, tip in (("player", "film", "Player", "The video and its subtitles"),
                                    ("discover", "compass", "Discover", "Find free programmes from ARD, ZDF, 3sat, Arte, DW (Ctrl+F)"),
                                    ("words", "star", "My Words", "Saved words and phrases"),
                                    ("review", "cards", "Review", "Review the words that are due"),
                                    ("practice", "puzzle", "Practice", "Gap-fill, dictation, der·die·das")):
            self.nav[key] = nav(ic, label, tip, lambda _=False, k=key: self.show_page(k))
        self.writing_btn = nav("pen", "Writing", "Writing coach: write a text — every sentence corrected, feedback on development, "
                               "cohesion and coherence, three better versions (Ollama, ChatGPT, Gemini, DeepSeek, Grok …)",
                               self.writing_coach, checkable=False)
        self.notebook_btn = nav("notes", "Notebook", "Every answer of the teacher (the line explained, your questions, checked "
                                "sentences and texts, A1 → C1) — read again and review", self.notebook, checkable=False)
        self.due_badge = QLabel("", objectName="badge", alignment=Qt.AlignCenter)
        self.due_badge.setToolTip("Words due for review")
        v.addWidget(self.due_badge)
        v.addStretch(1)
        self.streak_lbl = QLabel("", alignment=Qt.AlignCenter, objectName="small")
        v.addWidget(self.streak_lbl)
        self.sync_btn = nav("sync", "Sync", "Sync with your phone now (private GitHub gist)", lambda: self.sync_now(), checkable=False)
        nav("gear", "Settings", "Licence, sync, reminder, online transcription, downloads", self.settings_dialog, checkable=False)
        nav("help", "Help", "How everything works (F1)", self.help_dialog, checkable=False)
        QShortcut(QKeySequence("F1"), self, activated=self.help_dialog)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.open_dialog)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.link_dialog)
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self.generate_dialog)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: (self.show_page("discover"), self.discover_page.q.setFocus()))
        return rail

    def _panel(self) -> QFrame:
        self.panel = QFrame(objectName="panel")
        self.panel.setFixedWidth(410)
        v = QVBoxLayout(self.panel)
        v.setContentsMargins(18, 14, 14, 14)
        head = QHBoxLayout()
        head.setSpacing(6)
        self.tab_card = ibtn("book", "The dictionary entry of the word you clicked", lambda: self.panel_tab(0), checkable=True,
                             kind="chip", text=" Word card", size=15)
        self.tab_tr = ibtn("list", "All subtitle lines — click one to jump there, double-click to loop it (T)", lambda: self.panel_tab(1),
                           checkable=True, kind="chip", text=" Transcript", size=15)
        head.addWidget(self.tab_card)
        head.addWidget(self.tab_tr)
        head.addStretch(1)
        x = ibtn("x", "Hide the panel", self.toggle_panel, size=16)
        head.addWidget(x)
        v.addLayout(head)
        self.panel_stack = QStackedWidget()
        card_page = QWidget(objectName="clear")
        cv = QVBoxLayout(card_page)
        cv.setContentsMargins(0, 6, 0, 0)
        self.card_view = QTextBrowser(openLinks=False)
        self.card_view.anchorClicked.connect(self._card_link)
        cv.addWidget(self.card_view, 1)
        g = QGridLayout()
        g.setSpacing(8)
        self.save_btn = ibtn("star", "Save to My Words with this video moment", self.save_from_card, kind="", text=" Save")
        b_speak = ibtn("volume", "Speak (Windows voice)", lambda: self.speak_card(False), kind="", text=" Speak")
        b_slow = QPushButton("Slow", toolTip="Speak slowly")
        b_slow.clicked.connect(lambda: self.speak_card(True))
        b_sent = ibtn("translate", "Translate the whole sentence (online)", self.translate_sentence, kind="", text=" Sentence")
        self.learn_btn = ibtn("sparkles", "ChatGPT / Gemini / DeepSeek / Grok with a ready question, DWDS or Cambridge, dict.cc", self.learn_menu,
                              kind="", text=" Learn more")
        g.addWidget(self.save_btn, 0, 0)
        g.addWidget(b_speak, 0, 1)
        g.addWidget(b_slow, 0, 2)
        self.b_teach = b_teach = ibtn("study", "Your AI teacher on this PC (Ollama): collocations, example sentences at your level, the line "
                       "explained, your own sentence corrected", self.open_teacher, kind="", text=" Teacher")
        g.addWidget(b_sent, 1, 0)
        g.addWidget(b_teach, 1, 1)
        g.addWidget(self.learn_btn, 1, 2)
        b_para = ibtn("paraphrase", "Paraphrase the sentence of this word: the same meaning at A1, A2, B1, B2 and C1 (P)",
                      lambda: self.open_teacher(6) if self.card else self.paraphrase_line(), kind="", text=" Paraphrase the sentence (A1 → C1)")
        g.addWidget(b_para, 2, 0, 1, 3)
        cv.addLayout(g)
        self.panel_stack.addWidget(card_page)

        tr_page = QWidget(objectName="clear")
        tv = QVBoxLayout(tr_page)
        tv.setContentsMargins(0, 6, 0, 0)
        self.tr_search = QLineEdit(placeholderText="Find in the transcript…")
        self.tr_search.textChanged.connect(self._filter_transcript)
        tv.addWidget(self.tr_search)
        self.transcript = QListWidget()
        self.transcript.setWordWrap(True)
        self.transcript.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.transcript.setResizeMode(QListWidget.Adjust)
        self.transcript.setTextElideMode(Qt.ElideNone)
        self.transcript.setObjectName("transcript")
        self.transcript.itemClicked.connect(self._transcript_click)
        self.transcript.itemDoubleClicked.connect(self._transcript_loop)
        self.transcript.verticalScrollBar().valueChanged.connect(self._transcript_scrolled)
        self.transcript.setContextMenuPolicy(Qt.CustomContextMenu)
        self.transcript.customContextMenuRequested.connect(self._transcript_menu)
        tv.addWidget(self.transcript, 1)
        self.tr_info = QLabel("", objectName="small")
        self.tr_info.setWordWrap(True)
        tv.addWidget(self.tr_info)
        trow = QHBoxLayout()
        self.study_btn = ibtn("study", "Study this video: its words by level, your saved words from it, practice with its whole text",
                              lambda: self.open_study(), kind="", text=" Study this video", size=15)
        self.trall_btn = ibtn("translate", "Translate every line now (English or Persian) — then the translation line works offline",
                              lambda: self.translate_all(), kind="", text=" Translate all", size=15)
        trow.addWidget(self.study_btn)
        trow.addWidget(self.trall_btn)
        tv.addLayout(trow)
        self.panel_stack.addWidget(tr_page)
        v.addWidget(self.panel_stack, 1)
        self.panel_tab(0)
        self._card_html(f"<p style='font-size:20pt;font-weight:800;color:{theme.CYAN};margin-bottom:4px'>Tap a word</p>"
                        f"<p style='color:{theme.DIM};line-height:150%'>Pause the video and click any word in the subtitle: "
                        "dictionary entry, IPA, meanings with examples, English/German and Persian.</p>"
                        f"<p style='color:{theme.DIM};line-height:150%'><b style='color:{theme.LIGHT}'>Shift+click</b> a first and a last "
                        f"word → phrase translation.<br><b style='color:{theme.LIGHT}'>Ctrl+click</b> a word → whole sentence.</p>")
        return self.panel

    def _player_page(self) -> QWidget:
        page = QWidget(objectName="page")
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        # ---- top bar
        self.topbar = QFrame(objectName="topbar")
        t = QHBoxLayout(self.topbar)
        t.setContentsMargins(0, 0, 0, 0)
        t.setSpacing(8)
        self.title_lbl = GradientLabel("SubPlayer", 17, QFont.Black)
        self.title_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        t.addWidget(self.title_lbl, 1)
        for ic, label, tip, fn in (("folder", " Open", "Open a video (Ctrl+O) — or drag it onto the window", self.open_dialog),
                                   ("link", " Link", "Open a video link — ARD, ZDF, 3sat, Arte, DW, Tagesschau pages or any .mp4 (Ctrl+L)", self.link_dialog),
                                   ("clock", " Recent", "Recent videos — continues where you stopped", self.show_recent),
                                   ("captions", " Subtitles", "Make subtitles for this video: offline Whisper or online (Ctrl+G)", self.generate_dialog),
                                   ("file", " Subtitle file", "Load an .srt/.vtt, save the current subtitles", self.subtitle_menu)):
            b = ibtn(ic, tip, fn, kind="chip", text=label, size=17)
            t.addWidget(b)
            if label.strip() == "Recent":
                self.recent_btn = b
        self.panel_btn = ibtn("panel", "Show / hide the word card", self.toggle_panel, checkable=True, size=18)
        self.panel_btn.setChecked(True)
        t.addWidget(self.panel_btn)
        t.addWidget(ibtn("fullscreen", "Full screen (F)", self.toggle_fullscreen, size=18))
        v.addWidget(self.topbar)

        self.pstack = QStackedWidget()
        self.pstack.addWidget(self._hero())
        self.pstack.addWidget(self._player_view())
        v.addWidget(self.pstack, 1)

        for key, fn in (("Space", self.toggle_play), ("Left", lambda: self.seek_rel(-5000)), ("Right", lambda: self.seek_rel(5000)),
                        ("Up", lambda: self.jump_line(-1)), ("Down", lambda: self.jump_line(1)), ("A", self.set_a), ("B", self.set_b),
                        ("L", lambda: self.loop_btn.click()), ("S", lambda: self.shadow_btn.click()), ("Escape", self._escape),
                        ("F", self.toggle_fullscreen), ("F11", self.toggle_fullscreen),
                        ("G", lambda: self.shift_subs(-100)), ("H", lambda: self.shift_subs(100)), ("V", lambda: self.hide_btn.click()),
                        ("Ctrl+T", lambda: self.trl_btn.click()), ("T", lambda: self.panel_tab(1 if self.panel_stack.currentIndex() == 0 else 0, show=True)),
                        ("M", self.toggle_mute), ("R", self.cycle_repeat), ("K", lambda: self.lvl_btn.click()), ("E", lambda: self.edit_cue()), ("P", lambda: self.paraphrase_line()), ("Y", lambda: self.record_compare()), ("[", lambda: self.step_speed(-1)), ("]", lambda: self.step_speed(1)),
                        ("Ctrl+=", lambda: self.step_sub_size(1)), ("Ctrl++", lambda: self.step_sub_size(1)), ("Ctrl+-", lambda: self.step_sub_size(-1))):
            QShortcut(QKeySequence(key), page, activated=fn, context=Qt.WidgetWithChildrenShortcut)
        self.ticker = QTimer(self, interval=40, timeout=self._tick)
        self.ticker.start()
        return page

    def _hero(self) -> QWidget:
        w = QWidget(objectName="clear")
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        hero = QFrame(objectName="hero")
        hv = QVBoxLayout(hero)
        hv.setContentsMargins(40, 26, 40, 30)
        hv.setSpacing(8)
        orb = Orb(210)
        hv.addWidget(orb, 0, Qt.AlignHCenter)
        t = GradientLabel("Learn from the videos you love", 26, QFont.Black)
        t.setAlignment(Qt.AlignHCenter)
        hv.addWidget(t)
        sub = QLabel("German & English subtitles · tap any word · loop, shadow, save and review — all on your PC",
                     objectName="hint", alignment=Qt.AlignCenter)
        hv.addWidget(sub)
        hv.addSpacing(14)
        row = QHBoxLayout()
        row.addStretch(1)
        b1 = ibtn("folder", "Open a video file (Ctrl+O)", self.open_dialog, kind="", text="  Open a video", size=20, color="#FFFFFF")
        b1.setProperty("accent", True)
        b1.setMinimumHeight(46)
        theme.glow(b1, theme.MAGENTA, 34, 140)
        b2 = ibtn("link", "Paste a web link (Ctrl+L)", self.link_dialog, kind="", text="  Paste a video link", size=20)
        b2.setMinimumHeight(46)
        b3 = ibtn("compass", "Free programmes from ARD, ZDF, 3sat, Arte, DW — many with subtitles (Ctrl+F)",
                  lambda: self.show_page("discover"), kind="", text="  Discover videos", size=20)
        b3.setMinimumHeight(46)
        for b in (b1, b2, b3):
            b.setMinimumWidth(220)
            row.addWidget(b)
        row.addStretch(1)
        hv.addLayout(row)
        drop = QLabel("…or drop a video (or an .srt) anywhere on this window", objectName="small", alignment=Qt.AlignCenter)
        hv.addWidget(drop)
        hv.addSpacing(16)
        self.recent_title = QLabel("CONTINUE WATCHING", alignment=Qt.AlignLeft)
        self.recent_title.setStyleSheet(f"color:{theme.CYAN};font-weight:700;letter-spacing:2px;font-size:9pt")
        hv.addWidget(self.recent_title)
        self.recent_grid = QGridLayout()
        self.recent_grid.setSpacing(12)
        hv.addLayout(self.recent_grid)
        hv.addStretch(1)
        outer.addWidget(hero, 1)
        return w

    def _fill_recents(self):
        while self.recent_grid.count():
            it = self.recent_grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        rs = [r for r in self.recents() if os.path.exists(r["path"])][:6]
        self.recent_title.setVisible(bool(rs))
        for i, r in enumerate(rs):
            self.recent_grid.addWidget(RecentCard(r, self.open_video), i // 3, i % 3)

    def _player_view(self) -> QWidget:
        w = QWidget(objectName="clear")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.vframe = QFrame(objectName="videoFrame")
        vf = QVBoxLayout(self.vframe)
        vf.setContentsMargins(2, 2, 2, 2)
        self.vw = QVideoWidget()
        self.vw.setStyleSheet("background:black;border-radius:16px")
        self.player.setVideoOutput(self.vw)
        self.player.errorOccurred.connect(lambda e, s: self.msg("Video error: " + s))
        self.player.durationChanged.connect(lambda d: self.slider.setRange(0, max(0, d)))
        self.vw.mousePressEvent = lambda e: self.toggle_play()
        self.vw.mouseDoubleClickEvent = lambda e: self.toggle_fullscreen()
        self.vw.wheelEvent = self._video_wheel
        self.vstack = QStackedWidget()
        self.vstack.addWidget(self.vw)
        self.audio_cover = QLabel(alignment=Qt.AlignCenter)
        self.audio_cover.setWordWrap(True)
        self.audio_cover.setStyleSheet(theme.recolor("background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #1B1240,stop:1 #0B2A3A);"
                                       "border-radius:16px;color:#E8E6FF;font-size:15pt;padding:24px"))
        self.audio_cover.mousePressEvent = lambda e: self.toggle_play()
        self.vstack.addWidget(self.audio_cover)
        self.player.hasVideoChanged.connect(self._has_video)
        vf.addWidget(self.vstack)
        theme.glow(self.vframe, theme.VIOLET, 40, 110)
        v.addWidget(self.vframe, 1)

        self.subs_frame = QFrame(objectName="subs")
        sl = QHBoxLayout(self.subs_frame)
        sl.setContentsMargins(14, 6, 8, 6)
        sl.setSpacing(4)
        self.sub_view = QTextBrowser(openLinks=False)
        self.sub_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sub_view.anchorClicked.connect(self._sub_click)
        sl.addWidget(self.sub_view, 1)
        tools = QVBoxLayout()
        tools.setSpacing(2)
        self.size_btn = ibtn("textsize", "Subtitle size and timing (G / H move the subtitles earlier / later)", self.subtitle_options, size=17)
        self.hide_btn = ibtn("eye", "Listening mode: hide the text while the video plays — it shows when you pause (V)",
                             self.toggle_hide_text, checkable=True, size=17)
        self.trl_btn = ibtn("translate", "Show a translation of each line underneath (online) — English or Persian (Ctrl+T)",
                            self.toggle_translation_line, checkable=True, size=17)
        self.trs_btn = ibtn("list", "Transcript: all lines, click to jump (T)", lambda: self.panel_tab(1, show=True), size=17)
        self.lvl_btn = ibtn("bars", "Word levels in colour: A1 green · A2 cyan · B1 blue · B2 violet · C1 orange · C2 pink (K) — "
                                    "right-click to show only harder words", self.toggle_levels, checkable=True, size=17)
        self.lvl_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lvl_btn.customContextMenuRequested.connect(lambda _: self.level_menu())
        self.edit_btn = ibtn("edit", "Correct this subtitle line (E) — text and timing", lambda: self.edit_cue(), size=17)
        self.para_btn = ibtn("paraphrase", "Paraphrase this line (P): the same meaning said at A1, A2, B1, B2 and C1 — the teacher's "
                                           "A1 → C1, with translations. The video pauses; a line you paraphrased before opens at once.",
                             lambda: self.paraphrase_line(), size=17, color=theme.CYAN)
        self.rec_btn = ibtn("mic", "Record yourself and compare (Y): the line plays from the video, you say it, then you hear the "
                                   "original again and yourself right after it. Esc stops.", lambda: self.record_compare(), size=17,
                            color=theme.MAGENTA)
        for b in (self.size_btn, self.hide_btn, self.trl_btn, self.lvl_btn, self.rec_btn, self.para_btn, self.edit_btn, self.trs_btn):
            tools.addWidget(b)
        tools.addStretch(1)
        sl.addLayout(tools)
        v.addWidget(self.subs_frame)

        self.controls = QFrame(objectName="controls")
        cv = QVBoxLayout(self.controls)
        cv.setContentsMargins(14, 8, 16, 10)
        cv.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(ibtn("prev", "Previous line (↑)", lambda: self.jump_line(-1)))
        row.addWidget(ibtn("back5", "Back 5 seconds (←)", lambda: self.seek_rel(-5000), size=22))
        self.play_btn = ibtn("play", "Play / pause (Space)", self.toggle_play, kind="play", size=26, color="#FFFFFF")
        theme.glow(self.play_btn, theme.CYAN, 30, 150)
        row.addWidget(self.play_btn)
        row.addWidget(ibtn("fwd5", "Forward 5 seconds (→)", lambda: self.seek_rel(5000), size=22))
        row.addWidget(ibtn("next", "Next line (↓)", lambda: self.jump_line(1)))
        row.addSpacing(10)
        self.time_lbl = QLabel("0:00", objectName="time")
        self.dur_lbl = QLabel("0:00", objectName="time")
        self.slider = JumpSlider(Qt.Horizontal)
        self.slider.sliderMoved.connect(lambda p: self.player.setPosition(p))
        self.slider.setCursor(Qt.PointingHandCursor)
        row.addWidget(self.time_lbl)
        row.addWidget(self.slider, 1)
        row.addWidget(self.dur_lbl)
        row.addSpacing(6)
        self.vol_btn = ibtn("volume", "Mute / sound on (M) — the mouse wheel over the video changes the volume", self.toggle_mute, size=18)
        row.addWidget(self.vol_btn)
        self.vol_slider = JumpSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setFixedWidth(84)
        self.vol_slider.setToolTip("Volume")
        self.vol_slider.valueChanged.connect(self.set_volume)
        row.addWidget(self.vol_slider)
        self.speed_btn = QPushButton("1×", toolTip="Playback speed — slower speech helps: [ slower, ] faster")
        self.speed_btn.setProperty("kind", "chip")
        self.speed_btn.setMinimumWidth(64)
        self.speed_btn.clicked.connect(self.speed_menu)
        row.addWidget(self.speed_btn)
        cv.addLayout(row)

        ctl = QHBoxLayout()
        ctl.setSpacing(6)

        def chip(text, tip, fn, checkable=False, icon=None):
            b = ibtn(icon, tip, fn, checkable, 16, "chip", text) if icon else QPushButton(text, toolTip=tip, checkable=checkable)
            if not icon:
                b.setProperty("kind", "chip")
                b.clicked.connect(fn)
            b.setMinimumWidth(b.sizeHint().width())
            ctl.addWidget(b)
            return b

        self.a_btn = chip("A", "Loop start (key A)", self.set_a)
        self.b_btn = chip("B", "Loop end (key B) — repeats A→B until × / Esc", self.set_b)
        for b in (self.a_btn, self.b_btn):
            b.setFixedWidth(46)
        ctl.addWidget(ibtn("x", "Stop looping (Esc)", self.clear_ab, size=16))
        ctl.addSpacing(4)
        self.loop_btn = chip(" Loop line", "Repeat the current subtitle line (L)", self.toggle_loop_line, True, "repeat")
        self.rep_btn = chip("∞", "How often a loop repeats: until you stop it, or 2× / 3× / 5× — then it goes on "
                                 "(Loop line then moves to the next line: every line N times) (R)", self.cycle_repeat)
        self.rep_btn.setFixedWidth(46)
        self.pause_btn = chip(" Pause each line", "Stops after each sentence (a long one: after each part), waits so you can read, "
                                                  "then goes on by itself. Click a word to stay; Space goes on at once. "
                                                  "Right-click: how long it waits", self.toggle_pause_each, True, "pause")
        self.pause_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pause_btn.customContextMenuRequested.connect(lambda *_: self.pause_menu())
        self.shadow_btn = chip(" Shadowing", "Listen, then repeat aloud in the pause — the line plays again (S)", self.toggle_shadowing, True, "mic")
        self.part_btn = chip("", "How long a part is for Pause each line, Loop line and Shadowing: the whole sentence, or 1, 2 or 3 "
                                 "subtitle lines", self.part_menu)
        self._part_label()
        ctl.addSpacing(8)
        self.ab_lbl = QLabel("", objectName="ab")
        self.ab_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        ctl.addWidget(self.ab_lbl, 1)
        self.export_btn = chip(" Save clip", "Save the A→B part as a new video, with or without subtitles", self.export_dialog, False, "scissors")
        cv.addLayout(ctl)
        v.addWidget(self.controls)
        return w

    # ================================================================== startup / licence
    def _startup(self):
        theme.dark_title_bar(self)
        self.vol_slider.setValue(int(self.settings.get("volume", 90)))
        if self.settings.get("show_tr"):
            self.trl_btn.setChecked(True)
            self.show_tr = True
        if self.settings.get("show_levels"):
            self.lvl_btn.setChecked(True)
        QApplication.instance().installEventFilter(self)
        self._apply_sub_height()
        if self._broken:
            QTimer.singleShot(7000, lambda: self.msg(f"My Words: {self._broken} unreadable collocation line(s) from an escaped paste removed — "
                                                     "paste that answer again, it is read properly now", 14000))
        if self._colfixed:
            QTimer.singleShot(5000, lambda: self.msg(f"My Words: {self._colfixed} collocation line(s) pasted among the sentences moved to "
                                                     "Collocations", 12000))
        if self._merged:
            QTimer.singleShot(2500, lambda: self.msg(f"My Words: {self._merged} word(s) saved twice were joined into one entry "
                                                     "(their sentences kept)", 12000))
        left = self.lic.check_trial()
        if self.lic.holder is None and left <= 0:
            from .dialogs import ActivationDialog
            if not ActivationDialog(self, ended=True).exec() or self.lic.holder is None:
                QApplication.quit()
                return
        elif self.lic.holder is None:
            self.msg(f"Free trial · {left} of {licence.TRIAL_DAYS} days left — Settings › Buy / activate")
        if self.settings.get("sync_token"):
            QTimer.singleShot(1500, lambda: self.sync_now(silent=True))
        arg = next((a for a in sys.argv[1:] if os.path.isfile(a)), None)
        if arg:
            self.open_video(arg)
        self.refresh_words()
        self._fill_recents()
        if not self.settings.get("tour_done"):
            QTimer.singleShot(500, self.show_tour)

    def show_tour(self):
        from .dialogs import TourDialog
        TourDialog(self).exec()
        self.settings["tour_done"] = True
        self.save_settings()

    def msg(self, text: str, ms: int = 6000):
        self.statusBar().showMessage(text, ms)

    def save_settings(self):
        SETTINGS.write_text(json.dumps(self.settings, ensure_ascii=False, indent=1), encoding="utf-8")

    # ================================================================== pages
    def show_page(self, key: str, start: bool = True):
        idx = {"player": 0, "words": 1, "review": 2, "practice": 3, "discover": 4, "study": 5}[key]
        self.page = key
        for k, a in self.nav.items():
            a.setChecked(k == key)
        if key == "words":
            self.words_page.refresh()
        elif key == "review":
            self.review_page.start()
        elif key == "practice" and start:
            self.practice_page.start()
        elif key == "discover":
            self.discover_page.activate()
        if key != "review" and hasattr(self, "review_page"):
            self.review_page.stop_video()
        if key != "words" and hasattr(self, "words_page"):
            self.words_page.stop_video()
        if key != "player":
            # the video keeps playing in a small window while another page is open (✕ there pauses it)
            if self.video and self.player.playbackState() == QMediaPlayer.PlayingState and key not in ("review",):
                self.show_mini()
            elif key == "review":
                self.hide_mini()
                self.player.pause()
        else:
            self.hide_mini()
            self._fill_recents()
        self.stack.setCurrentIndex(idx)
        self.panel.setVisible(key == "player" and self.panel_open and not self.isFullScreen())
        self._update_motion()

    # ------------------------------------------------------------------ mini player
    def set_output(self, widget):
        """Moves the picture to another video widget. The video is paused for the switch and goes on afterwards: switching
        while it plays can hang the Windows video driver."""
        was = self.player.playbackState() == QMediaPlayer.PlayingState
        if was:
            self.player.pause()
        try:
            self.player.setVideoOutput(widget)
        except Exception as e:
            log_error("set_output", e)
        if was:
            QTimer.singleShot(250, self.player.play)

    def show_mini(self):
        if self.mini is None:
            self.mini = MiniPlayer(self)
        if not self.mini.isVisible():
            self.mini.place()
        self.mini.show()
        self.mini.raise_()
        self.set_output(self.mini.vw)

    def hide_mini(self):
        if self.mini is not None and self.mini.isVisible():
            self.mini.hide()
            self.set_output(self.vw)

    def mini_visible(self) -> bool:
        return self.mini is not None and self.mini.isVisible()

    def toggle_panel(self):
        self.panel_open = not self.panel.isVisible()
        self.panel.setVisible(self.panel_open and self.page == "player")
        self.panel_btn.setChecked(self.panel_open)

    def show_panel(self, card: bool = False):
        if card and hasattr(self, "panel_stack"):
            self.panel_tab(0)
        self.panel_open = True
        if self.page == "player" and not self.isFullScreen():
            self.panel.show()

    def _update_motion(self):
        playing = self.player.playbackState() == QMediaPlayer.PlayingState
        busy_video = playing
        self.cosmos.set_running(self.isActiveWindow() and not self.isMinimized() and not busy_video and not self.isFullScreen())

    # ================================================================== video
    def open_dialog(self):
        f, _ = QFileDialog.getOpenFileName(self, "Open a video", self.settings.get("last_dir", ""),
                                           "Videos (*.mp4 *.mkv *.webm *.mov *.avi *.m4v *.mp3 *.m4a *.wav);;All files (*)")
        if f:
            self.settings["last_dir"] = str(Path(f).parent)
            self.open_video(f)

    def recents(self) -> list:
        return [r for r in self.settings.get("recents", []) if isinstance(r, dict)]

    def remember_position(self):
        if not self.video:
            return
        rs = [r for r in self.recents() if r["path"] != self.video]
        rs.insert(0, {"path": self.video, "name": self.video_name, "pos": self.player.position(), "dur": self.player.duration()})
        self.settings["recents"] = rs[:30]
        self.save_settings()

    def show_recent(self):
        m = QMenu(self)
        for r in self.recents()[:15]:
            if os.path.exists(r["path"]):
                m.addAction(icons.icon("film", theme.CYAN, 16), f"{r['name']}   ·  {fmt(r.get('pos', 0))}",
                            lambda p=r["path"]: self.open_video(p))
        if m.isEmpty():
            m.addAction("No recent videos").setEnabled(False)
        btn = getattr(self, "recent_btn", None)
        m.exec(btn.mapToGlobal(btn.rect().bottomLeft()) if btn else self.cursor().pos())

    def open_video(self, path: str, at_ms: int | None = None, play: bool = True, switch: bool = True):
        if self.video and self.video != path:
            self.remember_position()
        self.video = path
        self.video_name = Path(path).name
        self.player.setSource(QUrl.fromLocalFile(path))
        self.clear_ab()
        self.cues = []
        self.sub_offset = int(self.settings.get("sub_offsets", {}).get(subtitles.video_key(self.video_name), 0))
        self.repeat_done = 0
        self.pstack.setCurrentIndex(1)
        self._load_subs_for_video()
        pos = at_ms if at_ms is not None else next((r.get("pos", 0) for r in self.recents() if r["path"] == path), 0)
        if pos > 0:
            QTimer.singleShot(400, lambda: self.player.setPosition(pos))
        if play:
            self.player.play()
        self.setWindowTitle(f"SubPlayer — {self.video_name}")
        self.title_lbl.setText(Path(path).stem)
        self.remember_position()
        if switch:
            self.show_page("player")

    def srt_path(self, lang: str) -> Path:
        return syncer.subs_dir() / f"{subtitles.video_key(self.video_name)}.{lang}.srt"

    def _load_subs_for_video(self):
        for lang in ("de", "en"):
            f = self.srt_path(lang)
            if f.exists():
                self.set_cues(subtitles.parse(f.read_text(encoding="utf-8")), lang, f"Saved {self.lang_name(lang)} subtitles")
                return
        side = Path(self.video).with_suffix(".srt")
        if side.exists():
            self.set_cues(subtitles.parse(side.read_text(encoding="utf-8", errors="replace")), self.settings.get("sub_lang", "de"),
                          "Subtitles from the .srt next to the video")
            return
        self.sub_view.setHtml(f"<p style='color:{theme.DIM};text-align:center;font-size:12pt;margin-top:22px'>No subtitles yet — "
                              f"<b style='color:{theme.CYAN}'>Subtitles</b> makes them, <b style='color:{theme.CYAN}'>Subtitle file</b> "
                              "loads an .srt.</p>")

    @staticmethod
    def lang_name(lang: str) -> str:
        return {"de": "German", "en": "English"}.get(lang, lang)

    def set_cues(self, cues, lang, info=""):
        self.cues, self.cue_lang = cues, lang
        self.held_cue = -1
        self.pe_last, self.pe_resume = -1, 0
        self._shown = None
        self._fill_transcript()
        if self._load_translations() and not self.show_tr:
            self.msg("This video has a saved translation — the translate button beside the subtitle shows it", 8000)
        if info:
            self.msg(f"{info} · {len(cues)} lines")

    def toggle_play(self):
        if not self.video:
            self.open_dialog()
            return
        self.pe_resume = 0
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.shadow_resume = 0
        else:
            if self.held_cue >= 0:
                self.held_cue = -1
            self.shadow_resume = 0
            self.player.play()

    def seek_rel(self, d):
        self.pe_last, self.pe_resume = -1, 0
        self.player.setPosition(max(0, self.player.position() + d))

    def jump_line(self, step):
        if not self.cues:
            self.seek_rel(5000 * step)
            return
        pos = self.cpos()
        i = subtitles.index_before(self.cues, pos)
        if step < 0 and i >= 0 and pos - self.cues[i].start_ms > 1200:
            j = i
        else:
            j = max(0, min(len(self.cues) - 1, i + step))
        self.held_cue = -1
        self.pe_last, self.pe_resume = -1, 0
        self.repeat_done = 0
        if self.loop_line or self.shadowing:          # ↑ / ↓ move a whole part
            cur = self.parts()[max(i, 0)]
            if step > 0:
                j = min(len(self.cues) - 1, cur[1] + 1)
            elif step < 0 and i >= 0 and pos - self.cues[cur[0]].start_ms <= 1200:
                j = max(0, cur[0] - 1)
            else:
                j = cur[0]
            ja, jb = self.parts()[j]
            j = ja
            self.a, self.b = self.cues[ja].start_ms + self.sub_offset, self.cues[jb].end_ms + self.sub_offset + 150
            self._ab_label()
        self.player.setPosition(self.cues[j].start_ms + self.sub_offset)
        self.player.play()

    def speed_menu(self):
        m = QMenu(self)
        cur = round(self.player.playbackRate(), 2)
        for r in SPEEDS:
            a = m.addAction(("✓  " if abs(r - cur) < 0.01 else "     ") + f"{r:g}×" + ("  normal" if r == 1 else ""))
            a.triggered.connect(lambda _=False, x=r: self.set_speed(x))
        m.exec(self.speed_btn.mapToGlobal(self.speed_btn.rect().topLeft()) - m.sizeHint().height() * QPoint(0, 1))

    def step_speed(self, d):
        cur = round(self.player.playbackRate(), 2)
        i = min(range(len(SPEEDS)), key=lambda k: abs(SPEEDS[k] - cur))
        self.set_speed(SPEEDS[max(0, min(len(SPEEDS) - 1, i + d))])

    def set_speed(self, r: float):
        self.player.setPlaybackRate(r)
        self.speed_btn.setText(f"{r:g}×")
        self.speed_btn.setProperty("accent", r < 1)
        theme.repolish(self.speed_btn)
        self.msg(f"Speed {r:g}×")

    # ------------------------------------------------------------------ volume
    def set_volume(self, v: int):
        self.audio.setVolume(v / 100)
        if v and self.audio.isMuted():
            self.audio.setMuted(False)
        self.settings["volume"] = v
        self._vol_icon()

    def toggle_mute(self):
        self.audio.setMuted(not self.audio.isMuted())
        self._vol_icon()
        self.msg("Sound off" if self.audio.isMuted() else "Sound on")

    def _vol_icon(self):
        off = self.audio.isMuted() or self.vol_slider.value() == 0
        self.vol_btn.setIcon(icons.icon("mute" if off else "volume", theme.MAGENTA if off else theme.LIGHT, 18))

    def _video_wheel(self, e):
        self.vol_slider.setValue(self.vol_slider.value() + (5 if e.angleDelta().y() > 0 else -5))

    # ------------------------------------------------------------------ subtitle options
    def subtitle_options(self):
        m = QMenu(self)
        cur = self.settings.get("sub_size", 21)
        m.addSection("Text size")
        for name, pt in SUB_SIZES.items():
            a = m.addAction(("✓  " if pt == cur else "     ") + name)
            a.triggered.connect(lambda _=False, x=pt: self.set_sub_size(x))
        m.addSection(f"Timing — now {self.sub_offset / 1000:+.1f} s")
        m.addAction("Subtitles earlier  (G)   −0.1 s", lambda: self.shift_subs(-100))
        m.addAction("Subtitles later  (H)   +0.1 s", lambda: self.shift_subs(100))
        m.addAction("Subtitles earlier   −1 s", lambda: self.shift_subs(-1000))
        m.addAction("Subtitles later   +1 s", lambda: self.shift_subs(1000))
        r = m.addAction("Reset timing", lambda: self.shift_subs(-self.sub_offset))
        r.setEnabled(self.sub_offset != 0)
        m.addSection("Translation line")
        tgt = self.settings.get("tr_target", "en")
        for key, label in (("en", "English  (German for English videos)"), ("fa", "فارسی — Persian")):
            a = m.addAction(("✓  " if key == tgt else "     ") + label)
            a.triggered.connect(lambda _=False, k=key: self.set_tr_target(k))
        m.exec(self.size_btn.mapToGlobal(self.size_btn.rect().topLeft()) - m.sizeHint().height() * QPoint(0, 1))

    def set_sub_size(self, pt: int):
        self.settings["sub_size"] = pt
        self.save_settings()
        self._apply_sub_height()
        self._shown = None

    def step_sub_size(self, d):
        sizes = sorted(SUB_SIZES.values())
        cur = self.settings.get("sub_size", 21)
        i = min(range(len(sizes)), key=lambda k: abs(sizes[k] - cur))
        self.set_sub_size(sizes[max(0, min(len(sizes) - 1, i + d))])

    def _apply_sub_height(self):
        pt = self.settings.get("sub_size", 21)
        lines = 2 + (1 if self.show_tr else 0)
        self.sub_view.setFixedHeight(int(pt * 2.05 * lines + 22))

    def shift_subs(self, d: int):
        if not self.cues:
            self.msg("Load subtitles first — then G / H move them earlier / later")
            return
        self.sub_offset += d
        offs = self.settings.setdefault("sub_offsets", {})
        key = subtitles.video_key(self.video_name)
        if self.sub_offset:
            offs[key] = self.sub_offset
        else:
            offs.pop(key, None)
        self.save_settings()
        self._shown = None
        self.msg(f"Subtitle timing {self.sub_offset / 1000:+.1f} s  (G earlier · H later)" if self.sub_offset else "Subtitle timing reset")

    def cpos(self) -> int:
        """The video position on the subtitles' clock."""
        return self.player.position() - self.sub_offset

    def toggle_hide_text(self):
        self.hide_text = self.hide_btn.isChecked()
        self.hide_btn.setIcon(icons.icon("eye_off" if self.hide_text else "eye", theme.CYAN if self.hide_text else theme.LIGHT, 17))
        self._shown = None
        self.msg("Listening mode: the text hides while the video plays and shows when you pause" if self.hide_text
                 else "Subtitles always visible")

    def toggle_translation_line(self):
        self.show_tr = self.trl_btn.isChecked()
        self.settings["show_tr"] = self.show_tr
        self._apply_sub_height()
        self._shown = None
        if self.show_tr:
            self.msg("Translation line on (online) — " + ("Persian" if self.settings.get("tr_target") == "fa" else "English")
                     + " · change it with the Aa button")

    def set_tr_target(self, k):
        self.settings["tr_target"] = k
        self.save_settings()
        if not self.show_tr:
            self.trl_btn.setChecked(True)
            self.toggle_translation_line()
        self._shown = None

    def _tr_target(self) -> str:
        t = self.settings.get("tr_target", "en")
        if t == "en" and self.cue_lang == "en":
            return "de"
        return t

    PARTS = (("sentence", "Whole sentence"), ("1", "1 subtitle line"), ("2", "2 subtitle lines"), ("3", "3 subtitle lines"))

    def part_menu(self):
        m = QMenu(self)
        m.addSection("A part (Pause each line · Loop line · Shadowing)")
        cur = self.settings.get("part", "sentence")
        for k, label in self.PARTS:
            a = m.addAction(label, lambda k=k: self.set_part(k))
            a.setCheckable(True)
            a.setChecked(k == cur)
        m.exec(QCursor.pos())

    def set_part(self, k: str):
        self.settings["part"] = k
        self.save_settings()
        self._part_label()
        self._parts_key = None
        if (self.loop_line or self.shadowing) and self.a >= 0:       # the running loop takes the new length at once
            self._loop_current_line()
            self._ab_label()
        self.msg("A part is now: " + dict(self.PARTS)[k].lower() + " (the translation stays by whole sentence)")

    def _part_label(self):
        k = self.settings.get("part", "sentence")
        self.part_btn.setText("⟷ " + ("Sentence" if k == "sentence" else f"{k} line" + ("s" if k != "1" else "")))
        self.part_btn.setMinimumWidth(self.part_btn.sizeHint().width())

    def parts(self) -> list[tuple[int, int]]:
        """For every line, the part it belongs to — the whole sentence or the chosen number of lines (Pause each line, Loop line,
        Shadowing)."""
        k = self.settings.get("part", "sentence")
        key = (id(self.cues), len(self.cues), getattr(self, "_cue_rev", 0), k)
        if getattr(self, "_parts_key", None) != key:
            self._parts_key = key
            if k == "sentence":
                self._parts = self.units()
            else:
                n = int(k)                               # n lines at a time, never across the end of a sentence
                out = [(0, 0)] * len(self.cues)
                for a, b in sorted(set(self.units())):
                    for p0 in range(a, b + 1, n):
                        p1 = min(b, p0 + n - 1)
                        for x in range(p0, p1 + 1):
                            out[x] = (p0, p1)
                self._parts = out
        return self._parts

    def units(self) -> list[tuple[int, int]]:
        """For every subtitle line, the whole sentence it belongs to (first and last line) — translations and Pause each
        line work on sentences, not on the pieces the subtitle cut them into."""
        k = (id(self.cues), len(self.cues), getattr(self, "_cue_rev", 0))
        if self._units_key != k:
            self._units_key, self._units = k, subtitles.sentence_ranges(self.cues)
        return self._units

    def unit_text(self, i: int) -> str:
        a, b = self.units()[i]
        return " ".join(subtitles.sentence_text(self.cues, a, b).split())

    def _want_translation(self, i: int):
        if i < 0 or i >= len(self.cues):
            return
        tgt = self._tr_target()
        text = self.unit_text(i)                          # the whole sentence, so the translation makes sense
        key = (text, self.cue_lang, tgt)
        if key in self.tr_cache or key in self.tr_pending:
            return
        self.tr_pending.add(key)

        def work():
            try:
                out, _ = translate.translate(text, self.cue_lang, tgt)
            except Exception:
                out = None
            self.bus.done.emit("trline", (key, out))
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------ repeat count
    def cycle_repeat(self):
        i = REPEATS.index(self.repeat_n) if self.repeat_n in REPEATS else 0
        self.repeat_n = REPEATS[(i + 1) % len(REPEATS)]
        self.repeat_done = 0
        self.rep_btn.setText("∞" if not self.repeat_n else f"{self.repeat_n}×")
        self.rep_btn.setProperty("accent", bool(self.repeat_n))
        theme.repolish(self.rep_btn)
        self.msg("Loops repeat until you stop them" if not self.repeat_n else
                 f"Loops play {self.repeat_n}× — then go on (Loop line: every line {self.repeat_n}×, then the next)")

    def _loop_finished(self) -> bool:
        """Called at the end of each loop pass; True when the repeat count is reached and playback moved on."""
        self.repeat_done += 1
        if not self.repeat_n or self.repeat_done < self.repeat_n:
            return False
        self.repeat_done = 0
        if (self.loop_line or self.shadowing) and self.cues:
            i = subtitles.index_before(self.cues, self.a - self.sub_offset + 50)
            nxt = self.parts()[i][1] + 1 if i >= 0 else 0
            if nxt < len(self.cues):
                a, b = self.parts()[nxt]
                self.a, self.b = self.cues[a].start_ms + self.sub_offset, self.cues[b].end_ms + self.sub_offset + 150
                self.player.setPosition(self.a)
                self._ab_label()
                return True
        self.clear_ab()
        self.msg(f"Played {self.repeat_n}× — going on")
        return True

    # ------------------------------------------------------------------ transcript
    def panel_tab(self, i: int, show: bool = False):
        self.panel_stack.setCurrentIndex(i)
        self.tab_card.setChecked(i == 0)
        self.tab_tr.setChecked(i == 1)
        if show:
            self.show_panel()
        if i == 1:
            self._tr_scrolled_at = 0.0
            if 0 <= self._tr_idx < self.transcript.count():
                self._tr_auto = True
                self.transcript.scrollToItem(self.transcript.item(self._tr_idx), QListWidget.PositionAtCenter)
                self._tr_auto = False

    def _fill_transcript(self):
        self.transcript.clear()
        self._tr_idx = -1
        for k, c in enumerate(self.cues):
            it = QListWidgetItem(f"{fmt(c.start_ms)}   {' '.join(c.text.split())}")
            it.setData(Qt.UserRole, k)
            self.transcript.addItem(it)
        self.tr_info.setText(f"{len(self.cues)} lines · click = jump · double-click = loop that line" if self.cues
                             else "No subtitles yet.")
        if self.tr_search.text():
            self._filter_transcript(self.tr_search.text())

    def _filter_transcript(self, q: str):
        q = q.strip().lower()
        n = 0
        for r in range(self.transcript.count()):
            it = self.transcript.item(r)
            hide = bool(q) and q not in it.text().lower()
            it.setHidden(hide)
            n += not hide
        if q:
            self.tr_info.setText(f"{n} of {self.transcript.count()} lines contain “{q}”")

    def _transcript_scrolled(self, _):
        if not self._tr_auto:
            self._tr_scrolled_at = time.monotonic()

    def _transcript_click(self, it):
        k = it.data(Qt.UserRole)
        if k is None or not (0 <= k < len(self.cues)):
            return
        self.held_cue = -1
        self.pe_last, self.pe_resume = -1, 0
        self.repeat_done = 0
        if self.loop_line or self.shadowing:
            self.a, self.b = self.cues[k].start_ms + self.sub_offset, self.cues[k].end_ms + self.sub_offset + 150
            self._ab_label()
        self.player.setPosition(self.cues[k].start_ms + self.sub_offset)
        self.player.play()

    def _transcript_loop(self, it):
        k = it.data(Qt.UserRole)
        if k is None:
            return
        self.player.setPosition(self.cues[k].start_ms + self.sub_offset)
        if not self.loop_btn.isChecked():
            self.loop_btn.setChecked(True)
        self.loop_line = True
        self.repeat_done = 0
        self.a, self.b = self.cues[k].start_ms + self.sub_offset, self.cues[k].end_ms + self.sub_offset + 150
        self._ab_label()
        self.player.play()

    def _transcript_follow(self, i: int):
        if i == self._tr_idx or i < 0 or i >= self.transcript.count():
            return
        prev = self.transcript.item(self._tr_idx) if 0 <= self._tr_idx < self.transcript.count() else None
        if prev:
            prev.setForeground(QColor(theme.LIGHT))
            f = prev.font(); f.setBold(False); prev.setFont(f)
        it = self.transcript.item(i)
        it.setForeground(QColor(theme.CYAN))
        f = it.font(); f.setBold(True); it.setFont(f)
        self._tr_idx = i
        if time.monotonic() - self._tr_scrolled_at > 4 and self.panel.isVisible() and self.panel_stack.currentIndex() == 1:
            self._tr_auto = True
            self.transcript.scrollToItem(it, QListWidget.PositionAtCenter)
            self._tr_auto = False

    def set_a(self):
        self.repeat_done = 0
        self.a = self.player.position()
        if self.b >= 0 and self.b <= self.a:
            self.b = -1
        self._ab_label()

    def set_b(self):
        self.repeat_done = 0
        if self.a < 0:
            self.a = 0
        p = self.player.position()
        if p > self.a + 300:
            self.b = p
            self.player.setPosition(self.a)
            self.player.play()
        self._ab_label()

    def clear_ab(self):
        self.repeat_done = 0
        self.a = self.b = -1
        self.loop_line = False
        self.shadowing = False
        self.shadow_resume = 0
        if hasattr(self, "loop_btn"):
            self.loop_btn.setChecked(False)
            self.shadow_btn.setChecked(False)
            self._ab_label()

    def _ab_label(self):
        if self.shadow_resume:
            t = "🎙 Your turn — say it aloud"
        elif self.a >= 0 and self.b >= 0:
            t = ("Shadowing " if self.shadowing else "Looping ") + f"{fmt(self.a)} → {fmt(self.b)}"
        elif self.a >= 0:
            t = f"A = {fmt(self.a)} · now set B"
        else:
            t = ""
        self.ab_lbl.setText(t)
        self.a_btn.setProperty("accent", self.a >= 0)
        self.b_btn.setProperty("accent", self.b >= 0)
        self.export_btn.setEnabled(self.a >= 0 and self.b > self.a)
        theme.repolish(self.a_btn, self.b_btn)

    def _loop_current_line(self) -> bool:
        if not self.cues:
            return False
        i = subtitles.index_before(self.cues, self.cpos())
        if i < 0:
            i = 0
        a, b = self.parts()[i]                          # the whole sentence, or the chosen number of lines
        self.a, self.b = self.cues[a].start_ms + self.sub_offset, self.cues[b].end_ms + self.sub_offset + 150
        self.repeat_done = 0
        return True

    def toggle_loop_line(self):
        self.loop_line = self.loop_btn.isChecked()
        if self.loop_line:
            if not self._loop_current_line():
                self.msg("Loop line needs subtitles — use A and B instead")
                self.loop_btn.setChecked(False)
                self.loop_line = False
        elif not self.shadowing:
            self.a = self.b = -1
        self._ab_label()

    PAUSE_WAITS = (("auto", "As long as the sentence took (1.5–8 s)"), ("2", "2 seconds"), ("4", "4 seconds"), ("6", "6 seconds"),
                   ("10", "10 seconds"), ("space", "Until I press Space"))

    def toggle_pause_each(self):
        self.pause_each = self.pause_btn.isChecked()
        self.pe_last, self.pe_resume = -1, 0
        if self.pause_each:
            self.shadowing = False
            self.shadow_btn.setChecked(False)
            self.shadow_resume = 0
            w = self.settings.get("pause_wait", "auto")
            self.msg("Pauses after each sentence, then goes on by itself (right-click the button: how long)" if w != "space" else
                     "Pauses after each sentence — Space goes on", 8000)
        self._ab_label()

    def pause_menu(self):
        m = QMenu(self)
        cur = self.settings.get("pause_wait", "auto")
        m.addSection("Pause each line: wait")
        for k, label in self.PAUSE_WAITS:
            a = m.addAction(label, lambda k=k: (self.settings.__setitem__("pause_wait", k), self.save_settings()))
            a.setCheckable(True)
            a.setChecked(k == cur)
        m.exec(QCursor.pos())

    def _pause_wait(self, a: int, b: int):
        """Seconds to wait after a sentence (cues a..b) before going on; None = wait for Space."""
        w = self.settings.get("pause_wait", "auto")
        if w == "space":
            return None
        if w == "auto":
            took = (self.cues[b].end_ms - self.cues[a].start_ms) / 1000 / max(0.25, self.player.playbackRate())
            return max(1.5, min(8.0, took * 0.8))
        try:
            return float(w)
        except ValueError:
            return 3.0

    def toggle_shadowing(self):
        self.shadowing = self.shadow_btn.isChecked()
        self.shadow_resume = 0
        if self.shadowing:
            self.pause_each = False
            self.pause_btn.setChecked(False)
            if not (self.a >= 0 and self.b > self.a) and not self._loop_current_line():
                self.msg("Shadowing needs a line: load subtitles, or set A and B")
                self.shadow_btn.setChecked(False)
                self.shadowing = False
                return
            self.msg("Shadowing: listen, then repeat aloud in the pause. ↓ moves to the next line.", 9000)
            if self.player.playbackState() != QMediaPlayer.PlayingState:
                self.player.setPosition(self.a)
                self.player.play()
        elif not self.loop_line:
            self.a = self.b = -1
        self._ab_label()

    def _escape(self):
        if getattr(self, "comparer", None) is not None and self.comparer.busy:
            self.comparer.cancel()
        elif self.isFullScreen():
            self.toggle_fullscreen()
        else:
            self.clear_ab()

    def toggle_fullscreen(self):
        full = not self.isFullScreen()
        for w in (self.findChild(QFrame, "rail"), self.topbar, self.statusBar()):
            w.setVisible(not full)
        if full:
            self.panel.hide()
            self.showFullScreen()
        else:
            self.showNormal()
            self.panel.setVisible(self.page == "player" and self.panel_open)
        self._update_motion()

    # ------------------------------------------------------------------ ticker
    def _tick(self):
        pos = self.player.position()
        dur = self.player.duration()
        if not self.slider.isSliderDown():
            self.slider.setValue(pos)
        self.time_lbl.setText(fmt(pos))
        self.dur_lbl.setText(fmt(dur))
        playing = self.player.playbackState() == QMediaPlayer.PlayingState
        if playing != self._playing:
            self._playing = playing
            self.play_btn.setIcon(icons.icon("pause" if playing else "play", "#FFFFFF", 26))
            self._update_motion()
        if getattr(self, "comparer", None) is not None and self.comparer.busy:
            return                                         # record & compare drives the player now (loops, pauses wait)
        if self.shadow_resume and time.monotonic() >= self.shadow_resume:
            self.shadow_resume = 0
            if not self._loop_finished() and self.a >= 0:
                self.player.setPosition(self.a)
            self.player.play()
            self._ab_label()
        if playing and self.a >= 0 and self.b > self.a and pos >= self.b:
            if self.shadowing:
                self.player.pause()
                self.shadow_resume = time.monotonic() + (self.b - self.a) * 1.2 / 1000 + 0.6
                self._ab_label()
            elif not self._loop_finished():
                self.player.setPosition(self.a)
            return
        cp = pos - self.sub_offset
        i = subtitles.index_at(self.cues, cp) if self.cues else -1
        if self.pe_resume and time.monotonic() >= self.pe_resume:
            self.pe_resume = 0
            if self.pause_each and not playing:
                self.held_cue = -1
                self.player.play()
                playing = True
        if playing and self.pause_each and self.cues:
            j = subtitles.index_before(self.cues, cp)
            if j >= 0 and cp < self.cues[j].end_ms - 60:
                self.pe_inside = j                          # the line being played
            if j >= 0 and j != self.pe_last and cp >= self.cues[j].end_ms - 60:
                self.pe_last = j                            # each line is looked at once
                a, b = self.parts()[j]
                # the end of a sentence (or of a part of a long one) that was played through — not a seek past it
                if j == b and getattr(self, "pe_inside", -1) == j:
                    self.held_cue = j
                    self.player.pause()
                    playing = False
                    i = j
                    wait = self._pause_wait(a, b)
                    self.pe_resume = time.monotonic() + wait if wait else 0
                    if wait:
                        self.msg(f"Next sentence in {wait:.0f} s — click a word to stay here, Space to go on now", int(wait * 1000))
        if i < 0 and not playing and self.held_cue >= 0:
            i = self.held_cue
        if i < 0 and self.shadowing and self.cues and self.a >= 0:
            i = subtitles.index_before(self.cues, self.a - self.sub_offset + 50)
        if i < 0 and self.card and not playing and self.card.get("cue", -1) >= 0:
            i = self.card["cue"]
        if self.cues and self.panel_stack.currentIndex() == 1 and self.panel.isVisible():
            self._transcript_follow(i if i >= 0 else subtitles.index_before(self.cues, cp))
        if self.show_tr and i >= 0:
            self._want_translation(i)
            self._want_translation(self.units()[i][1] + 1)     # the next sentence, ready before it is needed
        masked = self.hide_text and playing
        key = (i, len(self.cues), self._saved_version(), masked, self.show_tr, self.settings.get("sub_size", 21),
               self.lvl_btn.isChecked(), self.settings.get("level_min", 1), getattr(self, "_cue_rev", 0),
               self._tr_key(i) in self.tr_cache if self.show_tr and i >= 0 else None, self._held_sentence(i))
        if getattr(self, "_shown", None) != key:
            self._shown = key
            self._render_sub(i)
        if self.mini is not None and self.mini.isVisible():
            self.mini.update_state(playing, self.cues[i].text if 0 <= i < len(self.cues) and not masked else "")

    def _held_sentence(self, i: int) -> bool:
        """True while Pause each line holds at the end of a sentence of more than one line."""
        if not (self.pause_each and i >= 0 and i == self.held_cue and i < len(self.cues)):
            return False
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            return False
        a, b = self.parts()[i]
        return b > a

    def _tr_key(self, i: int):
        return (self.unit_text(i), self.cue_lang, self._tr_target())

    _saved_cache: tuple = (0, set())

    def _saved_version(self):
        return self._saved_cache[0]

    def refresh_words(self):
        words = self.store.all()
        self._saved_cache = (self._saved_cache[0] + 1, {w.text.lower() for w in words} | {w.lemma.lower() for w in words})
        self._shown = None
        now = now_ms()
        due = sum(1 for w in words if w.due <= now)
        self.due_badge.setText(f"{due} due" if due else "")
        self.due_badge.setVisible(bool(due))
        try:
            nd = len(self.store.due_notes(now_ms()))
            self.notebook_btn.setText(f"Notebook · {nd}" if nd else "Notebook")
        except Exception:
            pass
        s = self.progress.streak
        self.streak_lbl.setText(f"🔥 {s} day{'s' if s != 1 else ''}" if s else "")

    def _render_sub(self, i: int):
        pt = self.settings.get("sub_size", 21)
        if i < 0:
            self.sub_view.setHtml("")
            return
        text = self.cues[i].text
        if self.hide_text and self.player.playbackState() == QMediaPlayer.PlayingState:
            dots = " ".join("•" * min(6, max(2, len(t[2]) // 2)) for t in subtitles.tokens(text))
            self.sub_view.setHtml(f"<div style='text-align:center;font-size:{pt}pt;color:#4E4A72;letter-spacing:2px;"
                                  f"line-height:145%'>{dots}</div><div style='text-align:center;color:{theme.DIM};font-size:9pt'>"
                                  "listening mode — pause (Space) to read</div>")
            return
        saved = self._saved_cache[1]
        show_lv = self.lvl_btn.isChecked()
        lv_min = self.settings.get("level_min", 1)
        d = self.dictionary(self.cue_lang) if show_lv else None
        out = []
        lines = [i]
        if self._held_sentence(i):                       # Pause each line stopped here: the whole part, every word clickable
            a, b = self.parts()[i]
            lines = list(range(a, b + 1))
        for ci in lines:
            text, last = self.cues[ci].text, 0
            if len(lines) > 1:
                text = " ".join(text.split())
                if ci != lines[0]:
                    out.append(" ")
            for k, (s, e, tok) in enumerate(subtitles.tokens(text)):
                out.append(html.escape(text[last:s]).replace("\n", "<br>"))
                deco = "none"
                if show_lv:
                    lv = self.levels.level(tok, self.cue_lang, d)
                    col = LV_COLORS[lv] if lv >= lv_min else "#FFFFFF"
                    if tok.lower() in saved:
                        deco = "underline"
                else:
                    col = theme.GOLD if tok.lower() in saved else "#FFFFFF"
                if self.phrase_start and self.phrase_start[0] == ci and self.phrase_start[1] == k:
                    col = theme.MAGENTA
                out.append(f"<a href='w:{ci}:{k}' style='color:{col};text-decoration:{deco}'>{html.escape(tok)}</a>")
                last = e
            out.append(html.escape(text[last:]).replace("\n", "<br>"))
        body = f"<div style='text-align:center;font-size:{pt}pt;font-weight:600;line-height:145%'>{''.join(out)}</div>"
        if show_lv and not self.show_tr:
            body += ("<div style='text-align:center;font-size:8pt'>" + " ".join(
                f"<span style='color:{LV_COLORS[n]}'>■ {LV_NAMES[n]}</span>" for n in range(max(1, lv_min), 7)) +
                (" <span style='color:#7F7A9E'>· word list + estimate</span>" if self.cue_lang == "de" else "") + "</div>")
        if self.show_tr:
            tr = self.tr_cache.get(self._tr_key(i), "…")
            if tr is None:
                tr = "(translation needs internet)"
            small = max(11, int(pt * 0.62))
            if self._tr_target() == "fa":
                body += (f"<div dir='rtl' style='text-align:center;font-family:{theme.FA_FONT};font-size:{small + 1}pt;"
                         f"color:{theme.CYAN}'>{html.escape(tr)}</div>")
            elif tr in ("…", "(translation needs internet)"):
                body += f"<div style='text-align:center;font-size:{small}pt;color:{theme.CYAN};font-style:italic'>{html.escape(tr)}</div>"
            else:
                # German or English translation: every word can be clicked and learnt like a subtitle word
                saved_tr = self._saved_cache[1]
                parts, last = [], 0
                for k, (s0, e0, tok) in enumerate(subtitles.tokens(tr)):
                    parts.append(html.escape(tr[last:s0]))
                    col = theme.GOLD if tok.lower() in saved_tr else theme.CYAN
                    parts.append(f"<a href='t:{i}:{k}' style='color:{col};text-decoration:none'>{html.escape(tok)}</a>")
                    last = e0
                parts.append(html.escape(tr[last:]))
                body += (f"<div style='text-align:center;font-size:{small}pt;color:{theme.CYAN};font-style:italic'>"
                         f"{''.join(parts)}</div>")
        self.sub_view.setHtml(body)

    # ================================================================== words in subtitles
    def _sub_click(self, url: QUrl):
        s = url.toString()
        if s.startswith("t:"):
            self._tr_click(s)
            return
        if not s.startswith("w:"):
            return
        _, ci, ti = s.split(":")
        ci, ti = int(ci), int(ti)
        toks = subtitles.tokens(self.cues[ci].text)
        word = toks[ti][2]
        mods = QApplication.keyboardModifiers()
        self.player.pause()
        self.shadow_resume = 0
        self.pe_resume = 0
        a, b = subtitles.sentence_range(self.cues, ci)
        sentence = subtitles.sentence_text(self.cues, a, b)
        start, end = self.cues[a].start_ms + self.sub_offset, self.cues[b].end_ms + self.sub_offset
        if mods & Qt.ControlModifier:
            self.open_phrase(sentence, sentence, start, end, whole=True)
        elif mods & Qt.ShiftModifier:
            if self.phrase_start and self.phrase_start[0] == ci:
                lo, hi = sorted((self.phrase_start[1], ti))
                phrase = " ".join(t[2] for t in toks[lo:hi + 1]) if hi > lo else word
                self.phrase_start = None
                self.open_phrase(phrase, sentence, start, end)
            else:
                self.phrase_start = (ci, ti)
                self.msg("Phrase: now Shift+click the last word")
        else:
            self.phrase_start = None
            self.open_word(word, sentence, start, end, cue=ci)
        self._shown = None

    def _tr_click(self, s: str):
        """A word of the translation line (German under an English video, or English under a German one): its word card in
        that language, with the translated line as the sentence and the video moment of the subtitle line."""
        _, ci, ti = s.split(":")
        ci, ti = int(ci), int(ti)
        tr = self.tr_cache.get(self._tr_key(ci)) or ""
        toks = subtitles.tokens(tr)
        if ti >= len(toks):
            return
        self.player.pause()
        self.shadow_resume = 0
        self.pe_resume = 0
        self.phrase_start = None
        lang = self._tr_target()
        a, b = self.units()[ci]
        start, end = self.cues[a].start_ms + self.sub_offset, self.cues[b].end_ms + self.sub_offset
        self.open_word(toks[ti][2], tr, start, end, lang=lang, cue=ci)
        self._shown = None

    def dictionary(self, lang: str) -> Dictionary | None:
        if lang in self.dicts:
            return self.dicts[lang]
        a = downloads.DICT_EN if lang == "en" else downloads.DICT_DE
        if not downloads.is_ready(a):
            return None
        self.dicts[lang] = Dictionary(downloads.ready_path(a))
        return self.dicts[lang]

    def open_word(self, raw: str, sentence: str = "", start: int = -1, end: int = -1, lang: str | None = None, cue: int = -1):
        lang = lang or self.cue_lang
        word = normalize(raw)
        self.card = {"kind": "word", "word": word, "sentence": sentence, "start": start, "end": end, "lang": lang, "cue": cue,
                     "entries": [], "fa_online": None}
        self.show_panel(card=True)
        d = self.dictionary(lang)
        if d is None:
            a = downloads.DICT_EN if lang == "en" else downloads.DICT_DE
            self._card_html(f"<h1>{html.escape(word)}</h1><table width='100%' cellpadding='14' style='background:{theme.CARD};"
                            f"border-radius:12px'><tr><td><b>{a.label} not downloaded yet</b><br>About {a.size_mb} MB, once. "
                            f"Then every word works offline.<br><br><a href='dl:{lang}' style='color:{theme.CYAN}'>⬇ Download "
                            f"{a.label.lower()}</a></td></tr></table>")
            self._update_save_btn()
            return
        entries = d.lookup(raw)
        if not entries and lang == "de" and self.dictionary("en"):
            entries = self.dictionary("en").lookup(raw)          # other language as a fallback
            if entries:
                self.card["lang"] = "en"
        if not entries and lang == "en" and self.dictionary("de"):
            entries = self.dictionary("de").lookup(raw)
            if entries:
                self.card["lang"] = "de"
        self.card["entries"] = entries
        self._render_card()

    def _render_card(self):
        c = self.card
        if not c:
            return
        if c["kind"] == "phrase":
            return self._render_phrase()
        h = []
        lang = c["lang"]
        if not c["entries"]:
            h.append(f"<p style='font-size:22pt;font-weight:800;margin:0'>{html.escape(c['word'])}</p>"
                     f"<p style='color:{theme.DIM}'>Not in the offline dictionary (names and rare words may be missing).</p>"
                     f"<p><a href='uses:' style='color:{theme.CYAN};text-decoration:none'>🔎 Where else is it used in my videos?</a></p>")
        for n, e in enumerate(c["entries"]):
            if n:
                h.append(f"<hr style='background:{theme.VIOLET}'>")
            art = f"<span style='color:{theme.ARTICLE.get(e.article, theme.LIGHT)}'>{e.article} </span>" if e.article else ""
            h.append(f"<p style='font-size:24pt;font-weight:800;margin:0 0 2px 0'>{art}{html.escape(e.lemma)}</p>")
            meta = [f"<span style='color:{theme.MAGENTA};font-weight:600'>{html.escape(e.pos_de or e.pos)}</span>"]
            if e.ipa:
                meta.append(f"<span style='font-family:\"Segoe UI\",serif;font-size:12.5pt;color:{theme.GOLD}'>{html.escape(e.ipa)}</span>")
            if e.hyphenation:
                meta.append(f"<span style='color:{theme.DIM}'>{html.escape(e.hyphenation)}</span>")
            if e.audio_url:
                meta.append(f"<a href='rec:{n}' style='color:{theme.CYAN};text-decoration:none'>▶ recording</a>")
            if n == 0:
                lv = self.levels.level(c["word"], lang, self.dictionary(lang))
                if lv:
                    sure = lang == "en" or self.levels.listed(e.lemma, lang)
                    tip = "CEFR-J" if lang == "en" else ("Goethe/telc word list" if sure else "estimated from frequency")
                    meta.append(f"<span style='color:{LV_COLORS[lv]};font-weight:800'>{'' if sure else '≈'}{LV_NAMES[lv]}</span>"
                                f"<span style='color:{theme.DIM};font-size:8pt'> ({tip})</span>")
            h.append(" &nbsp;·&nbsp; ".join(meta))
            if n == 0:
                d = self.dictionary(lang)
                try:
                    sep = d.separable_in(c["word"], c["sentence"]) if (d and lang == "de") else []
                except Exception:
                    sep = []
                for lemma, vf, part in sep[:2]:                      # "bringt … mit" is the separable verb mitbringen
                    h.append(f"<p style='margin:8px 0 0 0;padding:6px 9px;border-left:3px solid {theme.GOLD}'>"
                             f"<span style='color:{theme.GOLD}'>↪ In this sentence it is part of </span>"
                             f"<a href='pw:{urllib.parse.quote(lemma)}' style='color:{theme.CYAN};font-weight:700;text-decoration:none'>"
                             f"{html.escape(lemma)}</a> <span style='color:{theme.DIM}'>({html.escape(vf)} … {html.escape(part)})</span></p>")
                h.append(f"<p style='margin:6px 0 0 0'><a href='uses:' style='color:{theme.CYAN};text-decoration:none'>"
                         f"🔎 Where else is “{html.escape(e.lemma)}” used in my videos?</a>"
                         f"<span style='color:{theme.DIM};font-size:8.5pt'> — all its forms</span></p>")
                try:
                    _, fset, split = d.forms_of(e.lemma) if d else ("", set(), set())
                except Exception:
                    fset, split = set(), set()
                tapped = c["word"].lower()
                flist = sorted(f for f in fset if f != e.lemma.lower())
                if split:
                    flist = sorted({f"{a} … {b}" for a, b in split}) + flist
                if flist:
                    shown = flist[:24]
                    if tapped in flist and tapped not in shown:
                        shown.append(tapped)
                    h.append(self._sec("Forms" if lang == "en" else "Formen") + " · ".join(
                        (f"<b style='color:{theme.GOLD}'>{html.escape(f)}</b>" if f == tapped else html.escape(f)) for f in shown)
                        + (f" <span style='color:{theme.DIM}'>… +{len(flist) - len(shown)}</span>" if len(flist) > len(shown) else ""))
            if e.lang == "en" and e.german:
                h.append(self._sec("Deutsch") + html.escape(", ".join(e.german[:6])))
            if e.lang != "en" and e.english:
                h.append(self._sec("English") + "<br>".join(f"<span style='color:{theme.DIM}'>{k}.</span> {html.escape(g)}"
                                                             for k, g in enumerate(e.english[:6], 1)))
            h.append(self._sec("فارسی"))
            if e.persian:
                h.append(theme.fa_span(html.escape("، ".join(e.persian)), "15pt"))
            elif e.persian_via_english:
                h.append(theme.fa_span(html.escape("، ".join(e.persian_via_english)), "14pt")
                         + f"<p style='color:{theme.DIM};font-size:8.5pt;margin-top:2px'>through the English meaning — check it fits "
                           f"this sense · <a href='tr:word' style='color:{theme.CYAN}'>translate online</a></p>")
            else:
                h.append(self._online_fa())
            if e.senses:
                h.append(self._sec("Definitions" if e.lang == "en" else "Bedeutungen"))
                for k, s in enumerate(e.senses, 1):
                    h.append(f"<p style='margin:5px 0'><span style='color:{theme.CYAN}'>{k}</span>&nbsp; {html.escape(s.de)}</p>")
                    for ex in s.examples:
                        h.append(f"<p style='margin:2px 0 2px 16px;color:{theme.DIM}'><i>{html.escape(ex)}</i> "
                                 f"<a href='say:{urllib.parse.quote(clean_example(ex))}' style='color:{theme.CYAN};text-decoration:none'>🔊</a></p>")
            if e.synonyms:
                h.append(self._sec("Synonyms" if e.lang == "en" else "Synonyme") + " · ".join(
                    f"<a href='word:{urllib.parse.quote(s)}' style='color:{theme.CYAN};text-decoration:none'>{html.escape(s)}</a>"
                    for s in e.synonyms))
        if not c["entries"]:
            h.append(self._online_fa())
        if c["sentence"]:
            h.append(self._sec("In the video") + f"<i style='color:{theme.LIGHT}'>{html.escape(c['sentence'])}</i>")
        h.append(f"<p style='color:{theme.DIM};font-size:8pt;margin-top:16px'>"
                 + ("English Wiktionary" if lang == "en" else "German &amp; English Wiktionary") + " via kaikki.org (CC BY-SA 4.0)</p>")
        self._card_html("".join(h))
        self._update_save_btn()

    def _online_fa(self):
        c = self.card
        if c.get("fa_online"):
            en, fa = c["fa_online"]
            return f"<p style='margin-bottom:2px'>Online: {html.escape(en)}</p>" + theme.fa_span(html.escape(fa), "14pt")
        return f"<a href='tr:word' style='color:{theme.CYAN}'>Translate online (needs internet)</a>"

    @staticmethod
    def _sec(t):
        return (f"<p style='color:{theme.CYAN};font-weight:700;letter-spacing:2px;font-size:9pt;margin:16px 0 5px 0'>"
                f"{t.upper()}</p>")

    def _card_html(self, body):
        self.card_view.setHtml(f"<div style='font-size:11pt;line-height:140%'>{body}</div>")

    def _card_link(self, url: QUrl):
        s = url.toString()
        kind, _, val = s.partition(":")
        if kind == "dl":
            self.download_asset(downloads.DICT_EN if val == "en" else downloads.DICT_DE,
                                then=lambda: self.open_word(self.card["word"], self.card["sentence"], self.card["start"], self.card["end"], val))
        elif kind == "rec":
            e = self.card["entries"][int(val)]
            self.play_recording(e.audio_url)
        elif kind == "say":
            self.speak(urllib.parse.unquote(val), lang=self.card["lang"])
        elif kind == "word":
            self.open_word(urllib.parse.unquote(val), lang=self.card["lang"])
        elif kind == "tr":
            self.translate_word_online()
        elif kind == "pw":
            self.open_word(urllib.parse.unquote(val), self.card.get("sentence", ""), lang=self.card["lang"])
        elif kind == "uses":
            ents = self.card.get("entries") or []
            self.show_uses(ents[0].lemma if ents else self.card["word"], self.card["lang"])

    def translate_word_online(self):
        c = self.card
        other = "de" if c["lang"] == "en" else "en"
        self.run_bg("trword", lambda: (translate.translate(c["word"], c["lang"], other)[0], translate.translate(c["word"], c["lang"], "fa")[0]))

    # ------------------------------------------------------------------ phrases
    def open_phrase(self, text, sentence, start, end, whole=False):
        lang = self.cue_lang
        self.card = {"kind": "phrase", "word": text, "sentence": sentence, "start": start, "end": end, "lang": lang,
                     "tr": None, "fa": None, "service": "", "error": None, "glosses": {}, "cue": -1}
        d = self.dictionary(lang)
        if d:
            for w in [normalize(t[2]) for t in subtitles.tokens(text)][:14]:
                e = d.lookup(w)
                if e:
                    x = e[0]
                    self.card["glosses"][w] = (x.english[:1] or [("DE: " + g) for g in x.german[:1]] or [x.senses[0].de if x.senses else ""])[0][:60]
        self.show_panel(card=True)
        self._render_phrase()
        other = "de" if lang == "en" else "en"
        self.run_bg("phrase", lambda: (translate.translate(text, lang, other), translate.translate(text, lang, "fa")[0]))

    def translate_sentence(self):
        if self.card and self.card.get("sentence"):
            c = self.card
            self.open_phrase(c["sentence"], c["sentence"], c["start"], c["end"], whole=True)

    def _render_phrase(self):
        c = self.card
        h = [f"<p style='font-size:16pt;font-weight:700;margin:0'>{html.escape(c['word'])}</p>"]
        if c["error"]:
            h.append(f"<p style='color:{theme.MAGENTA}'>{html.escape(c['error'])}</p>")
        elif c["tr"] is None:
            h.append(f"<p style='color:{theme.DIM}'>Translating…</p>")
        else:
            h.append(self._sec("Deutsch" if c["lang"] == "en" else "English") + html.escape(c["tr"]))
            h.append(self._sec("فارسی") + theme.fa_span(html.escape(c["fa"] or ""), "15pt"))
            h.append(f"<p style='color:{theme.DIM};font-size:8pt'>Machine translation · {html.escape(c['service'])}</p>")
        if c["glosses"]:
            h.append(self._sec("Word by word"))
            for w, g in c["glosses"].items():
                h.append(f"<p style='margin:3px 0'><a href='pw:{urllib.parse.quote(w)}' style='color:{theme.CYAN};text-decoration:none'>"
                         f"{html.escape(w)}</a> &nbsp; <span style='color:{theme.DIM}'>{html.escape(g)}</span></p>")
        self._card_html("".join(h))
        self._update_save_btn()

    # ------------------------------------------------------------------ save / speak / learn more
    def _update_save_btn(self):
        c = self.card
        saved = bool(c) and (self.store.find(c["word"], self.video or "", c["start"]) is not None or self._same_as_card() is not None)
        self.save_btn.setText(" Saved" if saved else " Save")
        self.save_btn.setIcon(icons.icon("star_fill" if saved else "star", "#FFFFFF" if saved else theme.LIGHT, 20))
        self.save_btn.setProperty("accent", saved)
        theme.repolish(self.save_btn)

    def save_from_card(self):
        c = self.card
        if not c:
            return
        if self.store.find(c["word"], self.video or "", c["start"]):
            self.msg("Already in My Words")
            return
        e = c.get("entries", [None])[0] if c.get("entries") else None
        same = self.store.find_same(c["word"], (e.lemma if e and c["kind"] != "phrase" else c["word"]), e.lang if e else c["lang"])
        if same:                                   # the same word from another line or video: one entry, this line as a sentence
            n = 0
            if c["sentence"] and c["sentence"].strip().lower() != (same.sentence or "").strip().lower():
                n = self.store.add_examples(same.id, [Example(de=c["sentence"].strip(),
                                                             en=f"from “{self.video_name}”" if self.video_name else "")])
            self.card["same_id"] = same.id
            self.after_change()
            self._update_save_btn()
            self.msg(f"„{same.text}“ is already in My Words" + (" — this line was added to its sentences" if n else ""))
            return
        if c["kind"] == "phrase":
            english = c.get("tr") or ""
            persian = c.get("fa") or ""
            lemma, article, ipa = c["word"], "", ""
        else:
            lemma = e.lemma if e else c["word"]
            article, ipa = (e.article, e.ipa) if e else ("", "")
            if e and e.lang == "en":
                english = "; ".join((s.de for s in e.senses[:1])) + ((" · DE: " + ", ".join(e.german[:3])) if e.german else "")
            else:
                english = ", ".join(e.english[:3]) if e else (c["fa_online"][0] if c.get("fa_online") else "")
            persian = "، ".join((e.persian or e.persian_via_english)[:3]) if e else (c["fa_online"][1] if c.get("fa_online") else "")
        start = c["start"]
        w = SavedWord(text=c["word"], lemma=lemma, sentence=c["sentence"], video_uri=self.video or "", video_name=self.video_name,
                      start_ms=start, end_ms=c["end"], article=article, ipa=ipa, english=english, persian=persian,
                      lang=e.lang if e else c["lang"])
        w.id = self.store.insert(w)
        self.make_snapshot(w)
        self.after_change()
        self._update_save_btn()
        self.msg("★ Saved to My Words — it will come up for review")

    def after_change(self):
        self.refresh_words()
        if getattr(self, "page", "") == "words" and hasattr(self, "words_page"):
            self.words_page.refresh_panels()
        if self.settings.get("sync_token"):
            self.sync_timer.start()

    def speak_card(self, slow):
        c = self.card
        if c:
            e = c.get("entries") or []
            self.speak(e[0].lemma if e and c["kind"] == "word" else c["word"], slow, c["lang"])

    _speech_gen = 0
    _speech_warned = False
    _speech_pending = (0, "", "de", False)

    def speak(self, text: str, slow: bool = False, lang: str = "de"):
        """Reads text aloud: a natural voice (Microsoft online or Piper offline — Settings ▸ Voice), the Windows voice as fallback."""
        text = (text or "").strip()
        if not text:
            return
        eng = self.settings.get("voice_engine", "edge")
        self._speech_gen += 1
        if self.tts is not None:
            self.tts.stop()
        if getattr(self, "voice_player", None):
            self.voice_player.stop()
        if eng == "windows":
            return self._speak_windows(text, slow, lang)
        from . import voice
        if eng == "piper" and not voice.piper_ready(lang, self.settings):
            self._speak_windows(text, slow, lang)
            self.offer_piper(lang)
            return
        self._speech_pending = (self._speech_gen, text, lang, slow)
        gen, settings = self._speech_gen, dict(self.settings)
        self.run_bg("speech", lambda: (gen, str(voice.audio_file(settings, text, lang, slow))))

    def _play_speech(self, f: str):
        if not getattr(self, "voice_player", None):
            self.voice_player = QMediaPlayer(self)
            self.voice_out = QAudioOutput(self)
            self.voice_player.setAudioOutput(self.voice_out)
        self.voice_player.stop()
        self.voice_player.setSource(QUrl.fromLocalFile(f))
        self.voice_player.play()

    def offer_piper(self, lang: str):
        """Piper and the voice for this language are downloaded once (about 136 MB), then read offline."""
        from . import voice
        missing = voice.piper_missing(lang, self.settings) if lang != "all" else \
            voice.piper_missing("de", self.settings) + [a for a in voice.piper_missing("en", self.settings) if a.id != voice.PIPER.id]
        if not missing or self.busy:
            return
        mb = sum(a.size_mb for a in missing)
        if QMessageBox.question(self, "Offline voice", f"The offline natural voice needs a download of about {mb} MB once "
                                f"({', '.join(a.label for a in missing)}).\n\nDownload it now?") != QMessageBox.Yes:
            return
        def chain(rest):
            if not rest:
                return lambda: self.msg("Offline voice ready ✓ — words and sentences are read with Piper now", 9000)
            return lambda: self.download_asset(rest[0], chain(rest[1:]))
        self.download_asset(missing[0], chain(missing[1:]))

    def _speak_windows(self, text: str, slow: bool = False, lang: str = "de"):
        try:
            from PySide6.QtCore import QLocale
            from PySide6.QtTextToSpeech import QTextToSpeech
        except Exception:
            self.msg("Speech is not available on this PC")
            return
        if self.tts is None:
            self.tts = QTextToSpeech(self)
        loc = QLocale(QLocale.German, QLocale.Germany) if lang == "de" else QLocale(QLocale.English, QLocale.UnitedStates)
        self.tts.stop()
        self.tts.setLocale(loc)
        match = [v for v in self.tts.availableVoices() if v.locale().language() == loc.language()]
        if match:
            self.tts.setVoice(match[0])
        else:
            self.msg(f"No {self.lang_name(lang)} voice installed — Windows Settings › Time & language › Speech › Add voices", 9000)
        self.tts.setRate(-0.45 if slow else 0.0)
        self.tts.say(text)

    def play_recording(self, url: str):
        if not hasattr(self, "rec_player"):
            self.rec_player = QMediaPlayer(self)
            self.rec_out = QAudioOutput(self)
            self.rec_player.setAudioOutput(self.rec_out)
        self.player.pause()
        self.rec_player.setSource(QUrl(url))
        self.rec_player.play()

    def ai_prompt(self, word, sentence, lang):
        s = sentence.replace("\n", " ")
        if lang == "en":
            return (f"Explain the English word “{word}”" + (f" as used in: “{s}”" if s else "") + ".\n"
                    "1) Meaning in simple English, plus the German and the Persian translation.\n"
                    "2) IPA (UK and US) and word forms.\n"
                    "2b) 6 typical collocations (verb + noun, adjective + noun, with prepositions), one per line, in this format:\n"
                    "COLL: collocation | meaning | short example sentence\n"
                    "2c) 4 synonyms or near-synonyms, one per line, in this format:\n"
                    "SYN: synonym | meaning and how it differs | an example sentence that uses the synonym\n"
                    "3) Exactly 3 natural example sentences of everyday English, one per line, in this format:\nEN: … | DE: … | FA: …")
        return (f"Explain the German word „{word}“" + (f" as used in: „{s}“" if s else "") + ".\n"
                "1) Meaning in English and in Persian.\n"
                "2) IPA; for nouns article and plural, for verbs Präteritum and Perfekt; the preposition or case it goes with.\n"
                "2b) 6 typical collocations (Kollokationen: Nomen-Verb-Verbindungen, Adjektiv + Nomen, feste Wendungen), one per line, in this format:\n"
                "KOLL: Kollokation | meaning in English | kurzer Beispielsatz\n"
                "2c) 4 Synonyme (Wörter, die man stattdessen sagen kann), one per line, in this format:\n"
                "SYN: Synonym | meaning in English and how it differs | ein Beispielsatz mit dem Synonym\n"
                "3) Exactly 3 natural example sentences (Beispielsätze) of everyday German, one per line, in this format:\nDE: … | EN: … | FA: …")

    def ask_ai(self, source: str, question: str, after: str = ""):
        """Opens ChatGPT / Gemini / DeepSeek / Grok with the question: handed over in the address where the site takes
        it and the question is short enough, and always copied, so Ctrl+V pastes it."""
        from . import lessons
        name, home, with_q = lessons.ASSISTANTS[source]
        QApplication.clipboard().setText(question)
        fits = bool(with_q) and len(urllib.parse.quote(question)) <= lessons.URL_LIMIT
        QDesktopServices.openUrl(QUrl((with_q + urllib.parse.quote(question)) if fits else home))
        self.msg((f"{name} opens with the question. " if fits else f"The question is copied — click into {name}'s box and press Ctrl+V. ")
                 + after, 12000)

    def learn_more(self, source, word, sentence, lang):
        q = urllib.parse.quote
        if source in lessons_assistants():
            self.ask_ai(source, self.ai_prompt(word, sentence, lang), "Then copy the whole answer and use ＋ Add sentences — collocations and synonyms go to Collocations.")
            return
        elif source == "dwds":
            url = "https://www.dwds.de/wb/" + q(word)
        elif source == "cambridge":
            url = "https://dictionary.cambridge.org/dictionary/english/" + q(word.lower())
        else:
            url = "https://www.dict.cc/?s=" + q(word)
        QDesktopServices.openUrl(QUrl(url))

    def learn_menu(self):
        c = self.card
        if not c:
            return
        word = (c.get("entries") or [None])[0].lemma if c.get("entries") else c["word"]
        m = QMenu(self)
        self.fill_learn_menu(m, word, c["sentence"], c["lang"], saved_getter=self.ensure_saved_from_card)
        m.exec(self.learn_btn.mapToGlobal(self.learn_btn.rect().bottomLeft()))

    def open_teacher(self, tab: int = 0):
        """The local AI teacher (Ollama) for the word on the card."""
        c = self.card
        if not c:
            self.msg("Click a word in the subtitles first")
            return
        lemma = c["entries"][0].lemma if c.get("entries") else c["word"]
        self.teacher_for(c["word"], lemma, c["sentence"], c["lang"], self.ensure_saved_from_card, tab, at_ms=c.get("start", -1))

    def ensure_teacher(self) -> bool:
        """True when a local model is chosen; otherwise opens the set-up (Settings ▸ Local AI teacher) first."""
        if self.settings.get("ollama_model"):
            return True
        from .dialogs import SettingsDialog
        self.msg("Set up the local AI teacher first: install Ollama and download a model (Settings ▸ Local AI teacher)", 9000)
        d = SettingsDialog(self)
        d.show_section("Local AI teacher")
        d.exec()
        return bool(self.settings.get("ollama_model"))

    def teacher_for(self, word, lemma, sentence, lang, saved_getter=None, tab: int = 0, at_ms: int | None = None,
                    video: str | None = None):
        from .teacher import TeacherDialog                 # Ollama or an online assistant — chosen in the window
        if at_ms is None:                                  # the line of the word card / of the player, if it is this one
            c = self.card or {}
            at_ms = c.get("start", -1) if c.get("sentence") and " ".join(c["sentence"].split()) == " ".join((sentence or "").split()) else -1
        d = TeacherDialog(self, word, lemma, sentence, lang, saved_getter, tab, at_ms, video)      # not modal: the video keeps playing
        self._teachers = [t for t in getattr(self, "_teachers", []) if t.isVisible()] + [d]
        d.destroyed.connect(lambda *_: setattr(self, "_teachers", [t for t in self._teachers if t is not d]))
        d.show()
        d.raise_()

    def notebook(self, review_first: bool = False, lemma: str | None = None):
        from .notebook import NotebookDialog
        d = NotebookDialog(self, review_first, lemma)
        self._notebooks = [x for x in getattr(self, "_notebooks", []) if x.isVisible()] + [d]
        d.show()
        d.raise_()

    def writing_coach(self):
        """The teacher opened for writing only: German or English."""
        m = QMenu(self)
        m.addAction("✍  German text (Deutsch)", lambda: self.teacher_for("", "", "", "de", None, 5))
        m.addAction("✍  English text", lambda: self.teacher_for("", "", "", "en", None, 5))
        m.exec(QCursor.pos())

    def fill_learn_menu(self, m: QMenu, word, sentence, lang, saved_getter):
        m.addAction(icons.icon("study", theme.MINT, 16), "Teacher (Ollama, ChatGPT, Gemini, DeepSeek, Grok, GapGPT) — collocations + sentences",
                    lambda: self.teacher_for(word, word, sentence, lang, saved_getter, 0))
        m.addAction(icons.icon("study", theme.MINT, 16), "Teacher — explain the line",
                    lambda: self.teacher_for(word, word, sentence, lang, saved_getter, 1))
        m.addAction(icons.icon("study", theme.MINT, 16), "Teacher — check my own sentence",
                    lambda: self.teacher_for(word, word, sentence, lang, saved_getter, 2))
        m.addAction(icons.icon("study", theme.MINT, 16), "Teacher — TestDaF / IELTS questions on the word",
                    lambda: self.teacher_for(word, word, sentence, lang, saved_getter, 4))
        m.addAction(icons.icon("study", theme.MINT, 16), "Teacher — this sentence at A1, A2, B1, B2, C1",
                    lambda: self.teacher_for(word, word, sentence, lang, saved_getter, 6))
        m.addAction(icons.icon("study", theme.MINT, 16), "Teacher — ✍ writing coach",
                    lambda: self.teacher_for(word, word, sentence, lang, saved_getter, 5))
        m.addSeparator()
        m.addAction(icons.icon("sparkles", theme.CYAN, 16), "ChatGPT — meaning, collocations + 3 sentences", lambda: self.learn_more("chatgpt", word, sentence, lang))
        m.addAction(icons.icon("sparkles", theme.GOLD, 16), "Gemini — meaning + 3 sentences", lambda: self.learn_more("gemini", word, sentence, lang))
        m.addAction(icons.icon("sparkles", theme.MINT, 16), "DeepSeek — meaning + 3 sentences", lambda: self.learn_more("deepseek", word, sentence, lang))
        m.addAction(icons.icon("sparkles", theme.MAGENTA, 16), "Grok — meaning + 3 sentences", lambda: self.learn_more("grok", word, sentence, lang))
        m.addAction(icons.icon("sparkles", theme.CYAN, 16), "GapGPT — meaning + 3 sentences", lambda: self.learn_more("gapgpt", word, sentence, lang))
        if lang == "en":
            m.addAction(icons.icon("book", theme.GOLD, 16), "Cambridge Dictionary", lambda: self.learn_more("cambridge", word, sentence, lang))
        else:
            m.addAction(icons.icon("book", theme.GOLD, 16), "DWDS", lambda: self.learn_more("dwds", word, sentence, lang))
        m.addAction(icons.icon("book", theme.LIGHT, 16), "dict.cc", lambda: self.learn_more("dictcc", word, sentence, lang))
        m.addSeparator()

        def add():
            w = saved_getter()
            if w:
                from .dialogs import AddSentencesDialog
                AddSentencesDialog(self, w).exec()
        m.addAction(icons.icon("plus", theme.MINT, 16), "Add sentences (paste the answer)…", add)

    def ensure_saved_from_card(self) -> SavedWord | None:
        c = self.card
        if not c:
            return None
        w = self.store.find(c["word"], self.video or "", c["start"]) or self._same_as_card()
        if not w:
            self.save_from_card()
            w = self.store.find(c["word"], self.video or "", c["start"]) or self._same_as_card()
        return w

    def _same_as_card(self) -> SavedWord | None:
        c = self.card
        if not c:
            return None
        e = (c.get("entries") or [None])[0]
        return self.store.find_same(c["word"], e.lemma if e and c["kind"] != "phrase" else c["word"], e.lang if e else c["lang"])

    # ================================================================== subtitles
    def subtitle_menu(self):
        m = QMenu(self)
        m.addAction(icons.icon("file", theme.CYAN, 16), "Load .srt / .vtt…", self.load_srt)
        a1 = m.addAction(icons.icon("download", theme.CYAN, 16), "Save .srt as…", self.save_srt_as)
        a1.setEnabled(bool(self.cues))
        m.addAction(icons.icon("folder", theme.CYAN, 16), "Open the subtitles folder",
                    lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(syncer.subs_dir()))))
        m.exec(self.cursor().pos())

    def load_srt(self, f: str | None = None):
        if not f:
            f, _ = QFileDialog.getOpenFileName(self, "Load subtitles", self.settings.get("last_dir", ""), "Subtitles (*.srt *.vtt);;All files (*)")
        if not f:
            return
        cues = subtitles.parse(Path(f).read_text(encoding="utf-8", errors="replace"))
        if not cues:
            self.msg("No subtitles found in that file")
            return
        from .dialogs import ask_language
        lang = ask_language(self, "Which language are these subtitles?")
        if not lang:
            return
        self.set_cues(cues, lang, "Loaded")
        if self.video:
            self.srt_path(lang).write_text(subtitles.write(cues), encoding="utf-8")
            self.after_change()

    def save_srt_as(self):
        name = (Path(self.video_name).stem if self.video_name else "subtitles") + f".{self.cue_lang}.srt"
        f, _ = QFileDialog.getSaveFileName(self, "Save subtitles", str(Path(self.settings.get("last_dir", str(Path.home()))) / name), "SubRip (*.srt)")
        if f:
            Path(f).write_text(subtitles.write(self.cues), encoding="utf-8")
            self.msg("Saved " + f)

    def generate_dialog(self):
        if not self.video:
            self.msg("Open a video first")
            return
        from .dialogs import GenerateDialog
        d = GenerateDialog(self)
        if d.exec():
            self.generate(d.lang, d.engine)

    def generate(self, lang: str, engine: str):
        from . import asr
        video, name = self.video, self.video_name
        self.settings["sub_lang"] = lang
        self.save_settings()
        if engine == "online":
            prov = asr.PROVIDERS[self.settings.get("online_provider", "GROQ")]
            key = self.settings.get("online_key_" + prov.id, "")

            def job():
                return asr.transcribe_online(video, prov, key, lang, self._bg_progress, lambda: self.cancel)
        else:
            asset = {"base": downloads.FW_BASE, "small": downloads.FW_SMALL, "turbo": downloads.FW_TURBO}[engine]

            def job():
                folder = downloads.ensure(asset, lambda d, t: self._bg_progress(d / max(t, 1), f"Downloading {asset.label}… "
                                                                                f"{d // 1_000_000} of {t // 1_000_000} MB"), lambda: self.cancel)
                return asr.transcribe_offline(video, str(folder), lang, self._bg_progress, lambda: self.cancel)
        self.run_bg("subs", lambda: (job(), lang, video, name), cancellable=True, label="Making subtitles…")

    # ================================================================== links & clips (new in 2.0)
    def link_dialog(self):
        from .dialogs import LinkDialog
        d = LinkDialog(self)
        if d.exec() and d.url:
            self.import_link(d.url)

    def import_link(self, url: str):
        from . import linkimport
        why = linkimport.refused_reason(url)
        if why:
            QMessageBox.information(self, "SubPlayer", why)
            return

        def job():
            self._bg_progress(0, "Looking for the video…")
            return self._fetch_found(linkimport.resolve(url))
        self.run_bg("link", job, cancellable=True, label="Opening the link…")

    def import_film(self, film, quality: str = "normal"):
        """A programme picked in Discover: its MP4 (and the broadcaster's subtitles) straight from the broadcaster."""
        from . import linkimport
        title = film.title if film.topic.lower() in film.title.lower() else f"{film.topic} – {film.title}"
        if not film.video(quality):                    # English sources: the file is found on the page when downloading
            def job():
                self._bg_progress(0, "Looking for the video…")
                f = linkimport.resolve(film.url_website)
                f.title = title
                return self._fetch_found(f)
            self.run_bg("link", job, cancellable=True, label=f"Downloading {title}…")
            return
        found = linkimport.Found(film.video(quality), title, film.url_subtitle, duration=film.duration)
        found.hls = bool(linkimport.HLS.search(found.video_url.split("?")[0]))
        self.run_bg("link", lambda: self._fetch_found(found), cancellable=True, label=f"Downloading {title}…")

    def _fetch_found(self, found):
        """(runs in the background) downloads the video + subtitles; returns (video path, srt text or None)."""
        from . import linkimport
        def prog(done, total):
            if total and total < 200_000:                  # a stream copied by time (seconds), not by bytes
                self._bg_progress(done / total if total else 0, f"Downloading “{found.title}” · {fmt(done * 1000)}"
                                  + (f" of {fmt(total * 1000)}" if total else ""))
            else:
                self._bg_progress(done / total if total else 0, f"Downloading “{found.title}” · {done // 1_000_000} MB"
                                  + (f" of {total // 1_000_000} MB" if total else ""))
        path = linkimport.download(found, progress=prog, cancelled=lambda: self.cancel)
        srt = found.subtitle_text or None
        if not srt and found.subtitle_url:
            self._bg_progress(1, "Getting the broadcaster's subtitles…")
            srt = linkimport.subtitle_srt(found.subtitle_url)
        return path, srt

    def export_dialog(self):
        if not self.video or not (self.a >= 0 and self.b > self.a):
            self.msg("Set A and B first — the part between them is saved")
            return
        from .dialogs import ExportDialog
        d = ExportDialog(self, bool(self.cues))
        if not d.exec():
            return
        from . import export, linkimport
        burn = d.burn and bool(self.cues)
        src, a, b, cues = self.video, self.a, self.b, list(self.cues)
        out = linkimport.videos_dir() / export.clip_name(self.video_name, a, b, burn)
        self.player.pause()
        self.run_bg("clip", lambda: export.export_clip(src, a, b, cues, burn, out, self._bg_progress, lambda: self.cancel),
                    cancellable=True, label="Saving clip…")

    # ================================================================== drag & drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            f = u.toLocalFile()
            ext = Path(f).suffix.lower()
            if ext in VIDEO_EXT:
                self.open_video(f)
                return
            if ext in (".srt", ".vtt"):
                if not self.video:
                    self.msg("Open the video first, then drop its subtitles")
                    return
                self.load_srt(f)
                return
        txt = e.mimeData().text()
        if txt.startswith("http"):
            self.import_link(txt.strip())

    # ================================================================== background work
    def _bg_progress(self, frac, text):
        self.bus.progress.emit(float(frac), text)

    def run_bg(self, kind, fn, cancellable=False, label=None):
        heavy = kind in ("subs", "download", "link", "clip", "wordbook")
        if heavy and self.busy:
            if kind == "link":                              # downloads wait their turn in the queue
                self.dl_queue.append((kind, fn, cancellable, label or "Download"))
                self._update_queue()
                self.msg(f"Added to the download queue — {len(self.dl_queue)} waiting (status bar ▸ Downloads)", 8000)
            else:
                self.msg("Please wait — " + self.busy)
            return
        if heavy:
            self.busy = label or kind
            QTimer.singleShot(0, self._update_queue)
            self.cancel = False
            self.prog.setVisible(True)
            self.prog.setValue(0)
            self.cancel_btn.setVisible(cancellable)
            if label:
                self.msg(label, 0)

        def run():
            try:
                self.bus.done.emit(kind, fn())
            except Exception as e:
                self.bus.failed.emit(kind, str(e) or e.__class__.__name__)
        threading.Thread(target=run, daemon=True).start()

    def _cancel_task(self):
        self.cancel = True
        self.msg("Cancelling…")

    def _on_progress(self, frac, text):
        self.prog.setValue(int(frac * 100))
        self.statusBar().showMessage(text)

    def _end_task(self):
        self.busy = None
        self.prog.setVisible(False)
        self.cancel_btn.setVisible(False)
        if self.dl_queue:
            QTimer.singleShot(400, self._next_download)
        self._update_queue()

    # ------------------------------------------------------------------ download queue
    def _next_download(self):
        if self.busy or not self.dl_queue:
            return
        kind, fn, cancellable, label = self.dl_queue.pop(0)
        self._dl_queued = True
        self.run_bg(kind, fn, cancellable, label)
        self._update_queue()

    def _update_queue(self):
        running = bool(self.busy) and str(self.busy).startswith(("Downloading", "Opening the link"))
        n = len(self.dl_queue)
        parts = []
        if running:
            parts.append("1 downloading")
        if n:
            parts.append(f"{n} waiting")
        if self.dl_done and not parts:
            parts.append(f"{len(self.dl_done)} downloaded")
        self.queue_btn.setText("⬇ Downloads: " + " · ".join(parts) if parts else "")
        self.queue_btn.setVisible(bool(parts))

    def queue_menu(self):
        m = QMenu(self)
        if self.busy:
            m.addSection("Now")
            m.addAction(icons.icon("x", theme.MAGENTA, 16), f"Cancel: {str(self.busy)[:70]}", self._cancel_task)
        if self.dl_queue:
            m.addSection(f"Waiting ({len(self.dl_queue)})")
            for k, item in enumerate(self.dl_queue):
                sub = m.addMenu(f"{k + 1}. {item[3][:70]}")
                if k:
                    sub.addAction("Move up", lambda k=k: self._queue_move(k, -1))
                sub.addAction("Download next", lambda k=k: self._queue_move(k, -k))
                sub.addAction("Remove from the queue", lambda k=k: (self.dl_queue.pop(k), self._update_queue()))
        if self.dl_done:
            m.addSection("Downloaded")
            for title, path in self.dl_done[-12:][::-1]:
                m.addAction(icons.icon("play", theme.MINT, 16), f"Open: {title[:70]}", lambda p=path: self.open_video(str(p), at_ms=0))
            m.addAction("Clear this list", lambda: (self.dl_done.clear(), self._update_queue()))
        if m.isEmpty():
            m.addAction("No downloads").setEnabled(False)
        m.exec(QCursor.pos())

    def _queue_move(self, k: int, d: int):
        it = self.dl_queue.pop(k)
        self.dl_queue.insert(max(0, k + d), it)
        self._update_queue()

    def _on_done(self, kind, res):
        if kind == "wordbook":
            self._end_task()
            f, nw, nclips, nwant, note, nmp3, mp3_dir = res
            text = f"Word book saved: {nw} words" + (f", {nclips} audio clips inside" if nclips else "")
            if nwant and nclips < nwant:
                text += (" — no natural voice could be reached, the browser's voice reads instead"
                         if not nclips else f" — {nwant - nclips} clip(s) missing, the browser reads those")
                if note:
                    log_error("word book audio", None, note)
            if nmp3:
                text += f" · {nmp3} MP3 files in {mp3_dir}"
            self.msg(text, 15000)
            QDesktopServices.openUrl(QUrl.fromLocalFile(f))
            return
        if kind == "speech":
            gen, f = res
            if gen == self._speech_gen:
                self._play_speech(f)
            return
        if kind == "subs":
            self._end_task()
            cues, lang, video, name = res
            if not cues:
                self.msg("No speech found")
                return
            f = syncer.subs_dir() / f"{subtitles.video_key(name)}.{lang}.srt"
            f.write_text(subtitles.write(cues), encoding="utf-8")
            if video == self.video:
                self.set_cues(cues, lang, f"{self.lang_name(lang)} subtitles ready")
            self.after_change()
        elif kind == "download":
            self._end_task()
            then = res
            if callable(then):
                then()
        elif kind == "link":
            queued, self._dl_queued = self._dl_queued, False
            path, srt = res
            if srt:
                cues = subtitles.parse(srt)
                lang = subtitles.guess_lang(cues)
                (syncer.subs_dir() / f"{subtitles.video_key(path.name)}.{lang}.srt").write_text(srt, encoding="utf-8")
            watching = self.video and self.player.playbackState() == QMediaPlayer.PlayingState
            if queued or self.dl_queue or watching:          # don't take the screen away: it waits in Downloads
                self.dl_done.append((path.stem, path))
                self._end_task()
                if srt:
                    self.after_change()
                self.msg(f"Downloaded: {path.stem} — open it from ⬇ Downloads in the status bar" + (" (with subtitles)" if srt else ""), 12000)
                return
            self._end_task()
            self.open_video(str(path), at_ms=0)
            if srt:
                self.msg(f"Saved to {path.parent} — with the broadcaster's own subtitles ({len(cues)} lines)", 12000)
                self.after_change()
            else:
                self.msg(f"Saved to {path.parent} — click Subtitles to transcribe it", 12000)
                QTimer.singleShot(600, self.generate_dialog)
        elif kind == "clip":
            self._end_task()
            box = QMessageBox(self)
            box.setWindowTitle("Clip saved")
            box.setText(f"Saved:\n{res}")
            show = box.addButton("Show in folder", QMessageBox.AcceptRole)
            box.addButton("OK", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is show:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(res).parent)))
        elif kind == "snap":
            uid, cb = res
            try:
                cb(uid)
            except Exception:
                pass
        elif kind == "trall":
            self._end_task()
            tgt, done = res
            lang = self.cue_lang
            for t, o in done.items():
                self.tr_cache[(t, lang, tgt)] = o
            tr = [subtitles.Cue(self.cues[a].start_ms, self.cues[b].end_ms, self.tr_cache.get((self.unit_text(a), lang, tgt), ""))
                  for a, b in sorted(set(self.units()))]                    # one entry per sentence
            tr = [c for c in tr if c.text]
            if tr:
                self._tr_file(tgt).write_text(subtitles.write(tr), encoding="utf-8")
            if not self.show_tr:
                self.trl_btn.setChecked(True)
                self.toggle_translation_line()
            self._shown = None
            self.msg(f"{len(tr)} sentences ({len(self.cues)} lines) translated and saved — the translation line now works offline "
                     "(button beside the subtitle turns it on/off)", 12000)
        elif kind == "trline":
            key, out = res
            self.tr_pending.discard(key)
            self.tr_cache[key] = out
            if len(self.tr_cache) > 4000:
                self.tr_cache.clear()
            self._shown = None
        elif kind == "trword" and self.card and self.card["kind"] == "word":
            self.card["fa_online"] = res
            self._render_card()
        elif kind == "phrase" and self.card and self.card["kind"] == "phrase":
            (tr, service), fa = res
            self.card.update(tr=tr, service=service, fa=fa)
            self._render_phrase()
        elif kind == "sync":
            gid, n = res
            self.settings["gist_id"] = gid
            self.settings["sync_status"] = f"Synced {time.strftime('%d %b %H:%M')} · {n} words"
            self.save_settings()
            self.last_sync = time.time()
            self.sync_btn.setText("Sync")
            self.refresh_words()
            if self.video and not self.cues:
                self._load_subs_for_video()
            if self.stack.currentIndex() == 1:
                self.words_page.refresh()
            if not self._sync_silent:
                self.msg(f"Synced ✓ — {n} words")
            self._syncing = False

    def _on_failed(self, kind, err):
        if kind == "speech":
            gen, text, lang, slow = self._speech_pending
            if gen == self._speech_gen:
                log_error("natural voice", err)
                if not self._speech_warned:
                    self._speech_warned = True
                    self.msg("Microsoft's natural voice could not be reached — the Windows voice reads instead. "
                             "For a natural voice without internet: Settings ▸ Voice ▸ Download offline voices (Piper).", 14000)
                self._speak_windows(text, slow, lang)
            return
        if kind in ("subs", "download", "link", "clip", "wordbook"):
            queued, self._dl_queued = self._dl_queued, False
            self._end_task()
            if kind == "link" and (queued or self.dl_queue):     # a failed download in the queue: note it, go on with the rest
                self.msg(("Cancelled" if "cancel" in err.lower() else "A download failed: " + err) +
                         (f" — {len(self.dl_queue)} still waiting" if self.dl_queue else ""), 12000)
                return
            cancelled = "cancel" in err.lower()
            self.msg("Cancelled" if cancelled else err, 12000)
            if not cancelled:
                what = {"link": "The link didn't work", "clip": "Saving the clip failed"}.get(kind, "")
                QMessageBox.warning(self, "SubPlayer", (what + " — " if what else "") + err)
        elif kind == "phrase" and self.card and self.card["kind"] == "phrase":
            self.card["error"] = "Offline — translation needs internet. Word meanings are shown below."
            self._render_phrase()
        elif kind == "sync":
            self._syncing = False
            self.sync_btn.setText("Sync")
            self.settings["sync_status"] = "Sync failed: " + err
            self.save_settings()
            if not self._sync_silent:
                self.msg("Sync failed: " + err, 12000)
        else:
            self.msg(err, 9000)

    def download_asset(self, asset, then=None):
        def job():
            downloads.ensure(asset, lambda d, t: self._bg_progress(d / max(t, 1), f"Downloading {asset.label}… {d // 1_000_000} of {t // 1_000_000} MB"),
                             lambda: self.cancel)
            return then
        self.run_bg("download", job, cancellable=True, label=f"Downloading {asset.label}…")

    # ================================================================== sync
    _syncing = False
    _sync_silent = True

    def sync_now(self, silent=False):
        token = self.settings.get("sync_token", "")
        if not token:
            if not silent:
                self.msg("Add your GitHub token first: Settings › Sync")
                self.settings_dialog()
            return
        if self._syncing:
            return
        self._syncing = True
        self._sync_silent = silent
        self.sync_btn.setText("Syncing…")
        gid = self.settings.get("gist_id")
        names = {r["name"].lower(): r["path"] for r in self.recents()}
        self.run_bg("sync", lambda: syncer.sync_now(token, gid, self.store, self.progress, syncer.subs_dir(),
                                                     lambda n: names.get(n.lower(), "")))

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() in (e.Type.ActivationChange, e.Type.WindowStateChange):
            self._update_motion()
        if e.type() == e.Type.ActivationChange and self.isActiveWindow() and self.settings.get("sync_token") \
                and time.time() - self.last_sync > 120 and not self._syncing:
            self.sync_now(silent=True)

    # ================================================================== dialogs
    def settings_dialog(self):
        from .dialogs import SettingsDialog
        SettingsDialog(self).exec()

    def help_dialog(self):
        from .dialogs import HelpDialog
        HelpDialog(self).exec()

    def restart_ui(self):
        """Builds the window again in the chosen theme and carries on where you were (same video, same moment)."""
        video, pos = self.video, (self.player.position() if self.video else 0)
        geo, maxi = self.geometry(), self.isMaximized()
        self.player.pause()
        self.remember_position()
        theme.apply(self.settings.get("theme", "nebula"), self.settings.get("accent", ""))
        w = Main()
        w.setGeometry(geo)
        (w.showMaximized if maxi else w.show)()
        QApplication.instance()._main_window = w                      # keep it alive
        self._replaced = True
        QApplication.instance().removeEventFilter(self)
        for t in self.findChildren(QTimer):
            t.stop()
        self.player.stop()
        self.close()
        self.deleteLater()
        if video and os.path.exists(video):
            QTimer.singleShot(700, lambda: w.open_video(video, at_ms=pos, play=False))
        w.msg("Theme changed: " + theme.THEMES[theme.current()[0]][0] + (" · your own colour" if theme.current()[1] else ""), 6000)

    def closeEvent(self, e):
        if getattr(self, "_replaced", False):                         # the old window of a theme change: nothing left to save
            super().closeEvent(e)
            return
        self.remember_position()
        if self.sync_timer.isActive() and self.settings.get("sync_token"):
            try:   # last changes go up before closing
                syncer.sync_now(self.settings["sync_token"], self.settings.get("gist_id"), self.store, self.progress, syncer.subs_dir())
            except Exception:
                pass
        super().closeEvent(e)

    # ================================================================== word levels
    def toggle_levels(self):
        on = self.lvl_btn.isChecked()
        self.settings["show_levels"] = on
        self.save_settings()
        self._shown = None
        if on:
            self.msg("Word levels: A1 green · A2 cyan · B1 blue · B2 violet · C1 orange · C2 pink" +
                     (" — German levels are estimated from how common a word is" if self.cue_lang == "de" else
                      " — CEFR-J; words not in it estimated") + " · right-click the button: only harder words", 12000)

    def level_menu(self):
        m = QMenu(self)
        cur = self.settings.get("level_min", 1)
        for n in range(1, 7):
            label = "Colour all words" if n == 1 else f"Colour only {LV_NAMES[n]} and harder"
            a = m.addAction(("✓  " if n == cur else "     ") + label)
            a.triggered.connect(lambda _=False, x=n: self._set_level_min(x))
        m.exec(self.lvl_btn.mapToGlobal(self.lvl_btn.rect().topLeft()) - m.sizeHint().height() * QPoint(0, 1))

    def _set_level_min(self, n):
        self.settings["level_min"] = n
        self.save_settings()
        if not self.lvl_btn.isChecked():
            self.lvl_btn.setChecked(True)
            self.toggle_levels()
        self._shown = None

    # ================================================================== where else is the word used
    def show_uses(self, word: str, lang: str):
        from .dialogs import UsesDialog
        UsesDialog(self, word, lang).exec()

    def open_use(self, video: str, srt, start_ms: int, end_ms: int):
        if not video or not os.path.exists(video):
            self.msg("That video isn't on this PC any more (only its subtitles are)", 8000)
            return
        if self.video != video:
            self.open_video(video, at_ms=max(0, start_ms - 300), play=False)
        self.show_page("player")
        self.a, self.b = max(0, start_ms - 300), end_ms + 300
        self._ab_label()
        self.player.setPosition(self.a)
        self.player.play()

    # ================================================================== Space everywhere
    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QPlainTextEdit, QTextEdit
        try:
            key_press = ev.type() == QEvent.KeyPress
        except (AttributeError, RuntimeError):                 # an object being deleted (Qt hands over a layout item)
            return False
        if key_press and ev.key() == Qt.Key_Space and not ev.modifiers() and self.isActiveWindow():
            fw = QApplication.focusWidget()
            typing = isinstance(fw, (QLineEdit, QPlainTextEdit, QAbstractSpinBox)) or \
                (isinstance(fw, QTextEdit) and not fw.isReadOnly()) or (isinstance(fw, QComboBox) and fw.isEditable())
            if not typing and QApplication.activeModalWidget() is None:
                if self.stack.currentIndex() == 0 and self.video:
                    self.toggle_play()
                    return True
                if self.stack.currentIndex() == 2:              # Review keeps its own Space (show the meaning)
                    return False
                if self.video and self.player.playbackState() == QMediaPlayer.PlayingState:
                    self.player.pause()
                    return True
        return super().eventFilter(obj, ev)

    # ================================================================== correcting subtitles
    def edit_cue(self, i: int | None = None):
        if not self.cues:
            self.msg("No subtitles to correct yet")
            return
        if i is None:
            i = subtitles.index_before(self.cues, self.cpos())
            if i < 0:
                i = 0
        was = self.player.playbackState() == QMediaPlayer.PlayingState
        self.player.pause()
        from .dialogs import CueEditDialog
        d = CueEditDialog(self, i)
        if d.exec() and d.result_action:
            act, payload = d.result_action
            cues = list(self.cues)
            if act == "save":
                cues[i] = payload
            elif act == "delete":
                del cues[i]
            elif act == "insert":
                cues.insert(i + 1, payload)
            cues.sort(key=lambda c: c.start_ms)
            self._save_edited(cues)
            self.msg({"save": "Line corrected and saved", "delete": "Line deleted", "insert": "Line added"}[act])
        elif was:
            self.player.play()

    def _save_edited(self, cues):
        path = self.srt_path(self.cue_lang)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            bak = path.with_suffix(".before-edit.srt")
            if not bak.exists():
                bak.write_bytes(path.read_bytes())
        path.write_text(subtitles.write(cues), encoding="utf-8")
        self.cues = cues
        self._cue_rev = getattr(self, "_cue_rev", 0) + 1
        self._fill_transcript()
        self._shown = None
        self.after_change()

    def _transcript_menu(self, pos):
        it = self.transcript.itemAt(pos)
        if not it:
            return
        k = it.data(Qt.UserRole)
        m = QMenu(self)
        m.addAction("Play this line", lambda: self._transcript_click(it))
        m.addAction("Loop this line", lambda: self._transcript_loop(it))
        m.addSeparator()
        m.addAction("Record myself and compare  (Y)", lambda: self.record_compare(k))
        m.addAction("Paraphrase this line (A1 → C1)  (P)", lambda: self.paraphrase_line(k))
        m.addAction("Correct this line…  (E)", lambda: self.edit_cue(k))
        m.exec(self.transcript.viewport().mapToGlobal(pos))

    def record_compare(self, i: int | None = None):
        """Shadowing with your own voice: the line (or the A–B part) from the video, then you, then both to compare."""
        if not self.video:
            self.msg("Open a video first")
            return
        from .compare import RecordCompare
        if getattr(self, "comparer", None) is None:
            self.comparer = RecordCompare(self)
        if i is None and self.a >= 0 and self.b > self.a:
            a, b = self.a, self.b                           # the A–B part or the line that loops now
        elif self.cues:
            if i is None:
                i = max(0, subtitles.index_before(self.cues, self.cpos()))
            pa, pb = self.parts()[min(i, len(self.cues) - 1)]
            a, b = self.cues[pa].start_ms + self.sub_offset, self.cues[pb].end_ms + self.sub_offset + 150
        else:
            self.msg("Record and compare needs subtitles, or a part set with A and B")
            return
        self.clear_ab()                                     # loop / shadowing pause while you record
        self.comparer.start(a, b)

    def paraphrase_line(self, i: int | None = None):
        """The teacher's A1 → C1 on the whole sentence that is playing (or line i): the same meaning at five levels."""
        if not self.cues:
            self.msg("Open a video with subtitles first")
            return
        if i is None:
            i = max(0, subtitles.index_before(self.cues, self.cpos()))
        i = min(i, len(self.cues) - 1)
        text = self.unit_text(i)
        if len(text.split()) < 2:
            self.msg("This line is too short to paraphrase")
            return
        self.player.pause()
        a, _ = self.units()[i]
        self.teacher_for("", "", text, self.cue_lang, None, 6, at_ms=self.cues[a].start_ms + self.sub_offset)

    # ================================================================== translate the whole subtitle
    def _tr_file(self, tgt: str) -> Path:
        return self.srt_path(self.cue_lang).with_name(f"{subtitles.video_key(self.video_name)}.{self.cue_lang}.tr-{tgt}.srt")

    def _load_translations(self):
        """A saved full translation of this video's subtitles fills the translation line (offline)."""
        if not self.cues or not self.video_name:
            return 0
        n = 0
        units = sorted(set(self.units()))
        for tgt in ("en", "fa", "de"):
            f = self._tr_file(tgt)
            if f.exists():
                tr = subtitles.parse(f.read_text(encoding="utf-8", errors="replace"))
                by_start = {c.start_ms: c for c in tr}
                for a, b in units:
                    t = by_start.get(self.cues[a].start_ms)
                    if t and t.end_ms >= self.cues[b].end_ms - 20:          # saved per sentence (2.6)
                        out = t.text
                    else:                                                  # saved per line (before 2.6): join the lines
                        parts = [by_start.get(self.cues[k].start_ms) for k in range(a, b + 1)]
                        if not all(parts):
                            continue
                        out = " ".join(p.text for p in parts)
                    self.tr_cache[(self.unit_text(a), self.cue_lang, tgt)] = " ".join(out.split())
                    n += 1
        return n

    def translate_all(self):
        if not self.cues:
            self.msg("Load or make subtitles first")
            return
        tgt = self._tr_target()
        name = {"en": "English", "fa": "Persian", "de": "German"}[tgt]
        cues, lang = list(self.cues), self.cue_lang
        todo = list(dict.fromkeys(t for t in (self.unit_text(a) for a, _ in sorted(set(self.units())))
                                  if (t, lang, tgt) not in self.tr_cache))      # whole sentences, each once

        def job():
            done = {}
            batch, size = [], 0
            groups = []
            for t in todo:
                if size + len(t) > 1800 and batch:
                    groups.append(batch)
                    batch, size = [], 0
                batch.append(t)
                size += len(t) + 1
            if batch:
                groups.append(batch)
            for gi, g in enumerate(groups):
                if self.cancel:
                    raise RuntimeError("Cancelled")
                self._bg_progress(gi / max(1, len(groups)), f"Translating into {name}… {sum(len(x) for x in groups[:gi])} of {len(todo)} sentences")
                out = None
                try:
                    res, _ = translate.translate("\n".join(g), lang, tgt)
                    parts = [x.strip() for x in res.split("\n")]
                    if len(parts) == len(g):
                        out = parts
                except Exception:
                    out = None
                if out is None:                                    # line by line when the service merged lines
                    out = []
                    for t in g:
                        try:
                            out.append(translate.translate(t, lang, tgt)[0])
                        except Exception:
                            out.append("")
                for t, o in zip(g, out):
                    if o:
                        done[t] = o
            return tgt, done
        self.run_bg("trall", job, cancellable=True, label=f"Translating the subtitles into {name}…")

    # ================================================================== video study
    # ================================================================== snapshots of the video moment
    def snap_path(self, w: SavedWord) -> Path:
        return paths.data_dir() / "snaps" / f"{w.uid}.jpg"

    def make_snapshot(self, w: SavedWord, done=None):
        """A small picture of the video where the word is said (made in the background)."""
        path = self.find_video(w)
        out = self.snap_path(w)
        if not path or w.start_ms < 0 or out.exists():
            return False

        def work():
            try:
                from . import export
                export.snapshot(path, w.start_ms + 400, out)
            except Exception:
                pass
            if done:
                self.bus.done.emit("snap", (w.uid, done))
        threading.Thread(target=work, daemon=True).start()
        return True

    def open_study(self):
        if not self.cues:
            self.msg("Open a video with subtitles first")
            return
        self.study_page.load(self.video, self.video_name, list(self.cues), self.cue_lang)
        self.show_page("study")

    def _has_video(self, has: bool):
        """Audio files (podcasts) show a cover instead of a black picture."""
        if has or not self.video:
            self.vstack.setCurrentIndex(0)
            return
        self.audio_cover.setText(f"<div style='font-size:46pt'>🎧</div><div style='font-weight:800;font-size:17pt'>"
                                 f"{html.escape(Path(self.video).stem)}</div><div style='color:#9A98B5;font-size:11pt;margin-top:8px'>"
                                 "Audio — click words in the subtitles as usual. No subtitles yet? Click Subtitles to make them."
                                 "</div>")
        self.vstack.setCurrentIndex(1)

    def find_video(self, w: SavedWord) -> str | None:
        """The word's video: where it was, or — if it moved — the same file name in recent videos or your video folders."""
        if w.video_uri and os.path.exists(w.video_uri):
            return w.video_uri
        name = (w.video_name or Path(w.video_uri or "").name).lower()
        if not name:
            return None
        hit = next((r["path"] for r in self.recents() if r["name"].lower() == name and os.path.exists(r["path"])), None)
        if hit:
            return hit
        cache = getattr(self, "_found_videos", {})
        if name in cache and os.path.exists(cache[name]):
            return cache[name]
        from . import library
        for folder in library.video_folders(self.settings):
            for root, dirs, files in os.walk(folder):
                dirs[:] = [d for d in dirs if not d.startswith((".", "$"))]
                for f in files:
                    if f.lower() == name:
                        cache[name] = os.path.join(root, f)
                        self._found_videos = cache
                        return cache[name]
                if root.count(os.sep) - str(folder).count(os.sep) >= 3:
                    dirs[:] = []
        return None

    def play_clip(self, w: SavedWord, after=None, quiet: bool = False):
        """Plays the saved word's video moment (finds the video by name if it moved)."""
        path = self.find_video(w)
        if not path:
            self.msg(f"Video “{w.video_name}” not found on this PC — put it in Videos, Downloads or a folder you opened "
                     "before (same file name)", 9000)
            return False
        if self.video != path:
            self.open_video(path, at_ms=max(0, w.start_ms), play=False, switch=not quiet)
        self.a, self.b = max(0, w.start_ms - 200), w.end_ms + 300
        self._ab_label()
        self.player.setPosition(self.a)
        self.player.play()
        return True


class MiniPlayer(QFrame):
    """A small video window that floats over SubPlayer while My Words, Discover, Study … are open, so the video goes on."""

    def __init__(self, main):
        super().__init__(main, Qt.Tool | Qt.WindowStaysOnTopHint)
        self.main = main
        self.setWindowTitle("SubPlayer — video")
        self.setObjectName("card")
        self.setStyleSheet(f"QFrame#card{{background:{theme.CARD}}}")
        self.resize(420, 290)
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(4)
        self.vw = QVideoWidget()
        self.vw.setStyleSheet("background:#000")
        v.addWidget(self.vw, 1)
        self.line = QLabel("", alignment=Qt.AlignCenter, wordWrap=True)
        self.line.setStyleSheet("color:#FFFFFF;font-size:11pt;font-weight:600")
        v.addWidget(self.line)
        row = QHBoxLayout()
        self.pp = ibtn("pause", "Play / pause", main.toggle_play, size=18)
        row.addWidget(self.pp)
        row.addWidget(ibtn("back5", "Back 5 seconds", lambda: main.seek_rel(-5000), size=18))
        row.addWidget(ibtn("fwd5", "Forward 5 seconds", lambda: main.seek_rel(5000), size=18))
        row.addStretch(1)
        row.addWidget(ibtn("fullscreen", "Back to the player", lambda: main.show_page("player"), kind="chip", size=15, text=" Player"))
        row.addWidget(ibtn("x", "Close (pauses the video)", self.close_and_pause, size=16))
        v.addLayout(row)
        self._playing = None

    def place(self):
        g = self.main.geometry()
        self.move(g.right() - self.width() - 28, g.bottom() - self.height() - 70)

    def update_state(self, playing: bool, text: str):
        if playing != self._playing:
            self._playing = playing
            self.pp.setIcon(icons.icon("pause" if playing else "play", theme.LIGHT, 18))
        if text != self.line.text():
            self.line.setText(" ".join(text.split()))

    def close_and_pause(self):
        self.main.player.pause()
        self.main.hide_mini()

    def closeEvent(self, e):
        self.main.player.pause()
        self.main.set_output(self.main.vw)
        super().closeEvent(e)


def selftest(out: str) -> int:
    """Used by the build: proves the packaged app can load everything it needs."""
    lines, ok = [], True
    for mod in ("faster_whisper", "ctranslate2", "av", "onnxruntime", "numpy", "PySide6.QtMultimedia", "PySide6.QtTextToSpeech",
                "PySide6.QtSvg", "cryptography", "requests", "socks", "urllib3.contrib.socks", "subplayer_win.discover",
                "subplayer_win.mediathek", "subplayer_win.netcfg", "subplayer_win.english", "subplayer_win.study",
                "subplayer_win.library", "subplayer_win.levels", "subplayer_win.lessons", "edge_tts", "aiohttp", "subplayer_win.voice",
                "subplayer_win.piper_catalog", "subplayer_win.piper_ui", "subplayer_win.compare"):
        try:
            __import__(mod)
            lines.append(f"OK   {mod}")
        except Exception as e:
            ok = False
            lines.append(f"FAIL {mod}: {e}")
    try:
        from faster_whisper.vad import get_vad_model  # bundled voice-detector file
        get_vad_model()
        lines.append("OK   vad model")
    except Exception as e:
        ok = False
        lines.append(f"FAIL vad model: {e}")
    try:  # decode real audio through the packaged PyAV (1 s, 440 Hz tone written as WAV)
        import math
        import struct
        import tempfile
        import wave
        from . import asr
        f = Path(tempfile.gettempdir()) / "subplayer-selftest.wav"
        with wave.open(str(f), "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"".join(struct.pack("<hh", v, v) for v in (int(8000 * math.sin(2 * math.pi * 440 * i / 44100)) for i in range(44100))))
        n = len(asr.decode_audio(str(f)))
        if abs(n - 16000) > 400:
            raise ValueError(f"{n} samples instead of 16000")
        lines.append(f"OK   audio decoding ({n} samples for 1 s)")
    except Exception as e:
        ok = False
        lines.append(f"FAIL audio decoding: {e}")
    # natural voices — reported, never a reason to fail the build (they depend on the network of the build machine)
    try:
        from . import voice
        f = voice.edge_file("Die Versicherung beziffert den Schaden auf achttausend Euro.", "de-DE-SeraphinaMultilingualNeural")
        lines.append(f"OK   Microsoft natural voice ({f.stat().st_size} bytes of mp3)")
    except Exception as e:
        lines.append(f"INFO Microsoft natural voice not reached: {e.__class__.__name__}: {e}")
    if os.environ.get("SUBPLAYER_SELFTEST_PIPER"):
        try:
            from . import voice
            for a_ in (voice.PIPER, voice.PIPER_VOICES["de"]):
                downloads.ensure(a_)
            f = voice.piper_file("Die Versicherung beziffert den Schaden auf achttausend Euro.", "de")
            lines.append(f"OK   Piper offline voice ({f.stat().st_size} bytes of wav)")
        except Exception as e:
            lines.append(f"INFO Piper offline voice: {e.__class__.__name__}: {e}")
        strict = os.environ.get("SUBPLAYER_SELFTEST_PIPER") == "strict"   # a test build: the catalogue must work
        try:  # the Piper catalogue from the packaged app: read the list, download the smallest German voice, read with it
            from . import piper_catalog as pc, voice
            voices, _, from_copy = pc.fetch_catalogue(offline_ok=False)
            fams = {v.family for v in voices}
            lines.append(f"OK   Piper catalogue: {len(voices)} voices in {len(fams)} languages")
            small = min((v for v in voices if v.family == "de" and v.key != "de_DE-thorsten-high"), key=lambda v: v.size_bytes)
            got = []
            pc.install(small, lambda d, t: got.append(d))
            if not pc.is_installed(small):
                raise IOError("installed voice not found")
            st = {"voice_piper_de": small.key}
            text = "Die Versicherung beziffert den Schaden auf achttausend Euro."
            a = voice.piper_file(text, "de", settings=st)
            b = voice.piper_file(text, "de", settings={})
            if a == b or voice.piper_model(st, "de")[1] != small.model_path:
                raise ValueError("the chosen voice and the bundled voice share a cache file")
            lines.append(f"OK   Piper catalogue voice {small.key} downloaded ({small.size_bytes // 1_000_000} MB, checksum ok) "
                         f"and read ({a.stat().st_size} bytes of wav; cache separate from the bundled voice)")
            pc.remove(small.key)
            if pc.model_path(small.key):
                raise IOError("voice not removed")
            lines.append("OK   Piper catalogue voice removed")
        except Exception as e:
            if strict:
                ok = False
            lines.append(f"{'FAIL' if strict else 'INFO'} Piper catalogue: {e.__class__.__name__}: {e}")
    want = os.environ.get("SUBPLAYER_SELFTEST_DATA")          # a test build: the data folder it must use (portable mode)
    lines.append(f"INFO data folder: {paths.data_dir()}")
    if want:
        same = Path(want).resolve() == paths.data_dir().resolve()
        ok = ok and same
        lines.append(("OK   " if same else "FAIL ") + f"data folder is {want}")
    try:
        cues = subtitles.parse_any('<tt xmlns="http://www.w3.org/ns/ttml"><body><div><p begin="10:00:01.000" end="10:00:02.000">'
                                   'Guten Tag</p></div></body></tt>')
        if not (len(cues) == 1 and cues[0].start_ms == 1000):
            raise ValueError(cues)
        import av
        if "hls" not in av.formats_available:
            raise ValueError("FFmpeg has no HLS reader")
        lines.append("OK   broadcaster subtitles + HLS streams")
        from .levels import Levels
        lv = Levels()
        if not (lv.level("warum", "de") == 1 and lv.level("journey", "en") == 2 and len(lv.table("de")) > 20000):
            raise ValueError("word level lists missing")
        lines.append(f"OK   word levels ({len(lv.table('de'))} German, {len(lv.table('en'))} English)")
    except Exception as e:
        ok = False
        lines.append(f"FAIL broadcaster subtitles / HLS: {e}")
    try:
        from . import export
        enc = export.pick_encoder()
        lines.append(f"{'OK  ' if enc != 'mpeg4' else 'WARN'} clip encoder {enc}")
    except Exception as e:
        ok = False
        lines.append(f"FAIL clip encoder: {e}")
    try:
        from PySide6.QtWidgets import QApplication as _A
        app = _A.instance() or _A(["selftest", "-platform", "offscreen"])
        fams = theme.load_fonts()
        if "Vazirmatn" not in fams:
            raise ValueError(f"fonts loaded: {fams}")
        icons.pixmap("play", "#FFFFFF", 20)
        lines.append("OK   fonts + icons")
    except Exception as e:
        ok = False
        lines.append(f"FAIL fonts/icons: {e}")
    lines.append(f"device code {licence.device_code()}")
    Path(out).write_text("\n".join(lines) + ("\nALL OK\n" if ok else "\n"), encoding="utf-8")
    return 0 if ok else 1


def lessons_assistants():
    from . import lessons
    return tuple(lessons.ASSISTANTS)


def log_error(where: str, e: BaseException | None = None, tb: str = ""):
    """Errors go to errors.log in the data folder (the program has no console window to show them)."""
    try:
        import traceback
        txt = tb or "".join(traceback.format_exception(type(e), e, e.__traceback__)) if e else tb
        with open(paths.data_dir() / "errors.log", "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} SubPlayer {VERSION} · {where}\n{txt}\n")
    except Exception:
        pass


def _install_error_log():
    """An unexpected error in a button never closes SubPlayer: it is written to errors.log and shown in the status bar.
    A hard crash (in Qt or the video driver) leaves its traceback in crash.log."""
    def hook(t, v, tb):
        import traceback
        log_error("unexpected error", tb="".join(traceback.format_exception(t, v, tb)))
        try:
            w = QApplication.instance()._main_window
            w.msg(f"Something went wrong ({t.__name__}: {v}) — written to errors.log in the data folder", 12000)
        except Exception:
            pass
    sys.excepthook = hook
    try:
        import faulthandler
        _install_error_log.crash = open(paths.data_dir() / "crash.log", "a", encoding="utf-8")
        faulthandler.enable(_install_error_log.crash)
    except Exception:
        pass


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest(sys.argv[sys.argv.index("--selftest") + 1]))
    if "--remind" in sys.argv:
        from . import reminder
        sys.exit(reminder.remind_main())
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("SubPlayer")
    app.setWindowIcon(icons.app_icon())
    _install_error_log()
    theme.load_fonts()
    f = QFont()
    f.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Inter", "Vazirmatn"])
    f.setPointSize(10)
    app.setFont(f)
    st = load_settings()
    theme.apply(st.get("theme", "nebula"), st.get("accent", ""))
    w = Main()
    w.show()
    app._main_window = w
    sys.exit(app.exec())
