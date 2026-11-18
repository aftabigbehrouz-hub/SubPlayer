"""The local AI teacher window (Ollama): word coach with collocations, the line explained, check my sentence, ask anything."""
from __future__ import annotations

import html
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QStackedWidget, QTextBrowser,
                               QVBoxLayout, QWidget)

from . import ollama, theme
from .store import Example


class Runner(QObject):
    """Runs one Ollama request in a thread; pieces of text, the result and errors come back as Qt signals."""
    text = Signal(str)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stop = False
        self.busy = False

    def run(self, fn):
        self.stop, self.busy = False, True

        def work():
            try:
                try:
                    res = fn(lambda t: self.text.emit(t), lambda: self.stop)
                    self.done.emit(res or "")
                except RuntimeError:
                    raise
                except Exception as e:
                    self.failed.emit(str(e))
            except RuntimeError:
                pass                                       # the window was closed while the answer was coming
            finally:
                self.busy = False
        threading.Thread(target=work, daemon=True).start()


# Where the teacher's answers come from: Ollama on this PC, or an online assistant (the question is copied and the site opens;
# its answer is pasted back with "Paste answer" and shown exactly like Ollama's).
SOURCES = (("ollama", "Ollama (this PC)"), ("chatgpt", "ChatGPT"), ("gemini", "Gemini"), ("deepseek", "DeepSeek"), ("grok", "Grok"),
           ("copy", "Other AI — copy the question"))


def client(main) -> ollama.Client:
    return ollama.Client(main.settings.get("ollama_url", ollama.DEFAULT_URL), main.settings.get("ollama_model", ""))


def level(main) -> str:
    return main.settings.get("teacher_level", "B1")


def explain(main) -> str:
    return main.settings.get("lesson_explain", "en")


