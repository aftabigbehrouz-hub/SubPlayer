"""
English programmes for Discover — free to download:
  VOA Learning English (Voice of America — US government work, public domain; lessons made for learners, A2–B2;
  "Let's Learn English with Anna" is only on YouTube, so it is not offered)
  NASA video library (images.nasa.gov — public domain; most videos come with English .srt subtitles)
  Podcasts (audio) the broadcasters publish for download: BBC Learning English (6 Minute English / Grammar / Vocabulary),
  BBC World Service, PBS NewsHour, TED Talks Daily, NPR — for personal listening, as in any podcast app
Both are listed with the same Film type as the German catalogue; the video file is found when you download.
"""
from __future__ import annotations

import html
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime

from .mediathek import Film

UA = "SubPlayer (language-learning video player)"
VOA = "https://learningenglish.voanews.com"
NASA = "https://images-api.nasa.gov"


@dataclass
class EnShelf:
    title: str
    level: str
    why: str
    feed: str = ""            # VOA RSS path
    podcast: str = ""         # podcast RSS address
    nasa: str = ""            # NASA search words
    channels: list = field(default_factory=list)


PODCASTS = [
    EnShelf("BBC 6 Minute English", "B1–B2", "Two presenters, one topic, useful words — BBC Learning English (audio)",
            podcast="https://podcasts.files.bbci.co.uk/p02pc9tn.rss", channels=["BBC"]),
    EnShelf("BBC 6 Minute Grammar", "B1", "One grammar point in six minutes (audio)", podcast="https://podcasts.files.bbci.co.uk/p02pc9wq.rss",
            channels=["BBC"]),
    EnShelf("BBC 6 Minute Vocabulary", "B1–B2", "Words and phrases explained (audio)", podcast="https://podcasts.files.bbci.co.uk/p02pc9xz.rss",
            channels=["BBC"]),
    EnShelf("BBC Global News Podcast", "C1", "The world's news from the BBC World Service, twice a day (audio)",
            podcast="https://podcasts.files.bbci.co.uk/p02nq0gn.rss", channels=["BBC"]),
    EnShelf("BBC Witness History", "B2–C1", "History told by the people who were there (audio)",
            podcast="https://podcasts.files.bbci.co.uk/p004t1hd.rss", channels=["BBC"]),
    EnShelf("BBC The Documentary", "C1", "Award-winning documentaries from the World Service (audio)",
            podcast="https://podcasts.files.bbci.co.uk/p02nq0lx.rss", channels=["BBC"]),
    EnShelf("BBC Business Daily", "C1", "Money, work and the economy (audio)", podcast="https://podcasts.files.bbci.co.uk/p002vsxs.rss",
            channels=["BBC"]),
    EnShelf("PBS NewsHour", "C1", "The full US evening news programme (audio)", podcast="https://www.pbs.org/newshour/feeds/rss/podcasts/show",
            channels=["PBS"]),
    EnShelf("TED Talks Daily", "B2–C1", "Ideas worth spreading, one talk a day (audio)", podcast="https://feeds.feedburner.com/TEDTalks_audio",
            channels=["TED"]),
    EnShelf("NPR News Now", "B2–C1", "Five-minute news summary, every hour (audio)", podcast="https://feeds.npr.org/500005/podcast.xml",
            channels=["NPR"]),
]

SHELVES = [
    EnShelf("English in a Minute", "A2–B1", "One expression explained in a minute", feed="/api/zjk-rl-vomx-tpebpqqo"),
    EnShelf("How to Pronounce", "A2–B1", "Sounds of American English, step by step", feed="/api/zpivqol-vomx-tpe_guqi"),
    EnShelf("Everyday Grammar Video", "B1", "Grammar in short, real situations", feed="/api/z_riqtl-vomx-tpevtmqr"),
    EnShelf("News Words", "B1", "Words from the news, in context", feed="/api/z-k-ql-vomx-tpermqqi"),
    EnShelf("VOA60: Watch & Learn", "B1", "Short reports with simple narration", feed="/api/zyk-il-vomx-tpetpqqm"),
    EnShelf("NASA — space & science", "B2–C1", "Real English from scientists and engineers, with subtitles", nasa="Artemis Moon"),
    EnShelf("NASA — Earth & climate", "B2–C1", "How our planet works, explained by NASA", nasa="Earth climate"),
] + PODCASTS[:4] + PODCASTS[7:9]


