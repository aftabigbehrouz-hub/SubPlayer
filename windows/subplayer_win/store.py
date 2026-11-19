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


@dataclass
class Question:
    """An exam-style question (TestDaF / IELTS) that comes back in Review like a word."""
    question: str
    answer: str
    options: list = field(default_factory=list)
    explanation: str = ""
    kind: str = ""                 # mc · tf (richtig/falsch) · yn (ja/nein/text sagt nichts) · gap · open
    lang: str = "de"
    lemma: str = ""
    video_name: str = ""
    source: str = ""               # "teacher" or "lesson:TestDaF" …
    created: int = field(default_factory=now_ms)
    reviews: int = 0
    correct: int = 0
    box: int = 0
    due: int = field(default_factory=now_ms)
    last_review: int = 0
    uid: str = ""
    id: int = 0

    @staticmethod
    def of(r) -> "Question":
        try:
            opts = json.loads(r["options"] or "[]")
        except Exception:
            opts = []
        return Question(r["question"] or "", r["answer"] or "", opts if isinstance(opts, list) else [], r["explanation"] or "",
                        r["kind"] or "", r["lang"] or "de", r["lemma"] or "", r["video_name"] or "", r["source"] or "",
                        r["created"] or 0, r["reviews"] or 0, r["correct"] or 0, r["box"] or 0, r["due"] or 0,
                        r["last_review"] or 0, r["uid"] or "", r["id"])


@dataclass
class Note:
    """A teacher's answer kept for later: the line explained, an answer to a question, a checked text, A1 → C1 …"""
    title: str                     # what was asked: the sentence, the question, the start of the text
    body: str                      # the answer as HTML (as it was shown)
    kind: str = "ask"              # line · ask · check · writing · levels
    lang: str = "de"
    lemma: str = ""
    video_name: str = ""
    source: str = ""               # ollama · chatgpt · gemini …
    created: int = field(default_factory=now_ms)
    reviews: int = 0
    correct: int = 0
    box: int = 0
    due: int = field(default_factory=now_ms)
    last_review: int = 0
    starred: int = 0
    id: int = 0


def _note(r) -> Note:
    return Note(r["title"] or "", r["body"] or "", r["kind"] or "", r["lang"] or "de", r["lemma"] or "", r["video_name"] or "",
                r["source"] or "", r["created"] or 0, r["reviews"] or 0, r["correct"] or 0, r["box"] or 0, r["due"] or 0,
                r["last_review"] or 0, r["starred"] or 0, r["id"])


