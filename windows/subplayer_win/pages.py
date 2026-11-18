"""My Words, Review and Practice pages."""
from __future__ import annotations

import html
import random

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
                               QPushButton, QSizePolicy, QTextBrowser, QVBoxLayout, QWidget)

from . import icons, practice, theme
from .cosmos import GradientLabel
from .store import Question, SavedWord, due_label, now_ms, review


def card() -> QFrame:
    f = QFrame(objectName="card")
    return f


def ibtn(*a, **k):
    from .app import ibtn as _ib
    return _ib(*a, **k)


def article_html(w) -> str:
    return f"<span style='color:{theme.ARTICLE.get(w.article, theme.LIGHT)}'>{w.article} </span>" if w.article else ""


def highlight(sentence: str, word: str) -> str:
    s = html.escape(sentence)
    i = s.lower().find(html.escape(word).lower()) if word else -1
    if i < 0:
        return s
    j = i + len(html.escape(word))
    return f"{s[:i]}<span style='color:{theme.GOLD};font-weight:700'>{s[i:j]}</span>{s[j:]}"


def sentences_of(main, w):
    """The video line first, then added example sentences (sentence, translation, persian)."""
    out = []
    if w.sentence:
        out.append((w.sentence, "", ""))
    out += [(e.de, e.en, e.fa) for e in main.store.examples(w.id)]
    return out


class Pane(QFrame):
    """One of the four panels of a word in My Words. Click its title (or ⤢) to make it big; click again to go back."""

    def __init__(self, title: str, on_toggle):
        super().__init__(objectName="card")
        self.title, self.on_toggle = title, on_toggle
        self.setMinimumSize(200, 150)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 8, 8, 10)
        v.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(4)
        self.lbl = QLabel(f"<span style='color:{theme.CYAN};font-weight:700;letter-spacing:2px;font-size:9pt'>{title.upper()}</span>")
        self.lbl.setCursor(Qt.PointingHandCursor)
        self.lbl.setToolTip("Click to make this panel big (click again to go back)")
        self.lbl.mousePressEvent = lambda e: self.on_toggle(self)
        head.addWidget(self.lbl)
        self.count = QLabel("", objectName="small")
        head.addWidget(self.count)
        head.addStretch(1)
        self.extra = QHBoxLayout()
        self.extra.setSpacing(4)
        head.addLayout(self.extra)
        self.big_btn = ibtn("fullscreen", "Make this panel big", lambda: self.on_toggle(self), kind="chip", size=13)
        head.addWidget(self.big_btn)
        v.addLayout(head)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        v.addLayout(self.body, 1)

    def add_button(self, b):
        self.extra.addWidget(b)

    def set_big(self, on: bool):
        from . import icons as _ic
        self.big_btn.setIcon(_ic.icon("x" if on else "fullscreen", theme.LIGHT, 13))
        self.big_btn.setToolTip("Back to the four panels" if on else "Make this panel big")


