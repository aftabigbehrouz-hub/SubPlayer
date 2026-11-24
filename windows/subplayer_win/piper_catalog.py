"""The Piper voice catalogue: every voice of rhasspy/piper-voices (Hugging Face), downloaded one by one on demand.

Source: https://huggingface.co/rhasspy/piper-voices — the voice repository of the Piper project (the engine itself moved to
github.com/OHF-Voice/piper1-gpl; the voices stayed here). Its voices.json lists every voice with its language, quality,
speakers and files (size + MD5). The catalogue is read when the Voices window opens and kept as a copy, so the list is
there offline too; a voice works offline once downloaded.

Voices are stored in <SubPlayer data>/assets/piper/catalog/<family>/<locale>/<name>/<quality>/ (portable mode: next to
SubPlayer.exe in "SubPlayer data"). Each voice keeps the licence of its dataset — see its MODEL_CARD (downloaded with it).
SubPlayer uses these voices only to read words and sentences aloud when asked; the video's own sound is never replaced.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from . import paths

REPOSITORY = "rhasspy/piper-voices"
BASE = f"https://huggingface.co/{REPOSITORY}/resolve/main"
CATALOGUE_URL = BASE + "/voices.json"
QUALITIES = ("x_low", "low", "medium", "high")
QUALITY_NAME = {"x_low": "x-low", "low": "low", "medium": "medium", "high": "high"}
_TIMEOUT = (15, 60)
_KEY = re.compile(r"^[A-Za-z0-9_\-]+$")


class CatalogueError(ValueError):
    """The catalogue could not be read (network, or a response that is not the voice list)."""


@dataclass(frozen=True)
class PiperVoice:
    key: str                      # de_DE-thorsten-high
    name: str                     # thorsten
    family: str                   # de
    code: str                     # de_DE
    language: str                 # German
    language_native: str          # Deutsch
    country: str                  # Germany
    quality: str                  # high
    num_speakers: int = 1
    files: dict = field(default_factory=dict, compare=False, hash=False)   # relative path → {"size_bytes", "md5_digest"}

    # -- the files of the voice
    def _one(self, suffix: str) -> str:
        return next((p for p in self.files if p.endswith(suffix)), "")

    @property
    def model_rel(self) -> str:
        return self._one(".onnx")

    @property
    def config_rel(self) -> str:
        return self._one(".onnx.json")

    @property
    def card_rel(self) -> str:
        return self._one("MODEL_CARD")

    @property
    def size_bytes(self) -> int:
        return sum(int(f.get("size_bytes") or 0) for f in self.files.values())

    @property
    def folder(self) -> Path:
        return voice_root() / Path(*PurePosixPath(self.model_rel).parent.parts)

    @property
    def model_path(self) -> Path:
        return voice_root() / Path(*PurePosixPath(self.model_rel).parts)

    @property
    def label(self) -> str:
        sp = f" · {self.num_speakers} speakers" if self.num_speakers > 1 else ""
        return f"{self.name} — {self.language} ({self.country}) · {QUALITY_NAME.get(self.quality, self.quality)}{sp}"

    @property
    def sample_url(self) -> str:
        """The upstream sample recording (the first speaker) beside the voice's files."""
        d = str(PurePosixPath(self.model_rel).parent)
        return f"{BASE}/{quote(d, safe='/')}/samples/speaker_0.mp3"


def voice_root() -> Path:
    return paths.sub_dir("assets") / "piper" / "catalog"


def _cache_file() -> Path:
    return voice_root() / "voices.json"


def _safe_rel(rel: str) -> str:
    """A path from the catalogue, only if it is a plain relative path (no drive, no .., no backslash)."""
    p = PurePosixPath(rel)
    if not rel or "\\" in rel or p.is_absolute() or ".." in p.parts or ":" in rel or rel.startswith("/"):
        raise CatalogueError(f"unsafe path in the catalogue: {rel!r}")
    return str(p)


