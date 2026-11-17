"""Offline speech-to-text with faster-whisper."""

import numpy as np
from faster_whisper import WhisperModel

from . import config


class Transcriber:
    """Loads a local Whisper model and transcribes audio."""

    def __init__(
        self,
        model_size: str = config.MODEL_SIZE,
        device: str = config.DEVICE,
        compute_type: str = config.COMPUTE_TYPE,
        language: str | None = config.LANGUAGE,
    ):
        print(f"Loading Whisper model '{model_size}' on {device} (first run downloads it)...")
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self._language = language

    def transcribe(self, audio: np.ndarray) -> str:
        """Return the transcribed text for a float32 mono audio buffer."""
        if audio.size == 0:
            return ""
        segments, _info = self._model.transcribe(
            audio,
            language=self._language,
            beam_size=5,
            vad_filter=True,  # skip silence so pauses don't confuse the model
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
