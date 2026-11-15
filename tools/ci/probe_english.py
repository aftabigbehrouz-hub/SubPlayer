"""Live check of the Windows app's English sources (VOA Learning English, NASA)."""
import sys, time, traceback
sys.path.insert(0, "windows")
import requests
from subplayer_win import english as E, linkimport as L, subtitles as S
s = requests.Session()
print("== English shelves")
for sh in E.SHELVES:
    try:
        t0 = time.time(); fs = E.shelf_films(sh, 8, session=s)
        print(f"{sh.title[:32]:32} {len(fs):2} {time.time()-t0:.1f}s  {[f.title[:30] for f in fs[:2]]}")
    except Exception as e:
        print(sh.title, "FAILED", e)
print("\n== search 'grammar' (VOA + NASA) and 'Mars' (NASA)")
for q, ch in (("grammar", None), ("Mars", ["NASA"])):
    try:
        fs, total = E.search(q, ch, 10, 0, s); print(q, total, [(f.channel, f.title[:30]) for f in fs[:4]])
    except Exception: traceback.print_exc()
print("\n== resolve + download check")
for sh in (E.SHELVES[0], E.SHELVES[3], E.SHELVES[6]):
    try:
        f = E.shelf_films(sh, 3, session=s)[0]
        t0 = time.time(); found = L.resolve(f.url_website, s)
        r = s.get(found.video_url, headers={"User-Agent": L.UA, "Range": "bytes=0-2047"}, timeout=30, stream=True)
        print(f"{sh.title[:28]:28} {time.time()-t0:.1f}s -> {r.status_code} {r.headers.get('Content-Range')} {found.video_url[-60:]}")
        if found.subtitle_url:
            srt = L.subtitle_srt(found.subtitle_url, s); n = len(S.parse(srt)) if srt else 0
            print(f"{'':28} subtitles: {n} lines" + (f", lang {S.guess_lang(S.parse(srt))}: {S.parse(srt)[1].text[:60]!r}" if n > 2 else ""))
    except Exception as e:
        print(sh.title, "FAIL", type(e).__name__, str(e)[:150])
print("DONE")
