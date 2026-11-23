"""Exam-style questions (TestDaF for German, IELTS for English) that come back in Review like saved words.

They come from two places:
  • the teacher (word card ▸ Teacher ▸ TestDaF questions): Ollama writes a few questions on one word as JSON;
  • an AI lesson (Study this video ▸ AI lesson ▸ TestDaF / IELTS): the assistant ends its answer with a block

        ---REVIEW---
        Q: Laut dem Video sind die Angriffe auf Schiffe zurückgegangen.
        O: richtig | falsch
        A: falsch
        E: „Aktuell gibt es wieder etliche Angriffe …“

    which is read when the lesson is pasted or saved. Q = question, O = options (separated by |; none for an open
    question), A = the answer, E = why (the proof), T = the text the question is about (a reading paragraph; optional) —
    it is shown above the question in Review. Cards without T: from a lesson get the lesson's reading text instead.
"""
from __future__ import annotations

import re

from . import ollama
from .store import Question

MARK = "---REVIEW---"
_LINE = re.compile(r"^\s*(?:\d+[.)]\s*)?(?:\*\*)?(Q|O|A|E|F|L|T|Frage|Optionen|Antwort|Lösung|Begründung|Question|Options|Answer|Why|Text|Lesetext|Passage)"
                   r"(?:\*\*)?\s*[:：]\s*(.*)$", re.I)
_KEY = {"q": "q", "f": "q", "frage": "q", "question": "q", "o": "o", "optionen": "o", "options": "o", "a": "a", "l": "a",
        "antwort": "a", "lösung": "a", "answer": "a", "e": "e", "begründung": "e", "why": "e", "t": "t", "text": "t",
        "lesetext": "t", "passage": "t"}


def instructions(lang: str, n: int = 15) -> str:
    """The extra task for the lesson question: review cards in a fixed format at the very end."""
    if lang == "en":
        return (f"REVIEW CARDS — at the very end, after a line “{MARK}”, {n} of the questions above (listening, reading, "
                "vocabulary) once more as cards, EXACTLY in this format, four lines per card (five for a reading question) and "
                "nothing else:\n"
                "   Q: the question or statement\n   O: the options separated by | (TRUE | FALSE | NOT GIVEN, A) … | B) … | "
                "C) …) — leave empty for an open question\n   A: the correct answer\n   E: one sentence why (the proof from the "
                "text)\n   T: ONLY for a reading question: the paragraph of the reading passage it is about, word for word, on one "
                "line (with its letter, e.g. “B: …”) — so the card can be answered without the lesson")
    return (f"KARTEIKARTEN — ganz am Ende, nach einer Zeile „{MARK}“, {n} der Aufgaben oben (Hören, Lesen, Wortschatz) noch "
            "einmal als Karten, GENAU in diesem Format, vier Zeilen pro Karte (fünf bei einer Leseaufgabe) und sonst nichts:\n"
            "   Q: die Frage oder Aussage\n   O: die Antwortmöglichkeiten, getrennt durch | (richtig | falsch, Ja | Nein | "
            "Text sagt dazu nichts, A) … | B) … | C) …) — leer bei einer offenen Frage\n   A: die richtige Lösung\n"
            "   E: ein Satz, warum (der Beleg aus dem Text)\n"
            "   T: NUR bei einer Leseaufgabe: der Absatz des Lesetextes, um den es geht, wörtlich, in einer Zeile (mit seinem "
            "Buchstaben, z. B. „B: …“) — damit man die Karte ohne die Lektion beantworten kann")


def _kind(opts: list[str]) -> str:
    low = [o.lower() for o in opts]
    if not opts:
        return "open"
    if set(low) <= {"richtig", "falsch", "true", "false"}:
        return "tf"
    if any("sagt dazu nichts" in o or "not given" in o for o in low):
        return "yn"
    return "mc"


def _options(raw: str) -> list[str]:
    raw = raw.strip()
    if not raw or raw.lower() in ("-", "—", "(leer)", "leer", "none", "keine"):
        return []
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) == 1:                                          # "A) … B) … C) …" on one line without |
        parts = [p.strip() for p in re.split(r"\s+(?=[A-F]\)\s)", raw)]
    return [p for p in parts if p]


def parse(text: str, lang: str = "de", video_name: str = "", source: str = "") -> list[Question]:
    """The review cards in a lesson: everything after ---REVIEW--- (or the whole text when the mark is missing but it is
    written as Q:/O:/A:/E: cards)."""
    from . import practice
    text = practice.clean_ai(text)
    i = text.rfind(MARK)
    body = text[i + len(MARK):] if i >= 0 else text
    out, cur = [], {}

    def flush():
        if cur.get("q") and cur.get("a"):
            opts = _options(cur.get("o", ""))
            out.append(Question(question=cur["q"].strip(), answer=cur["a"].strip(), options=opts,
                                explanation=cur.get("e", "").strip(), kind=_kind(opts), lang=lang, video_name=video_name,
                                source=source, passage=cur.get("t", "").strip()))
    for line in body.splitlines():
        m = _LINE.match(line.strip().lstrip("-•* "))
        if not m:
            if cur.get("last") and line.strip() and not line.strip().startswith(("---", "===")):
                cur[cur["last"]] = cur.get(cur["last"], "") + " " + line.strip()     # a card line that wrapped
            continue
        k = _KEY[m.group(1).lower()]
        if k == "q" and cur.get("q"):
            flush()
            cur = {}
        cur[k] = m.group(2).strip()
        cur["last"] = k
    flush()
    if i < 0 and len(out) < 2:                                   # a stray "A: …" in a normal lesson is no card set
        return []
    return out


