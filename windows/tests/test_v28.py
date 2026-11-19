import json
import os
import re
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SUBPLAYER_HOME"] = tempfile.mkdtemp()

from subplayer_win import wordbook  # noqa: E402

ITEM = {"id": 1, "text": "beziffert", "lemma": "beziffern", "article": "", "ipa": "", "english": "estimated", "persian": "تخمین زدن",
        "lang": "de", "say": "beziffern", "a": wordbook.akey("beziffern", "de"), "level": "C2", "cat": "verb",
        "sentence": "So beziffert etwa das Haushaltsbüro die Kosten.", "sa": wordbook.akey("So beziffert etwa das Haushaltsbüro die Kosten.", "de"),
        "video": "ZDF.mp4", "time": "0:32", "saved": "2026-11-19", "reviews": 0, "dict": {},
        "examples": [{"de": "Die Versicherung beziffert den Schaden.", "en": "", "fa": "", "a": wordbook.akey("Die Versicherung beziffert den Schaden.", "de")}],
        "cols": [{"p": "etwas auf einen Betrag beziffern", "m": "", "ex": "", "a": wordbook.akey("etwas auf einen Betrag beziffern", "de"), "xa": ""}]}


class WordBook(unittest.TestCase):
    def test_wanted(self):
        self.assertEqual(len(wordbook.wanted([ITEM], True, False, False)), 1)
        self.assertEqual(len(wordbook.wanted([ITEM], True, True, False)), 3)
        self.assertEqual(len(wordbook.wanted([ITEM], True, True, True)), 4)
        self.assertEqual(wordbook.wanted([ITEM], False, False, False), {})

    def test_html_carries_data_and_audio(self):
        h = wordbook.build_html([ITEM], {ITEM["a"]: b"ID3fake"}, "My Words")
        data = json.loads(re.search(r"const W=(.*?); const A=", h).group(1).replace("<\\/", "</"))
        self.assertEqual(data[0]["persian"], "تخمین زدن")
        audio = json.loads(re.search(r"const A=(.*?);\n", h).group(1))
        self.assertEqual(list(audio), [ITEM["a"]])
        for tab in ("Words", "Sentences", "Collocations", "Flashcards"):
            self.assertIn(f'"{tab}"', h)

    def test_no_audio_when_nothing_reachable(self):
        from subplayer_win import voice
        real = voice.audio_file
        voice.audio_file = lambda *a, **k: (_ for _ in ()).throw(IOError("403"))
        try:
            clips, note = wordbook.make_audio({"voice_engine": "edge"}, wordbook.wanted([ITEM] * 3, True, True, True))
        finally:
            voice.audio_file = real
        self.assertEqual(clips, {})
        self.assertIn("403", note)

    def test_script_closing_tag_cannot_break_out(self):
        bad = dict(ITEM, english="</script><b>x</b>")
        h = wordbook.build_html([bad], {})
        self.assertEqual(h.count("</script>"), 1)


if __name__ == "__main__":
    unittest.main()
