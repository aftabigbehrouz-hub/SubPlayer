import json
import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SUBPLAYER_HOME"] = tempfile.mkdtemp()

from subplayer_win import ollama, voice  # noqa: E402

WRITING = {
    "corrections": [{"original": "Ich gehe gestern ins Kino.", "corrected": "Ich bin gestern ins Kino gegangen.", "why": "Perfekt für die Vergangenheit"},
                    {"original": "Es war gut.", "corrected": "Es war gut.", "why": ""}],
    "feedback": {"development": "Zu kurz.", "cohesion": "Keine Konnektoren.", "coherence": "Klar."},
    "level": "A2", "score": 4,
    "versions": [{"title": "Corrected", "text": "Ich bin gestern ins Kino gegangen. Es war gut.", "changes": "Perfekt"},
                 {"title": "Clear and coherent", "text": "Gestern bin ich ins Kino gegangen, und der Film hat mir gut gefallen.", "changes": ""},
                 {"title": "Exam level", "text": "Der gestrige Kinobesuch hat sich durchaus gelohnt.", "changes": ""}],
    "useful": [{"phrase": "außerdem", "meaning": "moreover"}],
}
LEVELS = {"versions": [{"level": lv, "sentence": f"Satz {lv}.", "translation": "t", "note": "n"} for lv in ("A1", "A2", "B1", "B2", "C1")]}


class Prompts(unittest.TestCase):
    def test_writing_prompt(self):
        q = ollama.writing_prompt("Ich gehe gestern ins Kino.", "de", "fa", "B1", "Freizeit")
        for k in ('"corrections"', '"feedback"', '"versions"', "cohesion", "coherence", "development", "TestDaF", "Persian", "Freizeit"):
            self.assertIn(k, q)

    def test_levels_prompt(self):
        q = ollama.levels_prompt("Er weigert sich zu zahlen.", "de", "en")
        self.assertIn("A1, A2, B1, B2 and C1", q)
        self.assertIn('"versions"', q)


class Voice(unittest.TestCase):
    def test_defaults_and_cache(self):
        self.assertEqual(voice.edge_voice({}, "de"), "de-DE-SeraphinaMultilingualNeural")
        self.assertEqual(voice.edge_voice({"voice_edge_en": "en-GB-RyanNeural"}, "en"), "en-GB-RyanNeural")
        self.assertFalse(voice.piper_ready("de"))
        self.assertEqual(len(voice.piper_missing("de")), 2)
        a = voice._cache("edge", "v", "Hallo", False, "mp3")
        self.assertNotEqual(a, voice._cache("edge", "v", "Hallo", True, "mp3"))

    def test_piper_missing_means_fallback(self):
        with self.assertRaises(FileNotFoundError):
            voice.audio_file({"voice_engine": "piper"}, "Hallo", "de")


class TeacherTabs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _main(self):
        from PySide6.QtWidgets import QWidget

        class M(QWidget):
            settings = {"teacher_source": "chatgpt"}
            video = ""
            spoken = []

            def save_settings(self): pass

            def speak(self, text, slow=False, lang="de"): self.spoken.append(text)

            def ask_ai(self, *a): pass

            def msg(self, *a): pass
        return M()

    def test_writing_only_and_paste(self):
        from PySide6.QtWidgets import QApplication
        from subplayer_win.teacher import TeacherDialog
        m = self._main()
        d = TeacherDialog(m, "", "", "", "de", None, 5)
        self.assertFalse(d.tab_btns[0].isVisibleTo(d))            # word tabs hidden when opened for writing only
        d.w_text.setPlainText("Ich gehe gestern ins Kino. Es war gut.")
        QApplication.clipboard().setText("```json\n" + json.dumps(WRITING, ensure_ascii=False) + "\n```")
        d.paste_answer()
        h = d.view6.toHtml()
        for k in ("SENTENCE BY SENTENCE", "Ich bin gestern ins Kino gegangen.", "Cohesion", "THREE BETTER VERSIONS", "Exam level", "außerdem", "4/10"):
            self.assertIn(k, h)
        from subplayer_win import paths
        self.assertTrue((paths.data_dir() / "writing.jsonl").exists())
        d._say_or_copy(__import__("PySide6.QtCore", fromlist=["QUrl"]).QUrl("use:Neuer%20Text"))
        self.assertEqual(d.w_text.toPlainText(), "Neuer Text")
        d.close()

    def test_levels_tab(self):
        from PySide6.QtWidgets import QApplication
        from subplayer_win.teacher import TeacherDialog
        m = self._main()
        d = TeacherDialog(m, "weigere", "weigern", "Ich weigere mich.", "de", None, 6)
        self.assertEqual(d.l_sent.text(), "Ich weigere mich.")
        QApplication.clipboard().setText(json.dumps(LEVELS))
        d.paste_answer()
        h = d.view7.toHtml()
        for lv in ("A1", "B2", "C1", "Satz C1."):
            self.assertIn(lv, h)
        d.close()


if __name__ == "__main__":
    unittest.main()
