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


def passage_html(text: str) -> str:
    """The text an exam question is about, in a box above the question (Review and Practice)."""
    if not (text or "").strip():
        return ""
    paras = [p.strip() for p in text.replace("\r", "").split("\n") if p.strip()]
    body = "".join(f"<p style='margin:0 0 6px 0'>{html.escape(p)}</p>" for p in paras)
    return (f"<table width='100%' cellspacing=0 cellpadding=10 style='margin-bottom:8px'><tr><td style='background:#16133A;"
            f"border-left:3px solid {theme.CYAN};font-size:11pt;line-height:145%'>"
            f"<p style='color:{theme.CYAN};font-size:8.5pt;font-weight:700;letter-spacing:1px;margin:0 0 6px 0'>📖 TEXT</p>"
            f"{body}</td></tr></table>")


def _contains_word(sentence: str, w) -> bool:
    """The word itself (or its base form / a form starting like it) is in the sentence."""
    t = sentence.lower()
    base = (w.lemma or w.text).lower()
    return w.text.lower() in t or base in t or (len(base) >= 5 and base[:max(4, len(base) - 3)] in t)


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
    """The picture of the video moment, drawn to fit the panel (click = play it here). It is painted, not set as the label's
    pixmap, so a new size never asks the layout for another size (that loop could freeze the window)."""
    clicked = Signal()

    def __init__(self):
        super().__init__(alignment=Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setMinimumSize(10, 10)
        self.setCursor(Qt.PointingHandCursor)
        self._pm = None

    def set_file(self, path, text=""):
        from PySide6.QtGui import QPixmap
        pm = QPixmap(str(path)) if path else None
        self._pm = pm if pm is not None and not pm.isNull() else None
        self.setText("" if self._pm else text)
        self.update()

    def paintEvent(self, e):
        if not self._pm:
            return super().paintEvent(e)
        from PySide6.QtGui import QPainter
        r = self.rect()
        pm = self._pm.scaled(r.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        p = QPainter(self)
        p.drawPixmap((r.width() - pm.width()) // 2, (r.height() - pm.height()) // 2, pm)
        p.end()

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
        self.find_all = QLineEdit(placeholderText="🎬 Find in all my videos…")
        self.find_all.setToolTip("Any word or phrase: every subtitle line of your videos that uses it (all its forms) — "
                                 "double-click a line to play that moment")
        self.find_all.returnPressed.connect(self.find_in_videos)
        frow.addWidget(self.find_all, 1)
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
        self.vw = None                       # the video widget is made only while a moment plays here (see play_here)
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
        self.p_sent.add_button(ibtn("paraphrase", "Paraphrase the video line: the same meaning at A1, A2, B1, B2 and C1 (the teacher's "
                                    "A1 → C1). The ≈ link after each sentence paraphrases that one.", lambda: self.paraphrase(),
                                    kind="chip", text=" Paraphrase", size=13))
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

    def open_lemma(self, lemma: str, lang: str = "") -> bool:
        """Shows this word (or phrase) in My Words — all filters cleared. False when it isn't saved."""
        k = (lemma or "").strip().lower()
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.video_box.blockSignals(True)
        self.video_box.setCurrentIndex(0)
        self.video_box.blockSignals(False)
        self.day = None
        self.day_lbl.hide()
        self.set_cat("all", refresh=False)
        self.refresh()
        for i, w in enumerate(self.words):
            if k in (w.text.lower(), (w.lemma or "").lower()) and (not lang or w.lang == lang):
                self.list.setCurrentRow(i)
                return True
        return False

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
        m.addAction(f"🔊 Word book — HTML with tabs and natural audio ({n} words)…", self.export_book)
        m.addSeparator()
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

    def find_in_videos(self):
        """Any word or phrase in every subtitle of your videos — the language guessed from the dictionaries."""
        w = self.find_all.text().strip()
        lang = self.main.settings.get("find_lang", "de")
        if w and " " not in w:
            de, en = self.main.dictionary("de"), self.main.dictionary("en")
            try:
                in_de = bool(de and de.lookup(w))
                in_en = bool(en and en.lookup(w))
                if in_en and not in_de:
                    lang = "en"
                elif in_de and not in_en:
                    lang = "de"
            except Exception:
                pass
        from .dialogs import UsesDialog
        d = UsesDialog(self.main, w, lang)
        d.exec()
        self.main.settings["find_lang"] = d.lang
        self.main.save_settings()

    def export_book(self):
        """My Words as one HTML file: tabs, explanations, sentences, collocations, flashcards — audio inside."""
        import datetime
        from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QVBoxLayout
        from . import voice, wordbook
        if not self.words:
            self.main.msg("No words to export")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Word book (HTML)")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(f"<b>{len(self.words)} words</b> (the ones in the list now) as one HTML file: tabs for the words with "
                           "their explanations, all sentences, collocations and flashcards. Double-click it — it opens in any "
                           "browser, also on the phone and without internet.", wordWrap=True))
        v.addWidget(QLabel("Audio in the file, read by", objectName="small"))
        eng = QComboBox()
        eng.addItem("Microsoft natural voice (online)", "edge")
        eng.addItem("Piper natural voice (offline)" + ("" if voice.piper_ready("de", self.main.settings) else " — needs a download once"), "piper")
        eng.addItem("No audio in the file (the browser's own voice reads)", "none")
        cur = self.main.settings.get("voice_engine", "edge")
        eng.setCurrentIndex(max(0, eng.findData("piper" if cur == "piper" else "edge")))
        v.addWidget(eng)
        c_w = QCheckBox("Audio for the words", checked=True)
        c_s = QCheckBox("Audio for the sentences (from the video and the ones you added)", checked=True)
        c_c = QCheckBox("Audio for the collocations and their examples (takes longer)", checked=False)
        c_f = QCheckBox("Also save the word audio as MP3 files in a folder next to it", checked=False)
        for c in (c_w, c_s, c_c, c_f):
            v.addWidget(c)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if not dlg.exec():
            return
        engine = eng.currentData()
        if engine == "piper" and (voice.piper_missing("de", self.main.settings) or voice.piper_missing("en", self.main.settings)):
            langs = {w.lang for w in self.words}
            if any(voice.piper_missing(lg, self.main.settings) for lg in langs):
                self.main.offer_piper("all")
                self.main.msg("After the offline voices are downloaded, export the word book again", 12000)
                return
        default = str(Path.home() / "Documents" / f"SubPlayer words {datetime.date.today():%Y-%m-%d}.html")
        f, _ = QFileDialog.getSaveFileName(self, "Save the word book", default, "Web page (*.html)")
        if not f:
            return
        items = wordbook.collect(self.main, list(self.words), self._level_name, self.pos_of)
        settings = dict(self.main.settings, voice_engine=engine)
        want = wordbook.wanted(items, c_w.isChecked(), c_s.isChecked(), c_c.isChecked()) if engine != "none" else {}
        mp3_dir = Path(f).with_suffix("") if c_f.isChecked() else None
        main = self.main

        def job():
            clips, note = {}, ""
            if want:
                clips, note = wordbook.make_audio(settings, want,
                                                  lambda d, t, _n: main._bg_progress(d / max(t, 1), f"Word book: audio {d} of {t}…"),
                                                  lambda: main.cancel)
            Path(f).write_text(wordbook.build_html(items, clips), encoding="utf-8")
            n = wordbook.save_mp3_folder(mp3_dir, items, clips) if mp3_dir and clips else 0
            return f, len(items), len(clips), len(want), note, n, str(mp3_dir) if mp3_dir else ""
        self.main.run_bg("wordbook", job, cancellable=True, label=f"Word book: {len(items)} words…")

    def _level_name(self, w) -> str:
        from .levels import NAMES
        lv = self.main.levels.level(w.lemma or w.text, w.lang, self.main.dictionary(w.lang)) if " " not in w.text else 0
        return NAMES[lv]

    def current(self):
        r = self.list.currentRow()
        return self.words[r] if 0 <= r < len(self.words) else None

    # ------------------------------------------------------------------ the four panels
    def toggle_pane(self, pane):
        """One panel big (the others hidden, their row and column get no space) — or back to the four."""
        self.big = None if self.big is pane else pane
        rr = cc = None
        for p, r, c in self.panes:
            on = self.big is None or p is self.big
            p.setVisible(on)
            p.set_big(p is self.big)
            if p is self.big:
                rr, cc = r, c
        for k in (0, 1):
            self.grid.setRowStretch(k, 1 if rr is None or k == rr else 0)
            self.grid.setColumnStretch(k, 1 if cc is None or k == cc else 0)

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

    def _cols_of(self, w) -> list[dict]:
        cols = self.main.store.collocations(w.lang, w.lemma or w.text)
        if not cols and (w.lemma or w.text).lower() != w.text.lower():
            cols = self.main.store.collocations(w.lang, w.text)
        return cols

    def fill_sentences(self, w):
        h = ["<div style='font-size:10.5pt;line-height:140%'>"]
        exs = self.main.store.examples(w.id)
        syns = [c["phrase"] for c in self._cols_of(w) if c.get("kind") == "syn" and c["phrase"]]
        para = f"<a href='para:{{k}}' style='color:{theme.VIOLET};text-decoration:none'>≈&nbsp;A1‑C1</a>"
        if w.sentence:
            h.append(f"<p><a href='play:' style='color:{theme.MAGENTA};text-decoration:none'>▶ video</a>&nbsp; "
                     f"{highlight(w.sentence, w.text)} {para.format(k='v')}</p>")
        for e in exs:
            syn = "" if _contains_word(e.de, w) else next((x for x in syns if x.lower() in e.de.lower()), "")
            body = highlight(e.de, syn) if syn else highlight(e.de, w.text)
            tag = (f"<span style='color:{theme.MINT};font-size:9pt'>≈ {html.escape(syn)}</span>&nbsp; " if syn else "")
            h.append(f"<p style='margin-bottom:0'>{tag}{body} "
                     f"<a href='say:{e.id}' style='color:{theme.CYAN};text-decoration:none'>🔊</a> {para.format(k=e.id)} "
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
        allc = self._cols_of(w)
        cols = [c for c in allc if c.get("kind") != "syn"]
        syns = [c for c in allc if c.get("kind") == "syn"]
        qs = self.main.store.questions(lang=w.lang, lemma=w.lemma or w.text)
        e_ = html.escape

        def rows(items, color, mark=""):
            out = ["<table cellspacing=0 cellpadding=3 width='100%'>"]
            for c in items:
                out.append(f"<tr><td style='color:{color};font-weight:600;padding-right:10px'>{mark}{e_(c['phrase'])}</td>"
                           f"<td>{e_(c['meaning'])} <a href='delc:{c['id']}' style='color:{theme.DIM};text-decoration:none'>✕</a></td></tr>")
                if c["example"]:
                    out.append(f"<tr><td></td><td style='color:{theme.DIM};font-style:italic'>{e_(c['example'])} "
                               f"<a href='sayt:{_q(c['example'])}' style='color:{theme.CYAN};text-decoration:none'>🔊</a></td></tr>")
            out.append("</table>")
            return out

        h = ["<div style='font-size:10.5pt;line-height:140%'>"]
        h += rows(cols, theme.GOLD)
        if syns:
            h.append(f"<p style='color:{theme.MINT};font-weight:700;letter-spacing:1px;margin:12px 0 2px 0'>SYNONYMS</p>")
            h += rows(syns, theme.MINT, "≈ ")
        if not allc:
            h.append(f"<p style='color:{theme.DIM}'>No collocations or synonyms yet. <a href='teach:' style='color:{theme.CYAN}'>Ask the "
                     "teacher</a> (Ollama, ChatGPT, Gemini, DeepSeek or Grok), or <a href='edit:' style='color:{theme.CYAN}'>write "
                     "them yourself</a>.</p>")
        elif not syns:
            h.append(f"<p style='color:{theme.DIM};margin-top:10px'>No synonyms yet — <a href='teach:' style='color:{theme.CYAN}'>ask "
                     "the teacher</a> again (New answer): it now gives synonyms with example sentences.</p>")
        if qs:
            h.append(f"<p style='color:{theme.DIM};margin-top:10px'>📝 {len(qs)} exam question(s) on this word are in Review.</p>")
        nn = self.main.store.note_count({w.lemma or w.text, w.text})
        if nn:
            h.append(f"<p style='margin-top:6px'><a href='notes:' style='color:{theme.CYAN};text-decoration:none'>📓 {nn} answer(s) "
                     "of the teacher on this word in the Notebook</a></p>")
        h.append("</div>")
        self.v_coll.setHtml("".join(h))
        self.p_coll.count.setText(f"· {len(allc)}" if allc else "")

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
            self.fill_collocations(w)
            return self.fill_sentences(w)
        if kind == "notes":
            return self.main.notebook(lemma=w.lemma or w.text)
        if kind == "para":
            if val == "v":
                return self.paraphrase(w.sentence)
            ex = next((e for e in self.main.store.examples(w.id) if str(e.id) == val), None)
            return self.paraphrase(ex.de) if ex else None
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
        if self.vw is not None:
            return self.stop_video()
        if not self.main.find_video(w):
            self.vmsg.setText(f"The video “{w.video_name}” isn't on this PC (or was renamed) — put it in Videos, Downloads or a "
                              "folder you opened before.")
            self.vmsg.show()
            return
        from PySide6.QtMultimediaWidgets import QVideoWidget
        self.main.hide_mini()
        self.vw = QVideoWidget()
        self.vw.setStyleSheet("background:#000")
        self.p_video.body.insertWidget(1, self.vw, 1)
        self.snap.hide()
        self.vw.show()
        self.main.set_output(self.vw)
        self.main.play_clip(w, quiet=True)

    def stop_video(self):
        self.vmsg.hide()
        if self.vw is not None:
            self.main.player.pause()
            self.main.clear_ab()
            self.main.player.setVideoOutput(self.main.vw)
            vw, self.vw = self.vw, None
            vw.hide()
            vw.setParent(None)
            vw.deleteLater()
            self.snap.show()

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
            self.main.teacher_for(w.text, w.lemma or w.text, w.sentence, w.lang, lambda: w, 0, at_ms=w.start_ms, video=w.video_name)

    def paraphrase(self, sentence: str | None = None):
        """The teacher's A1 → C1 tab on the word's video line (or one of its sentences): the same meaning at five levels."""
        w = self.current()
        if not w:
            return
        s = (sentence if sentence is not None else w.sentence) or ""
        if not s.strip():
            exs = self.main.store.examples(w.id)
            s = exs[0].de if exs else ""
        if not s.strip():
            self.main.msg("This word has no sentence yet — add one (＋ in Sentences) to paraphrase it")
            return
        self.main.teacher_for(w.text, w.lemma or w.text, s, w.lang, lambda: w, 6,
                              at_ms=w.start_ms if s == w.sentence else -1, video=w.video_name)

    def play(self):
        w = self.current()
        self.stop_video()
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
        from . import questions
        q = self.cur
        self.sent = None
        try:
            self.passage = questions.passage_of(q)          # its reading text (or the lesson's), shown above the question
        except Exception:
            self.passage = ""
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
            h.append(passage_html(getattr(self, "passage", "")))
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
TYPES = (("gap", "Fill the gap", "A word is missing from a sentence — choose or type it"),
         ("dictation", "Dictation", "Hear the line of the video and type it"),
         ("article", "der · die · das", "The article of German nouns"),
         ("exam", "Exam questions", "Your TestDaF / IELTS questions — from AI lessons (To Review) and the teacher — with their texts"))
TYPE_NAME = {k: n for k, n, _ in TYPES}


def _cues_for(main, name: str):
    """(cues, lang, video path) of a video by its file name: the one in the player, SubPlayer's own subtitles, or an .srt
    next to the video. ([], "", "") when it has no subtitles on this PC."""
    from . import subtitles, syncer
    if name and getattr(main, "video_name", "") == name and getattr(main, "cues", None):
        return main.cues, main.cue_lang, main.video
    path = main.find_video(SavedWord(text="", lemma="", sentence="", video_name=name)) if name else None
    for lang in ("de", "en"):
        f = syncer.subs_dir() / f"{subtitles.video_key(name)}.{lang}.srt"
        if f.exists():
            cues = subtitles.parse(f.read_text(encoding="utf-8", errors="replace"))
            if cues:
                return cues, lang, path or ""
    if path:
        base = Path(path)
        for cand in (base.with_suffix(".de.srt"), base.with_suffix(".en.srt"), base.with_suffix(".srt")):
            if cand.exists():
                cues = subtitles.parse(cand.read_text(encoding="utf-8", errors="replace"))
                if cues:
                    lang = "en" if cand.name.endswith(".en.srt") else ("de" if cand.name.endswith(".de.srt") else subtitles.guess_lang(cues[:80]))
                    return cues, lang, path
    return [], "", ""


class PracticePage(QWidget):
    N = 10

    def __init__(self, main):
        super().__init__(objectName="page")
        from PySide6.QtWidgets import QCheckBox, QComboBox
        self.main = main
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(GradientLabel("Practice", 22, QFont.Black))
        top.addSpacing(10)
        top.addWidget(QLabel("Question types", objectName="small"))
        self.modes = {}
        for key, label, tip in TYPES:
            b = QPushButton(label, checkable=True, toolTip=tip + " — choose one or more, then ▶ Start")
            b.setProperty("kind", "chip")
            b.setMinimumWidth(120)
            b.clicked.connect(lambda _=False, k=key: self._type_clicked(k))
            self.modes[key] = b
            top.addWidget(b)
        top.addStretch(1)
        v.addLayout(top)

        bar = QHBoxLayout()                              # what to practise: which video, which words, the whole text
        bar.setSpacing(8)
        bar.addWidget(QLabel("Video", objectName="small"))
        self.video_box = QComboBox()
        self.video_box.setToolTip("Practise everything you saved — or only one video: its words, its lessons' questions, its whole text")
        self.video_box.setMinimumContentsLength(30)
        self.video_box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.video_box.currentIndexChanged.connect(self._video_changed)
        bar.addWidget(self.video_box, 2)
        self.words_b = QPushButton("All words ▾")
        self.words_b.setToolTip("Choose the words to practise (all of them, or only some)")
        self.words_b.clicked.connect(self.pick_words)
        bar.addWidget(self.words_b)
        self.whole = QCheckBox("Whole video text")
        self.whole.setToolTip("Gaps and dictation from every line of the video — not only from the words you saved "
                              "(needs the video's subtitles on this PC)")
        self.whole.toggled.connect(self._whole_toggled)
        bar.addWidget(self.whole)
        self.lv_box = QComboBox()
        self.lv_box.setToolTip("Whole video text: gaps at words of this level or harder")
        from .levels import NAMES
        for n in range(1, 7):
            self.lv_box.addItem(f"gaps {NAMES[n]}+", n)
        self.lv_box.setCurrentIndex(2)
        bar.addWidget(self.lv_box)
        bar.addWidget(QLabel("Questions", objectName="small"))
        self.n_box = QComboBox()
        for n in (10, 20, 30, 50):
            self.n_box.addItem(str(n), n)
        self.n_box.addItem("All", 10_000)
        self.n_box.setCurrentIndex(max(0, self.n_box.findData(int(main.settings.get("practice_n", 10)))))
        bar.addWidget(self.n_box)
        self.start_b = QPushButton("▶ Start")
        self.start_b.setProperty("accent", True)
        self.start_b.setToolTip("New questions with these choices")
        self.start_b.clicked.connect(lambda: self.start())
        bar.addWidget(self.start_b)
        v.addLayout(bar)

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
        self.view.setMaximumHeight(420)
        v.addStretch(1)
        wrap = QHBoxLayout()
        wrap.addStretch(1)
        wrap.addWidget(self.box, 5)
        wrap.addStretch(1)
        v.addLayout(wrap)
        v.addStretch(2)
        st = main.settings.get("practice_types") or ["gap"]
        self.types = [k for k, _, _ in TYPES if k in st] or ["gap"]
        self.chosen: set[int] | None = None              # word ids, None = all words of the selection
        self.qs, self.k, self.score, self.answered, self.show_hint, self.source = [], 0, 0, False, False, ""
        self.mode = self.types[0]
        self._filling = False
        self._show_types()
        self.rnd = random.Random()

    # ------------------------------------------------------------------ choices
    def _show_types(self):
        for k, b in self.modes.items():
            b.setChecked(k in self.types)

    def _type_clicked(self, k):
        if k in self.types and len(self.types) > 1:
            self.types.remove(k)
        elif k not in self.types:
            self.types.append(k)
        self.types = [x for x, _, _ in TYPES if x in self.types]
        self._show_types()
        self.main.settings["practice_types"] = self.types
        self.main.save_settings()
        self.start()

    def _video_names(self) -> list[tuple[str, str]]:
        """[(video name, label)] — videos with saved words, exam questions or AI lessons, the newest first."""
        from . import lessons
        when, nw, nq = {}, {}, {}
        for w in self.main.store.all():
            if w.video_name:
                when[w.video_name] = max(when.get(w.video_name, 0), w.created)
                nw[w.video_name] = nw.get(w.video_name, 0) + 1
        for q in self.main.store.questions():
            if q.video_name:
                when[q.video_name] = max(when.get(q.video_name, 0), q.created)
                nq[q.video_name] = nq.get(q.video_name, 0) + 1
        try:
            for name, _ in lessons.all_lessons():
                when.setdefault(name, 1)
        except Exception:
            pass
        cur = getattr(self.main, "video_name", "")
        if cur:
            when[cur] = max(when.get(cur, 0), now_ms())
        out = []
        for n in sorted(when, key=lambda x: -when[x]):
            bits = [f"{nw[n]} words" if nw.get(n) else "", f"{nq[n]} questions" if nq.get(n) else ""]
            short = Path(n).stem
            out.append((n, (short[:48] + ("…" if len(short) > 48 else "")) + (" · " + " · ".join(b for b in bits if b) if any(bits) else "")))
        return out

    def _fill_videos(self, want: str | None = None):
        cur = want if want is not None else (self.video_box.currentData() if self.video_box.count() else "")
        self._filling = True
        self.video_box.clear()
        self.video_box.addItem("All my words and questions", "")
        for n, label in self._video_names():
            self.video_box.addItem(label, n)
            self.video_box.setItemData(self.video_box.count() - 1, n, Qt.ItemDataRole.ToolTipRole)
        if cur and self.video_box.findData(cur) < 0:
            self.video_box.addItem(Path(cur).stem[:48], cur)
        self.video_box.setCurrentIndex(max(0, self.video_box.findData(cur or "")))
        self._filling = False
        self._update_bar()

    def video(self) -> str:
        return self.video_box.currentData() or ""

    def _video_changed(self, *_):
        if self._filling:
            return
        self.chosen = None
        if not self.video():
            self._filling = True
            self.whole.setChecked(False)
            self._filling = False
        self._update_bar()
        self.start()

    def _whole_toggled(self, on):
        self._update_bar()
        if not self._filling:
            self.start()

    def _update_bar(self):
        vid = self.video()
        self.whole.setEnabled(bool(vid))
        self.lv_box.setVisible(self.whole.isChecked() and bool(vid))
        words = self._words(all_of_video=True)
        n = len(words) if self.chosen is None else len([w for w in words if w.id in self.chosen])
        self.words_b.setText((f"All {len(words)} words ▾" if self.chosen is None else f"{n} of {len(words)} words ▾")
                             if words else "No saved words ▾")
        self.words_b.setEnabled(bool(words))

    def _words(self, all_of_video: bool = False) -> list[SavedWord]:
        vid = self.video()
        ws = [w for w in self.main.store.all() if not vid or w.video_name == vid]
        if not all_of_video and self.chosen is not None:
            ws = [w for w in ws if w.id in self.chosen]
        return sorted(ws, key=lambda w: (w.box, w.due))

    def pick_words(self):
        from PySide6.QtWidgets import QDialog
        words = sorted(self._words(all_of_video=True), key=lambda w: (w.text.lower()))
        if not words:
            return
        d = QDialog(self)
        d.setWindowTitle("Words to practise")
        d.resize(460, 560)
        lv = QVBoxLayout(d)
        lv.addWidget(QLabel(("From “" + Path(self.video()).stem[:60] + "”") if self.video() else "All your saved words", objectName="hint"))
        find = QLineEdit(placeholderText="Find…")
        lv.addWidget(find)
        lst = QListWidget()
        for w in words:
            it = QListWidgetItem(f"{(w.article + ' ') if w.article else ''}{w.text}   —   {w.english[:40]}")
            it.setData(Qt.ItemDataRole.UserRole, w.id)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if self.chosen is None or w.id in self.chosen else Qt.CheckState.Unchecked)
            lst.addItem(it)
        lv.addWidget(lst, 1)
        find.textChanged.connect(lambda t: [lst.item(i).setHidden(t.lower() not in lst.item(i).text().lower()) for i in range(lst.count())])
        row = QHBoxLayout()

        def set_all(on):
            for i in range(lst.count()):
                if not lst.item(i).isHidden():
                    lst.item(i).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        for label, on in (("All", True), ("None", False)):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, x=on: set_all(x))
            row.addWidget(b)
        due = QPushButton("Only due ones")
        due.setToolTip("Tick only the words that are due for review now")
        due.clicked.connect(lambda: [lst.item(i).setCheckState(Qt.CheckState.Checked if words[i].due <= now_ms() else Qt.CheckState.Unchecked)
                                     for i in range(lst.count())])
        row.addWidget(due)
        row.addStretch(1)
        ok = QPushButton("Practise these")
        ok.setProperty("accent", True)
        ok.clicked.connect(d.accept)
        row.addWidget(ok)
        lv.addLayout(row)
        if not d.exec():
            return
        ids = {lst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lst.count())
               if lst.item(i).checkState() == Qt.CheckState.Checked}
        self.chosen = None if len(ids) == len(words) else ids
        self._update_bar()
        self.start()

    # ------------------------------------------------------------------ questions
    def start(self, mode=None):
        """New questions with the choices of the bar. [mode] (an old caller) practises that one type."""
        if mode:
            self.types = [mode]
            self._show_types()
        if not self.video_box.count():
            self._fill_videos()
        n = int(self.n_box.currentData() or 10)
        self.main.settings["practice_n"] = n
        self.N = n
        vid = self.video()
        per: dict[str, list] = {}
        cues, lang, path = ([], "", "")
        if self.whole.isChecked() and vid and any(t in self.types for t in ("gap", "dictation")):
            cues, lang, path = _cues_for(self.main, vid)
        for t in self.types:
            if t in ("gap", "dictation") and cues:
                per[t] = self._from_text(cues, path, vid, lang, t, int(self.lv_box.currentData() or 3))
            else:
                per[t] = {"gap": self._gaps, "dictation": self._dictation, "article": self._articles, "exam": self._exam}[t]()
        self.qs = []
        lists = [list(per[t]) for t in self.types]
        while any(lists) and len(self.qs) < n:                      # mixed: one of each type in turn
            for lst in lists:
                if lst and len(self.qs) < n:
                    self.qs.append(lst.pop(0))
        self.k = self.score = 0
        bits = [f"“{Path(vid).stem[:40]}”" if vid else "all your words"]
        if self.chosen is not None:
            bits.append(f"{len(self.chosen)} chosen word(s)")
        if self.whole.isChecked() and vid:
            bits.append("whole text" if cues else "whole text: no subtitles of this video found on this PC")
        self.source = " · ".join(bits)
        self.show_q()

    def start_text(self, cues, video: str, name: str, lang: str, mode: str, min_level: int = 3):
        """From Study this video: questions from every line of that video (not only saved words)."""
        self._fill_videos(name)
        self._filling = True
        self.whole.setChecked(True)
        self.lv_box.setCurrentIndex(max(0, self.lv_box.findData(min_level)))
        self._filling = False
        self.chosen = None
        self._update_bar()
        self.types = [mode]
        self._show_types()
        self.start()

    def _gaps(self) -> list:
        words = self._words()
        pool = [w.text for w in self.main.store.all()]
        out = []
        for w in words:
            opts = sentences_of(self.main, w)
            self.rnd.shuffle(opts)
            for s_, en, fa in opts:
                c = practice.cloze(w, s_, en, fa)
                if c:
                    out.append(("gap", w, c, practice.choices(c.answer, pool, self.rnd)))
                    break
            if len(out) >= self.N:
                break
        return out

    def _dictation(self) -> list:
        return [("dictation", w, None, []) for w in self._words() if w.start_ms >= 0 and w.sentence and w.video_name][:self.N]

    def _articles(self) -> list:
        return [("article", w, None, ["der", "die", "das"]) for w in self._words()
                if w.lang == "de" and w.article in ("der", "die", "das")][:self.N]

    def _exam(self) -> list:
        vid = self.video()
        qs = self.main.store.questions(video_name=vid) if vid else self.main.store.questions()
        if self.chosen is not None:                                   # only the chosen words' questions
            lem = {(w.lemma or w.text).lower() for w in self._words()} | {w.text.lower() for w in self._words()}
            qs = [q for q in qs if q.lemma and q.lemma.lower() in lem]
        qs.sort(key=lambda q: (q.reviews, q.box, q.due))
        return [("exam", q, None, list(q.options)) for q in qs[:self.N]]

    def _from_text(self, cues, video: str, name: str, lang: str, mode: str, min_level: int) -> list:
        """Questions from every line of a video (not only saved words): gaps at words of min_level or harder, dictation of
        its lines."""
        from . import library
        d = self.main.dictionary(lang)
        lines = [c for c in cues if len(c.text.split()) >= 4]
        self.rnd.shuffle(lines)
        out = []
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
                out.append(("gap", w, cz, practice.choices(cz.answer, pool, self.rnd)))
        else:
            for c in lines[:self.N]:
                out.append(("dictation", SavedWord(text=c.text.split()[0], lemma="", sentence=c.text, video_uri=video, video_name=name,
                                                   start_ms=c.start_ms, end_ms=c.end_ms, lang=lang), None, []))
        return out

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
            if empty:
                need = {"gap": "saved words with sentences", "dictation": "saved words with their video moment",
                        "article": "German nouns (der · die · das)",
                        "exam": "exam questions (AI lesson ▸ To Review, or Teacher ▸ TestDaF / IELTS questions)"}
                msg = (f"Nothing for {' · '.join(TYPE_NAME[t] for t in self.types)} in {self.source or 'your words'}. "
                       f"This needs {' or '.join(need[t] for t in self.types)}"
                       + (" — or tick “Whole video text”." if self.video() and not self.whole.isChecked() else "."))
            else:
                msg = f"{self.score} of {len(self.qs)} right · 🔥 {self.main.progress.streak} day streak"
            self.view.setHtml(f"<h1 style='text-align:center;color:{theme.CYAN}'>{'Nothing to practise yet' if empty else 'Finished!'}</h1>"
                              f"<p style='text-align:center;color:{theme.DIM}'>{html.escape(msg)}</p>"
                              + ("" if empty else f"<p style='text-align:center;color:{theme.DIM}'>▶ Start for new questions</p>"))
            self.head.setText(self.source)
            for wdg in (self.input, self.b_play, self.b_hint, self.b_next):
                wdg.setVisible(False)
            return
        mode, w, c, ch = self.qs[self.k]
        self.mode = mode
        self.head.setText(f"Question {self.k + 1} of {len(self.qs)} · {TYPE_NAME[mode]} · score {self.score}"
                          + (f" · {self.source}" if self.source else ""))
        self.b_next.setVisible(False)
        self.b_play.setVisible(mode in ("dictation", "gap") or (mode == "exam" and bool(w.question)))
        self.b_hint.setVisible(mode == "gap")
        self.input.setVisible(not ch or mode == "dictation")
        self.input.setPlaceholderText("Your answer — then Enter (it is compared with the model answer)" if mode == "exam"
                                      else "Type your answer and press Enter")
        for opt in ch:
            b = QPushButton(opt)
            if mode == "exam":
                b.setStyleSheet("text-align:left;padding:6px 12px")
            b.clicked.connect(lambda _=False, o=opt: self.check(o))
            self.choice_row.addWidget(b)
        from PySide6.QtWidgets import QBoxLayout
        self.choice_row.setDirection(QBoxLayout.Direction.TopToBottom if mode == "exam" and (len(ch) > 3 or max(map(len, ch), default=0) > 40)
                                     else QBoxLayout.Direction.LeftToRight)
        self.render()
        if mode == "dictation":
            self.listen()
        self.input.setFocus()

    def render(self, feedback: str = ""):
        mode, w, c, ch = self.qs[self.k]
        if mode == "gap":
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
        elif mode == "dictation":
            h = f"<p style='text-align:center;font-size:15pt;color:{theme.DIM}'>Listen and type the sentence.</p>"
        elif mode == "exam":
            from . import questions
            try:
                passage = questions.passage_of(w)
            except Exception:
                passage = ""
            exam = "IELTS" if w.lang == "en" else "TestDaF"
            src = " · ".join(x for x in (exam, f"„{w.lemma}“" if w.lemma else "", Path(w.video_name).stem[:40] if w.video_name else "") if x)
            h = (f"<p style='text-align:center;color:{theme.DIM};font-size:9pt'>{html.escape(src)}</p>" + passage_html(passage)
                 + f"<p style='text-align:center;font-size:15pt'>{html.escape(w.question)}</p>")
            if self.answered:
                h += f"<p style='text-align:center;font-size:14pt;color:{theme.GOLD}'><b>{html.escape(w.answer)}</b></p>"
                if w.explanation:
                    h += f"<p style='text-align:center;color:{theme.DIM}'>{html.escape(w.explanation)}</p>"
        else:
            art = f"<span style='color:{theme.ARTICLE[w.article]}'>{w.article}</span>" if self.answered else "___"
            h = f"<p style='text-align:center;font-size:30pt;font-weight:800'>{art} {html.escape(w.lemma)}</p>"
            if w.english:
                h += f"<p style='text-align:center;color:{theme.DIM}'>{html.escape(w.english)}</p>"
        self.view.setHtml(h + feedback)

    def check(self, given):
        if self.answered:
            return
        mode, w, c, ch = self.qs[self.k]
        if mode == "exam":
            ok = ReviewPage.is_answer(given, w.answer) if ch else (
                practice.same(given, w.answer) or (len(practice.normalize(given)) > 3 and
                                                   practice.normalize(given) in practice.normalize(w.answer)))
            for i in range(self.choice_row.count()):
                b = self.choice_row.itemAt(i).widget()
                if b and (ReviewPage.is_answer(b.text(), w.answer) or b.text() == given):
                    right = ReviewPage.is_answer(b.text(), w.answer)
                    b.setStyleSheet(f"text-align:left;padding:6px 12px;color:#FFFFFF;background:{'#2E8B57' if right else '#8B2E4F'}")
            return self._finish(ok, "the answer is below" if ch else "compare with the answer below")
        right = (c.answer if mode == "gap" else w.article)
        self._finish(practice.same(given, right), f"The answer: {right}")

    def check_typed(self):
        if self.answered or self.k >= len(self.qs):
            return self.next() if self.answered else None
        mode, w, c, ch = self.qs[self.k]
        t = self.input.text()
        if mode == "dictation":
            marks, score = practice.dictation(w.sentence, t)
            words = " ".join(f"<span style='color:{theme.GOLD if ok else theme.MAGENTA}'>{html.escape(x)}</span>" for x, ok in marks)
            self.answered = True
            ok = score >= 80
            self._finish(ok, "", extra=f"<p style='text-align:center;font-size:15pt'>{words}</p><p style='text-align:center'>{score}% of the words</p>")
        else:
            self.check(t)

    def _finish(self, ok, right_text, extra=""):
        self.answered = True
        mode, w = self.qs[self.k][0], self.qs[self.k][1]
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
        if mode == "article":
            self.main.speak(f"{w.article} {w.lemma}", lang="de")

    def hint(self):
        self.show_hint = True
        self.render()

    def listen(self):
        mode, w, c, ch = self.qs[self.k]
        if mode == "dictation":
            if not self.main.play_clip(w, quiet=True):
                self.main.speak(w.sentence, lang=w.lang)
        elif mode == "exam":
            self.main.speak(w.question, lang=w.lang)
        elif c:
            self.main.speak(c.sentence, lang=w.lang)

    def next(self):
        self.main.player.pause()
        self.main.clear_ab()
        self.k += 1
        self.show_q()

    def showEvent(self, e):
        super().showEvent(e)
        self._fill_videos()                                # new words, questions or lessons since last time
