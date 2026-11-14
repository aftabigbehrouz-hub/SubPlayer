"""Where the Windows app keeps its files: %APPDATA%\\SubPlayer (or ~/.subplayer elsewhere)."""
import os
from pathlib import Path


def data_dir() -> Path:
    base = os.environ.get("SUBPLAYER_HOME")
    if base:
        p = Path(base)
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
