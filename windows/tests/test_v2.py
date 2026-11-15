"""Tests for the 2.0 features: video links, clip export, reminder command, owner key check."""
import math
import os
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SUBPLAYER_HOME", tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from subplayer_win import export, linkimport, reminder, subtitles  # noqa: E402

PAGE = """<html><head><meta property="og:title" content="tagesschau 20:00 Uhr &amp; mehr"><title>x</title></head>
<script>var m = {"a":"https:\\/\\/media.tagesschau.de\\/video\\/2026\\/1113\\/TV-20261113-2022-4000.webs.h264.mp4",
"b":"https://media.tagesschau.de/video/2026/1113/TV-20261113-2022-4000.webl.h264.mp4",
"c":"https://media.tagesschau.de/video/2026/1113/TV-20261113-2022-4000.webxxl.h264.mp4",
"d":"https://media.tagesschau.de/video/trailer.webl.mp4"}</script></html>"""


class LinkTest(unittest.TestCase):
    def test_refused(self):
        self.assertIsNotNone(linkimport.refused_reason("https://www.youtube.com/watch?v=1"))
        self.assertIsNotNone(linkimport.refused_reason("https://youtu.be/abc"))
        self.assertIsNotNone(linkimport.refused_reason("https://m.facebook.com/x"))
        self.assertIsNone(linkimport.refused_reason("https://www.tagesschau.de/multimedia"))
        self.assertIsNone(linkimport.refused_reason("https://notyoutube.com/x"))

    def test_best_video_in_page(self):
        f = linkimport.find_in_page(PAGE)
        self.assertTrue(f.video_url.endswith("4000.webl.h264.mp4"), f.video_url)
        self.assertEqual("tagesschau 20:00 Uhr & mehr", f.title)
        self.assertIsNone(linkimport.find_in_page("<html>nothing</html>"))

    def test_names_and_links(self):
        self.assertEqual("tagesschau 20 00 Uhr mehr.mp4", linkimport.safe_name("tagesschau 20:00 Uhr & mehr"))
        self.assertEqual("video.mp4", linkimport.safe_name("///"))
        self.assertEqual("https://a.de/v.mp4", linkimport.first_link("look: https://a.de/v.mp4."))
        self.assertIsNone(linkimport.first_link("no link here"))

    def test_direct_link_needs_no_page(self):
        f = linkimport.resolve("https://cdn.example.org/clips/Lektion_3.mp4?token=1")
        self.assertEqual("Lektion_3", f.title)


class ReminderTest(unittest.TestCase):
    def test_command(self):
        a = reminder.create_args(7)
        self.assertEqual(["schtasks", "/Create", "/F", "/SC", "DAILY", "/TN", reminder.TASK], a[:7])
        self.assertEqual("07:00", a[-1])
        self.assertIn("--remind", a[8])
        self.assertEqual("23:00", reminder.create_args(99)[-1])
        self.assertEqual(["schtasks", "/Delete", "/F", "/TN", reminder.TASK], reminder.delete_args())


def make_video(path, seconds=6, fps=25):
    import av
    import numpy as np
    c = av.open(str(path), "w")
    v = c.add_stream(export.pick_encoder(), rate=fps)
    v.width, v.height, v.pix_fmt = 320, 180, "yuv420p"
    a = c.add_stream("aac", rate=44100)
    a.layout = "stereo"
    for i in range(seconds * fps):
        arr = np.zeros((180, 320, 3), np.uint8)
        arr[:, :, 1] = (i * 4) % 255
        f = av.VideoFrame.from_ndarray(arr, format="rgb24")
        f.pts, f.time_base = i, Fraction(1, fps)
        for p in v.encode(f):
            c.mux(p)
    n = 0
    for _ in range(int(seconds * 44100 / 1024)):
        t = (np.arange(1024) + n) / 44100
        s = (0.2 * np.sin(2 * math.pi * 330 * t)).astype(np.float32)
        f = av.AudioFrame.from_ndarray(np.vstack([s, s]), format="fltp", layout="stereo")
        f.sample_rate, f.pts = 44100, n
        n += 1024
        for p in a.encode(f):
            c.mux(p)
    for s in (v, a):
        for p in s.encode(None):
            c.mux(p)
    c.close()


class ExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtGui import QGuiApplication
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.dir = Path(tempfile.mkdtemp())
        cls.src = cls.dir / "src.mp4"
        make_video(cls.src)

    def check(self, burn):
        import av
        cues = [subtitles.Cue(1000, 3500, "Ich strebe nach Perfektion"), subtitles.Cue(3600, 5000, "Zweite Zeile")]
        out = export.export_clip(str(self.src), 1200, 4200, cues, burn, self.dir / f"clip{int(burn)}.mp4")
        c = av.open(str(out))
        frames = sum(1 for _ in c.decode(video=0))
        c.close()
        c = av.open(str(out))
        has_audio = len(c.streams.audio) == 1
        dur = c.duration / 1e6
        c.close()
        self.assertTrue(74 <= frames <= 76, frames)          # 3.0 s × 25 fps
        self.assertTrue(has_audio)
        self.assertAlmostEqual(3.0, dur, delta=0.15)
        self.assertFalse(any(p.name.endswith(".part.mp4") for p in self.dir.iterdir()))

    def test_clean_clip(self):
        self.check(False)

    def test_clip_with_subtitles(self):
        self.check(True)

    def test_name(self):
        self.assertEqual("Mein_Weg_00-12_to_00-19_subs.mp4", export.clip_name("Mein Weg.mp4", 12500, 19000, True))

    def test_needs_a_and_b(self):
        with self.assertRaises(ValueError):
            export.export_clip(str(self.src), 3000, 2000, [], False, self.dir / "x.mp4")


if __name__ == "__main__":
    unittest.main()
