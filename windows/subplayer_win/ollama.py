"""Local AI teacher with Ollama (https://ollama.com) — free, private, works offline once a model is downloaded.

SubPlayer talks to the Ollama program on this PC (http://127.0.0.1:11434) and uses it as a language teacher:
  • word coach: meaning in this sentence, forms, 8 collocations, 5 example sentences at your level, prepositions, synonyms,
    a memory tip — the sentences can be added to the word for review;
  • sentence explained: translation, word order, cases, tenses, separable verbs, idioms, and 3 sentences on the same pattern;
  • check my sentence: write your own sentence with the word, the teacher corrects and explains;
  • ask the teacher: any question about the word, the line or the video;
  • AI lesson / TestDaF / IELTS set written straight into the lesson box (no copy-paste).
Results of the word coach are kept (per model, word and level), so a second look is instant.
"""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass

import requests

from . import paths

DOWNLOAD_PAGE = "https://ollama.com/download"
DEFAULT_URL = "http://127.0.0.1:11434"
LEVELS = ("A2", "B1", "B2", "C1")
EXPLAIN = {"en": "English", "fa": "Persian (فارسی)", "de": "simple German"}

# The models SubPlayer suggests (the first that fits the PC's memory is the one-click download). All are free and good
# in German, English and Persian; sizes are what Ollama downloads.
@dataclass(frozen=True)
class Suggestion:
    name: str
    size: str
    ram_gb: int
    why: str


SUGGESTED = (
    Suggestion("gemma3:4b", "3.3 GB", 8, "quick on most PCs; good German, English and Persian"),
    Suggestion("qwen3:8b", "5.2 GB", 12, "strong at grammar explanations; a little slower"),
    Suggestion("gemma3:12b", "8.1 GB", 16, "the best language teacher at this size — recommended with 16 GB memory"),
    Suggestion("mistral-small3.2", "15 GB", 32, "best quality; needs 32 GB memory or a graphics card with 16 GB"),
)

# How well a model family suits SubPlayer (higher = better): multilingual chat models first; code, OCR, embedding and
# vision-only models are no teachers.
_FAMILY = (
    (r"^gemma4", 96), (r"^gemma3n", 70), (r"^gemma3", 95), (r"^qwen3\.\d", 92), (r"^qwen3(?!-coder)", 90),
    (r"^mistral-small", 89), (r"^mistral-nemo", 80), (r"^llama4", 85), (r"^llama3\.[13]", 78), (r"^aya", 82),
    (r"^gpt-oss", 84), (r"^phi4", 70), (r"^qwen2\.5(?!-coder)", 72), (r"^mistral", 65), (r"^deepseek-r1", 60),
    (r"^llama3", 62), (r"^gemma2", 66), (r"^glm", 75),
)
_NOT_A_TEACHER = re.compile(r"(embed|ocr|coder|code|vision|llava|moondream|whisper|bge|minilm|rerank|guard|math|sql)", re.I)


