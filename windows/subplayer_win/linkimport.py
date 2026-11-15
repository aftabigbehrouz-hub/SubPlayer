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
    subtitle_text: str = ""      # subtitles found inside a stream (already .srt)


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


ALT_VERSION = re.compile(r"(audiodeskription|/ad/|_ad_|-ad-|_ad\.|gebaerdensprache|_dgs|klaresprache|klare-sprache|_ks_)", re.I)


def _pick_mp4(cands: list[tuple[str, int]]) -> str:
    """(url, height) — the best file up to 720p (good picture, sensible size); otherwise the smallest bigger one."""
    cands = [(u, h) for u, h in cands if not ALT_VERSION.search(u)] or cands
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
    # the size given beside each file is more reliable than the file name: "forcedLabel": "HD 720p", or
    # "maxHResolutionPx" (the picture WIDTH, e.g. 1280 = 720p)
    for path, v in _walk(data):
        if not path or path[-1] not in ("maxHResolutionPx", "forcedLabel"):
            continue
        node = data
        for k in path[:-1]:
            node = node[int(k)] if isinstance(node, list) else node[k]
        u = node.get("url") if isinstance(node, dict) else None
        if not isinstance(u, str):
            continue
        u = "https:" + u if u.startswith("//") else u
        h = 0
        if path[-1] == "forcedLabel" and isinstance(v, str):
            m = re.search(r"(\d{3,4})p", v)
            h = int(m.group(1)) if m else 0
        elif isinstance(v, int) and v > 0:
            h = round(v * 9 / 16)
        if h:
            mp4 = [(x, h if x == u else hh) for x, hh in mp4]
    sub = next((u for u in subs if u.lower().split("?")[0].endswith(".vtt")), subs[0] if subs else "")
    if mp4:
        return Found(_pick_mp4(mp4), title or "ARD video", sub)
    if hls:
        return Found(hls[0], title or "ARD video", sub, hls=True)
    raise ValueError("This ARD video isn't available (it may have expired, or be a live stream)")


ARTE_ID = re.compile(r"arte\.tv/(de|fr|en|es|pl|it)/videos/(\d{6}-\d{3}-[A-Z])", re.I)


