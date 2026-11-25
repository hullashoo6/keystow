"""Offline speech-to-text with faster-whisper."""

import logging
import os
import sys
import time

import numpy as np
from faster_whisper import WhisperModel

from . import config, denoise


# The model that ships inside the installer.
BUNDLED_MODEL = "base"


class ModelMissing(RuntimeError):
    """The installed app's built-in model is gone or damaged."""


class ModelNotDownloaded(RuntimeError):
    """An optional model is not on this computer yet; downloading needs consent."""


def _resolve_model(model_size: str) -> str:
    """Use the Whisper model bundled in the installer when available.

    In the installed app the built-in model must come from the app itself.
    Falling back to a name here would make faster-whisper download it from
    the internet without anyone having asked, so say what is wrong instead.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        bundled = os.path.join(base, "models", f"faster-whisper-{model_size}")
        if os.path.isfile(os.path.join(bundled, "model.bin")):
            return bundled
        if model_size == BUNDLED_MODEL:
            raise ModelMissing("KeyStow's built-in speech model is missing or damaged. "
                               "Reinstall KeyStow to repair it; your settings are kept.")
    return model_size


def model_cached(model_size: str) -> bool:
    """Whether a model can load right now without the internet. Makes no network call."""
    try:
        source = _resolve_model(model_size)
    except ModelMissing:
        return False
    if os.path.isdir(source):
        return True
    try:
        from faster_whisper.utils import download_model

        download_model(source, local_files_only=True)
        return True
    except Exception:  # noqa: BLE001 - absent or incomplete in the cache
        return False


class Transcriber:
    """Loads a local Whisper model and transcribes audio."""

    def __init__(
        self,
        model_size: str = config.MODEL_SIZE,
        device: str = config.DEVICE,
        compute_type: str = config.COMPUTE_TYPE,
        language: str | None = config.LANGUAGE,
        allow_download: bool | None = None,
    ):
        source = _resolve_model(model_size)
        if allow_download is None:
            # Run from source, the first start fetches the model (documented).
            # The installed app downloads only after the user agreed to it.
            allow_download = not getattr(sys, "frozen", False)
        self.last_timings = {}
        try:
            # Prefer what is already on this computer: no network at all.
            self._model = WhisperModel(source, device=device, compute_type=compute_type,
                                       local_files_only=True)
        except Exception:
            if os.path.isdir(source):
                raise  # a local folder that will not load: report the real error
            if not allow_download:
                raise ModelNotDownloaded(f"The '{model_size}' model is not on this computer yet.")
            logging.info("downloading speech model '%s' after the user chose it", model_size)
            self._model = WhisperModel(source, device=device, compute_type=compute_type)
        self._language = language

    def transcribe(self, audio: np.ndarray, denoised: np.ndarray | None = None) -> str:
        """Return the transcribed text for a float32 mono audio buffer.

        Every utterance is transcribed independently: no context from previous
        dictations (which snowballs one mistake into garbage), VAD filters
        silence/background noise, and low-confidence segments are dropped
        instead of typed.

        denoised: the same audio already noise-suppressed while it was being
        recorded; when given, the denoising step is skipped here.
        """
        if audio.size == 0:
            return ""
        started = time.perf_counter()
        if denoised is not None and denoised.size == audio.size:
            audio = denoised
        else:
            audio = denoise.denoise_if_enabled(audio)  # strip fan/ground noise first
        ready = time.perf_counter()
        text = self._recognise(audio)
        self.last_timings = {"denoise": (ready - started) * 1000.0,
                             "infer": (time.perf_counter() - ready) * 1000.0}
        return text

    def _recognise(self, audio: np.ndarray) -> str:
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
