"""Study one video: every word of its text by level, the words you saved from it, and practice with its whole text."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QStackedWidget, QTextBrowser, QVBoxLayout, QWidget)

from . import library, subtitles, theme
from .cosmos import GradientLabel
from .levels import COLORS, NAMES
from .store import SavedWord


def ibtn(*a, **k):
    from .app import ibtn as _ib
    return _ib(*a, **k)


class StudyPage(QWidget):
    def __init__(self, main):
        super().__init__(objectName="page")
        self.main = main
        self.video, self.name, self.cues, self.lang = "", "", [], "de"
        self.vocab: list[tuple[str, int, int]] = []
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        left = QFrame(objectName="card")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(20, 16, 16, 14)
        lv.setSpacing(9)
        head = QHBoxLayout()
        self.title = GradientLabel("Study this video", 20, QFont.Black)
        head.addWidget(self.title)
        head.addStretch(1)
        back = ibtn("film", "Back to the video", lambda: main.show_page("player"), kind="", text=" Back to the video", size=15)
        head.addWidget(back)
        lv.addLayout(head)
        self.stats = QLabel("", objectName="hint")
        self.stats.setWordWrap(True)
        lv.addWidget(self.stats)

        tabs = QHBoxLayout()
        self.tab_btns = []
        for k, (ic, label) in enumerate((("bars", " Its words by level"), ("star", " My words from it"),
                                         ("puzzle", " Practise its whole text"))):
            b = ibtn(ic, label.strip(), lambda _=False, i=k: self.tab(i), checkable=True, kind="chip", text=label, size=15)
            self.tab_btns.append(b)
            tabs.addWidget(b)
        tabs.addStretch(1)
        lv.addLayout(tabs)
        self.stack = QStackedWidget()
        lv.addWidget(self.stack, 1)

        # 0 — vocabulary by level
        p0 = QWidget(objectName="clear")
        v0 = QVBoxLayout(p0)
        v0.setContentsMargins(0, 4, 0, 0)
        frow = QHBoxLayout()
        self.lv_btns = {}
        for n in range(0, 7):
            b = QPushButton("All" if n == 0 else NAMES[n], checkable=True)
            b.setProperty("kind", "chip")
            if n:
                b.setStyleSheet(f"QPushButton{{color:{COLORS[n]}}}")
            b.clicked.connect(lambda _=False, x=n: self._pick_level(x))
            self.lv_btns[n] = b
            frow.addWidget(b)
        self.unsaved = QCheckBox("Not saved yet")
        self.unsaved.toggled.connect(self._fill_vocab)
        frow.addWidget(self.unsaved)
        frow.addStretch(1)
        v0.addLayout(frow)
        self.find = QLineEdit(placeholderText="Find a word…")
        self.find.textChanged.connect(self._fill_vocab)
        v0.addWidget(self.find)
        self.vlist = QListWidget()
        self.vlist.currentItemChanged.connect(self._show_vocab_word)
        self.vlist.itemDoubleClicked.connect(lambda it: self.play_first())
        v0.addWidget(self.vlist, 1)
        self.stack.addWidget(p0)

        # 1 — my words from this video
        p1 = QWidget(objectName="clear")
        v1 = QVBoxLayout(p1)
        v1.setContentsMargins(0, 4, 0, 0)
        self.slist = QListWidget()
        self.slist.currentItemChanged.connect(self._show_saved_word)
        self.slist.itemDoubleClicked.connect(lambda it: self.play_saved())
        v1.addWidget(self.slist, 1)
        self.stack.addWidget(p1)

        # 2 — practice with the whole text
        p2 = QWidget(objectName="clear")
        v2 = QVBoxLayout(p2)
        v2.setContentsMargins(0, 10, 0, 0)
        v2.addWidget(QLabel("Practise with every line of this video — not only the words you saved.", objectName="hint"))
        self.min_lv = 3
        lrow = QHBoxLayout()
        lrow.addWidget(QLabel("Gaps from words at level", objectName="small"))
        self.gap_lv = {}
        for n in range(1, 7):
            b = QPushButton(f"{NAMES[n]}+", checkable=True)
            b.setProperty("kind", "chip")
            b.clicked.connect(lambda _=False, x=n: self._set_min(x))
            self.gap_lv[n] = b
            lrow.addWidget(b)
        lrow.addStretch(1)
        v2.addLayout(lrow)
        self._set_min(3)
        for ic, label, tip, mode in (("puzzle", "  Fill the gap — whole text", "A word is missing from a line of the video", "gap"),
                                     ("captions", "  Dictation — whole text", "Hear a line of the video and type it", "dictation")):
            b = ibtn(ic, tip, lambda _=False, m=mode: self.practise(m), kind="", text=label, size=18)
            b.setMinimumHeight(46)
            v2.addWidget(b)
        v2.addStretch(1)
        self.stack.addWidget(p2)
        root.addWidget(left, 3)

        right = QFrame(objectName="card")
        right.setFixedWidth(400)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(20, 18, 16, 16)
        self.detail = QTextBrowser(openLinks=False)
        self.detail.anchorClicked.connect(self._link)
        rv.addWidget(self.detail, 1)
        brow = QHBoxLayout()
        self.b_play = ibtn("play", "Play where it is said", self.play_current, kind="", text=" Play", size=15)
        self.b_save = ibtn("star", "Save to My Words with this moment", self.save_current, kind="", text=" Save", size=15)
        self.b_uses = ibtn("where", "Where else is it used in my videos?", self.uses_current, kind="", text=" Other videos", size=15)
        for b in (self.b_play, self.b_save, self.b_uses):
            brow.addWidget(b)
        rv.addLayout(brow)
        root.addWidget(right)
        self.level_filter = 0
        self._pick_level(0)
        self.tab(0)

    # ------------------------------------------------------------------ load
    def load(self, video: str, name: str, cues: list, lang: str):
        self.video, self.name, self.cues, self.lang = video, name, cues, lang
        self.title.setText(f"Study: {name[:60]}")
        d = self.main.dictionary(lang)
        self.vocab = library.vocabulary(cues, lang, self.main.levels, d)
        self._first = {}
        for k, c in enumerate(cues):
            for m in library.TOKEN.finditer(c.text):
                self._first.setdefault(m.group(0).strip("'’-").lower(), k)
        counts = [0] * 7
        for _, _, lv in self.vocab:
            counts[lv] += 1
        words = sum(1 for c in cues for _ in library.TOKEN.finditer(c.text))
        mine = self._saved()
        self.stats.setText(f"{len(cues)} lines · {words} words · {len(self.vocab)} different · " + " · ".join(
            f"<span style='color:{COLORS[n]}'>{NAMES[n]} {counts[n]}</span>" for n in range(1, 7)) +
            f" · you saved {len(mine)}" + (" · <span style='color:#7F7A9E'>German levels are estimates</span>" if lang == "de" else ""))
        self._fill_vocab()
        self._fill_saved()
        self.detail.setHtml(f"<p style='font-size:17pt;font-weight:800;color:{theme.CYAN}'>Pick a word</p>"
                            f"<p style='color:{theme.DIM}'>Words of this video, most frequent first. Filter by level to find the ones "
                            "worth learning, save them with the moment they are said, and practise with the whole text.</p>")

    def _saved(self) -> list[SavedWord]:
        return [w for w in self.main.store.all() if (self.video and w.video_uri == self.video) or
                (w.video_name and w.video_name.lower() == self.name.lower())]

    def tab(self, i: int):
        self.stack.setCurrentIndex(i)
        for k, b in enumerate(self.tab_btns):
            b.setChecked(k == i)

    def _pick_level(self, n: int):
        self.level_filter = n
        for k, b in self.lv_btns.items():
            b.setChecked(k == n)
        self._fill_vocab()

    def _fill_vocab(self, *_):
        self.vlist.clear()
        q = self.find.text().strip().lower()
        saved = {w.text.lower() for w in self.main.store.all()} | {w.lemma.lower() for w in self.main.store.all()}
        for word, n, lv in self.vocab:
            if self.level_filter and lv != self.level_filter:
                continue
            if q and q not in word.lower():
                continue
            if self.unsaved.isChecked() and word.lower() in saved:
                continue
            it = QListWidgetItem(f"{word}   ·   {n}×   ·   {NAMES[lv] or '–'}" + ("   ★" if word.lower() in saved else ""))
            it.setForeground(QColor(COLORS[lv] if lv else theme.DIM))
            it.setData(Qt.UserRole, word)
            self.vlist.addItem(it)

    def _fill_saved(self):
        self.slist.clear()
        for w in self._saved():
            mm, ss = divmod(max(0, w.start_ms) // 1000, 60)
            it = QListWidgetItem(f"{(w.article + ' ') if w.article else ''}{w.text}   —   {w.english[:50]}\n{mm}:{ss:02d} · "
                                 f"{html.unescape(w.sentence[:90])}")
            it.setData(Qt.UserRole, w.id)
            self.slist.addItem(it)
        if not self.slist.count():
            it = QListWidgetItem("No words saved from this video yet — pick some in “Its words by level”.")
            it.setFlags(Qt.NoItemFlags)
            self.slist.addItem(it)

    # ------------------------------------------------------------------ details
    def _current_word(self) -> str | None:
        if self.stack.currentIndex() == 1:
            it = self.slist.currentItem()
            wid = it.data(Qt.UserRole) if it else None
            w = next((x for x in self.main.store.all() if x.id == wid), None)
            return w.text if w else None
        it = self.vlist.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _cue_of(self, word: str) -> int:
        return self._first.get(word.lower(), -1)

    def _show_vocab_word(self, *_):
        word = self._current_word()
        if word:
            self._render(word, self._cue_of(word))

    def _show_saved_word(self, *_):
        it = self.slist.currentItem()
        wid = it.data(Qt.UserRole) if it else None
        w = next((x for x in self.main.store.all() if x.id == wid), None)
        if w:
            k = next((i for i, c in enumerate(self.cues) if c.start_ms == w.start_ms), self._cue_of(w.text))
            self._render(w.text, k)

    def _render(self, word: str, k: int):
        d = self.main.dictionary(self.lang)
        entries = d.lookup(word) if d else []
        lv = self.main.levels.level(word, self.lang, d)
        h = []
        e = entries[0] if entries else None
        art = f"<span style='color:{theme.ARTICLE.get(e.article, theme.LIGHT)}'>{e.article} </span>" if e and e.article else ""
        h.append(f"<p style='font-size:22pt;font-weight:800;margin:0'>{art}{html.escape(e.lemma if e else word)}</p>")
        meta = []
        if lv:
            meta.append(f"<span style='color:{COLORS[lv]};font-weight:800'>{'≈' if self.lang == 'de' else ''}{NAMES[lv]}</span>")
        if e:
            meta.append(f"<span style='color:{theme.MAGENTA}'>{html.escape(e.pos_de or e.pos)}</span>")
            if e.ipa:
                meta.append(f"<span style='color:{theme.GOLD}'>{html.escape(e.ipa)}</span>")
        h.append(" · ".join(meta))
        if e:
            if e.lang != "en" and e.english:
                h.append(f"<p>{html.escape(', '.join(e.english[:4]))}</p>")
            elif e.senses:
                h.append(f"<p>{html.escape(e.senses[0].de)}</p>")
            fa = e.persian or e.persian_via_english
            if fa:
                h.append(theme.fa_span(html.escape("، ".join(fa[:4])), "14pt"))
        if 0 <= k < len(self.cues):
            c = self.cues[k]
            mm, ss = divmod(c.start_ms // 1000, 60)
            h.append(f"<p style='color:{theme.CYAN};font-weight:700;letter-spacing:2px;font-size:9pt;margin-top:14px'>IN THIS VIDEO · "
                     f"{mm}:{ss:02d}</p><p><i>{html.escape(c.text)}</i></p>")
            uses = [i for i, cc in enumerate(self.cues) if any(m.group(0).lower() == word.lower()
                                                                for m in library.TOKEN.finditer(cc.text))]
            if len(uses) > 1:
                h.append(f"<p style='color:{theme.DIM}'>Said {len(uses)} times here: " + " ".join(
                    f"<a href='cue:{i}' style='color:{theme.CYAN};text-decoration:none'>{self.cues[i].start_ms // 60000}:"
                    f"{self.cues[i].start_ms // 1000 % 60:02d}</a>" for i in uses[:12]) + "</p>")
        self._shown = (word, k, e)
        self.detail.setHtml("".join(h))

    def _link(self, url):
        kind, _, val = url.toString().partition(":")
        if kind == "cue" and val.isdigit():
            c = self.cues[int(val)]
            self.main.show_page("player")
            self.main.open_use(self.video, None, c.start_ms + self.main.sub_offset, c.end_ms + self.main.sub_offset)

    # ------------------------------------------------------------------ actions
    def play_current(self):
        s = getattr(self, "_shown", None)
        if s and 0 <= s[1] < len(self.cues):
            c = self.cues[s[1]]
            self.main.open_use(self.video, None, c.start_ms + self.main.sub_offset, c.end_ms + self.main.sub_offset)

    play_first = play_current

    def play_saved(self):
        self._show_saved_word()
        self.play_current()

    def save_current(self):
        s = getattr(self, "_shown", None)
        if not s:
            return
        word, k, e = s
        if not (0 <= k < len(self.cues)):
            return
        c = self.cues[k]
        start = c.start_ms + self.main.sub_offset
        if self.main.store.find(word, self.video, start):
            self.main.msg("Already in My Words")
            return
        english = (", ".join(e.english[:3]) if e.lang != "en" else (e.senses[0].de if e.senses else "")) if e else ""
        persian = "، ".join((e.persian or e.persian_via_english)[:3]) if e else ""
        w = SavedWord(text=word, lemma=e.lemma if e else word, sentence=c.text, video_uri=self.video, video_name=self.name,
                      start_ms=start, end_ms=c.end_ms + self.main.sub_offset, article=e.article if e else "",
                      ipa=e.ipa if e else "", english=english, persian=persian, lang=e.lang if e else self.lang)
        w.id = self.main.store.insert(w)
        self.main.make_snapshot(w)
        self.main.after_change()
        self._fill_saved()
        self._fill_vocab()
        self.main.msg(f"★ “{word}” saved with its moment in the video")

    def uses_current(self):
        s = getattr(self, "_shown", None)
        if s:
            self.main.show_uses(s[0], self.lang)

    def _set_min(self, n):
        self.min_lv = n
        for k, b in self.gap_lv.items():
            b.setChecked(k == n)

    def practise(self, mode: str):
        if not self.cues:
            return
        self.main.practice_page.start_text(self.cues, self.video, self.name, self.lang, mode, self.min_lv)
        self.main.show_page("practice", start=False)
