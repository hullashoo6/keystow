"""App data directory, with recoverable migration from ~/.murmur."""

import logging
import os
import shutil
import tempfile

_OLD = os.path.join(os.path.expanduser("~"), ".murmur")
_DIR = os.path.join(os.path.expanduser("~"), ".keystow")
# A failed migration must not split settings/stats/logs between directories.
# Keep using the legacy directory for this process; next launch retries.
_FALLBACK = None


def data_dir() -> str:
    """Migrate once without exposing a partial copy as the new data store.

    An existing destination always wins. If migration fails, the legacy store
    remains active for this process and is retried on the next launch.
    """
    global _FALLBACK
    identity = (_OLD, _DIR)
    if _FALLBACK == identity:
        return _OLD
    if not os.path.exists(_DIR) and os.path.isdir(_OLD):
        try:
            os.replace(_OLD, _DIR)
        except OSError:
            try:
                # Copy on the destination filesystem, then publish only the
                # complete directory. A failed copy leaves no partial _DIR.
                parent = os.path.dirname(_DIR)
                with tempfile.TemporaryDirectory(prefix=".keystow-migration-", dir=parent) as staging:
                    copied = os.path.join(staging, "data")
                    shutil.copytree(_OLD, copied)
                    # Never replace a destination another startup created.
                    if not os.path.exists(_DIR):
                        os.rename(copied, _DIR)
            except OSError:
                logging.exception("data migration failed; using legacy directory until restart")
                _FALLBACK = identity
                return _OLD
    os.makedirs(_DIR, exist_ok=True)
    return _DIR
