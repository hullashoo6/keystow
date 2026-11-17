"""Push-to-talk microphone recording."""

import threading

import numpy as np
import sounddevice as sd

from . import config


class PushToTalkRecorder:
    """Records microphone audio while the hotkey is held."""

    def __init__(self, sample_rate: int = config.SAMPLE_RATE, channels: int = config.CHANNELS):
        self.sample_rate = sample_rate
        self.channels = channels
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        """Begin capturing audio."""
        with self._lock:
            if self._recording:
                return
            self._frames = []
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
            self._recording = True

    def stop(self) -> np.ndarray:
        """Stop capturing and return the recorded audio as float32 mono."""
        with self._lock:
            self._recording = False
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            if not self._frames:
                return np.zeros(0, dtype="float32")
            return np.concatenate(self._frames, axis=0).flatten()

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        self._frames.append(indata.copy())
