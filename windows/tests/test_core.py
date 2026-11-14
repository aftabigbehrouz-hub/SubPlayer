"""Tests for the Windows core: licence, sync merge + JSON (shared with Android), word store, subtitles, practice."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["SUBPLAYER_HOME"] = tempfile.mkdtemp()

from subplayer_win import licence, sync, subtitles, practice, syncer  # noqa: E402
from subplayer_win.store import WordStore, Progress, SavedWord, Example, review, INTERVAL_DAYS, DAY  # noqa: E402
from subplayer_win.dictionary import Dictionary, normalize  # noqa: E402

# made by licence-tool/make_activation_code.py for device AB12C-DE34F (same vector as the Android test)
PC_CODE = ("KNIDC7CBIIYTEQZNIRCTGNCGPRKGK43UEBBHK6LFOIQNROOZQTNYY.GBCQEIIAQWA6CMMWEK3NKNQRRQLUY2FTDQLUFPDQFMAATELEYSPQ6K63N33QE"
           "ICD7AXGWVB74A5P7DAJDD7TIY2NL3ZRCEPMEJMEPNIIJ3VRS4QEUU")
NOW = 1_800_000_000_000


def W(uid, text, updated, box=0, lang="de"):
    return {"uid": uid, "text": text, "lemma": text, "article": "", "ipa": "", "english": "", "persian": "", "sentence": "",
            "video_name": "video.mp4", "start_ms": 0, "end_ms": 1000, "created": 1, "reviews": 0, "correct": 0, "box": box,
            "due": 0, "last_review": 0, "lang": lang, "updated": updated}


class LicenceTest(unittest.TestCase):
    def test_same_codes_as_android(self):
        self.assertEqual("Test Buyer علی", licence.verify(PC_CODE, "AB12C-DE34F"))
        self.assertEqual("Test Buyer علی", licence.verify(" " + PC_CODE.lower() + "\n", "ab12c-de34f"))
        self.assertIsNone(licence.verify(PC_CODE, "ZZZZZ-ZZZZZ"))
        self.assertIsNone(licence.verify("A" + PC_CODE[1:], "AB12C-DE34F"))
        self.assertIsNone(licence.verify("garbage", "AB12C-DE34F"))

    def test_device_code_format(self):
        c = licence.code_for("4c4c4544-0042-3510-8051-b4c04f4a4d32")
        self.assertRegex(c, r"^[A-Z2-7]{5}-[A-Z2-7]{5}$")
        self.assertEqual(c, licence.code_for("4c4c4544-0042-3510-8051-b4c04f4a4d32"))
        self.assertNotEqual(c, licence.code_for("other"))

    def test_trial(self):
        d = licence.DAY
        self.assertEqual(10, licence.trial_days_left(NOW, NOW, 0))
        self.assertEqual(1, licence.trial_days_left(NOW, NOW + 9 * d + 1, 0))
        self.assertEqual(0, licence.trial_days_left(NOW, NOW + 10 * d, 0))
        self.assertEqual(0, licence.trial_days_left(NOW, NOW + d, NOW + 3 * d))   # clock turned back


class MergeTest(unittest.TestCase):
    def test_newest_wins_any_order(self):
        a = sync.SyncDoc(words={"1": W("1", "Haus", 100, box=2)})
        b = sync.SyncDoc(words={"1": W("1", "Haus", 200, box=5)})
        self.assertEqual(5, sync.merge(a, b, NOW).words["1"]["box"])
        self.assertEqual(5, sync.merge(b, a, NOW).words["1"]["box"])

    def test_tombstones(self):
        dele = sync.SyncDoc(deleted={"1": NOW - 1000})
        self.assertNotIn("1", sync.merge(dele, sync.SyncDoc(words={"1": W("1", "Haus", NOW - 5000)}), NOW).words)
        self.assertIn("1", sync.merge(dele, sync.SyncDoc(words={"1": W("1", "Haus", NOW - 10)}), NOW).words)
        old = sync.merge(sync.SyncDoc(deleted={"x": NOW - 121 * 86_400_000, "y": NOW - 1}), sync.SyncDoc(), NOW)
        self.assertEqual({"y"}, set(old.deleted))

    def test_examples_follow_word_and_progress(self):
        e = {"uid": "e1", "word_uid": "1", "de": "Das Haus ist groß.", "en": "", "fa": "", "created": 1, "updated": 1}
        m = sync.merge(sync.SyncDoc(examples={"e1": e}, deleted={"1": NOW - 1}),
                       sync.SyncDoc(words={"1": W("1", "Haus", NOW - 100)}, examples={"e1": e}), NOW)
        self.assertEqual({}, m.words)
        self.assertEqual({}, m.examples)
        p = sync.merge(sync.SyncDoc(streak=4, last_day=100, today=3), sync.SyncDoc(streak=5, last_day=100, today=1), NOW)
        self.assertEqual((5, 100, 3), (p.streak, p.last_day, p.today))

    def test_json_round_trip_and_android_shape(self):
        d = sync.SyncDoc(words={"1": W("1", "Mädchen", 5), "2": W("2", "house", 6, lang="en")},
                         examples={"e": {"uid": "e", "word_uid": "1", "de": "Das Mädchen lacht.", "en": "The girl laughs.",
                                         "fa": "دختر می‌خندد.", "created": 3, "updated": 4}},
                         deleted={"z": 77}, subs={"v|de": {"key": "v", "lang": "de", "srt": "1\n00:00:00,000 --> 00:00:01,000\nHallo\n", "updated": 9}},
                         streak=3, last_day=20000, today=7)
        js = sync.to_json(d)
        self.assertEqual(d, sync.from_json(js))
        o = json.loads(js)
        self.assertEqual({"app", "version", "words", "examples", "deleted", "subtitles", "progress"}, set(o))
        self.assertEqual(set(sync.WORD_KEYS), set(o["words"][0]))
        self.assertEqual(sync.SyncDoc(), sync.from_json(""))


class FakeGist:
    def __init__(self):
        self.files = {}

    def find(self):
        return next(iter(self.files), None)

    def create(self, content):
        self.files["g1"] = content
        return "g1"

    def read(self, gid):
        return self.files.get(gid, "")

    def write(self, gid, content):
        self.files[gid] = content


class StoreAndSyncTest(unittest.TestCase):
    def test_two_devices_meet_in_the_middle(self):
        tmp = Path(tempfile.mkdtemp())
        pc = WordStore(tmp / "pc.db"); phone = WordStore(tmp / "phone.db")
        pc_p = Progress(tmp / "pc.json"); phone_p = Progress(tmp / "phone.json")
        (tmp / "pcsubs").mkdir(); (tmp / "phonesubs").mkdir()
        gist = FakeGist()

        wid = pc.insert(SavedWord(text="Haus", lemma="Haus", sentence="Das Haus ist alt.", video_name="film.mp4", lang="de"))
        pc.add_examples(wid, practice.parse_sentences("DE: Das Haus ist groß. | EN: The house is big. | FA: خانه بزرگ است."))
        (tmp / "pcsubs" / "film.de.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHallo\n", encoding="utf-8")
        pc_p.record()
        gid, n = syncer.sync_now("t", None, pc, pc_p, tmp / "pcsubs", client=gist)
        self.assertEqual(1, n)

        gid2, n2 = syncer.sync_now("t", None, phone, phone_p, tmp / "phonesubs", resolve_video=lambda name: "C:/v/" + name, client=gist)
        self.assertEqual(gid, gid2)
        w = phone.all()[0]
        self.assertEqual(("Haus", "C:/v/film.mp4"), (w.text, w.video_uri))
        self.assertEqual("Das Haus ist groß.", phone.examples(w.id)[0].de)
        self.assertTrue((tmp / "phonesubs" / "film.de.srt").exists())
        self.assertEqual(1, phone_p.today_count)

        # review on the phone, delete on... nothing yet; then delete on the PC → gone everywhere
        import time
        time.sleep(0.01)
        phone.update(review(w, True, NOW))
        syncer.sync_now("t", gid, phone, phone_p, tmp / "phonesubs", client=gist)
        syncer.sync_now("t", gid, pc, pc_p, tmp / "pcsubs", client=gist)
        self.assertEqual(1, pc.all()[0].box)
        time.sleep(0.01)
        pc.delete(pc.all()[0].id)
        syncer.sync_now("t", gid, pc, pc_p, tmp / "pcsubs", client=gist)
        syncer.sync_now("t", gid, phone, phone_p, tmp / "phonesubs", client=gist)
        self.assertEqual([], phone.all())
        self.assertEqual([], phone.examples(w.id))

    def test_review_steps(self):
        w = SavedWord(text="a", lemma="a", sentence="")
        r = review(w, True, NOW)
        self.assertEqual((1, NOW + INTERVAL_DAYS[1] * DAY), (r.box, r.due))
        r2 = review(r, False, NOW)
        self.assertEqual((0, NOW + 10 * 60 * 1000, 2, 1), (r2.box, r2.due, r2.reviews, r2.correct))


class SubtitleTest(unittest.TestCase):
    def test_parse_write(self):
        cues = subtitles.parse("1\n00:00:01,000 --> 00:00:02,500\nHallo <i>Welt</i>\n\n2\n00:00:03.000 --> 00:00:04.000\nZwei\n")
        self.assertEqual([(1000, 2500, "Hallo Welt"), (3000, 4000, "Zwei")], [(c.start_ms, c.end_ms, c.text) for c in cues])
        self.assertEqual(cues, subtitles.parse(subtitles.write(cues)))
        self.assertEqual(0, subtitles.index_at(cues, 1500))
        self.assertEqual(-1, subtitles.index_at(cues, 2700))

    def test_sentence_range(self):
        C = subtitles.Cue
        cues = [C(0, 1000, "Ich glaube,"), C(1200, 2000, "dass wir heute"), C(2100, 3000, "ins Kino gehen."), C(3100, 4000, "Gut.")]
        self.assertEqual((0, 2), subtitles.sentence_range(cues, 1))
        self.assertEqual("Ich glaube, dass wir heute ins Kino gehen.", subtitles.sentence_text(cues, 0, 2))
        no_punct = [C(0, 1000, "a b"), C(1100, 2000, "c d")]
        self.assertEqual((1, 1), subtitles.sentence_range(no_punct, 1))

    def test_video_key_matches_android(self):
        self.assertEqual("Tagesschau_20_00_Uhr", subtitles.video_key("Tagesschau 20:00 Uhr.mp4"))
        self.assertEqual("Mädchen-film.v2", subtitles.video_key("Mädchen-film.v2.mkv"))


class PracticeTest(unittest.TestCase):
    def test_parse_formats(self):
        e = practice.parse_sentences("1. DE: Ich gehe nach Hause. | EN: I go home. | FA: من به خانه می‌روم.")
        self.assertEqual(("Ich gehe nach Hause.", "I go home.", "من به خانه می‌روم."), (e[0].de, e[0].en, e[0].fa))
        en = practice.parse_sentences("DE: Das Haus ist groß.\nEN: The house is big.\nDE: Ich gehe heim.\nEN: I go home.", primary="en")
        self.assertEqual(["The house is big.", "I go home."], [x.de for x in en])
        self.assertEqual("Das Haus ist groß.", en[0].en)

    def test_cloze_and_dictation(self):
        w = SavedWord(text="ging", lemma="gehen", sentence="")
        c = practice.cloze(w, "Gestern ging ich früh.")
        self.assertEqual(("Gestern ", "ging", " ich früh."), (c.before, c.answer, c.after))
        self.assertTrue(practice.same("Straße", "strasse"))
        marks, score = practice.dictation("Ich gehe heute nach Hause.", "ich gehe nach hause")
        self.assertEqual([True, True, False, True, True], [o for _, o in marks])
        self.assertEqual(80, score)


class DictionaryTest(unittest.TestCase):
    def test_lookup_on_a_tiny_db(self):
        f = Path(tempfile.mkdtemp()) / "d.db"
        db = sqlite3.connect(f)
        db.executescript("CREATE TABLE entry(id INTEGER PRIMARY KEY, lemma TEXT, pos TEXT, gender TEXT, ipa TEXT, hyph TEXT, audio TEXT, data TEXT);"
                         "CREATE TABLE lookup(key TEXT, id INTEGER, PRIMARY KEY(key,id)) WITHOUT ROWID;")
        db.execute("INSERT INTO entry VALUES(1,'gehen','verb','','ˈɡeːən','ge·hen','',?)",
                   (json.dumps({"posDe": "Verb", "senses": [{"de": "sich fortbewegen", "ex": ["[1] Ich gehe."]}], "en": ["to go"], "fa": ["رفتن"]}),))
        db.execute("INSERT INTO entry VALUES(2,'Gehen','name','','','','',?)", (json.dumps({"posDe": "Name"}),))
        db.executemany("INSERT INTO lookup VALUES(?,?)", [("ging", 1), ("gehen", 1), ("gehen", 2)])
        db.commit(); db.close()
        d = Dictionary(f)
        r = d.lookup("„ging“,")
        self.assertEqual("gehen", r[0].lemma)
        self.assertEqual(["to go"], r[0].english)
        self.assertEqual("gehen", d.lookup("gehen")[0].lemma)    # names ranked last
        self.assertEqual("Tom's", normalize("Tom's,"))


if __name__ == "__main__":
    unittest.main()
