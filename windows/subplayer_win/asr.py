"""
Speech → subtitles.
 - Offline: faster-whisper (Whisper on the PC's CPU, or an NVIDIA GPU if present). Reads the audio straight from the video.
 - Online: Groq (free tier, whisper-large-v3) or OpenAI (whisper-1) with the user's own API key.
"""
from __future__ import annotations

import io
import wave
from dataclasses import dataclass

import requests

from .subtitles import Cue, from_segments


@dataclass
class Provider:
    id: str
    title: str
    url: str
    model: str
    key_page: str


GROQ = Provider("GROQ", "Groq · free tier", "https://api.groq.com/openai/v1/audio/transcriptions", "whisper-large-v3",
                "https://console.groq.com/keys")
OPENAI = Provider("OPENAI", "OpenAI", "https://api.openai.com/v1/audio/transcriptions", "whisper-1",
                  "https://platform.openai.com/api-keys")
PROVIDERS = {p.id: p for p in (GROQ, OPENAI)}

CHUNK_S = 600   # 10-minute pieces stay under the 25 MB upload limit (16 kHz mono 16-bit ≈ 19 MB)


class Cancelled(Exception):
    pass


def decode_audio(path: str):
    from faster_whisper.audio import decode_audio as dec
    return dec(path, sampling_rate=16000)


def transcribe_offline(video: str, model_dir: str, lang: str, progress=lambda f, msg: None, cancelled=lambda: False) -> list[Cue]:
    from faster_whisper import WhisperModel
    progress(0.0, "Loading the speech model…")
    try:
        model = WhisperModel(model_dir, device="auto", compute_type="int8")
    except Exception:
        model = WhisperModel(model_dir, device="cpu", compute_type="int8")
    progress(0.0, "Reading the audio…")
    segments, info = model.transcribe(video, language=lang, beam_size=5, vad_filter=True, word_timestamps=True,
                                      condition_on_previous_text=False)
    total = max(1.0, float(info.duration or 1))
    segs = []
    for s in segments:
        if cancelled():
            raise Cancelled()
        words = [(w.start, w.end, w.word) for w in (s.words or [])]
        segs.append((s.start, s.end, s.text, words))
        progress(min(0.99, s.end / total), f"{int(s.end // 60)}:{int(s.end % 60):02d} of {int(total // 60)}:{int(total % 60):02d}")
    return from_segments(segs)


def _wav(samples) -> bytes:
    import numpy as np
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm)
    return b.getvalue()


def transcribe_online(video: str, provider: Provider, key: str, lang: str, progress=lambda f, msg: None,
                      cancelled=lambda: False) -> list[Cue]:
    if not key.strip():
        raise ValueError(f"Add your {provider.title.split(' ·')[0]} API key first (Settings).")
    progress(0.0, "Reading the audio…")
    audio = decode_audio(video)
    n = len(audio)
    step = CHUNK_S * 16000
    segs = []
    for k, start in enumerate(range(0, max(n, 1), step)):
        if cancelled():
            raise Cancelled()
        piece = audio[start:start + step]
        off = start / 16000
        progress(start / max(n, 1), f"Uploading part {k + 1} of {(n + step - 1) // step}…")
        data = {"model": provider.model, "response_format": "verbose_json", "language": lang, "temperature": "0"}
        r = requests.post(provider.url, headers={"Authorization": "Bearer " + key.strip()},
                          files={"file": ("audio.wav", _wav(piece), "audio/wav")}, data=data, timeout=600)
        if r.status_code == 401:
            raise IOError("The API key was refused — check it in Settings.")
        if r.status_code == 429:
            raise IOError("The provider's free limit was reached — wait a bit and try again.")
        if r.status_code >= 400:
            raise IOError(f"{provider.title}: HTTP {r.status_code} {r.text[:200]}")
        for s in r.json().get("segments") or []:
            segs.append((off + float(s["start"]), off + float(s["end"]), s.get("text") or "", None))
    progress(1.0, "Done")
    return from_segments(segs)
