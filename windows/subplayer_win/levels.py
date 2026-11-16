"""
Word levels (A1…C2) for colouring subtitles.
English: CEFR-J Vocabulary Profile 1.5 (Tono Laboratory, TUFS) + Octanove Vocabulary Profile C1/C2 (CC BY-SA 4.0); words in
neither list are estimated from their frequency. German: the 2,557 single words of the WordFeather list (Goethe/telc-oriented
levels; the CC0 version of 6 June 2026) have their listed level; every other word is an ESTIMATE from how common its base
word is (FrequencyWords 2018 by Hermit Dave, OpenSubtitles, CC BY-SA 4.0). Built by tools/levels/build_levels.py.
"""
from __future__ import annotations

import re
from pathlib import Path

NAMES = ["", "A1", "A2", "B1", "B2", "C1", "C2"]
COLORS = ["#FFFFFF", "#5BE38F", "#3EF0FF", "#5B8CFF", "#B07CFF", "#FFB347", "#FF5C8A"]
SOURCE = {"en": "CEFR-J / Octanove (C1–C2); others estimated",
          "de": "WordFeather list (Goethe/telc-oriented) for 2,557 words; others estimated from frequency"}
_DATA = Path(__file__).with_name("data")


class Levels:
    def __init__(self):
        self._tables: dict[str, dict[str, int]] = {}
        self._listed: dict[str, set[str]] = {}
        self._cache: dict[tuple, int] = {}

    def table(self, lang: str) -> dict[str, int]:
        t = self._tables.get(lang)
        if t is None:
            t, listed = {}, set()
            f = _DATA / f"levels-{lang}.tsv"
            if f.exists():
                for line in f.read_text(encoding="utf-8").splitlines():
                    p = line.split("\t")
                    if len(p) >= 2 and p[1].isdigit():
                        t[p[0]] = int(p[1])
                        if len(p) > 2 and p[2] == "L":
                            listed.add(p[0])
            self._tables[lang] = t
            self._listed[lang] = listed
        return t

    def listed(self, lemma: str, lang: str) -> bool:
        """True when the level of this base word comes from a published list (German: WordFeather), not an estimate."""
        self.table(lang)
        return lemma.strip().lower() in self._listed.get(lang, set())

    def level(self, word: str, lang: str, dictionary=None) -> int:
        """1..6, or 0 for names, numbers and words nobody knows."""
        w = word.strip().lower().strip("'’-")
        if not w or not re.search(r"[^\W\d_]", w):
            return 0
        key = (w, lang)
        if key in self._cache:
            return self._cache[key]
        t = self.table(lang)
        lv = t.get(w, 0)
        if dictionary is not None:
            try:
                rows = [(x,) for x in dictionary.lemmas_for(w)]
            except Exception:
                rows = []
            if rows:
                found = [t[r[0].lower()] for r in rows if r[0] and r[0].lower() in t]
                if lv:
                    found.append(lv)
                lv = min(found) if found else 6                               # known word, but rare: C2
            elif not lv and word[:1].isupper() and lang == "en":
                lv = 0                                                         # probably a name
        self._cache[key] = lv
        if len(self._cache) > 200_000:
            self._cache.clear()
        return lv
