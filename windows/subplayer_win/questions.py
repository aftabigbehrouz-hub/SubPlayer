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
    question), A = the answer, E = why (the proof).
"""
from __future__ import annotations

import re

from . import ollama
from .store import Question

MARK = "---REVIEW---"
_LINE = re.compile(r"^\s*(?:\d+[.)]\s*)?(?:\*\*)?(Q|O|A|E|F|L|Frage|Optionen|Antwort|Lösung|Begründung|Question|Options|Answer|Why)"
                   r"(?:\*\*)?\s*[:：]\s*(.*)$", re.I)
_KEY = {"q": "q", "f": "q", "frage": "q", "question": "q", "o": "o", "optionen": "o", "options": "o", "a": "a", "l": "a",
        "antwort": "a", "lösung": "a", "answer": "a", "e": "e", "begründung": "e", "why": "e"}


def instructions(lang: str, n: int = 15) -> str:
    """The extra task for the lesson question: review cards in a fixed format at the very end."""
    if lang == "en":
        return (f"REVIEW CARDS — at the very end, after a line “{MARK}”, {n} of the questions above (listening, reading, "
                "vocabulary) once more as cards, EXACTLY in this format, four lines per card and nothing else:\n"
                "   Q: the question or statement\n   O: the options separated by | (TRUE | FALSE | NOT GIVEN, A) … | B) … | "
                "C) …) — leave empty for an open question\n   A: the correct answer\n   E: one sentence why (the proof from the "
                "text)")
    return (f"KARTEIKARTEN — ganz am Ende, nach einer Zeile „{MARK}“, {n} der Aufgaben oben (Hören, Lesen, Wortschatz) noch "
            "einmal als Karten, GENAU in diesem Format, vier Zeilen pro Karte und sonst nichts:\n"
            "   Q: die Frage oder Aussage\n   O: die Antwortmöglichkeiten, getrennt durch | (richtig | falsch, Ja | Nein | "
            "Text sagt dazu nichts, A) … | B) … | C) …) — leer bei einer offenen Frage\n   A: die richtige Lösung\n"
            "   E: ein Satz, warum (der Beleg aus dem Text)")


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
    i = text.rfind(MARK)
    body = text[i + len(MARK):] if i >= 0 else text
    out, cur = [], {}

    def flush():
        if cur.get("q") and cur.get("a"):
            opts = _options(cur.get("o", ""))
            out.append(Question(question=cur["q"].strip(), answer=cur["a"].strip(), options=opts,
                                explanation=cur.get("e", "").strip(), kind=_kind(opts), lang=lang, video_name=video_name,
                                source=source))
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
            f"Mix these kinds: {kinds}. Put any short text the question needs into the question itself.\n"
            "Answer ONLY with a JSON object: {\"questions\": [ {\"question\": \"...\", \"options\": [\"...\", \"...\"] "
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
                            video_name=video_name, source="teacher"))
    return out


def lesson_to_cards_prompt(lesson: str, lang: str) -> str:
    """Ollama: turns a pasted lesson that has no ---REVIEW--- part into review cards."""
    return (("Here is an exam practice set with its answers. " if lang == "en" else
             "Hier ist ein Übungssatz mit Lösungen. ")
            + instructions(lang) + "\nWrite only the line " + MARK + " and the cards.\n\n" + lesson[:24000])
