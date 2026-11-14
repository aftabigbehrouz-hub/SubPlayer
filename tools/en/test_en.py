import json, sqlite3, sys
WORDS = ["house", "went", "children", "better", "running", "although", "apartment", "beautiful", "thought", "got",
         "mice", "bought", "learn", "station", "however", "eventually", "quickly", "train"]
db = sqlite3.connect(sys.argv[1]); found = 0
for w in WORDS:
    rows = db.execute("SELECT e.lemma,e.pos,e.ipa,e.audio,e.data FROM lookup l JOIN entry e ON e.id=l.id WHERE l.key=? LIMIT 40", (w,)).fetchall()
    def score(r):
        d = json.loads(r[4]); s = 0
        if r[0] == w: s += 3
        if d["fa"]: s += 2
        if d["deTr"]: s += 2
        return (s, len(d["senses"]))
    rows = sorted(rows, key=score, reverse=True)[:1]
    found += bool(rows)
    for lemma, pos, ipa, audio, data in rows:
        d = json.loads(data)
        print(f"--- {w} -> {lemma} [{pos}] {ipa} audio={'y' if audio else 'n'}")
        if d["senses"]: print("   def:", d["senses"][0]["de"][:100], "| ex:", (d["senses"][0]["ex"] or [""])[0][:80])
        print("   FA:", ", ".join(d["fa"][:3]) or "-", "| DE:", ", ".join(d["deTr"][:3]) or "-")
print(f"FOUND {found}/{len(WORDS)}")
