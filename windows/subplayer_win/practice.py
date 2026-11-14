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