class SnapLabel(QLabel):
    """The picture of the video moment, scaled to the panel (click = play it here)."""
    clicked = Signal()

    def __init__(self):
        super().__init__(alignment=Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setCursor(Qt.PointingHandCursor)
        self._pm = None

    def set_file(self, path, text=""):
        from PySide6.QtGui import QPixmap
        self._pm = QPixmap(str(path)) if path else None
        if not self._pm or self._pm.isNull():
            self._pm = None
            self.setPixmap(QPixmap())
            self.setText(text)
        else:
            self.setText("")
            self._fit()

    def _fit(self):
        if self._pm:
            self.setPixmap(self._pm.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()

    def mousePressEvent(self, e):
        self.clicked.emit()


def _q(t: str) -> str:
    import urllib.parse
    return urllib.parse.quote(t, safe="")


def dictionary_html(main, w) -> str:
    """The offline dictionary for a saved word: forms, IPA, English, Persian, the meanings with examples, synonyms."""
    e_ = html.escape
    d = main.dictionary(w.lang)
    entries = []
    if d and " " not in w.text.strip():
        try:
            entries = [x for x in d.lookup(w.lemma or w.text) if x.pos != "name"][:3] or d.lookup(w.text)[:3]
        except Exception:
            entries = []
    sec = lambda t: (f"<p style='color:{theme.CYAN};font-weight:700;letter-spacing:2px;font-size:8.5pt;margin:12px 0 4px 0'>"
                     f"{t.upper()}</p>")
    h = ["<div style='font-size:10.5pt;line-height:140%'>"]
    if not entries:
        if w.english:
            h.append(sec("Meaning") + e_(w.english))
        if w.persian:
            h.append(sec("فارسی") + theme.fa_span(e_(w.persian), "13pt"))
        h.append(f"<p style='color:{theme.DIM}'>" + ("Not in the offline dictionary." if d else
                                                    "The dictionary isn't downloaded yet — click any word in a subtitle once.") + "</p>")
    for n, e in enumerate(entries):
        if n:
            h.append(f"<hr style='background:{theme.VIOLET}'>")
        art = f"<span style='color:{theme.ARTICLE.get(e.article, theme.LIGHT)}'>{e.article} </span>" if e.article else ""
        h.append(f"<p style='font-size:15pt;font-weight:800;margin:0'>{art}{e_(e.lemma)}</p>")
        meta = [f"<span style='color:{theme.MAGENTA}'>{e_(e.pos_de or e.pos)}</span>"]
        if e.ipa:
            meta.append(f"<span style='color:{theme.GOLD}'>{e_(e.ipa)}</span>")
        if e.hyphenation:
            meta.append(f"<span style='color:{theme.DIM}'>{e_(e.hyphenation)}</span>")
        h.append(" · ".join(meta))
        if e.lang == "en" and e.german:
            h.append(sec("Deutsch") + e_(", ".join(e.german[:6])))
        if e.lang != "en" and e.english:
            h.append(sec("English") + "<br>".join(f"<span style='color:{theme.DIM}'>{k}.</span> {e_(g)}" for k, g in enumerate(e.english[:6], 1)))
        fa = e.persian or e.persian_via_english
        if fa:
            h.append(sec("فارسی") + theme.fa_span(e_("، ".join(fa)), "13pt"))
        if e.senses:
            h.append(sec("Definitions" if e.lang == "en" else "Bedeutungen"))
            for k, sn in enumerate(e.senses[:8], 1):
                h.append(f"<p style='margin:4px 0'><span style='color:{theme.CYAN}'>{k}</span>&nbsp; {e_(sn.de)}</p>")
                for ex in sn.examples[:2]:
                    h.append(f"<p style='margin:1px 0 1px 14px;color:{theme.DIM}'><i>{e_(ex)}</i> "
                             f"<a href='sayt:{_q(ex)}' style='color:{theme.CYAN};text-decoration:none'>🔊</a></p>")
        if e.synonyms:
            h.append(sec("Synonyms" if e.lang == "en" else "Synonyme") + e_(" · ".join(e.synonyms[:10])))
    h.append("</div>")
    return "".join(h)


# ==================================================================== My Words
CATS = (("all", "All"), ("phrase", "Phrases"), ("noun", "Nouns"), ("verb", "Verbs"), ("adj", "Adjectives"), ("other", "Others"))


class WordsPage(QWidget):
    def __init__(self, main):
        super().__init__(objectName="page")
        from PySide6.QtWidgets import QCalendarWidget, QComboBox
        self.main = main
        self.cat = "all"
        self.day = None                     # a date picked in the calendar (datetime.date) or None
        self._pos: dict[int, str] = {}
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)
        lcard = card()
        left = QVBoxLayout(lcard)
        left.setContentsMargins(18, 16, 18, 16)
        head = QHBoxLayout()
        self.title = GradientLabel("My Words", 22, QFont.Black)
        head.addWidget(self.title)
        head.addStretch(1)
        self.stats = QLabel("", objectName="hint")
        head.addWidget(self.stats)
        left.addLayout(head)
        crow = QHBoxLayout()
        crow.setSpacing(5)
        self.cat_btns = {}
        for key, label in CATS:
            b = QPushButton(label, checkable=True)
            b.setProperty("kind", "chip")
            b.clicked.connect(lambda _=False, k=key: self.set_cat(k))
            self.cat_btns[key] = b
            crow.addWidget(b)
        crow.addStretch(1)
        left.addLayout(crow)
        frow = QHBoxLayout()
        self.search = QLineEdit(placeholderText="Search your words…")
        self.search.textChanged.connect(self.refresh)
        frow.addWidget(self.search, 1)
        self.video_box = QComboBox()
        self.video_box.setMinimumWidth(190)
        self.video_box.setToolTip("Only the words from one video")
        self.video_box.currentIndexChanged.connect(self.refresh)
        frow.addWidget(self.video_box)
        self.cal_btn = ibtn("calendar", "Calendar: the days you saved words — click a day to see them", self.toggle_calendar,
                            checkable=True, kind="chip", size=15)
        frow.addWidget(self.cal_btn)
        self.exp_btn = ibtn("export", "Export these words (CSV for Excel, text, Anki)", self.export_menu, kind="chip", size=15)
        frow.addWidget(self.exp_btn)
        frow.addWidget(ibtn("plus", "A new word by hand (without a video)", self.new_word, kind="chip", size=15, text=" New word"))
        left.addLayout(frow)
        self.cal = QCalendarWidget()
        self.cal.setGridVisible(False)
        self.cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.cal.setMaximumHeight(250)
        self.cal.clicked.connect(self.pick_day)
        self.cal.currentPageChanged.connect(lambda *_: self._mark_calendar())
        self.cal.setStyleSheet(theme.recolor(
            "QCalendarWidget QWidget#qt_calendar_navigationbar{background:rgba(40,32,84,0.95);border-radius:8px}"
            "QCalendarWidget QToolButton{color:#FFFFFF;background:transparent;font-weight:700;padding:4px 10px}"
            "QCalendarWidget QToolButton:hover{background:rgba(255,255,255,0.08);border-radius:6px}"
            "QCalendarWidget QMenu{background:#1A1638;color:#E8E6FF}"
            "QCalendarWidget QSpinBox{background:#1A1638;color:#FFFFFF;border:0}"
            "QCalendarWidget QAbstractItemView{background:#110E26;color:#E8E6FF;selection-background-color:#8A5CFF;"
            "selection-color:#FFFFFF;outline:0;border:0}"
            "QCalendarWidget QAbstractItemView:disabled{color:#4A4670}"))
        from PySide6.QtGui import QTextCharFormat, QColor as _QC, QBrush as _QB
        wk = QTextCharFormat()
        wk.setForeground(_QB(_QC(theme.shade("#E8E6FF"))))
        for d in (Qt.Saturday, Qt.Sunday):
            self.cal.setWeekdayTextFormat(d, wk)
        hd = QTextCharFormat()
        hd.setForeground(_QB(_QC(theme.DIM)))
        self.cal.setHeaderTextFormat(hd)
        self.cal.hide()
        left.addWidget(self.cal)
        self.day_lbl = QLabel("", objectName="small")
        self.day_lbl.hide()
        left.addWidget(self.day_lbl)
        self.list = QListWidget()
        self.list.setIconSize(QSize(96, 54))
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.ElideRight)
        self.list.currentRowChanged.connect(self.show_word)
        left.addWidget(self.list, 1)
        row = QHBoxLayout()
        b1 = ibtn("cards", "Review the words that are due", lambda: main.show_page("review"), kind="", text="  Review due words", color="#FFFFFF")
        b1.setProperty("accent", True)
        theme.glow(b1, theme.MAGENTA, 28, 120)
        b2 = ibtn("puzzle", "Gap-fill, dictation, der·die·das", lambda: main.show_page("practice"), kind="", text="  Practice")
        row.addWidget(b1)
        row.addWidget(b2)
        left.addLayout(row)
        root.addWidget(lcard, 2)

        rcard = card()
        right = QVBoxLayout(rcard)
        right.setContentsMargins(20, 14, 16, 14)
        right.setSpacing(10)
        self.head_view = QLabel("", wordWrap=True)
        self.head_view.setTextFormat(Qt.RichText)
        self.head_view.setTextInteractionFlags(Qt.TextSelectableByMouse)
        right.addWidget(self.head_view)
        # four panels side by side: video · dictionary · sentences · collocations — click one to make it big
        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.p_video = Pane("Video", self.toggle_pane)
        self.snap = SnapLabel()
        self.snap.clicked.connect(self.play_here)
        self.p_video.body.addWidget(self.snap, 1)
        from PySide6.QtMultimediaWidgets import QVideoWidget
        self.vw = QVideoWidget()
        self.vw.setStyleSheet("background:#000")
        self.vw.hide()
        self.p_video.body.addWidget(self.vw, 1)
        self.vname = QLabel("", objectName="small", wordWrap=True)
        self.p_video.body.addWidget(self.vname)
        self.vmsg = QLabel("", objectName="hint", wordWrap=True)
        self.vmsg.hide()
        self.p_video.body.addWidget(self.vmsg)
        self.p_video.add_button(ibtn("play", "Play the moment here in the panel (click the picture too)", self.play_here, kind="chip", size=13))
        self.p_video.add_button(ibtn("film", "Open it in the player", self.play, kind="chip", size=13))
        self.p_dict = Pane("Dictionary", self.toggle_pane)
        self.v_dict = QTextBrowser(openLinks=False)
        self.v_dict.anchorClicked.connect(self._link)
        self.p_dict.body.addWidget(self.v_dict, 1)
        self.p_sent = Pane("Sentences", self.toggle_pane)
        self.v_sent = QTextBrowser(openLinks=False)
        self.v_sent.anchorClicked.connect(self._link)
        self.p_sent.body.addWidget(self.v_sent, 1)
        self.p_sent.add_button(ibtn("plus", "Add sentences (paste an AI answer)", self.add_sentences, kind="chip", size=13))
        self.p_coll = Pane("Collocations", self.toggle_pane)
        self.v_coll = QTextBrowser(openLinks=False)
        self.v_coll.anchorClicked.connect(self._link)
        self.p_coll.body.addWidget(self.v_coll, 1)
        self.p_coll.add_button(ibtn("plus", "Add collocations, meanings or sentences yourself", self.edit_word, kind="chip", size=13))
        self.p_coll.add_button(ibtn("study", "Ask the teacher (Ollama, ChatGPT, Gemini, DeepSeek, Grok) for collocations, sentences and TestDaF questions",
                                    self.teacher, kind="chip", size=13, text=" Teacher"))
        self.panes = [(self.p_video, 0, 0), (self.p_dict, 0, 1), (self.p_sent, 1, 0), (self.p_coll, 1, 1)]
        for p, r, c in self.panes:
            self.grid.addWidget(p, r, c)
        self.grid.setRowStretch(0, 1)
        self.grid.setRowStretch(1, 1)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        self.big = None
        right.addLayout(self.grid, 1)
        btns = QHBoxLayout()
        self.b_play = ibtn("play", "Play this moment in the video", self.play, kind="", text=" Play in video")
        self.b_speak = ibtn("volume", "Speak", self.speak, kind="", text=" Speak")
        self.b_learn = ibtn("sparkles", "Teacher, ChatGPT / Gemini / DeepSeek / Grok / dictionaries, add sentences", self.learn, kind="", text=" Learn more ▾")
        self.b_edit = ibtn("edit", "Edit the meaning, Persian, IPA — add collocations and sentences yourself", self.edit_word, kind="", text=" Edit")
        self.b_del = ibtn("trash", "Delete this word", self.delete, kind="", text=" Delete", color=theme.MAGENTA)
        for b in (self.b_play, self.b_speak, self.b_learn, self.b_edit, self.b_del):
            btns.addWidget(b)
        right.addLayout(btns)
        root.addWidget(rcard, 3)
        self.words = []
        self.set_cat("all", refresh=False)

    # ------------------------------------------------------------------ grouping
    def pos_of(self, w) -> str:
        if " " in w.text.strip():
            return "phrase"
        if w.id in self._pos:
            return self._pos[w.id]
        cat = "other"
        d = self.main.dictionary(w.lang)
        if d:
            try:
                es = [e for e in d.lookup(w.lemma or w.text) if e.pos != "name"]
                p = es[0].pos if es else ""
            except Exception:
                p = ""
            cat = {"noun": "noun", "verb": "verb", "adj": "adj", "adjective": "adj"}.get(p, "other")
            if cat == "other" and w.article in ("der", "die", "das"):
                cat = "noun"
        elif w.article in ("der", "die", "das"):
            cat = "noun"
        self._pos[w.id] = cat
        return cat

    def set_cat(self, k, refresh=True):
        self.cat = k
        for key, b in self.cat_btns.items():
            b.setChecked(key == k)
        if refresh:
            self.refresh()

    def toggle_calendar(self):
        on = self.cal_btn.isChecked()
        self.cal.setVisible(on)
        if not on:
            self.day = None
            self.day_lbl.hide()
            self.refresh()
        else:
            self._mark_calendar()

    def _day_of(self, ms: int):
        import datetime
        return datetime.date.fromtimestamp(ms / 1000) if ms else None

    def _mark_calendar(self):
        from PySide6.QtCore import QDate
        from PySide6.QtGui import QBrush, QColor, QTextCharFormat
        self.cal.setDateTextFormat(QDate(), QTextCharFormat())
        counts = {}
        for w in self.main.store.all():
            d = self._day_of(w.created)
            if d:
                counts[d] = counts.get(d, 0) + 1
        for d, n in counts.items():
            f = QTextCharFormat()
            f.setForeground(QBrush(QColor("#0B0A1A")))
            f.setBackground(QBrush(QColor(theme.CYAN if n < 5 else theme.MAGENTA)))
            f.setFontWeight(800)
            f.setToolTip(f"{n} word{'s' if n != 1 else ''} saved")
            self.cal.setDateTextFormat(QDate(d.year, d.month, d.day), f)

    def pick_day(self, qd):
        import datetime
        d = datetime.date(qd.year(), qd.month(), qd.day())
        self.day = None if self.day == d else d
        self.day_lbl.setVisible(self.day is not None)
        self.day_lbl.setText(f"Words saved on {self.day:%A, %d %B %Y} — click the day again to show all" if self.day else "")
        self.refresh()

    def _videos(self, words):
        names = []
        for w in words:
            if w.video_name and w.video_name not in names:
                names.append(w.video_name)
        return names

    def refresh(self, *_):
        q = self.search.text().strip().lower()
        all_words = self.main.store.all()
        # video filter (keep the choice)
        cur_v = self.video_box.currentData() if self.video_box.count() else None
        self.video_box.blockSignals(True)
        self.video_box.clear()
        self.video_box.addItem("All videos", None)
        for n in self._videos(all_words):
            self.video_box.addItem(n[:42] + ("…" if len(n) > 42 else ""), n)
        i = self.video_box.findData(cur_v) if cur_v else 0
        self.video_box.setCurrentIndex(max(0, i))
        self.video_box.blockSignals(False)
        vid = self.video_box.currentData()
        ws = [w for w in all_words if not q or q in w.text.lower() or q in w.lemma.lower() or q in w.english.lower()
              or q in w.persian]
        if vid:
            ws = [w for w in ws if w.video_name == vid]
        if self.day:
            ws = [w for w in ws if self._day_of(w.created) == self.day]
        counts = {k: 0 for k, _ in CATS}
        for w in ws:
            counts["all"] += 1
            counts[self.pos_of(w)] += 1
        for key, label in CATS:
            self.cat_btns[key].setText(f"{label} {counts[key]}")
        if self.cat != "all":
            ws = [w for w in ws if self.pos_of(w) == self.cat]
        ws.sort(key=lambda w: (-w.created, -w.id))          # always newest first (the day the word was saved)
        self.words = ws
        now = now_ms()
        due = sum(1 for w in all_words if w.due <= now)
        p = self.main.progress
        self.stats.setText(f"{len(all_words)} words  ·  {due} due  ·  🔥 {p.streak} day streak  ·  {p.today_count} today")
        cur = self.list.currentRow()
        self.list.clear()
        from PySide6.QtGui import QIcon, QPixmap
        missing = []
        for w in self.words:
            flag = "EN · " if w.lang == "en" else ""
            d = self._day_of(w.created)
            it = QListWidgetItem(f"{flag}{(w.article + ' ') if w.article else ''}{w.text}   —   {w.english[:56]}\n"
                                 f"{d:%d.%m.%Y} · reviewed {w.reviews}× · box {w.box}/7 · {due_label(w.due, now)}")
            snap = self.main.snap_path(w)
            if snap.exists():
                it.setIcon(QIcon(QPixmap(str(snap))))
            else:
                missing.append(w)
            self.list.addItem(it)
        for w in missing[:12]:                        # pictures for older words, a few at a time
            self.main.make_snapshot(w, done=lambda uid: self._snap_ready(uid))
        if self.words:
            self.list.setCurrentRow(min(max(cur, 0), len(self.words) - 1))
        else:
            self.detail.setHtml(f"<h2 style='color:{theme.CYAN}'>No words here</h2><p style='color:{theme.DIM}'>Click a word in the "
                                "subtitles, then ☆ Save. The word, its meaning, the sentence, a picture and the exact video moment "
                                "are kept.</p>")
        if self.cal.isVisible():
            self._mark_calendar()

    def _snap_ready(self, uid):
        from PySide6.QtGui import QIcon, QPixmap
        for r, w in enumerate(self.words):
            if w.uid == uid:
                snap = self.main.snap_path(w)
                it = self.list.item(r)
                if it and snap.exists():
                    it.setIcon(QIcon(QPixmap(str(snap))))
                if r == self.list.currentRow():
                    self.show_word()

    # ------------------------------------------------------------------ export
    def export_menu(self):
        m = QMenu(self)
        n = len(self.words)
        m.addAction(f"CSV for Excel ({n} words)…", lambda: self.export("csv"))
        m.addAction(f"Text list ({n} words)…", lambda: self.export("txt"))
        m.addAction(f"Anki import file ({n} words)…", lambda: self.export("anki"))
        m.exec(self.exp_btn.mapToGlobal(self.exp_btn.rect().bottomLeft()))

    def export(self, kind):
        import csv
        import io
        from PySide6.QtWidgets import QFileDialog
        ext = {"csv": "csv", "txt": "txt", "anki": "txt"}[kind]
        default = str(Path.home() / "Documents" / f"SubPlayer words.{ext}")
        f, _ = QFileDialog.getSaveFileName(self, "Export words", default, f"*.{ext}")
        if not f:
            return
        rows = []
        for w in self.words:
            ex = self.main.store.examples(w.id)
            rows.append(dict(word=w.text, article=w.article, base=w.lemma, english=w.english, persian=w.persian, ipa=w.ipa,
                             sentence=w.sentence, video=w.video_name,
                             time=f"{max(0, w.start_ms) // 60000}:{max(0, w.start_ms) // 1000 % 60:02d}" if w.start_ms >= 0 else "",
                             saved=f"{self._day_of(w.created):%Y-%m-%d}", category=dict(CATS)[self.pos_of(w)],
                             level=self._level_name(w), reviews=w.reviews, box=w.box,
                             examples=" | ".join(e.de + (f" = {e.en}" if e.en else "") for e in ex)))
        if kind == "csv":
            buf = io.StringIO()
            wr = csv.DictWriter(buf, fieldnames=list(rows[0]) if rows else ["word"], delimiter=";")
            wr.writeheader()
            wr.writerows(rows)
            Path(f).write_text("\ufeff" + buf.getvalue(), encoding="utf-8")       # BOM: Excel opens umlauts and Persian right
        elif kind == "txt":
            out = []
            for r in rows:
                out.append(f"{(r['article'] + ' ') if r['article'] else ''}{r['word']} — {r['english']}"
                           + (f" — {r['persian']}" if r['persian'] else ""))
                if r["sentence"]:
                    out.append(f"    „{r['sentence']}“ ({r['video']} {r['time']})")
            Path(f).write_text("\n".join(out) + "\n", encoding="utf-8")
        else:
            out = ["#separator:tab", "#html:true", "#columns:Front\tBack\tTags"]
            for r in rows:
                front = f"{(r['article'] + ' ') if r['article'] else ''}{r['word']}" + (f"<br><i>{html.escape(r['sentence'])}</i>"
                                                                                       if r["sentence"] else "")
                back = html.escape(r["english"]) + (f"<br>{html.escape(r['persian'])}" if r["persian"] else "")
                if r["examples"]:
                    back += "<br><small>" + html.escape(r["examples"]) + "</small>"
                out.append(f"{front}\t{back}\tSubPlayer {r['category']} {r['level']}".replace("\n", " "))
            Path(f).write_text("\n".join(out) + "\n", encoding="utf-8")
        self.main.msg(f"{len(rows)} words exported to {f}", 9000)

    def _level_name(self, w) -> str:
        from .levels import NAMES
        lv = self.main.levels.level(w.lemma or w.text, w.lang, self.main.dictionary(w.lang)) if " " not in w.text else 0
        return NAMES[lv]

    def current(self):
        r = self.list.currentRow()
        return self.words[r] if 0 <= r < len(self.words) else None

    # ------------------------------------------------------------------ the four panels
    def toggle_pane(self, pane):
        if self.big is pane:
            self.big = None
            for p, r, c in self.panes:
                self.grid.addWidget(p, r, c)
                p.setVisible(True)
                p.set_big(False)
        else:
            self.big = pane
            for p, _, _ in self.panes:
                p.setVisible(p is pane)
                p.set_big(p is pane)
            self.grid.addWidget(pane, 0, 0, 2, 2)

    def show_word(self, *_):
        w = self.current()
        self.stop_video()
        if not w:
            return
        lvn = self._level_name(w)
        cat = dict(CATS)[self.pos_of(w)]
        acc = f"{w.correct * 100 // w.reviews}%" if w.reviews else "–"
        h = [f"<span style='font-size:22pt;font-weight:800'>{article_html(w)}{html.escape(w.text)}</span>"]
        if w.ipa:
            h.append(f"&nbsp;&nbsp;<span style='color:{theme.GOLD};font-size:12pt'>{html.escape(w.ipa)}</span>")
        h.append(f"<br><span style='color:{theme.DIM}'>{cat[:-1] if cat.endswith('s') and cat != 'Others' else cat}"
                 + (f" · <b>{'≈' if w.lang == 'de' else ''}{lvn}</b>" if lvn else "")
                 + (f" · → {html.escape(w.lemma)}" if w.lemma and w.lemma.lower() != w.text.lower() else "")
                 + f" · saved {self._day_of(w.created):%d.%m.%Y} · reviewed {w.reviews}× · right {acc} · next "
                   f"{due_label(w.due, now_ms())}</span>")
        if w.english:
            h.append(f"<br>{html.escape(w.english)}")
        if w.persian:
            h.append(f"<br><span style='font-family:Vazirmatn;font-size:13pt'>{html.escape(w.persian)}</span>")
        self.head_view.setText("".join(h))
        # video
        snap = self.main.snap_path(w)
        self.snap.set_file(snap if snap.exists() else None,
                           f"<span style='color:{theme.DIM}'>" + (f"▶ {html.escape(w.video_name)}" if w.video_name else "No video moment")
                           + "</span>")
        when = f" · {max(0, w.start_ms) // 60000}:{max(0, w.start_ms) // 1000 % 60:02d}" if w.start_ms >= 0 and w.video_name else ""
        self.vname.setText(f"{w.video_name}{when}" if w.video_name else "")
        self.v_dict.setHtml(dictionary_html(self.main, w))
        self.fill_sentences(w)
        self.fill_collocations(w)

    def fill_sentences(self, w):
        h = ["<div style='font-size:10.5pt;line-height:140%'>"]
        exs = self.main.store.examples(w.id)
        if w.sentence:
            h.append(f"<p><a href='play:' style='color:{theme.MAGENTA};text-decoration:none'>▶ video</a>&nbsp; "
                     f"{highlight(w.sentence, w.text)}</p>")
        for e in exs:
            h.append(f"<p style='margin-bottom:0'>{highlight(e.de, w.text)} "
                     f"<a href='say:{e.id}' style='color:{theme.CYAN};text-decoration:none'>🔊</a> "
                     f"<a href='del:{e.id}' style='color:{theme.DIM};text-decoration:none'>✕</a></p>")
            if e.en:
                h.append(f"<p style='color:{theme.DIM};margin:0'>{html.escape(e.en)}</p>")
            if e.fa:
                h.append(f"<p dir='rtl' style='font-family:Vazirmatn;color:{theme.DIM};margin:0 0 6px 0'>{html.escape(e.fa)}</p>")
        if not exs:
            h.append(f"<p style='color:{theme.DIM}'>No added sentences yet — Teacher ▸ ＋ Add sentences &amp; collocations, or ＋ "
                     "to paste an answer from ChatGPT / Gemini.</p>")
        h.append("</div>")
        self.v_sent.setHtml("".join(h))
        self.p_sent.count.setText(f"· {len(exs) + (1 if w.sentence else 0)}")

    def fill_collocations(self, w):
        cols = self.main.store.collocations(w.lang, w.lemma or w.text)
        if not cols and (w.lemma or w.text).lower() != w.text.lower():
            cols = self.main.store.collocations(w.lang, w.text)
        qs = self.main.store.questions(lang=w.lang, lemma=w.lemma or w.text)
        e_ = html.escape
        h = ["<div style='font-size:10.5pt;line-height:140%'><table cellspacing=0 cellpadding=3 width='100%'>"]
        for c in cols:
            h.append(f"<tr><td style='color:{theme.GOLD};font-weight:600;padding-right:10px'>{e_(c['phrase'])}</td>"
                     f"<td>{e_(c['meaning'])} <a href='delc:{c['id']}' style='color:{theme.DIM};text-decoration:none'>✕</a></td></tr>")
            if c["example"]:
                h.append(f"<tr><td></td><td style='color:{theme.DIM};font-style:italic'>{e_(c['example'])} "
                         f"<a href='sayt:{_q(c['example'])}' style='color:{theme.CYAN};text-decoration:none'>🔊</a></td></tr>")
        h.append("</table>")
        if not cols:
            h.append(f"<p style='color:{theme.DIM}'>No collocations yet. <a href='teach:' style='color:{theme.CYAN}'>Ask the "
                     "teacher</a> (Ollama, ChatGPT, Gemini, DeepSeek or Grok), or <a href='edit:' style='color:{theme.CYAN}'>write "
                     "them yourself</a>.</p>")
        if qs:
            h.append(f"<p style='color:{theme.DIM};margin-top:10px'>📝 {len(qs)} exam question(s) on this word are in Review.</p>")
        h.append("</div>")
        self.v_coll.setHtml("".join(h))
        self.p_coll.count.setText(f"· {len(cols)}" if cols else "")

    def _link(self, url):
        kind, _, val = url.toString().partition(":")
        w = self.current()
        if not w:
            return
        if kind == "play":
            return self.play_here()
        if kind == "teach":
            return self.teacher()
        if kind == "edit":
            return self.edit_word()
        if kind == "sayt":
            import urllib.parse
            return self.main.speak(urllib.parse.unquote(val), lang=w.lang)
        if kind == "delc":
            self.main.store.delete_collocation(int(val))
            return self.fill_collocations(w)
        ex = next((e for e in self.main.store.examples(w.id) if str(e.id) == val), None)
        if ex and kind == "say":
            self.main.speak(ex.de, lang=w.lang)
        elif ex and kind == "del":
            self.main.store.delete_example(ex.id)
            self.main.after_change()
            self.fill_sentences(w)

    def refresh_panels(self):
        """After a change elsewhere (the teacher added sentences or collocations): the panels of the shown word again."""
        w = self.current()
        if w:
            self.fill_sentences(w)
            self.fill_collocations(w)

    def play_here(self):
        """The video moment plays inside the Video panel (the picture comes back to the player afterwards)."""
        w = self.current()
        if not w:
            return
        if self.vw.isVisible():
            return self.stop_video()
        if not self.main.find_video(w):
            self.vmsg.setText(f"The video “{w.video_name}” isn't on this PC (or was renamed) — put it in Videos, Downloads or a "
                              "folder you opened before.")
            self.vmsg.show()
            return
        self.main.hide_mini()
        self.main.player.setVideoOutput(self.vw)
        self.snap.hide()
        self.vw.show()
        self.main.play_clip(w, quiet=True)

    def stop_video(self):
        self.vmsg.hide()
        if self.vw.isVisible():
            self.main.player.pause()
            self.main.clear_ab()
            self.vw.hide()
            self.snap.show()
            self.main.player.setVideoOutput(self.main.vw)

    def add_sentences(self):
        w = self.current()
        if w:
            from .dialogs import AddSentencesDialog
            AddSentencesDialog(self.main, w).exec()
            self.show_word()

    def edit_word(self):
        w = self.current()
        if w:
            from .dialogs import WordEditDialog
            if WordEditDialog(self.main, self.main, w).exec():
                self.refresh()

    def new_word(self):
        from .dialogs import WordEditDialog
        if WordEditDialog(self.main, self.main, None).exec():
            self.refresh()
            self.list.setCurrentRow(0)

    def teacher(self):
        w = self.current()
        if w:
            self.main.teacher_for(w.text, w.lemma or w.text, w.sentence, w.lang, lambda: w, 0)

    def play(self):
        w = self.current()
        if w and self.main.play_clip(w):
            self.main.show_page("player")

    def speak(self):
        w = self.current()
        if w:
            self.main.speak(w.text if " " in w.text else (w.lemma or w.text), lang=w.lang)

    def learn(self):
        w = self.current()
        if not w:
            return
        m = QMenu(self)
        self.main.fill_learn_menu(m, w.lemma or w.text, w.sentence, w.lang, saved_getter=lambda: w)
        m.exec(self.b_learn.mapToGlobal(self.b_learn.rect().bottomLeft()))
        self.show_word()

    def delete(self):
        w = self.current()
        if w:
            self.main.store.delete(w.id)
            self.main.after_change()
            self.refresh()


