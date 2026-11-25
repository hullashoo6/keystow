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
                # Building the window must not open any other top-level window
                # (a stray one confused the packaged launch check).
                stray = [w for w in QApplication.topLevelWidgets() if w.isVisible()]
                assert stray == [], [type(w).__name__ for w in stray]
                window.show()
                for recording,busy in [(False, True),(True, False),(False, False)]:
                    window.set_state("state under test", recording=recording, busy=busy)
                    app.processEvents()
                    assert window.record_btn.isEnabled() == (not busy)
                    assert window.model_box.isEnabled() == (not (recording or busy))
                    assert window.hotkey_box.isEnabled() == (not (recording or busy))
                    assert window._hotkey_group.isEnabled() == (not (recording or busy))
                    assert window.mode_box.isEnabled() == (not (recording or busy))
                    # The state is named in words, never by colour alone.
                    assert window.badge.text() == ("Listening" if recording else "Working" if busy else "Ready")
                assert window.transcript.textInteractionFlags() & Qt.TextSelectableByMouse
                for text, word in [("Pasted. Hold Right Ctrl to speak again.", "Pasted"),
                                   ("You switched windows before the text was ready, so KeyStow did not paste it.", "Not pasted"),
                                   ("Paste sent, but KeyStow could not confirm the app took it.", "Check the text"),
                                   ("Your Mac is blocking the shortcut. Allow KeyStow under Accessibility.", "Needs permission")]:
                    window.set_state(text)
                    app.processEvents()
                    assert window.badge.text() == word, (text, window.badge.text())
                window.set_model_selection("base")
                app.processEvents()
                assert window.model_box.currentText() == ui.MODEL_LABELS["base"]
                window.set_mode(True)
                app.processEvents()
                assert window.mode_box.currentData() == "toggle" and window.record_btn.text() == "Click to talk"
                window.set_mode(False)
                app.processEvents()
                assert window.record_btn.text() == "Hold to talk"
                window.set_hotkey_label("shift_r")
                app.processEvents()
                assert window.hotkey_box.currentData() == "shift_r"
                assert [a.text() for a in window._hotkey_group.actions() if a.isChecked()] == ["Right Shift"]
        ''')
        result = subprocess.run([sys.executable, '-c', script],
                                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
