"""Request a paste into the currently focused application, with text recovery."""

import logging
import sys
import time

import pyperclip
from pynput.keyboard import Controller, Key

# How long the dictated text stays on the clipboard after the paste keys are
# sent, before the previous clipboard text is put back.
PASTE_SETTLE_SECONDS = 0.3


def type_text(text: str, restore_clipboard: bool = True) -> None:
    """Request clipboard paste, releasing owned keys even on dispatch failure.

    This cannot confirm the target accepted text or lock the focus. Restore
    prior text only if our temporary clipboard value is still there. Clipboard
    compare/write is best-effort, not an atomic OS transaction; non-text formats
    are not preserved by pyperclip.
    """
    if not text:
        return
    previous = None
    if restore_clipboard:
        try:
            previous = pyperclip.paste()
        except pyperclip.PyperclipException:
            previous = None

    pyperclip.copy(text)
    keyboard = None
    held = []
    try:
        keyboard = Controller()
        time.sleep(0.05)
        modifier = Key.cmd if sys.platform == "darwin" else Key.ctrl
        # Track before dispatch: an OS call can take effect and then raise.
        held.append(modifier)
        keyboard.press(modifier)
        held.append("v")
        keyboard.press("v")
        keyboard.release("v")
        held.remove("v")
        keyboard.release(modifier)
        held.remove(modifier)
        # The target app reads the clipboard when it handles the keystroke,
        # not when we send it. Restoring sooner makes slower apps (Electron,
        # browsers, remote desktops) paste the previous clipboard instead.
        time.sleep(PASTE_SETTLE_SECONDS)
    finally:
        cleanup_error = None
        for key in reversed(held):
            try:
                keyboard.release(key)
            except Exception as exc:
                logging.exception("paste key cleanup failed")
                cleanup_error = exc
        try:
            if previous is not None and pyperclip.paste() == text:
                pyperclip.copy(previous)
        except Exception as exc:
            logging.exception("clipboard text restoration failed")
            cleanup_error = exc
        # Do not mask the original dispatch failure with a cleanup failure.
        if cleanup_error is not None and sys.exc_info()[0] is None:
            raise RuntimeError("Paste requested, but clipboard/key cleanup failed; transcript remains available") from cleanup_error
