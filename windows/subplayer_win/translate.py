"""Online sentence translation (Google's free endpoint, then MyMemory) — needs internet."""
from __future__ import annotations

import requests


def translate(text: str, src: str, dst: str) -> tuple[str, str]:
    errors = []
    try:
        r = requests.get("https://translate.googleapis.com/translate_a/single",
                         params={"client": "gtx", "sl": src, "tl": dst, "dt": "t", "q": text}, timeout=15)
        r.raise_for_status()
        out = "".join(p[0] for p in r.json()[0] if p and p[0]).strip()
        if out:
            return out, "Google Translate"
    except Exception as e:
        errors.append(f"Google: {e}")
    try:
        r = requests.get("https://api.mymemory.translated.net/get", params={"q": text, "langpair": f"{src}|{dst}"}, timeout=15)
        out = (r.json().get("responseData") or {}).get("translatedText", "").strip()
        if out:
            return out, "MyMemory"
    except Exception as e:
        errors.append(f"MyMemory: {e}")
    raise IOError("No connection to a translation service (" + "; ".join(errors) + ")")
