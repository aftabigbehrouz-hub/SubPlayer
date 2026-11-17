"""Study one video: every word of its text by level, the words you saved from it, and practice with its whole text."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPlainTextEdit, QPushButton, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget)

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
                                         ("puzzle", " Practise its whole text"), ("sparkles", " AI lesson"))):
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

        # 3 — AI lesson: a text at my level + exercises from the whole video, and the place to keep the answer
        from . import lessons
        p3 = QWidget(objectName="clear")
        v3 = QVBoxLayout(p3)
        v3.setContentsMargins(0, 8, 0, 0)
        v3.setSpacing(8)
        h3 = QLabel("<b>1.</b> Choose a level — or the exam: TestDaF for a German video, IELTS for an English one. &nbsp;<b>2.</b> Send the ready question (with the whole text of the video) to an assistant — or let Ollama on this PC write it: "
                    "it writes a text at that level, the key words, the structures, exercises and the answers. &nbsp;<b>3.</b> Copy the "
                    "answer and paste it here — it is kept with the video for practice.", objectName="hint")
        h3.setWordWrap(True)
        v3.addWidget(h3)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Level", objectName="small"))
        self.ai_lv = {}
        for x in lessons.ALL:
            if x in lessons.EXAMS:
                r1.addSpacing(6) if x == lessons.EXAMS[0] else None
            b = QPushButton(x, checkable=True)
            b.setProperty("kind", "chip")
            b.setToolTip({"TestDaF": "A TestDaF practice set on the whole video (German videos)",
                          "IELTS": "An IELTS Academic practice set on the whole video (English videos)"}.get(x, f"A text at {x} with exercises"))
            b.clicked.connect(lambda _=False, y=x: self._ai_level(y))
            self.ai_lv[x] = b
            r1.addWidget(b)
        r1.addSpacing(14)
        r1.addWidget(QLabel("Explanations in", objectName="small"))
        self.ai_explain = QComboBox()
        for k, label in (("en", "English"), ("fa", "فارسی"), ("de", "Deutsch")):
            self.ai_explain.addItem(label, k)
        self.ai_explain.setCurrentIndex(max(0, self.ai_explain.findData(main.settings.get("lesson_explain", "en"))))
        self.ai_explain.currentIndexChanged.connect(self._ai_explain_changed)
        r1.addWidget(self.ai_explain)
        r1.addStretch(1)
        v3.addLayout(r1)
        r2 = QHBoxLayout()
        for key, col in (("chatgpt", theme.CYAN), ("gemini", theme.GOLD), ("deepseek", theme.MINT), ("grok", theme.MAGENTA)):
            b = ibtn("sparkles", f"Copy the question and open {lessons.ASSISTANTS[key][0]}", lambda _=False, k=key: self._ai_ask(k),
                     kind="", text=" " + lessons.ASSISTANTS[key][0], size=15, color=col)
            r2.addWidget(b)
        self.ai_local = ibtn("study", "Your AI teacher on this PC (Ollama) writes the lesson straight into the box — free and offline",
                             self._ai_local, kind="", text=" Ollama (this PC)", size=15, color=theme.MINT)
        r2.addWidget(self.ai_local)
        b = ibtn("copy", "Only copy the question (for any other assistant)", lambda: self._ai_ask(""), kind="", text=" Copy question", size=15)
        r2.addWidget(b)
        r2.addStretch(1)
        v3.addLayout(r2)
        self.ai_text = QPlainTextEdit(placeholderText="Paste the assistant's answer here (Ctrl+V) — the text, word list, structures, "
                                                      "exercises and answers. It is saved by itself, one lesson per level.")
        self.ai_text.textChanged.connect(self._ai_changed)
        v3.addWidget(self.ai_text, 1)
        r3 = QHBoxLayout()
        self.ai_state = QLabel("", objectName="small")
        r3.addWidget(self.ai_state, 1)
        for ic, label, tip, fn in (("paste", " Paste", "Put the copied answer here (replaces what is here if it is empty, otherwise adds it below)", self._ai_paste),
                                   ("eye", " Hide answers", "Hide / show everything after ---LÖSUNGEN--- so you can test yourself", self._ai_toggle_answers),
                                   ("copy", " Copy", "Copy this lesson", lambda: (QApplication.clipboard().setText(self._ai_full()), main.msg("Lesson copied"))),
                                   ("download", " Save as file…", "Save this lesson as a text file (to print or keep elsewhere)", self._ai_export),
                                   ("trash", " Delete", "Delete this level's lesson", self._ai_delete)):
            b = ibtn(ic, tip, fn, kind="", text=label, size=15)
            if ic == "eye":
                b.setCheckable(True)
                self.ai_hide = b
            r3.addWidget(b)
        v3.addLayout(r3)
        self.stack.addWidget(p3)
        self._ai_level_name, self._ai_loading, self._ai_hidden = "B1", False, ""
        from PySide6.QtCore import QTimer
        self._ai_timer = QTimer(self, singleShot=True, interval=700)
        self._ai_timer.timeout.connect(self._ai_save)
        root.addWidget(left, 3)

        right = QFrame(objectName="card")
        self.right = right
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
        self._ai_save()                                # the lesson being typed belongs to the video shown until now
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
            f" · you saved {len(mine)}" + (" · <span style='color:#7F7A9E'>German levels: word list where listed, else estimated</span>" if lang == "de" else ""))
        self._fill_vocab()
        self._fill_saved()
        self.detail.setHtml(f"<p style='font-size:17pt;font-weight:800;color:{theme.CYAN}'>Pick a word</p>"
                            f"<p style='color:{theme.DIM}'>Words of this video, most frequent first. Filter by level to find the ones "
                            "worth learning, save them with the moment they are said, and practise with the whole text.</p>")
        if self.stack.currentIndex() == 3:
            self._ai_level(self.main.settings.get("lesson_level", "B1"))

    def _saved(self) -> list[SavedWord]:
        return [w for w in self.main.store.all() if (self.video and w.video_uri == self.video) or
                (w.video_name and w.video_name.lower() == self.name.lower())]

    def tab(self, i: int):
        self._ai_save()
        self.stack.setCurrentIndex(i)
        for k, b in enumerate(self.tab_btns):
            b.setChecked(k == i)
        self.right.setVisible(i != 3)                 # the lesson gets the whole width
        if i == 3:
            self._ai_level(self.main.settings.get("lesson_level", "B1"))

    # ------------------------------------------------------------------ AI lesson
    def _ai_level(self, lv: str):
        from . import lessons
        r = getattr(self, "_ai_runner", None)
        if r and r.busy:                                     # Ollama is still writing the current level: keep it there
            for k, b in self.ai_lv.items():
                b.setChecked(k == self._ai_level_name)
            self.main.msg("Ollama is still writing this lesson — wait, or press Stop first")
            return
        self._ai_save()
        if lv not in lessons.ALL:
            lv = "B1"
        if lv in lessons.EXAMS and lv != lessons.exam_for(self.lang):
            lv = lessons.exam_for(self.lang)                 # TestDaF for German videos, IELTS for English ones
        for x in lessons.EXAMS:
            self.ai_lv[x].setVisible(x == lessons.exam_for(self.lang))
        self._ai_level_name = lv
        self.main.settings["lesson_level"] = lv
        self.main.save_settings()
        have = lessons.kept(self.name) if self.name else []
        for k, b in self.ai_lv.items():
            b.setChecked(k == lv)
            b.setText(k + (" ●" if k in have else ""))
            b.setToolTip("A lesson is kept for this level" if k in have else "No lesson kept yet")
        self._ai_loading = True
        self._ai_hidden = ""
        self.ai_hide.setChecked(False)
        self.ai_hide.setText(" Hide answers")
        self.ai_text.setPlainText(lessons.text(self.name, lv) if self.name else "")
        self._ai_loading = False
        self._ai_note()

    def _ai_note(self, saved: bool = False):
        n = len(self._ai_full().split())
        self.ai_state.setText((f"{self._ai_level_name} lesson · {n} words · " + ("saved ✓" if saved else "kept with this video")) if n else
                              f"No {self._ai_level_name} lesson yet for this video")

    def _ai_explain_changed(self, *_):
        self.main.settings["lesson_explain"] = self.ai_explain.currentData()
        self.main.save_settings()

    def _ai_prompt(self) -> str:
        from . import lessons
        mine = [(w.lemma or w.text) for w in self._saved()]
        return lessons.prompt(self._ai_level_name, self.lang, self.name, self.cues, mine, self.ai_explain.currentData(),
                              self._exam_words())

    def _exam_words(self, limit: int = 60) -> list[str]:
        """The video's words of level B2 and above, most frequent first (the base words, as the word lists know them)."""
        out = []
        for w, n, lv in (getattr(self, "vocab", None) or []):
            if lv >= 4 and len(w) > 3:
                out.append(w)
                if len(out) >= limit:
                    break
        return out

    def _ai_ask(self, source: str):
        if not self.cues:
            self.main.msg("This video has no subtitles yet")
            return
        q = self._ai_prompt()
        if source:
            self.main.ask_ai(source, q, "When the answer is there, copy it and press Paste here.")
        else:
            QApplication.clipboard().setText(q)
            self.main.msg(f"Question for a {self._ai_level_name} lesson copied ({len(q):,} characters) — paste it into any assistant", 9000)

    def _ai_local(self):
        """Writes the lesson with Ollama on this PC, piece by piece into the box (Stop: press the button again)."""
        from . import ollama
        from .teacher import Runner, client
        if getattr(self, "_ai_runner", None) and self._ai_runner.busy:
            self._ai_runner.stop = True
            return
        if not self.cues:
            self.main.msg("This video has no subtitles yet")
            return
        if not self.main.ensure_teacher():                          # opens the set-up first
            return
        if self._ai_full().strip():
            from PySide6.QtWidgets import QMessageBox
            if QMessageBox.question(self, "AI lesson", f"Replace the {self._ai_level_name} lesson in the box with a new one from Ollama?") != QMessageBox.Yes:
                return
        q = self._ai_prompt()
        c = client(self.main)
        self._ai_runner = r = Runner(self)
        self._ai_loading, self._ai_hidden = True, ""
        self.ai_text.setPlainText("")
        self._ai_loading = False
        self.ai_local.setText(" Stop")
        self.ai_state.setText(f"Ollama ({c.model}) is writing the {self._ai_level_name} lesson… the first words can take a minute; "
                              "long videos take several minutes")

        def piece(t):
            self._ai_loading = True
            cur = self.ai_text.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(t)
            self._ai_loading = False

        def finish(_=""):
            self.ai_local.setText(" Ollama (this PC)")
            self._ai_save()
            self._ai_note(saved=True)

        def fail(m):
            self.ai_local.setText(" Ollama (this PC)")
            self.ai_state.setText("⚠ " + m)
            if self._ai_full().strip():
                self._ai_save()
        r.text.connect(piece)
        r.done.connect(finish)
        r.failed.connect(fail)
        r.run(lambda on, stop: c.chat(q, "", on_text=on, cancelled=stop, ctx=ollama.lesson_ctx(q), temperature=0.6))

    def _ai_full(self) -> str:
        return self.ai_text.toPlainText() + self._ai_hidden

    def _ai_changed(self):
        if not self._ai_loading:
            self._ai_timer.start()

    def _ai_save(self):
        from . import lessons
        self._ai_timer.stop()
        if not self.name or self._ai_loading:
            return
        body = self._ai_full()
        if body != lessons.text(self.name, self._ai_level_name):
            lessons.save(self.name, self.lang, self._ai_level_name, body)
            have = lessons.kept(self.name)
            for k, b in self.ai_lv.items():
                b.setText(k + (" ●" if k in have else ""))
            self._ai_note(saved=True)

    def _ai_paste(self):
        t = QApplication.clipboard().text().strip()
        if not t:
            self.main.msg("Nothing copied yet — copy the assistant's answer first")
            return
        if t.startswith("You are an experienced") and "TRANSCRIPT" in t:
            self.main.msg("That is still the question — copy the assistant's ANSWER, then press Paste", 9000)
            return
        cur = self.ai_text.toPlainText().strip()
        self.ai_text.setPlainText(t if not cur else cur + "\n\n" + "─" * 30 + "\n\n" + t)
        self._ai_save()

    _ANSWERS = ("---LÖSUNGEN---", "---ANSWERS---", "LÖSUNGEN", "ANSWERS", "Lösungen", "Answers")

    def _ai_toggle_answers(self):
        if self.ai_hide.isChecked():
            body = self.ai_text.toPlainText()
            cut = -1
            for mark in self._ANSWERS:
                cut = body.rfind(mark)
                if cut > len(body) // 3:
                    break
                cut = -1
            if cut < 0:
                self.ai_hide.setChecked(False)
                self.main.msg("No answer part found (a line with LÖSUNGEN or ANSWERS)")
                return
            self._ai_save()
            self._ai_loading = True
            self._ai_hidden = body[cut:]
            self.ai_text.setPlainText(body[:cut])
            self._ai_loading = False
            self.ai_hide.setText(" Show answers")
        else:
            self._ai_loading = True
            self.ai_text.setPlainText(self._ai_full())
            self._ai_hidden = ""
            self._ai_loading = False
            self.ai_hide.setText(" Hide answers")

    def _ai_export(self):
        from pathlib import Path
        from PySide6.QtWidgets import QFileDialog
        body = self._ai_full()
        if not body.strip():
            self.main.msg("Nothing to save yet")
            return
        f, _ = QFileDialog.getSaveFileName(self, "Save the lesson", f"{Path(self.name).stem} - {self._ai_level_name} lesson.txt", "Text (*.txt)")
        if f:
            Path(f).write_text(f"{Path(self.name).stem} — {self._ai_level_name}\n\n{body}\n", encoding="utf-8-sig")
            self.main.msg("Lesson saved as a file")

    def _ai_delete(self):
        from . import lessons
        if not self._ai_full().strip():
            return
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(self, "Delete lesson", f"Delete the {self._ai_level_name} lesson of this video?") != QMessageBox.Yes:
            return
        lessons.save(self.name, self.lang, self._ai_level_name, "")
        self._ai_level(self._ai_level_name)

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
