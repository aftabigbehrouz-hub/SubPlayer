"""
My sources: websites, RSS / podcast feeds and public Telegram channels the user adds in Discover. Their videos are listed
like the broadcasters' programmes and found by Search.

- Telegram: the public web view of a channel (t.me/s/<channel>) — the posts with their videos, no login. Telegram only
  puts small and medium videos there; bigger ones ("Media is too big") are listed with a link to open in Telegram.
- Feeds (RSS / Atom / podcasts): every item with a video or audio file.
- Web pages: the video files on the page — and, when the page names its RSS feed, that feed.
Sites whose terms forbid downloading (YouTube, Instagram, TikTok, streaming services) are refused, as for links.
"""
from __future__ import annotations

import html
import re
import time
import urllib.parse
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime

from . import linkimport
from .mediathek import Film

UA = linkimport.UA
TG_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")


@dataclass
class Source:
    url: str                 # t.me/s/<channel>, the feed address or the page
    name: str
    kind: str                # telegram · feed · page
    lang: str = "de"

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Source":
        return Source(d.get("url", ""), d.get("name", ""), d.get("kind", "page"), d.get("lang", "de"))


def _session(session=None):
    import requests
    return session or requests.Session()


def _get(url: str, session=None, timeout=(8, 25)):
    r = _session(session).get(url, headers={"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"}, timeout=timeout)
    r.raise_for_status()
    return r


def _text(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"[ \t]+", " ", html.unescape(s)).strip()


