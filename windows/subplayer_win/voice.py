"""
Natural voices for reading words and sentences aloud.

- "edge":    Microsoft's natural (neural) voices — the ones Edge reads with. Free, no key, needs the internet. Through the
             `edge-tts` package; the proxy in Settings ▸ Network is used.
- "piper":   Piper — free, offline neural voices. Piper and one German and one English voice are downloaded once
             (from this app's data-v1 release, SHA-checked), then work without internet.
- "windows": the voices installed in Windows (as before).
Each spoken text is kept as a small file (speech folder), so repeating it is instant and works offline.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess
from pathlib import Path

from . import downloads, paths

ENGINES = (("edge", "Natural — Microsoft voices (online, free)"),
           ("piper", "Natural — Piper (offline, download once)"),
           ("windows", "Windows voice (installed voices)"))

EDGE_VOICES = {
    "de": (("de-DE-KatjaNeural", "Katja (female)"), ("de-DE-ConradNeural", "Conrad (male)"),
           ("de-DE-SeraphinaMultilingualNeural", "Seraphina (female, very natural)"),
           ("de-DE-FlorianMultilingualNeural", "Florian (male, very natural)"),
           ("de-DE-AmalaNeural", "Amala (female)"), ("de-DE-KillianNeural", "Killian (male)"),
           ("de-AT-IngridNeural", "Ingrid (Austria)"), ("de-CH-LeniNeural", "Leni (Switzerland)")),
    "en": (("en-US-AvaMultilingualNeural", "Ava (US, very natural)"), ("en-US-AndrewMultilingualNeural", "Andrew (US, very natural)"),
           ("en-US-AriaNeural", "Aria (US)"), ("en-US-GuyNeural", "Guy (US)"), ("en-US-JennyNeural", "Jenny (US)"),
           ("en-GB-SoniaNeural", "Sonia (UK)"), ("en-GB-RyanNeural", "Ryan (UK)"), ("en-AU-NatashaNeural", "Natasha (Australia)")),
}

PIPER = downloads.Asset("piper-win", "Piper (offline voices)", "piper-win-v1.zip", 22,
                        "81fc27d5859bfc9aa3d7802f5eb1d05a0651be2f037ac44d8798a6605abf344f", "", "piper/piper.exe")
PIPER_VOICES = {
    "de": downloads.Asset("voice-de", "German offline voice (Thorsten)", "voice-de-v1.zip", 114,
                          "cd4c0a9532e76d05b623af09c049e8a08ef5a320d0c2b5e651c24b3f8a5149c0", "", "voices/de_DE-thorsten-high.onnx"),
    "en": downloads.Asset("voice-en", "English offline voice (Lessac)", "voice-en-v1.zip", 114,
                          "4b4354dfd6c37e87ad3813e2cf3685b3cf885a4c752c997f09a9883f284d7b45", "", "voices/en_US-lessac-high.onnx"),
}


def edge_voice(settings: dict, lang: str) -> str:
    lang = "en" if lang == "en" else "de"
    v = settings.get(f"voice_edge_{lang}", "")
    return v if v else EDGE_VOICES[lang][2 if lang == "de" else 0][0]


def piper_ready(lang: str) -> bool:
    return downloads.is_ready(PIPER) and downloads.is_ready(PIPER_VOICES["en" if lang == "en" else "de"])


def piper_missing(lang: str) -> list:
    return [a for a in (PIPER, PIPER_VOICES["en" if lang == "en" else "de"]) if not downloads.is_ready(a)]


def _cache(engine: str, voice: str, text: str, slow: bool, ext: str) -> Path:
    h = hashlib.sha1(f"{engine}|{voice}|{slow}|{text}".encode("utf-8")).hexdigest()[:20]
    return paths.sub_dir("speech") / f"{h}.{ext}"


def _http_proxy() -> str | None:
    for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        v = os.environ.get(k)
        if v and v.lower().startswith("http"):
            return v                      # edge-tts (aiohttp) takes an http proxy; a socks one is left to the system
    return None


def edge_file(text: str, voice: str, slow: bool = False) -> Path:
    f = _cache("edge", voice, text, slow, "mp3")
    if f.exists() and f.stat().st_size > 0:
        return f
    import edge_tts
    tmp = f.with_suffix(".part")

    async def go():
        c = edge_tts.Communicate(text, voice, rate="-25%" if slow else "+0%", proxy=_http_proxy(), connect_timeout=10, receive_timeout=30)
        await c.save(str(tmp))

    asyncio.run(go())
    if not tmp.exists() or tmp.stat().st_size == 0:
        raise IOError("No audio came back from Microsoft")
    tmp.replace(f)
    return f


def piper_file(text: str, lang: str, slow: bool = False) -> Path:
    a = PIPER_VOICES["en" if lang == "en" else "de"]
    f = _cache("piper", a.id, text, slow, "wav")
    if f.exists() and f.stat().st_size > 0:
        return f
    exe = downloads.ready_path(PIPER)
    model = downloads.ready_path(a)
    tmp = f.with_suffix(".part.wav")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run([str(exe), "--model", str(model), "--output_file", str(tmp), "--length_scale", "1.3" if slow else "1.0",
                        "--sentence_silence", "0.25"], input=text.replace("\n", " ").encode("utf-8"), capture_output=True,
                       timeout=120, cwd=str(exe.parent), creationflags=flags)
    if r.returncode != 0 or not tmp.exists() or tmp.stat().st_size < 100:
        raise IOError("Piper could not read it: " + (r.stderr.decode("utf-8", "replace")[-300:] or f"exit {r.returncode}"))
    tmp.replace(f)
    return f


def audio_file(settings: dict, text: str, lang: str, slow: bool = False) -> Path:
    """The spoken text as a file, with the chosen natural engine. Raises if it can't (the caller falls back to Windows)."""
    eng = settings.get("voice_engine", "edge")
    if eng == "piper":
        if not piper_ready(lang):
            raise FileNotFoundError("piper")
        return piper_file(text, lang, slow)
    return edge_file(text, edge_voice(settings, lang), slow)


def clear_cache() -> int:
    n = 0
    for f in paths.sub_dir("speech").glob("*"):
        try:
            f.unlink()
            n += 1
        except OSError:
            pass
    return n
