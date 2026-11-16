"""Version 2.3: trustworthy dictionary links (helper verbs, particles), word forms and separable verbs for "Where else",
AI lessons, themes."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def make_dict(folder: str) -> str:
    """A small dictionary with the same faults as the real file: every verb also hangs under sein / haben / werden / worden /
    gewesen / sie, separable verbs under their particle, and "machen" under saubermachen."""
    f = os.path.join(folder, "dict.db")
    db = sqlite3.connect(f)
    db.executescript("CREATE TABLE entry(id INTEGER PRIMARY KEY, lemma TEXT, pos TEXT, gender TEXT, ipa TEXT, hyph TEXT, audio TEXT, data TEXT);"
                     "CREATE TABLE lookup(key TEXT, id INTEGER, PRIMARY KEY(key,id)) WITHOUT ROWID;")
    n = [0]

    def add(lemma, pos, keys):
        n[0] += 1
        db.execute("INSERT INTO entry VALUES(?,?,?,?,?,?,?,?)", (n[0], lemma, pos, "", "", "", "", json.dumps({"en": [lemma]})))
        for k in {lemma.lower(), *keys}:
            db.execute("INSERT OR IGNORE INTO lookup VALUES(?,?)", (k, n[0]))
    junk = ["sein", "haben", "werden", "worden", "gewesen", "sie", "…"]
    for i in range(40):                                               # forty ordinary verbs, all with the junk links
        add(f"verb{i}en", "verb", [f"verb{i}t", f"geverb{i}t"] + junk)
    add("bringen", "verb", ["bringe", "bringst", "bringt", "brachte", "gebracht"] + junk)
    add("mitbringen", "verb", ["mitbringt", "mitgebracht", "mitzubringen", "bringt mit", "bringst mit", "brachte mit", "mit"] + junk)
    for i in range(30):
        add(f"mitverb{i}en", "verb", ["mit", f"verb{i}t mit"])       # "mit" is shared by many separable verbs
    add("sein", "verb", ["bin", "ist", "sind", "war", "gewesen", "sie"])
    add("sein", "pron", ["seine", "seinem"])
    add("werden", "verb", ["wird", "wurde", "geworden", "worden", "sein", "sie"])
    add("haben", "verb", ["hat", "hatte", "gehabt", "sein", "sie", "werden", "worden"])
    add("mit", "prep", [])
    add("sie", "pron", ["ihr", "ihnen"])
    add("machen", "verb", ["macht", "gemacht"] + junk)
    for i in range(8):
        add(f"x{i}machen", "verb", ["machen", f"macht x{i}"])
    add("Haus", "noun", ["hauses", "häuser", "häusern", "h"])
    db.commit()
    db.close()
    return f


class Links(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from subplayer_win.dictionary import Dictionary
        cls.tmp = tempfile.TemporaryDirectory()
        cls.d = Dictionary(make_dict(cls.tmp.name))

    def lemmas(self, w):
        return [(e.lemma, e.pos) for e in self.d.lookup(w)]

    def test_helper_verbs_open_their_own_entry(self):
        self.assertEqual(self.lemmas("worden"), [("werden", "verb")])
        self.assertEqual(self.lemmas("haben"), [("haben", "verb")])
        self.assertEqual(self.lemmas("gewesen"), [("sein", "verb")])
        self.assertEqual(self.lemmas("sein")[0][0], "sein")
        self.assertEqual({p for _, p in self.lemmas("sein")}, {"verb", "pron"})
        self.assertEqual(self.lemmas("sie"), [("sie", "pron")])
        self.assertEqual(self.lemmas("mit"), [("mit", "prep")])                # not mitbringen
        self.assertEqual(self.lemmas("machen"), [("machen", "verb")])          # not x0machen …
        self.assertEqual(self.lemmas("bringst"), [("bringen", "verb")])

    def test_forms_are_only_real_forms(self):
        base, forms, split = self.d.forms_of("Bringst")
        self.assertEqual(base, "bringen")
        self.assertEqual(forms, {"bringen", "bringe", "bringst", "bringt", "brachte", "gebracht"})
        self.assertFalse(split)
        _, forms, _ = self.d.forms_of("sein")
        self.assertIn("gewesen", forms)                                        # a true form of sein, kept by hand
        self.assertNotIn("sie", forms)
        self.assertNotIn("seine", forms)                                       # sein the verb, not the pronoun
        _, forms, _ = self.d.forms_of("werden")
        self.assertTrue({"worden", "geworden", "wird"} <= forms)
        self.assertNotIn("sein", forms)
        _, forms, _ = self.d.forms_of("Häuser")
        self.assertEqual(forms, {"haus", "hauses", "häuser", "häusern"})       # no single letters

    def test_separable_verbs(self):
        from subplayer_win import library
        base, forms, split = self.d.forms_of("mitbringen")
        self.assertEqual(base, "mitbringen")
        self.assertNotIn("mit", forms)
        self.assertEqual(split, {("bringt", "mit"), ("bringst", "mit"), ("brachte", "mit")})
        hit = lambda t: [t[a:b] for a, b in library.match_spans(t, forms, split)]
        self.assertEqual(hit("Bringst du bitte das Buch mit?"), ["Bringst", "mit"])
        self.assertEqual(hit("Er bringt es mit und geht."), ["bringt", "mit"])
        self.assertEqual(hit("Er bringt mit dem Auto die Kinder."), [])        # "mit" is a preposition here
        self.assertEqual(hit("Er bringt es, aber nicht mit."), [])             # another clause
        self.assertEqual(hit("Ich habe es mitgebracht."), ["mitgebracht"])
        self.assertEqual(self.d.separable_in("bringst", "Bringst du bitte das Buch mit?"), [("mitbringen", "bringst", "mit")])
        self.assertEqual(self.d.separable_in("mit", "Bringst du bitte das Buch mit?"), [("mitbringen", "bringst", "mit")])
        self.assertEqual(self.d.separable_in("bringt", "Er bringt mit dem Auto die Kinder."), [])

    def test_where_else_and_levels(self):
        from subplayer_win import library, subtitles
        from subplayer_win.levels import Levels
        with tempfile.TemporaryDirectory() as t:
            srt = Path(t) / "a.de.srt"
            srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nDie hier gewohnt haben, sind gestorben.\n\n"
                           "2\n00:00:03,000 --> 00:00:04,000\nSie bringt Blumen. Es ist geprüft worden.\n\n"
                           "3\n00:00:05,000 --> 00:00:06,000\nEr hat sie gebracht.\n", encoding="utf-8")
            it = library.Item(srt=srt, lang="de", video="", name="a")
            info = {}
            uses, n = library.find_uses("Bringst", "de", [it], self.d, info=info)
            self.assertEqual([u.index for u in uses], [1, 2])                 # not the line with "haben … sind"
            self.assertEqual(info["base"], "bringen")
            self.assertEqual(info["found"], {"bringt": 1, "gebracht": 1})
        lv = Levels()
        lv._tables["de"] = {"werden": 1, "verb0en": 6, "bringen": 1}
        self.assertEqual(lv.level("worden", "de", self.d), 1)                  # werden, not one of thousands of verbs
        self.assertEqual(lv.level("verb0t", "de", self.d), 6)


class Lessons(unittest.TestCase):
    def test_prompt_and_keeping(self):
        os.environ["SUBPLAYER_HOME"] = tempfile.mkdtemp()
        from subplayer_win import lessons, subtitles
        cues = subtitles.parse("1\n00:00:01,000 --> 00:00:02,000\nGuten Abend und\nwillkommen.\n\n2\n00:00:03,000 --> 00:00:04,000\nDas Wetter wird schön.\n")
        self.assertEqual(lessons.transcript(cues), "Guten Abend und willkommen. Das Wetter wird schön.")
        p = lessons.prompt("B1", "de", "Wetter.mp4", cues, ["Wetter", "schön", "Wetter"], "fa")
        for part in ("level B1", "German teacher", "Lückentext", "Umformung", "---LÖSUNGEN---", "Persian", "Words I am learning from this video: Wetter, schön",
                     "Guten Abend und willkommen. Das Wetter wird schön."):
            self.assertIn(part, p)
        en = lessons.prompt("C1", "en", "News.mp4", cues, [], "de")
        self.assertIn("Gap-fill", en)
        self.assertIn("---ANSWERS---", en)
        self.assertNotIn("Words I am learning", en)
        long = [type("C", (), {"text": "Wort " * 20})() for _ in range(2000)]
        self.assertLess(len(lessons.prompt("A2", "de", "x", long, [])), lessons.MAX_TRANSCRIPT + 4000)
        lessons.save("Mein Film: Teil 1.mp4", "de", "B1", "Text B1")
        lessons.save("Mein Film: Teil 1.mp4", "de", "C1", "Text C1")
        self.assertEqual(lessons.kept("Mein Film: Teil 1.mp4"), ["B1", "C1"])
        self.assertEqual(lessons.text("Mein Film: Teil 1.mp4", "C1"), "Text C1")
        self.assertEqual(lessons.all_lessons(), [("Mein Film: Teil 1.mp4", ["B1", "C1"])])
        lessons.save("Mein Film: Teil 1.mp4", "de", "B1", "  ")
        lessons.save("Mein Film: Teil 1.mp4", "de", "C1", "")
        self.assertEqual(lessons.kept("Mein Film: Teil 1.mp4"), [])
        self.assertEqual(lessons.all_lessons(), [])
        self.assertEqual(set(lessons.ASSISTANTS), {"chatgpt", "gemini", "deepseek", "grok"})


class Themes(unittest.TestCase):
    def test_themes(self):
        from subplayer_win import theme
        theme.apply("nebula")
        standard = theme.QSS
        self.assertEqual((theme.CYAN, theme.VIOLET, theme.MAGENTA, theme.BG), ("#3EF0FF", "#8B5CFF", "#FF4FD8", "#05040D"))
        self.assertEqual(theme.shade("#3EF0FF"), "#3EF0FF")
        self.assertGreaterEqual(len(theme.THEMES), 8)
        for key in theme.THEMES:
            theme.apply(key)
            self.assertEqual(theme.current(), (key, ""))
            self.assertEqual(theme.shade("#FFD166"), "#FFD166")               # gold of saved words stays
            self.assertEqual(theme.shade("#5BE38F"), "#5BE38F")               # A1 green stays
            self.assertEqual(theme.shade("#FFFFFF"), "#FFFFFF")
            r, g, b = (int(theme.BG[i:i + 2], 16) for i in (1, 3, 5))
            self.assertLess(max(r, g, b), 40)                                  # every theme is a dark theme
            self.assertEqual(theme.QSS.count("{"), standard.count("{"))
        theme.apply("ocean")
        self.assertEqual(theme.CYAN, "#6CCBFF")
        self.assertNotEqual(theme.QSS, standard)
        self.assertEqual(theme.shade("#3EF0FF"), "#6CCBFF")                   # the first accent takes the theme's colour
        theme.apply("ocean", "#FF8800")
        self.assertEqual(theme.current(), ("ocean", "#FF8800"))
        self.assertTrue(theme.CYAN.startswith("#FF"))
        theme.apply("no-such-theme", "red")
        self.assertEqual(theme.current(), ("nebula", ""))
        self.assertEqual(theme.QSS, standard)


if __name__ == "__main__":
    unittest.main()
