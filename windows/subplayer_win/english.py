"""
English programmes for Discover — free to download:
  VOA Learning English (Voice of America — US government work, public domain; lessons made for learners, A1–B2)
  NASA video library (images.nasa.gov — public domain; most videos come with English .srt subtitles)
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
    nasa: str = ""            # NASA search words
    channels: list = field(default_factory=list)


SHELVES = [
    EnShelf("Let's Learn English with Anna", "A1–A2", "VOA's video course: everyday English, slow and clear", feed="/api/zyygqpl-vomx-tpetrbqm"),
    EnShelf("English in a Minute", "A2–B1", "One expression explained in a minute", feed="/api/zjk-rl-vomx-tpebpqqo"),
    EnShelf("How to Pronounce", "A2–B1", "Sounds of American English, step by step", feed="/api/zpivqol-vomx-tpe_guqi"),
    EnShelf("Everyday Grammar Video", "B1", "Grammar in short, real situations", feed="/api/z_riqtl-vomx-tpevtmqr"),
    EnShelf("News Words", "B1", "Words from the news, in context", feed="/api/z-k-ql-vomx-tpermqqi"),
    EnShelf("VOA60: Watch & Learn", "B1", "Short reports with simple narration", feed="/api/zyk-il-vomx-tpetpqqm"),
    EnShelf("NASA — space & science", "B2–C1", "Real English from scientists and engineers, with subtitles", nasa="Artemis Moon"),
    EnShelf("NASA — Earth & climate", "B2–C1", "How our planet works, explained by NASA", nasa="Earth climate"),
]


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


def shelf_films(sh: EnShelf, size: int = 10, session=None) -> list[Film]:
    if sh.feed:
        return voa_feed(sh.feed, size, session)
    films, _ = nasa_search(sh.nasa, size, session=session)
    return films


def search(text: str, channels: list[str] | None = None, size: int = 30, offset: int = 0, session=None) -> tuple[list[Film], int]:
    chans = channels or ["VOA", "NASA"]
    films, total = [], 0
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
