"""Dynamic catalogue and safe on-demand installer for Piper voice models.

The catalogue is read from the Hugging Face tree API at runtime. Model files are
stored under the user's SubPlayer data directory, never beside the executable.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote

import requests

from . import paths

REPOSITORY = "rhasspy/piper-voices"
API = f"https://huggingface.co/api/models/{REPOSITORY}/tree/main"
RESOLVE = f"https://huggingface.co/{REPOSITORY}/resolve/main"
QUALITIES = ("x_low", "low", "medium", "high")
_TIMEOUT = (15, 90)


@dataclass(frozen=True)
class PiperModel:
    model_id: str
    language: str
    locale: str
    name: str
    quality: str
    model_path: str
    config_path: str
    size_bytes: int = 0

    @property
    def label(self) -> str:
        return f"{self.name} — {self.locale} — {self.quality}"

    @property
    def installed_path(self) -> Path:
        return voice_root() / self.model_path


def voice_root() -> Path:
    return paths.sub_dir("assets") / "piper" / "voices"


def _safe_relative(value: str) -> Path:
    p = Path(value)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError("Unsafe model path in remote catalogue")
    return p


def _tree(session: requests.Session) -> list[dict]:
    """Read all pages of the HF tree API; never silently return a partial catalogue."""
    out: list[dict] = []
    params = {"recursive": "true", "expand": "true", "limit": 1000}
    while True:
        response = session.get(API, params=params, timeout=_TIMEOUT)
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise ValueError("Unexpected Piper catalogue response")
        out.extend(page)
        link = response.links.get("next", {}).get("url")
        if not link:
            break
        # The next URL is supplied by Hugging Face; keep requests on its host.
        if not link.startswith("https://huggingface.co/"):
            raise ValueError("Unexpected catalogue pagination host")
        response = session.get(link, timeout=_TIMEOUT)
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise ValueError("Unexpected Piper catalogue page")
        out.extend(page)
        if not response.links.get("next"):
            break
        params = {}
        API_next = response.links["next"]["url"]
        while API_next:
            response = session.get(API_next, timeout=_TIMEOUT)
            response.raise_for_status()
            page = response.json()
            if not isinstance(page, list):
                raise ValueError("Unexpected Piper catalogue page")
            out.extend(page)
            API_next = response.links.get("next", {}).get("url")
    return out


def fetch_catalogue(session: requests.Session | None = None) -> list[PiperModel]:
    """Discover all .onnx voices with their matching JSON config from upstream."""
    own = session is None
    s = session or requests.Session()
    try:
        entries = _tree(s)
    finally:
        if own:
            s.close()

    files = {str(x.get("path", "")): x for x in entries if x.get("type") == "file"}
    models: list[PiperModel] = []
    for path, meta in files.items():
        if not path.endswith(".onnx"):
            continue
        # Piper's repository layout is <family>/<locale>/<voice>/<quality>/<file>.
        parts = path.split("/")
        if len(parts) < 5 or parts[-2] not in QUALITIES:
            continue
        config = path + ".json"
        if config not in files:
            continue
        locale = parts[1]
        name = parts[2]
        quality = parts[-2]
        models.append(PiperModel(
            model_id=path[:-5],
            language=parts[0],
            locale=locale,
            name=name,
            quality=quality,
            model_path=path,
            config_path=config,
            size_bytes=int(meta.get("size") or 0),
        ))
    return sorted(models, key=lambda m: (m.language, m.locale, m.name, QUALITIES.index(m.quality)))


def installed_models() -> list[Path]:
    root = voice_root()
    return sorted(p for p in root.rglob("*.onnx") if p.with_suffix(p.suffix + ".json").is_file()) if root.exists() else []


def install_model(model: PiperModel, progress=lambda done, total: None, cancelled=lambda: False,
                  session: requests.Session | None = None) -> Path:
    """Download model + config atomically; resume is intentionally not attempted on unknown servers."""
    root = voice_root()
    target = root / _safe_relative(model.model_path)
    config_target = root / _safe_relative(model.config_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    own = session is None
    s = session or requests.Session()
    try:
        for relative, destination in ((model.model_path, target), (model.config_path, config_target)):
            if destination.exists() and destination.stat().st_size > 0:
                continue
            url = RESOLVE + "/" + quote(relative, safe="/")
            tmp = destination.with_name(destination.name + ".part")
            try:
                with s.get(url, stream=True, timeout=_TIMEOUT) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("Content-Length") or 0)
                    done = 0
                    with tmp.open("wb") as fh:
                        for chunk in response.iter_content(1024 * 256):
                            if cancelled():
                                raise InterruptedError("Download cancelled")
                            if chunk:
                                fh.write(chunk)
                                done += len(chunk)
                                progress(done, total)
                if tmp.stat().st_size == 0:
                    raise IOError(f"Empty Piper file: {relative}")
                tmp.replace(destination)
            except Exception:
                tmp.unlink(missing_ok=True)
                raise
    finally:
        if own:
            s.close()
    return target


def remove_model(model_path: str) -> bool:
    """Remove only a model under the managed Piper directory, never arbitrary paths."""
    root = voice_root().resolve()
    model = (root / _safe_relative(model_path)).resolve()
    if root not in model.parents or model.suffix != ".onnx":
        raise ValueError("Refusing to remove a path outside the Piper voice directory")
    config = model.with_suffix(model.suffix + ".json")
    existed = model.exists()
    model.unlink(missing_ok=True)
    config.unlink(missing_ok=True)
    return existed


def model_config(model_path: str | Path) -> dict:
    p = Path(model_path)
    config = p.with_suffix(p.suffix + ".json")
    return json.loads(config.read_text(encoding="utf-8")) if config.is_file() else {}


def model_fingerprint(model_path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(model_path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
