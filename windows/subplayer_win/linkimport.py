"""
Opens video links: a direct .mp4/.webm/.m3u8 link, or a page of the German public broadcasters — Tagesschau, ARD Mediathek,
ZDF, 3sat, Arte, Deutsche Welle, KiKA, phoenix and the regional stations — which offer their programmes as plain video files.
The broadcaster's own subtitles come along when it has them. The video is saved to Videos\\SubPlayer so it can be watched
offline. Services whose terms forbid downloading (YouTube, Instagram, TikTok, Netflix…) are refused.
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
    subtitle_url: str = ""
    hls: bool = False            # an .m3u8 stream: copied into an MP4 (no re-encoding)
    duration: int = 0            # seconds, if known (for the progress of streams)


BROADCASTERS = ("ardmediathek.de", "ard.de", "tagesschau.de", "sportschau.de", "zdf.de", "zdfheute.de", "3sat.de", "arte.tv",
                "dw.com", "kika.de", "phoenix.de", "br.de", "swr.de", "wdr.de", "ndr.de", "mdr.de", "hr.de", "rbb-online.de",
                "rbb24.de", "sr.de", "radiobremen.de", "funk.net", "orf.at", "srf.ch", "zdftivi.de", "planet-wissen.de", "quarks.de")


def is_broadcaster(url: str) -> bool:
    host = (urllib.parse.urlparse(url.strip()).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in BROADCASTERS)


def first_link(text: str) -> str | None:
    m = re.search(r"https?://\S+", text or "")
    return m.group(0).rstrip(").,;'\"") if m else None


def refused_reason(url: str) -> str | None:
    host = (urllib.parse.urlparse(url.strip()).hostname or "").lower()
    hit = next((d for d in REFUSED if host == d or host.endswith("." + d)), None)
    if not hit:
        return None
    names = {"youtu.be": "YouTube", "youtube.com": "YouTube", "fb.watch": "Facebook", "x.com": "X", "tiktok.com": "TikTok",
             "primevideo.com": "Prime Video", "disneyplus.com": "Disney+"}
    name = names.get(hit, hit.split(".")[0].capitalize())
    return (f"SubPlayer can't download from {name}: its terms don't allow it (and in Germany getting around its download "
            "protection is not allowed either). Videos already on your PC open with Open or by dragging them onto SubPlayer — "
            "and Discover finds thousands of ARD, ZDF, 3sat, Arte and DW programmes that may be downloaded.")


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


HLS = re.compile(r"\.m3u8(\?.*)?$", re.I)
def ard_id(url: str) -> str | None:
    """ARD Mediathek item ids are base64 of "crid://…" (they start with Y3JpZDovL)."""
    p = urllib.parse.urlparse(url)
    if not (p.hostname or "").endswith("ardmediathek.de"):
        return None
    return next((seg for seg in reversed(p.path.split("/")) if seg.startswith("Y3JpZDovL")), None)


def _walk(o, path=()):
    """Every (key-path, value) pair in a JSON tree."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _walk(v, path + (str(k),))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk(v, path + (str(i),))
    else:
        yield path, o


def _pick_mp4(cands: list[tuple[str, int]]) -> str:
    """(url, height) — the best file up to 720p (good picture, sensible size); otherwise the smallest bigger one."""
    cands = [(u, h) for u, h in cands if not re.search(r"(audiodeskription|/ad/|_ad_|-ad-|gebaerdensprache|_dgs)", u, re.I)] or cands
    upto = [c for c in cands if 0 < c[1] <= 720]
    if upto:
        return max(upto, key=lambda c: c[1])[0]
    known = [c for c in cands if c[1] > 720]
    if known:
        return min(known, key=lambda c: c[1])[0]
    return max((c[0] for c in cands), key=score)


