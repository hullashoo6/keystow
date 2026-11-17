"""Tiny JSON settings store (~/.keystow/settings.json) for user preferences."""

import json
import os

from . import paths

_PATH = os.path.join(paths.data_dir(), "settings.json")


def _read() -> dict:
    try:
        with open(_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def get(key: str, default=None):
    return _read().get(key, default)


def set(key: str, value) -> None:
    data = _read()
    data[key] = value
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)
