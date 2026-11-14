"""
Per-PC activation, the same scheme as the Android app.

 - Every PC shows a DEVICE CODE (from Windows' MachineGuid).
 - The owner turns "device code + buyer name" into an ACTIVATION CODE with his private key
   (licence-tool/make_activation_code.py, or Settings > Owner tools on the phone).
 - Activation code = BASE32(payload) "." BASE32(ECDSA P-256 / SHA-256 signature), payload = "SP1|<device>|<name>".
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from . import paths

PUBLIC_KEY = ("MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE8Y3bSq60qPtp/kJ28JJaSeUcjoAjSGSw1+yIH7Xs55Xb9Xx2YHpWAUSYMBBa0JR45Oo55RV0Tm9M7n53XKRE4g==")
TRIAL_DAYS = 10
SELLER_TELEGRAM = "Bgilone"
DAY = 24 * 60 * 60 * 1000


def b32encode(data: bytes) -> str:
    return base64.b32encode(data).decode().rstrip("=")


def b32decode(text: str) -> bytes:
    t = text.strip().upper().rstrip("=")
    return base64.b32decode(t + "=" * (-len(t) % 8))


def code_for(machine_id: str) -> str:
    """10 characters shown as XXXXX-XXXXX (same derivation as Android, with a "win:" prefix)."""
    h = hashlib.sha256(("SubPlayer-device:win:" + machine_id).encode("utf-8")).digest()
    b = b32encode(h)[:10]
    return b[:5] + "-" + b[5:]


def machine_id() -> str:
    try:
        import winreg  # type: ignore
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                            winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)) as k:
            return str(winreg.QueryValueEx(k, "MachineGuid")[0])
    except Exception:
        # not Windows (or no access): a stable id kept in the app folder
        f = paths.data_dir() / "machine-id.txt"
        if not f.exists():
            f.write_text(str(uuid.uuid4()), encoding="utf-8")
        return f.read_text(encoding="utf-8").strip()


def device_code() -> str:
    return code_for(machine_id())


def payload(device: str, name: str) -> str:
    return f"SP1|{device.strip().upper()}|{name.strip()}"


def verify(code: str, device: str, public_key: str = PUBLIC_KEY) -> str | None:
    """The buyer's name if the code is genuine and made for [device]; otherwise None."""
    try:
        clean = "".join(code.split()).upper()
        parts = clean.split(".")
        if len(parts) != 2:
            return None
        p, sig = b32decode(parts[0]), b32decode(parts[1])
        pub = serialization.load_der_public_key(base64.b64decode(public_key))
        pub.verify(sig, p, ec.ECDSA(hashes.SHA256()))
        f = p.decode("utf-8").split("|", 2)
        if len(f) == 3 and f[0] == "SP1" and f[1] == device.strip().upper():
            return f[2]
    except (InvalidSignature, ValueError, UnicodeDecodeError, Exception):
        return None
    return None


def create(private_key_b64: str, device: str, name: str) -> str:
    key = serialization.load_der_private_key(base64.b64decode("".join(private_key_b64.split())), password=None)
    p = payload(device, name).encode("utf-8")
    return b32encode(p) + "." + b32encode(key.sign(p, ec.ECDSA(hashes.SHA256())))


def trial_days_left(start: int, now: int, last_seen: int, days: int = TRIAL_DAYS) -> int:
    """Same rule as Android: clock turned back more than a day → ended."""
    if now + DAY < last_seen:
        return 0
    end = start + days * DAY
    if now >= end:
        return 0
    return max(1, min(days, (end - now + DAY - 1) // DAY))


class LicenceState:
    """Stored in licence.json in the app folder."""

    def __init__(self):
        self.file = paths.data_dir() / "licence.json"
        try:
            self.d = json.loads(self.file.read_text(encoding="utf-8"))
        except Exception:
            self.d = {}
        self.device = device_code()

    def _save(self):
        self.file.write_text(json.dumps(self.d), encoding="utf-8")

    @property
    def holder(self) -> str | None:
        c = self.d.get("code")
        return verify(c, self.device) if c else None

    def activate(self, code: str) -> str | None:
        name = verify(code, self.device)
        if name is not None:
            self.d["code"] = "".join(code.split())
            self._save()
        return name

    def check_trial(self) -> int:
        now = int(time.time() * 1000)
        start = self.d.get("trial_start") or now
        last = self.d.get("last_seen", 0)
        left = trial_days_left(start, now, last)
        self.d["trial_start"] = start
        if now > last:
            self.d["last_seen"] = now
        self._save()
        return left
