"""
Notebook: every answer of the teacher (the line explained, your questions, checked sentences and texts, A1 → C1) is kept
here, to read again and to review: the question comes first, you think of the answer, then Show answer, Got it / Again —
spaced like the words (1 → 2 → 4 → 7 → 15 → 30 → 60 days).
"""
from __future__ import annotations

import html
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QSplitter, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget)

from . import store as st
from . import theme

KINDS = (("", "All answers"), ("line", "Explain the line"), ("ask", "My questions"), ("check", "My sentences checked"),
         ("writing", "My texts (writing)"), ("levels", "A1 → C1"))
KIND_NAME = dict(KINDS)


class NotebookDialog(QDialog):
    def __init__(self, main, review_first: bool = False):
        super().__init__(main)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint |
                            Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.main = main
        self.setWindowTitle("Notebook — the teacher's answers")
        self.resize(1000, 680)
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 16, 22, 16)
        head = QHBoxLayout()
        head.addWidget(QLabel(f"<span style='font-size:19pt;font-weight:700;color:{theme.CYAN}'>Notebook</span>"
                              f"<span style='color:{theme.DIM}'> &nbsp;· every answer of the teacher, kept to read and review</span>"), 1)
        self.review_b = QPushButton("")
        self.review_b.setProperty("accent", True)
        self.review_b.clicked.connect(self.start_review)
        head.addWidget(self.review_b)
        v.addLayout(head)
        self.stack = QStackedWidget()
        v.addWidget(self.stack, 1)

        # ---- 0: the list and the reader
        page = QWidget(objectName="clear")
        pv = QVBoxLayout(page)
        pv.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.search = QLineEdit(placeholderText="Search the questions and answers …")
        self.search.textChanged.connect(self.refresh)
        row.addWidget(self.search, 1)
        self.kind = QComboBox()
        for k, label in KINDS:
            self.kind.addItem(label, k)
        self.kind.currentIndexChanged.connect(self.refresh)
        row.addWidget(self.kind)
        pv.addLayout(row)
        split = QSplitter()
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.show_note)
        split.addWidget(self.list)
        right = QWidget(objectName="clear")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.reader = QTextBrowser(openLinks=False)
        self.reader.anchorClicked.connect(self._link)
        rv.addWidget(self.reader, 1)
        tools = QHBoxLayout()
        self.info = QLabel("", objectName="small")
        tools.addWidget(self.info, 1)
        self.star_b = QPushButton("☆ Star")
        self.star_b.clicked.connect(self.toggle_star)
        tools.addWidget(self.star_b)
        self.say_b = QPushButton("🔊 Read the question")
        self.say_b.clicked.connect(lambda: self.cur and self.main.speak(self.cur.title, lang=self.cur.lang))
        tools.addWidget(self.say_b)
        self.del_b = QPushButton("Delete")
        self.del_b.clicked.connect(self.delete)
        tools.addWidget(self.del_b)
        rv.addLayout(tools)
        split.addWidget(right)
        split.setSizes([330, 650])
        pv.addWidget(split, 1)
        self.stack.addWidget(page)

        # ---- 1: review
        rp = QWidget(objectName="clear")
        rl = QVBoxLayout(rp)
        rl.setContentsMargins(0, 0, 0, 0)
        self.r_head = QLabel("", objectName="small")
        rl.addWidget(self.r_head)
        self.r_q = QLabel("")
        self.r_q.setWordWrap(True)
        self.r_q.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        rl.addWidget(self.r_q)
        self.r_hint = QLabel("Think of the answer first — say it aloud or write it down — then press Show answer.", objectName="small")
        rl.addWidget(self.r_hint)
        self.r_body = QTextBrowser(openLinks=False)
        self.r_body.anchorClicked.connect(self._link)
        rl.addWidget(self.r_body, 1)
        bar = QHBoxLayout()
        back = QPushButton("← Back to the list")
        back.clicked.connect(self.end_review)
        bar.addWidget(back)
        bar.addStretch(1)
        self.show_b = QPushButton("Show answer")
        self.show_b.setProperty("accent", True)
        self.show_b.clicked.connect(self.reveal)
        bar.addWidget(self.show_b)
        self.again_b = QPushButton("Again")
        self.again_b.clicked.connect(lambda: self.grade(False))
        bar.addWidget(self.again_b)
        self.got_b = QPushButton("Got it")
        self.got_b.setProperty("accent", True)
        self.got_b.clicked.connect(lambda: self.grade(True))
        bar.addWidget(self.got_b)
        rl.addLayout(bar)
        self.stack.addWidget(rp)

        self.cur: st.Note | None = None
        self.items: list = []
        self.queue: list = []
        self.refresh()
        if review_first and self.main.store.due_notes(st.now_ms()):
            self.start_review()

    # ------------------------------------------------------------------ list
    def refresh(self, *_):
        self.items = self.main.store.notes(self.search.text(), self.kind.currentData() or "")
        self.items.sort(key=lambda n: (-n.starred, -n.created))
        self.list.blockSignals(True)
        self.list.clear()
        for n in self.items:
            when = time.strftime("%d.%m.%Y", time.localtime(n.created / 1000))
            it = QListWidgetItem(("★ " if n.starred else "") + (n.title[:90] + ("…" if len(n.title) > 90 else "")) +
                                 f"\n{KIND_NAME.get(n.kind, n.kind)} · {when}")
            self.list.addItem(it)
        self.list.blockSignals(False)
        due = len(self.main.store.due_notes(st.now_ms()))
        self.review_b.setText(f"▶ Review {due} due" if due else "Nothing due — review all")
        self.review_b.setEnabled(bool(self.items) or due > 0)
        if self.items:
            self.list.setCurrentRow(0)
        else:
            self.cur = None
            self.reader.setHtml(f"<p style='color:{theme.DIM}'>No saved answers yet. Every answer of the teacher — Explain the "
                                "line, Ask the teacher, Check my sentence, ✍ Writing, A1 → C1 — is kept here by itself.</p>")
            self.info.setText("")

    def show_note(self, row: int):
        self.cur = self.items[row] if 0 <= row < len(self.items) else None
        if not self.cur:
            return
        n = self.cur
        self.reader.setHtml(self._page(n, reveal=True))
        self.star_b.setText("★ Starred" if n.starred else "☆ Star")
        self.info.setText(f"{KIND_NAME.get(n.kind, n.kind)} · from {n.source or 'the teacher'} · reviewed {n.reviews}× · "
                          + st.due_label(n.due, st.now_ms()))

    def _page(self, n: st.Note, reveal: bool) -> str:
        e = html.escape
        top = (f"<p style='color:{theme.DIM};font-size:9.5pt'>{e(KIND_NAME.get(n.kind, n.kind))}"
               + (f" · „{e(n.lemma)}“" if n.lemma else "") + (f" · {e(n.video_name)}" if n.video_name else "") + "</p>"
               f"<p style='font-size:13pt;color:{theme.GOLD};font-weight:600'>{e(n.title)}</p>")
        return top + ("<hr>" + _inner(n.body) if reveal else "")

    def _link(self, url):
        u = url.toString()
        if u.startswith("say:"):
            import urllib.parse
            lang = self.cur.lang if self.cur else "de"
            self.main.speak(urllib.parse.unquote(u[4:]), lang=lang)

    def toggle_star(self):
        if self.cur:
            self.cur.starred = 0 if self.cur.starred else 1
            self.main.store.update_note(self.cur)
            self.refresh()

    def delete(self):
        if self.cur:
            self.main.store.delete_note(self.cur.id)
            self.refresh()

    # ------------------------------------------------------------------ review
    def start_review(self):
        now = st.now_ms()
        self.queue = self.main.store.due_notes(now) or sorted(self.main.store.notes(), key=lambda n: (n.reviews, n.box, n.due))
        if not self.queue:
            return
        self.stack.setCurrentIndex(1)
        self._next()

    def _next(self):
        if not self.queue:
            self.end_review()
            self.main.msg("Notebook review done ✓", 6000)
            return
        n = self.queue[0]
        self.r_head.setText(f"{len(self.queue)} left · {KIND_NAME.get(n.kind, n.kind)}" + (f" · „{n.lemma}“" if n.lemma else ""))
        self.r_q.setText(f"<span style='font-size:15pt;color:{theme.GOLD};font-weight:600'>{html.escape(n.title)}</span>")
        self.r_body.setHtml("")
        self.r_hint.setVisible(True)
        self.show_b.setVisible(True)
        self.again_b.setVisible(False)
        self.got_b.setVisible(False)

    def reveal(self):
        n = self.queue[0]
        self.r_body.setHtml(_inner(n.body))
        self.r_hint.setVisible(False)
        self.show_b.setVisible(False)
        self.again_b.setVisible(True)
        self.got_b.setVisible(True)

    def grade(self, got_it: bool):
        n = self.queue.pop(0)
        m = st.review(n, got_it, st.now_ms())
        self.main.store.update_note(m)
        if not got_it:
            self.queue.append(m)                        # once more at the end of this round
        self._next()

    def end_review(self):
        self.queue = []
        self.stack.setCurrentIndex(0)
        self.refresh()


def _inner(body: str) -> str:
    """The saved HTML of an answer without its own <html>/<body> wrapper (so it can follow the question)."""
    b = body or ""
    lo = b.lower()
    i = lo.find("<body")
    if i >= 0:
        i = lo.find(">", i) + 1
        j = lo.rfind("</body>")
        b = b[i:j if j > i else len(b)]
    return b
