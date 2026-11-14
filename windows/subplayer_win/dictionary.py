"""Offline dictionaries (the same SQLite files as the Android app): German and English Wiktionary."""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field


@dataclass
class Sense:
    de: str              # definition (German for the German dictionary, English for the English one)
    examples: list


@dataclass
class Entry:
    lemma: str
    pos: str
    pos_de: str
    article: str
    ipa: str
    hyphenation: str
    audio_url: str
    senses: list
    english: list
    persian: list
    persian_via_english: list
    synonyms: list
    german: list = field(default_factory=list)
    lang: str = "de"


_EDGE = re.compile(r"^[\W_„“”‚‘’«»–—…\s]+|[\W_„“”‚‘’«»–—…\s]+$", re.UNICODE)


def normalize(raw: str) -> str:
    w = raw.strip()
    keep = w.endswith("'s") or w.endswith("’s")
    w = _EDGE.sub("", w)
    if keep and not w.endswith("s"):
        w += "'s"
    return w


class Dictionary:
    def __init__(self, file):
        self.db = sqlite3.connect(f"file:{file}?mode=ro", uri=True, check_same_thread=False)

    def close(self):
        self.db.close()

    def lookup(self, raw: str) -> list[Entry]:
        word = normalize(raw)
        if not word:
            return []
        cands = [word.lower()]
        if word.endswith("'s") or word.endswith("’s"):
            cands.append(word[:-2].lower())
        if "-" in word:
            cands.append(word.rsplit("-", 1)[1].lower())
        if word.endswith("n't"):
            cands.append(word[:-3].lower())
        seen = set()
        for key in cands:
            if key in seen or not key:
                continue
            seen.add(key)
            lst = self._query(key)
            if lst:
                return self._rank(lst, word)
        return []

    def _query(self, key: str) -> list[Entry]:
        out = []
        for lemma, pos, gender, ipa, hyph, audio, data in self.db.execute(
                "SELECT e.lemma,e.pos,e.gender,e.ipa,e.hyph,e.audio,e.data FROM lookup l JOIN entry e ON e.id=l.id "
                "WHERE l.key=? LIMIT 40", (key,)):
            d = json.loads(data)
            s = lambda k: [x for x in (d.get(k) or []) if isinstance(x, str) and x.strip()]
            out.append(Entry(
                lemma=lemma, pos=pos or "", pos_de=d.get("posDe") or "", article=gender or "", ipa=ipa or "",
                hyphenation=hyph or "", audio_url=audio or "",
                senses=[Sense(x.get("de") or "", [e for e in (x.get("ex") or []) if e]) for x in (d.get("senses") or [])],
                english=s("enGloss") or s("en"), persian=s("fa"), persian_via_english=s("faVia"), synonyms=s("syn"),
                german=s("deTr"), lang=d.get("lang") or "de"))
        return out

    @staticmethod
    def _rank(lst: list[Entry], word: str) -> list[Entry]:
        capital = word[:1].isupper()

        def score(e: Entry) -> int:
            s = 0
            if e.lemma == word:
                s += 3
            elif e.lemma.lower() == word.lower():
                s += 2
            if e.english:
                s += 2
            if e.persian:
                s += 2
            elif e.persian_via_english:
                s += 1
            if e.german:
                s += 1
            if capital == (e.pos == "noun"):
                s += 1
            if e.pos == "name":
                s -= 6
            return s

        uniq, seen = [], set()
        for e in lst:
            k = e.lemma + "|" + e.pos
            if k not in seen:
                seen.add(k)
                uniq.append(e)
        uniq.sort(key=lambda e: (-score(e), -len(e.senses)))   # stable, like Kotlin's sortedWith
        return uniq[:3]


def clean_example(ex: str) -> str:
    """Wiktionary examples start with a sense marker like "[1]" — remove it before speaking."""
    return re.sub(r"^\s*\[[\d,.\s–-]+\]\s*", "", ex)
