"""AI lessons from a whole video: a ready prompt (text at A2 / B1 / B2 / C1 + exercises on the video's words and structures,
or a TestDaF / IELTS practice set built on the whole video) for ChatGPT, Gemini, DeepSeek or Grok, and a place to keep the
answers for practice.

Kept in <data folder>/lessons/<video name>.json: {"name": …, "lang": …, "levels": {"B1": {"text": …, "saved": unix seconds}}}.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from . import paths

LEVELS = ("A2", "B1", "B2", "C1")
EXAMS = ("TestDaF", "IELTS")
ALL = LEVELS + EXAMS


def exam_for(lang: str) -> str:
    """The exam that fits the video's language: TestDaF for German, IELTS for English."""
    return "IELTS" if lang == "en" else "TestDaF"
EXPLAIN = {"en": "English", "fa": "Persian (فارسی)", "de": "German (einfaches Deutsch)"}
MAX_TRANSCRIPT = 60_000            # characters; a 45-minute documentary is about 40,000

# name, address, whether the question can be handed over in the address (otherwise it is pasted with Ctrl+V)
ASSISTANTS = {
    "chatgpt": ("ChatGPT", "https://chatgpt.com/", "https://chatgpt.com/?q="),
    "gemini": ("Gemini", "https://gemini.google.com/app", ""),
    "deepseek": ("DeepSeek", "https://chat.deepseek.com/", ""),
    "grok": ("Grok", "https://grok.com/", "https://grok.com/?q="),
}
URL_LIMIT = 6000                   # longer questions don't fit in a web address — they are pasted

_WHAT = {
    "A2": "very simple: short main clauses, present tense and Perfekt, only everyday words; 150–200 words",
    "B1": "simple and clear: main clauses with weil / dass / wenn / obwohl, Präteritum of common verbs; 200–260 words",
    "B2": "natural and connected: relative clauses, passive, Konjunktiv II, linking words (allerdings, dennoch, sowohl … als auch); "
          "260–330 words",
    "C1": "demanding, as in a quality newspaper: nominal style, participle constructions, Konjunktiv I for reported speech, precise "
          "vocabulary; 330–420 words",
}
_WHAT_EN = {
    "A2": "very simple: short sentences, present and past simple, only everyday words; 150–200 words",
    "B1": "simple and clear: because / although / if clauses, common phrasal verbs; 200–260 words",
    "B2": "natural and connected: relative clauses, passive, conditionals, linking words (however, nevertheless, whereas); 260–330 words",
    "C1": "demanding, as in a quality newspaper: complex sentences, inversion, nominalisation, precise and idiomatic vocabulary; "
          "330–420 words",
}


def transcript(cues: list) -> str:
    """The whole text of the video, one flowing text (line breaks of the subtitles removed)."""
    return re.sub(r"\s+", " ", " ".join(c.text for c in cues)).strip()


def _cut(cues):
    text = transcript(cues)
    if len(text) > MAX_TRANSCRIPT:
        return text[:MAX_TRANSCRIPT].rsplit(" ", 1)[0] + " …", True
    return text, False


