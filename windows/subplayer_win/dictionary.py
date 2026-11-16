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

    # ------------------------------------------------------------------ trustworthy links only
    # The dictionary file links every word form to its base word. Conjugation tables also left links that are no forms:
    # the helper verbs of compound tenses ("gebracht worden sein" → sein, haben, werden, worden, gewesen under ~13,000
    # verbs), "sie", reflexive pronouns, and the particle of separable verbs ("bringt mit" → mit). A key that many
    # entries share is therefore trusted only for the entry it names (or a pronoun); two true forms are kept by hand.
    POPULAR = 25                      # a word card looks at up to this many entries of a key before filtering
    SHARED = 5                        # a real word form belongs to at most this many base words
    KEEP = {("sein", "gewesen"), ("werden", "worden")}
    _NOT_A_FORM = ("verb", "adj", "suffix", "num")

    def links(self, key: str, cap: int = 60) -> int:
        """How many entries a key leads to (counted up to cap)."""
        c = self.__dict__.setdefault("_links", {})
        n = c.get(key)
        if n is None:
            n = self.db.execute("SELECT count(*) FROM (SELECT 1 FROM lookup WHERE key=? LIMIT ?)", (key, cap)).fetchone()[0]
            if len(c) > 50_000:
                c.clear()
            c[key] = n
        return n

    def _variants(self, key: str) -> list[str]:
        return list(dict.fromkeys([key, key.capitalize(), key.upper(), key.title()]))

    def _rows(self, key: str, cols: str, limit: int = 60) -> list[tuple]:
        """Rows of the entries a key truly belongs to."""
        n = self.links(key)
        if n <= self.SHARED:
            return self.db.execute(f"SELECT {cols} FROM lookup l JOIN entry e ON e.id=l.id WHERE l.key=? LIMIT ?", (key, limit)).fetchall()
        # shared by many: no verb but the one it names (machen is not a form of saubermachen); by very many: no adjective either
        bad = self._NOT_A_FORM if n > self.POPULAR else ("verb",)
        var = self._variants(key)
        extra = [lem for lem, k in self.KEEP if k == key]
        sql = (f"SELECT {cols} FROM lookup l JOIN entry e ON e.id=l.id WHERE l.key=? AND (e.lemma IN ({','.join('?' * len(var))}) "
               f"OR e.pos NOT IN ({','.join('?' * len(bad))})"
               + (f" OR (e.pos='verb' AND e.lemma IN ({','.join('?' * len(extra))}))" if extra else "") + ") LIMIT ?")
        return self.db.execute(sql, (key, *var, *bad, *extra, limit)).fetchall()

    def lemmas_for(self, key: str) -> list[str]:
        """Base words of a word form, names and abbreviations left out (for word levels)."""
        skip = ("name", "abbrev", "symbol", "letter", "character")
        rows = self._rows(key.lower(), "e.lemma, e.pos")
        return list(dict.fromkeys(r[0] for r in rows if r[0] and r[1] not in skip))

    def forms_of(self, raw: str) -> tuple[str, set[str], set[tuple[str, str]]]:
        """(base word, its one-word forms, split forms of a separable verb as (verb form, particle)).
        gehen → geht, ging, gegangen …;  mitbringen → mitbringt, mitgebracht … and (bringt, mit), (brachte, mit) …"""
        w = normalize(raw).lower()
        forms, split = {w}, set()
        if not w:
            return w, forms, split
        ranked = [e for e in self.lookup(raw) if e.pos != "name"]
        base = ranked[0].lemma if ranked else ""
        if not base:
            return w, forms, split
        bl = base.lower()
        forms.add(bl)
        ids = [r[0] for r in self.db.execute("SELECT id FROM entry WHERE lemma=? AND pos=?", (base, ranked[0].pos))]   # sein the verb, not "sein Haus"
        if not ids:
            return base, forms, split
        keys = {k.lower() for (k,) in self.db.execute(
            f"SELECT DISTINCT key FROM lookup WHERE id IN ({','.join('?' * len(ids))})", ids) if k}
        particles = {k.rsplit(" ", 1)[1] for k in keys if k.count(" ") == 1}
        for k in keys:
            if " " in k:
                a, _, b = k.partition(" ")
                if " " not in b and bl.startswith(b) and len(a) >= 2 and a.isalpha():
                    split.add((a, b))                                   # "bringt mit" of mitbringen
                continue
            if k == bl or k == w:
                continue
            if len(k) < 2 or not any(ch.isalpha() for ch in k) or not all(ch.isalpha() or ch in "-'’" for ch in k):
                continue                                                # "…", "%ig", single letters
            if k in particles and bl.startswith(k):
                continue                                                # the particle alone is not a form
            if self.links(k) > self.SHARED and (bl, k) not in self.KEEP:
                continue                                                # helper verbs, pronouns, other verbs' base words
            forms.add(k)
        return base, forms, split

    _TOK = re.compile(r"[^\W\d_][\w\-'’]*", re.UNICODE)

    def separable_in(self, word: str, sentence: str) -> list[tuple[str, str, str]]:
        """Separable verbs the tapped word belongs to in this sentence: [(base verb, verb form, particle)].
        "Er bringt das Buch mit." + bringt (or mit) → (mitbringen, bringt, mit)."""
        w = normalize(word).lower()
        toks = [m.group(0).lower().strip("'’-") for m in self._TOK.finditer(sentence or "")]
        if not w or w not in toks:
            return []
        pairs = []
        for i, t in enumerate(toks):
            if t == w:
                pairs += [(w, t2) for t2 in toks[i + 1:]] + [(t1, w) for t1 in toks[:i]]
        out, seen = [], set()
        from .library import match_spans
        for a, b in dict.fromkeys(pairs):
            if a == b or len(b) > 12:
                continue
            rows = self.db.execute("SELECT e.lemma FROM lookup l JOIN entry e ON e.id=l.id WHERE l.key=? AND e.pos='verb' LIMIT 4",
                                   (f"{a} {b}",)).fetchall()
            for (lemma,) in rows:
                if lemma.lower().startswith(b) and lemma not in seen and match_spans(sentence, set(), {(a, b)}):
                    seen.add(lemma)
                    out.append((lemma, a, b))
        return out

    def _query(self, key: str) -> list[Entry]:
        out = []
        for lemma, pos, gender, ipa, hyph, audio, data in self._rows(key, "e.lemma,e.pos,e.gender,e.ipa,e.hyph,e.audio,e.data"):
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
