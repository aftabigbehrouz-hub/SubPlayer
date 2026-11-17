"""2.5: the local AI teacher (Ollama) — model choice, prompts, answers and the streaming client (against a stand-in server)."""
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("SUBPLAYER_HOME", tempfile.mkdtemp())

from subplayer_win import ollama  # noqa: E402


def m(name, size):
    return {"name": name, "details": {"parameter_size": size}}


class ModelChoice(unittest.TestCase):
    def test_the_users_models_rank_below_a_real_teacher(self):
        theirs = [m("deepseek-v2.5:latest", "236B"), m("Keyvan/german-ocr-3:latest", "4B"), m("Keyvan/german-text-3.1:latest", "4B"),
                  m("Keyvan/german-ocr:latest", "4B"), m("starling-lm:7b", "7B"), m("phi:latest", "3B"), m("billy/billy:latest", "7B"),
                  m("mannix/starling-lm-10.7b:latest", "10.7B"), m("caplette776/glubbot1.2-132m:latest", "132M")]
        good = [m("gemma3:12b", "12.2B"), m("gemma3:4b", "4.3B"), m("qwen3:8b", "8.2B")]
        for ram in (8, 16, 32):
            top = ollama.best_installed(theirs + good, ram)
            self.assertIn(top.split(":")[0], ("gemma3", "qwen3"), (ram, top))
        self.assertEqual(ollama.best_installed(theirs + good, 16), "gemma3:12b")
        self.assertEqual(ollama.best_installed(theirs + good, 8), "gemma3:4b")
        for x in theirs:                                       # none of them is a good German teacher
            self.assertLess(ollama.score(x, 16), 60, x["name"])
        self.assertEqual(ollama.score(m("Keyvan/german-ocr-3:latest", "4B"), 16), 0)     # an OCR model can't teach
        self.assertLess(ollama.score(m("deepseek-v2.5:latest", "236B"), 64), 20)         # far too big for a PC

    def test_embedding_models_are_never_chosen(self):
        self.assertEqual(ollama.best_installed([m("nomic-embed-text:latest", "137M")], 16), "")

    def test_suggestion_by_memory(self):
        self.assertEqual(ollama.suggestion_for(7.8).name, "gemma3:4b")
        self.assertEqual(ollama.suggestion_for(15.7).name, "gemma3:12b")     # a "16 GB" PC
        self.assertEqual(ollama.suggestion_for(12).name, "qwen3:8b")
        self.assertEqual(ollama.suggestion_for(64).name, "gemma3:12b")       # the 15 GB model only on purpose


class Prompts(unittest.TestCase):
    def test_word_prompt_asks_for_collocations_and_level(self):
        q = ollama.word_prompt("brachte", "bringen", "Er brachte die Kinder zur Schule.", "de", "B2", "fa")
        for s in ("collocations", "8 typical collocations", "level B2", "Persian", "Perfekt", "„brachte“", "bringen", "JSON"):
            self.assertIn(s, q)

    def test_english_video(self):
        q = ollama.word_prompt("run", "run", "They run a shop.", "en", "C1", "de")
        self.assertIn("English word", q)
        self.assertIn("German", q)              # explained in German
        self.assertIn("phrasal", ollama.sentence_prompt("He gave up.", "en", "en", "B2"))
        self.assertIn("Akkusativ", ollama.sentence_prompt("Ich sehe den Hund.", "de", "en", "B1"))

    def test_check_and_ask(self):
        q = ollama.check_prompt("Wetter", "Bei schöne Wetter …", "de", "en", "B1")
        self.assertIn('"corrected"', q)
        self.assertIn("score", q)
        a = ollama.ask_prompt("Ist das formell?", "Wetter", "Das Wetter ist gut.", "Tagesschau", "de", "en", "B1")
        self.assertIn("Tagesschau", a)
        self.assertIn("Ist das formell?", a)

    def test_lesson_context(self):
        self.assertEqual(ollama.lesson_ctx("x" * 100), 8192)
        self.assertEqual(ollama.lesson_ctx("x" * 300000), 32768)


class Answers(unittest.TestCase):
    def test_parse_json(self):
        self.assertEqual(ollama.parse_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(ollama.parse_json('Here you go: {"a": [1, 2]} hope it helps'), {"a": [1, 2]})
        self.assertEqual(ollama.parse_json("no json"), {})
        self.assertEqual(ollama.parse_json("[1, 2]"), {})

    def test_as_list(self):
        self.assertEqual(ollama.as_list("a; b\nc"), ["a", "b", "c"])
        self.assertEqual(ollama.as_list(None), [])

    def test_thinking_is_hidden(self):
        v = ollama.Client.visible
        self.assertEqual(v("<think>x</think>Hallo"), "Hallo")
        self.assertEqual(v("Hallo <think>still thinking"), "Hallo ")
        self.assertEqual(v("Hallo <thi"), "Hallo ")              # a tag that is still arriving
        self.assertEqual(v("Hallo"), "Hallo")

    def test_cache(self):
        c = ollama.Cache()
        k = ollama.Cache.key("gemma3:4b", "de", "Wetter", "B1", "en")
        c.put(k, {"meaning": "weather"})
        self.assertEqual(ollama.Cache().get(k)["meaning"], "weather")


CHUNKS = ["<thi", "nk>hmm</th", "ink>Das ", "ist ", "gut."]


class Fake(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        body = {"/api/version": {"version": "0.12.9"}, "/api/tags": {"models": [m("gemma3:4b", "4.3B")]}}[self.path]
        b = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Fake.seen.append((self.path, d))
        self.send_response(200)
        self.end_headers()
        if self.path == "/api/pull":
            rows = [{"status": "pulling manifest"}, {"status": "downloading", "total": 100, "completed": 50},
                    {"status": "downloading", "total": 100, "completed": 100}, {"status": "success"}]
            if d["model"] == "nope":
                rows = [{"error": "pull model manifest: file does not exist"}]
        else:
            rows = [{"message": {"content": c}, "done": False} for c in CHUNKS] + [{"message": {"content": ""}, "done": True}]
        for r in rows:
            self.wfile.write((json.dumps(r) + "\n").encode())


class ClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_version_models_pull(self):
        c = ollama.Client(self.url)
        self.assertEqual(c.version(), "0.12.9")
        self.assertEqual(c.models()[0]["name"], "gemma3:4b")
        steps = []
        c.pull("gemma3:4b", lambda done, total, status: steps.append((done, total)))
        self.assertIn((100, 100), steps)
        with self.assertRaises(ollama.OllamaError):
            c.pull("nope")

    def test_chat_streams_without_thinking(self):
        c = ollama.Client(self.url, "gemma3:4b")
        pieces = []
        out = c.chat("Hallo", "teacher", json_mode=True, on_text=pieces.append, ctx=16000)
        self.assertEqual(out, "Das ist gut.")
        self.assertEqual("".join(pieces), "Das ist gut.")
        path, body = Fake.seen[-1]
        self.assertEqual(path, "/api/chat")
        self.assertIs(body["think"], False)
        self.assertEqual(body["format"], "json")
        self.assertEqual(body["options"]["num_ctx"], 16000)
        self.assertEqual(body["messages"][0]["role"], "system")

    def test_not_running_and_no_model(self):
        with self.assertRaises(ollama.OllamaError) as e:
            ollama.Client("http://127.0.0.1:9", "gemma3:4b").chat("x")
        self.assertIn("not running", str(e.exception))
        with self.assertRaises(ollama.OllamaError):
            ollama.Client(self.url, "").chat("x")


if __name__ == "__main__":
    unittest.main()
