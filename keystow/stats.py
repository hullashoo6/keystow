"""Local-only word stats (~/.keystow/stats.json): words dictated, today + all time."""

import json
import os
import time

from . import paths

_PATH = os.path.join(paths.data_dir(), "stats.json")


def _read() -> dict:
    try:
        with open(_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write(data: dict) -> None:
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


def add_words(count: int) -> None:
    """Record *count* dictated words under today's date. Local only."""
    if count <= 0:
        return
    data = _read()
    day = time.strftime("%Y-%m-%d")
    days = data.get("days", {})
    days[day] = days.get(day, 0) + count
    data["days"] = days
    data["total"] = data.get("total", 0) + count
    _write(data)


def today() -> int:
    return _read().get("days", {}).get(time.strftime("%Y-%m-%d"), 0)


def total() -> int:
    return _read().get("total", 0)
