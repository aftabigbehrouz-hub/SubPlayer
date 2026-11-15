"""English sources: VOA Learning English feeds + search, NASA search (run by probe-media.yml)."""
import re, sys, traceback, time
import requests
s = requests.Session(); UA = {"User-Agent": "SubPlayer (language-learning video player)"}
def get(u, **k): return s.get(u, headers=UA, timeout=30, **k)
print("== VOA feeds with video")
try:
    page = get("https://learningenglish.voanews.com/rssfeeds").text
    feeds = list(dict.fromkeys(re.findall(r'href="(/api/[^"]+)"', page)))
    for u in feeds:
        try:
            x = get("https://learningenglish.voanews.com" + u).text
        except Exception as e:
            print("  ", u, "ERR", e); continue
        t = re.search(r"<channel>.*?<title>(.*?)</title>", x, re.S)
        items = re.findall(r"<item>(.*?)</item>", x, re.S)
        vids = [i for i in items if re.search(r'type="video', i)]
        first = items[0] if items else ""
        ti = re.search(r"<title>(.*?)</title>", first, re.S)
        enc = re.search(r'<enclosure[^>]+>', first)
        print(f"  {u:34} {(t.group(1) if t else '')[:40]!r:44} items={len(items):3} video={len(vids):3} | {(ti.group(1) if ti else '')[:40]!r} | {(enc.group(0) if enc else '')[:120]}")
except Exception: traceback.print_exc()
print("\n== VOA search")
for url in ("https://learningenglish.voanews.com/s?k=grammar&tab=video", "https://learningenglish.voanews.com/s?k=grammar"):
    try:
        r = get(url); links = re.findall(r'<a[^>]+href="(/a/[^"]+\.html)"[^>]*>(.*?)</a>', r.text, re.S)
        print(url, r.status_code, len(r.text), "links", len(links))
        for l, t in links[:6]:
            print("   ", l, "|", re.sub(r"<[^>]+>|\s+", " ", t).strip()[:70])
    except Exception: traceback.print_exc()
print("\n== NASA search speed + asset endpoint")
try:
    t0 = time.time(); j = get("https://images-api.nasa.gov/search", params={"q": "Artemis", "media_type": "video", "page_size": 20}).json()
    print("search", round(time.time() - t0, 2), "s", j["collection"]["metadata"].get("total_hits"))
    nid = j["collection"]["items"][0]["data"][0]["nasa_id"]
    a = get(f"https://images-api.nasa.gov/asset/{requests.utils.quote(nid)}").json()
    hrefs = [i["href"] for i in a["collection"]["items"]]
    print("asset", nid, [h.rsplit("/", 1)[-1] for h in hrefs][:10])
    srt = next((h for h in hrefs if h.endswith(".srt")), None)
    if srt:
        r = get(srt.replace("http://", "https://")); print("srt", r.status_code, r.text[:160].replace("\n", " / "))
    med = next((h for h in hrefs if "~medium.mp4" in h or "~mobile.mp4" in h), None)
    if med:
        r = get(med.replace("http://", "https://"), headers={"Range": "bytes=0-1023"}); print("mp4", r.status_code, r.headers.get("Content-Range"))
except Exception: traceback.print_exc()
print("DONE")
