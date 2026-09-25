#!/usr/bin/env python3
"""Run with: python3 -m unittest tools.harness.test_verify_audio_window."""

import tempfile
from pathlib import Path
import unittest
import wave

from tools.harness.verify_audio_window import compare


class AudioWindowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        self.start = 4
        self.pcm = bytes([0, 1, 2] * 8 * 40)
        for name in ("stock-a", "candidate", "stock-b"):
            (self.run / f"{name}.log").write_text(
                f"audio out : mock, transport start at frame {self.start}\n")
            self.write_wav(name, self.pcm)

    def write_wav(self, name, pcm):
        with wave.open(str(self.run / f"{name}_core0.wav"), "wb") as wav:
            wav.setnchannels(8)
            wav.setsampwidth(3)
            wav.setframerate(44100)
            wav.writeframes(pcm)

    def test_equal_window(self):
        result = compare(self.run, 2)
        self.assertTrue(result["window_equal"])
        self.assertTrue(result["window_non_silent"])
        self.assertEqual(result["window_audio_samples"], 32)

    def test_detects_changed_sample(self):
        pcm = bytearray(self.pcm)
        pcm[(self.start + 3) * 24 + 4] ^= 1
        self.write_wav("candidate", pcm)
        self.assertFalse(compare(self.run, 2)["window_equal"])

    def test_rejects_short_capture(self):
        self.write_wav("candidate", self.pcm[:(self.start + 31) * 24])
        with self.assertRaisesRegex(ValueError, "ends before requested window"):
            compare(self.run, 2)


if __name__ == "__main__":
    unittest.main()
