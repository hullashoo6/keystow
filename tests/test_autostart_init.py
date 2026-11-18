"""Real UI first-run retry state, not OS login acceptance."""
import os
import subprocess
import sys
import textwrap
import unittest


class AutostartInitTest(unittest.TestCase):
    def test_failed_first_registration_retries_without_resetting_explicit_optout(self):
        script = textwrap.dedent('''
            from unittest.mock import patch, Mock
            from PySide6.QtWidgets import QApplication
            from keystow import ui
            app = QApplication([])
            saved = {}
            enabled = [False]
            def register(on):
                if register.calls == 0:
                    register.calls += 1
                    raise OSError('synthetic permission failure')
                register.calls += 1
                enabled[0] = on
            register.calls = 0
            with patch.object(ui.autostart, 'set_enabled', side_effect=register), \\
                 patch.object(ui.autostart, 'is_enabled', side_effect=lambda:enabled[0]), \\
                 patch.object(ui.settings, 'get', side_effect=lambda k,d=None:saved.get(k,d)), \\
                 patch.object(ui.settings, 'set', side_effect=lambda k,v:saved.__setitem__(k,v)):
                first = ui.MainWindow()
                assert not saved.get('autostart_initialized'), saved
                assert not first.autostart_action.isChecked()
                second = ui.MainWindow()
                assert register.calls == 2
                assert saved['autostart_initialized'] is True
                assert second.autostart_action.isChecked()
                enabled[0] = False  # later explicit opt-out must remain off
                third = ui.MainWindow()
                assert register.calls == 2
                assert not third.autostart_action.isChecked()
        ''')
        result = subprocess.run([sys.executable, '-c', script],
                                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