# ==================================================================== Review
class ReviewPage(QWidget):
    def __init__(self, main):
        super().__init__(objectName="page")
        self.main = main
        v = QVBoxLayout(self)
        t = GradientLabel("Review", 22, QFont.Black)
        v.addWidget(t)
        v.addStretch(1)
        self.head = QLabel("", objectName="hint", alignment=Qt.AlignCenter)
        v.addWidget(self.head)
        self.box = card()
        theme.glow(self.box, theme.VIOLET, 60, 120)
        bv = QVBoxLayout(self.box)
        bv.setContentsMargins(26, 22, 26, 20)
        self.view = QTextBrowser(openLinks=False)
        self.view.setMinimumHeight(340)
        bv.addWidget(self.view)
        from PySide6.QtMultimediaWidgets import QVideoWidget
        self.vw = QVideoWidget()                 # the moment plays right here, inside the card
        self.vw.setMinimumHeight(260)
        self.vw.setStyleSheet("background:#000")
        self.vw.hide()
        bv.addWidget(self.vw)
        self.vmsg = QLabel("", objectName="hint", alignment=Qt.AlignCenter, wordWrap=True)
        self.vmsg.hide()
        bv.addWidget(self.vmsg)
        self.opt_row = QVBoxLayout()                 # the choices of an exam question
        self.opt_row.setSpacing(5)
        bv.addLayout(self.opt_row)
        row = QHBoxLayout()
        self.b_play = ibtn("play", "Play the video moment (here in the card)", self.play, kind="", text=" Play the moment")
        self.b_speak = ibtn("volume", "Speak the sentence", self._speak, kind="", text=" Speak")
        self.b_reveal = ibtn("sparkles", "Show the meaning (Space)", self.reveal, kind="", text=" Show meaning", color="#FFFFFF")
        self.b_reveal.setProperty("accent", True)
        self.b_again = ibtn("repeat", "Again in 10 minutes (1 / ←)", lambda: self.answer(False), kind="", text=" Again — 10 min")
        self.b_got = ibtn("check", "Got it (2 / → / Space)", None, kind="", text=" Got it", color="#FFFFFF")
        self.b_got.setProperty("accent", True)
        self.b_got.clicked.connect(lambda: self.answer(True))
        for b in (self.b_play, self.b_speak, self.b_reveal, self.b_again, self.b_got):
            row.addWidget(b)
        bv.addLayout(row)
        wrap = QHBoxLayout()
        wrap.addStretch(1)
        wrap.addWidget(self.box, 4)
        wrap.addStretch(1)
        v.addLayout(wrap)
        v.addStretch(2)
        self.queue, self.i, self.done, self.got, self.revealed, self.cur, self.sent = [], 0, 0, 0, False, None, None

    def start(self):
        now = now_ms()
        items = self.main.store.due(now) + self.main.store.due_questions(now)
        items.sort(key=lambda x: (x.reviews, x.box, x.due))      # the least reviewed first
        self.queue = items
        self.i = self.done = self.got = 0
        self.show_card()

    def _speak(self):
        if not self.cur:
            return
        if isinstance(self.cur, Question):
            self.main.speak(self.cur.question, lang=self.cur.lang)
        else:
            self.main.speak(self.sent[0] if self.sent else self.cur.text, lang=self.cur.lang)

    def _clear_opts(self):
        while self.opt_row.count():
            it = self.opt_row.takeAt(0)
            if it.widget():
                it.widget().hide()
                it.widget().deleteLater()

    @staticmethod
    def is_answer(opt: str, ans: str) -> bool:
        """An option is the answer when it is the same text, or the same letter (A / B) / the answer is inside it."""
        import re as _re
        o, a = " ".join(opt.lower().split()), " ".join(ans.lower().split())
        if not a:
            return False
        if o == a:
            return True
        lo, la = _re.match(r"^\(?([a-f])[).:]", o), _re.match(r"^\(?([a-f])(?:[).:]|$)", a)
        if lo and la:
            return lo.group(1) == la.group(1)
        strip = lambda t: _re.sub(r"^\(?[a-f][).:]\s*", "", t).strip(" .")
        return strip(o) == strip(a) or (len(strip(a)) > 3 and strip(a) in strip(o))

    def show_card(self):
        self.stop_video()
        self._clear_opts()
        self.revealed = False
        self.picked = None
        self.cur = self.queue[self.i] if self.i < len(self.queue) else None
        if isinstance(self.cur, Question):
            return self.show_question()
        if not self.cur:
            self.head.setText("")
            msg = f"Done ✓ — {self.got} of {self.done} right. 🔥 {self.main.progress.streak} day streak" if self.done else \
                "Nothing is due right now. Save words from the subtitles, and they come back here at the right time."
            self.view.setHtml(f"<h1 style='text-align:center;color:{theme.CYAN}'>{'Well done!' if self.done else 'All caught up'}</h1>"
                              f"<p style='text-align:center;color:{theme.DIM}'>{msg}</p>")
            for b in (self.b_play, self.b_speak, self.b_reveal, self.b_again, self.b_got):
                b.setVisible(False)
            return
        w = self.cur
        opts = sentences_of(self.main, w)
        self.sent = opts[w.reviews % len(opts)] if opts else None     # a different sentence each time
        self.head.setText(f"{self.i + 1} of {len(self.queue)} · reviewed {w.reviews}× · box {w.box}/7")
        for b, vis in ((self.b_play, w.start_ms >= 0 and bool(w.video_name) and self.sent and self.sent[0] == w.sentence),
                       (self.b_speak, True), (self.b_reveal, True), (self.b_again, False), (self.b_got, False)):
            b.setVisible(bool(vis))
        self.render()

    def show_question(self):
        q = self.cur
        self.sent = None
        exam = "IELTS" if q.lang == "en" else "TestDaF"
        self.head.setText(f"{self.i + 1} of {len(self.queue)} · {exam} question · reviewed {q.reviews}× · box {q.box}/7")
        for b, vis in ((self.b_play, False), (self.b_speak, True), (self.b_reveal, not q.options), (self.b_again, False), (self.b_got, False)):
            b.setVisible(vis)
        for o in q.options:
            b = QPushButton(o)
            b.setStyleSheet("text-align:left;padding:8px 14px")
            b.clicked.connect(lambda _=False, x=o: self.pick(x))
            self.opt_row.addWidget(b)
        self.render()

    def pick(self, opt: str):
        if self.revealed:
            return
        self.picked = opt
        ok = self.is_answer(opt, self.cur.answer)
        for k in range(self.opt_row.count()):
            b = self.opt_row.itemAt(k).widget()
            if b:
                b.setEnabled(False)
                right = self.is_answer(b.text(), self.cur.answer)
                if right or b.text() == opt:
                    b.setStyleSheet(f"text-align:left;padding:8px 14px;color:#FFFFFF;background:{'#2E8B57' if right else '#8B2E4F'}")
        self.reveal()
        (self.b_got if ok else self.b_again).setFocus()

    def render(self):
        w = self.cur
        h = []
        if isinstance(w, Question):
            src = (f" · from “{html.escape(w.video_name[:50])}”" if w.video_name else "") + (f" · word „{html.escape(w.lemma)}“" if w.lemma else "")
            h.append(f"<p style='text-align:center;color:{theme.DIM};font-size:9pt'>{src.lstrip(' ·')}</p>")
            h.append(f"<p style='text-align:center;font-size:15pt'>{html.escape(w.question)}</p>")
            if self.revealed:
                ok = self.picked is None or self.is_answer(self.picked, w.answer)
                mark = "" if self.picked is None else ("✓ Right! " if ok else "✗ ")
                h.append(f"<p style='text-align:center;font-size:15pt;color:{theme.MINT if ok else theme.MAGENTA}'>{mark}"
                         f"<b>{html.escape(w.answer)}</b></p>")
                if w.explanation:
                    h.append(f"<p style='text-align:center;color:{theme.DIM}'>{html.escape(w.explanation)}</p>")
            self.view.setHtml("".join(h))
            return
        if self.sent:
            h.append(f"<p style='text-align:center;font-size:17pt'>{highlight(self.sent[0], w.text)}</p>")
        h.append(f"<p style='text-align:center;font-size:26pt;font-weight:800;color:{theme.GOLD}'>"
                 f"{article_html(w) if self.revealed else ''}{html.escape(w.text)}</p>")
        if self.revealed:
            if w.ipa:
                h.append(f"<p style='text-align:center;color:{theme.GOLD};font-size:12.5pt'>{html.escape(w.ipa)}</p>")
            if w.english:
                h.append(f"<p style='text-align:center'>{html.escape(w.english)}</p>")
            if w.persian:
                h.append(f"<p dir='rtl' style='font-family:Vazirmatn;text-align:center;font-size:15pt'>{html.escape(w.persian)}</p>")
            if self.sent and (self.sent[1] or self.sent[2]):
                h.append(f"<p style='text-align:center;color:{theme.DIM}'>{html.escape(self.sent[1])}</p>"
                         f"<p dir='rtl' style='font-family:Vazirmatn;text-align:center;color:{theme.DIM}'>{html.escape(self.sent[2])}</p>")
        self.view.setHtml("".join(h))

    def keyPressEvent(self, e):
        if isinstance(self.cur, Question) and self.cur.options and not self.revealed and Qt.Key_1 <= e.key() <= Qt.Key_9:
            k = e.key() - Qt.Key_1
            if k < len(self.cur.options):
                return self.pick(self.cur.options[k])
        if e.key() == Qt.Key_Space and self.cur and isinstance(self.cur, Question) and self.cur.options and not self.revealed:
            return
        if e.key() == Qt.Key_Space and self.cur:
            self.reveal() if not self.revealed else self.answer(True)
        elif e.key() in (Qt.Key_1, Qt.Key_Left) and self.revealed:
            self.answer(False)
        elif e.key() in (Qt.Key_2, Qt.Key_Right) and self.revealed:
            self.answer(True)
        else:
            super().keyPressEvent(e)

    def play(self):
        if not self.cur:
            return
        path = self.main.find_video(self.cur)
        if not path:
            self.vmsg.setText(f"The video “{self.cur.video_name}” isn't on this PC (or was renamed). Put it in Videos, "
                              "Downloads or a folder you opened before — SubPlayer finds it by its file name.")
            self.vmsg.show()
            return
        self.vmsg.hide()
        self.main.hide_mini()
        self.main.player.setVideoOutput(self.vw)
        self.view.setMinimumHeight(120)
        self.view.setMaximumHeight(170)
        self.vw.show()
        self.main.play_clip(self.cur, quiet=True)

    def stop_video(self):
        """Gives the picture back to the player page."""
        if self.vw.isVisible():
            self.main.player.pause()
            self.main.clear_ab()
            self.vw.hide()
            self.view.setMaximumHeight(16777215)
            self.view.setMinimumHeight(340)
            self.main.player.setVideoOutput(self.main.vw)
        self.vmsg.hide()

    def reveal(self):
        self.revealed = True
        self.b_reveal.setVisible(False)
        self.b_again.setVisible(True)
        self.b_got.setVisible(True)
        self.render()

    def answer(self, got):
        w = self.cur
        if not w:
            return
        upd = review(w, got, now_ms())
        if isinstance(w, Question):
            self.main.store.update_question(upd)
        else:
            self.main.store.update(upd)
        self.main.progress.record()
        self.done += 1
        self.got += 1 if got else 0
        if not got:
            self.queue.append(upd)        # back at the end of this session
        self.i += 1
        self.main.after_change()
        self.show_card()


