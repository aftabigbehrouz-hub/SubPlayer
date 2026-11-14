#!/usr/bin/env python3
"""
SubPlayer offline ENGLISH dictionary from English Wiktionary (kaikki.org extract).
Same SQLite layout as the German one (entry + lookup), data JSON:
  posDe (part of speech label), senses[{de: English definition, ex: [examples]}],
  enGloss [], en [], fa [Persian], faVia [], syn [synonyms], deTr [German translations], lang "en"
"""
import io, json, re, sqlite3, sys, urllib.request, collections, os

URL = "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl"
SKIP_POS = {"name", "character", "symbol", "prefix", "suffix", "infix", "interfix", "affix", "punct",
            "abbrev", "phrase", "proverb", "romanization", "contraction"}
POS_LABEL = {"noun": "noun", "verb": "verb", "adj": "adjective", "adv": "adverb", "pron": "pronoun", "prep": "preposition",
             "conj": "conjunction", "intj": "interjection", "num": "numeral", "det": "determiner", "article": "article",
             "particle": "particle", "prep_phrase": "phrase"}


def stream(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SubPlayer-dict-builder"})
    with urllib.request.urlopen(req, timeout=120) as r:
        for raw in io.TextIOWrapper(r, encoding="utf-8"):
            if raw.strip():
                yield json.loads(raw)


def clean(s): return re.sub(r"\s+", " ", s or "").strip()


def uniq(seq, n):
    out, seen = [], set()
    for x in seq:
        x = clean(x); k = x.lower()
        if x and k not in seen:
            seen.add(k); out.append(x)
            if len(out) >= n: break
    return out


def tr_of(e, code, senses_limit=3):
    out = [t.get("word", "") for t in (e.get("translations") or []) if (t.get("lang_code") or t.get("code")) == code]
    for s in (e.get("senses") or [])[:senses_limit]:
        out += [t.get("word", "") for t in (s.get("translations") or []) if (t.get("lang_code") or t.get("code")) == code]
    return out


def ipa_of(e):
    uk = us = other = ""
    for s in e.get("sounds") or []:
        ipa = s.get("ipa")
        if not ipa: continue
        tags = " ".join(s.get("tags") or []) + " " + " ".join(s.get("raw_tags") or [])
        if not uk and ("Received-Pronunciation" in tags or "UK" in tags): uk = ipa
        elif not us and ("General-American" in tags or "US" in tags): us = ipa
        elif not other: other = ipa
    if uk and us and uk != us: return f"UK {uk} · US {us}"
    return uk or us or other


def main(out):
    entries = {}
    lookup = collections.defaultdict(set)
    form_of = []
    n = 0
    for e in stream(URL):
        n += 1
        word = e.get("word", ""); pos = e.get("pos", "")
        if not word or pos in SKIP_POS or len(word.split()) > 3 or len(word) > 40:
            continue
        senses = e.get("senses") or []
        real = [s for s in senses if not s.get("form_of") and "form-of" not in (s.get("tags") or [])]
        for s in senses:
            for fo in s.get("form_of") or []:
                if fo.get("word"): form_of.append((word, fo["word"]))
        if not real:
            continue
        fa = tr_of(e, "fa"); de = tr_of(e, "de"); ipa = ipa_of(e)
        if not (fa or de or ipa):
            continue          # obscure entries without pronunciation or translations
        key = (word, pos)
        ent = entries.get(key)
        if ent is None:
            ent = entries[key] = {"lemma": word, "pos": pos, "ipa": ipa, "audio": "", "senses": [], "fa": [], "de": [], "syn": []}
        if not ent["ipa"]: ent["ipa"] = ipa
        for snd in e.get("sounds") or []:
            if snd.get("mp3_url") and not ent["audio"]: ent["audio"] = snd["mp3_url"]
        for s in real:
            if len(ent["senses"]) >= 5: break
            gl = s.get("glosses") or s.get("raw_glosses") or []
            g = clean(gl[-1] if gl else "")[:220]
            if not g: continue
            ex = [clean(x.get("text", "")) for x in (s.get("examples") or [])]
            ex = sorted([x for x in ex if x and len(x) <= 140], key=len)[:1]
            ent["senses"].append({"de": g, "ex": ex})
        ent["fa"] += fa; ent["de"] += de
        ent["syn"] += [x.get("word", "") for x in (e.get("synonyms") or [])[:6]]
        lookup[word.lower()].add(key)
        for f in e.get("forms") or []:
            fw = clean(f.get("form", ""))
            if fw and " " not in fw and fw.lower() != word.lower() and len(fw) < 40:
                lookup[fw.lower()].add(key)
    print("read", n, "kept", len(entries), flush=True)
    by_lemma = collections.defaultdict(list)
    for k in entries: by_lemma[k[0]].append(k)
    for f, lemma in form_of:
        for k in by_lemma.get(lemma, []): lookup[f.lower()].add(k)

    if os.path.exists(out): os.remove(out)
    db = sqlite3.connect(out)
    db.execute("CREATE TABLE entry(id INTEGER PRIMARY KEY, lemma TEXT, pos TEXT, gender TEXT, ipa TEXT, hyph TEXT, audio TEXT, data TEXT)")
    db.execute("CREATE TABLE lookup(key TEXT, id INTEGER, PRIMARY KEY(key, id)) WITHOUT ROWID")
    db.execute("CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT)")
    ids = {}; rows = []; stats = collections.Counter()
    for i, (k, ent) in enumerate(sorted(entries.items()), 1):
        ids[k] = i
        fa = uniq(ent["fa"], 6); de = uniq(ent["de"], 6)
        stats["entries"] += 1
        if ent["ipa"]: stats["ipa"] += 1
        if fa: stats["fa"] += 1
        if de: stats["de"] += 1
        if any(s["ex"] for s in ent["senses"]): stats["examples"] += 1
        data = {"posDe": POS_LABEL.get(ent["pos"], ent["pos"]), "senses": ent["senses"], "enGloss": [], "en": [],
                "fa": fa, "faVia": [], "syn": uniq(ent["syn"], 6), "deTr": de, "lang": "en"}
        rows.append((i, ent["lemma"], ent["pos"], "", ent["ipa"], "", ent["audio"], json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
        if len(rows) >= 20000:
            db.executemany("INSERT INTO entry VALUES(?,?,?,?,?,?,?,?)", rows); rows = []
    if rows: db.executemany("INSERT INTO entry VALUES(?,?,?,?,?,?,?,?)", rows)
    lrows = sorted({(key, ids[k]) for key, ks in lookup.items() for k in ks if k in ids})
    db.executemany("INSERT INTO lookup VALUES(?,?)", lrows)
    db.execute("INSERT INTO meta VALUES('version','1')")
    db.execute("INSERT INTO meta VALUES('lang','en')")
    db.execute("INSERT INTO meta VALUES('source','English Wiktionary via kaikki.org, CC BY-SA 4.0')")
    db.commit(); db.execute("VACUUM"); db.close()
    print("STATS", dict(stats), "lookup rows", len(lrows), flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dict-en.db")