def exam_prompt(exam: str, lang: str, name: str, cues: list, my_words: list[str], explain: str = "en",
                exam_words: list[str] = ()) -> str:
    """A TestDaF (German) or IELTS Academic (English) practice set built on the whole video: exam vocabulary from the video and
    the topic words likely in future videos and exam texts, listening tasks on the video, a reading text, writing and speaking
    tasks — answers at the end."""
    ex = EXPLAIN.get(explain, "English")
    text, cut = _cut(cues)
    mine = ", ".join(dict.fromkeys(w.strip() for w in my_words if w.strip()))[:1200]
    found = ", ".join(dict.fromkeys(w.strip() for w in exam_words if w.strip()))[:1500]
    if exam == "IELTS":
        head = ("You are an experienced IELTS Academic examiner and teacher. I am preparing for IELTS (target band 7+) with an English "
                "video. Build a complete practice set on the WHOLE video below — its topic, arguments, facts and language.")
        tasks = [
            "VOCABULARY FOR IELTS\n"
            "   a) 20 words and expressions FROM THE VIDEO that are most useful for band 7+ (use the B2–C2 words listed below where "
            f"they fit): word family (noun / verb / adjective / adverb), 2 typical collocations, the meaning in {ex}, and the sentence "
            "from the video.\n"
            "   b) TOPIC VOCABULARY: 15 further words and collocations that are NOT in the video but are very likely to appear in "
            "future videos and in IELTS reading, listening and writing on this topic, each with meaning and one example.",
            "LISTENING (the video is the recording; do not quote the answers in the questions)\n"
            "   Part A — note completion: 8 gaps, NO MORE THAN TWO WORDS AND/OR A NUMBER.\n"
            "   Part B — 5 multiple-choice questions (A–C).\n"
            "   Part C — matching: 5 statements to the people / options / parts of the video they belong to.",
            "READING — write an academic passage of about 600 words on the topic of the video (new text, IELTS style, with paragraphs "
            "A–F), then 13 questions: 5 TRUE / FALSE / NOT GIVEN, 4 matching headings to paragraphs, 4 summary completion with "
            "words from the passage.",
            "WRITING\n"
            "   Task 1 (150 words): a chart or table on the topic with numbers you invent — say clearly that the data are invented "
            "for practice — and the usual instruction.\n"
            "   Task 2 (250 words): an essay question on the topic (opinion, discuss both views, or problem–solution).\n"
            "   Then: a band-7 checklist (task response, coherence, lexical resource, grammar) and 10 useful linking phrases.",
            "SPEAKING — Part 1: 4 questions · Part 2: a cue card with 4 prompts · Part 3: 5 discussion questions; plus 8 useful "
            "phrases for giving and supporting opinions.",
            "ANSWERS — after a line “---ANSWERS---”: all answers of Listening and Reading (with the sentence that proves each one), "
            "and a short band-8 model answer for Writing Task 2.",
        ]
        tail = f"Write everything in English, except the meanings and short explanations, which are in {ex}. Plain text with clear headings, no tables."
        target = "English"
    else:
        head = ("You are an experienced TestDaF examiner and German teacher. I am preparing for the (digital) TestDaF, aiming at TDN 4–5 "
                "(B2–C1), with a German video. Build a complete practice set on the WHOLE video below — its topic, arguments, facts and "
                "language.")
        tasks = [
            "WORTSCHATZ FÜR DEN TESTDAF\n"
            "   a) 20 Wörter und Ausdrücke AUS DEM VIDEO, die für TestDaF-Texte (Hochschule, Wissenschaft, Gesellschaft, Umwelt, "
            "Arbeit) am wichtigsten sind (nimm die B2–C2-Wörter unten, wo sie passen): Artikel und Plural bzw. Präteritum und "
            f"Perfekt, typische Nomen-Verb-Verbindungen und Präpositionen, die Bedeutung auf {ex} und den Satz aus dem Video.\n"
            "   b) THEMENWORTSCHATZ: 15 weitere Wörter und Wendungen, die NICHT im Video vorkommen, aber in künftigen Videos und in "
            "TestDaF-Lese- und Hörtexten zu diesem Thema sehr wahrscheinlich sind — mit Bedeutung und einem Beispiel.",
            "HÖREN (das Video ist der Hörtext; die Lösungen nicht in den Aufgaben verraten)\n"
            "   Aufgabe 1 — 8 Notizen mit Lücken zu den wichtigsten Informationen (Stichworte).\n"
            "   Aufgabe 2 — 8 Aussagen: richtig oder falsch?\n"
            "   Aufgabe 3 — 5 Fragen mit kurzen Antworten (Meinungen, Gründe, Folgen).",
            "LESEN — schreibe einen neuen wissenschaftsnahen Text von etwa 450 Wörtern zum Thema des Videos (Absätze A–E), dann "
            "10 Aufgaben: 4 Zuordnungen von Überschriften zu Absätzen, 3 Multiple-Choice-Fragen, 3 Aussagen mit „Ja / Nein / "
            "Text sagt dazu nichts“.",
            "SCHREIBEN — eine TestDaF-Schreibaufgabe zum Thema: eine kleine Grafik oder Tabelle mit erfundenen Zahlen (sag deutlich, "
            "dass die Zahlen zur Übung erfunden sind), zwei Positionen; ich soll die Grafik beschreiben, die Positionen vergleichen und "
            "begründet Stellung nehmen (mindestens 250 Wörter). Dazu 12 Redemittel für Grafikbeschreibung und Argumentation.",
            "SPRECHEN — 4 Aufgaben wie im TestDaF: (1) eine Situation beschreiben / Auskunft geben, (2) Optionen vergleichen und eine "
            "Empfehlung geben, (3) zu einer These Stellung nehmen, (4) Hypothesen zu einer Entwicklung bilden — jeweils mit "
            "Vorbereitungs- und Sprechzeit und 6 passenden Redemitteln.",
            "LÖSUNGEN — nach einer Zeile „---LÖSUNGEN---“: alle Lösungen zu Hören und Lesen (mit dem Satz, der sie belegt), dazu "
            "ein kurzer Mustertext auf Niveau TDN 5 für Schreiben und was ihn zu TDN 5 macht.",
        ]
        tail = f"Schreibe alles auf Deutsch, nur die Bedeutungen und kurzen Erklärungen auf {ex}. Klarer Text mit Überschriften, keine Tabellen."
        target = "German"
    out = [head, ""] + [f"{i}. {t}" for i, t in enumerate(tasks, 1)] + ["", tail, ""]
    if found:
        out += [f"B2–C2 words in this video (from the CEFR word lists): {found}", ""]
    if mine:
        out += [f"Words I have already saved from this video: {mine}", ""]
    out += [f"Video: {name}" + (" (the transcript is long — only its first part is given)" if cut else ""),
            f"TRANSCRIPT ({target}):", text]
    return "\n".join(out)


