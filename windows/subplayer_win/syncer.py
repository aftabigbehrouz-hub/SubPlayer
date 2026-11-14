"""Pull → merge → apply → push, the same steps as the Android app's syncNow()."""
from __future__ import annotations

import os
from pathlib import Path

from . import sync
from .store import Progress, WordStore


def subs_dir() -> Path:
    from . import paths
    return paths.sub_dir("subtitles")


def local_subs(folder: Path) -> dict:
    """Subtitles saved here as "<video key>.<lang>.srt"; file time = updated."""
    out = {}
    for f in folder.glob("*.srt"):
        stem = f.name[:-4]
        if "." not in stem:
            continue
        key, lang = stem.rsplit(".", 1)
        upd = int(f.stat().st_mtime * 1000)
        k = key + "|" + lang
        if out.get(k, {}).get("updated", -1) < upd:
            out[k] = {"key": key, "lang": lang, "srt": f.read_text(encoding="utf-8"), "updated": upd}
    return out


def apply_subs(doc: sync.SyncDoc, folder: Path):
    local = local_subs(folder)
    for k, s in doc.subs.items():
        if local.get(k, {}).get("updated", -1) >= s["updated"]:
            continue
        f = folder / f"{s['key']}.{s['lang']}.srt"
        f.write_text(s["srt"], encoding="utf-8")
        t = s["updated"] / 1000
        os.utime(f, (t, t))


def local_doc(store: WordStore, progress: Progress, folder: Path) -> sync.SyncDoc:
    ws, es = store.export_sync()
    st, day, today = progress.raw
    return sync.SyncDoc(ws, es, store.tombstones(), local_subs(folder), st, day, today)


def sync_now(token: str, gist_id: str | None, store: WordStore, progress: Progress, folder: Path,
             resolve_video=lambda name: "", client=None) -> tuple[str, int]:
    """Returns (gist id, number of words). Raises on network/auth errors."""
    g = client or sync.GistSync(token)
    gid = gist_id or g.find()
    remote_text = g.read(gid) if gid else ""
    merged = sync.merge(local_doc(store, progress, folder), sync.from_json(remote_text))
    store.apply_sync(merged, resolve_video)
    apply_subs(merged, folder)
    progress.set_raw(merged.streak, merged.last_day, merged.today)
    js = sync.to_json(merged)
    if gid is None:
        gid = g.create(js)
    elif js != remote_text:
        g.write(gid, js)
    return gid, len(merged.words)