class TeacherDialog(QDialog):
    TABS = ("Word && collocations", "Explain the line", "Check my sentence", "Ask the teacher", "{exam} questions")

    def __init__(self, main, word: str, lemma: str, sentence: str, lang: str, saved=None, tab: int = 0):
        super().__init__(main)
        # an ordinary window: it can be minimised or put beside the video, and the video keeps playing
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint |
                            Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.exam = "IELTS" if lang == "en" else "TestDaF"
        self.qs: list = []
        self.main, self.word, self.lemma, self.sentence, self.lang = main, word, lemma or word, sentence, lang
        self.saved = saved                                # SavedWord getter (to add sentences)
        self.result: dict = {}
        self.setWindowTitle(f"Teacher — „{self.lemma}“")
        self.resize(820, 700)
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 16, 22, 16)
        head = QHBoxLayout()
        t = QLabel(f"<span style='font-size:19pt;font-weight:700;color:{theme.CYAN}'>{html.escape(self.lemma)}</span>"
                   f"<span style='color:{theme.DIM}'> &nbsp;· your teacher — Ollama on this PC or an online assistant</span>")
        head.addWidget(t, 1)
        head.addWidget(QLabel("Level", objectName="small"))
        self.lv = QComboBox()
        self.lv.addItems(ollama.LEVELS)
        self.lv.setCurrentText(level(main))
        self.lv.currentTextChanged.connect(self._level_changed)
        head.addWidget(self.lv)
        head.addWidget(QLabel("Explain in", objectName="small"))
        self.ex = QComboBox()
        for k, label in (("en", "English"), ("fa", "فارسی"), ("de", "Deutsch")):
            self.ex.addItem(label, k)
        self.ex.setCurrentIndex(max(0, self.ex.findData(explain(main))))
        self.ex.currentIndexChanged.connect(self._explain_changed)
        head.addWidget(self.ex)
        v.addLayout(head)
        srow = QHBoxLayout()
        srow.addWidget(QLabel("Answer from", objectName="small"))
        self.src = QComboBox()
        for k, label in SOURCES:
            self.src.addItem(label, k)
        default = main.settings.get("teacher_source") or ("ollama" if main.settings.get("ollama_model") else "chatgpt")
        self.src.setCurrentIndex(max(0, self.src.findData(default)))
        self.src.currentIndexChanged.connect(self._source_changed)
        srow.addWidget(self.src)
        self.src_hint = QLabel("", objectName="small")
        srow.addWidget(self.src_hint, 1)
        v.addLayout(srow)
        if sentence:
            s = QLabel(f"<span style='color:{theme.DIM}'>„{html.escape(sentence)}“</span>")
            s.setWordWrap(True)
            v.addWidget(s)
        tabs = QHBoxLayout()
        self.tab_btns = []
        for i, name in enumerate(self.TABS):
            b = QPushButton(name.format(exam=self.exam), checkable=True)
            b.setProperty("kind", "chip")
            b.clicked.connect(lambda _=False, k=i: self.tab(k))
            self.tab_btns.append(b)
            tabs.addWidget(b)
        tabs.addStretch(1)
        v.addLayout(tabs)

        self.stack = QStackedWidget()
        # 0 word coach
        self.view = QTextBrowser(openLinks=False)
        self.view.anchorClicked.connect(lambda u: self.main.speak(u.toString()[4:], self.lang) if u.toString().startswith("say:") else None)
        self.stack.addWidget(self.view)
        # 1 the line explained
        self.view2 = QTextBrowser()
        self.stack.addWidget(self.view2)
        # 2 check my sentence
        p = QWidget(objectName="clear")
        pv = QVBoxLayout(p)
        pv.setContentsMargins(0, 0, 0, 0)
        target = "English" if lang == "en" else "German"
        pv.addWidget(QLabel(f"Write your own {target} sentence with „{self.lemma}“ — the teacher corrects it and explains:", objectName="small"))
        row = QHBoxLayout()
        self.attempt = QLineEdit(placeholderText=f"Your sentence with „{self.lemma}“ …")
        self.attempt.returnPressed.connect(self.check)
        row.addWidget(self.attempt, 1)
        b = QPushButton("Check")
        b.setProperty("accent", True)
        b.clicked.connect(self.check)
        row.addWidget(b)
        pv.addLayout(row)
        self.view3 = QTextBrowser()
        pv.addWidget(self.view3, 1)
        self.stack.addWidget(p)
        # 3 ask
        q = QWidget(objectName="clear")
        qv = QVBoxLayout(q)
        qv.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.question = QLineEdit(placeholderText="Ask anything: “What's the difference to …?”, “Is it formal?”, “Give me a dialogue with it” …")
        self.question.returnPressed.connect(self.ask)
        row.addWidget(self.question, 1)
        b = QPushButton("Ask")
        b.setProperty("accent", True)
        b.clicked.connect(self.ask)
        row.addWidget(b)
        qv.addLayout(row)
        self.view4 = QTextBrowser()
        qv.addWidget(self.view4, 1)
        self.stack.addWidget(q)
        # 4 exam-style questions on the word, which can go into Review
        self.view5 = QTextBrowser(openLinks=False)
        self.view5.anchorClicked.connect(self._q_link)
        self.stack.addWidget(self.view5)
        v.addWidget(self.stack, 1)

        foot = QHBoxLayout()
        self.state = QLabel("", objectName="small")
        foot.addWidget(self.state, 1)
        self.add_b = QPushButton("＋ Add sentences && collocations to my word")
        self.add_b.setToolTip("The sentences appear in review and practice; the collocations in My Words ▸ Collocations")
        self.add_b.clicked.connect(self.add_examples)
        self.addq_b = QPushButton("＋ Add the questions to Review")
        self.addq_b.setToolTip("They come back in Review like your words — answer, then Got it / Again")
        self.addq_b.clicked.connect(self.add_questions)
        self.addq_b.setEnabled(False)
        foot.addWidget(self.addq_b)
        self.manual_b = QPushButton("✎ Add my own…")
        self.manual_b.setToolTip("Write meanings, collocations and sentences yourself (Word tab), or your own exam question (TestDaF tab)")
        self.manual_b.clicked.connect(self.manual)
        foot.addWidget(self.manual_b)
        self.ask_b = QPushButton("➜ Ask")
        self.ask_b.setToolTip("Copy this tab's question and open the assistant")
        self.ask_b.clicked.connect(self.ask_online)
        foot.addWidget(self.ask_b)
        self.paste_b = QPushButton("📋 Paste answer")
        self.paste_b.setProperty("accent", True)
        self.paste_b.setToolTip("Copy the assistant's whole answer, then press this — it is shown here like Ollama's")
        self.paste_b.clicked.connect(self.paste_answer)
        foot.addWidget(self.paste_b)
        self.add_b.setEnabled(False)
        foot.addWidget(self.add_b)
        self.again_b = QPushButton("New answer")
        self.again_b.setToolTip("Ask the teacher again (other sentences and collocations)")
        self.again_b.clicked.connect(self.again)
        foot.addWidget(self.again_b)
        self.stop_b = QPushButton("Stop")
        self.stop_b.clicked.connect(lambda: setattr(self.runner, "stop", True))
        foot.addWidget(self.stop_b)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        foot.addWidget(close)
        v.addLayout(foot)

        self.runner = Runner(self)
        self._gen, self._run_gen = 0, -1               # answers of an Ollama request made before the source changed are ignored
        self.runner.text.connect(lambda t: self._piece(t) if self._run_gen == self._gen else None)
        self.runner.done.connect(lambda r: self._done(r) if self._run_gen == self._gen else None)
        self.runner.failed.connect(lambda m: self._failed(m) if self._run_gen == self._gen else None)
        self._target_view, self._buf, self._mode = None, "", ""
        self.cache = ollama.Cache()
        self._source_changed()
        self.tab(tab)

    # ------------------------------------------------------------------ source: Ollama or an online assistant
    def source(self) -> str:
        return self.src.currentData() or "ollama"

    def _source_changed(self, *_):
        k = self.source()
        self.main.settings["teacher_source"] = k
        self.main.save_settings()
        online = k != "ollama"
        self._gen += 1                                  # whatever Ollama is still writing is dropped
        if getattr(self, "runner", None) and self.runner.busy:
            self.runner.stop = True
        self.paste_b.setVisible(online)
        self.ask_b.setVisible(online)
        self.ask_b.setText("➜ Ask " + dict(SOURCES)[k].split(" —")[0] if k != "copy" else "➜ Copy the question")
        self.stop_b.setVisible(not online)
        if hasattr(self, "stack"):
            self.state.setText("")
            v = self._tab_view(self.stack.currentIndex())
            if online and v is not None:
                v.setHtml(self._ask_hint())
        self.src_hint.setText("" if not online else
                              "The question is copied and the site opens — paste it there (Ctrl+V) if it isn't filled in, "
                              "then copy the whole answer and press 📋 Paste answer.")

    def _tab_view(self, i: int):
        return {0: self.view, 1: self.view2, 2: self.view3, 3: self.view4, 4: self.view5}.get(i)

    def _ask_hint(self) -> str:
        name = dict(SOURCES)[self.source()].split(" —")[0]
        how = {2: "Write your sentence above first. ", 3: "Write your question above first. "}.get(self.stack.currentIndex(), "")
        return (f"<p style='color:{theme.DIM}'>{how}Press <b style='color:{theme.CYAN}'>➜ Ask</b> below: the question is copied"
                + ("" if self.source() == "copy" else f" and {html.escape(name)} opens")
                + f". Then copy the whole answer and press <b style='color:{theme.CYAN}'>📋 Paste answer</b>.</p>")

    def ask_online(self):
        i = self.stack.currentIndex()
        if i == 0:
            self.coach(fresh=True)
        elif i == 1:
            self.explain_line()
        elif i == 2:
            self.check()
        elif i == 3:
            self.ask()
        else:
            self.exam_questions(fresh=True)

    def _model_tag(self) -> str:
        return self.main.settings.get("ollama_model", "") if self.source() == "ollama" else self.source()

    def manual(self):
        from .dialogs import QuestionDialog, WordEditDialog
        if self.stack.currentIndex() == 4:
            from pathlib import Path
            video = Path(self.main.video).name if getattr(self.main, "video", "") else ""
            if QuestionDialog(self, self.main, self.lang, self.lemma, video).exec():
                self.state.setText("Your question was added to Review ✓")
            return
        w = self.saved() if self.saved else None
        if not w:
            self.state.setText("Save the word first (☆ Save on the word card)")
            return
        WordEditDialog(self, self.main, w).exec()

    def paste_answer(self):
        from PySide6.QtWidgets import QApplication
        from . import practice
        t = practice.clean_ai(QApplication.clipboard().text())     # &#x20; and line-end backslashes of some copy buttons
        if not t:
            self.state.setText("Nothing copied yet — copy the assistant's whole answer first")
            return
        if t == getattr(self, "_asked", ""):
            self.state.setText("That is still the question — copy the assistant's ANSWER, then press 📋 Paste answer")
            return
        i = self.stack.currentIndex()                 # the answer belongs to the tab that is open
        self._target_view, self._mode = {0: (self.view, "word"), 1: (self.view2, "text"), 2: (self.view3, "check"),
                                         3: (self.view4, "text"), 4: (self.view5, "exam")}[i]
        self._run_gen = self._gen
        if self._mode == "text":
            self._target_view.setPlainText(t)
        self._done(t)

    # ------------------------------------------------------------------ helpers
    def _level_changed(self, lv):
        self.main.settings["teacher_level"] = lv
        self.main.save_settings()
        if self.stack.currentIndex() == 0:
            self.coach()

    def _explain_changed(self, *_):
        self.main.settings["lesson_explain"] = self.ex.currentData()
        self.main.save_settings()
        if self.stack.currentIndex() == 0:
            self.coach()

    def tab(self, i: int):
        for k, b in enumerate(self.tab_btns):
            b.setChecked(k == i)
        self.stack.setCurrentIndex(i)
        self.add_b.setVisible(i == 0)
        self.addq_b.setVisible(i == 4)
        self.manual_b.setVisible(i in (0, 4))
        self.manual_b.setText("✎ Write a question…" if i == 4 else "✎ Add my own…")
        self.again_b.setVisible(i in (0, 1, 4))
        if self.source() != "ollama":                  # online: nothing is asked by itself — ➜ Ask does it
            if i == 0 and not self.result:
                hit = self.cache.get(self._ckey())
                self.show_word(hit) if hit else self.view.setHtml(self._ask_hint())
            elif i == 4 and not self.qs:
                hit = self.cache.get(self._ckey() + "|exam")
                self.show_questions(hit) if hit else self.view5.setHtml(self._ask_hint())
            elif i == 1 and not self.view2.toPlainText():
                self.view2.setHtml(self._ask_hint())
            elif i == 2:
                self.attempt.setFocus()
            elif i == 3:
                self.question.setFocus()
            return
        if i == 0 and not self.result:
            self.coach()
        elif i == 1 and not self.view2.toPlainText():
            self.explain_line()
        elif i == 4 and not self.qs:
            self.exam_questions()
        elif i == 2:
            self.attempt.setFocus()
        elif i == 3:
            self.question.setFocus()

    def _start(self, view, mode: str, fn, waiting: str, q: str = "", sys_: str = ""):
        if self.source() != "ollama":                      # an online assistant: the question goes there, the answer is pasted
            from . import lessons
            from PySide6.QtWidgets import QApplication
            self._target_view, self._buf, self._mode = view, "", mode
            full = (sys_ + "\n\n" + q).strip()
            self._asked = full
            src = self.source()
            name = dict(SOURCES)[src].split(" —")[0]
            if src == "copy":
                QApplication.clipboard().setText(full)
            else:
                self.main.ask_ai(src, full, "Copy its whole answer, then press 📋 Paste answer in the teacher.")
            view.setHtml(f"<p style='color:{theme.DIM}'>The question is copied" + ("" if src == "copy" else f" and {html.escape(name)} opens")
                         + ". Paste it there (Ctrl+V) if it isn't filled in. When the answer is complete, copy all of it and press "
                         f"<b style='color:{theme.CYAN}'>📋 Paste answer</b>.</p>")
            self.state.setText(f"Waiting for {name}'s answer…")
            return
        if not self.main.settings.get("ollama_model"):
            ok = self.main.ensure_teacher()
            self.state.setText("Ollama is ready — press the button again" if ok else
                               "No Ollama model — choose ChatGPT, Gemini, DeepSeek or Grok under “Answer from”")
            return
        if self.runner.busy:
            self.state.setText("The teacher is still answering — press Stop first")
            return
        self._run_gen = self._gen
        self._target_view, self._buf, self._mode = view, "", mode
        view.setHtml(f"<p style='color:{theme.DIM}'>{waiting}</p>")
        self.state.setText("The teacher is thinking… (the first answer after starting the PC can take a minute while the model loads)")
        self.stop_b.setEnabled(True)
        self.runner.run(fn)

    def _piece(self, t: str):
        self._buf += t
        if self._mode == "text":
            self._target_view.setPlainText(self._buf)
            self._target_view.verticalScrollBar().setValue(self._target_view.verticalScrollBar().maximum())
        else:
            self.state.setText(f"Writing… {len(self._buf):,} characters")

    def _failed(self, msg: str):
        self.stop_b.setEnabled(False)
        self.state.setText("")
        self._target_view.setHtml(f"<p style='color:{theme.MAGENTA}'>{html.escape(msg)}</p>"
                                  f"<p style='color:{theme.DIM}'>Settings ▸ Local AI teacher (Ollama) shows how to set it up.</p>")

    def _done(self, res: str):
        self.stop_b.setEnabled(False)
        self.state.setText("Done · answers from a local model can contain mistakes — trust the dictionary for the meaning")
        if self._mode == "word":
            d = ollama.parse_json(res) or word_from_text(res, self.lang)
            if not d:
                self._target_view.setPlainText(res or "The model gave no answer.")
                return
            self.cache.put(self._ckey(), d)
            self.show_word(d)
        elif self._mode == "exam":
            d = ollama.parse_json(res) or exam_from_text(res, self.lang)
            if not d:
                self._target_view.setPlainText(res or "The model gave no answer.")
                return
            self.cache.put(self._ckey() + "|exam", d)
            self.show_questions(d)
        elif self._mode == "check":
            self.show_check(ollama.parse_json(res), res)
        if self.source() != "ollama":
            self.state.setText("Answer pasted · answers from AI can contain mistakes — trust the dictionary for the meaning")

    # ------------------------------------------------------------------ 0 word coach
    def _ckey(self):
        return ollama.Cache.key(self._model_tag(), self.lang, self.lemma, self.lv.currentText(), self.ex.currentData())

    def coach(self, fresh: bool = False):
        self.add_b.setEnabled(False)
        hit = None if fresh else self.cache.get(self._ckey())
        if hit:
            self.show_word(hit)
            self.state.setText("From your earlier question · New answer asks again")
            return
        c = client(self.main)
        sys_ = ollama._teacher(self.lang, self.ex.currentData())
        q = ollama.word_prompt(self.word, self.lemma, self.sentence, self.lang, self.lv.currentText(), self.ex.currentData())
        self._start(self.view, "word", lambda on, stop: c.chat(q, sys_, json_mode=True, on_text=on, cancelled=stop,
                                                                temperature=0.8 if fresh else 0.5),
                    "Your teacher is preparing the meaning, collocations and example sentences…", q, sys_)

    def show_word(self, d: dict):
        self.result = d
        e = html.escape
        rtl = self.ex.currentData() == "fa"
        expl = (lambda s: f"<span dir='rtl'>{e(s)}</span>") if rtl else e
        h = [f"<div style='font-size:11pt;line-height:150%'>"]
        if d.get("meaning"):
            h.append(f"<p style='font-size:12.5pt'>{expl(str(d['meaning']))}</p>")
        if d.get("forms"):
            h.append(f"<p><span style='color:{theme.DIM}'>Forms: </span>{e(str(d['forms']))}</p>")
        if d.get("grammar"):
            h.append(f"<p><span style='color:{theme.DIM}'>Grammar: </span><b style='color:{theme.GOLD}'>{e(str(d['grammar']))}</b></p>")
        cols = [c for c in ollama.as_list(d.get("collocations")) if c]
        if cols:
            h.append(f"<p style='color:{theme.CYAN};font-weight:700;letter-spacing:1px;margin-top:14px'>COLLOCATIONS</p><table cellspacing=0 cellpadding=3>")
            for c in cols:
                if isinstance(c, dict):
                    h.append(f"<tr><td style='color:{theme.GOLD};font-weight:600;padding-right:14px'>{e(str(c.get('phrase', '')))}</td>"
                             f"<td>{expl(str(c.get('meaning', '')))}</td></tr>")
                    if c.get("example"):
                        h.append(f"<tr><td></td><td style='color:{theme.DIM};font-style:italic'>{e(str(c['example']))}</td></tr>")
                else:
                    h.append(f"<tr><td colspan=2>{e(str(c))}</td></tr>")
            h.append("</table>")
        exs = [x for x in ollama.as_list(d.get("examples")) if x]
        if exs:
            h.append(f"<p style='color:{theme.CYAN};font-weight:700;letter-spacing:1px;margin-top:14px'>EXAMPLE SENTENCES · {self.lv.currentText()}</p>")
            for x in exs:
                s, tr = (x.get("sentence", ""), x.get("translation", "")) if isinstance(x, dict) else (str(x), "")
                h.append(f"<p style='margin:4px 0'><a href='say:{e(s)}' style='text-decoration:none'>🔊</a> "
                         f"<span style='font-size:12pt'>{e(s)}</span><br><span style='color:{theme.DIM}'>{expl(tr)}</span></p>")
        syn = ollama.as_list(d.get("synonyms"))
        if syn:
            h.append(f"<p style='margin-top:12px'><span style='color:{theme.DIM}'>Similar: </span>"
                     + " · ".join(e(str(x if not isinstance(x, dict) else ' — '.join(str(v) for v in x.values()))) for x in syn) + "</p>")
        if d.get("opposite"):
            h.append(f"<p><span style='color:{theme.DIM}'>Opposite: </span>{e(str(d['opposite']))}</p>")
        if d.get("tip"):
            h.append(f"<p style='margin-top:12px;padding:8px;border-left:3px solid {theme.GOLD}'>💡 {expl(str(d['tip']))}</p>")
        h.append("</div>")
        self.view.setHtml("".join(h))
        self.add_b.setEnabled(bool(exs or cols) and self.saved is not None)

    def add_examples(self):
        w = self.saved() if self.saved else None
        if not w:
            return
        items = []
        fa = self.ex.currentData() == "fa"
        for x in ollama.as_list(self.result.get("examples")):
            if isinstance(x, dict) and x.get("sentence"):
                tr = str(x.get("translation", ""))
                items.append(Example(de=str(x["sentence"]).strip(), en="" if fa else tr, fa=tr if fa else ""))
        n = self.main.store.add_examples(w.id, items)
        k = self.main.store.add_collocations(w.lang, w.lemma or w.text, collocations_of(self.result))
        self.main.after_change()
        self.state.setText(f"Added to „{w.text}“: {n} sentence(s) for review and practice, {k} collocation(s) — see My Words"
                           if n or k else "These sentences and collocations are already saved")
        self.add_b.setEnabled(False)

    # ------------------------------------------------------------------ 4 exam questions on the word
    def exam_questions(self, fresh: bool = False):
        from . import questions
        self.addq_b.setEnabled(False)
        hit = None if fresh else self.cache.get(self._ckey() + "|exam")
        if hit:
            self.show_questions(hit)
            self.state.setText("From your earlier question · New answer asks again")
            return
        c = client(self.main)
        sys_ = ollama._teacher(self.lang, self.ex.currentData())
        q = questions.teacher_prompt(self.word, self.lemma, self.sentence, self.lang, self.lv.currentText(), self.ex.currentData())
        self._start(self.view5, "exam", lambda on, stop: c.chat(q, sys_, json_mode=True, on_text=on, cancelled=stop,
                                                                 temperature=0.8 if fresh else 0.5),
                    f"Your teacher is writing {self.exam}-style questions on „{html.escape(self.lemma)}“…", q, sys_)

    def show_questions(self, d: dict, reveal: bool = False):
        from . import questions
        from pathlib import Path
        video = Path(self.main.video).name if getattr(self.main, "video", "") else ""
        self.qs = questions.from_json(d, self.lang, self.lemma, video)
        self._qd, e = d, html.escape
        if not self.qs:
            self.view5.setPlainText("The model gave no questions — press New answer.")
            return
        h = [f"<div style='font-size:11pt;line-height:150%'>"]
        for n, x in enumerate(self.qs, 1):
            h.append(f"<p style='margin:12px 0 4px 0'><b style='color:{theme.CYAN}'>{n}.</b> {e(x.question)}</p>")
            for o in x.options:
                h.append(f"<p style='margin:0 0 0 22px'>○ {e(o)}</p>")
            if reveal:
                h.append(f"<p style='margin:4px 0 0 22px;color:{theme.MINT}'>✓ {e(x.answer)}</p>")
                if x.explanation:
                    h.append(f"<p style='margin:0 0 0 22px;color:{theme.DIM}'>{e(x.explanation)}</p>")
        h.append(f"<p style='margin-top:14px'><a href='{'hide' if reveal else 'show'}' style='color:{theme.GOLD}'>"
                 f"{'Hide the answers' if reveal else 'Show the answers'}</a></p></div>")
        self.view5.setHtml("".join(h))
        self.addq_b.setEnabled(True)

    def _q_link(self, url):
        if getattr(self, "_qd", None):
            self.show_questions(self._qd, reveal=url.toString() == "show")

    def add_questions(self):
        n = self.main.store.add_questions(self.qs)
        self.main.after_change()
        self.state.setText(f"{n} question(s) added to Review ✓" if n else "These questions are already in Review")
        self.addq_b.setEnabled(False)

    # ------------------------------------------------------------------ 1 explain the line
    def explain_line(self):
        if not self.sentence:
            self.view2.setPlainText("No line to explain.")
            return
        c = client(self.main)
        sys_ = ollama._teacher(self.lang, self.ex.currentData())
        q = ollama.sentence_prompt(self.sentence, self.lang, self.ex.currentData(), self.lv.currentText())
        self._start(self.view2, "text", lambda on, stop: c.chat(q, sys_, on_text=on, cancelled=stop), "…", q, sys_)

    def again(self):
        if self.stack.currentIndex() == 1:
            self.explain_line()
        elif self.stack.currentIndex() == 4:
            self.exam_questions(fresh=True)
        else:
            self.coach(fresh=True)

    # ------------------------------------------------------------------ 2 check my sentence
    def check(self):
        a = self.attempt.text().strip()
        if len(a.split()) < 2:
            self.view3.setPlainText("Write a whole sentence first.")
            return
        c = client(self.main)
        sys_ = ollama._teacher(self.lang, self.ex.currentData())
        q = ollama.check_prompt(self.lemma, a, self.lang, self.ex.currentData(), self.lv.currentText())
        self._start(self.view3, "check", lambda on, stop: c.chat(q, sys_, json_mode=True, on_text=on, cancelled=stop, temperature=0.2),
                    "Checking…", q, sys_)

    def show_check(self, d: dict, raw: str):
        if not d:
            self.view3.setPlainText(raw)
            return
        e = html.escape
        ok = bool(d.get("correct"))
        rtl = self.ex.currentData() == "fa"
        expl = (lambda s: f"<span dir='rtl'>{e(s)}</span>") if rtl else e
        sc = d.get("score")
        h = [f"<p style='font-size:14pt;color:{theme.MINT if ok else theme.GOLD}'>{'✓ Correct' if ok else '✎ Corrected'}"
             + (f" &nbsp;<span style='color:{theme.DIM};font-size:11pt'>{e(str(sc))}/10</span>" if sc not in (None, "") else "") + "</p>"]
        if not ok and d.get("corrected"):
            h.append(f"<p style='font-size:13pt'>{e(str(d['corrected']))}</p>")
        if d.get("explanation"):
            h.append(f"<p>{expl(str(d['explanation']))}</p>")
        if d.get("better"):
            h.append(f"<p><span style='color:{theme.DIM}'>More natural / more advanced: </span><i>{e(str(d['better']))}</i></p>")
        self.view3.setHtml("".join(h))
        if self.saved and (d.get("corrected") or ok):
            w = self.saved()
            sent = str(d.get("corrected") or self.attempt.text()).strip()
            if w and len(sent.split()) >= 3:
                n = self.main.store.add_examples(w.id, [Example(de=sent)])
                if n:
                    self.main.after_change()
                    self.state.setText("Your (corrected) sentence was added to the word — it comes back in review")

    # ------------------------------------------------------------------ 3 ask
    def ask(self):
        qn = self.question.text().strip()
        if not qn:
            return
        c = client(self.main)
        sys_ = ollama._teacher(self.lang, self.ex.currentData())
        from pathlib import Path
        video = Path(self.main.video).stem if getattr(self.main, "video", "") else ""
        q = ollama.ask_prompt(qn, self.lemma, self.sentence, video, self.lang, self.ex.currentData(), self.lv.currentText())
        self._start(self.view4, "text", lambda on, stop: c.chat(q, sys_, on_text=on, cancelled=stop), "…", q, sys_)

    def reject(self):
        self.runner.stop = True
        super().reject()

    def closeEvent(self, e):
        self.runner.stop = True
        super().closeEvent(e)


