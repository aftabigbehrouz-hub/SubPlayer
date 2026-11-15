"""
Opens video links, like the phone app: a direct .mp4/.webm link, or a web page that offers an MP4 file
(Tagesschau and many news / public-broadcaster pages). The video is saved to Videos\\SubPlayer so it can be
watched offline and transcribed. Services whose terms forbid downloading (YouTube, Instagram, TikTok, Netflix…)
are refused.
"""
from __future__ import annotations

import html
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

REFUSED = ["youtube.com", "youtu.be", "instagram.com", "tiktok.com", "facebook.com", "fb.watch",
           "netflix.com", "x.com", "twitter.com", "disneyplus.com", "primevideo.com", "joyn.de"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SubPlayer"

DIRECT = re.compile(r"\.(mp4|m4v|webm|mov)(\?.*)?$", re.I)
VIDEO_URL = re.compile(r"""https?://[^"'\s<>\\]+\.(?:mp4|m4v|webm)(?:\?[^"'\s<>\\]*)?(?=["'\s<>\\]|$)""", re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
OG_TITLE = re.compile(r"""<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)""", re.I)


@dataclass
class Found:
    video_url: str
    title: str


def first_link(text: str) -> str | None:
    m = re.search(r"https?://\S+", text or "")
    return m.group(0).rstrip(").,;'\"") if m else None


def refused_reason(url: str) -> str | None:
    host = (urllib.parse.urlparse(url.strip()).hostname or "").lower()
    hit = next((d for d in REFUSED if host == d or host.endswith("." + d)), None)
    if not hit:
        return None
    return (f"SubPlayer can't download from {hit.split('.')[0].capitalize()}: its terms don't allow it. "
            "Videos already on your PC open with Open, or by dragging them onto SubPlayer.")


def score(u: str) -> int:
    """Medium quality first (Tagesschau names qualities webs < webm < webl < webxl < webxxl)."""
    l = u.lower()
    if ".webl." in l:
        s = 60
    elif ".webxl." in l:
        s = 55
    elif ".webm." in l and "h264" in l:
        s = 50
    elif ".webxxl." in l:
        s = 40
    elif ".webs." in l:
        s = 30
    else:
        s = 45
    if "h264" in l:
        s += 3
    if "trailer" in l or "teaser" in l:
        s -= 20
    return s


def find_in_page(page: str) -> Found | None:
    text = page.replace("\\/", "/").replace("\\u002F", "/").replace("&amp;", "&")
    urls = list(dict.fromkeys(m.group(0) for m in VIDEO_URL.finditer(text)))
    if not urls:
        return None
    best = max(urls, key=score)
    m = OG_TITLE.search(page) or TITLE.search(page)
    title = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else "video"
    return Found(best, title or "video")


def safe_name(title: str) -> str:
    n = re.sub(r"[^\w .-]+", " ", title, flags=re.U)
    n = re.sub(r"\s+", " ", n).strip()[:70].strip(" .")
    return (n or "video") + ".mp4"


def resolve(url: str, session=None) -> Found:
    import requests
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        raise ValueError("That doesn't look like a web link")
    parsed = urllib.parse.urlparse(u)
    if DIRECT.search(parsed.path + (("?" + parsed.query) if parsed.query else "")):
        return Found(u, Path(parsed.path).stem or "video")
    s = session or requests.Session()
    r = s.get(u, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    found = find_in_page(r.text[:5_000_000])
    if not found:
        raise ValueError("No downloadable video found on that page")
    return found


def videos_dir() -> Path:
    p = Path.home() / "Videos" / "SubPlayer"
    p.mkdir(parents=True, exist_ok=True)
    return p


def download(found: Found, folder: Path | None = None, progress=lambda done, total: None, cancelled=lambda: False) -> Path:
    import requests
    folder = folder or videos_dir()
    dest = folder / safe_name(found.title)
    k = 2
    while dest.exists():
        dest = folder / f"{Path(safe_name(found.title)).stem} ({k}).mp4"
        k += 1
    tmp = dest.with_suffix(".part")
    with requests.get(found.video_url, headers={"User-Agent": UA}, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        try:
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(256 * 1024):
                    if cancelled():
                        raise RuntimeError("Cancelled")
                    f.write(chunk)
                    done += len(chunk)
                    progress(done, total)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    tmp.replace(dest)
    return dest
