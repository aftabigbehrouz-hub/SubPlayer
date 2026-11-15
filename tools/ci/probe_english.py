"""Explores English video sources for Discover (run by probe-media.yml with PROBE=english)."""
import json, re, sys, traceback
import requests
s = requests.Session(); UA = {"User-Agent": "SubPlayer (language-learning video player)"}
def get(u, **k):
    r = s.get(u, headers=UA, timeout=30, **k); return r

print("== VOA Learning English RSS list")
try:
    r = get("https://learningenglish.voanews.com/rssfeeds")
    print(r.status_code, len(r.text))
    feeds = re.findall(r'href="(/api/[^"]+)"[^>]*>([^<]*)<', r.text)
    for u, t in feeds[:80]:
        print("  ", u, "|", t.strip())
except Exception: traceback.print_exc()

print("\n== VOA: a video feed's items")
try:
    for u, t in feeds:
        if any(k in t.lower() for k in ("video", "let's learn", "english in a minute", "grammar", "news words", "movies")):
            x = get("https://learningenglish.voanews.com" + u).text
            items = re.findall(r"<item>(.*?)</item>", x, re.S)
            print("FEED", t.strip(), u, len(items))
            for it in items[:2]:
                ti = re.search(r"<title>(.*?)</title>", it, re.S); en = re.findall(r'<enclosure[^>]+>', it); li = re.search(r"<link>(.*?)</link>", it)
                print("    ", (ti.group(1) if ti else "")[:70], "|", li.group(1) if li else "", "|", en[:2])
except Exception: traceback.print_exc()

print("\n== VOA: one video page")
try:
    x = get("https://learningenglish.voanews.com/z/3613").text   # Let's Learn English (zone)
    links = re.findall(r'href="(/a/[^"]+\.html)"', x)[:3]
    print("zone links", links)
    for l in links[:2]:
        pg = get("https://learningenglish.voanews.com" + l).text
        mp4 = sorted(set(re.findall(r'https?://[^"\'\s]+\.mp4[^"\'\s]*', pg)))[:6]
        vtt = sorted(set(re.findall(r'https?://[^"\'\s]+\.(?:vtt|srt)[^"\'\s]*', pg)))[:4]
        print(" page", l, "mp4:", mp4, "captions:", vtt)
except Exception: traceback.print_exc()

print("\n== NASA images API")
try:
    j = get("https://images-api.nasa.gov/search", params={"q": "Mars rover", "media_type": "video", "page_size": 5}).json()
    items = j["collection"]["items"]
    print("hits", j["collection"]["metadata"].get("total_hits"))
    for it in items[:3]:
        d = it["data"][0]
        print("  ", d.get("nasa_id"), "|", d.get("title")[:60], "|", d.get("date_created"), "| keys", list(d)[:12])
        files = get(it["href"]).json()
        print("     files:", [f.rsplit("/", 1)[-1] for f in files][:12])
except Exception: traceback.print_exc()

print("\n== Internet Archive")
try:
    q = 'mediatype:movies AND (licenseurl:*publicdomain* OR licenseurl:*creativecommons.org/licenses/by/*) AND language:(English OR eng) AND format:"MPEG4"'
    j = get("https://archive.org/advancedsearch.php", params={"q": q, "fl[]": ["identifier", "title", "licenseurl", "runtime", "downloads"],
             "rows": 5, "sort[]": "downloads desc", "output": "json"}).json()
    print("found", j["response"]["numFound"])
    for d in j["response"]["docs"][:3]:
        print("  ", d.get("identifier"), "|", str(d.get("title"))[:50], "|", d.get("licenseurl"), "|", d.get("runtime"))
        m = get(f"https://archive.org/metadata/{d['identifier']}").json()
        fs = [(f["name"], f.get("format"), f.get("size")) for f in m.get("files", []) if f["name"].lower().endswith((".mp4", ".srt", ".vtt"))]
        print("     ", fs[:6])
except Exception: traceback.print_exc()
print("DONE")