def word_from_text(text: str, lang: str) -> dict:
    """A word-coach answer written as text (not JSON): its collocations and example sentences."""
    from . import practice
    cols, rest = practice.split_collocations(text)
    exs = practice.parse_sentences(rest, primary=lang)
    if not cols and not exs:
        return {}
    first = next((ln.strip(" *#-") for ln in text.splitlines() if ln.strip() and "|" not in ln), "")
    return {"meaning": first[:300], "collocations": cols,
            "examples": [{"sentence": e.de, "translation": e.en or e.fa} for e in exs]}


def exam_from_text(text: str, lang: str) -> dict:
    """Exam questions written as Q: / O: / A: / E: cards (not JSON)."""
    from . import questions
    qs = questions.parse(text, lang)
    return {"questions": [{"question": q.question, "options": q.options, "answer": q.answer, "explanation": q.explanation} for q in qs]} if qs else {}


def collocations_of(d: dict) -> list[dict]:
    """The collocations of a word-coach answer as [{phrase, meaning, example}]."""
    out = []
    for c in ollama.as_list((d or {}).get("collocations")):
        if isinstance(c, dict) and c.get("phrase"):
            out.append({"phrase": str(c["phrase"]), "meaning": str(c.get("meaning", "")), "example": str(c.get("example", ""))})
        elif isinstance(c, str) and c.strip():
            ph, _, mean = c.partition(" — ") if " — " in c else c.partition(" - ")
            out.append({"phrase": ph.strip(), "meaning": mean.strip(), "example": ""})
    return out


