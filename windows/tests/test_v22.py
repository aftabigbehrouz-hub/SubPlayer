"""Windows 2.2: word levels, word search across videos, English sources, subtitle line times."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from subplayer_win import english, library, linkimport, subtitles   # noqa: E402
from subplayer_win.levels import NAMES, Levels                      # noqa: E402


class WordLevels(unittest.TestCase):
    def setUp(self):
        self.lv = Levels()

    def test_tables_are_bundled(self):
        self.assertGreater(len(self.lv.table("de")), 20000)
        self.assertGreater(len(self.lv.table("en")), 20000)

    def test_known_levels(self):
        self.assertEqual(NAMES[self.lv.level("warum", "de")], "A1")
        self.assertEqual(NAMES[self.lv.level("why", "en")], "A1")
        self.assertEqual(NAMES[self.lv.level("journey", "en")], "A2")
        self.assertEqual(NAMES[self.lv.level("reluctant", "en")], "B2")
        self.assertIn(NAMES[self.lv.level("Bilanz", "de")], ("C1", "C2"))

    def test_no_level_for_numbers_and_punctuation(self):
        self.assertEqual(self.lv.level("2026", "de"), 0)
        self.assertEqual(self.lv.level("–", "en"), 0)


class Library(unittest.TestCase):
    def test_scan_and_find_uses(self):
        with tempfile.TemporaryDirectory() as tmp:
            subs = Path(tmp) / "subs"
            vids = Path(tmp) / "Videos"
            subs.mkdir()
            vids.mkdir()
            (vids / "Film A.mp4").write_bytes(b"x")
            (subs / f"{subtitles.video_key('Film A.mp4')}.de.srt").write_text(subtitles.write([
                subtitles.Cue(0, 1000, "Warum gehst du?"), subtitles.Cue(1000, 2000, "Ich weiß nicht, warum.")]), encoding="utf-8")
            (vids / "Film B.mp4").write_bytes(b"x")
            (vids / "Film B.srt").write_text(subtitles.write([subtitles.Cue(0, 1000, "Darum! Warum nicht?"),
                                                              subtitles.Cue(1000, 2000, "Das ist der Grund.")]), encoding="utf-8")
            items = library.scan({"video_folders": [str(vids)]}, subs)
            self.assertEqual(sorted(i.name for i in items), ["Film A.mp4", "Film B.mp4"])
            self.assertTrue(all(i.video for i in items))
            uses, n = library.find_uses("warum", "de", items)
            self.assertEqual(n, 2)
            self.assertEqual(len(uses), 3)
            u = next(x for x in uses if x.text == "Darum! Warum nicht?")
            self.assertEqual(u.text[u.spans[0][0]:u.spans[0][1]], "Warum")
            phrase, _ = library.find_uses("weiß nicht", "de", items)
            self.assertEqual(len(phrase), 1)

    def test_vocabulary(self):
        cues = [subtitles.Cue(0, 1, "Das Haus ist alt. Das Haus ist schön."), subtitles.Cue(1, 2, "Ein altes Haus!")]
        voc = library.vocabulary(cues, "de", Levels())
        self.assertEqual(voc[0][:2], ("Haus", 3))
        self.assertTrue(all(lv >= 0 for _, _, lv in voc))


class EnglishSources(unittest.TestCase):
    RSS = """<rss><channel><item><title>News Words: Illusion</title><link>https://learningenglish.voanews.com/a/1.html</link>
    <pubDate>Thu, 13 Mar 2025 14:00:00 -0400</pubDate><description><![CDATA[<p>A word &amp; its use</p>]]></description></item>
    </channel></rss>"""

    def test_voa_feed(self):
        class R:
            text = self.RSS

            def raise_for_status(self):
                pass

        class S:
            def get(self, *a, **k):
                return R()
        f = english.voa_feed("/api/x", session=S())[0]
        self.assertEqual((f.channel, f.topic, f.title, f.date), ("VOA", "News Words", "News Words: Illusion", "13.03.2025"))
        self.assertEqual(f.description, "A word & its use")
        self.assertEqual(f.video(), "")                       # found on the page when downloading

    def test_voa_file_choice(self):
        urls = ["https://v/a.mp4?cb=1", "https://v/a_240p.mp4?cb=1", "https://v/a_480p.mp4?cb=1", "https://v/a_fullhd.mp4?cb=1"]
        self.assertEqual(max(urls, key=linkimport.score), "https://v/a_480p.mp4?cb=1")

    def test_shelves_have_no_youtube_only_series(self):
        self.assertFalse(any("Anna" in s.title for s in english.SHELVES))


class CueTimes(unittest.TestCase):
    def test_parse_and_format(self):
        from subplayer_win.dialogs import CueEditDialog as D
        self.assertEqual(D._parse("01:23.450"), 83450)
        self.assertEqual(D._parse("1:02:03,5"), 3723500)
        self.assertEqual(D._fmt(83450), "01:23.450")
        self.assertEqual(D._fmt(3723500), "1:02:03.500")
        with self.assertRaises(ValueError):
            D._parse("83 seconds")


if __name__ == "__main__":
    unittest.main()
