"""Actual Qt tray-quit coordination while a real QThread is active."""
import os
import subprocess
import sys
import textwrap
import unittest


class ShutdownJourneyTest(unittest.TestCase):
    def test_tray_quit_waits_for_loading_and_keeps_controller_alive(self):
        script = textwrap.dedent('''
            from unittest.mock import patch
            from PySide6.QtCore import QThread, QTimer
            from PySide6.QtWidgets import QApplication
            from keystow import ui
            events = []
            class Worker(QThread):
                def run(self):
                    self.msleep(250)
            class Controller:
                def __init__(self, window):
                    self.window = window
                    self.worker = Worker()
                def start(self):
                    self.worker.start()
                    QTimer.singleShot(20, self.window.quit_requested.emit)
                    # Safety timeout is a failure, not a passing quit route.
                    QTimer.singleShot(2000, self.timeout)
                def timeout(self):
                    events.append("timeout")
                    QApplication.instance().quit()
                def shutdown(self):
                    events.append("closing")
                def can_exit(self):
                    events.append("checked")
                    return not self.worker.isRunning()
                def wait_for_shutdown(self):
                    events.append("finished" if not self.worker.isRunning() else "too early")
                    self.worker.wait()
            with patch.object(ui.autostart, "set_enabled"), \\
                 patch.object(ui.autostart, "is_enabled", return_value=False), \\
                 patch.object(ui.settings, "get", side_effect=lambda k,d=None:d), \\
                 patch.object(ui.settings, "set"):
                try:
                    ui.run_app(Controller)
                except SystemExit as exc:
                    assert exc.code == 0
            assert "closing" in events, events
            assert events[-1] == "finished", events
            assert "timeout" not in events and "too early" not in events, events
        ''')
        result = subprocess.run([sys.executable, '-c', script],
                                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
