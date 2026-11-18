"""Pasted sentences, gap-fill, answer checking and dictation marks (same rules as the Android app)."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass

from .store import Example, SavedWord

LABEL = re.compile(r"^\s*(DE|EN|FA|Deutsch|German|English|Englisch|Persian|Persisch|Farsi|فارسی)\s*[:：]\s*", re.I)
BULLET = re.compile(r"^\s*(?:[-*•>]+|\d+[.)]|[(]\d+[)])\s*")
ARABIC = re.compile(r"[؀-ۿ]")


def _clean(s: str) -> str:
    s = s.replace("**", "").replace("__", "")
    return re.sub(r"^[\s\"„“”»«']+|[\s\"„“”»«']+$", "", s).strip()


def _persian(s: str) -> bool:
    return bool(ARABIC.search(s))


def clean_ai(text: str) -> str:
    """An answer copied from ChatGPT & co. as it should be: HTML entities (&#x20; for a space) decoded, the backslash that
    some copy buttons put at the end of every line removed, markdown escapes (\\* \\_ \\#) undone, ``` fences dropped."""
    import html as _html
    t = _html.unescape(text or "").replace("\u00a0", " ").replace("\r", "")
    t = re.sub(r"\\[ \t]*$", "", t, flags=re.M)                      # "{\\" → "{"
    t = re.sub(r"\\([*_#>\[\]()`~|-])", r"\1", t)                    # \\* → *
    t = re.sub(r"^\s*```[\w-]*\s*$", "", t, flags=re.M)
    return t.strip()


def looks_like_ai_answer(text: str) -> bool:
    """A whole pasted AI answer (JSON, a table, KOLL / Q: lines) rather than lines typed by hand."""
    t = clean_ai(text)
    return ('{' in t and '":' in t) or bool(re.search(r"^\s*(?:[-*•]\s*)?(KOLL|COLL|Q)\s*:", t, re.M | re.I)) or t.count("|") >= 4


COLL = re.compile(r"^\s*(?:[-*•]\s*)?(?:\*\*)?(KOLL|COLL|Kollokation|Collocation)(?:\*\*)?\s*[:：]\s*(.*)$", re.I)
HEADER_WORDS = {"german", "deutsch", "english", "englisch", "persian", "persisch", "farsi", "فارسی", "collocation", "collocations",
                "kollokation", "kollokationen", "meaning", "bedeutung", "example", "examples", "beispiel", "beispielsatz",
                "translation", "übersetzung", "phrase", "ausdruck", "word", "wort", "sentence", "satz", "#", "nr", "no"}


def is_header(cell: str) -> bool:
    """A table header cell such as "German collocation" or "English"."""
    ws = [w.strip("*:()").lower() for w in cell.split()]
    return bool(ws) and all(w in HEADER_WORDS for w in ws)


def is_phrase(t: str) -> bool:
    """A collocation, not a sentence: at most 5 words and no full stop / ! / ? at the end."""
    t = t.strip()
    return 1 <= len(t.split()) <= 5 and t[-1:] not in ".!?…" and not _persian(t)


def split_collocations(raw: str) -> tuple[list[dict], str]:
    """Collocations in a pasted AI answer — "KOLL: phrase | meaning | example" lines, and table rows whose first cell is a
    short phrase (ChatGPT often answers with a table) — and the rest of the text (the sentences) without them. Table headers
    and separator rows are dropped."""
    cols, rest = [], []
    for line in raw.replace("\r", "").split("\n"):
        m = COLL.match(line)
        if m:
            parts = [_clean(p) for p in m.group(2).split("|")]
            if parts and parts[0]:
                cols.append({"phrase": parts[0], "meaning": parts[1] if len(parts) > 1 else "", "example": parts[2] if len(parts) > 2 else ""})
            continue
        st = BULLET.sub("", line.strip())
        if "|" in st:
            cells = [_clean(LABEL.sub("", _clean(c))) for c in st.strip().strip("|").split("|")]
            cells = [c for c in cells if c]
            if not cells or all(set(c) <= set("-:= ") for c in cells):
                continue                                          # a markdown separator row |---|---|
            if all(is_header(c) for c in cells if not _persian(c)):
                continue                                          # the header row
            if is_phrase(cells[0]):
                others = cells[1:]
                fa = next((c for c in others if _persian(c)), "")
                ex = next((c for c in others if not _persian(c) and len(c.split()) >= 3 and c[-1:] in ".!?"), "")
                mean = next((c for c in others if not _persian(c) and c != ex), "")
                cols.append({"phrase": cells[0], "meaning": " · ".join(x for x in (mean, fa) if x), "example": ex})
                continue
        rest.append(line)
    return cols, "\n".join(rest)


def parse_sentences(raw: str, max_n: int = 12, primary: str = "de") -> list[Example]:
    """
    Accepts "DE: … | EN: … | FA: …", any "a | b | c" rows, blocks of labelled lines, or plain sentences.
    [primary] = language being learnt; its sentence goes in Example.de, the other language in .en.
    """
    lines = [_clean(BULLET.sub("", l).replace("**", "")) for l in raw.replace("\r", "").split("\n")]
    lines = [l for l in lines if l]
    structured = any("|" in l or LABEL.search(l) for l in lines)
    out: list[Example] = []
    if structured:
        cur = None

        def flush():
            nonlocal cur
            if cur is not None and cur.de:
                out.append(cur)
            cur = None

        for line in lines:
            if "|" in line:
                flush()
                parts = [_clean(LABEL.sub("", _clean(p))) for p in line.split("|")]
                parts = [p for p in parts if p]
                if not parts:
                    continue
                fa = next((p for p in parts if _persian(p)), "")
                rest = [p for p in parts if not _persian(p)]
                if not rest or len(rest[0].split(" ")) < 2:
                    continue
                out.append(Example(de=rest[0], en=rest[1] if len(rest) > 1 else "", fa=fa))
            else:
                m = LABEL.search(line)
                if not m:
                    continue
                label = m.group(1).lower()
                value = _clean(line[m.end():])
                if not value:
                    continue
                is_de = label in ("de", "deutsch", "german")
                is_en = label in ("en", "english", "englisch")
                main = is_en if primary == "en" else is_de
                other = is_de if primary == "en" else is_en
                fld = "de" if main else ("en" if other else "fa")
                c = cur or Example(de="")
                if getattr(c, fld):
                    flush()
                    c = Example(de="")
                setattr(c, fld, value)
                cur = c
        flush()
    else:
        for line in lines:
            t = _clean(line)
            if not _persian(t) and len(t.split(" ")) >= 3 and t[-1] in ".!?":
                out.append(Example(de=t))
    res, seen = [], set()
    for e in out:
        if e.de.lower() not in seen:
            seen.add(e.de.lower())
            res.append(e)
    return res[:max_n]


@dataclass
class Cloze:
    word: SavedWord
    before: str
    answer: str
    after: str
    en: str
    fa: str

    @property
    def sentence(self):
        return self.before + self.answer + self.after


TOKEN = re.compile(r"[^\W\d_][\w\-']*", re.UNICODE)


def cloze(w: SavedWord, sentence: str, en: str = "", fa: str = "") -> Cloze | None:
    if " " in w.text:
        i = sentence.lower().find(w.text.lower())
        return None if i < 0 else Cloze(w, sentence[:i], sentence[i:i + len(w.text)], sentence[i + len(w.text):], en, fa)
    toks = list(TOKEN.finditer(sentence))
    text, lemma = w.text.lower(), w.lemma.lower()
    base = lemma if len(lemma) >= len(text) else text
    stem = base[:max(4, len(base) - 3)]

    def pick(test):
        return next((m for m in toks if test(m.group(0).lower())), None)

    m = pick(lambda t: t == text) or pick(lambda t: t == lemma) or pick(lambda t: len(t) >= 4 and t.startswith(stem))
    if not m:
        return None
    return Cloze(w, sentence[:m.start()], m.group(0), sentence[m.end():], en, fa)


def choices(answer: str, pool: list[str], rnd: random.Random) -> list[str]:
    others, seen = [], set()
    for p in pool:
        p = p.strip()
        if p and p.lower() != answer.lower() and " " not in p and p.lower() not in seen:
            seen.add(p.lower())
            others.append(p)
    rnd.shuffle(others)
    others = others[:3]
    if len(others) < 3:
        return []
    res = others + [answer]
    rnd.shuffle(res)
    return res


def normalize(s: str) -> str:
    s = s.lower().strip().replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    s = re.sub(r"[^\w ]|_", "", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s)


def same(a: str, b: str) -> bool:
    return normalize(a) == normalize(b)


def dictation(expected: str, typed: str):
    """[(word, ok)], score 0..100 — longest common subsequence of words."""
    e = expected.split()
    t = [normalize(x) for x in typed.split()]
    en = [normalize(x) for x in e]
    dp = [[0] * (len(t) + 1) for _ in range(len(e) + 1)]
    for i in range(len(e) - 1, -1, -1):
        for j in range(len(t) - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if en[i] == t[j] and en[i] else max(dp[i + 1][j], dp[i][j + 1])
    ok = [False] * len(e)
    i = j = 0
    while i < len(e) and j < len(t):
        if en[i] == t[j] and en[i]:
            ok[i] = True
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    marks = [(w, ok[k] or not en[k]) for k, w in enumerate(e)]
    score = 0 if not e else sum(1 for _, o in marks if o) * 100 // len(e)
    return marks, score
