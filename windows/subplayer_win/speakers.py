"""Optional local speaker diarisation helpers."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from . import paths, subtitles


@dataclass(frozen=True)
class SpeakerTurn:
    speaker: str
    start_ms: int
    end_ms: int


def mapping_path(video: str) -> Path:
    key = subtitles.video_key(Path(video).name) or "video"
    return paths.sub_dir("speakers") / (key + ".json")


def save_mapping(video: str, turns: list[SpeakerTurn], voices: dict[str, str]) -> Path:
    path = mapping_path(video)
    data = {"schema": 1, "video": Path(video).name,
            "turns": [asdict(t) for t in turns], "voices": dict(voices)}
    tmp = path.with_suffix(".part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def load_mapping(video: str) -> tuple[list[SpeakerTurn], dict[str, str]]:
    path = mapping_path(video)
    if not path.is_file():
        return [], {}
    data = json.loads(path.read_text(encoding="utf-8"))
    turns = []
    for item in data.get("turns", []):
        start, end = int(item["start_ms"]), int(item["end_ms"])
        if start >= 0 and end > start:
            turns.append(SpeakerTurn(str(item["speaker"]), start, end))
    return turns, {str(k): str(v) for k, v in data.get("voices", {}).items()}


def assign_subtitles(cues, turns: list[SpeakerTurn]) -> list[str | None]:
    result = []
    for cue in cues:
        overlaps: dict[str, int] = {}
        for turn in turns:
            overlap = max(0, min(cue.end_ms, turn.end_ms) - max(cue.start_ms, turn.start_ms))
            if overlap:
                overlaps[turn.speaker] = overlaps.get(turn.speaker, 0) + overlap
        ranked = sorted(overlaps.items(), key=lambda item: item[1], reverse=True)
        result.append(ranked[0][0] if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]) else None)
    return result


def diarize(audio_path: str | Path) -> list[SpeakerTurn]:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    if not token:
        raise RuntimeError("Set HF_TOKEN after accepting the diarisation model's Hugging Face conditions.")
    try:
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise RuntimeError("Install the optional pyannote.audio dependency to enable speaker analysis.") from exc
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1", token=token)
    if pipeline is None:
        raise RuntimeError("Could not load the diarisation model; check access and licence acceptance.")
    annotation = pipeline(str(audio_path))
    return [SpeakerTurn(str(speaker), max(0, round(segment.start * 1000)), round(segment.end * 1000))
            for segment, _, speaker in annotation.itertracks(yield_label=True) if segment.end > segment.start]
