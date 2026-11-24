"""Record yourself and compare (shadowing with your own voice): the line plays from the video, you say it while the
microphone records, then the original line plays again and your recording right after it. The model is always the
video's own sound — the actor's real voice; nothing synthetic is involved. Only your last attempt is kept
(<data>/recordings/last-attempt.*), on this PC."""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtMultimedia import QAudioInput, QAudioOutput, QMediaCaptureSession, QMediaDevices, QMediaPlayer, QMediaRecorder

from . import paths

IDLE, LISTEN, RECORD, SAVING, ORIGINAL, YOU = "idle", "listen", "record", "saving", "original", "you"


def record_ms(line_ms: int) -> int:
    """How long you get to say a line: a bit more than the actor needed, at least 2 s, at most 30 s."""
    return max(2000, min(30_000, int(line_ms * 1.5) + 1000))


class RecordCompare(QObject):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.stage = IDLE
        self.a = self.b = 0
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)
        self.session = self.recorder = self.mic = None
        self.you = QMediaPlayer(self)
        self.you_out = QAudioOutput(self)
        self.you.setAudioOutput(self.you_out)
        self.you.mediaStatusChanged.connect(self._you_status)

    @staticmethod
    def has_microphone() -> bool:
        return bool(QMediaDevices.audioInputs())

    def start(self, a_ms: int, b_ms: int) -> bool:
        """Plays a_ms…b_ms, records you, plays it again and then you. False if there is no microphone."""
        self.cancel(quiet=True)
        if not self.has_microphone():
            self.main.msg("No microphone found — connect one (Windows Settings ▸ Privacy ▸ Microphone: allow desktop apps)", 9000)
            return False
        self.a, self.b = max(0, a_ms), max(a_ms + 300, b_ms)
        self._ensure_recorder()
        self.stage = LISTEN
        self.main.player.setPosition(self.a)
        self.main.player.play()
        self.timer.start()
        self.main.msg("🎧 Listen to the line … then say it yourself (Esc stops)", 0)
        return True

    def _ensure_recorder(self):
        if self.recorder is not None:
            self.mic.setDevice(QMediaDevices.defaultAudioInput())
            return
        self.session = QMediaCaptureSession(self)
        self.mic = QAudioInput(QMediaDevices.defaultAudioInput(), self)
        self.session.setAudioInput(self.mic)
        self.recorder = QMediaRecorder(self)
        self.session.setRecorder(self.recorder)
        self.recorder.setQuality(QMediaRecorder.Quality.HighQuality)
        self.recorder.recorderStateChanged.connect(self._rec_state)
        self.recorder.errorOccurred.connect(lambda *_: self._failed(self.recorder.errorString()))

    def _tick(self):
        p = self.main.player
        if self.stage in (LISTEN, ORIGINAL) and (p.position() >= self.b or p.playbackState() == QMediaPlayer.StoppedState):
            p.pause()
            if self.stage == LISTEN:
                self._record()
            else:
                self.stage = YOU
                self.you.setSource(QUrl.fromLocalFile(str(self.file)))
                self.you.play()
                self.main.msg("🗣 … and you", 0)

    def _record(self):
        self.stage = RECORD
        old = paths.sub_dir("recordings")
        for f in old.glob("last-attempt.*"):
            try:
                f.unlink()
            except OSError:
                pass
        self.you.setSource(QUrl())
        self.recorder.setOutputLocation(QUrl.fromLocalFile(str(old / "last-attempt")))
        self.recorder.record()
        ms = record_ms(self.b - self.a)
        self.main.msg(f"🎙 Your turn — say the line now ({ms // 1000} s)", 0)
        QTimer.singleShot(ms, self._stop_recording)

    def _stop_recording(self):
        if self.stage == RECORD:
            self.stage = SAVING
            self.recorder.stop()

    def _rec_state(self, state):
        if state == QMediaRecorder.RecorderState.StoppedState and self.stage == SAVING:
            loc = self.recorder.actualLocation()
            self.file = loc.toLocalFile() if loc.isValid() else ""
            if not self.file:
                return self._failed("nothing was recorded")
            self.stage = ORIGINAL
            self.main.player.setPosition(self.a)
            self.main.player.play()
            self.main.msg("🎧 The original …", 0)

    def _you_status(self, status):
        if self.stage == YOU and status in (QMediaPlayer.MediaStatus.EndOfMedia, QMediaPlayer.MediaStatus.InvalidMedia):
            self.stage = IDLE
            self.timer.stop()
            self.main.msg("Compare: did you sound like the original? Y records the line again, ↓ goes on" if
                          status == QMediaPlayer.MediaStatus.EndOfMedia else "Your recording could not be played", 9000)

    def _failed(self, why: str):
        self.cancel(quiet=True)
        self.main.msg(f"Recording didn't work: {why or 'the microphone could not be used'}", 9000)

    def cancel(self, quiet: bool = False):
        was = self.stage != IDLE
        self.stage = IDLE
        self.timer.stop()
        if self.recorder is not None and self.recorder.recorderState() != QMediaRecorder.RecorderState.StoppedState:
            self.recorder.stop()
        self.you.stop()
        if was and not quiet:
            self.main.player.pause()
            self.main.msg("Recording stopped", 3000)

    @property
    def busy(self) -> bool:
        return self.stage != IDLE
