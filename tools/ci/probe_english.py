import sys, time, pathlib
sys.path.insert(0, "windows")
import requests, av
from subplayer_win import english as E, linkimport as L
s = requests.Session()
for sh in E.PODCASTS:
    try:
        t0 = time.time(); fs = E.shelf_films(sh, 5, session=s)
        print(f"{sh.title[:28]:28} {len(fs)} {time.time()-t0:.1f}s  {fs[0].date} {fs[0].length:>8}  {fs[0].title[:40]!r}")
    except Exception as e:
        print(sh.title, "FAILED", e)
print("search 'climate':", [(f.channel, f.title[:30]) for f in E.podcast_search("climate", 5, s)])
f = E.shelf_films(E.PODCASTS[0], 1, session=s)[0]
found = L.Found(f.video(), f"{f.topic} – {f.title}")
out = L.download(found, pathlib.Path("/tmp"), lambda d, t: None)
c = av.open(str(out)); a = c.streams.audio[0]
print("downloaded:", out.name, out.stat().st_size, "bytes; audio", a.codec_context.name, a.codec_context.sample_rate, "Hz;", round(c.duration / 1e6), "s")
print("DONE")
