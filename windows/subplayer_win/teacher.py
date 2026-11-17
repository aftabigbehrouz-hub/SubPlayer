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
                res = fn(lambda t: self.text.emit(t), lambda: self.stop)
                self.done.emit(res or "")
            except Exception as e:
                self.failed.emit(str(e))
            finally:
                self.busy = False
        threading.Thread(target=work, daemon=True).start()


def client(main) -> ollama.Client:
    return ollama.Client(main.settings.get("ollama_url", ollama.DEFAULT_URL), main.settings.get("ollama_model", ""))


def level(main) -> str:
    return main.settings.get("teacher_level", "B1")


def explain(main) -> str:
    return main.settings.get("lesson_explain", "en")


class TeacherDialog(QDialog):
    TABS = ("Word && collocations", "Explain the line", "Check my sentence", "Ask the teacher")

    def __init__(self, main, word: str, lemma: str, sentence: str, lang: str, saved=None, tab: int = 0):
        super().__init__(main)
        self.main, self.word, self.lemma, self.sentence, self.lang = main, word, lemma or word, sentence, lang
        self.saved = saved                                # SavedWord getter (to add sentences)
        self.result: dict = {}
        self.setWindowTitle(f"Teacher — „{self.lemma}“")
        self.resize(820, 700)
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 16, 22, 16)
        head = QHBoxLayout()
        t = QLabel(f"<span style='font-size:19pt;font-weight:700;color:{theme.CYAN}'>{html.escape(self.lemma)}</span>"
                   f"<span style='color:{theme.DIM}'> &nbsp;· your teacher on this PC ({html.escape(main.settings.get('ollama_model', '') or '—')})</span>")
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
        if sentence:
            s = QLabel(f"<span style='color:{theme.DIM}'>„{html.escape(sentence)}“</span>")
            s.setWordWrap(True)
            v.addWidget(s)
        tabs = QHBoxLayout()
        self.tab_btns = []
        for i, name in enumerate(self.TABS):
            b = QPushButton(name, checkable=True)
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
        v.addWidget(self.stack, 1)

        foot = QHBoxLayout()
        self.state = QLabel("", objectName="small")
        foot.addWidget(self.state, 1)
        self.add_b = QPushButton("＋ Add the example sentences to my word")
        self.add_b.setToolTip("They appear in review and practice, like sentences from the video")
        self.add_b.clicked.connect(self.add_examples)
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
        self.runner.text.connect(self._piece)
        self.runner.done.connect(self._done)
        self.runner.failed.connect(self._failed)
        self._target_view, self._buf, self._mode = None, "", ""
        self.cache = ollama.Cache()
        self.tab(tab)

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
        self.again_b.setVisible(i in (0, 1))
        if i == 0 and not self.result:
            self.coach()
        elif i == 1 and not self.view2.toPlainText():
            self.explain_line()
        elif i == 2:
            self.attempt.setFocus()
        elif i == 3:
            self.question.setFocus()

    def _start(self, view, mode: str, fn, waiting: str):
        if self.runner.busy:
            self.state.setText("The teacher is still answering — press Stop first")
            return
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
            d = ollama.parse_json(res)
            if not d:
                self._target_view.setPlainText(res or "The model gave no answer.")
                return
            self.cache.put(self._ckey(), d)
            self.show_word(d)
        elif self._mode == "check":
            self.show_check(ollama.parse_json(res), res)

    # ------------------------------------------------------------------ 0 word coach
    def _ckey(self):
        return ollama.Cache.key(self.main.settings.get("ollama_model", ""), self.lang, self.lemma, self.lv.currentText(), self.ex.currentData())

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
                    "Your teacher is preparing the meaning, collocations and example sentences…")

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
        self.add_b.setEnabled(bool(exs) and self.saved is not None)

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
        for c in ollama.as_list(self.result.get("collocations")):
            if isinstance(c, dict) and c.get("example") and len(str(c["example"]).split()) >= 3:
                items.append(Example(de=str(c["example"]).strip(), en="" if fa else str(c.get("phrase", "")), fa=str(c.get("meaning", "")) if fa else ""))
        n = self.main.store.add_examples(w.id, items)
        self.main.after_change()
        self.state.setText(f"{n} sentence(s) added to „{w.text}“ — they appear in review and practice" if n else "These sentences are already saved")
        self.add_b.setEnabled(False)

    # ------------------------------------------------------------------ 1 explain the line
    def explain_line(self):
        if not self.sentence:
            self.view2.setPlainText("No line to explain.")
            return
        c = client(self.main)
        sys_ = ollama._teacher(self.lang, self.ex.currentData())
        q = ollama.sentence_prompt(self.sentence, self.lang, self.ex.currentData(), self.lv.currentText())
        self._start(self.view2, "text", lambda on, stop: c.chat(q, sys_, on_text=on, cancelled=stop), "…")

    def again(self):
        if self.stack.currentIndex() == 1:
            self.explain_line()
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
                    "Checking…")

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
        self._start(self.view4, "text", lambda on, stop: c.chat(q, sys_, on_text=on, cancelled=stop), "…")

    def reject(self):
        self.runner.stop = True
        super().reject()


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
