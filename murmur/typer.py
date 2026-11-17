"""Type text into whatever application currently has focus."""

import time

import pyperclip
from pynput.keyboard import Controller, Key


def type_text(text: str, restore_clipboard: bool = True) -> None:
    """Paste *text* into the active window via the clipboard.

    Clipboard paste is used instead of simulated keystrokes because it is
    instant and handles punctuation, capitals and Unicode reliably.
    The previous clipboard contents are restored afterwards.
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
    keyboard = Controller()
    time.sleep(0.05)  # let the clipboard settle
    keyboard.press(Key.ctrl)
    keyboard.press("v")
    keyboard.release("v")
    keyboard.release(Key.ctrl)
    time.sleep(0.05)

    if previous is not None:
        pyperclip.copy(previous)
