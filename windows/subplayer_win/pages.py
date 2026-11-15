"""My Words, Review and Practice pages."""
from __future__ import annotations

import html
import random

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
                               QTextBrowser, QVBoxLayout, QWidget)

from . import icons, practice, theme
from .cosmos import GradientLabel
from .store import SavedWord, due_label, now_ms, review


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
        left.addLayout(frow)
        self.cal = QCalendarWidget()
        self.cal.setGridVisible(False)
        self.cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.cal.setMaximumHeight(250)
        self.cal.clicked.connect(self.pick_day)
        self.cal.currentPageChanged.connect(lambda *_: self._mark_calendar())
        self.cal.setStyleSheet(
            "QCalendarWidget QWidget#qt_calendar_navigationbar{background:rgba(40,32,84,0.95);border-radius:8px}"
            "QCalendarWidget QToolButton{color:#FFFFFF;background:transparent;font-weight:700;padding:4px 10px}"
            "QCalendarWidget QToolButton:hover{background:rgba(255,255,255,0.08);border-radius:6px}"
            "QCalendarWidget QMenu{background:#1A1638;color:#E8E6FF}"
            "QCalendarWidget QSpinBox{background:#1A1638;color:#FFFFFF;border:0}"
            "QCalendarWidget QAbstractItemView{background:#110E26;color:#E8E6FF;selection-background-color:#8A5CFF;"
            "selection-color:#FFFFFF;outline:0;border:0}"
            "QCalendarWidget QAbstractItemView:disabled{color:#4A4670}")
        from PySide6.QtGui import QTextCharFormat, QColor as _QC, QBrush as _QB
        wk = QTextCharFormat()
        wk.setForeground(_QB(_QC("#E8E6FF")))
        for d in (Qt.Saturday, Qt.Sunday):
            self.cal.setWeekdayTextFormat(d, wk)
        hd = QTextCharFormat()
        hd.setForeground(_QB(_QC("#9A98B5")))
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
        right.setContentsMargins(22, 18, 18, 16)
        self.detail = QTextBrowser(openLinks=False)
        self.detail.anchorClicked.connect(self._link)
        right.addWidget(self.detail, 1)
        btns = QHBoxLayout()
        self.b_play = ibtn("play", "Play this moment in the video", self.play, kind="", text=" Play in video")
        self.b_speak = ibtn("volume", "Speak", self.speak, kind="", text=" Speak")
        self.b_learn = ibtn("sparkles", "ChatGPT / Grok / dictionaries, add sentences", self.learn, kind="", text=" Learn more ▾")
        self.b_del = ibtn("trash", "Delete this word", self.delete, kind="", text=" Delete", color=theme.MAGENTA)
        for b in (self.b_play, self.b_speak, self.b_learn, self.b_del):
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
        if self.day or self.cat != "all" or vid:
            ws.sort(key=lambda w: -w.created)
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

    def show_word(self, *_):
        w = self.current()
        if not w:
            return
        h = []
        snap = self.main.snap_path(w)
        if snap.exists():
            h.append(f"<p><a href='play:'><img src='{snap.as_uri()}' width='340'></a></p>")
        h.append(f"<p style='font-size:24pt;font-weight:800;margin:0'>{article_html(w)}{html.escape(w.text)}</p>")
        lvn = self._level_name(w)
        cat = dict(CATS)[self.pos_of(w)]
        h.append(f"<p style='color:{theme.DIM};margin:0'>{cat[:-1] if cat.endswith('s') and cat != 'Others' else cat}"
                 + (f" · <b>{'≈' if w.lang == 'de' else ''}{lvn}</b>" if lvn else "")
                 + f" · saved {self._day_of(w.created):%d.%m.%Y}</p>")
        if w.lemma and w.lemma.lower() != w.text.lower():
            h.append(f"<p style='color:{theme.DIM}'>→ {html.escape(w.lemma)}</p>")
        if w.ipa:
            h.append(f"<p style='color:{theme.GOLD};font-size:12.5pt'>{html.escape(w.ipa)}</p>")
        if w.english:
            h.append(f"<p>{html.escape(w.english)}</p>")
        if w.persian:
            h.append(f"<p dir='rtl' style='font-family:Vazirmatn;font-size:14pt'>{html.escape(w.persian)}</p>")
        acc = f"{w.correct * 100 // w.reviews}%" if w.reviews else "–"
        h.append(f"<p style='color:{theme.DIM}'>Reviewed {w.reviews}× · right {acc} · next {due_label(w.due, now_ms())}"
                 f" · from “{html.escape(w.video_name)}”</p>")
        h.append(f"<p style='color:{theme.CYAN};font-weight:700;letter-spacing:2px;font-size:9pt;margin-top:16px'>SENTENCES</p>")
        if w.sentence:
            h.append(f"<p><span style='color:{theme.MAGENTA}'>▶ video</span>&nbsp; {highlight(w.sentence, w.text)}</p>")
        for e in self.main.store.examples(w.id):
            h.append(f"<p style='margin-bottom:0'>{highlight(e.de, w.text)} "
                     f"<a href='say:{e.id}' style='color:{theme.CYAN};text-decoration:none'>🔊</a> "
                     f"<a href='del:{e.id}' style='color:{theme.DIM};text-decoration:none'>✕</a></p>")
            if e.en:
                h.append(f"<p style='color:{theme.DIM};margin:0'>{html.escape(e.en)}</p>")
            if e.fa:
                h.append(f"<p dir='rtl' style='font-family:Vazirmatn;color:{theme.DIM};margin:0 0 6px 0'>{html.escape(e.fa)}</p>")
        self.detail.setHtml("".join(h))

    def _link(self, url):
        kind, _, val = url.toString().partition(":")
        w = self.current()
        if not w:
            return
        if kind == "play":
            return self.play()
        ex = next((e for e in self.main.store.examples(w.id) if str(e.id) == val), None)
        if ex and kind == "say":
            self.main.speak(ex.de, lang=w.lang)
        elif ex and kind == "del":
            self.main.store.delete_example(ex.id)
            self.main.after_change()
            self.show_word()

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
        row = QHBoxLayout()
        self.b_play = ibtn("play", "Play the video moment", self.play, kind="", text=" Play the moment")
        self.b_speak = ibtn("volume", "Speak the sentence", lambda: self.cur and self.main.speak(self.sent[0] if self.sent else self.cur.text, lang=self.cur.lang),
                            kind="", text=" Speak")
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
        self.queue = self.main.store.due(now_ms())
        self.i = self.done = self.got = 0
        self.show_card()

    def show_card(self):
        self.revealed = False
        self.cur = self.queue[self.i] if self.i < len(self.queue) else None
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

    def render(self):
        w = self.cur
        h = []
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
        if e.key() == Qt.Key_Space and self.cur:
            self.reveal() if not self.revealed else self.answer(True)
        elif e.key() in (Qt.Key_1, Qt.Key_Left) and self.revealed:
            self.answer(False)
        elif e.key() in (Qt.Key_2, Qt.Key_Right) and self.revealed:
            self.answer(True)
        else:
            super().keyPressEvent(e)

    def play(self):
        if self.cur:
            self.main.play_clip(self.cur)
            self.main.msg("Playing the moment — come back with 🎓 Review")

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
            if not self.main.play_clip(w):
                self.main.speak(w.sentence, lang=w.lang)
        elif c:
            self.main.speak(c.sentence, lang=w.lang)

    def next(self):
        self.main.player.pause()
        self.main.clear_ab()
        self.k += 1
        self.show_q()
