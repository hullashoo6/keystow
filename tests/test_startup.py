"""Real Qt startup wiring check, without microphone/model/OS-hotkey claims.

Run with QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v.
Audio, model inference and keyboard integration are deliberately not exercised.
"""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest


SCRIPT = textwrap.dedent('''
    import gc
    import sys
    import tempfile
    import weakref
    from unittest.mock import patch
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from keystow import ui

    calls = []
    refs = []
    class Controller:
        def __init__(self, window):
            self.window = window
            refs.append(weakref.ref(self))
        def start(self):
            calls.append("started")
            self.window.set_state("Ready for startup wiring check.")
        def shutdown(self):
            pass
        def can_exit(self):
            return True
        def wait_for_shutdown(self):
            pass

    def verify():
        gc.collect()
        controller = refs[0]()
        calls.append("alive" if controller is not None else "collected")
        if controller is not None:
            calls.append("minimised" if controller.window.isMinimized() else "shown")
        QApplication.instance().quit()

    # Always leave the event loop, including on the broken baseline.
    original_exec = QApplication.exec
    def bounded_exec(app):
        QTimer.singleShot(100, verify)
        return original_exec()

    sys.argv = __ARGV__
    with tempfile.TemporaryDirectory() as home, \\
         patch.object(ui.autostart, "set_enabled"), \\
         patch.object(ui.autostart, "is_enabled", return_value=False), \\
         patch.object(ui.settings, "get", side_effect=lambda k, d=None: d), \\
         patch.object(ui.settings, "set"), \\
         patch.object(QApplication, "exec", bounded_exec):
        try:
            ui.run_app(Controller)
        except SystemExit as exc:
            assert exc.code == 0, exc.code
    assert calls == ["started", "alive", __WINDOW__], calls
''')


class StartupTest(unittest.TestCase):
    def run_app(self, arguments, window):
        script = SCRIPT.replace('__ARGV__', repr(arguments)).replace('__WINDOW__', repr(window))
        # Use a private home: with the real one, a KeyStow already running on
        # this machine owns the single-instance lock, the app under test exits
        # at once, and the running copy is asked to raise its window.
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", HOME=home, USERPROFILE=home)
            result = subprocess.run([sys.executable, "-c", script], env=env,
                                    capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_controller_starts_and_stays_alive_for_event_loop(self):
        self.run_app(["KeyStow"], "shown")

    def test_start_from_the_sign_in_entry_is_minimised(self):
        self.run_app(["KeyStow", "--startup"], "minimised")


if __name__ == "__main__":
    unittest.main()