def ard_item(item_id: str, session) -> Found:
    """ARD Mediathek: the player data of the item (video files in several sizes + subtitles)."""
    r = session.get(f"https://api.ardmediathek.de/page-gateway/pages/ard/item/{item_id}",
                    params={"devicetype": "pc", "embedded": "true"}, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    data = r.json()
    mp4, hls, subs = [], [], []
    title = ""
    for path, v in _walk(data):
        if not isinstance(v, str):
            continue
        if path and path[-1] == "title" and not title and len(path) <= 3:
            title = v
        u = v.strip()
        if u.startswith("//"):
            u = "https:" + u
        if not u.startswith("http"):
            continue
        low = u.lower().split("?")[0]
        joined = "/".join(path).lower()
        if low.endswith(".mp4"):
            h = 0
            m = re.search(r"(\d{3,4})p", low) or re.search(r"_(\d{3,4})x(\d{3,4})", low)
            if m:
                h = int(m.group(2) if m.lastindex == 2 else m.group(1))
            mp4.append((u, h))
        elif low.endswith(".m3u8"):
            hls.append(u)
        elif "subtitle" in joined and (low.endswith(".vtt") or low.endswith(".xml") or "ebutt" in low or "webvtt" in low):
            subs.append(u)
    # heights given beside the url (maxHResolutionPx) are more reliable than names
    for path, v in _walk(data):
        if path and path[-1] == "maxHResolutionPx" and isinstance(v, int):
            parent = path[:-1]
            node = data
            for k in parent:
                node = node[int(k)] if isinstance(node, list) else node[k]
            u = node.get("url") if isinstance(node, dict) else None
            if isinstance(u, str):
                u = "https:" + u if u.startswith("//") else u
                mp4 = [(x, v if x == u else h) for x, h in mp4]
    sub = next((u for u in subs if u.lower().split("?")[0].endswith(".vtt")), subs[0] if subs else "")
    if mp4:
        return Found(_pick_mp4(mp4), title or "ARD video", sub)
    if hls:
        return Found(hls[0], title or "ARD video", sub, hls=True)
    raise ValueError("This ARD video isn't available (it may have expired, or be a live stream)")


def resolve(url: str, session=None) -> Found:
    import requests
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        raise ValueError("That doesn't look like a web link")
    parsed = urllib.parse.urlparse(u)
    path_q = parsed.path + (("?" + parsed.query) if parsed.query else "")
    if DIRECT.search(path_q):
        return Found(u, Path(parsed.path).stem or "video")
    if HLS.search(path_q):
        return Found(u, Path(parsed.path).stem or "video", hls=True)
    s = session or requests.Session()
    aid = ard_id(u)
    if aid:
        try:
            return ard_item(aid, s)
        except ValueError:
            raise
        except Exception:
            pass                                    # fall back to the page and the catalogue
    r = s.get(u, headers={"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9"}, timeout=30)
    r.raise_for_status()
    page = r.text[:5_000_000]
    found = find_in_page(page)
    if found and is_broadcaster(u):
        found.subtitle_url = found.subtitle_url or find_subtitle(page)
    if not found and is_broadcaster(u):
        from . import mediathek
        mt = OG_TITLE.search(page) or TITLE.search(page)
        title = html.unescape(re.sub(r"<[^>]+>", "", mt.group(1))).strip() if mt else ""
        f = mediathek.lookup(u, title, session=s)
        if f:
            found = Found(f.video(), f.title if f.topic.lower() in f.title.lower() else f"{f.topic} – {f.title}", f.url_subtitle,
                          duration=f.duration)
    if not found:
        raise ValueError("No downloadable video found on that page. For ARD, ZDF, 3sat, Arte and DW programmes, "
                         "Discover finds them by name.")
    return found


SUB_URL = re.compile(r"""https?://[^"'\s<>\\]+\.(?:vtt|xml|ttml)(?:\?[^"'\s<>\\]*)?(?=["'\s<>\\]|$)""", re.I)


def find_subtitle(page: str) -> str:
    text = page.replace("\\/", "/").replace("\\u002F", "/").replace("&amp;", "&")
    for m in SUB_URL.finditer(text):
        u = m.group(0)
        if re.search(r"(untertitel|subtitle|/ut/|_ut|caption|ebutt|webvtt|\.vtt)", u, re.I) and "sitemap" not in u.lower():
            return u
    return ""


def subtitle_srt(url: str, session=None) -> str | None:
    """The broadcaster's subtitles as .srt text (None if missing or unreadable)."""
    if not url:
        return None
    import requests
    from . import subtitles
    try:
        r = (session or requests).get(url, headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        r.encoding = r.encoding or "utf-8"
        cues = subtitles.parse_any(r.content.decode("utf-8", errors="replace"))
    except Exception:
        return None
    return subtitles.write(cues) if len(cues) >= 3 else None


def videos_dir() -> Path:
    p = Path.home() / "Videos" / "SubPlayer"
    p.mkdir(parents=True, exist_ok=True)
    return p


GEO_HINT = ("This programme can only be watched from Germany (or Austria/Switzerland) — the broadcaster blocks other countries. "
            "With a VPN or proxy set to Germany it works: Settings ▸ Internet connection.")


def download(found: Found, folder: Path | None = None, progress=lambda done, total: None, cancelled=lambda: False) -> Path:
    import requests
    folder = folder or videos_dir()
    dest = folder / safe_name(found.title)
    k = 2
    while dest.exists():
        dest = folder / f"{Path(safe_name(found.title)).stem} ({k}).mp4"
        k += 1
    tmp = dest.with_name(dest.stem + ".part.mp4")
    if found.hls:
        _download_hls(found, tmp, progress, cancelled)
        tmp.replace(dest)
        return dest
    with requests.get(found.video_url, headers={"User-Agent": UA}, stream=True, timeout=60) as r:
        if r.status_code in (403, 451) or (r.status_code == 404 and re.search(r"/(de|dach)/|geo", found.video_url, re.I)):
            raise PermissionError(GEO_HINT)
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


def _download_hls(found: Found, tmp: Path, progress, cancelled):
    """Copies an HLS stream (the best video up to 720p + its audio) into an MP4 without re-encoding."""
    import av
    opts = {"user_agent": UA, "reconnect": "1", "reconnect_streamed": "1", "reconnect_delay_max": "5"}
    try:
        src = av.open(found.video_url, options=opts, timeout=(30, 60))
    except av.error.HTTPForbiddenError:
        raise PermissionError(GEO_HINT)
    try:
        vids = [s for s in src.streams.video]
        good = [s for s in vids if (s.codec_context.height or 0) <= 720] or vids
        v = max(good, key=lambda s: (s.codec_context.height or 0, s.bit_rate or 0)) if good else None
        a = None
        if src.streams.audio:
            a = next((s for s in src.streams.audio if (s.metadata or {}).get("language", "").startswith(("de", "ger", "deu"))), None) \
                or src.streams.audio[0]
        if v is None and a is None:
            raise ValueError("The stream has no picture or sound")
        dur = (src.duration / 1_000_000) if src.duration else float(found.duration or 0)
        out = av.open(str(tmp), "w", format="mp4")
        try:
            mapping = {}
            for s_in in (v, a):
                if s_in is not None:
                    mapping[s_in.index] = out.add_stream_from_template(s_in)
            for pkt in src.demux([x for x in (v, a) if x is not None]):
                if cancelled():
                    raise RuntimeError("Cancelled")
                if pkt.dts is None:
                    continue
                pkt.stream = mapping[pkt.stream.index]
                out.mux(pkt)
                if dur and pkt.pts is not None and pkt.time_base is not None:
                    progress(min(float(pkt.pts * pkt.time_base), dur), dur)
        finally:
            out.close()
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        src.close()