def prompt(level: str, lang: str, name: str, cues: list, my_words: list[str], explain: str = "en",
           exam_words: list[str] = ()) -> str:
    """The question for the assistant: a text at this level about the video + exercises to master its words and structures
    (or, for "TestDaF" / "IELTS", the exam practice set)."""
    if level in EXAMS:
        return exam_prompt(level, lang, name, cues, my_words, explain, exam_words)
    german = lang != "en"
    target = "German" if german else "English"
    ex = EXPLAIN.get(explain, "English")
    what = (_WHAT if german else _WHAT_EN).get(level, "")
    text = transcript(cues)
    cut = len(text) > MAX_TRANSCRIPT
    if cut:
        text = text[:MAX_TRANSCRIPT].rsplit(" ", 1)[0] + " …"
    words = ", ".join(dict.fromkeys(w.strip() for w in my_words if w.strip()))[:1500]
    tasks = [
        f"TEXT ({level}) — Write a new {target} text at CEFR level {level} that retells the content of the video ({what}). "
        "Use the important words and sentence structures of the transcript, but adapt them strictly to this level. "
        "Give it a title.",
        f"WORTSCHATZ — The 15 most useful words and expressions from the video for a {level} learner"
        + (" (include the words I am learning, listed below)" if words else "") + ". For each: "
        + ("article and plural for nouns, Präteritum and Perfekt for verbs, " if german else "word forms, ")
        + f"the meaning in {ex}, and one short example sentence in {target}.",
        f"STRUKTUREN — The 3 grammar structures of the video that matter most at {level}. For each: the sentence from the video "
        f"where it appears, a short explanation in {ex}, and 2 new examples.",
        "ÜBUNGEN — exercises that use ONLY the words and structures above:\n"
        "   A. Lückentext: 10 sentences with one gap each (word bank in mixed order above the sentences).\n"
        "   B. Zuordnung: match 8 words to their definitions or synonyms.\n"
        "   C. Umformung: 6 sentences to rewrite with one of the structures (say which).\n"
        f"   D. Fragen zum Text: 5 comprehension questions to answer in full {target} sentences.\n"
        f"   E. Schreiben: one writing task (60–120 words at {level}) with 5 words from the list that I must use.",
        f"LÖSUNGEN — the answers to A–D at the very end, after a line “---LÖSUNGEN---”, so that I can test myself first.",
    ]
    if not german:
        tasks = [t.replace("WORTSCHATZ", "VOCABULARY").replace("STRUKTUREN", "STRUCTURES").replace("ÜBUNGEN", "EXERCISES")
                 .replace("Lückentext", "Gap-fill").replace("Zuordnung", "Matching").replace("Umformung", "Transformation")
                 .replace("Fragen zum Text", "Questions on the text").replace("Schreiben", "Writing")
                 .replace("LÖSUNGEN", "ANSWERS") for t in tasks]
    out = [f"You are an experienced {target} teacher. I am learning {target} with a video and want to master its words and "
           f"sentence structures at level {level}. Work only from the transcript below.", ""]
    out += [f"{i}. {t}" for i, t in enumerate(tasks, 1)]
    out += ["", f"Write everything in {target}, except the meanings and explanations, which are in {ex}. Plain text with clear "
                "headings, no tables.", ""]
    if words:
        out += [f"Words I am learning from this video: {words}", ""]
    out += [f"Video: {name}" + (" (the transcript is long — only its first part is given)" if cut else ""),
            f"TRANSCRIPT ({target}):", text]
    return "\n".join(out)


def _file(name: str) -> Path:
    stem = re.sub(r"[^\w\- .]+", "_", Path(name).stem, flags=re.UNICODE).strip(" .")[:120] or "video"
    return paths.sub_dir("lessons") / f"{stem}.json"


def load(name: str) -> dict:
    try:
        d = json.loads(_file(name).read_text(encoding="utf-8"))
        return d if isinstance(d.get("levels"), dict) else {"levels": {}}
    except Exception:
        return {"levels": {}}


def text(name: str, level: str) -> str:
    return (load(name)["levels"].get(level) or {}).get("text", "")


def save(name: str, lang: str, level: str, body: str) -> None:
    """Keeps (or, when empty, removes) the lesson of one level."""
    d = load(name)
    d["name"], d["lang"] = name, lang
    if body.strip():
        d["levels"][level] = {"text": body, "saved": int(time.time())}
    else:
        d["levels"].pop(level, None)
    f = _file(name)
    if d["levels"]:
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    elif f.exists():
        f.unlink()


def kept(name: str) -> list[str]:
    """The levels that have a lesson for this video."""
    lv = load(name)["levels"]
    return [x for x in ALL if (lv.get(x) or {}).get("text", "").strip()]


def all_lessons() -> list[tuple[str, list[str]]]:
    """[(video name, levels)] of every kept lesson, newest first."""
    out = []
    for f in sorted(paths.sub_dir("lessons").glob("*.json"), key=lambda p: -p.stat().st_mtime):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            lv = [x for x in ALL if (d.get("levels", {}).get(x) or {}).get("text", "").strip()]
            if lv:
                out.append((d.get("name") or f.stem, lv))
        except Exception:
            pass
    return out