# ==================================================================== Practice
class PracticePage(QWidget):
    N = 10

    def __init__(self, main):
        super().__init__(objectName="page")
        self.main = main
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(GradientLabel("Practice", 22, QFont.Black))
        top.addStretch(1)
        self.modes = {}
        for key, label in (("gap", "Fill the gap"), ("dictation", "Dictation"), ("article", "der · die · das")):
            b = QPushButton(label, checkable=True)
            b.setProperty("kind", "chip")
            b.setMinimumWidth(130)
            b.clicked.connect(lambda _=False, k=key: self.start(k))
            self.modes[key] = b
            top.addWidget(b)
        v.addLayout(top)
        self.head = QLabel("", objectName="hint")
        v.addWidget(self.head)
        self.box = card()
        theme.glow(self.box, theme.VIOLET, 50, 100)
        bv = QVBoxLayout(self.box)
        bv.setContentsMargins(26, 22, 26, 20)
        self.view = QTextBrowser(openLinks=False)
        self.view.setMinimumHeight(260)
        bv.addWidget(self.view)
        self.choice_row = QHBoxLayout()
        bv.addLayout(self.choice_row)
        self.input = QLineEdit(placeholderText="Type your answer and press Enter")
        self.input.returnPressed.connect(self.check_typed)
        bv.addWidget(self.input)
        row = QHBoxLayout()
        self.b_play = ibtn("volume", "Listen", self.listen, kind="", text=" Listen")
        self.b_hint = ibtn("sparkles", "A hint", self.hint, kind="", text=" Hint")
        self.b_next = QPushButton("Next →")
        self.b_next.setProperty("accent", True)
        self.b_next.clicked.connect(self.next)
        for b in (self.b_play, self.b_hint, self.b_next):
            row.addWidget(b)
        bv.addLayout(row)
        self.view.setMaximumHeight(360)
        v.addStretch(1)
        wrap = QHBoxLayout()
        wrap.addStretch(1)
        wrap.addWidget(self.box, 5)
        wrap.addStretch(1)
        v.addLayout(wrap)
        v.addStretch(2)
        self.mode, self.qs, self.k, self.score, self.answered, self.show_hint = "gap", [], 0, 0, False, False
        self.rnd = random.Random()

    def start(self, mode=None):
        self.source = ""
        self.mode = mode or self.mode
        for k, b in self.modes.items():
            b.setChecked(k == self.mode)
        words = sorted(self.main.store.all(), key=lambda w: (w.box, w.due))
        self.qs = []
        if self.mode == "gap":
            pool = [w.text for w in words]
            for w in words:
                opts = sentences_of(self.main, w)
                self.rnd.shuffle(opts)
                for s, en, fa in opts:
                    c = practice.cloze(w, s, en, fa)
                    if c:
                        self.qs.append((w, c, practice.choices(c.answer, pool, self.rnd)))
                        break
                if len(self.qs) >= self.N:
                    break
        elif self.mode == "dictation":
            self.qs = [(w, None, []) for w in words if w.start_ms >= 0 and w.sentence and w.video_name][:self.N]
        else:
            self.qs = [(w, None, ["der", "die", "das"]) for w in words if w.lang == "de" and w.article in ("der", "die", "das")][:self.N]
        self.k = self.score = 0
        self.show_q()

    def start_text(self, cues, video: str, name: str, lang: str, mode: str, min_level: int = 3):
        """Questions from every line of a video (not only saved words): gaps at words of min_level or harder, dictation of
        its lines."""
        from . import library
        self.mode = mode
        for k, b in self.modes.items():
            b.setChecked(k == mode)
        d = self.main.dictionary(lang)
        lines = [c for c in cues if len(c.text.split()) >= 4]
        self.rnd.shuffle(lines)
        self.qs = []
        if mode == "gap":
            picks = []
            for c in lines:
                toks = [m.group(0) for m in library.TOKEN.finditer(c.text) if len(m.group(0)) >= 3]
                scored = [(self.main.levels.level(t, lang, d), t) for t in toks]
                good = [x for x in scored if x[0] >= min_level] or [x for x in scored if x[0] >= max(1, min_level - 1)]
                if not good:
                    continue
                lv, tok = max(good, key=lambda x: (x[0], len(x[1])))
                e = (d.lookup(tok) or [None])[0] if d else None
                hint = (", ".join(e.english[:2]) if e and e.lang != "en" else (e.senses[0].de[:70] if e and e.senses else "")) if e else ""
                w = SavedWord(text=tok, lemma=tok, sentence=c.text, video_uri=video, video_name=name, start_ms=c.start_ms,
                              end_ms=c.end_ms, english=hint, lang=lang)
                cz = practice.cloze(w, c.text)
                if cz:
                    picks.append((w, cz, lv))
                if len(picks) >= self.N:
                    break
            pool = [w.text for w, _, _ in picks] + [t for t, _, lv in library.vocabulary(cues, lang, self.main.levels, d)[:300]
                                                    if lv >= min_level - 1]
            for w, cz, lv in picks:
                self.qs.append((w, cz, practice.choices(cz.answer, pool, self.rnd)))
        else:
            for c in lines[:self.N]:
                self.qs.append((SavedWord(text=c.text.split()[0], lemma="", sentence=c.text, video_uri=video, video_name=name,
                                          start_ms=c.start_ms, end_ms=c.end_ms, lang=lang), None, []))
        self.k = self.score = 0
        self.source = f"from “{name[:40]}”"
        self.show_q()

    def _clear_choices(self):
        while self.choice_row.count():
            it = self.choice_row.takeAt(0)
            w = it.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def show_q(self):
        self._clear_choices()
        self.answered = self.show_hint = False
        self.input.clear()
        if self.k >= len(self.qs):
            empty = not self.qs
            msg = ("This video has no lines with words at that level — choose a lower level on the Study page."
                   if getattr(self, "source", "") else None) or {"gap": "Save words (and add sentences) to practise them here.",
                   "dictation": "Save words from a video to practise dictation.",
                   "article": "Save some German nouns to practise der · die · das."}[self.mode] if empty else \
                f"{self.score} of {len(self.qs)} right · 🔥 {self.main.progress.streak} day streak"
            self.view.setHtml(f"<h1 style='text-align:center;color:{theme.CYAN}'>{'Nothing to practise yet' if empty else 'Finished!'}</h1>"
                              f"<p style='text-align:center;color:{theme.DIM}'>{msg}</p>")
            self.head.setText("")
            for wdg in (self.input, self.b_play, self.b_hint, self.b_next):
                wdg.setVisible(False)
            return
        w, c, ch = self.qs[self.k]
        self.head.setText(f"Question {self.k + 1} of {len(self.qs)} · score {self.score}" +
                          (f" · {self.source}" if getattr(self, "source", "") else ""))
        self.b_next.setVisible(False)
        self.b_play.setVisible(self.mode in ("dictation",) or self.mode == "gap")
        self.b_hint.setVisible(self.mode == "gap")
        self.input.setVisible(not ch or self.mode == "dictation")
        for opt in ch:
            b = QPushButton(opt)
            b.clicked.connect(lambda _=False, o=opt: self.check(o))
            self.choice_row.addWidget(b)
        self.render()
        if self.mode == "dictation":
            self.listen()
        self.input.setFocus()

    def render(self, feedback: str = ""):
        w, c, ch = self.qs[self.k]
        if self.mode == "gap":
            blank = c.answer if self.answered else "_" * max(4, len(c.answer))
            col = theme.GOLD if self.answered else theme.CYAN
            h = (f"<p style='text-align:center;font-size:18pt'>{html.escape(c.before)}<span style='color:{col};font-weight:700'>"
                 f"{html.escape(blank)}</span>{html.escape(c.after)}</p>")
            if self.show_hint and not self.answered:
                h += f"<p style='text-align:center;color:{theme.GOLD}'>Starts with „{html.escape(c.answer[:2])}…“ · {len(c.answer)} letters</p>"
            if self.answered:
                h += (f"<p style='text-align:center;color:{theme.DIM}'>{html.escape(c.en)}</p>"
                      f"<p dir='rtl' style='font-family:Vazirmatn;text-align:center;color:{theme.DIM}'>{html.escape(c.fa)}</p>")
            elif w.english:
                h += f"<p style='text-align:center;color:{theme.DIM}'>({html.escape(w.english[:80])})</p>"
        elif self.mode == "dictation":
            h = f"<p style='text-align:center;font-size:15pt;color:{theme.DIM}'>Listen and type the sentence.</p>"
        else:
            art = f"<span style='color:{theme.ARTICLE[w.article]}'>{w.article}</span>" if self.answered else "___"
            h = f"<p style='text-align:center;font-size:30pt;font-weight:800'>{art} {html.escape(w.lemma)}</p>"
            if w.english:
                h += f"<p style='text-align:center;color:{theme.DIM}'>{html.escape(w.english)}</p>"
        self.view.setHtml(h + feedback)

    def check(self, given):
        if self.answered:
            return
        w, c, ch = self.qs[self.k]
        right = (c.answer if self.mode == "gap" else w.article)
        self._finish(practice.same(given, right), f"The answer: {right}")

    def check_typed(self):
        if self.answered or self.k >= len(self.qs):
            return self.next() if self.answered else None
        w, c, ch = self.qs[self.k]
        t = self.input.text()
        if self.mode == "dictation":
            marks, score = practice.dictation(w.sentence, t)
            words = " ".join(f"<span style='color:{theme.GOLD if ok else theme.MAGENTA}'>{html.escape(x)}</span>" for x, ok in marks)
            self.answered = True
            ok = score >= 80
            self._finish(ok, "", extra=f"<p style='text-align:center;font-size:15pt'>{words}</p><p style='text-align:center'>{score}% of the words</p>")
        else:
            self.check(t)

    def _finish(self, ok, right_text, extra=""):
        self.answered = True
        w = self.qs[self.k][0]
        self.score += 1 if ok else 0
        self.main.progress.record()
        self.main.after_change()
        fb = (f"<p style='text-align:center;font-size:16pt;color:{'#5BE38F' if ok else theme.MAGENTA}'>"
              f"{'✓ Right!' if ok else '✗ ' + html.escape(right_text)}</p>") + extra
        self.render(fb)
        for i in range(self.choice_row.count()):
            b = self.choice_row.itemAt(i).widget()
            if b:
                b.setEnabled(False)
        self.b_next.setVisible(True)
        self.b_next.setFocus()
        if self.mode == "article":
            self.main.speak(f"{w.article} {w.lemma}", lang="de")

    def hint(self):
        self.show_hint = True
        self.render()

    def listen(self):
        w, c, ch = self.qs[self.k]
        if self.mode == "dictation":
            if not self.main.play_clip(w, quiet=True):
                self.main.speak(w.sentence, lang=w.lang)
        elif c:
            self.main.speak(c.sentence, lang=w.lang)

    def next(self):
        self.main.player.pause()
        self.main.clear_ab()
        self.k += 1
        self.show_q()
