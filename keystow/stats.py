"""Local word counts. Invalid files fall back safely; writes are atomic."""

import json
import os
import tempfile
import time

from . import paths

_PATH = os.path.join(paths.data_dir(), "stats.json")


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _read() -> dict:
    try:
        with open(_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        days = data.get("days", {})
        return {
            "total": _count(data.get("total", 0)),
            "days": {k: _count(v) for k,v in days.items()} if isinstance(days, dict) else {},
        }
    except (OSError, ValueError):
        return {}


def _write(data: dict) -> None:
    directory = os.path.dirname(_PATH)
    os.makedirs(directory, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                         prefix=".stats-", delete=False) as f:
            temporary = f.name
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, _PATH)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def add_words(count: int) -> None:
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
