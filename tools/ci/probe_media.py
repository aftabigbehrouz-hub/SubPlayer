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
            try:
                import re as _re
                pg = s.get(f.url_website, headers={"User-Agent": L.UA}, timeout=30).text
                mt = L.OG_TITLE.search(pg) or L.TITLE.search(pg)
                print("         page title:", repr(mt.group(1)[:120]) if mt else None, " catalogue title:", repr(f.title[:80]))
                print("         queries:", M._title_queries(mt.group(1) if mt else ""))
                print("         mp4/m3u8 in page:", len(_re.findall(r"\.mp4", pg)), len(_re.findall(r"\.m3u8", pg)), " len", len(pg))
            except Exception as e2:
                print("         (page fetch failed)", e2)

print("\n== shelf candidates")
for kind, q, chans in M.SHELF_TRIALS:
    try:
        fs, total = M.search(text=q if kind == "text" else "", topic=q if kind == "topic" else "", channels=chans, size=10, session=s)
        print(f"{kind:5} {q!r:22} {chans} total={total} sub={sum(f.has_subtitles for f in fs)}/{len(fs)} {[f.title[:24] for f in fs[:2]]}")
    except Exception as e:
        print(q, "FAILED", e)

print("\n== ARD: all video files of one item")
try:
    fs, _ = M.search(channels=["ARD"], length=(600, 3600), size=10, session=s)
    f = next(x for x in fs if L.ard_id(x.url_website))
    r = s.get(f"https://api.ardmediathek.de/page-gateway/pages/ard/item/{L.ard_id(f.url_website)}",
              params={"devicetype": "pc", "embedded": "true"}, headers={"User-Agent": L.UA}, timeout=30)
    import json as _j
    d = r.json()
    for path, v in L._walk(d):
        if isinstance(v, str) and (".mp4" in v or ".m3u8" in v):
            print("   ", "/".join(path[-4:]), v[-70:])
        if path and path[-1] in ("maxHResolutionPx", "forcedLabel", "kind", "languageCode") and len(path) > 4:
            print("      ", "/".join(path[-4:]), "=", v)
    print("chosen:", L.ard_item(L.ard_id(f.url_website), s).video_url[-70:])
except Exception:
    traceback.print_exc()

print("\n== Arte stream diagnosis")
try:
    fs, _ = M.search(channels=["Arte"], length=(600, 3600), size=5, session=s)
    found = L.resolve(fs[0].url_website, s)
    m = s.get(found.video_url, headers={"User-Agent": L.UA}, timeout=30)
    print("master", m.status_code, m.headers.get("Content-Type"))
    lines = m.text.splitlines()
    print("\n".join("   " + l[:150] for l in lines[:14]))
    from urllib.parse import urljoin
    var = next((l for l in lines if l and not l.startswith("#")), None)
    if var:
        vu = urljoin(found.video_url, var)
        vr = s.get(vu, headers={"User-Agent": L.UA}, timeout=30)
        vl = vr.text.splitlines()
        print("variant", vr.status_code, "\n" + "\n".join("   " + l[:150] for l in vl[:10]))
        seg = next((l for l in vl if l and not l.startswith("#")), None)
        if seg:
            su = urljoin(vu, seg)
            sr = s.get(su, headers={"User-Agent": L.UA, "Range": "bytes=0-1023"}, timeout=30)
            print("segment", sr.status_code, sr.headers.get("Content-Type"), su[-80:])
except Exception:
    traceback.print_exc()

print("\n== Arte stream copy (20 s)")
try:
    fs, _ = M.search(channels=["Arte"], length=(600, 3600), size=5, session=s)
    f = fs[0]
    found = L.resolve(f.url_website, s)
    print("resolved:", found.hls, found.title[:60], found.duration, found.video_url[:90])
    import pathlib, av
    out = pathlib.Path("/tmp/arte.part.mp4")
    seen = {"t": 0}
    def prog(d, t): seen["t"] = d
    L._download_hls(found, out, prog, lambda: False, stop_at=20)
    c = av.open(str(out))
    print("sample:", out.stat().st_size, "bytes", [(st.type, st.codec_context.name) for st in c.streams], "duration", c.duration / 1e6 if c.duration else None)
    nfr = sum(1 for _ in c.decode(video=0))
    print("decoded video frames:", nfr)
    c.close()
    # cancelled deletes the file: run again keeping it by copying logic quickly
    src = av.open(found.video_url, options={"user_agent": L.UA})
    print("streams:", [(st.type, st.codec_context.name, getattr(st.codec_context, 'height', None), (st.metadata or {}).get('language')) for st in src.streams][:12])
    src.close()
    # catalogue manifest link (no .m3u8 ending) -> detected by content type?
    r = s.get(f.video(), headers={"User-Agent": L.UA}, stream=True, timeout=30)
    print("catalogue link content-type:", r.headers.get("Content-Type")); r.close()
except Exception as e:
    traceback.print_exc()

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
