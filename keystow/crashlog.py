"""Best-effort diagnostic logging; an unavailable log must not block startup."""

import faulthandler
import logging
import logging.handlers
import os
import sys
import threading

from . import paths

_LOG_DIR = os.path.join(paths.data_dir(), "logs")
_handler = None
_fault_file = None


def setup() -> str | None:
    """Install once, or return None if local log storage is unavailable.

    Never silently redirect diagnostics into an unexpected shared directory.
    Failure to enable native fault traces does not disable ordinary logging.
    """
    global _handler, _fault_file
    if _handler is not None:
        return _handler.baseFilename
    path = os.path.join(_LOG_DIR, "keystow.log")
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
    except OSError:
        logging.warning("Diagnostic file logging unavailable; continuing without a log file")
        return None
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    # The speech library logs a line with the audio length for every
    # dictation. That is a record of when and how long the user spoke, which
    # the log must not keep; its warnings and errors still get through.
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    _handler = handler

    fault_file = None
    try:
        fault_file = open(path, "a", encoding="utf-8")
        faulthandler.enable(fault_file)
        # Keep an explicit owner alive for as long as native tracing uses it.
        _fault_file = fault_file
    except (OSError, RuntimeError):
        if fault_file is not None:
            fault_file.close()
        logging.warning("Native fault traces unavailable; ordinary logging remains enabled")

    def _excepthook(exc_type, exc, tb):
        logging.critical("Unhandled exception", exc_info=(exc_type, exc, tb))

    def _thread_hook(args):
        logging.critical("Unhandled worker exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = _excepthook
    threading.excepthook = _thread_hook
    logging.info("KeyStow started")
    return path
