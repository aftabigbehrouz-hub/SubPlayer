"""2.6.1: online assistants in the teacher (their answers pasted back), collocations kept apart from sentences, things by hand."""
import os
import tempfile
import unittest

os.environ.setdefault("SUBPLAYER_HOME", tempfile.mkdtemp())

from subplayer_win import practice  # noqa: E402
from subplayer_win.teacher import exam_from_text, word_from_text  # noqa: E402

TABLE = """Here are collocations with „weitestgehend“:

| German collocation | English | Persian |
|---|---|---|
| weitestgehend wiederhergestellt | largely restored | تا حد زیادی بازسازی شده |
| **weitestgehend abgeschlossen** | largely completed | تا حد زیادی تکمیل شده |
KOLL: weitestgehend unabhängig | largely independent | Die Region ist weitestgehend unabhängig.

DE: Die Systeme laufen weitestgehend wieder. | EN: The systems are largely running again. | FA: سیستم‌ها دوباره کار می‌کنند.
"""


class Collocations(unittest.TestCase):
    def test_table_and_koll_lines_are_collocations(self):
        cols, rest = practice.split_collocations(TABLE)
        self.assertEqual([c["phrase"] for c in cols], ["weitestgehend wiederhergestellt", "weitestgehend abgeschlossen", "weitestgehend unabhängig"])
        self.assertIn("largely restored", cols[0]["meaning"])
        self.assertEqual(cols[2]["example"], "Die Region ist weitestgehend unabhängig.")
        s = practice.parse_sentences(rest)
        self.assertEqual([e.de for e in s], ["Die Systeme laufen weitestgehend wieder."])
        self.assertNotIn("German collocation", rest)

    def test_headers_and_phrases(self):
        self.assertTrue(practice.is_header("German collocation"))
        self.assertTrue(practice.is_header("English"))
        self.assertFalse(practice.is_header("weitestgehend abgeschlossen"))
        self.assertTrue(practice.is_phrase("weitestgehend abgeschlossen"))
        self.assertFalse(practice.is_phrase("Die Systeme laufen weitestgehend wieder."))


class PastedAnswers(unittest.TestCase):
    def test_word_answer_as_text(self):
        d = word_from_text(TABLE, "de")
        self.assertEqual(len(d["collocations"]), 3)
        self.assertEqual(d["examples"][0]["sentence"], "Die Systeme laufen weitestgehend wieder.")

    def test_exam_answer_as_cards(self):
        t = "Q: Was bedeutet weitestgehend?\nO: A) gar nicht | B) fast ganz\nA: B\nE: weitgehend\n\nQ: Richtig?\nO: richtig | falsch\nA: richtig\n"
        d = exam_from_text(t, "de")
        self.assertEqual(len(d["questions"]), 2)
        self.assertEqual(d["questions"][0]["answer"], "B")


if __name__ == "__main__":
    unittest.main()
