"""My Words, Review and Practice pages."""
from __future__ import annotations

import html
import random

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
                               QTextBrowser, QVBoxLayout, QWidget)

from . import practice, theme
from .store import due_label, now_ms, review


def card() -> QFrame:
    f = QFrame(objectName="card")
    return f


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
class WordsPage(QWidget):
    def __init__(self, main):
        super().__init__(objectName="page")
        self.main = main
        root = QHBoxLayout(self)
        left = QVBoxLayout()
        head = QHBoxLayout()
        self.title = QLabel("My Words", objectName="title")
        head.addWidget(self.title)
        head.addStretch(1)
        self.stats = QLabel("", objectName="hint")
        head.addWidget(self.stats)
        left.addLayout(head)
        self.search = QLineEdit(placeholderText="Search your words…")
        self.search.textChanged.connect(self.refresh)
        left.addWidget(self.search)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.show_word)
        left.addWidget(self.list, 1)
        row = QHBoxLayout()
        b1 = QPushButton("🎓 Review due words")
        b1.setProperty("accent", True)
        b1.clicked.connect(lambda: main.show_page("review"))
        b2 = QPushButton("🧩 Practice")
        b2.clicked.connect(lambda: main.show_page("practice"))
        row.addWidget(b1)
        row.addWidget(b2)
        left.addLayout(row)
        root.addLayout(left, 2)

        right = QVBoxLayout()
        self.detail = QTextBrowser(openLinks=False)
        self.detail.anchorClicked.connect(self._link)
        right.addWidget(self.detail, 1)
        btns = QHBoxLayout()
        self.b_play = QPushButton("▶ Play in video")
        self.b_play.clicked.connect(self.play)
        self.b_speak = QPushButton("🔊 Speak")
        self.b_speak.clicked.connect(self.speak)
        self.b_learn = QPushButton("Learn more / add sentences ▾")
        self.b_learn.clicked.connect(self.learn)
        self.b_del = QPushButton("🗑 Delete")
        self.b_del.clicked.connect(self.delete)
        for b in (self.b_play, self.b_speak, self.b_learn, self.b_del):
            btns.addWidget(b)
        right.addLayout(btns)
        root.addLayout(right, 3)
        self.words = []

    def refresh(self, *_):
        q = self.search.text().strip().lower()
        all_words = self.main.store.all()
        self.words = [w for w in all_words if not q or q in w.text.lower() or q in w.lemma.lower() or q in w.english.lower()]
        now = now_ms()
        due = sum(1 for w in all_words if w.due <= now)
        p = self.main.progress
        self.stats.setText(f"{len(all_words)} words · {due} due · 🔥 {p.streak} day streak · {p.today_count} today")
        cur = self.list.currentRow()
        self.list.clear()
        for w in self.words:
            flag = "🇬🇧 " if w.lang == "en" else ""
            it = QListWidgetItem(f"{flag}{(w.article + ' ') if w.article else ''}{w.text}   —   {w.english[:60]}\n"
                                 f"reviewed {w.reviews}× · box {w.box}/7 · {due_label(w.due, now)}")
            self.list.addItem(it)
        if self.words:
            self.list.setCurrentRow(min(max(cur, 0), len(self.words) - 1))
        else:
            self.detail.setHtml(f"<h2 style='color:{theme.CYAN}'>No words yet</h2><p style='color:{theme.DIM}'>Click a word in the "
                                "subtitles, then ☆ Save. The word, its meaning, the sentence and the exact video moment are kept.</p>")

    def current(self):
        r = self.list.currentRow()
        return self.words[r] if 0 <= r < len(self.words) else None

    def show_word(self, *_):
        w = self.current()
        if not w:
            return
        h = [f"<h1 style='margin-bottom:0'>{article_html(w)}{html.escape(w.text)}</h1>"]
        if w.lemma and w.lemma.lower() != w.text.lower():
            h.append(f"<p style='color:{theme.DIM}'>→ {html.escape(w.lemma)}</p>")
        if w.ipa:
            h.append(f"<p style='font-family:serif'>{html.escape(w.ipa)}</p>")
        if w.english:
            h.append(f"<p>{html.escape(w.english)}</p>")
        if w.persian:
            h.append(f"<p dir='rtl' style='font-size:14pt'>{html.escape(w.persian)}</p>")
        acc = f"{w.correct * 100 // w.reviews}%" if w.reviews else "–"
        h.append(f"<p style='color:{theme.DIM}'>Reviewed {w.reviews}× · right {acc} · next {due_label(w.due, now_ms())}"
                 f" · from “{html.escape(w.video_name)}”</p>")
        h.append(f"<p style='color:{theme.CYAN};font-weight:700;margin-top:14px'>SENTENCES</p>")
        if w.sentence:
            h.append(f"<p>🎬 {highlight(w.sentence, w.text)}</p>")
        for e in self.main.store.examples(w.id):
            h.append(f"<p style='margin-bottom:0'>{highlight(e.de, w.text)} "
                     f"<a href='say:{e.id}' style='color:{theme.CYAN};text-decoration:none'>🔊</a> "
                     f"<a href='del:{e.id}' style='color:{theme.DIM};text-decoration:none'>✕</a></p>")
            if e.en:
                h.append(f"<p style='color:{theme.DIM};margin:0'>{html.escape(e.en)}</p>")
            if e.fa:
                h.append(f"<p dir='rtl' style='color:{theme.DIM};margin:0 0 6px 0'>{html.escape(e.fa)}</p>")
        self.detail.setHtml("".join(h))

    def _link(self, url):
        kind, _, val = url.toString().partition(":")
        w = self.current()
        if not w:
            return
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
        v.addStretch(1)
        self.head = QLabel("", objectName="hint", alignment=Qt.AlignCenter)
        v.addWidget(self.head)
        self.box = card()
        bv = QVBoxLayout(self.box)
        self.view = QTextBrowser(openLinks=False)
        self.view.setMinimumHeight(330)
        bv.addWidget(self.view)
        row = QHBoxLayout()
        self.b_play = QPushButton("▶ Play the moment")
        self.b_play.clicked.connect(self.play)
        self.b_speak = QPushButton("🔊 Speak")
        self.b_speak.clicked.connect(lambda: self.cur and self.main.speak(self.sent[0] if self.sent else self.cur.text, lang=self.cur.lang))
        self.b_reveal = QPushButton("Show meaning (Space)")
        self.b_reveal.setProperty("accent", True)
        self.b_reveal.clicked.connect(self.reveal)
        self.b_again = QPushButton("↺ Again — 10 min")
        self.b_again.clicked.connect(lambda: self.answer(False))
        self.b_got = QPushButton("✓ Got it")
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
                h.append(f"<p style='text-align:center;font-family:serif'>{html.escape(w.ipa)}</p>")
            if w.english:
                h.append(f"<p style='text-align:center'>{html.escape(w.english)}</p>")
            if w.persian:
                h.append(f"<p dir='rtl' style='text-align:center;font-size:15pt'>{html.escape(w.persian)}</p>")
            if self.sent and (self.sent[1] or self.sent[2]):
                h.append(f"<p style='text-align:center;color:{theme.DIM}'>{html.escape(self.sent[1])}</p>"
                         f"<p dir='rtl' style='text-align:center;color:{theme.DIM}'>{html.escape(self.sent[2])}</p>")
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
        top.addWidget(QLabel("Practice", objectName="title"))
        top.addStretch(1)
        self.modes = {}
        for key, label in (("gap", "Fill the gap"), ("dictation", "Dictation"), ("article", "der · die · das")):
            b = QPushButton(label, checkable=True)
            b.clicked.connect(lambda _=False, k=key: self.start(k))
            self.modes[key] = b
            top.addWidget(b)
        v.addLayout(top)
        self.head = QLabel("", objectName="hint")
        v.addWidget(self.head)
        self.box = card()
        bv = QVBoxLayout(self.box)
        self.view = QTextBrowser(openLinks=False)
        self.view.setMinimumHeight(260)
        bv.addWidget(self.view)
        self.choice_row = QHBoxLayout()
        bv.addLayout(self.choice_row)
        self.input = QLineEdit(placeholderText="Type your answer and press Enter")
        self.input.returnPressed.connect(self.check_typed)
        bv.addWidget(self.input)
        row = QHBoxLayout()
        self.b_play = QPushButton("▶ Listen")
        self.b_play.clicked.connect(self.listen)
        self.b_hint = QPushButton("Hint")
        self.b_hint.clicked.connect(self.hint)
        self.b_next = QPushButton("Next →")
        self.b_next.setProperty("accent", True)
        self.b_next.clicked.connect(self.next)
        for b in (self.b_play, self.b_hint, self.b_next):
            row.addWidget(b)
        bv.addLayout(row)
        v.addWidget(self.box, 1)
        self.mode, self.qs, self.k, self.score, self.answered, self.show_hint = "gap", [], 0, 0, False, False
        self.rnd = random.Random()

    def start(self, mode=None):
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

    def _clear_choices(self):
        while self.choice_row.count():
            it = self.choice_row.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def show_q(self):
        self._clear_choices()
        self.answered = self.show_hint = False
        self.input.clear()
        if self.k >= len(self.qs):
            empty = not self.qs
            msg = {"gap": "Save words (and add sentences) to practise them here.",
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
        self.head.setText(f"Question {self.k + 1} of {len(self.qs)} · score {self.score}")
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
                      f"<p dir='rtl' style='text-align:center;color:{theme.DIM}'>{html.escape(c.fa)}</p>")
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
