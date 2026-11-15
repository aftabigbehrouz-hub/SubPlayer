"""SubPlayer for Windows — main window: player, clickable subtitles, word card, My Words, review, practice."""
from __future__ import annotations

import html
import json
import os
import sys
import threading
import time
import urllib.parse
from pathlib import Path

from PySide6.QtCore import QObject, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
                               QMenu, QMessageBox, QProgressBar, QPushButton, QSizePolicy, QSlider, QStackedWidget,
                               QTextBrowser, QToolButton, QVBoxLayout, QWidget)

from . import VERSION, downloads, icons, licence, paths, subtitles, syncer, theme, translate
from .cosmos import Cosmos, GradientLabel, Orb
from .dictionary import Dictionary, clean_example, normalize
from .store import Progress, SavedWord, WordStore, now_ms

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


def ibtn(name, tip, fn=None, checkable=False, size=20, kind="icon", text="", color=theme.LIGHT, active=theme.CYAN):
    b = QPushButton(text, toolTip=tip, checkable=checkable)
    b.setIcon(icons.icon(name, color, size, active=active))
    b.setIconSize(QSize(size, size))
    b.setProperty("kind", kind)
    b.setCursor(Qt.PointingHandCursor)
    if fn:
        b.clicked.connect(fn)
    return b


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
        self.store = WordStore()
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
        from .pages import PracticePage, ReviewPage, WordsPage
        self.words_page = WordsPage(self)
        self.review_page = ReviewPage(self)
        self.practice_page = PracticePage(self)
        for p in (self.words_page, self.review_page, self.practice_page):
            self.stack.addWidget(p)
        bl.addWidget(self.stack, 1)
        bl.addWidget(self._panel())
        root.addWidget(body, 1)

        self.prog = QProgressBar(maximumWidth=260, visible=False)
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
                                    ("words", "star", "My Words", "Saved words and phrases"),
                                    ("review", "cards", "Review", "Review the words that are due"),
                                    ("practice", "puzzle", "Practice", "Gap-fill, dictation, der·die·das")):
            self.nav[key] = nav(ic, label, tip, lambda _=False, k=key: self.show_page(k))
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
        return rail

    def _panel(self) -> QFrame:
        self.panel = QFrame(objectName="panel")
        self.panel.setFixedWidth(410)
        v = QVBoxLayout(self.panel)
        v.setContentsMargins(18, 14, 14, 14)
        head = QHBoxLayout()
        head.addWidget(GradientLabel("Word card", 14, QFont.Bold))
        head.addStretch(1)
        x = ibtn("x", "Hide the word card", self.toggle_panel, size=16)
        head.addWidget(x)
        v.addLayout(head)
        self.card_view = QTextBrowser(openLinks=False)
        self.card_view.anchorClicked.connect(self._card_link)
        v.addWidget(self.card_view, 1)
        g = QGridLayout()
        g.setSpacing(8)
        self.save_btn = ibtn("star", "Save to My Words with this video moment", self.save_from_card, kind="", text=" Save")
        b_speak = ibtn("volume", "Speak (Windows voice)", lambda: self.speak_card(False), kind="", text=" Speak")
        b_slow = QPushButton("Slow", toolTip="Speak slowly")
        b_slow.clicked.connect(lambda: self.speak_card(True))
        b_sent = ibtn("translate", "Translate the whole sentence (online)", self.translate_sentence, kind="", text=" Sentence")
        self.learn_btn = ibtn("sparkles", "ChatGPT / Grok with a ready question, DWDS or Cambridge, dict.cc", self.learn_menu,
                              kind="", text=" Learn more")
        g.addWidget(self.save_btn, 0, 0)
        g.addWidget(b_speak, 0, 1)
        g.addWidget(b_slow, 0, 2)
        g.addWidget(b_sent, 1, 0, 1, 1)
        g.addWidget(self.learn_btn, 1, 1, 1, 2)
        v.addLayout(g)
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
                                   ("link", " Link", "Open a video from a web link — Tagesschau, any .mp4 (Ctrl+L)", self.link_dialog),
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
                        ("F", self.toggle_fullscreen), ("F11", self.toggle_fullscreen)):
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
        for b in (b1, b2):
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
        vf.addWidget(self.vw)
        theme.glow(self.vframe, theme.VIOLET, 40, 110)
        v.addWidget(self.vframe, 1)

        self.subs_frame = QFrame(objectName="subs")
        sl = QVBoxLayout(self.subs_frame)
        sl.setContentsMargins(14, 6, 14, 6)
        self.sub_view = QTextBrowser(openLinks=False)
        self.sub_view.setFixedHeight(112)
        self.sub_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sub_view.anchorClicked.connect(self._sub_click)
        sl.addWidget(self.sub_view)
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
        self.slider = QSlider(Qt.Horizontal)
        self.slider.sliderMoved.connect(lambda p: self.player.setPosition(p))
        self.slider.setCursor(Qt.PointingHandCursor)
        row.addWidget(self.time_lbl)
        row.addWidget(self.slider, 1)
        row.addWidget(self.dur_lbl)
        row.addSpacing(6)
        self.speed_btn = QPushButton("1×", toolTip="Slower speech: 1× → 0.75× → 0.5×")
        self.speed_btn.setProperty("kind", "chip")
        self.speed_btn.setMinimumWidth(58)
        self.speed_btn.clicked.connect(self.cycle_speed)
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
        self.pause_btn = chip(" Pause each line", "Stop after every line so you can read and click words", self.toggle_pause_each, True, "pause")
        self.shadow_btn = chip(" Shadowing", "Listen, then repeat aloud in the pause — the line plays again (S)", self.toggle_shadowing, True, "mic")
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
    def show_page(self, key: str):
        idx = {"player": 0, "words": 1, "review": 2, "practice": 3}[key]
        self.page = key
        for k, a in self.nav.items():
            a.setChecked(k == key)
        if key == "words":
            self.words_page.refresh()
        elif key == "review":
            self.review_page.start()
        elif key == "practice":
            self.practice_page.start()
        if key != "player":
            self.player.pause()
        else:
            self._fill_recents()
        self.stack.setCurrentIndex(idx)
        self.panel.setVisible(key == "player" and self.panel_open and not self.isFullScreen())
        self._update_motion()

    def toggle_panel(self):
        self.panel_open = not self.panel.isVisible()
        self.panel.setVisible(self.panel_open and self.page == "player")
        self.panel_btn.setChecked(self.panel_open)

    def show_panel(self):
        self.panel_open = True
        if self.page == "player" and not self.isFullScreen():
            self.panel.show()

    def _update_motion(self):
        playing = self.player.playbackState() == QMediaPlayer.PlayingState
        busy_video = playing and self.page == "player"
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

    def open_video(self, path: str, at_ms: int | None = None, play: bool = True):
        if self.video and self.video != path:
            self.remember_position()
        self.video = path
        self.video_name = Path(path).name
        self.player.setSource(QUrl.fromLocalFile(path))
        self.clear_ab()
        self.cues = []
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
        self._shown = None
        if info:
            self.msg(f"{info} · {len(cues)} lines")

    def toggle_play(self):
        if not self.video:
            self.open_dialog()
            return
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.shadow_resume = 0
        else:
            if self.held_cue >= 0:
                self.held_cue = -1
            self.shadow_resume = 0
            self.player.play()

    def seek_rel(self, d):
        self.player.setPosition(max(0, self.player.position() + d))

    def jump_line(self, step):
        if not self.cues:
            self.seek_rel(5000 * step)
            return
        pos = self.player.position()
        i = subtitles.index_before(self.cues, pos)
        if step < 0 and i >= 0 and pos - self.cues[i].start_ms > 1200:
            j = i
        else:
            j = max(0, min(len(self.cues) - 1, i + step))
        self.held_cue = -1
        if self.loop_line or self.shadowing:
            self.a, self.b = self.cues[j].start_ms, self.cues[j].end_ms + 150
            self._ab_label()
        self.player.setPosition(self.cues[j].start_ms)
        self.player.play()

    def cycle_speed(self):
        r = {1.0: 0.75, 0.75: 0.5}.get(round(self.player.playbackRate(), 2), 1.0)
        self.player.setPlaybackRate(r)
        self.speed_btn.setText(f"{r:g}×")
        self.speed_btn.setChecked(False)
        self.speed_btn.setProperty("accent", r < 1)
        theme.repolish(self.speed_btn)

    def set_a(self):
        self.a = self.player.position()
        if self.b >= 0 and self.b <= self.a:
            self.b = -1
        self._ab_label()

    def set_b(self):
        if self.a < 0:
            self.a = 0
        p = self.player.position()
        if p > self.a + 300:
            self.b = p
            self.player.setPosition(self.a)
            self.player.play()
        self._ab_label()

    def clear_ab(self):
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
        i = subtitles.index_before(self.cues, self.player.position())
        if i < 0:
            i = 0
        self.a, self.b = self.cues[i].start_ms, self.cues[i].end_ms + 150
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

    def toggle_pause_each(self):
        self.pause_each = self.pause_btn.isChecked()
        if self.pause_each:
            self.shadowing = False
            self.shadow_btn.setChecked(False)
            self.shadow_resume = 0
            self.msg("Pauses after every line — click words, then Space to go on")
        self._ab_label()

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
        if self.isFullScreen():
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
        if self.shadow_resume and time.monotonic() >= self.shadow_resume:
            self.shadow_resume = 0
            self.player.setPosition(self.a)
            self.player.play()
            self._ab_label()
        if playing and self.a >= 0 and self.b > self.a and pos >= self.b:
            if self.shadowing:
                self.player.pause()
                self.shadow_resume = time.monotonic() + (self.b - self.a) * 1.2 / 1000 + 0.6
                self._ab_label()
            else:
                self.player.setPosition(self.a)
            return
        i = subtitles.index_at(self.cues, pos) if self.cues else -1
        if playing and self.pause_each and self.cues:
            j = subtitles.index_before(self.cues, pos)
            if j >= 0 and j != self.held_cue and pos >= self.cues[j].end_ms - 60:
                self.held_cue = j
                self.player.pause()
                i = j
        if i < 0 and not playing and self.held_cue >= 0:
            i = self.held_cue
        if i < 0 and self.shadowing and self.cues and self.a >= 0:
            i = subtitles.index_before(self.cues, self.a + 50)
        if i < 0 and self.card and not playing and self.card.get("cue", -1) >= 0:
            i = self.card["cue"]
        if getattr(self, "_shown", None) != (i, len(self.cues), self._saved_version()):
            self._shown = (i, len(self.cues), self._saved_version())
            self._render_sub(i)

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
        s = self.progress.streak
        self.streak_lbl.setText(f"🔥 {s} day{'s' if s != 1 else ''}" if s else "")

    def _render_sub(self, i: int):
        if i < 0:
            self.sub_view.setHtml("")
            return
        text = self.cues[i].text
        saved = self._saved_cache[1]
        out, last = [], 0
        for k, (s, e, tok) in enumerate(subtitles.tokens(text)):
            out.append(html.escape(text[last:s]).replace("\n", "<br>"))
            col = theme.GOLD if tok.lower() in saved else "#FFFFFF"
            if self.phrase_start and self.phrase_start[0] == i and self.phrase_start[1] == k:
                col = theme.MAGENTA
            out.append(f"<a href='w:{i}:{k}' style='color:{col};text-decoration:none'>{html.escape(tok)}</a>")
            last = e
        out.append(html.escape(text[last:]).replace("\n", "<br>"))
        self.sub_view.setHtml(f"<div style='text-align:center;font-size:21pt;font-weight:600;line-height:145%'>{''.join(out)}</div>")

    # ================================================================== words in subtitles
    def _sub_click(self, url: QUrl):
        s = url.toString()
        if not s.startswith("w:"):
            return
        _, ci, ti = s.split(":")
        ci, ti = int(ci), int(ti)
        toks = subtitles.tokens(self.cues[ci].text)
        word = toks[ti][2]
        mods = QApplication.keyboardModifiers()
        self.player.pause()
        self.shadow_resume = 0
        a, b = subtitles.sentence_range(self.cues, ci)
        sentence = subtitles.sentence_text(self.cues, a, b)
        start, end = self.cues[a].start_ms, self.cues[b].end_ms
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
        self.show_panel()
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
                     f"<p style='color:{theme.DIM}'>Not in the offline dictionary (names and rare words may be missing).</p>")
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
            h.append(" &nbsp;·&nbsp; ".join(meta))
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
        self.show_panel()
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
        saved = bool(c) and self.store.find(c["word"], self.video or "", c["start"]) is not None
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
        self.store.insert(w)
        self.after_change()
        self._update_save_btn()
        self.msg("★ Saved to My Words — it will come up for review")

    def after_change(self):
        self.refresh_words()
        if self.settings.get("sync_token"):
            self.sync_timer.start()

    def speak_card(self, slow):
        c = self.card
        if c:
            e = c.get("entries") or []
            self.speak(e[0].lemma if e and c["kind"] == "word" else c["word"], slow, c["lang"])

    def speak(self, text: str, slow: bool = False, lang: str = "de"):
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
                    "2) IPA (UK and US), word forms, and common collocations.\n"
                    "3) Exactly 3 natural example sentences of everyday English, one per line, in this format:\nEN: … | DE: … | FA: …")
        return (f"Explain the German word „{word}“" + (f" as used in: „{s}“" if s else "") + ".\n"
                "1) Meaning in English and in Persian.\n"
                "2) IPA; for nouns article and plural, for verbs Präteritum and Perfekt.\n"
                "3) Exactly 3 natural example sentences (Beispielsätze) of everyday German, one per line, in this format:\nDE: … | EN: … | FA: …")

    def learn_more(self, source, word, sentence, lang):
        q = urllib.parse.quote
        if source in ("chatgpt", "grok"):
            p = self.ai_prompt(word, sentence, lang)
            QApplication.clipboard().setText(p)
            url = ("https://chatgpt.com/?q=" if source == "chatgpt" else "https://grok.com/?q=") + q(p)
            self.msg("Question copied too — paste it if the chat opens empty. Then copy the 3 sentences back and use ＋ Add sentences.", 10000)
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

    def fill_learn_menu(self, m: QMenu, word, sentence, lang, saved_getter):
        m.addAction(icons.icon("sparkles", theme.CYAN, 16), "ChatGPT — meaning + 3 sentences", lambda: self.learn_more("chatgpt", word, sentence, lang))
        m.addAction(icons.icon("sparkles", theme.MAGENTA, 16), "Grok — meaning + 3 sentences", lambda: self.learn_more("grok", word, sentence, lang))
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
        if not self.store.find(c["word"], self.video or "", c["start"]):
            self.save_from_card()
        return self.store.find(c["word"], self.video or "", c["start"])

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
            found = linkimport.resolve(url)

            def prog(done, total):
                mb = done // 1_048_576
                self._bg_progress(done / total if total else 0, f"Downloading “{found.title}” · {mb} MB"
                                  + (f" of {total // 1_048_576} MB" if total else ""))
            return linkimport.download(found, progress=prog, cancelled=lambda: self.cancel)
        self.run_bg("link", job, cancellable=True, label="Opening the link…")

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
        heavy = kind in ("subs", "download", "link", "clip")
        if heavy and self.busy:
            self.msg("Please wait — " + self.busy)
            return
        if heavy:
            self.busy = label or kind
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

    def _on_done(self, kind, res):
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
            self._end_task()
            self.open_video(str(res), at_ms=0)
            self.msg(f"Saved to {res.parent} — click Subtitles to transcribe it", 12000)
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
        if kind in ("subs", "download", "link", "clip"):
            self._end_task()
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

    def closeEvent(self, e):
        self.remember_position()
        if self.sync_timer.isActive() and self.settings.get("sync_token"):
            try:   # last changes go up before closing
                syncer.sync_now(self.settings["sync_token"], self.settings.get("gist_id"), self.store, self.progress, syncer.subs_dir())
            except Exception:
                pass
        super().closeEvent(e)

    def play_clip(self, w: SavedWord, after=None):
        """Plays the saved word's video moment (finds the video by name if it moved)."""
        path = w.video_uri if w.video_uri and os.path.exists(w.video_uri) else \
            next((r["path"] for r in self.recents() if r["name"].lower() == w.video_name.lower() and os.path.exists(r["path"])), None)
        if not path:
            self.msg(f"Video “{w.video_name}” not found on this PC — open it once (same file name) and try again", 9000)
            return False
        if self.video != path:
            self.open_video(path, at_ms=max(0, w.start_ms), play=False)
        self.a, self.b = max(0, w.start_ms - 200), w.end_ms + 300
        self._ab_label()
        self.player.setPosition(self.a)
        self.player.play()
        return True


def selftest(out: str) -> int:
    """Used by the build: proves the packaged app can load everything it needs."""
    lines, ok = [], True
    for mod in ("faster_whisper", "ctranslate2", "av", "onnxruntime", "numpy", "PySide6.QtMultimedia", "PySide6.QtTextToSpeech",
                "PySide6.QtSvg", "cryptography", "requests"):
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
    theme.load_fonts()
    f = QFont()
    f.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Inter", "Vazirmatn"])
    f.setPointSize(10)
    app.setFont(f)
    w = Main()
    w.show()
    sys.exit(app.exec())
