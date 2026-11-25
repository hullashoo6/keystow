"""Opt-in timing diagnostics: how long each step of a dictation took.

Off by default. Turn on with the environment variable KEYSTOW_TIMINGS=1, or
"diagnostic_timings": true in settings.json; turn off by removing either.
Each dictation adds one log line with step durations in milliseconds, a
counter that restarts with the app, and the delivery outcome. Never the
dictated text, the clipboard, window titles or keystrokes.
"""

import itertools
import logging
import os
import time

from . import settings

_counter = itertools.count(1)


def enabled() -> bool:
    if os.environ.get("KEYSTOW_TIMINGS") == "1":
        return True
    try:
        return settings.get("diagnostic_timings") is True
    except Exception:  # noqa: BLE001 - diagnostics must never break dictation
        return False


class Dictation:
    """Marks for one dictation; logs a single line when finished, if enabled."""

    def __init__(self):
        self.on = enabled()
        self.number = next(_counter)
        self._last = time.perf_counter()
        self.steps = []

    def mark(self, step: str) -> None:
        now = time.perf_counter()
        self.steps.append((step, (now - self._last) * 1000.0))
        self._last = now

    def finish(self, **facts) -> None:
        if not self.on:
            return
        parts = [f"{name}={ms:.0f}ms" for name, ms in self.steps]
        parts += [f"{k}={v}" for k, v in sorted(facts.items()) if isinstance(v, (int, float, bool, str))]
        logging.info("timing #%d %s", self.number, " ".join(parts))
