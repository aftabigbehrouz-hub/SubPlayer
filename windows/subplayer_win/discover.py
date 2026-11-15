"""Discover: search the German public broadcasters' libraries and suggested programmes by level; one click downloads the
programme (and the broadcaster's own subtitles) and opens it in the player."""
from __future__ import annotations

import html
import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
                               QScrollArea, QSizePolicy, QTextBrowser, QVBoxLayout, QWidget)

from . import english, mediathek, theme
from .cosmos import GradientLabel

CH_COLOR = {"ARD": "#3B7BFF", "ZDF": "#FF8A1F", "3sat": "#E8364F", "Arte": "#FF5A36", "DW": "#19B6FF", "KiKA": "#7CCB2B",
            "phoenix": "#22B8D8", "BR": "#4AA3FF", "SWR": "#3FD0B0", "WDR": "#4F86FF", "NDR": "#2F7DE1", "MDR": "#5C9DFF",
            "HR": "#3C8CFF", "RBB": "#E84B6B", "ORF": "#E8364F", "SRF": "#E8364F", "VOA": "#3D8BFF", "NASA": "#FF5A3C"}
DE_CHANNELS = ("ARD", "ZDF", "3sat", "Arte", "DW", "KiKA", "phoenix")
EN_CHANNELS = ("VOA", "NASA")


def ibtn(*a, **k):
    from .app import ibtn as _ib
    return _ib(*a, **k)


class _Relay(QObject):
    done = Signal(int, object)
    failed = Signal(int, str)


def badge(text: str, color: str) -> QLabel:
    b = QLabel(text)
    b.setStyleSheet(f"background:{color}22;border:1px solid {color}99;color:{color};border-radius:8px;padding:1px 7px;"
                    "font-weight:700;font-size:8.5pt")
    return b


class FilmCard(QFrame):
    def __init__(self, film: mediathek.Film, on_pick, width: int = 250):
        super().__init__(objectName="recent")
        self.film, self.on_pick = film, on_pick
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(width)
        self.setMinimumHeight(132)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 11, 14, 11)
        v.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(badge(film.label, CH_COLOR.get(film.label, theme.VIOLET)))
        if film.has_subtitles:
            cc = badge("CC", theme.MINT)
            cc.setToolTip("Comes with the broadcaster's own subtitles — no transcription needed")
            top.addWidget(cc)
        top.addStretch(1)
        top.addWidget(QLabel(film.length, objectName="small"))
        v.addLayout(top)
        t = QLabel()
        t.setWordWrap(True)
        t.setStyleSheet("font-weight:650;font-size:10.5pt")
        fm = t.fontMetrics()
        title = film.title
        if fm.horizontalAdvance(title) > (width - 28) * 2:
            title = fm.elidedText(title, Qt.ElideRight, (width - 28) * 2 - 20)
        t.setText(title)
        v.addWidget(t)
        tp = QLabel(fm.elidedText(film.topic, Qt.ElideRight, width - 28), objectName="small")
        v.addWidget(tp)
        v.addStretch(1)
        v.addWidget(QLabel(film.date, objectName="small"))

    def mousePressEvent(self, e):
        self.on_pick(self)

    def set_selected(self, on: bool):
        self.setStyleSheet(f"QFrame#recent{{border:1px solid {theme.CYAN};background:rgba(62,240,255,0.10)}}" if on else "")