def review(w, got_it: bool, now: int):
    """The next review step of a word (or a question)."""
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
            CREATE TABLE IF NOT EXISTS collocations(id INTEGER PRIMARY KEY AUTOINCREMENT, lang TEXT, lemma TEXT, phrase TEXT,
                meaning TEXT, example TEXT, created INTEGER);
            CREATE INDEX IF NOT EXISTS collocations_word ON collocations(lang, lemma);
            CREATE TABLE IF NOT EXISTS questions(id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, lang TEXT, lemma TEXT,
                video_name TEXT, source TEXT, kind TEXT, question TEXT, options TEXT, answer TEXT, explanation TEXT,
                created INTEGER, reviews INTEGER DEFAULT 0, correct INTEGER DEFAULT 0, box INTEGER DEFAULT 0, due INTEGER,
                last_review INTEGER DEFAULT 0);
            CREATE INDEX IF NOT EXISTS questions_due ON questions(due);
            CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY AUTOINCREMENT, lang TEXT, kind TEXT, lemma TEXT, title TEXT,
                body TEXT, video_name TEXT, source TEXT, created INTEGER, reviews INTEGER DEFAULT 0, correct INTEGER DEFAULT 0,
                box INTEGER DEFAULT 0, due INTEGER, last_review INTEGER DEFAULT 0, starred INTEGER DEFAULT 0);
            CREATE INDEX IF NOT EXISTS notes_due ON notes(due);
        """)
        self.db.commit()

    # ------------------------------------------------------------- words
    @staticmethod
    def _word(r) -> SavedWord:
        return SavedWord(**{k: r[k] if r[k] is not None else ("" if k not in ("start_ms", "end_ms", "created", "reviews",
                         "correct", "box", "due", "last_review", "updated") else 0) for k in WORD_COLS}, id=r["id"])

    def all(self) -> list[SavedWord]:
        """Newest first (the day the word was saved)."""
        return [self._word(r) for r in self.db.execute("SELECT * FROM words ORDER BY created DESC, id DESC")]

    def due(self, now: int) -> list[SavedWord]:
        """Due words, the least reviewed first (then the lowest box, then the longest waiting)."""
        return [self._word(r) for r in self.db.execute(
            "SELECT * FROM words WHERE due <= ? ORDER BY reviews ASC, box ASC, due ASC", (now,))]

    @staticmethod
    def word_key(text: str, lemma: str, lang: str) -> tuple[str, str]:
        """What makes two saved entries the same word: the language and the base form (a phrase: its text)."""
        t = (text or "").strip()
        base = t if " " in t else ((lemma or "").strip() or t)
        return (lang or "de", " ".join(base.lower().split()))

    def find_same(self, text: str, lemma: str, lang: str) -> SavedWord | None:
        """The word already in My Words with the same base form (from any video), or None."""
        k = self.word_key(text, lemma, lang)
        for w in self.all():
            if self.word_key(w.text, w.lemma, w.lang) == k:
                return w
        return None

    def merge_duplicates(self) -> int:
        """Joins entries of the same word into one (the most reviewed, then the oldest, is kept): their example sentences
        and their video lines move to it. Returns how many entries were joined into others."""
        groups: dict[tuple, list[SavedWord]] = {}
        for w in self.all():
            groups.setdefault(self.word_key(w.text, w.lemma, w.lang), []).append(w)
        n = 0
        for ws in groups.values():
            if len(ws) < 2:
                continue
            ws.sort(key=lambda w: (-w.reviews, w.created, w.id))
            keep, rest = ws[0], ws[1:]
            items = []
            for o in rest:
                if o.sentence and o.sentence.strip().lower() != (keep.sentence or "").strip().lower():
                    items.append(Example(de=o.sentence.strip(), en=f"from “{o.video_name}”" if o.video_name else ""))
                items += self.examples(o.id)
            self.add_examples(keep.id, items)
            changed = False
            for f in ("english", "persian", "ipa", "article", "sentence"):
                if not getattr(keep, f) and any(getattr(o, f) for o in rest):
                    setattr(keep, f, next(getattr(o, f) for o in rest if getattr(o, f)))
                    changed = True
            if not keep.video_name:
                o = next((o for o in rest if o.video_name), None)
                if o:
                    keep.video_uri, keep.video_name, keep.start_ms, keep.end_ms = o.video_uri, o.video_name, o.start_ms, o.end_ms
                    changed = True
            if changed:
                self.update(keep)
            for o in rest:
                self.delete(o.id)
                n += 1
        return n

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

    # ------------------------------------------------------------- collocations (from the teacher; kept per base word)
    def collocations(self, lang: str, lemma: str) -> list[dict]:
        return [dict(id=r["id"], phrase=r["phrase"] or "", meaning=r["meaning"] or "", example=r["example"] or "")
                for r in self.db.execute("SELECT * FROM collocations WHERE lang=? AND lemma=? ORDER BY id",
                                         (lang or "de", (lemma or "").lower()))]

    def add_collocations(self, lang: str, lemma: str, items: list[dict]) -> int:
        have = {c["phrase"].lower() for c in self.collocations(lang, lemma)}
        n = 0
        for c in items:
            ph = str(c.get("phrase", "")).strip()
            if not ph or ph.lower() in have:
                continue
            have.add(ph.lower())
            self.db.execute("INSERT INTO collocations(lang,lemma,phrase,meaning,example,created) VALUES(?,?,?,?,?,?)",
                            (lang or "de", (lemma or "").lower(), ph, str(c.get("meaning", "")).strip(),
                             str(c.get("example", "")).strip(), now_ms()))
            n += 1
        self.db.commit()
        return n

    def delete_collocation(self, cid: int):
        self.db.execute("DELETE FROM collocations WHERE id=?", (cid,))
        self.db.commit()

    # ------------------------------------------------------------- exam-style questions (TestDaF / IELTS), reviewed like words
    def questions(self, lang: str = "", lemma: str = "", video_name: str = "") -> list["Question"]:
        q, a = "SELECT * FROM questions WHERE 1=1", []
        if lang:
            q, a = q + " AND lang=?", a + [lang]
        if lemma:
            q, a = q + " AND lemma=?", a + [lemma.lower()]
        if video_name:
            q, a = q + " AND video_name=?", a + [video_name]
        return [Question.of(r) for r in self.db.execute(q + " ORDER BY id", a)]

    def due_questions(self, now: int) -> list["Question"]:
        return [Question.of(r) for r in self.db.execute(
            "SELECT * FROM questions WHERE due <= ? ORDER BY reviews ASC, box ASC, due ASC", (now,))]

    def add_questions(self, items: list["Question"]) -> int:
        """Adds new questions (the same question text is not added twice); returns how many were new."""
        have = {r["question"].strip().lower() for r in self.db.execute("SELECT question FROM questions")}
        n = 0
        for x in items:
            k = x.question.strip().lower()
            if not k or k in have:
                continue
            have.add(k)
            t = now_ms()
            self.db.execute("INSERT INTO questions(uid,lang,lemma,video_name,source,kind,question,options,answer,explanation,"
                            "created,reviews,correct,box,due,last_review) VALUES(?,?,?,?,?,?,?,?,?,?,?,0,0,0,?,0)",
                            (str(uuid.uuid4()), x.lang, (x.lemma or "").lower(), x.video_name, x.source, x.kind, x.question.strip(),
                             json.dumps(x.options, ensure_ascii=False), x.answer, x.explanation, t, t))
            n += 1
        self.db.commit()
        return n

    def update_question(self, x: "Question"):
        self.db.execute("UPDATE questions SET reviews=?, correct=?, box=?, due=?, last_review=? WHERE id=?",
                        (x.reviews, x.correct, x.box, x.due, x.last_review, x.id))
        self.db.commit()

    # ---------------------------------------------------------------- saved teacher answers (Notebook)
    def add_note(self, n: "Note") -> int:
        """Keeps an answer; the same question asked again replaces its older answer (and keeps its review progress)."""
        old = self.db.execute("SELECT id FROM notes WHERE kind=? AND lower(title)=lower(?) AND lang=?",
                              (n.kind, n.title.strip(), n.lang)).fetchone()
        if old:
            self.db.execute("UPDATE notes SET body=?, source=?, created=? WHERE id=?", (n.body, n.source, now_ms(), old["id"]))
            self.db.commit()
            return old["id"]
        cur = self.db.execute("INSERT INTO notes(lang,kind,lemma,title,body,video_name,source,created,reviews,correct,box,due,"
                              "last_review,starred) VALUES(?,?,?,?,?,?,?,?,0,0,0,?,0,0)",
                              (n.lang, n.kind, (n.lemma or "").lower(), n.title.strip(), n.body, n.video_name, n.source, now_ms(),
                               now_ms() + DAY))                       # first review the next day
        self.db.commit()
        return cur.lastrowid

    def notes(self, search: str = "", kind: str = "") -> list:
        q, args = "SELECT * FROM notes WHERE 1=1", []
        if kind:
            q += " AND kind=?"
            args.append(kind)
        if search.strip():
            q += " AND (title LIKE ? OR body LIKE ? OR lemma LIKE ?)"
            args += [f"%{search.strip()}%"] * 3
        return [_note(r) for r in self.db.execute(q + " ORDER BY created DESC, id DESC", args)]

    def due_notes(self, now: int) -> list:
        return [_note(r) for r in self.db.execute("SELECT * FROM notes WHERE due<=? ORDER BY reviews ASC, box ASC, due ASC", (now,))]

    def update_note(self, n: "Note"):
        self.db.execute("UPDATE notes SET reviews=?, correct=?, box=?, due=?, last_review=?, starred=? WHERE id=?",
                        (n.reviews, n.correct, n.box, n.due, n.last_review, n.starred, n.id))
        self.db.commit()

    def delete_note(self, nid: int):
        self.db.execute("DELETE FROM notes WHERE id=?", (nid,))
        self.db.commit()

    def delete_question(self, qid: int):
        self.db.execute("DELETE FROM questions WHERE id=?", (qid,))
        self.db.commit()

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
