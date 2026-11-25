"""The fast RNNoise loop must match the old per-frame path and stay fast.

Uses the real native library when it is present (Windows release builds and
dev setups that fetched it); skips otherwise. Synthetic audio only.
"""
import os
import sys
import time
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1]))
from keystow import denoise  # noqa: E402

try:
    from keystow.vendor import rnnoise
except OSError:
    rnnoise = None


def old_denoise(audio):
    """The v1.0.6 algorithm, kept here as the reference."""
    state = rnnoise.create()
    try:
        up = np.interp(np.arange(audio.size * 3) / 3.0, np.arange(audio.size), audio).astype(np.float32)
        pad = (-up.size) % 480
        if pad:
            up = np.pad(up, (0, pad))
        frames = up.reshape(-1, 480)
        out = np.empty_like(frames)
        for i, frame in enumerate(frames):
            pcm = np.clip(frame * 32767.0, -32768, 32767).astype(np.int16)
            denoised, _ = rnnoise.process_mono_frame(state, pcm)
            out[i] = denoised.astype(np.float32) / 32767.0
        flat = out.flatten()
        return np.interp(np.arange(audio.size) * 3.0, np.arange(flat.size), flat).astype(np.float32)
    finally:
        rnnoise.destroy(state)


@unittest.skipIf(rnnoise is None, "native RNNoise library not present")
class FastDenoiseTest(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(3)
        t = np.arange(16000 * 3) / 16000
        # A synthetic "voice": a few harmonics with a slow envelope, plus room noise.
        voice = sum(np.sin(2 * np.pi * f * t) / k for k, f in enumerate((180, 360, 540, 900), 1))
        self.audio = (0.2 * voice * (0.5 + 0.5 * np.sin(2 * np.pi * 0.7 * t))
                      + rng.normal(0, 0.01, t.size)).astype(np.float32)

    def test_matches_the_old_path_within_one_16_bit_step(self):
        engine = denoise._RnNoise()
        try:
            new = engine.denoise(self.audio)
        finally:
            engine.close()
        old = old_denoise(self.audio)
        self.assertEqual(new.shape, old.shape)
        self.assertLessEqual(float(np.max(np.abs(new - old))), 2.0 / 32767)

    def test_streaming_in_mic_sized_chunks_matches_the_whole_recording(self):
        whole = old_denoise(self.audio)
        for chunk in (7, 160, 441, 1024, 3200):  # odd sizes on purpose
            with self.subTest(chunk=chunk):
                stream = denoise.Streaming()
                for start in range(0, self.audio.size, chunk):
                    stream.push(self.audio[start:start + chunk].reshape(-1, 1))
                out = stream.finish(self.audio.size)
                self.assertEqual(out.shape, whole.shape)
                self.assertLessEqual(float(np.max(np.abs(out - whole))), 2.0 / 32767)

    def test_streaming_leaves_little_work_after_release(self):
        # Feed at real-time pace for the first part, then time only finish().
        stream = denoise.Streaming()
        for start in range(0, self.audio.size, 1600):  # 100 ms chunks
            stream.push(self.audio[start:start + 1600])
            time.sleep(0.1)
        began = time.perf_counter()
        stream.finish(self.audio.size)
        waited = time.perf_counter() - began
        self.assertLess(waited, 0.5, f"release still waited {waited * 1000:.0f} ms")

    def test_cancel_discards_and_stops(self):
        stream = denoise.Streaming()
        stream.push(self.audio[:16000])
        stream.cancel()
        self.assertFalse(stream._thread.is_alive())
        self.assertEqual(stream._out, [])
