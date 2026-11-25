"""RNNoise mic noise suppression, with graceful passthrough when unavailable.

RNNoise runs at 48 kHz in 480-sample frames, so we resample 16 kHz -> 48 kHz,
denoise frame by frame, and resample back. The native library is vendored for
Windows; on platforms without it (or on any failure) audio passes through
unchanged so dictation always keeps working.
"""

import ctypes
import logging
import queue
import threading

import numpy as np

from . import settings

_denoiser = None
_unavailable = False


class _RnNoise:
    FRAME = 480  # RNNoise frame size at 48 kHz

    def __init__(self):
        from .vendor import rnnoise  # raises OSError if the native lib is missing

        self._rn = rnnoise
        # A private handle to the native function taking raw addresses, so
        # each 10 ms frame costs one native call and no Python-side copies.
        # (Indexing the library returns a new function object; the wrapper's
        # own declaration is left untouched.)
        self._process = rnnoise.lib["rnnoise_process_frame"]
        self._process.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        self._process.restype = ctypes.c_float
        self._state = rnnoise.create()

    def close(self):
        if self._state:
            self._rn.destroy(self._state)
            self._state = None

    def denoise(self, audio: np.ndarray) -> np.ndarray:
        """Denoise 16 kHz float audio. Same result as frame-by-frame wrapping, much faster.

        The earlier loop converted every frame between float and 16-bit
        integers several times in Python; on a 2-core laptop that cost about
        five times more than RNNoise itself. Here the audio is converted once
        and RNNoise reads and writes slices of one buffer directly. Output is
        clipped to the 16-bit range instead of wrapping around on overflow.
        """
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
        flat = self.process_frames(up)
        # 48 kHz -> 16 kHz, trimmed back to the original length
        return np.interp(
            np.arange(audio.size) * 3.0,
            np.arange(flat.size),
            flat,
        ).astype(np.float32)

    def process_frames(self, up: np.ndarray) -> np.ndarray:
        """Denoise whole 480-sample frames of 48 kHz audio in [-1, 1]; same scale out."""
        # RNNoise works on floats at 16-bit scale; truncate as the int16 cast did.
        source = np.ascontiguousarray(np.trunc(np.clip(up * 32767.0, -32768, 32767)), dtype=np.float32)
        result = np.empty_like(source)
        process, state = self._process, self._state
        src, dst, step = source.ctypes.data, result.ctypes.data, self.FRAME * source.itemsize
        for offset in range(0, source.nbytes, step):
            process(state, dst + offset, src + offset)
        return (np.trunc(np.clip(result, -32768, 32767)) / 32767.0).astype(np.float32)


class Streaming:
    """Denoise while the user is still speaking.

    RNNoise costs about a quarter of one core in real time on a modest laptop,
    so doing it after the key is released added roughly a quarter of the
    recording's length to every wait. Fed from the microphone as audio
    arrives, it keeps up, and on release only the last moments remain. The
    result is the same as denoise() on the whole recording.
    """

    def __init__(self):
        self._engine = _RnNoise()
        self._queue = queue.SimpleQueue()
        self._pending = np.zeros(0, np.float32)   # 16 kHz samples kept as look-ahead
        self._carry = np.zeros(0, np.float32)     # 48 kHz samples short of a full frame
        self._out = []
        self._error = None
        self._done = False
        self._thread = threading.Thread(target=self._run, daemon=True, name="keystow-denoise")
        self._thread.start()

    def push(self, chunk) -> None:
        """Called from the audio callback: hand over and return at once."""
        if not self._done:
            self._queue.put(np.asarray(chunk, dtype=np.float32).reshape(-1))

    def _run(self):
        while True:
            chunk = self._queue.get()
            if chunk is None:
                return
            if self._error is None:
                try:
                    self._feed(chunk)
                except Exception as exc:  # noqa: BLE001 - reported by finish()
                    self._error = exc

    def _feed(self, chunk):
        x = np.concatenate([self._pending, chunk])
        known = x.size - 1  # samples whose right-hand neighbour has arrived
        if known <= 0:
            self._pending = x
            return
        up = np.interp(np.arange(known * 3) / 3.0, np.arange(x.size), x).astype(np.float32)
        self._pending = x[known:]
        self._emit(up)

    def _emit(self, up):
        buffer = np.concatenate([self._carry, up])
        whole = buffer.size - buffer.size % _RnNoise.FRAME
        if whole:
            self._out.append(self._engine.process_frames(buffer[:whole]))
        self._carry = buffer[whole:]

    def finish(self, samples: int) -> np.ndarray:
        """Wait for the backlog, denoise the tail and return 16 kHz audio."""
        self._stop()
        try:
            if self._error is not None:
                raise self._error
            x = self._pending
            tail = np.interp(np.arange(x.size * 3) / 3.0, np.arange(x.size), x).astype(np.float32)
            buffer = np.concatenate([self._carry, tail])
            pad = (-buffer.size) % _RnNoise.FRAME
            if pad:
                buffer = np.pad(buffer, (0, pad))
            if buffer.size:
                self._out.append(self._engine.process_frames(buffer))
            flat = np.concatenate(self._out) if self._out else np.zeros(0, np.float32)
            return flat[::3][:samples].astype(np.float32)
        finally:
            self._out = []
            self._engine.close()

    def cancel(self) -> None:
        """Discard everything; nothing is kept after a cancelled recording."""
        self._stop()
        self._out = []
        self._engine.close()

    def _stop(self):
        if not self._done:
            self._done = True
            self._queue.put(None)
            self._thread.join(timeout=10)


def start_streaming():
    """A Streaming denoiser for a new recording, or None when suppression is off or unavailable."""
    global _denoiser, _unavailable
    if _unavailable or not settings.get("noise_suppression", True):
        return None
    try:
        stream = Streaming()
        _denoiser = stream._engine
        return stream
    except Exception:  # noqa: BLE001
        logging.warning("noise suppression unavailable; audio is used as recorded", exc_info=True)
        _unavailable = True
        return None


def denoise_if_enabled(audio: np.ndarray) -> np.ndarray:
    """Suppress background noise when the toggle is on; never break dictation.

    Used when a recording was not denoised while it was captured (see
    Streaming). Every recording gets a fresh RNNoise state: one state kept
    for the life of the app (often days, since KeyStow starts at sign-in)
    carried the tail of one recording into the start of the next.
    """
    global _denoiser, _unavailable
    if _unavailable or not settings.get("noise_suppression", True):
        return audio
    try:
        engine = _RnNoise()
        try:
            cleaned = engine.denoise(audio)
        finally:
            engine.close()
        _denoiser = engine  # marks the native library as working (self-test, status)
        return cleaned
    except Exception:  # noqa: BLE001
        logging.warning("noise suppression unavailable; audio is used as recorded", exc_info=True)
        _unavailable = True
        return audio


def status() -> str:
    """"off", "unavailable", "active" or "untested" (not run yet this session)."""
    if not settings.get("noise_suppression", True):
        return "off"
    if _unavailable:
        return "unavailable"
    return "active" if _denoiser is not None else "untested"
