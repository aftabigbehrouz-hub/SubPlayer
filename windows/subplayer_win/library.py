"""
Your video library: every video on this PC that has subtitles (SubPlayer's own subtitle folder, plus .srt files next to
videos in your video folders). Used to show where else a word is used, and for the video study page.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import subtitles

VIDEO_EXT = (".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".wmv", ".mpg", ".mpeg", ".ts", ".mp3", ".m4a", ".ogg", ".opus", ".wav")


@dataclass
class Item:
    srt: Path
    lang: str
    video: str = ""            # path of the video file, if found on this PC
    name: str = ""             # what the user sees

    def cues(self) -> list:
        try:
            return subtitles.parse(self.srt.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return []


@dataclass
class Use:
    item: Item
    index: int
    start_ms: int
    end_ms: int
    text: str
    spans: list = field(default_factory=list)      # [(start, end)] of the word in text


def video_folders(settings: dict) -> list[Path]:
    home = Path.home()
    out = [Path(p) for p in settings.get("video_folders", []) if p]
    for p in (home / "Videos", home / "Videos" / "SubPlayer", home / "Downloads"):
        if p not in out:
            out.append(p)
    for r in settings.get("recents", []):
        if isinstance(r, dict) and r.get("path"):
            d = Path(r["path"]).parent
            if d not in out:
                out.append(d)
    return [p for p in out if p.is_dir()]


def scan(settings: dict, subs_dir: Path, max_files: int = 4000) -> list[Item]:
    """All subtitled videos (SubPlayer's subtitles first, then .srt beside videos)."""
    videos: dict[str, str] = {}
    for folder in video_folders(settings):
        try:
            for root, dirs, files in os.walk(folder):
                dirs[:] = [d for d in dirs if not d.startswith((".", "$"))][:200]
                for f in files:
                    if f.lower().endswith(VIDEO_EXT):
                        videos.setdefault(subtitles.video_key(f), os.path.join(root, f))
                if root.count(os.sep) - str(folder).count(os.sep) >= 3:
                    dirs[:] = []
        except OSError:
            continue
    for r in settings.get("recents", []):
        if isinstance(r, dict) and r.get("path"):
            videos.setdefault(subtitles.video_key(Path(r["path"]).name), r["path"])
    items, seen = [], set()
    if subs_dir.is_dir():
        for f in sorted(subs_dir.glob("*.srt")):
            m = re.match(r"^(.*)\.(de|en)\.srt$", f.name)
            if not m:
                continue
            key, lang = m.group(1), m.group(2)
            vid = videos.get(key, "")
            items.append(Item(f, lang, vid, Path(vid).name if vid else key))
            seen.add((key, lang))
    for key, vid in videos.items():
        base = Path(vid)
        for cand in (base.with_suffix(".srt"), base.with_suffix(".de.srt"), base.with_suffix(".en.srt")):
            if cand.exists() and len(items) < max_files:
                lang = "en" if cand.name.endswith(".en.srt") else "de"
                if (key, lang) not in seen:
                    if not cand.name.endswith((".de.srt", ".en.srt")):
                        lang = subtitles.guess_lang(subtitles.parse(cand.read_text(encoding="utf-8", errors="replace"))[:80])
                    items.append(Item(cand, lang, vid, base.name))
                    seen.add((key, lang))
    return items


def word_forms(word: str, dictionary=None) -> set[str]:
    """The word and, through the dictionary, its other forms (warum; gehen → geht, ging, gegangen…)."""
    w = word.strip().lower()
    forms = {w}
    if dictionary is None:
        return forms
    try:
        rows = dictionary.db.execute("SELECT DISTINCT l.id FROM lookup l JOIN entry e ON e.id=l.id WHERE l.key=? AND e.pos!='name' "
                                     "LIMIT 6", (w,)).fetchall()
        ids = [r[0] for r in rows]
        lemmas = [r[0].lower() for r in dictionary.db.execute(
            f"SELECT lemma FROM entry WHERE id IN ({','.join('?' * len(ids))})", ids)] if ids else []
        # only the entries whose base word is this word or the word's base word (not every homograph)
        base = ""
        try:
            ranked = [e for e in dictionary.lookup(word) if e.pos != "name"]
            base = ranked[0].lemma.lower() if ranked else ""
        except Exception:
            pass
        keep = [i for i, lem in zip(ids, lemmas) if lem in (w, base)]
        if keep:
            for (k,) in dictionary.db.execute(f"SELECT key FROM lookup WHERE id IN ({','.join('?' * len(keep))})", keep):
                if k and " " not in k and max(2, len(w) // 2) <= len(k) <= 40:
                    forms.add(k.lower())
    except Exception:
        pass
    return forms


TOKEN = re.compile(r"[^\W\d_][\w\-'’]*", re.UNICODE)


def find_uses(word: str, lang: str, items: list[Item], dictionary=None, limit: int = 400,
              cancelled=lambda: False) -> tuple[list[Use], int]:
    """Every subtitle line (in the given language) that contains the word or one of its forms; (uses, files searched)."""
    phrase = " " in word.strip()
    forms = {word.strip().lower()} if phrase else word_forms(word, dictionary)
    out, n = [], 0
    for it in items:
        if it.lang != lang:
            continue
        if cancelled():
            break
        n += 1
        for k, c in enumerate(it.cues()):
            low = c.text.lower()
            if phrase:
                i = low.find(next(iter(forms)))
                spans = [(i, i + len(word.strip()))] if i >= 0 else []
            else:
                spans = [(m.start(), m.end()) for m in TOKEN.finditer(c.text) if m.group(0).lower().strip("'’-") in forms]
            if spans:
                out.append(Use(it, k, c.start_ms, c.end_ms, c.text, spans))
                if len(out) >= limit:
                    return out, n
    return out, n


def vocabulary(cues: list, lang: str, levels, dictionary=None) -> list[tuple[str, int, int]]:
    """[(word, count, level)] of a video's text, most frequent first. A capital at the start of a line or sentence doesn't
    make a German word a noun: such words count as lowercase unless they only ever appear capitalised mid-sentence."""
    counts: dict[str, int] = {}
    lower_seen: set = set()
    mid_capital: set = set()
    for c in cues:
        prev_end = True
        for m in TOKEN.finditer(c.text):
            t = m.group(0).strip("'’-")
            before = c.text[:m.start()].rstrip()
            sentence_start = prev_end or not before or before[-1:] in ".!?:…\"„“»«"
            prev_end = False
            if len(t) < 2:
                continue
            k = t.lower()
            counts[k] = counts.get(k, 0) + 1
            if t[:1].islower():
                lower_seen.add(k)
            elif not sentence_start:
                mid_capital.add(k)
    out = []
    for k, n in counts.items():
        if lang == "de" and k in mid_capital and k not in lower_seen:
            shown = k[:1].upper() + k[1:]                # a German noun (capitalised inside sentences)
        elif lang == "en" and k in mid_capital and k not in lower_seen:
            shown = k[:1].upper() + k[1:]                # a name
        else:
            shown = k
        out.append((shown, n, levels.level(shown, lang, dictionary)))
    return sorted(out, key=lambda x: (-x[1], x[0].lower()))
