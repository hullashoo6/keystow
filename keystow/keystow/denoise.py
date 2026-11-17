"""RNNoise mic noise suppression, with graceful passthrough when unavailable.

RNNoise runs at 48 kHz in 480-sample frames, so we resample 16 kHz -> 48 kHz,
denoise frame by frame, and resample back. The native library is vendored for
Windows; on platforms without it (or on any failure) audio passes through
unchanged so dictation always keeps working.
"""

import numpy as np

from . import settings

_denoiser = None
_unavailable = False


class _RnNoise:
    FRAME = 480  # RNNoise frame size at 48 kHz

    def __init__(self):
        from .vendor import rnnoise  # raises OSError if the native lib is missing

        self._rn = rnnoise
        self._state = rnnoise.create()

    def close(self):
        if self._state:
            self._rn.destroy(self._state)
            self._state = None

    def denoise(self, audio: np.ndarray) -> np.ndarray:
        if audio.size == 0:
            return audio
        # 16 kHz float32 -> 48 kHz (linear interp is plenty for speech)
        up = np.interp(
            np.arange(audio.size * 3) / 3.0,
            np.arange(audio.size),
            audio,
        ).astype(np.float32)
        pad = (-up.size) % self.FRAME
        if pad:
            up = np.pad(up, (0, pad))
        frames = up.reshape(-1, self.FRAME)
        out = np.empty_like(frames)
        for i, frame in enumerate(frames):
            pcm = np.clip(frame * 32767.0, -32768, 32767).astype(np.int16)
            denoised, _prob = self._rn.process_mono_frame(self._state, pcm)
            out[i] = denoised.astype(np.float32) / 32767.0
        flat = out.flatten()
        # 48 kHz -> 16 kHz, trimmed back to the original length
        return np.interp(
            np.arange(audio.size) * 3.0,
            np.arange(flat.size),
            flat,
        ).astype(np.float32)


def denoise_if_enabled(audio: np.ndarray) -> np.ndarray:
    """Suppress background noise when the toggle is on; never break dictation."""
    global _denoiser, _unavailable
    if _unavailable or not settings.get("noise_suppression", True):
        return audio
    try:
        if _denoiser is None:
            _denoiser = _RnNoise()
        return _denoiser.denoise(audio)
    except Exception:  # noqa: BLE001
        _unavailable = True
        return audio
