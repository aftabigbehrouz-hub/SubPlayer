"""2.9.2: synonyms with the collocations, paraphrases kept, notes tied to their word, the reading text of exam questions."""
import os
import sqlite3
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SUBPLAYER_HOME"] = tempfile.mkdtemp()

from subplayer_win import practice, questions, store as st  # noqa: E402
from subplayer_win.teacher import collocations_of, synonym_examples, synonyms_of  # noqa: E402


class Synonyms(unittest.TestCase):
    D = {"collocations": [{"phrase": "vermögende Kunden", "meaning": "wealthy clients", "example": "Die Bank sucht vermögende Kunden."}],
         "synonyms": [{"word": "reich", "meaning": "rich", "difference": "neutral", "example": "Er ist sehr reich geworden.",
                       "translation": "He became very rich."},
                      "betucht — colloquial"]}

    def test_json_synonyms(self):
        s = synonyms_of(self.D)
        self.assertEqual([x["phrase"] for x in s], ["reich", "betucht"])
        cols = collocations_of(self.D)
        self.assertEqual([(c["phrase"], c["kind"]) for c in cols], [("vermögende Kunden", ""), ("reich", "syn"), ("betucht", "syn")])
        ex = synonym_examples(self.D)
        self.assertEqual([(e.de, e.en) for e in ex], [("Er ist sehr reich geworden.", "He became very rich.")])
        self.assertEqual(synonym_examples(self.D, fa=True)[0].fa, "He became very rich.")

    def test_syn_lines(self):
        cols, rest = practice.split_collocations("KOLL: ein großes Haus | a big house | Wir haben ein großes Haus.\n"
                                                 "SYN: das Gebäude | building | Das Gebäude ist sehr alt.\nDE: Das Haus ist schön.")
        self.assertEqual([(c["phrase"], c.get("kind", "")) for c in cols], [("ein großes Haus", ""), ("das Gebäude", "syn")])
        self.assertIn("DE: Das Haus", rest)
        self.assertEqual([e.de for e in synonym_examples({"collocations": cols})], ["Das Gebäude ist sehr alt."])
        self.assertTrue(practice.looks_like_ai_answer("SYN: a | b | c"))


class Store(unittest.TestCase):
    def test_old_database_is_migrated(self):
        f = os.path.join(tempfile.mkdtemp(), "words.db")
        db = sqlite3.connect(f)
        db.executescript("""CREATE TABLE collocations(id INTEGER PRIMARY KEY AUTOINCREMENT, lang TEXT, lemma TEXT, phrase TEXT,
            meaning TEXT, example TEXT, created INTEGER);
            INSERT INTO collocations(lang,lemma,phrase,meaning,example,created) VALUES('de','gut','gut gehen','go well','',1);""")
        db.commit()
        db.close()
        s = st.WordStore(f)
        self.assertEqual(s.collocations("de", "gut")[0]["kind"], "")
        s.add_collocations("de", "gut", [{"phrase": "prima", "meaning": "great", "kind": "syn"}])
        self.assertEqual([c["kind"] for c in s.collocations("de", "gut")], ["", "syn"])

    def test_passage_and_notes(self):
        s = st.WordStore(os.path.join(tempfile.mkdtemp(), "w.db"))
        s.add_questions([st.Question("Q1?", "Ja")])
        s.add_questions([st.Question("Q1?", "Ja", passage="B: Ein Absatz.")])       # pasted again with its text
        self.assertEqual(s.questions()[0].passage, "B: Ein Absatz.")
        s.add_note(st.Note("Ein Satz.", "<p>x</p>", kind="levels", lemma="Gut", video_name="v.mp4", at_ms=4000))
        s.add_note(st.Note("Ein Text.", "<p>y</p>", kind="writing"))
        self.assertEqual([n.at_ms for n in s.notes(lemma="gut")], [4000])
        self.assertEqual([n.title for n in s.notes(lemma="")], ["Ein Text."])
        self.assertEqual(s.note_words(), [("gut", 1)])
        self.assertEqual(s.note_count(["GUT", "x"]), 1)


LESSON = ("1. WORTSCHATZ\nx\n3. LESEN\nDer Text\nA: " + "Seit Jahren steigen die Temperaturen weltweit. " * 6 + "\nB: "
          + "Forscher schlagen mehr Grünflächen vor. " * 6 + "\nAufgaben\n1. Ordnen Sie zu\n4. SCHREIBEN\nSchreiben Sie.\n"
          "---REVIEW---\nQ: Städte brauchen laut Absatz B mehr Grün.\nO: Ja | Nein | Text sagt dazu nichts\nA: Ja\nE: Absatz B\n"
          "Q: Forscher sind dagegen.\nO: Ja | Nein | Text sagt dazu nichts\nA: Nein\nE: B\nT: B: Forscher schlagen mehr Grünflächen vor.\n")


class Reading(unittest.TestCase):
    def test_t_line_and_lesson_text(self):
        qs = questions.parse(LESSON, "de", "v.mp4", "lesson:TestDaF")
        self.assertEqual([q.passage for q in qs], ["", "B: Forscher schlagen mehr Grünflächen vor."])
        t = questions.reading_text(LESSON)
        self.assertTrue(t.startswith("Der Text") and "Grünflächen" in t)
        self.assertNotIn("Ordnen", t)
        self.assertNotIn("Schreiben Sie", t)
        self.assertEqual(questions.reading_text("no reading here"), "")

    def test_passage_of_falls_back_to_the_lesson(self):
        from subplayer_win import lessons
        lessons.save("v.mp4", "de", "TestDaF", LESSON)
        q = questions.parse(LESSON, "de", "v.mp4", "lesson:TestDaF")[0]
        self.assertIn("Grünflächen", questions.passage_of(q))
        self.assertEqual(questions.passage_of(st.Question("Was zeigt das Video?", "A", source="teacher")), "")

    def test_teacher_json_text(self):
        qs = questions.from_json({"questions": [{"text": "Ein kurzer Text.", "question": "Stimmt das?", "options": ["Ja", "Nein"],
                                                 "answer": "Ja"}]}, "de", "gut")
        self.assertEqual(qs[0].passage, "Ein kurzer Text.")


if __name__ == "__main__":
    unittest.main()
