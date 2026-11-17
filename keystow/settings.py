"""Small JSON settings store in the per-user KeyStow data directory."""

import json
import os
import tempfile

from . import paths

_PATH = os.path.join(paths.data_dir(), "settings.json")


def _read() -> dict:
    try:
        with open(_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get(key: str, default=None):
    value = _read().get(key, default)
    # Known preferences must not let valid-but-wrong JSON types crash startup.
    if key == "hotkey" and (not isinstance(value, str) or not value):
        return default
    if key in {"noise_suppression", "autostart_initialized"} and not isinstance(value, bool):
        return default
    return value


def set(key: str, value) -> None:
    data = _read()
    data[key] = value
    directory = os.path.dirname(_PATH)
    os.makedirs(directory, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                         prefix=".settings-", delete=False) as f:
            temporary = f.name
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, _PATH)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
