"""App data directory (~/.keystow), with one-time migration from ~/.murmur."""

import os
import shutil

_OLD = os.path.join(os.path.expanduser("~"), ".murmur")
_DIR = os.path.join(os.path.expanduser("~"), ".keystow")


def data_dir() -> str:
    """Return ~/.keystow, migrating an existing ~/.murmur on first run."""
    if not os.path.exists(_DIR) and os.path.isdir(_OLD):
        try:
            os.replace(_OLD, _DIR)
        except OSError:
            try:
                shutil.copytree(_OLD, _DIR)
            except OSError:
                pass
    os.makedirs(_DIR, exist_ok=True)
    return _DIR
