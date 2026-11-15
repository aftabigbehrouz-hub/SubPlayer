"""
Search the German public broadcasters' media libraries (ARD, ZDF, 3sat, Arte, DW, KiKA, phoenix, BR, SWR, WDR, NDR…)
through the public MediathekViewWeb catalogue — the same open film list the MediathekView program uses. Every entry is a
programme the broadcaster itself offers as a plain MP4 file, often with the broadcaster's own subtitles.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

API = "https://mediathekviewweb.de/api/query"
UA = "SubPlayer (language-learning video player; Windows)"

# what the user sees -> the catalogue's channel name
CHANNELS = {"ARD": "ARD", "ZDF": "ZDF", "3sat": "3Sat", "Arte": "ARTE.DE", "DW": "DW", "KiKA": "KiKA", "phoenix": "PHOENIX",
            "BR": "BR", "SWR": "SWR", "WDR": "WDR", "NDR": "NDR", "MDR": "MDR", "HR": "HR", "RBB": "RBB", "ORF": "ORF", "SRF": "SRF"}

LENGTHS = {"Any length": (0, 0), "Short · under 15 min": (0, 15 * 60), "Medium · 15–45 min": (15 * 60, 45 * 60),
           "Long · over 45 min": (45 * 60, 0)}


@dataclass
class Film:
    channel: str
    topic: str
    title: str
    description: str
    timestamp: int            # seconds since 1970 (broadcast / publication)
    duration: int             # seconds
    size: int                 # bytes of the normal-quality file (0 if unknown)
    url_website: str
    url_subtitle: str
    url_video: str
    url_video_low: str = ""
    url_video_hd: str = ""
    id: str = ""

    @property
    def has_subtitles(self) -> bool:
        return bool(self.url_subtitle)

    def video(self, quality: str = "normal") -> str:
        if quality == "hd" and self.url_video_hd:
            return self.url_video_hd
        if quality == "low" and self.url_video_low:
            return self.url_video_low
        return self.url_video or self.url_video_hd or self.url_video_low

    @property
    def length(self) -> str:
        m = self.duration // 60
        return f"{m // 60} h {m % 60:02d} min" if m >= 60 else (f"{m} min" if m else f"{self.duration} s")

    @property
    def date(self) -> str:
        return time.strftime("%d.%m.%Y", time.localtime(self.timestamp)) if self.timestamp else ""

    @property
    def label(self) -> str:
        """Short name for the channel badge."""
        rev = {v.lower(): k for k, v in CHANNELS.items()}
        return rev.get(self.channel.lower(), self.channel)


def _full(base: str, v) -> str:
    """The film list shortens HD/low links as "<n>|<suffix>" = first n characters of the normal link + suffix."""
    v = (v or "").strip()
    m = re.match(r"^(\d+)\|(.*)$", v)
    if m and base:
        return base[: int(m.group(1))] + m.group(2)
    return v


def _https(u: str) -> str:
    return "https://" + u[7:] if u.startswith("http://") else u


def film_from(d: dict) -> Film:
    base = (d.get("url_video") or "").strip()
    return Film(channel=d.get("channel") or "", topic=(d.get("topic") or "").strip(), title=(d.get("title") or "").strip(),
                description=(d.get("description") or "").strip(), timestamp=int(d.get("timestamp") or 0),
                duration=int(d.get("duration") or 0), size=int(d.get("size") or 0),
                url_website=(d.get("url_website") or "").strip(), url_subtitle=_https((d.get("url_subtitle") or "").strip()),
                url_video=_https(base), url_video_low=_https(_full(base, d.get("url_video_low"))),
                url_video_hd=_https(_full(base, d.get("url_video_hd"))), id=str(d.get("id") or ""))


def build_query(text: str = "", channels: list[str] | None = None, topic: str = "", title: str = "",
                length: tuple[int, int] = (0, 0), offset: int = 0, size: int = 30, sort: str = "timestamp") -> dict:
    queries = []
    if text.strip():
        queries.append({"fields": ["title", "topic"], "query": text.strip()})
    if topic.strip():
        queries.append({"fields": ["topic"], "query": topic.strip()})
    if title.strip():
        queries.append({"fields": ["title"], "query": title.strip()})
    for c in channels or []:
        queries.append({"fields": ["channel"], "query": CHANNELS.get(c, c).lower()})
    q = {"queries": queries, "sortBy": sort, "sortOrder": "desc", "future": False, "offset": offset, "size": size}
    lo, hi = length
    if lo:
        q["duration_min"] = lo
    if hi:
        q["duration_max"] = hi
    return q


def parse_response(payload) -> tuple[list[Film], int]:
    data = payload if isinstance(payload, dict) else json.loads(payload)
    if data.get("err"):
        raise IOError(f"Catalogue error: {data['err']}")
    res = data.get("result") or {}
    films = [film_from(d) for d in res.get("results") or [] if d.get("url_video") or d.get("url_video_hd")]
    total = int((res.get("queryInfo") or {}).get("totalResults") or len(films))
    return films, total


def search(text: str = "", channels: list[str] | None = None, topic: str = "", title: str = "", length=(0, 0),
           offset: int = 0, size: int = 30, subtitles_only: bool = False, session=None) -> tuple[list[Film], int]:
    import requests
    s = session or requests
    q = build_query(text, channels, topic, title, length, offset, size * (3 if subtitles_only else 1))
    r = s.post(API, data=json.dumps(q), headers={"Content-Type": "text/plain", "User-Agent": UA}, timeout=(8, 25))
    r.raise_for_status()
    films, total = parse_response(r.json())
    films = [f for f in films if f.url_video.startswith("https://") or f.url_video.startswith("http")]
    if subtitles_only:
        films = [f for f in films if f.has_subtitles][:size]
    return dedupe(films), total


def dedupe(films: list[Film]) -> list[Film]:
    """The same programme is often listed by several channels (e.g. ARD and the regional station) — keep one."""
    seen, out = set(), []
    for f in films:
        k = (re.sub(r"\W+", "", f.title.lower()), f.duration // 30)
        if k in seen:
            continue
        seen.add(k)
        out.append(f)
    return out


# ------------------------------------------------------------------ suggestions (always the newest episodes)
@dataclass
class Shelf:
    title: str
    level: str
    why: str
    text: str = ""
    topic: str = ""
    title_q: str = ""
    channels: list[str] = field(default_factory=list)
    length: tuple[int, int] = (60, 0)


SHELVES = [
    Shelf("logo! — news for kids", "A2–B1", "Today's news in short, simple sentences", topic="logo!", channels=["ZDF"], length=(120, 20 * 60)),
    Shelf("Die Sendung mit der Maus", "A2–B1", "How things work, explained slowly and clearly", topic="Die Sendung mit der Maus"),
    Shelf("Kinder & Wissen", "A2–B1", "Clear explanations for young viewers: Checker, pur+, Wissen macht Ah!",
          text="Checker", channels=["KiKA"], length=(5 * 60, 0)),
    Shelf("tagesschau — the news", "B1", "Short news programmes, several times a day", topic="tagesschau", channels=["ARD"],
          length=(60, 20 * 60)),
    Shelf("Terra X", "B1–B2", "History, nature and science with a narrator", topic="Terra X", channels=["ZDF"]),
    Shelf("Quarks", "B2", "Science questions of everyday life", topic="Quarks", channels=["WDR"]),
    Shelf("WISO — money & consumers", "B2–C1", "Prices, contracts, taxes and jobs — everyday economic German", topic="WISO",
          channels=["ZDF"]),
    Shelf("3sat Wissenschaft", "B2–C1", "Science documentaries — real, natural German", topic="Wissenschaftsdoku", channels=["3sat"],
          length=(15 * 60, 0)),
    Shelf("ARTE auf Deutsch", "B2–C1", "Culture, society and history from ARTE", channels=["Arte"], length=(10 * 60, 0)),
]

# candidates checked live by tools/ci/probe_media.py (kept here so the probe can compare)
SHELF_TRIALS = [("topic", "Wissen macht Ah!", []), ("topic", "pur+", ["ZDF"]), ("text", "Checker", ["KiKA"]), ("topic", "neuneinhalb", []),
                ("topic", "WISO", ["ZDF"]), ("topic", "plusminus", ["ARD"]), ("topic", "Wissenschaftsdoku", ["3sat"]),
                ("topic", "nano", ["3sat"]), ("topic", "tagesschau", ["ARD"]), ("topic", "Nicos Weg", []), ("text", "Deutsch lernen", ["DW"])]


def shelf_films(sh: Shelf, size: int = 8, session=None) -> list[Film]:
    films, _ = search(sh.text, sh.channels, sh.topic, sh.title_q, sh.length, 0, size, session=session)
    return films


# ------------------------------------------------------------------ find a page's film in the catalogue
def _norm_url(u: str) -> str:
    u = re.sub(r"^https?://(www\.)?", "", (u or "").strip().lower())
    return u.split("?")[0].split("#")[0].rstrip("/")


def _title_queries(page_title: str) -> list[str]:
    """Search phrases from a page title: the whole title cleaned, then its parts (titles are often "Show – Episode | ZDF")."""
    t = re.sub(r"\s*\|\s*[^|]*$", "", page_title or "") if "|" in (page_title or "") else (page_title or "")
    t = re.sub(r"\b(ZDFmediathek|ARD Mediathek|Mediathek|ZDFheute|ARTE|3sat|KiKA|phoenix|DW)\b\s*$", "", t, flags=re.I).strip(" -–|:")
    parts = [p.strip() for p in re.split(r"\s+[|–-]\s+|:\s+", t) if len(p.strip()) >= 4]
    out = []

    def add(x):
        x = " ".join(re.sub(r"[^\w\s]", " ", x).split()[:7])
        if len(x) >= 4 and x.lower() not in [o.lower() for o in out]:
            out.append(x)
    add(t)
    for p in sorted(parts, key=len, reverse=True):
        add(p)
    return out[:4]


GENERIC_SEG = {"video", "videos", "sendungen", "sendung", "dokus", "doku", "dokumentation", "reportagen", "magazine", "filme",
               "serien", "nachrichten", "wissen", "kultur", "gesellschaft", "politik", "panorama", "multimedia", "de", "mediathek",
               "gespraeche", "comedy", "show", "kinder", "page", "p", "programm", "unterhaltung", "verbraucher"}


def _variants(t: str) -> list[str]:
    """'phoenix persoenlich' -> also 'phoenix persönlich' etc. (addresses write ö as oe; each word tried both ways)."""
    import itertools
    opts = []
    for w in t.split():
        alt = re.sub(r"ae", "ä", re.sub(r"oe", "ö", re.sub(r"ue", "ü", w)))
        opts.append([w] if alt == w else [w, alt])
    out = [" ".join(c) for c in itertools.product(*opts)]
    return out[:4]


def _url_topics(page_url: str) -> list[str]:
    """Programme names hidden in the address, e.g. zdf.de/video/reportagen/backstage-154/… -> 'backstage'."""
    from urllib.parse import urlparse
    segs = [x for x in urlparse(page_url).path.split("/") if x][:-1]
    out = []
    for seg in segs:
        t = re.sub(r"-\d+$", "", seg.lower()).replace("-", " ").strip()
        if len(t) < 3 or t in GENERIC_SEG or t.isdigit():
            continue
        for v in _variants(t):
            if v not in out:
                out.append(v)
    return out[:6]


def _exact(films: list[Film], want: str, tail: str) -> Film | None:
    for f in films:
        u = _norm_url(f.url_website)
        if u == want or (len(tail) >= 6 and u.rsplit("/", 1)[-1] == tail):
            return f
    return None


def lookup(page_url: str, page_title: str, session=None, similar: bool = True) -> Film | None:
    """The catalogue entry for a broadcaster page: same web address (found through the programme name in the address or the
    page title); if `similar`, else the closest title."""
    import html as _html
    page_title = _html.unescape(page_title or "")
    want = _norm_url(page_url)
    tail = want.rsplit("/", 1)[-1]
    pool: list[Film] = []
    for topic in _url_topics(page_url):
        try:
            films, _ = search(topic=topic, size=50, session=session)
        except Exception:
            continue
        hit = _exact(films, want, tail)
        if hit:
            return hit
        pool += films
    for q in _title_queries(page_title):
        for fields in ("title", "both"):
            try:
                films, _ = search(text=q if fields == "both" else "", title=q if fields == "title" else "", size=50, session=session)
            except Exception:
                continue
            hit = _exact(films, want, tail)
            if hit:
                return hit
            pool += films
            if films:
                break
    if not pool or not similar or not page_title.strip():
        return None

    def sim(a: str, b: str) -> float:
        A, B = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
        return len(A & B) / max(1, len(A | B))
    host = want.split("/", 1)[0]
    same_site = [f for f in pool if _norm_url(f.url_website).split("/", 1)[0] == host] or pool
    best = max(same_site, key=lambda f: max(sim(f.title, page_title), sim(f"{f.topic} {f.title}", page_title)))
    score = max(sim(best.title, page_title), sim(f"{best.topic} {best.title}", page_title))
    return best if score >= 0.55 else None