def telegram_name(text: str) -> str | None:
    """'t.me/tagesschau', 'https://t.me/s/tagesschau/123', '@tagesschau' → 'tagesschau' (public channels only)."""
    t = (text or "").strip()
    if t.startswith("@") and TG_NAME.match(t[1:]):
        return t[1:]
    m = re.match(r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/(?:s/)?([A-Za-z][A-Za-z0-9_]{3,31})(?:[/?#].*)?$", t)
    if m and m.group(1).lower() not in ("joinchat", "addstickers", "share", "proxy", "iv"):
        return m.group(1)
    return None


def detect(text: str, lang: str = "de", session=None) -> Source:
    """What the user typed or pasted, as a source: a Telegram channel, a feed or a page (raises with a clear reason)."""
    t = (text or "").strip()
    if not t:
        raise ValueError("Paste a web address, an RSS feed or a Telegram channel (t.me/…)")
    if re.match(r"^(?:https?://)?(?:t\.me|telegram\.me)/(?:\+|joinchat/)", t):
        raise ValueError("That is a private Telegram invite link. Only public channels can be read without logging in.")
    tg = telegram_name(t)
    if tg:
        s = Source(f"https://t.me/s/{tg}", tg, "telegram", lang)
        page = _get(s.url, session).text
        if "tgme_widget_message" not in page and "tgme_channel_info" not in page:
            raise ValueError(f"„{tg}“ is not a public Telegram channel (or Telegram can't be reached — turn on your VPN).")
        s.name = _tg_title(page) or tg
        return s
    if not re.match(r"^https?://", t):
        t = "https://" + t
    why = linkimport.refused_reason(t)
    if why:
        raise ValueError(why)
    r = _get(t, session)
    body = r.text[:3_000_000]
    ctype = r.headers.get("Content-Type", "").lower()
    if "xml" in ctype or re.match(r"^\s*(<\?xml[^>]*>\s*)?<(rss|feed|rdf:RDF)\b", body[:2000]):
        return Source(r.url, _feed_title(body) or urllib.parse.urlparse(r.url).hostname or t, "feed", lang)
    feed = _feed_link(body, r.url)
    title = _page_title(body) or (urllib.parse.urlparse(r.url).hostname or t)
    if feed:
        try:
            fr = _get(feed, session)
            if re.search(r"<(rss|feed|rdf:RDF)\b", fr.text[:3000]) and _feed_items(fr.text, Source(feed, title, "feed", lang), 50):
                return Source(feed, _feed_title(fr.text) or title, "feed", lang)
        except Exception:
            pass
    return Source(r.url, title, "page", lang)


# ------------------------------------------------------------------ Telegram
def _tg_title(page: str) -> str:
    m = re.search(r'tgme_channel_info_header_title[^>]*>\s*(?:<span[^>]*>)?(.*?)</', page, re.S) or \
        re.search(r'<meta property="og:title" content="([^"]*)"', page)
    return _text(m.group(1)) if m else ""


def _clock(t: str) -> int:
    n = 0
    for p in (t or "").strip().split(":"):
        if p.isdigit():
            n = n * 60 + int(p)
    return n


def telegram_posts(page: str, channel: str, channel_title: str = "") -> list[Film]:
    """The video posts of one page of t.me/s/<channel> (oldest first, as Telegram shows them)."""
    out = []
    parts = re.split(r'<div class="tgme_widget_message_wrap', page)[1:]
    for p in parts:
        post = re.search(r'data-post="([^"]+)"', p)
        if not post:
            continue
        has_video = "tgme_widget_message_video_player" in p or "<video" in p
        if not has_video:
            continue
        dur = re.search(r'message_video_duration[^>]*>([\d:]+)<', p)
        txt = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', p, re.S)
        text = _text(txt.group(1)) if txt else ""
        when = re.search(r'<time datetime="([^"]+)"', p)
        ts = 0
        if when:
            try:
                from datetime import datetime
                ts = int(datetime.fromisoformat(when.group(1)).timestamp())
            except Exception:
                ts = 0
        first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        title = first[:140] + ("…" if len(first) > 140 else "") if first else f"Video {post.group(1).split('/')[-1]}"
        # the video address is fetched when downloading (the addresses on the page expire, and "Media is too big" posts
        # still give their video when the post is opened on its own)
        out.append(Film(channel="Telegram", topic=channel_title or channel, title=title, description=text.strip()[:1500],
                        timestamp=ts, duration=_clock(dur.group(1)) if dur else 0, size=0,
                        url_website=f"https://t.me/{post.group(1)}", url_subtitle="",
                        url_video="", id="tg:" + post.group(1)))
    return out


def telegram_videos(src: Source, pages: int = 3, session=None) -> list[Film]:
    """The newest video posts of a public channel: a few pages back (each page is about 20 posts)."""
    name = telegram_name(src.url) or src.name
    s = _session(session)
    films, before = [], None
    for _ in range(max(1, pages)):
        url = f"https://t.me/s/{name}" + (f"?before={before}" if before else "")
        page = _get(url, s).text
        films += telegram_posts(page, name, src.name)
        ids = [int(x) for x in re.findall(r'data-post="[^"/]+/(\d+)"', page)]
        if not ids or (before and min(ids) >= before):
            break
        before = min(ids)
        if before <= 1:
            break
    seen, uniq = set(), []
    for f in films:
        if f.id not in seen:
            seen.add(f.id)
            uniq.append(f)
    return sorted(uniq, key=lambda f: -f.timestamp)


def fresh_video(post_url: str, session=None) -> str:
    """The current address of a Telegram post's video (the addresses in the web view expire after a while)."""
    m = re.search(r"t\.me/([A-Za-z0-9_]+)/(\d+)", post_url)
    if not m:
        return ""
    page = _get(f"https://t.me/{m.group(1)}/{m.group(2)}?embed=1&mode=tme", session).text
    v = re.search(r'<video[^>]+src="([^"]+)"', page)
    return html.unescape(v.group(1)) if v else ""


# ------------------------------------------------------------------ feeds
def _feed_title(xml: str) -> str:
    m = re.search(r"<channel[^>]*>.*?<title[^>]*>(.*?)</title>", xml, re.S) or re.search(r"<feed[^>]*>.*?<title[^>]*>(.*?)</title>", xml, re.S)
    return _text((m.group(1) if m else "").replace("<![CDATA[", "").replace("]]>", ""))


def _feed_link(page: str, base: str) -> str:
    for m in re.finditer(r"<link[^>]+>", page[:400_000], re.I):
        tag = m.group(0)
        if re.search(r'type=["\']application/(rss|atom)\+xml', tag, re.I):
            h = re.search(r'href=["\']([^"\']+)', tag)
            if h:
                return urllib.parse.urljoin(base, html.unescape(h.group(1)))
    return ""


def _page_title(page: str) -> str:
    m = linkimport.OG_TITLE.search(page) or linkimport.TITLE.search(page)
    return _text(m.group(1)) if m else ""


MEDIA = re.compile(r"\.(mp4|m4v|webm|mov|m3u8|mp3|m4a|aac|ogg|opus)(\?|$)", re.I)


def _feed_items(xml: str, src: Source, size: int = 60) -> list[Film]:
    out = []
    items = re.findall(r"<item\b.*?</item>", xml, re.S) or re.findall(r"<entry\b.*?</entry>", xml, re.S)
    for it in items[:size]:
        def tag(n):
            m = re.search(rf"<{n}\b[^>]*>(.*?)</{n}>", it, re.S)
            return _text(m.group(1).replace("<![CDATA[", "").replace("]]>", "")) if m else ""
        media = ""
        for pat in (r'<enclosure[^>]*\burl="([^"]+)"[^>]*>', r'<media:content[^>]*\burl="([^"]+)"[^>]*>',
                    r'<link[^>]*rel="enclosure"[^>]*href="([^"]+)"', r'<link[^>]*href="([^"]+)"[^>]*rel="enclosure"'):
            for m in re.finditer(pat, it):
                u = html.unescape(m.group(1))
                if MEDIA.search(urllib.parse.urlparse(u).path + "?") or re.search(r'type="(video|audio)/', m.group(0)):
                    media = u
                    break
            if media:
                break
        link = tag("link")
        if not link:
            lm = re.search(r'<link[^>]*href="([^"]+)"(?![^>]*enclosure)', it)
            link = html.unescape(lm.group(1)) if lm else ""
        if not media:
            continue
        if linkimport.refused_reason(media):
            continue
        ts = 0
        for k in ("pubDate", "published", "updated", "dc:date"):
            v = tag(k)
            if not v:
                continue
            try:
                ts = int(parsedate_to_datetime(v).timestamp())
            except Exception:
                try:
                    from datetime import datetime
                    ts = int(datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp())
                except Exception:
                    ts = 0
            if ts:
                break
        dur = tag("itunes:duration")
        out.append(Film(channel="Feed", topic=src.name, title=tag("title") or "Episode",
                        description=(tag("description") or tag("summary") or tag("itunes:summary") or tag("content"))[:1500],
                        timestamp=ts, duration=_clock(dur) if ":" in dur else (int(dur) if dur.isdigit() else 0), size=0,
                        url_website=link or src.url, url_subtitle="", url_video=media, id="feed:" + media))
    return out


def feed_videos(src: Source, session=None) -> list[Film]:
    return _feed_items(_get(src.url, session).text, src, 80)


# ------------------------------------------------------------------ pages
QUALITY = re.compile(r"\.(webs|webm|webl|webxl|webxxl)(?=\.)|[_-](\d{3,4}p|hq|lq|sd|hd|fullhd|low|high|mobile)(?=\.)|"
                     r"[_-]\d{3,4}x\d{3,4}(?=\.)")


def page_videos(src: Source, session=None) -> list[Film]:
    page = _get(src.url, session).text[:5_000_000]
    text = page.replace("\\/", "/").replace("\\u002F", "/").replace("&amp;", "&")
    urls = list(dict.fromkeys(m.group(0) for m in linkimport.VIDEO_URL.finditer(text)))
    groups: dict[str, list[str]] = {}
    for u in urls:                                   # the same video in several qualities: one entry, the best quality
        name = urllib.parse.unquote(u.split("?")[0].rsplit("/", 1)[-1])
        key = QUALITY.sub("", name.lower())
        groups.setdefault(key, []).append(u)
    urls = [max(g, key=linkimport.score) for g in groups.values()]
    title = _page_title(page) or src.name
    out = []
    for u in urls[:60]:
        if linkimport.refused_reason(u):
            continue
        name = urllib.parse.unquote(u.split("?")[0].rsplit("/", 1)[-1])
        out.append(Film(channel="Web", topic=src.name, title=f"{title} — {name}" if len(urls) > 1 else title, description=u,
                        timestamp=int(time.time()), duration=0, size=0, url_website=src.url, url_subtitle="", url_video=u,
                        id="web:" + u))
    return out


def videos(src: Source, session=None, tg_pages: int = 3) -> list[Film]:
    if src.kind == "telegram":
        return telegram_videos(src, tg_pages, session)
    if src.kind == "feed":
        return feed_videos(src, session)
    return page_videos(src, session)


def matches(f: Film, text: str) -> bool:
    words = [w for w in re.split(r"\s+", (text or "").casefold()) if w]
    hay = f"{f.title} {f.topic} {f.description}".casefold()
    return all(w in hay for w in words)


def search(sources: list[Source], text: str = "", session=None, tg_pages: int = 3) -> tuple[list[Film], list[str]]:
    """Every source's videos (in parallel) that contain all the words; newest first. Also the sources that failed."""
    from concurrent.futures import ThreadPoolExecutor
    errors: list[str] = []

    def one(s):
        try:
            return videos(s, None, tg_pages)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{s.name}: {e.__class__.__name__}")
            return []
    with ThreadPoolExecutor(max_workers=6) as ex:
        lists = list(ex.map(one, sources))
    films = [f for lst in lists for f in lst if matches(f, text)]
    return sorted(films, key=lambda f: -f.timestamp), errors
