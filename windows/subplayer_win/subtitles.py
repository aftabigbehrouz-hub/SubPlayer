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
