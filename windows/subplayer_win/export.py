"""
Saves the A-B part of a video as a new MP4 in Videos\\SubPlayer, optionally with the subtitles drawn into the
picture (burnt in) — the same feature as on the phone. Cut is frame-exact (re-encoded with H.264 + AAC).
"""
from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path

ENCODERS = ("libx264", "h264_mf", "libopenh264", "mpeg4")


def pick_encoder() -> str:
    import av
    have = av.codecs_available
    return next((e for e in ENCODERS if e in have), "mpeg4")


def clip_name(video_name: str, a_ms: int, b_ms: int, burn: bool) -> str:
    def t(ms):
        return f"{ms // 60000:02d}-{ms // 1000 % 60:02d}"
    base = re.sub(r"[^\w-]+", "_", Path(video_name).stem, flags=re.U)[:40] or "clip"
    return f"{base}_{t(a_ms)}_to_{t(b_ms)}{'_subs' if burn else ''}.mp4"


def _even(n: int) -> int:
    return max(2, n - n % 2)


class _Burner:
    """Draws the subtitle line of each moment onto the frame (white text, dark outline, soft box)."""

    def __init__(self, cues, width, height):
        from PySide6.QtGui import QFont
        self.cues = cues
        self.w, self.h = width, height
        self.font = QFont()
        self.font.setFamilies(["Segoe UI", "Inter", "Arial", "Vazirmatn"])
        self.font.setPixelSize(max(16, int(height * 0.052)))
        self.font.setBold(True)
        self.idx, self.cache = -2, None

    def text_at(self, ms):
        for i, c in enumerate(self.cues):
            if c.start_ms <= ms < c.end_ms:
                return i, c.text
        return -1, ""

    def draw(self, img, ms):
        from PySide6.QtCore import QRectF, Qt
        from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPainterPath, QPen
        i, text = self.text_at(ms)
        if i < 0:
            return
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        fm = QFontMetricsF(self.font)
        maxw = self.w * 0.86
        lines = []
        for para in text.split("\n"):
            cur = ""
            for word in para.split():
                trial = (cur + " " + word).strip()
                if fm.horizontalAdvance(trial) > maxw and cur:
                    lines.append(cur)
                    cur = word
                else:
                    cur = trial
            if cur:
                lines.append(cur)
        lh = fm.height() * 1.08
        total = lh * len(lines)
        y0 = self.h * 0.93 - total
        boxw = max(fm.horizontalAdvance(l) for l in lines) + fm.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 120))
        p.drawRoundedRect(QRectF((self.w - boxw) / 2, y0 - lh * 0.2, boxw, total + lh * 0.4), lh * 0.35, lh * 0.35)
        for k, line in enumerate(lines):
            path = QPainterPath()
            x = (self.w - fm.horizontalAdvance(line)) / 2
            path.addText(x, y0 + k * lh + fm.ascent(), self.font, line)
            p.strokePath(path, QPen(QColor(0, 0, 0, 230), max(2.0, self.font.pixelSize() / 9), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.fillPath(path, QColor("white"))
        p.end()


def export_clip(src: str, a_ms: int, b_ms: int, cues, burn: bool, out: Path,
                progress=lambda frac, msg: None, cancelled=lambda: False) -> Path:
    import av
    import numpy as np
    if b_ms <= a_ms:
        raise ValueError("Set A and B first")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".part.mp4")
    inp = av.open(src)
    try:
        vin = next((s for s in inp.streams.video), None)
        ain = next((s for s in inp.streams.audio), None)
        if vin is None and ain is None:
            raise ValueError("No picture or sound in that file")
        outc = av.open(str(tmp), "w", format="mp4")
        try:
            vout = aout = None
            burner = None
            rate = 25
            if vin is not None:
                rate = vin.average_rate or vin.guessed_rate or 25
                rate = Fraction(rate).limit_denominator(1001)
                if not (5 <= float(rate) <= 120):
                    rate = Fraction(25)
                enc = pick_encoder()
                vout = outc.add_stream(enc, rate=rate)
                w, h = _even(vin.codec_context.width), _even(vin.codec_context.height)
                vout.width, vout.height = w, h
                vout.pix_fmt = "yuv420p"
                if enc == "libx264":
                    vout.options = {"crf": "20", "preset": "veryfast"}
                else:
                    vout.bit_rate = 4_000_000
                if burn and cues:
                    clip = [c for c in cues if c.end_ms > a_ms and c.start_ms < b_ms]
                    burner = _Burner(clip, w, h) if clip else None
            resampler = None
            if ain is not None:
                sr = ain.codec_context.sample_rate or 48000
                aout = outc.add_stream("aac", rate=sr)
                aout.layout = "stereo"
                resampler = av.AudioResampler(format="fltp", layout="stereo", rate=sr)
            inp.seek(max(0, int((a_ms - 1500) * 1000)), any_frame=False, backward=True)
            a_s, b_s = a_ms / 1000, b_ms / 1000
            span = b_s - a_s
            vcount = 0
            asamples = 0
            streams = [s for s in (vin, ain) if s is not None]
            vdone = vin is None
            adone = ain is None
            for packet in inp.demux(*streams):
                if cancelled():
                    raise RuntimeError("Cancelled")
                if vdone and adone:
                    break
                for frame in packet.decode():
                    if frame.time is None:
                        continue
                    if packet.stream is vin and not vdone:
                        if frame.time < a_s - 0.001:
                            continue
                        if frame.time >= b_s:
                            vdone = True
                            continue
                        if burner:
                            arr = frame.to_ndarray(format="rgb24")
                            if arr.shape[1] != vout.width or arr.shape[0] != vout.height:
                                arr = np.ascontiguousarray(arr[:vout.height, :vout.width])
                            from PySide6.QtGui import QImage
                            img = QImage(arr.data, arr.shape[1], arr.shape[0], arr.strides[0], QImage.Format_RGB888)
                            burner.draw(img, int(frame.time * 1000))
                            nf = av.VideoFrame.from_ndarray(arr, format="rgb24")
                        else:
                            nf = frame.reformat(width=vout.width, height=vout.height, format="yuv420p")
                        nf.pts = vcount
                        nf.time_base = Fraction(1) / rate
                        vcount += 1
                        for pk in vout.encode(nf):
                            outc.mux(pk)
                        progress(min(0.99, (frame.time - a_s) / span), f"Saving clip… {int(100 * (frame.time - a_s) / span)}%")
                    elif packet.stream is ain and not adone:
                        if frame.time + frame.samples / frame.sample_rate <= a_s:
                            continue
                        if frame.time >= b_s:
                            adone = True
                            continue
                        frame.pts = None
                        for rf in resampler.resample(frame):
                            rf.pts = asamples
                            rf.time_base = Fraction(1, rf.sample_rate)
                            asamples += rf.samples
                            for pk in aout.encode(rf):
                                outc.mux(pk)
            if vout is not None:
                for pk in vout.encode(None):
                    outc.mux(pk)
            if aout is not None:
                for rf in resampler.resample(None) if resampler else []:
                    rf.pts = asamples
                    asamples += rf.samples
                    for pk in aout.encode(rf):
                        outc.mux(pk)
                for pk in aout.encode(None):
                    outc.mux(pk)
            if vout is not None and vcount == 0:
                raise ValueError("No video frames between A and B")
        finally:
            outc.close()
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        inp.close()
    if out.exists():
        out.unlink()
    tmp.replace(out)
    progress(1.0, "Clip saved")
    return out


def snapshot(video: str, at_ms: int, out, width: int = 360) -> bool:
    """Saves a small JPEG of the video frame at `at_ms`."""
    import av
    from pathlib import Path
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with av.open(video) as c:
        st = c.streams.video[0]
        st.thread_type = "AUTO"
        target = max(0, at_ms) / 1000
        c.seek(int(target / st.time_base) if st.time_base else int(target * 1_000_000), stream=st, backward=True, any_frame=False)
        frame = None
        for fr in c.decode(st):
            frame = fr
            if fr.time is None or fr.time >= target:
                break
        if frame is None:
            return False
        h = max(2, int(frame.height * width / max(1, frame.width)) // 2 * 2)
        import numpy as np
        img = np.ascontiguousarray(frame.reformat(width=width, height=h, format="rgb24").to_ndarray())
    q = QImage(img.data, img.shape[1], img.shape[0], 3 * img.shape[1], QImage.Format_RGB888).copy()
    tmp = out.with_suffix(".part.jpg")
    ok = q.save(str(tmp), "JPG", 82)
    if ok:
        tmp.replace(out)
    return ok
