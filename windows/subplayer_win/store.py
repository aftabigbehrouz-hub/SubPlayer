"""My Words: the same SQLite layout as the Android app (words.db v3), review steps and daily progress."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, replace

from . import paths
from .sync import SyncDoc

INTERVAL_DAYS = [0, 1, 2, 4, 7, 15, 30, 60]
DAY = 24 * 60 * 60 * 1000
AGAIN_MS = 10 * 60 * 1000


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class SavedWord:
    text: str
    lemma: str
    sentence: str
    video_uri: str = ""
    video_name: str = ""
    start_ms: int = -1
    end_ms: int = -1
    article: str = ""
    ipa: str = ""
    english: str = ""
    persian: str = ""
    created: int = field(default_factory=now_ms)
    reviews: int = 0
    correct: int = 0
    box: int = 0
    due: int = field(default_factory=now_ms)
    last_review: int = 0
    lang: str = "de"
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))
    updated: int = field(default_factory=now_ms)
    id: int = 0


@dataclass
class Example:
    de: str                 # the sentence in the language being learnt
    en: str = ""            # its translation (English, or German for English words)
    fa: str = ""
    id: int = 0
    word_id: int = 0
    created: int = field(default_factory=now_ms)
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))
    updated: int = field(default_factory=now_ms)


def review(w: SavedWord, got_it: bool, now: int) -> SavedWord:
    box = min(w.box + 1, len(INTERVAL_DAYS) - 1) if got_it else 0
    due = now + INTERVAL_DAYS[box] * DAY if got_it else now + AGAIN_MS
    return replace(w, reviews=w.reviews + 1, correct=w.correct + (1 if got_it else 0), box=box, due=due, last_review=now)


def due_label(due: int, now: int) -> str:
    d = due - now
    if d <= 0:
        return "due now"
    if d < 3_600_000:
        return f"in {d // 60000 + 1} min"
    if d < DAY:
        return f"in {d // 3_600_000 + 1} h"
    return f"in {(d + DAY // 2) // DAY} days"


WORD_COLS = ["text", "lemma", "article", "ipa", "english", "persian", "sentence", "video_uri", "video_name", "start_ms",
             "end_ms", "created", "reviews", "correct", "box", "due", "last_review", "lang", "uid", "updated"]


class WordStore:
    def __init__(self, file=None):
        self.db = sqlite3.connect(str(file or paths.data_dir() / "words.db"), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS words(
                id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, lemma TEXT, article TEXT, ipa TEXT,
                english TEXT, persian TEXT, sentence TEXT, video_uri TEXT, video_name TEXT,
                start_ms INTEGER, end_ms INTEGER, created INTEGER, reviews INTEGER, correct INTEGER,
                box INTEGER, due INTEGER, last_review INTEGER, lang TEXT DEFAULT 'de', uid TEXT, updated INTEGER);
            CREATE INDEX IF NOT EXISTS words_due ON words(due);
            CREATE TABLE IF NOT EXISTS examples(id INTEGER PRIMARY KEY AUTOINCREMENT, word_id INTEGER, de TEXT, en TEXT,
                fa TEXT, created INTEGER, uid TEXT, updated INTEGER);
            CREATE INDEX IF NOT EXISTS examples_word ON examples(word_id);
            CREATE TABLE IF NOT EXISTS deleted(uid TEXT PRIMARY KEY, at INTEGER);
        """)
        self.db.commit()

    # ------------------------------------------------------------- words
    @staticmethod
    def _word(r) -> SavedWord:
        return SavedWord(**{k: r[k] if r[k] is not None else ("" if k not in ("start_ms", "end_ms", "created", "reviews",
                         "correct", "box", "due", "last_review", "updated") else 0) for k in WORD_COLS}, id=r["id"])

    def all(self) -> list[SavedWord]:
        return [self._word(r) for r in self.db.execute("SELECT * FROM words ORDER BY due ASC, id DESC")]

    def due(self, now: int) -> list[SavedWord]:
        return [self._word(r) for r in self.db.execute("SELECT * FROM words WHERE due <= ? ORDER BY box ASC, due ASC", (now,))]

    def find(self, text: str, video_uri: str, start_ms: int) -> SavedWord | None:
        r = self.db.execute("SELECT * FROM words WHERE lower(text)=lower(?) AND video_uri=? AND start_ms=?",
                            (text, video_uri, start_ms)).fetchone()
        return self._word(r) if r else None

    def insert(self, w: SavedWord) -> int:
        w.updated = now_ms()
        cur = self.db.execute(f"INSERT INTO words({','.join(WORD_COLS)}) VALUES({','.join('?' * len(WORD_COLS))})",
                              [getattr(w, k) for k in WORD_COLS])
        self.db.commit()
        return cur.lastrowid

    def update(self, w: SavedWord):
        w.updated = now_ms()
        self.db.execute(f"UPDATE words SET {','.join(k + '=?' for k in WORD_COLS)} WHERE id=?",
                        [getattr(w, k) for k in WORD_COLS] + [w.id])
        self.db.commit()

    def delete(self, word_id: int):
        now = now_ms()
        r = self.db.execute("SELECT uid FROM words WHERE id=?", (word_id,)).fetchone()
        if r and r["uid"]:
            self.db.execute("INSERT OR REPLACE INTO deleted(uid, at) VALUES(?,?)", (r["uid"], now))
        for e in self.db.execute("SELECT uid FROM examples WHERE word_id=?", (word_id,)).fetchall():
            if e["uid"]:
                self.db.execute("INSERT OR REPLACE INTO deleted(uid, at) VALUES(?,?)", (e["uid"], now))
        self.db.execute("DELETE FROM examples WHERE word_id=?", (word_id,))
        self.db.execute("DELETE FROM words WHERE id=?", (word_id,))
        self.db.commit()

    # ------------------------------------------------------------- example sentences
    def examples(self, word_id: int) -> list[Example]:
        return [Example(r["de"] or "", r["en"] or "", r["fa"] or "", r["id"], r["word_id"], r["created"] or 0, r["uid"] or "",
                        r["updated"] or 0) for r in self.db.execute("SELECT * FROM examples WHERE word_id=? ORDER BY id", (word_id,))]

    def add_examples(self, word_id: int, items: list[Example]) -> int:
        have = {e.de.lower() for e in self.examples(word_id)}
        n = 0
        for e in items:
            if e.de.lower() in have:
                continue
            have.add(e.de.lower())
            t = now_ms()
            self.db.execute("INSERT INTO examples(word_id,de,en,fa,created,uid,updated) VALUES(?,?,?,?,?,?,?)",
                            (word_id, e.de, e.en, e.fa, t, str(uuid.uuid4()), t))
            n += 1
        self.db.commit()
        return n

    def delete_example(self, ex_id: int):
        r = self.db.execute("SELECT uid FROM examples WHERE id=?", (ex_id,)).fetchone()
        if r and r["uid"]:
            self.db.execute("INSERT OR REPLACE INTO deleted(uid, at) VALUES(?,?)", (r["uid"], now_ms()))
        self.db.execute("DELETE FROM examples WHERE id=?", (ex_id,))
        self.db.commit()

    # ------------------------------------------------------------- sync
    def tombstones(self) -> dict:
        return {r["uid"]: r["at"] for r in self.db.execute("SELECT uid, at FROM deleted")}

    def export_sync(self) -> tuple[dict, dict]:
        words = self.all()
        by_id = {w.id: w for w in words}
        ws = {w.uid: {"uid": w.uid, "text": w.text, "lemma": w.lemma, "article": w.article, "ipa": w.ipa, "english": w.english,
                      "persian": w.persian, "sentence": w.sentence, "video_name": w.video_name, "start_ms": w.start_ms,
                      "end_ms": w.end_ms, "created": w.created, "reviews": w.reviews, "correct": w.correct, "box": w.box,
                      "due": w.due, "last_review": w.last_review, "lang": w.lang, "updated": w.updated} for w in words}
        es = {}
        for r in self.db.execute("SELECT * FROM examples"):
            w = by_id.get(r["word_id"])
            if w is None:
                continue
            es[r["uid"]] = {"uid": r["uid"], "word_uid": w.uid, "de": r["de"] or "", "en": r["en"] or "", "fa": r["fa"] or "",
                            "created": r["created"] or 0, "updated": r["updated"] or 0}
        return ws, es

    def apply_sync(self, doc: SyncDoc, resolve_video=lambda name: ""):
        """Makes the local database equal to the merged document (keeps local video locations)."""
        db = self.db
        try:
            local = {w.uid: w for w in self.all()}
            cols = [c for c in WORD_COLS if c != "video_uri"]
            for w in doc.words.values():
                cur = local.get(w["uid"])
                if cur is not None and cur.updated >= w["updated"]:
                    continue
                vals = [w[c] for c in cols]
                if cur is None:
                    db.execute(f"INSERT INTO words({','.join(cols)},video_uri) VALUES({','.join('?' * (len(cols) + 1))})",
                               vals + [resolve_video(w["video_name"])])
                else:
                    db.execute(f"UPDATE words SET {','.join(c + '=?' for c in cols)} WHERE id=?", vals + [cur.id])
            for uid, w in local.items():
                if uid not in doc.words:
                    db.execute("DELETE FROM words WHERE id=?", (w.id,))
            id_of = {r["uid"]: r["id"] for r in db.execute("SELECT id, uid FROM words")}
            local_ex = {r["uid"]: (r["id"], r["updated"] or 0) for r in db.execute("SELECT id, uid, updated FROM examples")}
            for e in doc.examples.values():
                wid = id_of.get(e["word_uid"])
                if wid is None:
                    continue
                cur = local_ex.get(e["uid"])
                if cur is not None and cur[1] >= e["updated"]:
                    continue
                vals = (wid, e["de"], e["en"], e["fa"], e["created"], e["uid"], e["updated"])
                if cur is None:
                    db.execute("INSERT INTO examples(word_id,de,en,fa,created,uid,updated) VALUES(?,?,?,?,?,?,?)", vals)
                else:
                    db.execute("UPDATE examples SET word_id=?,de=?,en=?,fa=?,created=?,uid=?,updated=? WHERE id=?", vals + (cur[0],))
            for uid, (eid, _) in local_ex.items():
                if uid not in doc.examples:
                    db.execute("DELETE FROM examples WHERE id=?", (eid,))
            db.execute("DELETE FROM deleted")
            db.executemany("INSERT INTO deleted(uid, at) VALUES(?,?)", list(doc.deleted.items()))
            db.commit()
        except Exception:
            db.rollback()
            raise


