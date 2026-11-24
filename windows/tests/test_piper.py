"""Piper voice catalogue: parsing, malformed responses, safe download / cancel / remove, the chosen voice per language and
speech cache separation — without the network (a fake session answers)."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SUBPLAYER_HOME"] = tempfile.mkdtemp()

from subplayer_win import downloads, piper_catalog as pc, voice  # noqa: E402

MODEL = b"ONNX" * 5000
CONFIG = json.dumps({"audio": {"sample_rate": 22050}, "phoneme_type": "espeak"}).encode()
CARD = b"# Model card for eva_k (x_low)\n\n* Language: de_DE\n\n## Dataset\n\n* URL: https://example.org\n* License: CC0\n"


def entry(key, quality="x_low", files=None, family=None):
    fam, code = (family or key.split("_")[0]), key.split("-")[0]
    name = key.split("-")[1]
    d = f"{fam}/{code}/{name}/{quality}"
    return {"key": key, "name": name, "quality": quality, "num_speakers": 1, "speaker_id_map": {},
            "language": {"code": code, "family": fam, "region": code.split("_")[-1], "name_native": "Deutsch" if fam == "de" else fam,
                         "name_english": {"de": "German", "en": "English", "fr": "French"}.get(fam, fam), "country_english": "Germany"},
            "files": files if files is not None else {
                f"{d}/{key}.onnx": {"size_bytes": len(MODEL), "md5_digest": hashlib.md5(MODEL).hexdigest()},
                f"{d}/{key}.onnx.json": {"size_bytes": len(CONFIG), "md5_digest": hashlib.md5(CONFIG).hexdigest()},
                f"{d}/MODEL_CARD": {"size_bytes": len(CARD), "md5_digest": hashlib.md5(CARD).hexdigest()}},
            "aliases": []}


CATALOGUE = {k: entry(k, q) for k, q in (("de_DE-eva_k-x_low", "x_low"), ("de_DE-thorsten-high", "high"),
                                         ("en_US-lessac-medium", "medium"), ("fr_FR-siwis-low", "low"))}


class Resp:
    def __init__(self, body: bytes = b"", status=200, chunks=None, js=None):
        self.body, self.status_code, self._chunks, self._js = body, status, chunks, js
        self.headers = {"Content-Length": str(len(body))}
        self.text = body.decode("utf-8", "replace")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise IOError(f"HTTP {self.status_code}")

    def json(self):
        return self._js if self._js is not None else json.loads(self.body)

    def iter_content(self, n):
        yield from (self._chunks or [self.body[i:i + n] for i in range(0, len(self.body), n)])

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Session:
    """Answers like huggingface.co: the catalogue and the voice files (or what a test puts in .files)."""
    def __init__(self, catalogue=None, files=None):
        self.catalogue = CATALOGUE if catalogue is None else catalogue
        self.files = files or {}
        self.urls = []

    def get(self, url, **k):
        self.urls.append(url)
        if url == pc.CATALOGUE_URL:
            return self.catalogue if isinstance(self.catalogue, Resp) else Resp(js=self.catalogue)
        rel = url[len(pc.BASE) + 1:]
        if rel in self.files:
            v = self.files[rel]
            return v if isinstance(v, Resp) else Resp(v)
        if rel.endswith(".onnx"):
            return Resp(MODEL)
        if rel.endswith(".onnx.json"):
            return Resp(CONFIG)
        if rel.endswith("MODEL_CARD"):
            return Resp(CARD)
        return Resp(b"", 404)


def fresh_home():
    os.environ["SUBPLAYER_HOME"] = tempfile.mkdtemp()


class Catalogue(unittest.TestCase):
    def setUp(self):
        fresh_home()

    def test_parse_all_languages_and_qualities(self):
        vs = pc.parse_catalogue(CATALOGUE)
        self.assertEqual({v.family for v in vs}, {"de", "en", "fr"})
        self.assertEqual({v.quality for v in vs}, {"x_low", "high", "medium", "low"})
        de = [v for v in vs if v.family == "de"]
        self.assertEqual([v.quality for v in de], ["x_low", "high"])            # sorted by quality inside a voice name
        eva = de[0]
        self.assertEqual((eva.name, eva.code, eva.language, eva.size_bytes), ("eva_k", "de_DE", "German", len(MODEL) + len(CONFIG) + len(CARD)))
        self.assertTrue(eva.model_rel.endswith("de_DE-eva_k-x_low.onnx") and eva.config_rel.endswith(".onnx.json"))
        self.assertTrue(eva.sample_url.endswith("de/de_DE/eva_k/x_low/samples/speaker_0.mp3"))

    def test_malformed(self):
        for bad in ([], "x", None, {}, {"a": 1}, {"de_DE-x-low": {"files": {}}}):
            with self.assertRaises(pc.CatalogueError):
                pc.parse_catalogue(bad)
        cat = dict(CATALOGUE)
        cat["../evil"] = entry("de_DE-evil-low")
        cat["de_DE-evil-low"] = entry("de_DE-evil-low", files={"../../x.onnx": {"size_bytes": 1}, "../../x.onnx.json": {"size_bytes": 1}})
        cat["de_DE-abs-low"] = entry("de_DE-abs-low", files={"C:/x.onnx": {}, "C:/x.onnx.json": {}})
        cat["de_DE-split-low"] = entry("de_DE-split-low", files={"de/a/x.onnx": {}, "other/x.onnx.json": {}})
        cat["de_DE-broken-low"] = "not a voice"
        keys = {v.key for v in pc.parse_catalogue(cat)}
        self.assertEqual(keys, set(CATALOGUE))                                  # only the good voices, nothing raised

    def test_fetch_saves_a_copy_for_offline(self):
        voices, _, from_copy = pc.fetch_catalogue(Session())
        self.assertEqual((len(voices), from_copy), (4, False))
        self.assertEqual(len(pc.cached_catalogue()), 4)
        offline = Session(catalogue=Resp(b"", 503))
        voices, _, from_copy = pc.fetch_catalogue(offline)
        self.assertEqual((len(voices), from_copy), (4, True))
        with self.assertRaises(pc.CatalogueError):
            pc.fetch_catalogue(offline, offline_ok=False)
        with self.assertRaises(pc.CatalogueError):                              # an HTML error page instead of JSON
            fresh_home()
            pc.fetch_catalogue(Session(catalogue=Resp(b"<html>rate limited</html>")))

    def test_licence(self):
        self.assertEqual(pc.licence_of(CARD.decode()), "CC0")
        self.assertEqual(pc.licence_of("* License: [CC BY 4.0](https://x)"), "[CC BY 4.0](https://x)")
        self.assertEqual(pc.licence_of("no licence here"), "")
        eva = pc.parse_catalogue(CATALOGUE)[0]
        self.assertIn("CC0", pc.card_text(eva, Session()))


class Install(unittest.TestCase):
    def setUp(self):
        fresh_home()
        self.vs = {v.key: v for v in pc.parse_catalogue(CATALOGUE)}

    def test_install_and_remove(self):
        eva = self.vs["de_DE-eva_k-x_low"]
        seen = []
        m = pc.install(eva, lambda d, t: seen.append((d, t)), session=Session())
        self.assertEqual(m.read_bytes(), MODEL)
        self.assertTrue(pc.is_installed(eva))
        self.assertEqual(seen[-1], (eva.size_bytes, eva.size_bytes))
        self.assertEqual(list(pc.installed_models()), ["de_DE-eva_k-x_low"])
        self.assertFalse(list(eva.folder.glob("*.part")))
        self.assertTrue(pc.voice_root().resolve() in m.resolve().parents)
        self.assertTrue(pc.remove("de_DE-eva_k-x_low"))
        self.assertIsNone(pc.model_path("de_DE-eva_k-x_low"))
        self.assertFalse((pc.voice_root() / "de").exists())                     # empty folders tidied, the root kept
        self.assertTrue(pc.voice_root().exists())
        self.assertFalse(pc.remove("de_DE-eva_k-x_low"))
        self.assertFalse(pc.remove("../../etc"))

    def test_cancel_leaves_nothing(self):
        eva = self.vs["de_DE-eva_k-x_low"]
        n = {"i": 0}

        def cancelled():
            n["i"] += 1
            return n["i"] > 2
        with self.assertRaises(InterruptedError):
            pc.install(eva, cancelled=cancelled, session=Session(files={eva.model_rel: Resp(MODEL, chunks=[MODEL[:9000], MODEL[9000:]])}))
        self.assertIsNone(pc.model_path(eva.key))
        self.assertFalse(list(pc.voice_root().rglob("*.part")))
        self.assertFalse(list(pc.voice_root().rglob("*.onnx")))

    def test_damaged_or_cut_off_download(self):
        eva = self.vs["de_DE-eva_k-x_low"]
        for bad in (Resp(MODEL[:-10]), Resp(b"X" * len(MODEL)), Resp(b"", 500)):
            with self.assertRaises(IOError):
                pc.install(eva, session=Session(files={eva.model_rel: bad}))
            self.assertIsNone(pc.model_path(eva.key))
            self.assertFalse(list(pc.voice_root().rglob("*.part")))
        with self.assertRaises(IOError):                                         # a config that isn't JSON
            bad_cfg = b"not json" + b" " * (len(CONFIG) - 8)
            cat = dict(CATALOGUE)
            cat[eva.key] = entry(eva.key)
            cat[eva.key]["files"][eva.config_rel] = {"size_bytes": len(bad_cfg), "md5_digest": hashlib.md5(bad_cfg).hexdigest()}
            v = {x.key: x for x in pc.parse_catalogue(cat)}[eva.key]
            pc.install(v, session=Session(files={eva.config_rel: bad_cfg}))
        self.assertIsNone(pc.model_path(eva.key))

    def test_filters(self):
        vs = pc.parse_catalogue(CATALOGUE)
        self.assertEqual([v.key for v in vs if v.family == "de" and v.quality == "high"], ["de_DE-thorsten-high"])
        self.assertEqual(pc.voice_family("en_US-lessac-medium"), "en")


class ChosenVoice(unittest.TestCase):
    def setUp(self):
        fresh_home()
        self.vs = {v.key: v for v in pc.parse_catalogue(CATALOGUE)}

    def test_old_settings_and_no_voice(self):
        self.assertIsNone(voice.piper_model({}, "de"))
        self.assertFalse(voice.piper_ready("de", {}))
        self.assertEqual([a.id for a in voice.piper_missing("de", {})], ["piper-win", "voice-de"])
        self.assertEqual([a.id for a in voice.piper_missing("fr", {})], ["piper-win"])     # other languages: catalogue voices

    def _legacy(self, lang):
        a = voice.PIPER_VOICES[lang]
        p = downloads.ready_path(a)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"legacy")
        return p

    def test_choice_fallbacks_and_cache_separation(self):
        legacy = self._legacy("de")
        self.assertEqual(voice.piper_model({}, "de"), ("voice-de", legacy))          # as before: the bundled voice, same cache id
        pc.install(self.vs["de_DE-eva_k-x_low"], session=Session())
        pc.install(self.vs["fr_FR-siwis-low"], session=Session())
        st = {"voice_piper_de": "de_DE-eva_k-x_low"}
        vid, m = voice.piper_model(st, "de")
        self.assertTrue(vid.startswith("de_DE-eva_k-x_low@") and m.name == "de_DE-eva_k-x_low.onnx")
        self.assertEqual(voice.piper_model({"voice_piper_de": "de_DE-gone-low"}, "de")[0], "voice-de")   # removed → bundled
        self.assertEqual(voice.piper_model({}, "fr")[1].name, "fr_FR-siwis-low.onnx")                   # any voice of the language
        self.assertIsNone(voice.piper_model({}, "it"))
        self.assertIsNone(voice.piper_model({"voice_piper_de": "../../evil"}, "it"))
        t = "Guten Tag"
        a = voice._cache("piper", voice.piper_model(st, "de")[0], t, False, "wav")
        b = voice._cache("piper", voice.piper_model({}, "de")[0], t, False, "wav")
        c = voice._cache("piper", voice.piper_model({}, "fr")[0], t, False, "wav")
        self.assertEqual(len({a, b, c}), 3)

    def test_piper_file_runs_the_chosen_model(self):
        pc.install(self.vs["de_DE-eva_k-x_low"], session=Session())
        exe = downloads.ready_path(voice.PIPER)
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_bytes(b"exe")
        calls = []

        def fake_run(cmd, **k):
            calls.append(cmd)
            Path(cmd[cmd.index("--output_file") + 1]).write_bytes(b"RIFF" + b"\0" * 500)
            return mock.Mock(returncode=0, stderr=b"")
        with mock.patch("subprocess.run", fake_run):
            st = {"voice_piper_de": "de_DE-eva_k-x_low", "voice_engine": "piper"}
            f1 = voice.audio_file(st, "Hallo Welt", "de")
            f2 = voice.audio_file(st, "Hallo Welt", "de")                          # from the cache: Piper runs once
            self.assertEqual(f1, f2)
            self.assertEqual(len(calls), 1)
            self.assertTrue(calls[0][calls[0].index("--model") + 1].endswith("de_DE-eva_k-x_low.onnx"))
            self.assertEqual(calls[0][calls[0].index("--length_scale") + 1], "1.0")
            voice.audio_file(st, "Hallo Welt", "de", slow=True)
            self.assertEqual(calls[1][calls[1].index("--length_scale") + 1], "1.3")
        with mock.patch("subprocess.run", lambda cmd, **k: mock.Mock(returncode=1, stderr=b"Unsupported phoneme type")):
            with self.assertRaises(IOError) as e:
                voice.piper_file("Neu", "de", settings=st)
            self.assertIn("newer Piper", str(e.exception))

    def test_engine_missing(self):
        pc.install(self.vs["de_DE-eva_k-x_low"], session=Session())
        st = {"voice_piper_de": "de_DE-eva_k-x_low", "voice_engine": "piper"}
        self.assertFalse(voice.piper_ready("de", st))                             # the voice alone isn't enough
        with self.assertRaises(FileNotFoundError):
            voice.audio_file(st, "Hallo", "de")


if __name__ == "__main__":
    unittest.main()
