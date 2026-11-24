"""Record yourself and compare: timing and the order original → you → original → your recording (no real microphone)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SUBPLAYER_HOME"] = tempfile.mkdtemp()

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtMultimedia import QMediaPlayer, QMediaRecorder  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from subplayer_win import compare  # noqa: E402

app = QApplication.instance() or QApplication([])


class FakePlayer:
    def __init__(self):
        self.pos, self.state, self.log = 0, QMediaPlayer.PlaybackState.StoppedState, []

    def setPosition(self, p):
        self.pos = p
        self.log.append(("seek", p))

    def position(self):
        return self.pos

    def play(self):
        self.state = QMediaPlayer.PlaybackState.PlayingState
        self.log.append("play")

    def pause(self):
        self.state = QMediaPlayer.PlaybackState.PausedState
        self.log.append("pause")

    def playbackState(self):
        return self.state


class FakeMain(QWidget):
    def __init__(self):
        super().__init__()
        self.player, self.msgs = FakePlayer(), []

    def msg(self, t, *a):
        self.msgs.append(t)


class FakeRecorder:
    def __init__(self):
        self.state, self.loc, self.calls = QMediaRecorder.RecorderState.StoppedState, QUrl(), []

    def setOutputLocation(self, u):
        self.loc = u

    def record(self):
        self.calls.append("record")
        self.state = QMediaRecorder.RecorderState.RecordingState

    def stop(self):
        self.calls.append("stop")
        self.state = QMediaRecorder.RecorderState.StoppedState

    def recorderState(self):
        return self.state

    def actualLocation(self):
        return QUrl.fromLocalFile(self.loc.toLocalFile() + ".m4a")


class Compare(unittest.TestCase):
    def test_record_time(self):
        self.assertEqual(compare.record_ms(0), 2000)
        self.assertEqual(compare.record_ms(3000), 5500)
        self.assertEqual(compare.record_ms(60_000), 30_000)

    def test_no_microphone(self):
        m = FakeMain()
        c = compare.RecordCompare(m)
        with mock.patch.object(compare.RecordCompare, "has_microphone", staticmethod(lambda: False)):
            self.assertFalse(c.start(1000, 3000))
        self.assertIn("No microphone", m.msgs[-1])
        self.assertFalse(c.busy)
        self.assertEqual(m.player.log, [])                                  # the video wasn't touched

    def test_original_you_original_you(self):
        m = FakeMain()
        c = compare.RecordCompare(m)
        rec = FakeRecorder()
        with mock.patch.object(compare.RecordCompare, "has_microphone", staticmethod(lambda: True)), \
                mock.patch.object(compare.RecordCompare, "_ensure_recorder", lambda self: setattr(self, "recorder", rec)), \
                mock.patch.object(compare.QTimer, "singleShot"):
            self.assertTrue(c.start(1000, 3000))
            self.assertEqual((c.stage, m.player.log[:2]), (compare.LISTEN, [("seek", 1000), "play"]))
            m.player.pos = 2000
            c._tick()
            self.assertEqual(c.stage, compare.LISTEN)                       # still the actor speaking
            m.player.pos = 3000
            c._tick()
            self.assertEqual((c.stage, rec.calls), (compare.RECORD, ["record"]))
            self.assertEqual(m.player.log[-1], "pause")                     # the video is quiet while you speak
            c._stop_recording()
            c._rec_state(QMediaRecorder.RecorderState.StoppedState)
            self.assertEqual(c.stage, compare.ORIGINAL)
            self.assertEqual(m.player.log[-2:], [("seek", 1000), "play"])  # the original again
            m.player.pos = 3001
            c._tick()
            self.assertEqual(c.stage, compare.YOU)
            self.assertTrue(c.you.source().toLocalFile().endswith("last-attempt.m4a"))
            c._you_status(QMediaPlayer.MediaStatus.EndOfMedia)
            self.assertFalse(c.busy)
            self.assertIn("Compare", m.msgs[-1])

    def test_cancel(self):
        m = FakeMain()
        c = compare.RecordCompare(m)
        rec = FakeRecorder()
        with mock.patch.object(compare.RecordCompare, "has_microphone", staticmethod(lambda: True)), \
                mock.patch.object(compare.RecordCompare, "_ensure_recorder", lambda self: setattr(self, "recorder", rec)), \
                mock.patch.object(compare.QTimer, "singleShot"):
            c.start(0, 1000)
            m.player.pos = 1000
            c._tick()
            c.cancel()
        self.assertFalse(c.busy)
        self.assertEqual(rec.calls, ["record", "stop"])
        self.assertEqual(m.player.log[-1], "pause")


if __name__ == "__main__":
    unittest.main()