def parse_catalogue(data) -> list[PiperVoice]:
    """voices.json → [PiperVoice], sorted by language, locale, name and quality. Broken entries are skipped; a response
    that is not the voice list at all raises CatalogueError."""
    if not isinstance(data, dict) or not data:
        raise CatalogueError("the catalogue is not a list of voices")
    out = []
    for key, v in data.items():
        try:
            if not isinstance(v, dict) or not isinstance(key, str) or not _KEY.match(key):
                continue
            lang = v.get("language") or {}
            files = {}
            for rel, meta in (v.get("files") or {}).items():
                files[_safe_rel(rel)] = {"size_bytes": int((meta or {}).get("size_bytes") or 0),
                                         "md5_digest": str((meta or {}).get("md5_digest") or "").lower()}
            q = str(v.get("quality") or "")
            voice = PiperVoice(key=key, name=str(v.get("name") or key), family=str(lang.get("family") or key.split("_")[0]),
                               code=str(lang.get("code") or key.split("-")[0]), language=str(lang.get("name_english") or ""),
                               language_native=str(lang.get("name_native") or ""), country=str(lang.get("country_english") or ""),
                               quality=q if q in QUALITIES else (q or "medium"), num_speakers=int(v.get("num_speakers") or 1),
                               files=files)
            if not voice.model_rel or not voice.config_rel:
                continue
            # every file must sit in the voice's own folder
            folder = str(PurePosixPath(voice.model_rel).parent)
            if any(str(PurePosixPath(r).parent) not in (folder,) for r in (voice.config_rel, voice.card_rel) if r):
                continue
            out.append(voice)
        except (CatalogueError, TypeError, ValueError, AttributeError):
            continue
    if not out:
        raise CatalogueError("the catalogue has no usable voices")
    rank = {q: i for i, q in enumerate(QUALITIES)}
    return sorted(out, key=lambda x: (x.language or x.family, x.code, x.name, rank.get(x.quality, 9)))


def fetch_catalogue(session=None, offline_ok: bool = True) -> tuple[list[PiperVoice], float, bool]:
    """(voices, when the list was fetched, from the saved copy?). Reads the current list from upstream and saves it; if the
    internet can't be reached, the copy saved last time is used (offline_ok)."""
    import requests
    s = session or requests
    try:
        r = s.get(CATALOGUE_URL, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        voices = parse_catalogue(data)
        f = _cache_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f.name + ".part")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(f)
        return voices, time.time(), False
    except Exception as e:
        if offline_ok:
            cached = cached_catalogue()
            if cached:
                return cached, _cache_file().stat().st_mtime, True
        if isinstance(e, CatalogueError):
            raise
        raise CatalogueError(f"the voice list could not be read: {e.__class__.__name__}: {e}") from e


