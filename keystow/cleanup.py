"""Remove unpacked copies that single-file builds left in the temp folder.

KeyStow 1.0.5 and earlier shipped as one self-extracting file. At every start
it unpacked the whole app, about 500 MB, into a `_MEI...` folder under the
user's temp directory, and it could not remove that folder when Windows shut
down, the installer closed the app, or the app crashed. Those folders are never
used again. Later versions are installed as ordinary files and unpack nothing.
"""

import os
import shutil
import sys
import tempfile

_DOOMED = ".keystow-remove"


def _is_keystow_unpack_dir(path: str) -> bool:
    """Only folders that are unmistakably an unpacked KeyStow are touched."""
    if not os.path.basename(path).startswith("_MEI"):
        return False
    if not os.path.isdir(os.path.join(path, "keystow", "vendor")):
        return False
    models = os.path.join(path, "models")
    try:
        return any(name.startswith("faster-whisper-") for name in os.listdir(models))
    except OSError:
        return False


def _in_use(path: str) -> bool:
    """True if a running program still has a library from this folder loaded.

    Windows allows a folder to be renamed, and most of it deleted, while a
    library inside it is loaded, so a rename alone would not protect a running
    copy. A loaded library cannot be opened for writing; that is the test.
    """
    for root, _dirs, files in os.walk(path):
        for name in files:
            if name.lower().endswith((".dll", ".pyd", ".exe")):
                try:
                    with open(os.path.join(root, name), "r+b"):
                        pass
                except OSError:
                    return True
    return False


def remove_leftover_unpack_dirs(temp_dir: str | None = None) -> int:
    """Delete leftover unpack folders on Windows; return how many were removed.

    A folder still in use is left alone, on two checks: no library in it may be
    loaded by a running program, and the rename below fails while any program
    holds a file inside it open.
    """
    if sys.platform != "win32":
        return 0
    temp_dir = temp_dir or tempfile.gettempdir()
    own = getattr(sys, "_MEIPASS", None)
    own = os.path.normcase(os.path.abspath(own)) if own else None
    try:
        names = os.listdir(temp_dir)
    except OSError:
        return 0
    removed = 0
    for name in names:
        path = os.path.join(temp_dir, name)
        try:
            if name.startswith("_MEI") and name.endswith(_DOOMED):
                # A removal that an earlier run started but could not finish.
                shutil.rmtree(path, ignore_errors=True)
                removed += not os.path.exists(path)
                continue
            if not _is_keystow_unpack_dir(path):
                continue
            if own and os.path.normcase(os.path.abspath(path)) == own:
                continue
            if _in_use(path):
                continue
            doomed = path + _DOOMED
            os.rename(path, doomed)
            shutil.rmtree(doomed, ignore_errors=True)
            removed += not os.path.exists(doomed)
        except OSError:
            continue
    return removed
