"""Request a paste into the currently focused application, with text recovery."""

import logging
import sys
import time

import pyperclip
from pynput.keyboard import Controller, Key

# How long the dictated text stays on the clipboard after the paste keys are
# sent, before the previous clipboard text is put back.
PASTE_SETTLE_SECONDS = 0.3


class PasteBlocked(RuntimeError):
    """The system will not let this app send keys; the text is on the clipboard."""

    left_on_clipboard = True

    def __init__(self, message: str, reason: str = "accessibility"):
        super().__init__(message)
        self.reason = reason


def _mac_input():
    """KeyStow's Mac keyboard helpers, or None when they cannot be loaded."""
    try:
        from keystow import mac_input

        return mac_input
    except Exception:
        return None


def type_text(text: str, restore_clipboard: bool = True) -> None:
    """Request clipboard paste, releasing owned keys even on dispatch failure.

    This cannot confirm the target accepted text or lock the focus. Restore
    prior text only if our temporary clipboard value is still there. Clipboard
    compare/write is best-effort, not an atomic OS transaction; non-text formats
    are not preserved by pyperclip.

    On a Mac without Accessibility access the keys would be dropped silently,
    so none are sent: the text is left on the clipboard and PasteBlocked says so.
    """
    if not text:
        return
    darwin = sys.platform == "darwin"
    mac = _mac_input() if darwin else None
    previous = None
    if restore_clipboard:
        try:
            previous = pyperclip.paste()
        except pyperclip.PyperclipException:
            previous = None

    pyperclip.copy(text)
    if mac is not None and mac.accessibility_trusted() is False:
        raise PasteBlocked("macOS is not letting KeyStow paste; the text is on the clipboard")
    if darwin and (mac is None or mac.controller() is None):
        # Creating a key Controller on this worker thread ends the app on
        # current macOS. Without the one made on the main thread, send nothing
        # and leave the text for the user to paste.
        raise PasteBlocked("KeyStow could not prepare its paste keys; the text is on the clipboard",
                           reason="no_controller")
    keyboard = None
    held = []
    try:
        # On a Mac, use the Controller made on the main thread and the physical
        # V key: creating a Controller or looking a letter up in the keyboard
        # layout on this worker thread ends the app on current macOS.
        keyboard = (mac.controller() if mac is not None else None) or Controller()
        letter = (mac.paste_key() if mac is not None else None) or "v"
        time.sleep(0.05)
        modifier = Key.cmd if sys.platform == "darwin" else Key.ctrl
        # Track before dispatch: an OS call can take effect and then raise.
        held.append(modifier)
        keyboard.press(modifier)
        held.append(letter)
        keyboard.press(letter)
        keyboard.release(letter)
        held.remove(letter)
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


class Delivered:
    """What is known about one delivery attempt (mirrors win_delivery.Result)."""

    def __init__(self, outcome: str, reason: str = "", restored: bool = False):
        self.outcome, self.reason, self.restored = outcome, reason, restored


def capture_target():
    """Remember the window in front when the user releases the key (Windows)."""
    if sys.platform == "win32":
        from keystow import win_delivery

        return win_delivery.capture_target()
    return None


def deliver(text: str, target):
    """Insert one dictation at most once and report the outcome.

    Windows uses read-confirmed delivery (win_delivery). Elsewhere the paste
    is requested as before and reported as "requested": nothing confirms it.
    """
    if sys.platform == "win32":
        from keystow import win_delivery

        return win_delivery.deliver(text, target)
    type_text(text)
    return Delivered("requested", restored=True)


def copy_text(text: str) -> bool:
    """The user's explicit "Copy": put the latest dictation on the clipboard."""
    if sys.platform == "win32":
        from keystow import win_delivery

        return win_delivery.copy_text(text)
    pyperclip.copy(text)
    return True