def ram_gb() -> float:
    """The PC's memory in GB (Windows; elsewhere a guess of 16)."""
    try:
        import ctypes

        class MEM(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MEM()
        m.dwLength = ctypes.sizeof(MEM)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return m.ullTotalPhys / 1024 ** 3
    except Exception:
        pass
    try:
        import os
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3
    except Exception:
        return 16.0


def suggestion_for(ram: float) -> Suggestion:
    """The largest suggested model that runs comfortably with this much memory (not the 15 GB one by default)."""
    best = SUGGESTED[0]
    for s in SUGGESTED[:3]:
        if ram >= s.ram_gb - 0.6:            # "16 GB" PCs report 15.4–15.9 GB
            best = s
    return best


def _params_b(m: dict) -> float:
    t = ((m.get("details") or {}).get("parameter_size") or "").upper().strip()
    mm = re.match(r"([\d.]+)\s*([BM])", t)
    if mm:
        return float(mm.group(1)) / (1000 if mm.group(2) == "M" else 1)
    mm = re.search(r":(\d+(?:\.\d+)?)b", m.get("name", ""), re.I)
    return float(mm.group(1)) if mm else 0.0


def score(m: dict, ram: float) -> float:
    """How good an installed model is as SubPlayer's teacher on this PC (0 = not suitable)."""
    name = (m.get("name") or m.get("model") or "").lower()
    base = name.split("/")[-1]
    if _NOT_A_TEACHER.search(base):
        return 0.0
    fam = next((v for pat, v in _FAMILY if re.search(pat, base)), 40)
    p = _params_b(m)
    if p and p < 1.5:
        return fam * 0.3                     # too small to teach
    if p and p * 0.65 > ram * 0.8:           # would not fit in memory (≈0.65 GB per billion parameters at 4 bits)
        return fam * 0.2
    return fam + min(p, 30) * 0.4            # bigger is better while it fits


def best_installed(models: list[dict], ram: float | None = None) -> str:
    ram = ram_gb() if ram is None else ram
    ranked = sorted(models, key=lambda m: -score(m, ram))
    return (ranked[0].get("name") or "") if ranked and score(ranked[0], ram) > 0 else ""


# ---------------------------------------------------------------------------------------------------- talking to Ollama
class OllamaError(Exception):
    pass


class Client:
    def __init__(self, url: str = DEFAULT_URL, model: str = ""):
        self.url = (url or DEFAULT_URL).rstrip("/")
        self.model = model
        self.s = requests.Session()
        self.s.trust_env = False             # Ollama is on this PC (or the local network): never through a proxy

    # -------------------------------------------------------------- status
    def version(self, timeout: float = 2.5) -> str:
        try:
            r = self.s.get(self.url + "/api/version", timeout=timeout)
            r.raise_for_status()
            return r.json().get("version", "?")
        except Exception as e:
            raise OllamaError("Ollama is not running on this PC. Install it from ollama.com/download (or start it from the "
                              "Start menu), then press Check again.") from e

    def models(self) -> list[dict]:
        r = self.s.get(self.url + "/api/tags", timeout=10)
        r.raise_for_status()
        return r.json().get("models") or []

    # -------------------------------------------------------------- download a model
    def pull(self, name: str, progress=lambda done, total, status: None, cancelled=lambda: False) -> None:
        with self.s.post(self.url + "/api/pull", json={"model": name, "stream": True}, stream=True, timeout=(5, 600)) as r:
            if r.status_code >= 400:
                raise OllamaError(f"Ollama: {r.text[:200]}")
            for line in r.iter_lines():
                if cancelled():
                    raise OllamaError("Cancelled")
                if not line:
                    continue
                d = json.loads(line)
                if d.get("error"):
                    msg = d["error"]
                    if "does not exist" in msg or "not found" in msg:
                        msg = f"Ollama doesn't know a model called “{name}”."
                    elif any(k in msg.lower() for k in ("dial tcp", "timeout", "connection", "tls")):
                        msg = "Ollama could not reach its download server (from Iran a VPN is usually needed for ollama.com)."
                    raise OllamaError(msg)
                progress(int(d.get("completed") or 0), int(d.get("total") or 0), d.get("status") or "")
                if d.get("status") == "success":
                    return

    # -------------------------------------------------------------- chat
    def chat(self, user: str, system: str = "", json_mode: bool = False, on_text=None, cancelled=lambda: False,
             ctx: int = 8192, temperature: float = 0.5) -> str:
        """The model's answer (streamed piece by piece to on_text). Thinking models answer without showing their thoughts."""
        if not self.model:
            raise OllamaError("No model chosen — Settings ▸ Local AI teacher (Ollama).")
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
        body = {"model": self.model, "messages": msgs, "stream": True, "think": False, "keep_alive": "15m",
                "options": {"temperature": temperature, "num_ctx": int(ctx)}}
        if json_mode:
            body["format"] = "json"
        try:
            r = self.s.post(self.url + "/api/chat", json=body, stream=True, timeout=(5, 900))
        except requests.RequestException as e:
            raise OllamaError("Ollama is not running on this PC — start it from the Start menu.") from e
        with r:
            if r.status_code == 404:
                raise OllamaError(f"The model “{self.model}” is not on this PC — download it in Settings ▸ Local AI teacher.")
            if r.status_code >= 400:
                txt = r.text[:300]
                if "think" in txt and "not support" in txt:           # an older Ollama or a model without thinking
                    body.pop("think", None)
                    return self._retry(body, on_text, cancelled)
                raise OllamaError(f"Ollama: {txt}")
            return self._stream(r, on_text, cancelled)

    @staticmethod
    def visible(raw: str) -> str:
        """The answer without <think>…</think> blocks (older models write their thinking into the answer).
        An unfinished block — or a tag still arriving — hides everything after it."""
        out = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
        i = out.find("<think>")
        if i >= 0:
            out = out[:i]
        for k in range(min(len(out), 6), 0, -1):                     # "<thi" at the very end may be a tag arriving
            if "<think>".startswith(out[-k:]):
                out = out[:-k]
                break
        return out

    def _stream(self, r, on_text, cancelled) -> str:
        raw, shown = "", ""
        for line in r.iter_lines():
            if cancelled():
                raise OllamaError("Stopped")
            if not line:
                continue
            d = json.loads(line)
            if d.get("error"):
                raise OllamaError("Ollama: " + d["error"])
            raw += (d.get("message") or {}).get("content") or ""
            now = self.visible(raw)
            if len(now) > len(shown) and now.startswith(shown):
                if on_text:
                    on_text(now[len(shown):])
                shown = now
            if d.get("done"):
                break
        final = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
        if on_text and len(final) > len(shown) and final.startswith(shown):
            on_text(final[len(shown):])
        return final.strip()

    def _retry(self, body, on_text, cancelled):
        with self.s.post(self.url + "/api/chat", json=body, stream=True, timeout=(5, 900)) as r:
            if r.status_code >= 400:
                raise OllamaError(f"Ollama: {r.text[:300]}")
            return self._stream(r, on_text, cancelled)


# ---------------------------------------------------------------------------------------------------- the teacher's tasks
def _teacher(lang: str, explain: str) -> str:
    target = "English" if lang == "en" else "German"
    exam = "IELTS" if lang == "en" else "Goethe, telc and TestDaF"
    return (f"You are an experienced, warm {target} teacher who prepares adults for {exam} exams. Your learner speaks Persian "
            f"and English. Explain in {EXPLAIN.get(explain, 'English')}; every example sentence is natural, correct, everyday "
            f"{target}. Be precise and brief. Never invent words or meanings — if unsure, leave the field empty.")


def word_prompt(word: str, lemma: str, sentence: str, lang: str, level: str, explain: str) -> str:
    target = "English" if lang == "en" else "German"
    ex = EXPLAIN.get(explain, "English")
    forms = ("for a noun: article and plural; for a verb: Präteritum, Perfekt (with haben/sein) and the case it takes; "
             "for an adjective: comparative" if lang != "en" else "word family (noun / verb / adjective / adverb) and irregular forms")
    return (f"The {target} word „{word}“ (base form: {lemma or word}) appears in this line of a video:\n„{sentence}“\n"
            f"The learner's level is {level}.\n\n"
            "Answer ONLY with a JSON object with these keys:\n"
            f'  "meaning": the meaning of the word IN THIS LINE, in {ex} (one short sentence),\n'
            f'  "forms": {forms},\n'
            f'  "collocations": 8 typical collocations of the base form (verb + noun, adjective + noun, noun + preposition, '
            f'fixed expressions — the combinations native speakers really use), each as {{"phrase": "...", "meaning": "... in {ex}", '
            f'"example": "a short {target} sentence"}},\n'
            f'  "examples": 5 new {target} example sentences at level {level}, in different everyday situations, using the '
            f'collocations, each as {{"sentence": "...", "translation": "... in {ex}"}},\n'
            '  "grammar": the preposition or case the word goes with, or another grammar point it brings (one line, may be empty),\n'
            '  "synonyms": up to 4 synonyms or near-synonyms, with the difference in a few words,\n'
            '  "opposite": an antonym if there is a natural one, else empty,\n'
            f'  "tip": one memory tip or the typical mistake learners make with this word, in {ex}.')


def sentence_prompt(sentence: str, lang: str, explain: str, level: str) -> str:
    target = "English" if lang == "en" else "German"
    ex = EXPLAIN.get(explain, "English")
    return (f"Explain this {target} sentence from a video for a learner at level {level}:\n„{sentence}“\n\n"
            f"In {ex}, with short headings:\n"
            "1. Translation (natural).\n"
            "2. Structure: the parts of the sentence, where the verb(s) stand and why"
            + (", cases (Nominativ / Akkusativ / Dativ / Genitiv) of the noun groups, separable verbs, tense and mood"
               if lang != "en" else ", tense and aspect, phrasal verbs, clause types") + ".\n"
            "3. Words and expressions worth learning in it (with meaning).\n"
            f"4. Three new {target} sentences built on the same pattern, each with its translation.\n"
            "Plain text, no tables.")


def check_prompt(word: str, attempt: str, lang: str, explain: str, level: str) -> str:
    target = "English" if lang == "en" else "German"
    ex = EXPLAIN.get(explain, "English")
    return (f"A learner at level {level} wrote this {target} sentence to practise the word „{word}“:\n„{attempt}“\n\n"
            "Answer ONLY with a JSON object:\n"
            '  "correct": true or false (true only if it is fully correct and natural),\n'
            '  "corrected": the corrected sentence (the same if it was correct),\n'
            f'  "explanation": in {ex}, what was wrong and the rule behind it — or why it is good (2–4 short sentences),\n'
            f'  "better": one more natural or more advanced way to say it in {target},\n'
            '  "score": a number from 1 to 10.')


def ask_prompt(question: str, word: str, sentence: str, video: str, lang: str, explain: str, level: str) -> str:
    target = "English" if lang == "en" else "German"
    ctx = []
    if word:
        ctx.append(f"the word „{word}“")
    if sentence:
        ctx.append(f"this line: „{sentence}“")
    if video:
        ctx.append(f"from the video “{video}”")
    return (f"My {target} level is {level}. " + (("We are looking at " + ", ".join(ctx) + ".\n") if ctx else "")
            + f"My question: {question}\n\nAnswer in {EXPLAIN.get(explain, 'English')}, with {target} examples where they help.")


def parse_json(text: str) -> dict:
    """The JSON object in a model's answer (tolerates ``` fences and text around it)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        d = json.loads(t)
        return d if isinstance(d, dict) else {}
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}
    return {}


def as_list(v) -> list:
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v.strip():
        return [x.strip() for x in re.split(r"\n|;", v) if x.strip()]
    return []


def lesson_ctx(prompt: str) -> int:
    """Context size for a lesson question: the whole question (≈3 characters per token) plus room for the answer."""
    need = len(prompt) // 3 + 6000
    return max(8192, min(32768, need))


# ---------------------------------------------------------------------------------------------------- cache
class Cache:
    """Word-coach answers, so the same word at the same level opens instantly (data folder/teacher-cache.json)."""

    def __init__(self):
        self.file = paths.data_dir() / "teacher-cache.json"
        self.lock = threading.Lock()
        try:
            self.d = json.loads(self.file.read_text(encoding="utf-8"))
        except Exception:
            self.d = {}

    @staticmethod
    def key(model, lang, lemma, level, explain):
        return f"{model}|{lang}|{(lemma or '').lower()}|{level}|{explain}"

    def get(self, k):
        return self.d.get(k)

    def put(self, k, v):
        with self.lock:
            self.d[k] = v
            if len(self.d) > 3000:                       # keep the newest 2,500
                for old in sorted(self.d, key=lambda x: self.d[x].get("_t", 0))[:500]:
                    self.d.pop(old, None)
            v["_t"] = int(time.time())
            try:
                self.file.write_text(json.dumps(self.d, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