def _session(session):
    import requests
    return session or requests


def _clean(t: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", t or "")).split())


def voa_feed(path: str, size: int = 12, session=None) -> list[Film]:
    r = _session(session).get(VOA + path, headers={"User-Agent": UA}, timeout=(8, 25))
    r.raise_for_status()
    out = []
    for it in re.findall(r"<item>(.*?)</item>", r.text, re.S)[:size]:
        def tag(n):
            m = re.search(rf"<{n}>(.*?)</{n}>", it, re.S)
            return _clean(m.group(1).replace("<![CDATA[", "").replace("]]>", "")) if m else ""
        link = tag("link")
        if not link:
            continue
        ts = 0
        try:
            ts = int(parsedate_to_datetime(tag("pubDate")).timestamp())
        except Exception:
            pass
        title = tag("title")
        topic = re.match(r"^(.*?):", title)
        out.append(Film(channel="VOA", topic=topic.group(1) if topic else "VOA Learning English", title=title,
                        description=tag("description")[:600], timestamp=ts, duration=0, size=0, url_website=link,
                        url_subtitle="", url_video=""))
    return out


def voa_search(text: str, size: int = 20, session=None) -> list[Film]:
    r = _session(session).get(f"{VOA}/s", params={"k": text, "tab": "video"}, headers={"User-Agent": UA}, timeout=(8, 25))
    r.raise_for_status()
    seen, out = set(), []
    for link, inner in re.findall(r'<a[^>]+href="(/a/[^"]+\.html)"[^>]*>(.*?)</a>', r.text, re.S):
        title = _clean(inner)
        if not title or link in seen:
            continue
        seen.add(link)
        topic = re.match(r"^(.*?):", title)
        out.append(Film(channel="VOA", topic=topic.group(1) if topic else "VOA Learning English", title=title, description="",
                        timestamp=0, duration=0, size=0, url_website=VOA + link, url_subtitle="", url_video=""))
        if len(out) >= size:
            break
    return out


def nasa_search(text: str, size: int = 20, page: int = 1, session=None) -> tuple[list[Film], int]:
    r = _session(session).get(f"{NASA}/search", params={"q": text, "media_type": "video", "page_size": size, "page": page},
                              headers={"User-Agent": UA}, timeout=(8, 25))
    r.raise_for_status()
    col = r.json().get("collection") or {}
    out = []
    for it in col.get("items") or []:
        d = (it.get("data") or [{}])[0]
        nid = d.get("nasa_id") or ""
        if not nid:
            continue
        ts = 0
        try:
            ts = int(time.mktime(time.strptime((d.get("date_created") or "")[:10], "%Y-%m-%d")))
        except Exception:
            pass
        out.append(Film(channel="NASA", topic=d.get("center") or "NASA", title=d.get("title") or nid,
                        description=_clean(d.get("description") or "")[:900], timestamp=ts, duration=0, size=0,
                        url_website=f"https://images.nasa.gov/details/{urllib.parse.quote(nid)}", url_subtitle="", url_video=""))
    total = int((col.get("metadata") or {}).get("total_hits") or len(out))
    return out, total


def _secs(t: str) -> int:
    t = (t or "").strip()
    if t.isdigit():
        return int(t)
    parts = [int(x) for x in t.split(":") if x.isdigit()]
    n = 0
    for p_ in parts:
        n = n * 60 + p_
    return n


def podcast_feed(url: str, size: int = 15, session=None, channel: str = "") -> list[Film]:
    """A podcast's newest episodes (the audio file is the episode's own download)."""
    r = _session(session).get(url, headers={"User-Agent": UA}, timeout=(8, 25))
    r.raise_for_status()
    show = re.search(r"<channel>.*?<title>(.*?)</title>", r.text, re.S)
    show_t = _clean((show.group(1) if show else "").replace("<![CDATA[", "").replace("]]>", ""))
    ch = channel or ("BBC" if "bbc" in url else "PBS" if "pbs.org" in url else "TED" if "TED" in url else "NPR" if "npr" in url
                     else "Podcast")
    out = []
    for it in re.findall(r"<item>(.*?)</item>", r.text, re.S)[:size]:
        def tag(n):
            m = re.search(rf"<{n}[^>]*>(.*?)</{n}>", it, re.S)
            return _clean(m.group(1).replace("<![CDATA[", "").replace("]]>", "")) if m else ""
        enc = re.search(r'<enclosure[^>]*\burl="([^"]+)"', it)
        if not enc:
            continue
        audio = html.unescape(enc.group(1))
        ts = 0
        try:
            ts = int(parsedate_to_datetime(tag("pubDate")).timestamp())
        except Exception:
            pass
        link = tag("link") or url
        out.append(Film(channel=ch, topic=show_t or ch, title=tag("title"), description=tag("description")[:900], timestamp=ts,
                        duration=_secs(tag("itunes:duration")), size=0, url_website=link, url_subtitle="", url_video=audio))
    return out


def shelf_films(sh: EnShelf, size: int = 10, session=None) -> list[Film]:
    if sh.podcast:
        return podcast_feed(sh.podcast, size, session, sh.channels[0] if sh.channels else "")
    if sh.feed:
        return voa_feed(sh.feed, size, session)
    films, _ = nasa_search(sh.nasa, size, session=session)
    return films


_PODCAST_CACHE: dict = {}


def podcast_search(text: str, size: int = 40, session=None) -> list[Film]:
    """Episodes of all the podcasts whose title or description contain the words (feeds kept for 15 minutes)."""
    from concurrent.futures import ThreadPoolExecutor
    now = time.time()

    def one(sh):
        hit = _PODCAST_CACHE.get(sh.podcast)
        if hit and now - hit[0] < 900:
            return hit[1]
        try:
            fs = podcast_feed(sh.podcast, 60, session, sh.channels[0] if sh.channels else "")
        except Exception:
            fs = []
        _PODCAST_CACHE[sh.podcast] = (now, fs)
        return fs
    with ThreadPoolExecutor(max_workers=5) as ex:
        allf = [f for fs in ex.map(one, PODCASTS) for f in fs]
    words = [w for w in text.lower().split() if w]
    hits = [f for f in allf if all(w in (f.title + " " + f.description + " " + f.topic).lower() for w in words)]
    return sorted(hits, key=lambda f: -f.timestamp)[:size]


def search(text: str, channels: list[str] | None = None, size: int = 30, offset: int = 0, session=None) -> tuple[list[Film], int]:
    chans = channels or ["VOA", "NASA", "Podcasts"]
    films, total = [], 0
    if "Podcasts" in chans and offset == 0:
        f = podcast_search(text, size, session)
        films += f
        total += len(f)
    if "NASA" in chans:
        f, t = nasa_search(text, size, page=offset // size + 1, session=session)
        films += f
        total += t
    if "VOA" in chans and offset == 0:
        try:
            f = voa_search(text, size, session)
        except Exception:
            f = []
        films = f + films
        total += len(f)
    return films, total


# ------------------------------------------------------------------ resolving a page to its video
def nasa_asset(nasa_id: str, session=None) -> tuple[str, str]:
    """(mp4 of medium size, .srt or .vtt) for a NASA video."""
    r = _session(session).get(f"{NASA}/asset/{urllib.parse.quote(nasa_id)}", headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    hrefs = [i["href"].replace("http://", "https://") for i in (r.json().get("collection") or {}).get("items") or []]
    mp4 = next((h for pref in ("~medium.mp4", "~large.mp4", "~mobile.mp4", "~small.mp4", "~orig.mp4")
                for h in hrefs if h.endswith(pref)), "")
    sub = next((h for h in hrefs if h.lower().endswith(".srt")), "") or next((h for h in hrefs if h.lower().endswith(".vtt")), "")
    return (urllib.parse.quote(mp4, safe=":/~%") if mp4 else ""), (urllib.parse.quote(sub, safe=":/~%") if sub else "")
