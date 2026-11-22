"""Configuration, overridable via environment variables."""

import math
import os

# Whisper model size: tiny, base, small, medium, large-v3, turbo.
# "base" is bundled with the installer and is a good speed/accuracy tradeoff
# on CPU; "turbo" (large-v3-turbo) is the accuracy pick and downloads once.
MODEL_SIZE = os.environ.get("KEYSTOW_MODEL", "base")

# "cpu" works everywhere; use "cuda" with an NVIDIA GPU for big speedups.
DEVICE = os.environ.get("KEYSTOW_DEVICE", "cpu")

# "int8" keeps CPU inference fast; use "float16" on CUDA.
COMPUTE_TYPE = os.environ.get("KEYSTOW_COMPUTE_TYPE", "int8")

# Transcription language (None = auto-detect).
LANGUAGE = os.environ.get("KEYSTOW_LANGUAGE", "en")

# Hotkey (pynput key name). New/default installs hold to speak, release to type.
# KEYSTOW_TOGGLE=1 opts into toggle; 0 explicitly selects hold.
# settings.toggle_mode() also preserves existing explicit customizations.
HOTKEY = os.environ.get("KEYSTOW_HOTKEY", "ctrl_r")
TOGGLE_MODE = os.environ.get("KEYSTOW_TOGGLE", "0") != "0"

# Audio capture settings. 16 kHz mono is what Whisper expects.
SAMPLE_RATE = 16000
CHANNELS = 1


def _seconds(name: str, default: float) -> float:
    """Read a duration; a malformed value must not stop the app starting."""
    try:
        value = float(os.environ.get(name, default))
    except ValueError:
        return default
    return value if math.isfinite(value) and value >= 0 else default


# Captures shorter than this are treated as a stray tap of the key: nothing is
# transcribed or pasted. Set KEYSTOW_MIN_SECONDS=0 to disable.
MIN_RECORD_SECONDS = _seconds("KEYSTOW_MIN_SECONDS", 0.3)

# A recording left running is stopped and transcribed at this length, so a
# forgotten toggle cannot grow memory without bound. 0 disables the limit.
MAX_RECORD_SECONDS = _seconds("KEYSTOW_MAX_SECONDS", 120.0)
