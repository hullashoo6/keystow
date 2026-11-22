"""Start at login is opt-in. Real UI wiring, not OS login acceptance."""
import os
import subprocess
import sys
import textwrap
import unittest


class AutostartOptInTest(unittest.TestCase):
    def run_script(self, script):
        result = subprocess.run([sys.executable, '-c', textwrap.dedent(script)],
                                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_first_run_never_registers_a_login_entry(self):
        self.run_script('''
            from unittest.mock import patch
            from PySide6.QtWidgets import QApplication
            from keystow import ui
            app = QApplication([])
            with patch.object(ui.autostart, 'set_enabled') as register, \\
                 patch.object(ui.autostart, 'is_enabled', return_value=False), \\
                 patch.object(ui.settings, 'get', side_effect=lambda k,d=None:d), \\
                 patch.object(ui.settings, 'set'):
                window = ui.MainWindow()
                assert register.call_count == 0, register.call_args_list
                assert not window.autostart_action.isChecked()
        ''')

    def test_source_run_cannot_register_the_python_interpreter(self):
        self.run_script('''
            from unittest.mock import patch
            from PySide6.QtWidgets import QApplication
            from keystow import ui
            app = QApplication([])
            with patch.object(ui.autostart, 'set_enabled') as register, \\
                 patch.object(ui.autostart, 'is_enabled', return_value=False), \\
                 patch.object(ui.autostart, 'available', return_value=False), \\
                 patch.object(ui.settings, 'get', side_effect=lambda k,d=None:d), \\
                 patch.object(ui.settings, 'set'):
                window = ui.MainWindow()
                window.autostart_action.trigger()
                assert register.call_count == 0, register.call_args_list
                assert not window.autostart_action.isChecked()
        ''')

    def test_installed_app_registers_only_when_the_user_asks(self):
        self.run_script('''
            from unittest.mock import patch
            from PySide6.QtWidgets import QApplication
            from keystow import ui
            app = QApplication([])
            with patch.object(ui.autostart, 'set_enabled') as register, \\
                 patch.object(ui.autostart, 'is_enabled', return_value=False), \\
                 patch.object(ui.autostart, 'available', return_value=True), \\
                 patch.object(ui.settings, 'get', side_effect=lambda k,d=None:d), \\
                 patch.object(ui.settings, 'set'):
                window = ui.MainWindow()
                assert register.call_count == 0
                window.autostart_action.trigger()
                register.assert_called_once_with(True)
                assert window.autostart_action.isChecked()
        ''')

    def test_existing_entry_can_always_be_switched_off(self):
        self.run_script('''
            from unittest.mock import patch
            from PySide6.QtWidgets import QApplication
            from keystow import ui
            app = QApplication([])
            with patch.object(ui.autostart, 'set_enabled') as register, \\
                 patch.object(ui.autostart, 'is_enabled', return_value=True), \\
                 patch.object(ui.autostart, 'available', return_value=False), \\
                 patch.object(ui.settings, 'get', side_effect=lambda k,d=None:d), \\
                 patch.object(ui.settings, 'set'):
                window = ui.MainWindow()
                assert window.autostart_action.isChecked()
                window.autostart_action.trigger()
                register.assert_called_once_with(False)
                assert not window.autostart_action.isChecked()
        ''')