def teacher_prompt(word: str, lemma: str, sentence: str, lang: str, level: str, explain: str, n: int = 6) -> str:
    """Ollama: n exam-style questions that test this one word (its meaning, collocations, grammar) in context."""
    exam = "IELTS Academic" if lang == "en" else "TestDaF"
    target = "English" if lang == "en" else "German"
    ex = ollama.EXPLAIN.get(explain, "English")
    kinds = ("multiple choice (A–D), TRUE / FALSE / NOT GIVEN on a 2–3 sentence text, gap-fill, and choosing the right "
             "collocation or word form" if lang == "en" else
             "Multiple Choice (A–D), Ja / Nein / Text sagt dazu nichts zu einem kurzen Text von 2–3 Sätzen, Lückentext und "
             "die richtige Kollokation, Präposition oder Form")
    return (f"Write {n} {exam}-style practice questions in {target} at level {level} that test the word „{lemma or word}“"
            + (f" (as in this line: „{sentence}“)" if sentence else "") + ".\n"
            f"Mix these kinds: {kinds}. A question that needs a short text gets it in \"text\" (not in the question).\n"
            "Answer ONLY with a JSON object: {\"questions\": [ {\"text\": \"the short text the question is about, or empty\", "
            "\"question\": \"...\", \"options\": [\"...\", \"...\"] "
            "(empty list for an open question), \"answer\": \"the correct option or answer, exactly as written in options\", "
            f"\"explanation\": \"why, in {ex}, one or two sentences\"}} ]}}")


def from_json(d: dict, lang: str, lemma: str, video_name: str = "") -> list[Question]:
    out = []
    for x in ollama.as_list(d.get("questions")):
        if not isinstance(x, dict) or not x.get("question") or not x.get("answer"):
            continue
        opts = [str(o).strip() for o in ollama.as_list(x.get("options")) if str(o).strip()]
        out.append(Question(question=str(x["question"]).strip(), answer=str(x["answer"]).strip(), options=opts,
                            explanation=str(x.get("explanation", "")).strip(), kind=_kind(opts), lang=lang, lemma=lemma,
                            video_name=video_name, source="teacher",
                            passage=str(x.get("text") or x.get("passage") or "").strip()))
    return out


_READ_HEAD = re.compile(r"^\W*(?:\d+\W*)?(LESEN|LESEVERSTEHEN|READING)\b", re.I)
_NEXT_HEAD = re.compile(r"^\W*(?:\d+\W*)?(HÖREN|HÖRVERSTEHEN|SCHREIBEN|SPRECHEN|LISTENING|WRITING|SPEAKING|LÖSUNGEN|ANSWERS|"
                        r"WORTSCHATZ|VOCABULARY|KARTEIKARTEN|REVIEW CARDS)\b|^\s*---", re.I)
_TASKS = re.compile(r"^\W*(Aufgaben?|Fragen|Questions?|Teil \d|Part \d|Ordnen Sie|Match|Choose|Wählen Sie|Do the following|"
                    r"Questions \d|\d+\s*[–-]\s*\d+)\b", re.I)


def reading_text(lesson: str) -> str:
    """The reading passage of a TestDaF / IELTS lesson (the text under LESEN / READING, without its tasks) — shown with
    the reading cards that came without their own T: line. Empty when the lesson has none."""
    from . import practice
    lines = practice.clean_ai(lesson or "").splitlines()
    start = next((i for i, ln in enumerate(lines) if _READ_HEAD.match(ln.strip())), -1)
    if start < 0:
        return ""
    out, words = [], 0
    for ln in lines[start + 1:]:
        t = ln.strip()
        if _NEXT_HEAD.match(t):
            break
        if words >= 60 and _TASKS.match(t):
            break                                                     # the passage is over, its questions begin
        out.append(ln.rstrip())
        words += len(t.split())
    text = "\n".join(out).strip()
    return text if len(text.split()) >= 40 else ""


def passage_of(q: Question) -> str:
    """The question's own text, or for a reading card of a lesson the lesson's reading passage."""
    if q.passage:
        return q.passage
    if not q.source.startswith("lesson:") or not q.video_name:
        return ""
    low = (q.question + " " + q.explanation).lower()
    reading = q.kind == "yn" or any(k in low for k in ("absatz", "abschnitt", "lesetext", "im text", "der text", "laut text",
                                                         "paragraph", "passage", "the text", "the writer", "the author"))
    if not reading:
        return ""
    from . import lessons
    return reading_text(lessons.text(q.video_name, q.source.split(":", 1)[1]))


def lesson_to_cards_prompt(lesson: str, lang: str) -> str:
    """Ollama: turns a pasted lesson that has no ---REVIEW--- part into review cards."""
    return (("Here is an exam practice set with its answers. " if lang == "en" else
             "Hier ist ein Übungssatz mit Lösungen. ")
            + instructions(lang) + "\nWrite only the line " + MARK + " and the cards.\n\n" + lesson[:24000])