def cached_catalogue() -> list[PiperVoice]:
    f = _cache_file()
    try:
        return parse_catalogue(json.loads(f.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return []


# ---------------------------------------------------------------------- installed voices
def is_installed(v: PiperVoice) -> bool:
    m = v.model_path
    c = m.with_name(m.name + ".json")
    return m.is_file() and c.is_file() and m.stat().st_size > 0 and (
        not v.files[v.model_rel]["size_bytes"] or m.stat().st_size == v.files[v.model_rel]["size_bytes"])


def installed_models() -> dict[str, Path]:
    """{voice key: model path} of every downloaded voice (by its files — works without the catalogue)."""
    root = voice_root()
    out = {}
    if root.exists():
        for m in root.rglob("*.onnx"):
            if m.with_name(m.name + ".json").is_file() and m.stat().st_size > 0:
                out[m.stem] = m
    return dict(sorted(out.items()))


def model_path(key: str) -> Path | None:
    """The downloaded model of a voice key, or None."""
    if not key or not _KEY.match(key):
        return None
    return installed_models().get(key)


def config_of(model: Path) -> dict:
    try:
        return json.loads(Path(str(model) + ".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def voice_family(key: str) -> str:
    """de_DE-thorsten-high → de"""
    return key.split("_", 1)[0].split("-", 1)[0].lower()


def _md5(f: Path) -> str:
    h = hashlib.md5()                               # the checksum upstream publishes (integrity, not security)
    with open(f, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def install(v: PiperVoice, progress=lambda done, total: None, cancelled=lambda: False, session=None) -> Path:
    """Downloads the voice's files into its folder: each to a .part file, checked (size + MD5 from the catalogue), then
    moved in place — the model last, so a half-finished voice never counts as installed. Cancel or any error removes the
    .part files and leaves earlier voices untouched. Returns the model path."""
    import requests
    s = session or requests
    folder = v.folder
    root = voice_root().resolve()
    if root not in folder.resolve().parents:
        raise CatalogueError("the voice's folder is outside SubPlayer's voice folder")
    folder.mkdir(parents=True, exist_ok=True)
    order = [r for r in (v.config_rel, v.card_rel, v.model_rel) if r]
    total = sum(v.files[r]["size_bytes"] for r in order) or 0
    done = 0
    parts: list[tuple[Path, Path]] = []
    try:
        for rel in order:
            dest = voice_root() / Path(*PurePosixPath(rel).parts)
            tmp = dest.with_name(dest.name + ".part")
            want = v.files[rel]
            with s.get(f"{BASE}/{quote(rel, safe='/')}", stream=True, timeout=_TIMEOUT) as r:
                r.raise_for_status()
                if not total:
                    total = int(r.headers.get("Content-Length") or 0)
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(1 << 16):
                        if cancelled():
                            raise InterruptedError("cancelled")
                        if chunk:
                            fh.write(chunk)
                            done += len(chunk)
                            progress(done, total)
            parts.append((tmp, dest))
            size = tmp.stat().st_size
            if size == 0 or (want["size_bytes"] and size != want["size_bytes"]):
                raise IOError(f"{PurePosixPath(rel).name}: {size} bytes instead of {want['size_bytes']} — the download was cut off")
            if want["md5_digest"] and _md5(tmp) != want["md5_digest"]:
                raise IOError(f"{PurePosixPath(rel).name} is damaged (checksum mismatch) — try again")
            if rel.endswith(".onnx.json"):
                try:
                    json.loads(tmp.read_text(encoding="utf-8"))
                except ValueError as e:
                    raise IOError(f"the voice's settings file is not valid: {e}") from e
        for tmp, dest in parts:                              # config and card first, the model last
            tmp.replace(dest)
        parts.clear()
        return v.model_path
    finally:
        for tmp, _ in parts:
            tmp.unlink(missing_ok=True)
        for leftover in folder.glob("*.part"):
            leftover.unlink(missing_ok=True)


def remove(key: str) -> bool:
    """Deletes a downloaded voice (its folder under the voice folder only). True if something was removed."""
    m = model_path(key)
    if not m:
        return False
    root = voice_root().resolve()
    folder = m.parent.resolve()
    if root not in folder.parents:
        raise CatalogueError("refusing to delete outside SubPlayer's voice folder")
    shutil.rmtree(folder, ignore_errors=True)
    # tidy empty parents (name / locale / family), never the root
    p = folder.parent
    while p != root and root in p.parents and p.exists() and not any(p.iterdir()):
        p.rmdir()
        p = p.parent
    return not folder.exists()


# ---------------------------------------------------------------------- licence
def licence_of(card_text: str) -> str:
    """The licence line of a MODEL_CARD ("* License: CC BY 4.0") — or "" if the card names none."""
    for ln in (card_text or "").splitlines():
        m = re.match(r"^\W*licen[cs]e\W*[:=]\s*(.+?)\s*$", ln.strip(), re.I)
        if m:
            return m.group(1).strip(" *`")
    return ""


def card_text(v: PiperVoice, session=None) -> str:
    """The voice's MODEL_CARD: the downloaded copy, else read from upstream (small)."""
    if v.card_rel:
        local = voice_root() / Path(*PurePosixPath(v.card_rel).parts)
        if local.is_file():
            return local.read_text(encoding="utf-8", errors="replace")
        import requests
        s = session or requests
        r = s.get(f"{BASE}/{quote(v.card_rel, safe='/')}", timeout=_TIMEOUT)
        r.raise_for_status()
        return r.text[:20000]
    return ""
