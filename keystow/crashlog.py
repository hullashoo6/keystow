"""Persistent crash/error logging to ~/.keystow/logs/keystow.log.

Installed once at startup: captures unhandled exceptions (main thread and
worker threads) plus faulthandler tracebacks, so a silent crash leaves a
readable trace.
"""

import faulthandler
import logging
import logging.handlers
import os
import sys
import threading

from . import paths

_LOG_DIR = os.path.join(paths.data_dir(), "logs")


def setup() -> str:
    os.makedirs(_LOG_DIR, exist_ok=True)
    path = os.path.join(_LOG_DIR, "keystow.log")

    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    faulthandler.enable(open(path, "a", encoding="utf-8"))

    def _excepthook(exc_type, exc, tb):
        logging.critical("Unhandled exception", exc_info=(exc_type, exc, tb))

    def _thread_hook(args):
        logging.critical(
            "Unhandled exception in thread %s", args.thread, exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
        )

    sys.excepthook = _excepthook
    threading.excepthook = _thread_hook

    logging.info("KeyStow started (log: %s)", path)
    return path
