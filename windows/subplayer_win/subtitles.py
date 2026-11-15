"""Subtitles: .srt/.vtt read/write, line lookup and complete sentences (same rules as the Android app)."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Cue:
    start_ms: int
    end_ms: int
    text: str


_TIME = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[,.](\d{1,3})")


def _ms(t: str) -> int:
    m = _TIME.search(t)
    if not m:
        raise ValueError(t)
    h = int(m.group(1) or 0)
    return ((h * 60 + int(m.group(2))) * 60 + int(m.group(3))) * 1000 + int(m.group(4).ljust(3, "0"))


def parse(text: str) -> list[Cue]:
    text = text.replace("\r", "").lstrip("﻿")
    cues = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l for l in block.split("\n") if l.strip()]
        for i, l in enumerate(lines):
            if "-->" in l:
                a, b = l.split("-->", 1)
                try:
                    s, e = _ms(a), _ms(b)
                except ValueError:
                    break
                body = "\n".join(re.sub(r"<[^>]+>", "", x).strip() for x in lines[i + 1:]).strip()
                if body:
                    cues.append(Cue(s, e, body))
                break
    cues.sort(key=lambda c: c.start_ms)
    return cues


def fmt_time(ms: int) -> str:
    ms = max(0, int(ms))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write(cues: list[Cue]) -> str:
    return "".join(f"{i}\n{fmt_time(c.start_ms)} --> {fmt_time(c.end_ms)}\n{c.text}\n\n" for i, c in enumerate(cues, 1))


def index_at(cues: list[Cue], pos: int) -> int:
    lo, hi, found = 0, len(cues) - 1, -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if cues[mid].start_ms <= pos:
            found, lo = mid, mid + 1
        else:
            hi = mid - 1
    return found if found >= 0 and pos < cues[found].end_ms else -1


def index_before(cues: list[Cue], pos: int) -> int:
    lo, hi, found = 0, len(cues) - 1, -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if cues[mid].start_ms <= pos:
            found, lo = mid, mid + 1
        else:
            hi = mid - 1
    return found


def ends_sentence(text: str) -> bool:
    t = text.rstrip().rstrip("\"“”»«')")
    return t.endswith((".", "!", "?", "…", ":"))


def has_punctuation(cues: list[Cue]) -> bool:
    n = sum(1 for c in cues if ends_sentence(c.text))
    return n > 0 and n * 5 >= len(cues)


def sentence_range(cues: list[Cue], i: int, max_lines: int = 4, max_gap: int = 1500) -> tuple[int, int]:
    if not (0 <= i < len(cues)) or not has_punctuation(cues):
        return i, i
    a = b = i
    while a > 0 and b - a + 1 < max_lines and not ends_sentence(cues[a - 1].text) and cues[a].start_ms - cues[a - 1].end_ms <= max_gap:
        a -= 1
    while b < len(cues) - 1 and b - a + 1 < max_lines and not ends_sentence(cues[b].text) and cues[b + 1].start_ms - cues[b].end_ms <= max_gap:
        b += 1
    return a, b


def sentence_text(cues: list[Cue], a: int, b: int) -> str:
    return " ".join(cues[k].text.replace("\n", " ").strip() for k in range(a, b + 1))


def wrap(text: str, width: int = 42) -> str:
    """Two balanced lines for long subtitles."""
    t = " ".join(text.split())
    if len(t) <= width:
        return t
    words, best, best_d = t.split(" "), t, 10 ** 9
    for k in range(1, len(words)):
        l1, l2 = " ".join(words[:k]), " ".join(words[k:])
        d = abs(len(l1) - len(l2))
        if d < best_d:
            best, best_d = l1 + "\n" + l2, d
    return best


def from_segments(segs, max_chars: int = 84) -> list[Cue]:
    """[(start_s, end_s, text, words[(start_s, end_s, word)] or None)] -> cues no longer than ~2 lines."""
    cues = []
    for s, e, text, words in segs:
        text = " ".join(text.split())
        if not text or _hallucination(text):
            continue
        if len(text) <= max_chars or not words:
            cues.append(Cue(int(s * 1000), int(e * 1000), wrap(text)))
            continue
        cur, cs = [], None
        for ws, we, w in words:
            w = w.strip()
            if not w:
                continue
            if cs is None:
                cs = ws
            cur.append(w)
            line = " ".join(cur)
            if len(line) >= max_chars * 0.8 and (w[-1] in ".!?,;:" or len(line) >= max_chars):
                cues.append(Cue(int(cs * 1000), int(we * 1000), wrap(line)))
                cur, cs = [], None
        if cur:
            cues.append(Cue(int(cs * 1000), int(e * 1000), wrap(" ".join(cur))))
    # no overlaps
    for k in range(len(cues) - 1):
        if cues[k].end_ms > cues[k + 1].start_ms:
            cues[k].end_ms = max(cues[k].start_ms + 300, cues[k + 1].start_ms)
    return cues


_HALL = re.compile(r"(untertitel (der|im auftrag|von)|amara\.org|zdf|vielen dank fürs zuschauen|subtitles by|thanks for watching)", re.I)


def _hallucination(text: str) -> bool:
    return bool(_HALL.search(text)) and len(text) < 80


TOKEN = re.compile(r"[\w][\w\-'’]*", re.UNICODE)


def tokens(text: str) -> list[tuple[int, int, str]]:
    """Clickable words with their positions."""
    return [(m.start(), m.end(), m.group(0)) for m in TOKEN.finditer(text) if not m.group(0).isdigit()]


def video_key(name: str) -> str:
    """Same key on every device for the same video file name (used to sync subtitles)."""
    base = name.rsplit(".", 1)[0] if "." in name else name
    return _key(base)


def _key(base: str) -> str:
    # Kotlin: replace(Regex("[^\\p{L}\\p{N}._-]+"), "_").take(60)
    out, prev_bad = [], False
    for ch in base:
        ok = ch.isalpha() or ch.isnumeric() or ch in "._-"
        if ok:
            out.append(ch)
            prev_bad = False
        elif not prev_bad:
            out.append("_")
            prev_bad = True
    return "".join(out)[:60]


# ------------------------------------------------------------------ broadcaster subtitles (TTML / EBU-TT, WebVTT)
_CLOCK = re.compile(r"^(\d+):(\d{2}):(\d{2})(?:([.,]\d+)|:(\d+(?:\.\d+)?))?$")
_OFFSET = re.compile(r"^(\d+(?:\.\d+)?)(h|ms|m|s|f|t)$")


def _ttml_time(v: str, fps: float, tick_rate: float) -> int:
    v = (v or "").strip()
    m = _CLOCK.match(v)
    if m:
        h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
        ms = (h * 3600 + mi * 60 + s) * 1000
        if m.group(4):
            ms += int(round(float("0" + m.group(4).replace(",", ".")) * 1000))
        elif m.group(5):
            ms += int(round(float(m.group(5)) / fps * 1000))
        return ms
    m = _OFFSET.match(v)
    if m:
        n, unit = float(m.group(1)), m.group(2)
        return int(round(n * {"h": 3_600_000, "m": 60_000, "s": 1000, "ms": 1}.get(unit, 0) if unit in ("h", "m", "s", "ms")
                         else (n / fps * 1000 if unit == "f" else n / tick_rate * 1000)))
    raise ValueError(f"time {v!r}")


def parse_ttml(xml_text: str) -> list[Cue]:
    """TTML / EBU-TT-D as used by ARD and ZDF. Line breaks kept; colours and styles dropped; the 10:00:00 timecode start
    that broadcast subtitles often use is removed so the first line lines up with the video."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)

    def local(tag):
        return tag.rsplit("}", 1)[-1]

    def attr(el, name):
        for k, v in el.attrib.items():
            if local(k) == name:
                return v
        return None

    fps = float(attr(root, "frameRate") or 25)
    mult = (attr(root, "frameRateMultiplier") or "").split()          # e.g. "1000 1001" (NTSC)
    if len(mult) == 2 and float(mult[1]):
        fps *= float(mult[0]) / float(mult[1])
    tick_rate = float(attr(root, "tickRate") or 10_000_000)

    def text_of(el) -> str:
        parts = [el.text or ""]
        for ch in el:
            parts.append("\n" if local(ch.tag) == "br" else text_of(ch))
            parts.append(ch.tail or "")
        return "".join(parts)

    cues = []
    for p in root.iter():
        if local(p.tag) != "p":
            continue
        b, e, dur = attr(p, "begin"), attr(p, "end"), attr(p, "dur")
        if b is None:
            continue
        try:
            s = _ttml_time(b, fps, tick_rate)
            en = _ttml_time(e, fps, tick_rate) if e else s + _ttml_time(dur or "3s", fps, tick_rate)
        except ValueError:
            continue
        body = "\n".join(" ".join(l.split()) for l in text_of(p).split("\n"))
        body = "\n".join(l for l in body.split("\n") if l).strip()
        if body and en > s:
            cues.append(Cue(s, en, body))
    cues.sort(key=lambda c: c.start_ms)
    if cues and cues[0].start_ms >= 36_000_000:          # broadcast timecode that starts at 10:00:00
        for c in cues:
            c.start_ms -= 36_000_000
            c.end_ms -= 36_000_000
    return cues


def parse_any(text: str) -> list[Cue]:
    """.srt, .vtt or TTML/XML — whatever the text is."""
    t = text.lstrip("﻿ \r\n\t")
    if t.startswith("<"):
        return parse_ttml(t)
    return parse(text)


_DE = set("der die das und ist nicht ich sie wir ein eine es auf mit den dem zu von für sich auch noch wie aber oder wenn dass".split())
_EN = set("the and is not you we it of to in that for on with this are was be have he she they but or if".split())


def guess_lang(cues: list[Cue]) -> str:
    """'de' or 'en' from the most common little words."""
    words = re.findall(r"[a-zäöüß]+", " ".join(c.text for c in cues[:200]).lower())
    de = sum(w in _DE for w in words)
    en = sum(w in _EN for w in words)
    return "en" if en > de * 1.3 else "de"
