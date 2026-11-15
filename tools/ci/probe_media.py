"""Live check of the Windows app's broadcaster support (run by .github/workflows/probe-media.yml)."""
import sys, time, traceback
sys.path.insert(0, "windows")
import requests
from subplayer_win import linkimport as L, mediathek as M, subtitles as S

s = requests.Session()
ok = True

def head(url):
    try:
        r = s.get(url, headers={"User-Agent": L.UA, "Range": "bytes=0-2047"}, timeout=30, stream=True)
        return r.status_code, r.headers.get("Content-Type", ""), r.headers.get("Content-Range", "")
    except Exception as e:
        return "ERR", str(e)[:80], ""

print("== catalogue search per channel")
picked = {}
for ch in ["ARD", "ZDF", "3sat", "Arte", "DW", "KiKA", "phoenix"]:
    try:
        t0 = time.time()
        films, total = M.search(channels=[ch], length=(120, 3600), size=12, session=s)
        print(f"{ch:8} total={total:>7} got={len(films):2} {time.time()-t0:.1f}s")
        for f in films[:3]:
            print(f"    {f.date} {f.length:>10} sub={'Y' if f.has_subtitles else '-'} {f.topic[:30]!r} {f.title[:50]!r}")
            print(f"       web={f.url_website[:110]}")
            print(f"       mp4={f.url_video[:110]} hd={'Y' if f.url_video_hd else '-'} low={'Y' if f.url_video_low else '-'}")
        withsub = [f for f in films if f.has_subtitles]
        picked[ch] = (withsub or films)[:2]
    except Exception as e:
        ok = False
        print(ch, "SEARCH FAILED", e)

print("\n== free-text + subtitles filter")
try:
    films, total = M.search("Terra X", subtitles_only=True, size=5, session=s)
    print("terra x with subs:", total, [f.title[:40] for f in films])
except Exception as e:
    ok = False; print("FAILED", e)

print("\n== shelves")
for sh in M.SHELVES:
    try:
        fs = M.shelf_films(sh, 6, session=s)
        print(f"{sh.title[:34]:34} {len(fs)}  {[f.title[:28] for f in fs[:3]]}")
    except Exception as e:
        print(sh.title, "FAILED", e)

print("\n== catalogue film: mp4 reachable + subtitles readable")
for ch, films in picked.items():
    for f in films[:1]:
        st = head(f.video())
        print(f"{ch:8} mp4 {st}")
        if f.url_subtitle:
            srt = L.subtitle_srt(f.url_subtitle, s)
            n = len(S.parse(srt)) if srt else 0
            print(f"         subtitles {f.url_subtitle[:90]} -> {n} lines" + (f" lang={S.guess_lang(S.parse(srt))} first={S.parse(srt)[0].text[:50]!r}" if n else ""))

print("\n== resolve() on the broadcaster pages (what a user pastes)")
for ch, films in picked.items():
    for f in films[:2]:
        if not f.url_website:
            continue
        try:
            t0 = time.time()
            found = L.resolve(f.url_website, s)
            st = head(found.video_url) if not found.hls else ("HLS",)
            print(f"{ch:8} OK {time.time()-t0:.1f}s hls={found.hls} sub={'Y' if found.subtitle_url else '-'} {found.title[:50]!r}")
            print(f"         page {f.url_website[:100]}")
            print(f"         video {found.video_url[:100]} -> {st}")
        except Exception as e:
            print(f"{ch:8} FAIL {f.url_website[:100]}\n         {type(e).__name__}: {str(e)[:160]}")

print("\n== tagesschau page")
try:
    r = s.get("https://www.tagesschau.de/multimedia", headers={"User-Agent": L.UA}, timeout=30)
    import re
    links = list(dict.fromkeys(re.findall(r'href="(/multimedia/[^"]+\.html)"', r.text)))[:3]
    for l in links:
        try:
            found = L.resolve("https://www.tagesschau.de" + l, s)
            print("OK", l[:70], found.video_url[:90], "sub" if found.subtitle_url else "")
        except Exception as e:
            print("FAIL", l[:70], e)
except Exception as e:
    print("tagesschau FAILED", e)
print("\nDONE", "ok" if ok else "with failures")
