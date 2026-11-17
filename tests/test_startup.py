"""Real Qt startup wiring check, without microphone/model/OS-hotkey claims.

Run with QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v.
Audio, model inference and keyboard integration are deliberately not exercised.
"""
import os
import subprocess
import sys
import textwrap
import unittest


class StartupTest(unittest.TestCase):
    def test_controller_starts_and_stays_alive_for_event_loop(self):
        script = textwrap.dedent('''
            import gc
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

            def verify():
                gc.collect()
                calls.append("alive" if refs[0]() is not None else "collected")
                QApplication.instance().quit()

            # Always leave the event loop, including on the broken baseline.
            original_exec = QApplication.exec
            def bounded_exec(app):
                QTimer.singleShot(100, verify)
                return original_exec()

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
            assert calls == ["started", "alive"], calls
        ''')
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        result = subprocess.run([sys.executable, "-c", script], env=env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
