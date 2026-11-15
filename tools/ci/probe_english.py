import re, sys, requests
sys.path.insert(0, "windows")
from subplayer_win import english as E
s = requests.Session()
for sh in (E.SHELVES[0], E.SHELVES[1], E.SHELVES[2], E.SHELVES[4]):
    f = E.shelf_films(sh, 2, session=s)[0]
    pg = s.get(f.url_website, headers={"User-Agent": E.UA}, timeout=30).text
    print("==", sh.title, f.url_website, len(pg))
    for pat in (r'[^"\'\s<>]*\.mp4[^"\'\s<>]*', r'[^"\'\s<>]*\.m3u8[^"\'\s<>]*', r'youtube\.com/[^"\'\s<>]+', r'youtu\.be/[^"\'\s<>]+',
                r'data-src="[^"]+"', r'data-type="[^"]+"', r'"contentUrl":"[^"]+"', r'/embed/player/[^"\'\s<>]+', r'data-sources=\'[^\']{0,200}'):
        hits = list(dict.fromkeys(re.findall(pat, pg)))[:4]
        if hits:
            print("  ", pat[:24], hits)
    m = re.search(r'<div[^>]+class="[^"]*(?:player|video)[^"]*"[^>]*>', pg)
    print("   player div:", m.group(0)[:300] if m else None)
print("DONE")
