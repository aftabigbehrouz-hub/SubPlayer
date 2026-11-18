"""Where the Windows app keeps its files: %APPDATA%\\SubPlayer (or ~/.subplayer elsewhere).

Portable (2.6): when a folder named "SubPlayer data" is next to SubPlayer.exe, everything is kept there instead — words,
settings, subtitles, lessons, dictionaries and speech models — so the SubPlayer folder can be carried on a flash drive or
copied to another PC as it is."""
import os
import sys
from pathlib import Path

PORTABLE = "SubPlayer data"


def portable_dir() -> Path | None:
    if getattr(sys, "frozen", False):
        p = Path(sys.executable).resolve().parent / PORTABLE
        if p.is_dir():
            return p
    return None


def data_dir() -> Path:
    base = os.environ.get("SUBPLAYER_HOME")
    port = None if base else portable_dir()
    if base:
        p = Path(base)
    elif port:
        p = port
    elif os.name == "nt" and os.environ.get("APPDATA"):
        p = Path(os.environ["APPDATA"]) / "SubPlayer"
    else:
        p = Path.home() / ".subplayer"
    p.mkdir(parents=True, exist_ok=True)
    return p


def sub_dir(name: str) -> Path:
    p = data_dir() / name
    p.mkdir(parents=True, exist_ok=True)
    return p
