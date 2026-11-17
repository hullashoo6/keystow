"""Offline speech-to-text with faster-whisper."""

import os
import sys

import numpy as np
from faster_whisper import WhisperModel

from . import config


def _resolve_model(model_size: str) -> str:
    """Use the Whisper model bundled in the installer when available."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        bundled = os.path.join(base, "models", f"faster-whisper-{model_size}")
        if os.path.isdir(bundled):
            return bundled
    return model_size


class Transcriber:
    """Loads a local Whisper model and transcribes audio."""

    def __init__(
        self,
        model_size: str = config.MODEL_SIZE,
        device: str = config.DEVICE,
        compute_type: str = config.COMPUTE_TYPE,
        language: str | None = config.LANGUAGE,
    ):
        source = _resolve_model(model_size)
        print(f"Loading Whisper model '{source}' on {device} (downloads once if not bundled)...")
        self._model = WhisperModel(source, device=device, compute_type=compute_type)
        self._language = language

    def transcribe(self, audio: np.ndarray) -> str:
        """Return the transcribed text for a float32 mono audio buffer.

        Every utterance is transcribed independently: no context from previous
        dictations (which snowballs one mistake into garbage), VAD filters
        silence/background noise, and low-confidence segments are dropped
        instead of typed.
        """
        if audio.size == 0:
            return ""
        segments, _info = self._model.transcribe(
            audio,
            language=self._language,
            beam_size=5,
            condition_on_previous_text=False,  # each dictation stands alone
            vad_filter=True,  # skip silence so pauses/noise don't confuse the model
            vad_parameters={"min_silence_duration_ms": 500},
        )
        kept = []
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            # Hallucination guards: drop noise-as-speech and degenerate output.
            if segment.no_speech_prob > 0.6:
                continue
            if segment.compression_ratio > 2.4:
                continue
            if segment.avg_logprob < -1.0:
                continue
            kept.append(text)
        return " ".join(kept).strip()
