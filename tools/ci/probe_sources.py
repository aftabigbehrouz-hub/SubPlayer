"""Probe for Discover ▸ My sources: real Telegram channels, sites and feeds (run on GitHub, where they can be reached)."""
import os
import sys
import traceback

sys.path.insert(0, "windows")
from subplayer_win import sources  # noqa: E402

TRIES = os.environ.get("PROBE_SOURCES", "").split() or [
    "t.me/dw_persian", "https://t.me/s/bbcpersian", "@euronewspe", "t.me/durov",
    "https://www.deutschlandfunk.de", "https://www.dw.com/de/themen/s-9077", "https://feeds.br.de/radiowissen/feed.xml",
    "https://www.tagesschau.de/multimedia/sendung/tagesschau_in_100_sekunden", "https://www.youtube.com/@tagesschau",
]
os.makedirs("probe-out", exist_ok=True)
import requests  # noqa: E402
raw = requests.get("https://t.me/s/bbcpersian", headers={"User-Agent": sources.UA}, timeout=30).text
open("probe-out/tg-bbcpersian.html", "w", encoding="utf-8").write(raw)
i = raw.find("tgme_widget_message_video_player")
print("=== raw Telegram post with a video ===")
import base64, zlib
print("RAWB64:" + base64.b64encode(zlib.compress(raw.encode("utf-8"), 9)).decode())
print("=== end raw")
for t in TRIES:
    print("====", t)
    try:
        s = sources.detect(t)
        print("  source:", s)
        vs = sources.videos(s, tg_pages=2)
        print(f"  {len(vs)} videos; downloadable: {sum(1 for v in vs if v.url_video)}")
        for v in vs[:4]:
            print("   -", v.date, v.length, "|", v.title[:70], "|", (v.url_video or "(too big)")[:90])
        if s.kind == "telegram" and vs:
            fresh = sources.fresh_video(vs[0].url_website)
            print("  fresh video address:", fresh[:90])
            if fresh:
                r = requests.get(fresh, headers={"User-Agent": sources.UA, "Range": "bytes=0-1023"}, timeout=30)
                print("  first KB:", r.status_code, r.headers.get("Content-Type"), len(r.content))
    except Exception as e:
        print("  ERROR", e.__class__.__name__, str(e)[:300])
        traceback.print_exc(limit=2)
