"""
Sync document + private GitHub gist — the same format and merge rules as the Android app
(app/src/main/java/com/behrouz/subplayer/sync/SyncDoc.kt):

 - every word / sentence has a uid and an "updated" time (ms); the newer copy wins
 - a deletion is a tombstone (uid -> time); it wins over copies that are not newer; tombstones expire after 120 days
 - subtitles are keyed "<video key>|<lang>"; the newer one wins
 - progress: the later practice day wins; same day -> the larger numbers
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict

import requests

FILE = "subplayer-sync.json"
DESCRIPTION = "SubPlayer sync (private)"
TOKEN_PAGE = "https://github.com/settings/tokens/new?scopes=gist&description=SubPlayer%20sync"
VERSION = 1
TOMBSTONE_DAYS = 120

WORD_KEYS = ["uid", "text", "lemma", "article", "ipa", "english", "persian", "sentence", "video_name", "start_ms",
             "end_ms", "created", "reviews", "correct", "box", "due", "last_review", "lang", "updated"]
INT_KEYS = {"start_ms", "end_ms", "created", "reviews", "correct", "box", "due", "last_review", "updated"}


@dataclass
class SyncDoc:
    words: dict = field(default_factory=dict)      # uid -> word dict (WORD_KEYS)
    examples: dict = field(default_factory=dict)   # uid -> {uid, word_uid, de, en, fa, created, updated}
    deleted: dict = field(default_factory=dict)    # uid -> ms
    subs: dict = field(default_factory=dict)       # "key|lang" -> {key, lang, srt, updated}
    streak: int = 0
    last_day: int = -10
    today: int = 0


def now_ms() -> int:
    return int(time.time() * 1000)


def merge(a: SyncDoc, b: SyncDoc, now: int | None = None) -> SyncDoc:
    now = now_ms() if now is None else now
    deleted: dict = {}
    for src in (a.deleted, b.deleted):
        for k, v in src.items():
            deleted[k] = max(int(v), deleted.get(k, 0))
    deleted = {k: v for k, v in deleted.items() if now - v <= TOMBSTONE_DAYS * 86_400_000}

    words = {}
    for uid in set(a.words) | set(b.words):
        cands = [x for x in (a.words.get(uid), b.words.get(uid)) if x is not None]
        w = max(cands, key=lambda x: x["updated"])
        if deleted.get(uid, -1) >= w["updated"]:
            continue
        words[uid] = w
    examples = {}
    for uid in set(a.examples) | set(b.examples):
        cands = [x for x in (a.examples.get(uid), b.examples.get(uid)) if x is not None]
        e = max(cands, key=lambda x: x["updated"])
        if deleted.get(uid, -1) >= e["updated"] or e["word_uid"] not in words:
            continue
        examples[uid] = e
    subs = {}
    for k in set(a.subs) | set(b.subs):
        subs[k] = max([x for x in (a.subs.get(k), b.subs.get(k)) if x is not None], key=lambda x: x["updated"])
    if a.last_day > b.last_day:
        st, day, today = a.streak, a.last_day, a.today
    elif b.last_day > a.last_day:
        st, day, today = b.streak, b.last_day, b.today
    else:
        st, day, today = max(a.streak, b.streak), a.last_day, max(a.today, b.today)
    return SyncDoc(words, examples, deleted, subs, st, day, today)


def to_json(d: SyncDoc) -> str:
    return json.dumps({
        "app": "SubPlayer", "version": VERSION,
        "words": sorted(d.words.values(), key=lambda w: w["created"]),
        "examples": sorted(d.examples.values(), key=lambda e: e["created"]),
        "deleted": d.deleted,
        "subtitles": list(d.subs.values()),
        "progress": {"streak": d.streak, "last_day": d.last_day, "today": d.today},
    }, ensure_ascii=False)


def from_json(text: str) -> SyncDoc:
    if not text or not text.strip():
        return SyncDoc()
    o = json.loads(text)
    words = {}
    for w in o.get("words") or []:
        uid = w.get("uid") or ""
        if not uid:
            continue
        words[uid] = {k: (int(w.get(k) or 0) if k in INT_KEYS else str(w.get(k) or ("de" if k == "lang" else ""))) for k in WORD_KEYS}
    examples = {}
    for e in o.get("examples") or []:
        uid = e.get("uid") or ""
        if not uid:
            continue
        examples[uid] = {"uid": uid, "word_uid": e.get("word_uid") or "", "de": e.get("de") or "", "en": e.get("en") or "",
                         "fa": e.get("fa") or "", "created": int(e.get("created") or 0), "updated": int(e.get("updated") or 0)}
    deleted = {k: int(v) for k, v in (o.get("deleted") or {}).items()}
    subs = {}
    for s in o.get("subtitles") or []:
        sub = {"key": s.get("key") or "", "lang": s.get("lang") or "de", "srt": s.get("srt") or "", "updated": int(s.get("updated") or 0)}
        subs[sub["key"] + "|" + sub["lang"]] = sub
    p = o.get("progress") or {}
    return SyncDoc(words, examples, deleted, subs, int(p.get("streak", 0)), int(p.get("last_day", -10)), int(p.get("today", 0)))


class GistSync:
    """Finds / creates / reads / writes the one private gist that holds subplayer-sync.json."""
    API = "https://api.github.com"

    def __init__(self, token: str):
        self.s = requests.Session()
        self.s.headers.update({"Authorization": "Bearer " + token.strip(), "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "SubPlayer-Windows"})

    def _check(self, r):
        if r.status_code == 401:
            raise RuntimeError("GitHub token is wrong or expired")
        if r.status_code == 403:
            raise RuntimeError("GitHub refused (token needs the 'gist' scope, or rate limit)")
        r.raise_for_status()
        return r

    def find(self) -> str | None:
        page = 1
        while page <= 10:
            r = self._check(self.s.get(f"{self.API}/gists", params={"per_page": 100, "page": page}, timeout=30))
            items = r.json()
            for g in items:
                if FILE in (g.get("files") or {}):
                    return g["id"]
            if len(items) < 100:
                return None
            page += 1
        return None

    def create(self, content: str) -> str:
        r = self._check(self.s.post(f"{self.API}/gists", json={"description": DESCRIPTION, "public": False,
                                                                "files": {FILE: {"content": content}}}, timeout=60))
        return r.json()["id"]

    def read(self, gist_id: str) -> str:
        r = self._check(self.s.get(f"{self.API}/gists/{gist_id}", timeout=60))
        f = (r.json().get("files") or {}).get(FILE)
        if not f:
            return ""
        if f.get("truncated"):
            return self._check(self.s.get(f["raw_url"], timeout=120)).text
        return f.get("content") or ""

    def write(self, gist_id: str, content: str):
        self._check(self.s.patch(f"{self.API}/gists/{gist_id}", json={"files": {FILE: {"content": content}}}, timeout=60))
