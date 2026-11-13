#!/usr/bin/env python3
"""
Builds SubPlayer's offline German dictionary (SQLite) from Wiktionary data
extracted by kaikki.org (wiktextract). Runs in GitHub Actions.

Sources (streamed, never stored whole):
  A  German Wiktionary, German words  -> IPA, German meanings, examples, audio,
                                         inflected forms, direct EN / FA translations
  B  English Wiktionary, German words -> English meanings, "form of" links (ging -> gehen)
  C  English Wiktionary, English words-> Persian translations (used when A has no
                                         Persian: German -> English -> Persian, labelled)

Output: dict.db with
  entry(id, lemma, pos, gender, ipa, hyph, audio, data JSON)
  lookup(key, id)   key = lower-case lemma or inflected form
"""
import gzip, io, json, re, sqlite3, sys, urllib.request, collections, os

URL_A = "https://kaikki.org/dewiktionary/Deutsch/kaikki.org-dictionary-Deutsch.jsonl"
URL_B = "https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl"
URL_C = "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl"

MAX_SENSES = 8
MAX_EXAMPLES = 2
MAX_EN = 8
MAX_FA = 6


def stream(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SubPlayer-dict-builder"})
    with urllib.request.urlopen(req, timeout=120) as r:
        for raw in io.TextIOWrapper(r, encoding="utf-8"):
            if raw.strip():
                yield json.loads(raw)


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def uniq(seq, limit):
    out, seen = [], set()
    for x in seq:
        x = clean(x)
        k = x.lower()
        if x and k not in seen:
            seen.add(k); out.append(x)
            if len(out) >= limit:
                break
    return out


POS_DE = {"noun": "Substantiv", "verb": "Verb", "adj": "Adjektiv", "adv": "Adverb",
          "name": "Eigenname", "pron": "Pronomen", "prep": "Präposition", "conj": "Konjunktion",
          "num": "Numerale", "intj": "Interjektion", "article": "Artikel", "particle": "Partikel"}
GENDER = {"masculine": "der", "feminine": "die", "neuter": "das"}


def en_keys(text):
    """English phrase -> lookup keys for the English->Persian table."""
    t = re.sub(r"\([^)]*\)", "", text or "").strip().lower()
    t = re.sub(r"^(to|a|an|the)\s+", "", t)
    t = t.strip(" .;,!?")
    return [t] if t and len(t.split()) <= 3 else []


def main(out_path):
    entries = {}            # (lemma, pos) -> dict
    lookup = collections.defaultdict(set)   # key -> {(lemma,pos)}
    form_of_A = []          # (form, lemma)

    # ---------------- A: German Wiktionary ----------------
    nA = 0
    for e in stream(URL_A):
        nA += 1
        word = e.get("word", "")
        pos = e.get("pos", "")
        tags = e.get("tags", []) or []
        senses = e.get("senses", []) or []
        if not word:
            continue
        # inflected-form pages ("Deklinierte Form", "Konjugierte Form"): only keep link to lemma
        if "form-of" in tags or (e.get("pos_title", "").endswith("Form")):
            for s in senses:
                for fo in s.get("form_of", []) or []:
                    if fo.get("word"):
                        form_of_A.append((word, fo["word"]))
            continue
        key = (word, pos)
        ent = entries.get(key)
        if ent is None:
            ent = entries[key] = {"lemma": word, "pos": pos, "gender": "", "ipa": "", "hyph": "",
                                  "audio": "", "senses": [], "en": [], "fa": [], "syn": []}
        for t in tags:
            if t in GENDER and not ent["gender"]:
                ent["gender"] = GENDER[t]
        for snd in e.get("sounds", []) or []:
            if snd.get("ipa") and not ent["ipa"]:
                ent["ipa"] = snd["ipa"]
            if snd.get("mp3_url") and not ent["audio"]:
                ent["audio"] = snd["mp3_url"]
        hy = e.get("hyphenations") or []
        if hy and not ent["hyph"]:
            h = hy[0]
            ent["hyph"] = "·".join(h.get("parts", [])) if isinstance(h, dict) else str(h)
        for s in senses:
            if len(ent["senses"]) >= MAX_SENSES:
                break
            g = clean("; ".join(s.get("glosses", []) or []))
            if not g:
                continue
            ex = [clean(x.get("text", "")) for x in (s.get("examples") or [])]
            ent["senses"].append({"de": g, "ex": [x for x in ex if x][:MAX_EXAMPLES]})
        for t in e.get("translations", []) or []:
            if t.get("lang_code") == "en":
                ent["en"].append(t.get("word", ""))
            elif t.get("lang_code") == "fa":
                ent["fa"].append(t.get("word", ""))
        for s in (e.get("synonyms") or [])[:6]:
            if s.get("word"):
                ent["syn"].append(s["word"])
        lookup[word.lower()].add(key)
        for f in e.get("forms", []) or []:
            fw = clean(f.get("form", ""))
            # skip auxiliary phrases like "hat gemacht" -> keep last word too
            if fw and fw.lower() != word.lower() and len(fw) < 40:
                lookup[fw.lower()].add(key)
                parts = fw.split()
                if len(parts) == 2 and parts[0].lower() in ("hat", "ist", "haben", "sein", "werden", "wird"):
                    lookup[parts[1].lower()].add(key)
    print("A entries read:", nA, "lemmas kept:", len(entries), flush=True)

    by_lemma = collections.defaultdict(list)
    for (l, p) in entries:
        by_lemma[l].append((l, p))
    for form, lemma in form_of_A:
        for k in by_lemma.get(lemma, []):
            lookup[form.lower()].add(k)

    # ---------------- B: English Wiktionary (German words) ----------------
    nB = 0; enriched = 0
    for e in stream(URL_B):
        nB += 1
        word = e.get("word", "")
        pos = e.get("pos", "")
        if not word:
            continue
        glosses = []
        for s in e.get("senses", []) or []:
            fos = s.get("form_of", []) or []
            if fos:
                for fo in fos:
                    lw = fo.get("word")
                    for k in by_lemma.get(lw, []):
                        lookup[word.lower()].add(k)
                continue
            g = clean("; ".join(s.get("glosses", []) or []))
            if g:
                glosses.append(g)
        if not glosses:
            continue
        targets = [(word, pos)] if (word, pos) in entries else by_lemma.get(word, [])
        if not targets:
            # word only in English Wiktionary: add a minimal entry
            key = (word, pos)
            entries[key] = {"lemma": word, "pos": pos, "gender": "", "ipa": "", "hyph": "", "audio": "",
                            "senses": [], "en": [], "fa": [], "syn": []}
            for snd in e.get("sounds", []) or []:
                if snd.get("ipa") and not entries[key]["ipa"]:
                    entries[key]["ipa"] = snd["ipa"]
            by_lemma[word].append(key)
            lookup[word.lower()].add(key)
            targets = [key]
        for k in targets:
            ent = entries[k]
            ent.setdefault("en_gloss", [])
            ent["en_gloss"].extend(glosses)
            enriched += 1
    print("B entries read:", nB, "enriched:", enriched, flush=True)

    # English keys we need Persian for
    need = set()
    for ent in entries.values():
        if ent["fa"]:
            continue
        for w in ent["en"][:MAX_EN]:
            need.update(en_keys(w))
        for g in ent.get("en_gloss", [])[:3]:
            for part in g.split(";"):
                need.update(en_keys(part))
    print("English keys needing Persian:", len(need), flush=True)

    # ---------------- C: English Wiktionary (English words -> Persian) ----------------
    en2fa = {}
    nC = 0
    for e in stream(URL_C):
        nC += 1
        w = (e.get("word") or "").lower()
        if w not in need:
            continue
        fa = [t.get("word", "") for t in (e.get("translations") or [])
              if (t.get("lang_code") or t.get("code")) == "fa"]
        if fa:
            en2fa.setdefault(w, [])
            en2fa[w].extend(fa)
    print("C entries read:", nC, "English words with Persian:", len(en2fa), flush=True)

    # ---------------- write SQLite ----------------
    if os.path.exists(out_path):
        os.remove(out_path)
    db = sqlite3.connect(out_path)
    db.execute("PRAGMA page_size=4096")
    db.execute("CREATE TABLE entry(id INTEGER PRIMARY KEY, lemma TEXT, pos TEXT, gender TEXT, ipa TEXT, hyph TEXT, audio TEXT, data TEXT)")
    db.execute("CREATE TABLE lookup(key TEXT, id INTEGER)")
    db.execute("CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT)")
    ids = {}
    stats = collections.Counter()
    rows = []
    for i, (k, ent) in enumerate(sorted(entries.items()), start=1):
        if not ent["senses"] and not ent.get("en_gloss") and not ent["en"]:
            continue
        ids[k] = i
        fa = uniq(ent["fa"], MAX_FA)
        fa_via = []
        if not fa:
            cand = []
            for w in ent["en"][:MAX_EN]:
                cand += en_keys(w)
            for g in ent.get("en_gloss", [])[:3]:
                for part in g.split(";"):
                    cand += en_keys(part)
            for c in cand:
                for f in en2fa.get(c, [])[:3]:
                    fa_via.append(f + "  (" + c + ")")
            fa_via = uniq(fa_via, MAX_FA)
        stats["entries"] += 1
        if ent["ipa"]: stats["ipa"] += 1
        if fa: stats["fa_direct"] += 1
        elif fa_via: stats["fa_via_en"] += 1
        if ent.get("en_gloss") or ent["en"]: stats["english"] += 1
        if any(s["ex"] for s in ent["senses"]): stats["examples"] += 1
        data = {
            "posDe": POS_DE.get(ent["pos"], ent["pos"]),
            "senses": ent["senses"],
            "enGloss": uniq(ent.get("en_gloss", []), MAX_SENSES),
            "en": uniq(ent["en"], MAX_EN),
            "fa": fa,
            "faVia": fa_via,
            "syn": uniq(ent["syn"], 6),
        }
        rows.append((i, ent["lemma"], ent["pos"], ent["gender"], ent["ipa"], ent["hyph"], ent["audio"],
                     json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
        if len(rows) >= 20000:
            db.executemany("INSERT INTO entry VALUES(?,?,?,?,?,?,?,?)", rows); rows = []
    if rows:
        db.executemany("INSERT INTO entry VALUES(?,?,?,?,?,?,?,?)", rows)
    lrows = []
    for key, ks in lookup.items():
        for k in ks:
            if k in ids:
                lrows.append((key, ids[k]))
    lrows = sorted(set(lrows))
    db.executemany("INSERT INTO lookup VALUES(?,?)", lrows)
    db.execute("CREATE INDEX lookup_key ON lookup(key)")
    db.execute("INSERT INTO meta VALUES('version','1')")
    db.execute("INSERT INTO meta VALUES('source','Wiktionary (de, en) via kaikki.org, CC BY-SA 4.0')")
    db.commit()
    db.execute("VACUUM")
    db.close()
    print("STATS", dict(stats), "lookup rows", len(lrows), flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dict.db")
