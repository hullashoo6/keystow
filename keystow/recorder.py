"""Microphone capture with explicit ownership and cleanup of each stream."""

import logging
import threading

import numpy as np
import sounddevice as sd

from . import config


class PushToTalkRecorder:
    # start() accepts a sink that receives each block of audio as it arrives.
    supports_sink = True

    def __init__(self, sample_rate: int = config.SAMPLE_RATE, channels: int = config.CHANNELS):
        self.sample_rate = sample_rate
        self.channels = channels
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._recording = False
        self._sink = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self, sink=None) -> None:
        with self._lock:
            if self._recording:
                return
            self._frames = []
            self._sink = sink
            stream = sd.InputStream(samplerate=self.sample_rate,
                                    channels=self.channels, dtype="float32",
                                    callback=self._callback)
            try:
                stream.start()
            except Exception:
                # Creating a PortAudio stream can succeed before activation
                # fails. It is still ours to close, even on this error path.
                try:
                    stream.close()
                except Exception:
                    logging.exception("microphone cleanup after failed start")
                self._stream = None
                self._frames = []
                raise
            self._stream = stream
            self._recording = True

    def stop(self) -> np.ndarray:
        with self._lock:
            self._recording = False
            stream, self._stream = self._stream, None
            try:
                if stream is not None:
                    try:
                        stream.stop()
                    finally:
                        stream.close()
                if not self._frames:
                    return np.zeros(0, dtype="float32")
                return np.concatenate(self._frames, axis=0).flatten()
            finally:
                # Do not retain audio after delivery, failure or explicit quit.
                self._frames = []
                self._sink = None

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        block = indata.copy()
        self._frames.append(block)
        sink = self._sink
        if sink is not None:
            try:
                sink(block if self.channels == 1 else block.mean(axis=1))
            except Exception:  # noqa: BLE001 - the recording itself must go on
                self._sink = None
