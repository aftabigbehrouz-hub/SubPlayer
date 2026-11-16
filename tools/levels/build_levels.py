"""
Builds the word-level files the apps colour subtitles with (levels-de.tsv, levels-en.tsv: "word<TAB>level", 1=A1 … 6=C2).

English: CEFR-J Vocabulary Profile 1.5 (A1–B2; Tono Laboratory, TUFS — free incl. commercial use, with citation) and the
Octanove Vocabulary Profile C1/C2 1.0 (CC BY-SA 4.0); words in neither list get an estimate from their frequency.
German: the 3,041 words of the WordFeather list (Goethe/telc-oriented levels A1–C2, github.com/abdullahbutt/wordfeather,
version of 6 June 2026 — released under CC0 1.0 then; later versions are CC BY-NC and are NOT used; the CC0 copy is in
tools/levels/data) get their listed level, marked "L" in the file. Every other word's level is ESTIMATED from how common
its base word (lemma) is in subtitles — FrequencyWords 2018 (Hermit Dave, from OpenSubtitles; CC BY-SA 4.0) — with the
forms joined to their base word through SubPlayer's German Wiktionary dictionary. Labelled as an estimate in the apps.

File format: "word<TAB>level" or "word<TAB>level<TAB>L" (L = from a published list, not estimated).

usage: python build_levels.py DE_DICT.db EN_DICT.db de_50k.txt en_50k.txt cefrj.csv octanove.csv OUT_DIR
"""
import csv, json, re, sqlite3, sys
from collections import defaultdict
from pathlib import Path

de_db, en_db, de_freq, en_freq, cefrj, octa, out = sys.argv[1:8]
out = Path(out); out.mkdir(parents=True, exist_ok=True)
LV = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "windows"))
from subplayer_win.dictionary import Dictionary  # noqa: E402  (its _rows() leaves out links that are no word forms)


def lemmas_of(db, form):
    # "worden", "gewesen", "mich", "ab" … hang under thousands of verbs in the dictionary file (helper verbs, pronouns and
    # particles of their conjugation tables); counted there they made rare verbs look like everyday words
    rows = db._rows(form, "e.lemma, e.pos", 20)
    rows = [(l, p) for l, p in rows if p not in ("name", "abbrev", "symbol", "character", "suffix", "prefix", "letter")]
    if not rows:
        return []
    exact = [l for l, p in rows if l.lower() == form]
    return [exact[0].lower()] if exact else [rows[0][0].lower()]


def lemma_freq(db_file, freq_file):
    db = Dictionary(db_file)
    tot = defaultdict(int)
    for line in open(freq_file, encoding="utf-8"):
        try:
            w, n = line.rstrip("\n").rsplit(" ", 1)
        except ValueError:
            continue
        w = w.lower()
        if not re.fullmatch(r"[a-zäöüß][a-zäöüß'-]*", w):
            continue
        for lem in lemmas_of(db, w):
            tot[lem] += int(n)
    return sorted(tot, key=lambda k: -tot[k])


def band(rank, cuts):
    for lv, c in enumerate(cuts, 1):
        if rank < c:
            return lv
    return 6


# German: cumulative cut-offs by base-word rank (A1 1000, A2 2000, B1 4000, B2 7000, C1 12000, then C2)
de_rank = lemma_freq(de_db, de_freq)
de = {w: band(i, (1000, 2000, 4000, 7000, 12000)) for i, w in enumerate(de_rank)}


def wordfeather_lemma(entry: str) -> str | None:
    """"der Kollege, -n" → kollege · "die Zinsen (Pl.)" → zinsen · "sich erholen" → erholen · phrases → None."""
    t = re.sub(r"\s*\(.*?\)", "", entry).split(",")[0].strip()
    t = re.sub(r"^(der|die|das|der/die)\s+", "", t)
    t = re.sub(r"^sich\s+", "", t)
    if not t or " " in t or not re.fullmatch(r"[^\W\d_][\w\-]*", t):
        return None
    return t.lower()


listed = {}
wf = Path(__file__).resolve().parent / "data" / "wordfeather-cc0-2026-06-06.json"
for e in json.loads(wf.read_text(encoding="utf-8")):
    lem, lv = wordfeather_lemma(e.get("de", "")), LV.get(e.get("level", ""))
    if lem and lv:
        listed[lem] = min(lv, listed.get(lem, 9))       # a word listed twice (noun and verb) keeps its lower level
changed = sum(1 for w, lv in listed.items() if w in de and de[w] != lv)
for w, lv in listed.items():
    de[w] = lv
order = de_rank + [w for w in listed if w not in set(de_rank)]
with open(out / "levels-de.tsv", "w", encoding="utf-8") as f:
    for w in order:
        f.write(f"{w}\t{de[w]}" + ("\tL" if w in listed else "") + "\n")
print(f"German: {len(order)} words, {len(listed)} from the WordFeather list ({changed} estimates replaced)")

# English: CEFR-J + Octanove first, frequency estimate for the rest
en = {}
for path in (cefrj, octa):
    for r in csv.DictReader(open(path, encoding="utf-8")):
        lv = LV.get((r.get("CEFR") or "").strip().upper())
        if not lv:
            continue
        for hw in re.split(r"[/,]", r["headword"]):
            hw = hw.strip().lower()
            if hw and " " not in hw:
                en[hw] = min(en.get(hw, 9), lv)
listed = len(en)
en_rank = lemma_freq(en_db, en_freq)
for i, w in enumerate(en_rank):
    if w not in en:
        en[w] = band(i, (0, 0, 0, 4000, 9000))           # not in the lists: B2 / C1 / C2 by frequency
with open(out / "levels-en.tsv", "w", encoding="utf-8") as f:
    for w in sorted(en):
        f.write(f"{w}\t{en[w]}\n")

for name, d in (("de", de), ("en", en)):
    cnt = defaultdict(int)
    for v in d.values():
        cnt[v] += 1
    print(name, len(d), {k: cnt[k] for k in sorted(cnt)}, f"(from lists: {listed})" if name == "en" else "")