def arte_item(lang: str, pid: str, session) -> Found:
    """Arte: the player configuration lists the streams; the German original version is preferred (no burnt-in subtitles,
    no audio description)."""
    r = session.get(f"https://api.arte.tv/api/player/v2/config/{lang}/{pid}", headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    attrs = (r.json().get("data") or {}).get("attributes") or {}
    streams = attrs.get("streams") or []
    if not streams:
        raise ValueError("This Arte programme isn't available (expired, not yet online, or not offered in this country)")

    def rank(st):
        vs = st.get("versions") or [{}]
        label = " ".join(str(v.get("label", "")) + " " + str(v.get("shortLabel", "")) for v in vs).lower()
        code = " ".join(str(v.get("eStat", {}).get("ml5", "")) for v in vs).upper()
        bad = any(k in label for k in ("hörfilm", "audiodeskription", "untertitel", "sous-titr", "ut ", "st ", "sme"))
        german = "deutsch" in label or code.startswith(("VA", "VOA")) or "DE" in code
        return (german, not bad, -int(st.get("mainQuality", {}).get("code", "XQ") != "XQ"))
    best = max(streams, key=rank)
    meta = attrs.get("metadata") or {}
    title = " – ".join(x for x in (meta.get("title"), meta.get("subtitle")) if x) or pid
    dur = int((meta.get("duration") or {}).get("seconds") or 0)
    return Found(best["url"], title, "", hls=True, duration=dur)


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
    am = ARTE_ID.search(u)
    if am:
        return arte_item(am.group(1).lower(), am.group(2).upper(), s)
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
    mt = OG_TITLE.search(page) or TITLE.search(page)
    title = html.unescape(re.sub(r"<[^>]+>", "", mt.group(1))).strip() if mt else ""
    if "{{" in title:                                    # page filled in later by a script
        title = ""
    if is_broadcaster(u):
        from . import mediathek
        f = mediathek.lookup(u, title, session=s, similar=False)      # the catalogue's own entry for this page
        if f:
            return _from_film(f)
    found = find_in_page(page)
    if found and is_broadcaster(u):
        found.subtitle_url = found.subtitle_url or find_subtitle(page)
    if not found and is_broadcaster(u) and title:
        from . import mediathek
        f = mediathek.lookup(u, title, session=s, similar=True)
        if f:
            found = _from_film(f)
    if not found:
        raise ValueError("No downloadable video found on that page. For ARD, ZDF, 3sat, Arte and DW programmes, "
                         "Discover finds them by name.")
    return found


def _from_film(f) -> Found:
    title = f.title if f.topic.lower() in f.title.lower() else f"{f.topic} – {f.title}"
    u = f.video()
    return Found(u, title, f.url_subtitle, hls=bool(HLS.search(u.split("?")[0])), duration=f.duration)


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
        if "mpegurl" in r.headers.get("Content-Type", "").lower():          # a stream playlist behind a plain-looking link
            r.close()
            found.hls = True
            _download_hls(found, tmp, progress, cancelled)
            tmp.replace(dest)
            return dest
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


# ------------------------------------------------------------------ HLS streams
_ATTR = re.compile(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)')


def m3u8_attrs(line: str) -> dict:
    return {k: v.strip('"') for k, v in _ATTR.findall(line.split(":", 1)[1] if ":" in line else "")}


@dataclass
class HlsPick:
    video: str                      # media playlist of the picture (may also carry the sound)
    audio: str = ""                 # separate sound playlist, if the stream has one
    subtitles: str = ""             # subtitle playlist (WebVTT), if offered
    height: int = 0


def pick_hls(master_url: str, text: str, max_height: int = 720) -> HlsPick:
    """From a master playlist: the best H.264 picture up to max_height, the normal German sound (not Klare Sprache /
    audio description), German subtitles."""
    from urllib.parse import urljoin
    lines = text.splitlines()
    if not any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
        return HlsPick(master_url)                                  # already a media playlist
    variants, audios, subs = [], [], []
    for k, l in enumerate(lines):
        if l.startswith("#EXT-X-STREAM-INF"):
            a = m3u8_attrs(l)
            uri = next((x for x in lines[k + 1:] if x and not x.startswith("#")), "")
            res = a.get("RESOLUTION", "0x0")
            h = int(res.split("x")[1]) if "x" in res else 0
            variants.append((urljoin(master_url, uri), h, a.get("CODECS", ""), int(a.get("BANDWIDTH", 0) or 0), a.get("AUDIO", "")))
        elif l.startswith("#EXT-X-MEDIA"):
            a = m3u8_attrs(l)
            if a.get("URI"):
                a["URI"] = urljoin(master_url, a["URI"])
                (audios if a.get("TYPE") == "AUDIO" else subs if a.get("TYPE") == "SUBTITLES" else []).append(a)
    avc = [v for v in variants if "avc1" in v[2] or not v[2]] or variants
    fit = [v for v in avc if 0 < v[1] <= max_height] or avc
    v = max(fit, key=lambda x: (x[1], -x[3] if x[1] > max_height else x[3]))

    def alt(a):
        t = (a.get("NAME", "") + " " + a.get("CHARACTERISTICS", "")).lower()
        return any(x in t for x in ("klare sprache", "audiodeskription", "description", "public.accessibility", "hörfilm"))
    group = [a for a in audios if not v[4] or a.get("GROUP-ID") == v[4]] or audios
    de = [a for a in group if a.get("LANGUAGE", "").lower().startswith(("de", "ger", "deu"))]
    pool = [a for a in (de or group) if not alt(a)] or de or group
    au = max(pool, key=lambda a: a.get("DEFAULT") == "YES")["URI"] if pool else ""
    sde = [a for a in subs if a.get("LANGUAGE", "").lower().startswith(("de", "ger", "deu"))]
    sde.sort(key=lambda a: ("automat" in a.get("NAME", "").lower(), a.get("FORCED") == "YES"))
    return HlsPick(v[0], au, sde[0]["URI"] if sde else "", v[1])


def single_file(playlist_url: str, text: str) -> str | None:
    """CMAF streams often keep every piece in ONE file (byte ranges): then that file can simply be downloaded."""
    from urllib.parse import urljoin
    uris = {x.strip() for x in text.splitlines() if x.strip() and not x.startswith("#")}
    m = re.search(r'#EXT-X-MAP:.*URI="([^"]+)"', text)
    if m:
        uris.add(m.group(1))
    return urljoin(playlist_url, uris.pop()) if len(uris) == 1 else None


def _get_text(url: str) -> str:
    import requests
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    if r.status_code in (403, 451):
        raise PermissionError(GEO_HINT)
    r.raise_for_status()
    return r.text


def _fetch_file(url: str, dest: Path, progress, cancelled, base: int = 0, grand: int = 0):
    import requests
    with requests.get(url, headers={"User-Agent": UA}, stream=True, timeout=60) as r:
        if r.status_code in (403, 451):
            raise PermissionError(GEO_HINT)
        r.raise_for_status()
        done = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(256 * 1024):
                if cancelled():
                    raise RuntimeError("Cancelled")
                f.write(chunk)
                done += len(chunk)
                progress(base + done, grand or 0)
    return done


def _head_size(url: str) -> int:
    import requests
    try:
        r = requests.head(url, headers={"User-Agent": UA}, timeout=20, allow_redirects=True)
        return int(r.headers.get("Content-Length") or 0)
    except Exception:
        return 0


def _download_hls(found: Found, tmp: Path, progress, cancelled, stop_at: float = 0, max_height: int = 720):
    """Saves an HLS stream as one MP4 without re-encoding: picture + German sound (+ German subtitles into
    found.subtitle_text when the stream offers plain WebVTT)."""
    pick = pick_hls(found.video_url, _get_text(found.video_url), max_height)
    v_text = _get_text(pick.video)
    a_text = _get_text(pick.audio) if pick.audio else ""
    v_file = single_file(pick.video, v_text)
    a_file = single_file(pick.audio, a_text) if pick.audio else None
    parts = []
    try:
        if pick.subtitles:
            try:
                found.subtitle_text = _vtt_from_playlist(pick.subtitles)
            except Exception:
                found.subtitle_text = ""
        if v_file and (a_file or not pick.audio) and not stop_at:
            # whole files: plain downloads (fast, exact progress), then joined
            sizes = [_head_size(v_file), _head_size(a_file) if a_file else 0]
            grand = sum(sizes)
            vp = tmp.with_name(tmp.stem + ".v.mp4")
            parts.append(vp)
            got = _fetch_file(v_file, vp, progress, cancelled, 0, grand)
            ap = None
            if a_file:
                ap = tmp.with_name(tmp.stem + ".a.mp4")
                parts.append(ap)
                _fetch_file(a_file, ap, progress, cancelled, got, grand)
            _mux([str(vp)] + ([str(ap)] if ap else []), tmp, lambda d, t: None, cancelled, 0)
        else:
            dur = float(found.duration or 0)
            _mux([pick.video] + ([pick.audio] if pick.audio else []), tmp, progress, cancelled, dur, stop_at)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        for p_ in parts:
            p_.unlink(missing_ok=True)


def _vtt_from_playlist(url: str) -> str:
    from urllib.parse import urljoin
    import requests
    text = _get_text(url)
    uris = list(dict.fromkeys(x.strip() for x in text.splitlines() if x.strip() and not x.startswith("#")))
    out = []
    for u in uris[:2000]:
        r = requests.get(urljoin(url, u), headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        t = r.content.decode("utf-8", errors="replace")
        if not t.lstrip("\ufeff").startswith("WEBVTT"):
            return ""                                    # binary (CMAF) subtitles — not used
        out.append(t)
    from . import subtitles
    cues = []
    for t in out:
        cues += subtitles.parse(t)
    cues.sort(key=lambda c: c.start_ms)
    return subtitles.write(cues) if len(cues) >= 3 else ""


def _mux(inputs: list[str], tmp: Path, progress, cancelled, dur: float = 0, stop_at: float = 0):
    """Copies the picture (first input) and the sound (second input, or the first one's) into one MP4, interleaved."""
    import av
    from . import netcfg
    opts = {"user_agent": UA, "reconnect": "1", "reconnect_streamed": "1", "reconnect_delay_max": "5"}
    px = netcfg.ffmpeg_proxy()
    if px:
        opts["http_proxy"] = px
    srcs = []
    try:
        for i in inputs:
            try:
                srcs.append(av.open(i, options=opts if i.startswith("http") else {}, timeout=(30, 60)))
            except av.error.HTTPForbiddenError:
                raise PermissionError(GEO_HINT)
        vsrc = srcs[0]
        v = max(vsrc.streams.video, key=lambda s: (s.codec_context.height or 0)) if vsrc.streams.video else None
        asrc = srcs[1] if len(srcs) > 1 else srcs[0]
        a = None
        if asrc.streams.audio:
            a = next((s for s in asrc.streams.audio if (s.metadata or {}).get("language", "").startswith(("de", "ger", "deu"))), None) \
                or asrc.streams.audio[0]
        if v is None and a is None:
            raise ValueError("The stream has no picture or sound")
        dur = dur or ((vsrc.duration or 0) / 1_000_000)
        out = av.open(str(tmp), "w", format="mp4")
        try:
            omap = {}
            if v is not None:
                omap[(0, v.index)] = out.add_stream_from_template(v)
            if a is not None:
                omap[(srcs.index(asrc), a.index)] = out.add_stream_from_template(a)

            def packets(ci, src, streams):
                for pkt in src.demux(streams):
                    if pkt.dts is None:
                        continue
                    yield ci, pkt
            gens = []
            if asrc is vsrc:
                gens.append(packets(0, vsrc, [x for x in (v, a) if x is not None]))
            else:
                if v is not None:
                    gens.append(packets(0, vsrc, [v]))
                if a is not None:
                    gens.append(packets(1, asrc, [a]))
            heads = [next(g, None) for g in gens]
            while any(h is not None for h in heads):
                if cancelled():
                    raise RuntimeError("Cancelled")
                k = min((i for i, h in enumerate(heads) if h is not None),
                        key=lambda i: float(heads[i][1].dts * heads[i][1].time_base))
                ci, pkt = heads[k]
                t = float(pkt.dts * pkt.time_base)
                if stop_at and t > stop_at:
                    heads[k] = None
                    continue
                pkt.stream = omap[(ci, pkt.stream.index)]
                out.mux(pkt)
                if dur:
                    progress(min(t, dur), dur)
                heads[k] = next(gens[k], None)
        finally:
            out.close()
    finally:
        for s_ in srcs:
            s_.close()
