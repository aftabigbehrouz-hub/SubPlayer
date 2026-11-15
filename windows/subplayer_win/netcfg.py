"""
How SubPlayer reaches the internet: Windows' own proxy settings (default), a proxy the user enters — for example the local
port of a VPN app such as v2rayN, Hiddify or Psiphon — or a direct connection. Applied to everything: video links and
Discover, dictionary/model downloads, translation, online subtitles and sync (all use `requests`), and stream copying
(FFmpeg's http_proxy).
"""
from __future__ import annotations

import os
import re
import urllib.request

VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
_original = {k: os.environ.get(k) for k in VARS}


def normalise(text: str, kind: str = "http") -> str:
    """'127.0.0.1:10809' -> 'http://127.0.0.1:10809'; keeps an explicit scheme."""
    t = (text or "").strip()
    if not t:
        return ""
    if not re.match(r"^[a-z0-9]+://", t, re.I):
        t = f"{'socks5h' if kind == 'socks5' else 'http'}://{t}"
    if t.lower().startswith("socks5://"):
        t = "socks5h://" + t[9:]                      # names resolved through the proxy too (needed behind filters)
    return t


def valid(text: str) -> bool:
    return bool(re.match(r"^(https?|socks5h?)://[^\s:/]+:\d{2,5}/?$", normalise(text), re.I))


def apply(settings: dict) -> str:
    """Sets the process-wide proxy; returns a one-line description."""
    mode = settings.get("net_mode", "system")
    for k in VARS:                                     # back to what Windows / the user's environment had
        if _original[k] is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = _original[k]
    if mode == "proxy":
        url = normalise(settings.get("net_proxy", ""), settings.get("net_kind", "http"))
        if valid(url):
            for k in VARS:
                os.environ[k] = url
            os.environ.pop("NO_PROXY", None)
            os.environ["no_proxy"] = "localhost,127.0.0.1"
            return f"through the proxy {url}"
        return "proxy address not valid — using Windows' settings"
    if mode == "direct":
        for k in VARS:
            os.environ.pop(k, None)
        os.environ["NO_PROXY"] = os.environ["no_proxy"] = "*"
        return "direct (no proxy)"
    os.environ.pop("NO_PROXY", None)
    os.environ.pop("no_proxy", None)
    p = system_proxy()
    return f"Windows' settings ({p})" if p else "Windows' settings (no proxy)"


def system_proxy() -> str:
    try:
        d = urllib.request.getproxies()
    except Exception:
        return ""
    return d.get("https") or d.get("http") or ""


def ffmpeg_proxy() -> str:
    """For FFmpeg (stream copying): only http proxies work there."""
    p = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or system_proxy()
    if p and not p.lower().startswith("http"):
        return ""
    if p and "://" not in p:
        p = "http://" + p
    return p


def test() -> list[tuple[str, bool, str]]:
    """Reaches the catalogue, a broadcaster and GitHub (downloads) — [(name, ok, detail)]."""
    import time
    import requests
    out = []
    for name, url in (("Video catalogue (Discover)", "https://mediathekviewweb.de/"),
                      ("ARD / Tagesschau", "https://www.tagesschau.de/"),
                      ("ZDF", "https://www.zdf.de/"),
                      ("Downloads (GitHub)", "https://github.com/")):
        t0 = time.monotonic()
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "SubPlayer"})
            out.append((name, r.status_code < 400, f"{r.status_code} · {int((time.monotonic() - t0) * 1000)} ms"))
        except Exception as e:
            out.append((name, False, type(e).__name__ + ": " + str(e)[:90]))
    return out
