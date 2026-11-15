"""Candidate English podcast / video feeds (official downloads)."""
import re, requests
s = requests.Session(); UA = {"User-Agent": "SubPlayer (podcast client)"}
FEEDS = {
 "BBC 6 Minute English": "https://podcasts.files.bbci.co.uk/p02pc9tn.rss",
 "BBC 6 Minute Grammar": "https://podcasts.files.bbci.co.uk/p02pc9wq.rss",
 "BBC 6 Minute Vocabulary": "https://podcasts.files.bbci.co.uk/p02pc9xz.rss",
 "BBC Learning English Stories": "https://podcasts.files.bbci.co.uk/p02pc9vv.rss",
 "BBC Global News Podcast": "https://podcasts.files.bbci.co.uk/p02nq0gn.rss",
 "BBC The Documentary": "https://podcasts.files.bbci.co.uk/p02nq0lx.rss",
 "BBC Science in Action": "https://podcasts.files.bbci.co.uk/p002vsnb.rss",
 "BBC Witness History": "https://podcasts.files.bbci.co.uk/p004t1hd.rss",
 "BBC Business Daily": "https://podcasts.files.bbci.co.uk/p002vsxs.rss",
 "PBS NewsHour full show (video?)": "https://www.pbs.org/newshour/feeds/rss/podcasts/show",
 "PBS NewsHour video": "https://www.pbs.org/newshour/feeds/rss/podcasts/video",
 "TED Talks Daily": "https://feeds.feedburner.com/TEDTalks_audio",
 "TED Talks video": "https://feeds.feedburner.com/TedtalksHD",
 "NPR News Now": "https://feeds.npr.org/500005/podcast.xml",
 "CBS Evening News (video?)": "https://feeds.simplecast.com/cbsnewsevening",
 "DW Learn German? (DW English news)": "https://rss.dw.com/xml/podcast_dw-news",
 "Scientific American 60s": "https://www.scientificamerican.com/podcast/podcast.xml",
 "Al Jazeera The Take": "https://feeds.megaphone.fm/AJE2563580829",
}
for name, url in FEEDS.items():
    try:
        r = s.get(url, headers=UA, timeout=25, allow_redirects=True)
        items = re.findall(r"<item>(.*?)</item>", r.text, re.S)
        first = items[0] if items else ""
        enc = re.search(r'<enclosure[^>]*url="([^"]+)"[^>]*type="([^"]+)"', first) or re.search(r'<enclosure[^>]*type="([^"]+)"[^>]*url="([^"]+)"', first)
        ti = re.search(r"<title>(.*?)</title>", first, re.S); pd = re.search(r"<pubDate>(.*?)</pubDate>", first)
        dur = re.search(r"<itunes:duration>(.*?)</itunes:duration>", first)
        lic = re.search(r"<copyright>(.*?)</copyright>", r.text)
        print(f"{name:34} {r.status_code} items={len(items):3} | {(ti.group(1) if ti else '')[:44]!r} | {pd.group(1)[:16] if pd else ''} | {dur.group(1) if dur else ''} | {(enc.groups() if enc else '')} | ©{(lic.group(1)[:50] if lic else '')}")
    except Exception as e:
        print(f"{name:34} ERR {type(e).__name__}: {str(e)[:80]}")
# BBC Learning English page with transcript?
try:
    x = s.get("https://www.bbc.co.uk/learningenglish/english/features/6-minute-english", headers=UA, timeout=25)
    links = re.findall(r'href="(/learningenglish/english/features/6-minute-english_20\d+/ep-\d+)"', x.text)[:2]
    print("6ME page", x.status_code, links)
    if links:
        p = s.get("https://www.bbc.co.uk" + links[0], headers=UA, timeout=25).text
        print("  mp3:", re.findall(r'https?://[^"\']+\.mp3', p)[:2], "pdf:", re.findall(r'https?://[^"\']+\.pdf', p)[:2])
except Exception as e:
    print("6ME page ERR", e)
print("DONE")
