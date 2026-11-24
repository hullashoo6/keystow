"""macOS keyboard plumbing that has to happen on the main thread.

pynput reads the keyboard layout through Carbon's Text Input Sources API from
whichever thread starts a Listener or creates a Controller. KeyStow starts its
listener on a background thread and pastes from the transcription thread.
Current macOS allows those calls only on the main thread and ends the process
otherwise (a trap in dispatch_assert_queue, reported as "quit unexpectedly").

So the layout is read once here, on the main thread, and pynput is handed that
snapshot; the Controller used for pasting is created here too. Nothing in this
module is imported or run on Windows beyond the platform checks.
"""

import contextlib
import logging
import sys
import threading

# kVK_ANSI_V: the physical V key. Sending the key code, instead of the letter
# "v", needs no layout lookup and pastes on every keyboard layout.
V_KEY_CODE = 0x09

_lock = threading.Lock()
_installed = False
_controller = None


def prepare() -> bool:
    """Read the keyboard layout on this (the main) thread and give it to pynput.

    Call once before the key listener starts. Returns True when pynput will no
    longer look the layout up on other threads. A failure is logged and leaves
    pynput as it was: the app still starts.
    """
    global _installed, _controller
    if sys.platform != "darwin":
        return False
    with _lock:
        if _installed:
            return True
        try:
            from pynput._util import darwin as util_darwin
            from pynput.keyboard import _darwin as keyboard_darwin

            with util_darwin.keycode_context() as context:
                snapshot = context

            @contextlib.contextmanager
            def cached_keycode_context():
                yield snapshot

            # Both modules hold their own reference to the function.
            util_darwin.keycode_context = cached_keycode_context
            keyboard_darwin.keycode_context = cached_keycode_context
            if snapshot[1] is None:
                # Some input methods have no Unicode layout data. pynput
                # would pass that missing layout to the system to build its
                # letter-to-key table. KeyStow pastes by key code and needs
                # no such table, so give pynput an empty one.
                util_darwin.get_unicode_to_keycode_map = dict
                keyboard_darwin.get_unicode_to_keycode_map = dict
            _installed = True
        except Exception:
            logging.exception("keyboard layout could not be read on the main thread")
            return False
        try:
            from pynput.keyboard import Controller

            _controller = Controller()
        except Exception:
            logging.exception("paste controller could not be created on the main thread")
        return True


def controller():
    """The Controller made on the main thread, or None if prepare() has not run."""
    return _controller


def paste_key():
    """The physical V key as a pynput key, or None when pynput is unavailable."""
    try:
        from pynput.keyboard import KeyCode

        return KeyCode.from_vk(V_KEY_CODE)
    except Exception:
        return None


def accessibility_trusted(prompt: bool = False):
    """Whether macOS lets this app watch and send keys (Accessibility).

    True or False when macOS answers; None when it cannot be asked, including
    on other systems. With prompt=True macOS shows its own dialog, with a
    button to the right settings pane, if access has not been given.
    """
    if sys.platform != "darwin":
        return None
    try:
        import HIServices

        if not prompt:
            return bool(HIServices.AXIsProcessTrusted())
        # The constant's value is this string; fall back to it if the name is
        # missing from the bindings.
        key = getattr(HIServices, "kAXTrustedCheckOptionPrompt", "AXTrustedCheckOptionPrompt")
        return bool(HIServices.AXIsProcessTrustedWithOptions({key: True}))
    except Exception:
        logging.exception("could not ask macOS about Accessibility access")
        return None
