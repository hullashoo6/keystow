"""Configuration, overridable via environment variables."""

import os

# Whisper model size: tiny, base, small, medium, large-v3.
# "base" is a good speed/accuracy tradeoff for English on CPU.
MODEL_SIZE = os.environ.get("WISPR_MODEL", "base")

# "cpu" works everywhere; use "cuda" with an NVIDIA GPU for big speedups.
DEVICE = os.environ.get("WISPR_DEVICE", "cpu")

# "int8" keeps CPU inference fast; use "float16" on CUDA.
COMPUTE_TYPE = os.environ.get("WISPR_COMPUTE_TYPE", "int8")

# Transcription language (None = auto-detect).
LANGUAGE = os.environ.get("WISPR_LANGUAGE", "en")

# Push-to-talk hotkey (pynput key name). Hold to record, release to type.
HOTKEY = os.environ.get("WISPR_HOTKEY", "ctrl_r")

# Audio capture settings. 16 kHz mono is what Whisper expects.
SAMPLE_RATE = 16000
CHANNELS = 1
