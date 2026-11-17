"""2.4.1: a PC with an NVIDIA card but without the CUDA libraries transcribes on the processor instead of failing."""
import sys
import types
import unittest


class GpuFallback(unittest.TestCase):
    def test_falls_back_to_cpu(self):
        from subplayer_win import asr
        calls = []

        class Seg:
            def __init__(s, a, b, t):
                s.start, s.end, s.text, s.words = a, b, t, []

        class Info:
            duration = 4

        class Model:
            def __init__(s, d, device, compute_type):
                s.device = device
                calls.append(device)

            def transcribe(s, audio, **k):
                def gen():
                    if s.device == "cuda":
                        raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
                    yield Seg(0, 2, "Hallo Welt.")
                return gen(), Info()

        old = sys.modules.get("faster_whisper"), asr.decode_audio, asr.gpu_usable
        sys.modules["faster_whisper"] = types.SimpleNamespace(WhisperModel=Model)
        asr.decode_audio = lambda v, c: [0.0]
        try:
            asr.gpu_usable = lambda: True
            cues = asr.transcribe_offline("x", "m", "de")
            self.assertEqual(calls, ["cuda", "cpu"])
            self.assertEqual([c.text for c in cues], ["Hallo Welt."])
            calls.clear()
            asr.gpu_usable = lambda: False
            asr.transcribe_offline("x", "m", "de")
            self.assertEqual(calls, ["cpu"])
        finally:
            if old[0] is None:
                sys.modules.pop("faster_whisper", None)
            else:
                sys.modules["faster_whisper"] = old[0]
            asr.decode_audio, asr.gpu_usable = old[1], old[2]

    def test_no_gpu_without_libraries(self):
        from subplayer_win import asr
        self.assertFalse(asr.gpu_usable())          # no NVIDIA card / CUDA libraries on the test machine