class Progress:
    """Daily streak and today's count; days are local calendar days since 1970 (same as Android)."""

    def __init__(self, file=None):
        self.file = file or paths.data_dir() / "progress.json"
        try:
            self.d = json.loads(self.file.read_text(encoding="utf-8"))
        except Exception:
            self.d = {"streak": 0, "last_day": -10, "today": 0}

    @staticmethod
    def today_index(now: float | None = None) -> int:
        t = time.time() if now is None else now
        off = time.localtime(t).tm_gmtoff
        return int((t + off) // 86400)

    def _save(self):
        self.file.write_text(json.dumps(self.d), encoding="utf-8")

    @property
    def streak(self) -> int:
        return self.d["streak"] if self.d["last_day"] >= self.today_index() - 1 else 0

    @property
    def today_count(self) -> int:
        return self.d["today"] if self.d["last_day"] == self.today_index() else 0

    @property
    def raw(self):
        return self.d["streak"], self.d["last_day"], self.d["today"]

    def set_raw(self, streak: int, last_day: int, today: int):
        self.d = {"streak": streak, "last_day": last_day, "today": today}
        self._save()

    def record(self):
        d = self.today_index()
        last = self.d["last_day"]
        streak = self.d["streak"] or 1 if last == d else (self.d["streak"] + 1 if last == d - 1 else 1)
        count = self.d["today"] + 1 if last == d else 1
        self.set_raw(streak, d, count)
