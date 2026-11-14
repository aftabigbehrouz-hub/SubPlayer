"""Files the app downloads once, from this app's GitHub release, each checked against its SHA-256 fingerprint."""
from __future__ import annotations

import hashlib
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

from . import paths

BASE = "https://github.com/aftabigbehrouz-hub/SubPlayer/releases/download/data-v1/"


@dataclass
class Asset:
    id: str
    label: str
    file: str
    size_mb: int
    sha256: str
    folder: str          # extracted into <assets>/<folder>
    result: str          # ready file/folder relative to <assets>
    fallback: str | None = None

    @property
    def url(self):
        return BASE + self.file


DICT_DE = Asset("dict-de", "German dictionary", "dict-de-v1.zip", 38,
                "7991bd05f238b6697aa6eddc4a9ec710e537545cb6a2e605196370a6344babc7", "dict", "dict/dict.db")
DICT_EN = Asset("dict-en", "English dictionary", "dict-en-v1.zip", 19,
                "36ce4981ee0001d651bc451a0ebfca59eefab7d7f911815ef22f35f77be43ea3", "dict-en", "dict-en/dict.db")
# faster-whisper models (mirrored from Hugging Face by .github/workflows/data-win.yml)
FW_BASE = Asset("fw-base", "Whisper Base (fast)", "fw-base-v1.zip", 141, "405ec612c4a7e195aa1387a93646e928940e8ff9821e5af1f3550b9622717d70", "", "fw-base")
FW_SMALL = Asset("fw-small", "Whisper Small (accurate)", "fw-small-v1.zip", 464, "ef7c8f7d26200beafda1f69a1e8c13739fbbef423be01a783fc98abbe57976d5", "", "fw-small")
FW_TURBO = Asset("fw-turbo", "Whisper Large-v3 Turbo (best)", "fw-turbo-v1.zip", 1547, "9e26e965991680da8649b1afbc679b5908cd78d935a016fefeb9f05c044ace2c", "", "fw-turbo")


def root() -> Path:
    return paths.sub_dir("assets")


def ready_path(a: Asset) -> Path:
    return root() / a.result


def is_ready(a: Asset) -> bool:
    p = ready_path(a)
    return p.exists() and (p.is_file() or any(p.iterdir()))


def sha256_of(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure(a: Asset, progress=lambda done, total: None, cancelled=lambda: False) -> Path:
    """Downloads (resuming a partial file), checks the fingerprint, unzips. Returns the ready path."""
    if is_ready(a):
        return ready_path(a)
    tmp = root() / (a.file + ".part")
    urls = [a.url] + ([a.fallback] if a.fallback else [])
    last_err = None
    for url in urls:
        try:
            have = tmp.stat().st_size if tmp.exists() else 0
            headers = {"Range": f"bytes={have}-"} if have else {}
            with requests.get(url, headers=headers, stream=True, timeout=60) as r:
                if r.status_code == 416:      # already complete
                    pass
                else:
                    r.raise_for_status()
                    if have and r.status_code != 206:
                        have = 0
                    total = have + int(r.headers.get("Content-Length") or 0)
                    with open(tmp, "ab" if have else "wb") as fh:
                        done = have
                        for chunk in r.iter_content(1 << 16):
                            if cancelled():
                                raise InterruptedError("cancelled")
                            fh.write(chunk)
                            done += len(chunk)
                            progress(done, total)
            got = sha256_of(tmp)
            if not a.sha256.startswith("SHA_") and got != a.sha256:
                tmp.unlink(missing_ok=True)
                raise IOError(f"{a.label}: the downloaded file is damaged or was changed (fingerprint mismatch). Try again.")
            break
        except InterruptedError:
            raise
        except Exception as e:  # try the next source
            last_err = e
    else:
        raise IOError(f"Download of {a.label} failed: {last_err}")
    dest = root() / a.folder if a.folder else root()
    if zipfile.is_zipfile(tmp):
        with zipfile.ZipFile(tmp) as z:
            for m in z.infolist():
                target = (dest / m.filename).resolve()
                if not str(target).startswith(str(dest.resolve())):
                    raise IOError("bad zip entry")
            z.extractall(dest)
        tmp.unlink(missing_ok=True)
    else:
        dest.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp), str(ready_path(a)))
    return ready_path(a)