class SetupPanel(QWidget):
    """Settings ▸ Local AI teacher (Ollama): status, the model to use, one-click download of the suggested model."""

    def __init__(self, main, parent=None):
        super().__init__(parent)
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QProgressBar
        self.main = main
        self.setObjectName("clear")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        intro = QLabel(
            "A free AI teacher on your own PC — private, no API key, works without internet once a model is downloaded. "
            "It writes collocations and example sentences at your level, explains lines, corrects your own sentences and "
            "can write the AI lessons and TestDaF / IELTS sets directly.<br><br>"
            f"<b>1.</b> <a href='{ollama.DOWNLOAD_PAGE}' style='color:{theme.CYAN}'>Download Ollama for Windows</a> "
            "(OllamaSetup.exe) and install it — it then runs by itself in the system tray (the llama icon next to the clock).<br>"
            "<b>2.</b> Press <b>Check</b> below.<br>"
            "<b>3.</b> Press <b>Download suggested model</b> (or pick another one) and wait until it is done.<br>"
            "<b>4.</b> Use it: word card ▸ <b>Teacher</b>; Study this video ▸ AI lesson ▸ <b>Ollama</b>.<br>"
            f"<span style='color:{theme.DIM}'>Models are downloaded by Ollama from ollama.com — from Iran usually only with a VPN; "
            "after that everything runs offline.</span>")
        intro.setWordWrap(True)
        intro.setOpenExternalLinks(False)
        intro.linkActivated.connect(lambda u: QDesktopServices.openUrl(QUrl(u)))
        intro.setObjectName("hint")
        v.addWidget(intro)
        row = QHBoxLayout()
        self.url = QLineEdit(main.settings.get("ollama_url", ollama.DEFAULT_URL))
        self.url.setToolTip("Where Ollama runs. Normally this PC; another PC in your network works too (on that PC set OLLAMA_HOST=0.0.0.0).")
        row.addWidget(QLabel("Address", objectName="small"))
        row.addWidget(self.url, 1)
        chk = QPushButton("Check")
        chk.clicked.connect(self.check)
        row.addWidget(chk)
        v.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Model", objectName="small"))
        self.model = QComboBox()
        self.model.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.model.setMinimumContentsLength(24)
        self.model.currentIndexChanged.connect(self._model_chosen)
        row.addWidget(self.model, 1)
        v.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Suggested", objectName="small"))
        self.sugg = QComboBox()
        self.sugg.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.sugg.setMinimumContentsLength(24)
        for s in ollama.SUGGESTED:
            self.sugg.addItem(f"{s.name} · {s.size} · {s.why}", s.name)
            self.sugg.setItemData(self.sugg.count() - 1, f"{s.name} · {s.size} download · needs about {s.ram_gb} GB memory · {s.why}",
                                  Qt.ItemDataRole.ToolTipRole)
        row.addWidget(self.sugg, 1)
        self.pull_b = QPushButton("Download suggested model")
        self.pull_b.clicked.connect(self.pull)
        row.addWidget(self.pull_b)
        v.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        v.addWidget(self.bar)
        self.state = QLabel("", objectName="small")
        self.state.setWordWrap(True)
        v.addWidget(self.state)
        ram = ollama.ram_gb()
        best = ollama.suggestion_for(ram)
        self.sugg.setCurrentIndex(max(0, self.sugg.findData(best.name)))
        self.ram = ram
        self._models: list[dict] = []
        self.runner = Runner(self)
        self.runner.done.connect(self._pulled)
        self.runner.failed.connect(lambda m: (self.bar.setVisible(False), self.pull_b.setEnabled(True), self.state.setText("⚠ " + m)))
        self.runner.text.connect(self._pull_progress)
        self.check(quiet=True)

    def _client(self):
        self.main.settings["ollama_url"] = self.url.text().strip() or ollama.DEFAULT_URL
        self.main.save_settings()
        return ollama.Client(self.main.settings["ollama_url"])

    def check(self, quiet: bool = False):
        c = self._client()
        try:
            ver = c.version()
            self._models = c.models()
        except Exception as e:
            self.model.clear()
            self.state.setText(("" if quiet else "⚠ ") + str(e) + f" (This PC: {self.ram:.0f} GB memory — suggested model "
                               f"{ollama.suggestion_for(self.ram).name}.)")
            return
        names = [m.get("name", "") for m in self._models]
        cur = self.main.settings.get("ollama_model", "")
        if cur not in names:
            cur = ollama.best_installed(self._models, self.ram)
        self.model.blockSignals(True)
        self.model.clear()
        for m in sorted(self._models, key=lambda m: -ollama.score(m, self.ram)):
            ok = ollama.score(m, self.ram) > 0
            gb = (m.get("size") or 0) / 1e9
            self.model.addItem(f"{m.get('name')} · {gb:.1f} GB" + ("" if ok else " (not a language model)"), m.get("name"))
        self.model.setCurrentIndex(max(0, self.model.findData(cur)))
        self.model.blockSignals(False)
        self._model_chosen()
        best = ollama.suggestion_for(self.ram)
        if not self._models:
            self.state.setText(f"✓ Ollama {ver} is running, but no model is downloaded yet. This PC has {self.ram:.0f} GB memory: "
                               f"press Download suggested model ({best.name}, {best.size}).")
        else:
            self.state.setText(f"✓ Ollama {ver} is running · {len(self._models)} model(s) on this PC · teacher: "
                               f"{self.main.settings.get('ollama_model') or '—'} · this PC: {self.ram:.0f} GB memory"
                               + ("" if self.main.settings.get("ollama_model") else " — download a language model, the ones here can't teach")
                               + self._weak(best))

    def _weak(self, best) -> str:
        """A warning when the chosen model is an old / small / English-only one (phi, starling, OCR tunes …)."""
        name = self.main.settings.get("ollama_model") or ""
        m = next((x for x in self._models if x.get("name") == name), None)
        if m is None or ollama.score(m, self.ram) >= 60:
            return ""
        return (f"\n⚠ {name} is weak in German — its sentences and corrections will often be wrong. "
                f"Press Download suggested model ({best.name}, {best.size}) for a real teacher.")

    def _model_chosen(self, *_):
        name = self.model.currentData() or ""
        m = next((x for x in self._models if x.get("name") == name), None)
        if m is not None and ollama.score(m, self.ram) <= 0:
            name = ""
        self.main.settings["ollama_model"] = name
        self.main.save_settings()

    def pull(self):
        name = self.sugg.currentData()
        c = self._client()
        self.bar.setVisible(True)
        self.bar.setRange(0, 0)
        self.pull_b.setEnabled(False)
        self.state.setText(f"Ollama is downloading {name}… (you can keep using SubPlayer)")
        self._pulling = name

        def fn(on, stop):
            c.version()
            c.pull(name, lambda d, t, s: on(f"{d}|{t}|{s}"), stop)
            return name
        self.runner.run(fn)

    def _pull_progress(self, t: str):
        d, tot, s = t.split("|", 2)
        d, tot = int(d), int(tot)
        if tot:
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(d * 1000 / tot))
            self.state.setText(f"Downloading {self._pulling}: {d / 1e9:.2f} of {tot / 1e9:.2f} GB")
        else:
            self.bar.setRange(0, 0)
            self.state.setText(f"{self._pulling}: {s}")

    def _pulled(self, name: str):
        self.bar.setVisible(False)
        self.pull_b.setEnabled(True)
        self.main.settings["ollama_model"] = name
        self.main.save_settings()
        self.check()
        self.state.setText(f"✓ {name} is ready — word card ▸ Teacher. " + self.state.text().split("·", 1)[-1])
