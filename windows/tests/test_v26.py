"""2.6: My Words newest first, one entry per word, collocations kept, exam questions in Review (least reviewed first),
sentences for translation and Pause each line."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SUBPLAYER_HOME", tempfile.mkdtemp())

from subplayer_win import lessons, questions, subtitles  # noqa: E402
from subplayer_win.store import DAY, Example, Question, SavedWord, WordStore, review  # noqa: E402


def store():
    return WordStore(Path(tempfile.mkdtemp()) / "w.db")


class Words(unittest.TestCase):
    def test_newest_first_and_least_reviewed_due_first(self):
        s = store()
        old = SavedWord("eigentlich", "eigentlich", "", created=1000, reviews=9, box=0, due=5)
        mid = SavedWord("radeln", "radeln", "", created=2000, reviews=0, box=0, due=50)
        new = SavedWord("etliche", "etliche", "", created=3000, reviews=2, box=1, due=10)
        for w in (old, mid, new):
            s.insert(w)
        self.assertEqual([w.text for w in s.all()], ["etliche", "radeln", "eigentlich"])
        self.assertEqual([w.text for w in s.due(10 ** 12)], ["radeln", "etliche", "eigentlich"])

    def test_same_word_is_found_from_another_video(self):
        s = store()
        s.insert(SavedWord("zuzuspitzen", "zuspitzen", "Der Konflikt …", video_name="a.mp4", start_ms=100, lang="de"))
        self.assertIsNotNone(s.find_same("spitzt", "zuspitzen", "de"))
        self.assertIsNone(s.find_same("zuspitzen", "zuspitzen", "en"))
        self.assertIsNone(s.find_same("spitzen", "spitzen", "de"))

    def test_duplicates_are_joined_with_their_sentences(self):
        s = store()
        a = SavedWord("etliche", "etliche", "Aktuell gibt es wieder etliche Angriffe.", video_name="v.mp4", created=1000)
        b = SavedWord("etliche", "etliche", "Aktuell gibt es wieder etliche Angriffe.", video_name="v.mp4", created=2000)
        c = SavedWord("Etliche", "etliche", "Etliche Leute kamen.", video_name="w.mp4", created=3000, reviews=3)
        ids = [s.insert(w) for w in (a, b, c)]
        s.add_examples(ids[1], [Example("Es gab etliche Touristen in der Stadt.", "There were a few tourists.")])
        s.insert(SavedWord("radeln", "radeln", "Wir radeln."))
        self.assertEqual(s.merge_duplicates(), 2)
        ws = s.all()
        self.assertEqual(sorted(w.text for w in ws), ["Etliche", "radeln"])
        keep = next(w for w in ws if w.lemma == "etliche")
        self.assertEqual(keep.reviews, 3)                      # the most reviewed one stays, with its progress
        des = [e.de for e in s.examples(keep.id)]
        self.assertIn("Es gab etliche Touristen in der Stadt.", des)
        self.assertIn("Aktuell gibt es wieder etliche Angriffe.", des)
        self.assertEqual(len(des), 2)                          # the same video line only once
        self.assertEqual(len(s.tombstones()), 3)               # 2 words + 1 example deleted → the phone deletes them too
        self.assertEqual(s.merge_duplicates(), 0)

    def test_collocations_per_base_word(self):
        s = store()
        items = [{"phrase": "etliche Male", "meaning": "several times", "example": "Ich war etliche Male dort."},
                 {"phrase": "etliche Stunden", "meaning": "several hours", "example": ""}]
        self.assertEqual(s.add_collocations("de", "Etliche", items), 2)
        self.assertEqual(s.add_collocations("de", "etliche", items[:1]), 0)       # no doubles
        cs = s.collocations("de", "etliche")
        self.assertEqual([c["phrase"] for c in cs], ["etliche Male", "etliche Stunden"])
        s.delete_collocation(cs[0]["id"])
        self.assertEqual(len(s.collocations("de", "etliche")), 1)
        self.assertEqual(s.collocations("en", "etliche"), [])


class Questions(unittest.TestCase):
    LESSON = ("HÖREN\n1. ...\n---LÖSUNGEN---\n1 falsch\n\n" + questions.MARK + "\n"
              "Q: Laut dem Video sind die Angriffe auf Schiffe zurückgegangen.\nO: richtig | falsch\nA: falsch\n"
              "E: „Aktuell gibt es wieder etliche Angriffe …“\n\n"
              "Q: Was bedeutet „etliche“?\nO: A) keine | B) mehrere | C) alle\nA: B\nE: etliche = einige, mehrere\n\n"
              "2. Q: Text A: … Der Autor hält die Lage für stabil.\nO: Ja | Nein | Text sagt dazu nichts\nA: Text sagt dazu nichts\n"
              "E: Darüber steht nichts\n\n"
              "Q: Wie heißt die Meerenge, durch die viel Öl transportiert\nwird?\nO:\nA: die Straße von Hormuz\nE: Zeile 2\n")

    def test_the_lesson_block_is_read(self):
        qs = questions.parse(self.LESSON, "de", "v.mp4", "lesson:TestDaF")
        self.assertEqual(len(qs), 4)
        self.assertEqual([q.kind for q in qs], ["tf", "mc", "yn", "open"])
        self.assertEqual(qs[1].options, ["A) keine", "B) mehrere", "C) alle"])
        self.assertTrue(qs[3].question.endswith("transportiert wird?"))           # a wrapped line is joined
        self.assertEqual(qs[0].video_name, "v.mp4")

    def test_a_normal_lesson_has_no_cards(self):
        self.assertEqual(questions.parse("TEXT\nA: Das ist ein Satz.\nLÖSUNGEN 1a 2b"), [])

    def test_exam_prompt_asks_for_cards(self):
        c = [subtitles.Cue(0, 1000, "Hallo zusammen.")]
        self.assertIn(questions.MARK, lessons.prompt("TestDaF", "de", "v.mp4", c, []))
        self.assertIn(questions.MARK, lessons.prompt("IELTS", "en", "v.mp4", c, []))
        self.assertNotIn(questions.MARK, lessons.prompt("B1", "de", "v.mp4", c, []))

    def test_teacher_questions(self):
        q = questions.teacher_prompt("etliche", "etliche", "Aktuell gibt es wieder etliche Angriffe.", "de", "C1", "en")
        for t in ("TestDaF", "etliche", "JSON", "C1"):
            self.assertIn(t, q)
        d = {"questions": [{"question": "Welches Wort passt? Es gab ___ Probleme.", "options": ["etliche", "etlich"],
                            "answer": "etliche", "explanation": "Plural"}, {"question": "", "answer": "x"}]}
        qs = questions.from_json(d, "de", "etliche")
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0].source, "teacher")

    def test_questions_are_reviewed_like_words(self):
        s = store()
        qs = questions.parse(self.LESSON, "de", "v.mp4", "lesson:TestDaF")
        self.assertEqual(s.add_questions(qs), 4)
        self.assertEqual(s.add_questions(qs), 0)                # pasting the lesson again adds nothing
        due = s.due_questions(10 ** 13)
        self.assertEqual(len(due), 4)
        from subplayer_win.store import now_ms
        now = now_ms() + 5
        s.update_question(review(due[0], True, now))
        again = s.questions(lang="de", video_name="v.mp4")[0]
        self.assertEqual((again.reviews, again.box, again.due), (1, 1, now + DAY))
        self.assertEqual(len(s.due_questions(now)), 3)

    def test_choices_are_matched_to_the_answer(self):
        from subplayer_win.pages import ReviewPage
        ok = ReviewPage.is_answer
        self.assertTrue(ok("B) mehrere", "B"))
        self.assertTrue(ok("B) mehrere", "b) mehrere"))
        self.assertTrue(ok("B) mehrere", "mehrere"))
        self.assertFalse(ok("A) keine", "B"))
        self.assertTrue(ok("falsch", "Falsch"))
        self.assertFalse(ok("richtig", "falsch"))
        self.assertTrue(ok("Text sagt dazu nichts", "text sagt dazu nichts"))
        self.assertFalse(ok("Nein", "Text sagt dazu nichts"))


class Sentences(unittest.TestCase):
    def test_lines_are_grouped_into_sentences_without_overlap(self):
        C = subtitles.Cue
        cs = [C(0, 1000, "Aktuell gibt es wieder"), C(1000, 2000, "etliche Angriffe auf Schiffe"), C(2000, 3000, "in der Straße von Hormuz."),
              C(3100, 4000, "Gut.")] + [C(5000 + k * 1000, 5900 + k * 1000, f"teil {k}") for k in range(8)] + [C(14000, 15000, "Ende.")]
        r = subtitles.sentence_ranges(cs)
        self.assertEqual(r[:4], [(0, 2), (0, 2), (0, 2), (3, 3)])
        self.assertEqual(r[4:], [(4, 8)] * 5 + [(9, 12)] * 4)    # a 9-line sentence: two parts of 5 and 4 lines
        units = sorted(set(r))
        covered = [k for a, b in units for k in range(a, b + 1)]
        self.assertEqual(covered, list(range(len(cs))))          # every line in exactly one unit

    def test_long_pause_starts_a_new_unit(self):
        C = subtitles.Cue
        cs = [C(0, 1000, "eins,"), C(4000, 5000, "zwei."), C(5000, 6000, "Drei."), C(6000, 7000, "Vier.")]
        self.assertEqual(subtitles.sentence_ranges(cs)[:2], [(0, 0), (1, 1)])

    def test_without_punctuation_each_line(self):
        C = subtitles.Cue
        cs = [C(0, 1000, "eins"), C(1000, 2000, "zwei"), C(2000, 3000, "drei")]
        self.assertEqual(subtitles.sentence_ranges(cs), [(0, 0), (1, 1), (2, 2)])


class Portable(unittest.TestCase):
    def test_data_folder_next_to_the_exe(self):
        import sys
        from subplayer_win import paths
        d = Path(tempfile.mkdtemp())
        old = (getattr(sys, "frozen", None), sys.executable, os.environ.get("SUBPLAYER_HOME"))
        try:
            os.environ.pop("SUBPLAYER_HOME", None)
            sys.frozen, sys.executable = True, str(d / "SubPlayer.exe")
            self.assertIsNone(paths.portable_dir())
            (d / "SubPlayer data").mkdir()
            self.assertEqual(paths.data_dir(), (d / "SubPlayer data").resolve())
        finally:
            if old[0] is None:
                del sys.frozen
            sys.executable = old[1]
            if old[2] is not None:
                os.environ["SUBPLAYER_HOME"] = old[2]


if __name__ == "__main__":
    unittest.main()
