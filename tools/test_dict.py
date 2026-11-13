#!/usr/bin/env python3
"""Checks the built dictionary with real subtitle-style words (run in CI, output in the log)."""
import json, sqlite3, sys

WORDS = ["Haus", "Häuser", "ging", "gegangen", "schöne", "gemacht", "ist", "hat", "Hause",
         "aufgestanden", "Mädchen", "trotzdem", "Bahnhof", "eigentlich", "Wohnung", "gesagt",
         "kannst", "Fenster", "fährt", "Kindern", "besser", "Entschuldigung", "Brot", "schnell"]

db = sqlite3.connect(sys.argv[1] if len(sys.argv) > 1 else "dict.db")
found = 0
for w in WORDS:
    rows = db.execute(
        "SELECT e.lemma,e.pos,e.gender,e.ipa,e.audio,e.data FROM lookup l JOIN entry e ON e.id=l.id "
        "WHERE l.key=? LIMIT 3", (w.lower(),)).fetchall()
    if rows:
        found += 1
    print(f"--- {w}: {len(rows)} match(es)")
    for lemma, pos, gender, ipa, audio, data in rows:
        d = json.loads(data)
        print(f"  {gender} {lemma} [{pos}] IPA {ipa} audio={'yes' if audio else 'no'}")
        if d["senses"]:
            s = d["senses"][0]
            print(f"   DE: {s['de'][:110]}")
            if s["ex"]:
                print(f"   Bsp: {s['ex'][0][:110]}")
        print(f"   EN: {('; '.join(d['enGloss'][:2]) or ', '.join(d['en'][:4]))[:120]}")
        print(f"   FA: {', '.join(d['fa'][:4]) or '-'} | via EN: {', '.join(d['faVia'][:3]) or '-'}")
print(f"FOUND {found}/{len(WORDS)}")
