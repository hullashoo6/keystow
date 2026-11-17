"""Real offscreen Qt control/state checks; not OS shortcut/paste coverage."""
import os
import subprocess
import sys
import textwrap
import unittest


class UiStateTest(unittest.TestCase):
    def test_controls_and_recovery_text_match_state(self):
        script = textwrap.dedent('''
            from unittest.mock import patch
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QApplication
            from keystow import ui
            app = QApplication([])
            with patch.object(ui.autostart, "set_enabled"), \\
                 patch.object(ui.autostart, "is_enabled", return_value=False), \\
                 patch.object(ui.settings, "get", side_effect=lambda k,d=None:d), \\
                 patch.object(ui.settings, "set"):
                window = ui.MainWindow()
                window.show()
                for recording,busy in [(False, True),(True, False),(False, False)]:
                    window.set_state("state under test", recording=recording, busy=busy)
                    app.processEvents()
                    assert window.record_btn.isEnabled() == (not busy)
                    assert window.model_box.isEnabled() == (not (recording or busy))
                    assert window.hotkey_box.isEnabled() == (not (recording or busy))
                    assert window._hotkey_group.isEnabled() == (not (recording or busy))
                assert window.transcript.textInteractionFlags() & Qt.TextSelectableByMouse
                window.set_model_selection("base")
                app.processEvents()
                assert window.model_box.currentText() == "base"
                window.set_hotkey_label("shift_r")
                app.processEvents()
                assert window.hotkey_box.currentData() == "shift_r"
                assert [a.text() for a in window._hotkey_group.actions() if a.isChecked()] == ["Right Shift"]
        ''')
        result = subprocess.run([sys.executable, '-c', script],
                                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