class DiscoverPage(QWidget):
    def __init__(self, main):
        super().__init__(objectName="page")
        self.main = main
        self.gen = 0
        self.offset = 0
        self.mode = "shelves"
        self.selected: FilmCard | None = None
        self.shelves_loaded = False
        self.lang = main.settings.get("discover_lang", "de")
        self.relay = _Relay()
        self.relay.done.connect(self._done)
        self.relay.failed.connect(self._failed)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        # ------------------------------------------------ left: search + results
        left = QFrame(objectName="card")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(20, 16, 12, 14)
        lv.setSpacing(10)
        head = QHBoxLayout()
        head.addWidget(GradientLabel("Discover", 22, QFont.Black))
        sub = QLabel("Free programmes from ARD, ZDF, 3sat, Arte, DW and more — download, then learn with subtitles",
                     objectName="hint")
        sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        head.addWidget(sub, 1)
        lv.addLayout(head)

        row = QHBoxLayout()
        self.lang_btns = {}
        for code, label in (("de", "Deutsch"), ("en", "English")):
            b = QPushButton(label, checkable=True)
            b.setProperty("kind", "chip")
            b.setToolTip("German programmes (ARD, ZDF, 3sat, Arte, DW…)" if code == "de" else
                         "English programmes (VOA Learning English, NASA)")
            b.clicked.connect(lambda _=False, c=code: self.set_lang(c))
            self.lang_btns[code] = b
            row.addWidget(b)
        self.q = QLineEdit(placeholderText="Search programmes — e.g. Terra X, Tatort, Wirtschaft, Klimawandel, logo!")
        self.q.returnPressed.connect(lambda: self.search(new=True))
        row.addWidget(self.q, 1)
        go = ibtn("search", "Search", lambda: self.search(new=True), kind="", text=" Search", size=16, color="#FFFFFF")
        go.setProperty("accent", True)
        row.addWidget(go)
        home = ibtn("sparkles", "Back to the suggestions", self.show_shelves, kind="", text=" Suggestions", size=16)
        row.addWidget(home)
        lv.addLayout(row)

        f = QHBoxLayout()
        f.setSpacing(6)
        self.ch_btns = {}
        for ch in DE_CHANNELS + EN_CHANNELS:
            b = QPushButton(ch, checkable=True)
            b.setProperty("kind", "chip")
            b.setToolTip(f"Only {ch} (several can be ticked; none = all channels)")
            b.clicked.connect(lambda _=False: self.search(new=True) if self.mode == "search" or self.q.text().strip() else self._chips_changed())
            self.ch_btns[ch] = b
            f.addWidget(b)
        f.addSpacing(8)
        self.length = QComboBox()
        self.length.addItems(list(mediathek.LENGTHS))
        self.length.currentIndexChanged.connect(lambda _: self.search(new=True) if self.mode == "search" else None)
        f.addWidget(self.length)
        self.cc_only = QCheckBox("With subtitles")
        self.cc_only.setToolTip("Only programmes with the broadcaster's own subtitles (ready to learn, no transcription)")
        self.cc_only.toggled.connect(lambda _: self.search(new=True) if self.mode == "search" else None)
        f.addWidget(self.cc_only)
        f.addStretch(1)
        lv.addLayout(f)

        self.status = QLabel("", objectName="hint")
        lv.addWidget(self.status)
        self.scroll = QScrollArea(widgetResizable=True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body = QWidget(objectName="page")
        self.bv = QVBoxLayout(self.body)
        self.bv.setContentsMargins(0, 0, 8, 0)
        self.bv.setSpacing(16)
        self.bv.addStretch(1)
        self.scroll.setWidget(self.body)
        lv.addWidget(self.scroll, 1)
        root.addWidget(left, 1)

        # ------------------------------------------------ right: the chosen programme
        right = QFrame(objectName="card")
        right.setFixedWidth(380)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(20, 18, 16, 16)
        self.info = QTextBrowser(openLinks=False)
        self.info.anchorClicked.connect(lambda u: QDesktopServices.openUrl(u))
        rv.addWidget(self.info, 1)
        self.dl_btn = ibtn("download", "Download the programme and open it in the player", self.download, kind="",
                           text="  Download && open", size=18, color="#FFFFFF")
        self.dl_btn.setProperty("accent", True)
        self.dl_btn.setMinimumHeight(44)
        rv.addWidget(self.dl_btn)
        r2 = QHBoxLayout()
        self.q_btn = ibtn("film", "Choose the picture quality", self.quality_menu, kind="", text=" Quality: normal", size=15)
        self.web_btn = ibtn("link", "Open the broadcaster's page in the browser", self.open_web, kind="", text=" Web page", size=15)
        r2.addWidget(self.q_btn)
        r2.addWidget(self.web_btn)
        rv.addLayout(r2)
        root.addWidget(right)
        self.quality = "normal"
        self._apply_lang()
        self._show_info(None)

    # ------------------------------------------------------------------ German / English
    def set_lang(self, code: str):
        if code == self.lang:
            self.lang_btns[code].setChecked(True)
            return
        self.lang = code
        self.main.settings["discover_lang"] = code
        self.main.save_settings()
        self._apply_lang()
        self.shelves_loaded = False
        self.show_shelves()

    def _apply_lang(self):
        en = self.lang == "en"
        for c, b in self.lang_btns.items():
            b.setChecked(c == self.lang)
        for ch, b in self.ch_btns.items():
            b.setVisible(ch in (EN_CHANNELS if en else DE_CHANNELS))
            if not b.isVisible():
                b.setChecked(False)
        self.length.setVisible(not en)
        self.cc_only.setVisible(not en)
        self.q.setPlaceholderText("Search programmes — e.g. grammar, Mars, interview, climate, Thanksgiving" if en else
                                  "Search programmes — e.g. Terra X, Tatort, Wirtschaft, Klimawandel, logo!")
        self._show_info(None)

    # ------------------------------------------------------------------ background calls
    def _run(self, fn):
        self.gen += 1
        g = self.gen

        def work():
            try:
                self.relay.done.emit(g, fn())
            except Exception as e:
                self.relay.failed.emit(g, str(e) or type(e).__name__)
        threading.Thread(target=work, daemon=True).start()
        return g

    def _done(self, g, res):
        if g != self.gen:
            return
        kind, payload = res
        if kind == "shelves":
            self._render_shelves(payload)
        elif kind == "search":
            films, total, new = payload
            self._render_results(films, total, new)

    def _failed(self, g, err):
        if g != self.gen:
            return
        low = err.lower()
        why = ("no connection" if any(k in low for k in ("connectionpool", "max retries", "connection", "resolve", "proxy"))
               else "it took too long" if "timed out" in low or "timeout" in low else err[:140])
        self.status.setText(f"<span style='color:{theme.MAGENTA}'>Couldn't reach the programme catalogue — {html.escape(why)}.</span>"
                            "<br>Check the internet connection. Where it is filtered (e.g. in Iran) turn on your VPN — "
                            "Settings ▸ Internet connection ▸ Test connection shows what works.")

    # ------------------------------------------------------------------ views
    def activate(self):
        if not self.shelves_loaded and self.mode == "shelves":
            self.show_shelves()

    def _clear(self):
        self.selected = None
        while self.bv.count():
            it = self.bv.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
            elif it.layout():
                self._clear_layout(it.layout())

    def _clear_layout(self, lay):
        while lay.count():
            it = lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                self._clear_layout(it.layout())

    def _cols(self) -> tuple[int, int]:
        """(cards per row, card width) filling the visible width."""
        w = self.scroll.viewport().width()
        if w < 300:                                     # not laid out yet: estimate from the page
            w = self.width() - 380 - 14 - 46
        w = max(560, w - 10)
        cols = max(2, min(5, (w + 12) // 262))
        return cols, int((w - (cols - 1) * 12) / cols)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not hasattr(self, "_relayout"):
            from PySide6.QtCore import QTimer
            self._relayout = QTimer(self, singleShot=True, interval=180, timeout=self._redo_layout)
        self._relayout.start()

    def _redo_layout(self):
        last = getattr(self, "_last", None)
        if not last or self._cols() == getattr(self, "_last_cols", None):
            return
        sel = self.selected.film if self.selected else None
        if last[0] == "shelves":
            self._render_shelves(last[1])
        else:
            self._render_results(last[1], last[2], True, keep_offset=True)
        if sel:
            for c in self.body.findChildren(FilmCard):
                if c.film is sel:
                    self.pick(c)
                    break

    def _chosen_channels(self) -> list[str]:
        return [c for c, b in self.ch_btns.items() if b.isChecked()]

    def _chips_changed(self):
        if self._chosen_channels():
            self.search(new=True)

    def show_shelves(self):
        self.mode = "shelves"
        self.q.clear()
        for b in self.ch_btns.values():
            b.setChecked(False)
        self._clear()
        self.bv.addStretch(1)
        self.status.setText("Loading suggestions…")
        src = english if self.lang == "en" else mediathek
        shelves = src.SHELVES

        def job():
            from concurrent.futures import ThreadPoolExecutor
            first = src.shelf_films(shelves[0], 10)          # fails fast when there is no connection

            def one(sh):
                try:
                    return sh, src.shelf_films(sh, 10)
                except Exception as e:
                    return sh, e
            with ThreadPoolExecutor(max_workers=4) as ex:
                rest = list(ex.map(one, shelves[1:]))
            return "shelves", [(shelves[0], first)] + rest
        self._run(job)

    def _render_shelves(self, shelves):
        self._clear()
        self._last = ("shelves", shelves)
        self._last_cols = self._cols()
        self.shelves_loaded = True
        self.status.setText("Suggestions by level — always the newest episodes. Click a programme to see it; "
                            "<b style='color:#5BE38F'>CC</b> = comes with the broadcaster's subtitles.")
        cols, cw = self._cols()
        shown = 0
        for sh, films in shelves:
            if isinstance(films, Exception) or not films:
                continue
            shown += 1
            box = QVBoxLayout()
            box.setSpacing(8)
            h = QHBoxLayout()
            t = QLabel(sh.title)
            t.setStyleSheet("font-weight:800;font-size:12.5pt")
            h.addWidget(t)
            h.addWidget(badge(sh.level, theme.GOLD))
            why = QLabel(sh.why, objectName="hint")
            h.addWidget(why, 1)
            more = ibtn("search", "Show more of these", lambda _=False, s=sh: self.search_shelf(s), kind="link", text=" More", size=14,
                        color=theme.CYAN)
            h.addWidget(more)
            box.addLayout(h)
            g = QHBoxLayout()
            g.setSpacing(12)
            for f in films[:cols]:
                g.addWidget(FilmCard(f, self.pick, cw))
            g.addStretch(1)
            box.addLayout(g)
            self.bv.addLayout(box)
        if not shown:
            self.status.setText("No suggestions right now — try a search.")
        self.bv.addStretch(1)

    def search_shelf(self, sh):
        self.mode = "search"
        if self.lang == "en":
            self.q.setText(getattr(sh, "nasa", "") or "")
            self._shelf = sh
            self.search(new=True, shelf=sh)
            return
        self.q.setText(sh.text or sh.topic or sh.title_q)
        for c, b in self.ch_btns.items():
            b.setChecked(c in sh.channels)
        self._shelf = sh
        self.search(new=True, shelf=sh)

    def search(self, new=True, shelf=None):
        text = self.q.text().strip()
        chans = self._chosen_channels()
        if not text and not chans and shelf is None:
            self.show_shelves()
            return
        self.mode = "search"
        if new:
            self.offset = 0
            self._clear()
            self.bv.addStretch(1)
        length = mediathek.LENGTHS[self.length.currentText()]
        cc = self.cc_only.isChecked()
        off = self.offset
        self.status.setText("Searching…")

        en = self.lang == "en"

        def job():
            if en:
                if shelf is not None and getattr(shelf, "feed", ""):
                    films = english.voa_feed(shelf.feed, 40) if off == 0 else []
                    return "search", (films, len(films), new)
                films, total = english.search(text or getattr(shelf, "nasa", ""), chans, 30, off)
                return "search", (films, total, new)
            if shelf is not None:
                films, total = mediathek.search(shelf.text, shelf.channels, shelf.topic, shelf.title_q, length if any(length) else shelf.length,
                                                off, 30, cc)
            else:
                films, total = mediathek.search(text, chans, length=length, offset=off, size=30, subtitles_only=cc)
            return "search", (films, total, new)
        self._run(job)

    def _render_results(self, films, total, new, keep_offset=False):
        if new and not keep_offset:
            self._results = list(films)
        elif not keep_offset:
            self._results = getattr(self, "_results", []) + list(films)
        if keep_offset:
            self._clear()
            films = list(getattr(self, "_results", films))
        self._last = ("search", list(getattr(self, "_results", films)), total)
        self._last_cols = self._cols()
        # drop the trailing stretch / "more" button
        while self.bv.count() and (self.bv.itemAt(self.bv.count() - 1).spacerItem() or
                                   isinstance(self.bv.itemAt(self.bv.count() - 1).widget(), QPushButton)):
            it = self.bv.takeAt(self.bv.count() - 1)
            if it.widget():
                it.widget().deleteLater()
        if new and not films:
            self.status.setText("Nothing found. Try fewer or other words, another channel, or untick “With subtitles”.")
            self.bv.addStretch(1)
            return
        if not keep_offset:
            self.offset += 30
        self.status.setText(f"{total:,} programmes found" + (" (showing those with subtitles)" if self.cc_only.isChecked() else "")
                            + " — newest first.")
        cols, cw = self._cols()
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, f in enumerate(films):
            grid.addWidget(FilmCard(f, self.pick, cw), i // cols, i % cols, Qt.AlignLeft | Qt.AlignTop)
        grid.setColumnStretch(cols, 1)
        self.bv.addLayout(grid)
        if self.offset < total and films:
            more = QPushButton("Load more")
            more.clicked.connect(lambda: self.search(new=False, shelf=getattr(self, "_shelf", None) if self.q.text().strip() ==
                                                     (getattr(self, "_shelf", None) and (self._shelf.text or self._shelf.topic or self._shelf.title_q)) else None))
            self.bv.addWidget(more, 0, Qt.AlignHCenter)
        self.bv.addStretch(1)

    # ------------------------------------------------------------------ details + download
    def pick(self, card: FilmCard):
        if self.selected is not None:
            try:
                self.selected.set_selected(False)
            except RuntimeError:
                pass
        self.selected = card
        card.set_selected(True)
        self._show_info(card.film)

    def _show_info(self, f: mediathek.Film | None):
        self.dl_btn.setEnabled(f is not None)
        self.q_btn.setEnabled(f is not None and f.channel not in ("VOA", "NASA"))
        self.web_btn.setEnabled(bool(f and f.url_website))
        if f is None and self.lang == "en":
            self.info.setHtml(f"<p style='font-size:19pt;font-weight:800;color:{theme.CYAN};margin-bottom:6px'>Pick a programme</p>"
                              f"<p style='color:{theme.DIM};line-height:150%'><b>VOA Learning English</b> — lessons made for "
                              "learners by Voice of America (public domain): Let's Learn English, English in a Minute, grammar, "
                              "pronunciation. VOA stopped publishing in 2025, so these are its archive.</p>"
                              f"<p style='color:{theme.DIM};line-height:150%'><b>NASA</b> — science and space videos (public domain); "
                              "most bring English subtitles.</p>"
                              f"<p style='color:{theme.DIM};line-height:150%'>Download & open saves the video to "
                              "<b>Videos\\SubPlayer</b>; videos without subtitles get them with <b>Subtitles</b>.</p>")
            return
        if f is None:
            self.info.setHtml(f"<p style='font-size:19pt;font-weight:800;color:{theme.CYAN};margin-bottom:6px'>Pick a programme</p>"
                              f"<p style='color:{theme.DIM};line-height:150%'>Everything here is offered free by the broadcasters "
                              "themselves as a video file. SubPlayer downloads it to <b>Videos\\SubPlayer</b>, so it plays offline, "
                              "and opens it ready to learn.</p>"
                              f"<p style='color:{theme.DIM};line-height:150%'><b style='color:{theme.MINT}'>CC</b> programmes bring the "
                              "broadcaster's own subtitles — click words straight away. Others get subtitles with <b>Subtitles</b>.</p>"
                              f"<p style='color:{theme.DIM};line-height:150%'>Some programmes can only be watched from Germany "
                              "(Austria/Switzerland). From other countries use a VPN or proxy set to Germany: "
                              "Settings ▸ Internet connection.</p>")
            return
        col = CH_COLOR.get(f.label, theme.VIOLET)
        if f.channel in ("VOA", "NASA"):
            cc = (f"<span style='color:{theme.DIM}'>NASA videos usually bring English subtitles — they come along when there are</span>"
                  if f.channel == "NASA" else f"<span style='color:{theme.DIM}'>no subtitle file — SubPlayer makes them after "
                                              "downloading (VOA's lessons are slow and clear)</span>")
        else:
            cc = (f"<span style='color:{theme.MINT};font-weight:700'>✓ with the broadcaster's subtitles</span>" if f.has_subtitles
                  else f"<span style='color:{theme.DIM}'>no subtitles from the broadcaster — SubPlayer can make them</span>")
        size = f" · about {f.size / 1e6:,.0f} MB" if f.size else ""
        desc = html.escape(f.description or "").replace("\n", "<br>")
        self.info.setHtml(
            f"<p style='margin:0'><span style='color:{col};font-weight:800'>{html.escape(f.label)}</span>"
            f"<span style='color:{theme.DIM}'> · {html.escape(f.topic)}</span></p>"
            f"<p style='font-size:16pt;font-weight:800;margin:6px 0 8px 0'>{html.escape(f.title)}</p>"
            f"<p style='color:{theme.DIM};margin:0'>{' · '.join(x for x in (f.date, f.length) if x)}{size}</p>"
            f"<p style='margin:6px 0 12px 0'>{cc}</p>"
            f"<p style='line-height:150%'>{desc or '<i>No description.</i>'}</p>")

    def quality_menu(self):
        if not self.selected:
            return
        f = self.selected.film
        m = QMenu(self)
        for key, label, ok in (("normal", "Normal (recommended)", True), ("hd", "HD — bigger file", bool(f.url_video_hd)),
                               ("low", "Small — slow internet", bool(f.url_video_low))):
            a = m.addAction(("✓ " if key == self.quality else "   ") + label)
            a.setEnabled(ok)
            a.triggered.connect(lambda _=False, k=key: self._set_quality(k))
        m.exec(self.q_btn.mapToGlobal(self.q_btn.rect().bottomLeft()))

    def _set_quality(self, k):
        self.quality = k
        self.q_btn.setText(" Quality: " + {"normal": "normal", "hd": "HD", "low": "small"}[k])

    def open_web(self):
        if self.selected and self.selected.film.url_website:
            QDesktopServices.openUrl(QUrl(self.selected.film.url_website))

    def download(self):
        if self.selected:
            self.main.import_film(self.selected.film, self.quality)
