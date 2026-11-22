"""Start at login is on by default. Real UI wiring, not OS login acceptance.

Windows: the installer's ticked option sets it, so the app never does at first
run. Mac: the installed app sets it once at first run. Source runs never do.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import patch


def load_autostart():
    source = Path(__file__).resolve().parents[1] / 'keystow' / 'autostart.py'
    spec = importlib.util.spec_from_file_location('autostart_policy_under_test', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AutostartDefaultPolicyTest(unittest.TestCase):
    def test_only_the_installed_mac_app_enables_itself(self):
        autostart = load_autostart()
        cases = [
            ('darwin', True, True),
            ('win32', True, False),    # the Windows installer asks instead
            ('darwin', False, False),  # a source run would register bare Python
            ('win32', False, False),
            ('linux', True, False),
        ]
        for platform, frozen, expected in cases:
            with self.subTest(platform=platform, frozen=frozen), \
                 patch.object(autostart.sys, 'platform', platform), \
                 patch.object(autostart.sys, 'frozen', frozen, create=True):
                self.assertIs(autostart.enable_by_default(), expected)


class AutostartFirstRunTest(unittest.TestCase):
    def run_script(self, script):
        result = subprocess.run([sys.executable, '-c', textwrap.dedent(script)],
                                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_first_run_leaves_the_choice_to_the_windows_installer(self):
        self.run_script('''
            from unittest.mock import patch
            from PySide6.QtWidgets import QApplication
            from keystow import ui
            app = QApplication([])
            with patch.object(ui.autostart, 'set_enabled') as register, \\
                 patch.object(ui.autostart, 'is_enabled', return_value=False), \\
                 patch.object(ui.autostart, 'enable_by_default', return_value=False), \\
                 patch.object(ui.settings, 'get', side_effect=lambda k,d=None:d), \\
                 patch.object(ui.settings, 'set') as save:
                window = ui.MainWindow()
                assert register.call_count == 0, register.call_args_list
                assert save.call_count == 0, save.call_args_list
                assert not window.autostart_action.isChecked()
        ''')

    def test_installed_mac_app_switches_it_on_at_first_run_and_off_stays_off(self):
        self.run_script('''
            from unittest.mock import patch
            from PySide6.QtWidgets import QApplication
            from keystow import ui
            app = QApplication([])
            state = {'on': False}
            saved = {}
            with patch.object(ui.autostart, 'set_enabled', side_effect=lambda value: state.update(on=value)) as register, \\
                 patch.object(ui.autostart, 'is_enabled', side_effect=lambda: state['on']), \\
                 patch.object(ui.autostart, 'enable_by_default', return_value=True), \\
                 patch.object(ui.settings, 'get', side_effect=lambda k,d=None: saved.get(k, d)), \\
                 patch.object(ui.settings, 'set', side_effect=lambda k,v: saved.__setitem__(k, v)):
                window = ui.MainWindow()
                register.assert_called_once_with(True)
                assert saved.get('autostart_initialized') is True, saved
                assert window.autostart_action.isChecked()
                window.autostart_action.trigger()
                assert state['on'] is False
                assert not window.autostart_action.isChecked()
                assert saved.get('autostart_initialized') is True, saved
        ''')

    def test_mac_later_runs_never_switch_it_back_on(self):
        self.run_script('''
            from unittest.mock import patch
            from PySide6.QtWidgets import QApplication
            from keystow import ui
            app = QApplication([])
            saved = {'autostart_initialized': True}
            with patch.object(ui.autostart, 'set_enabled') as register, \\
                 patch.object(ui.autostart, 'is_enabled', return_value=False), \\
                 patch.object(ui.autostart, 'enable_by_default', return_value=True), \\
                 patch.object(ui.settings, 'get', side_effect=lambda k,d=None: saved.get(k, d)), \\
                 patch.object(ui.settings, 'set'):
                window = ui.MainWindow()
                assert register.call_count == 0, register.call_args_list
                assert not window.autostart_action.isChecked()
        ''')

    def test_failed_first_registration_keeps_the_app_usable_and_retryable(self):
        self.run_script('''
            from unittest.mock import patch
            from PySide6.QtWidgets import QApplication
            from keystow import ui
            app = QApplication([])
            saved = {}
            with patch.object(ui.autostart, 'set_enabled', side_effect=OSError('registration denied')) as register, \\
                 patch.object(ui.autostart, 'is_enabled', return_value=False), \\
                 patch.object(ui.autostart, 'enable_by_default', return_value=True), \\
                 patch.object(ui.settings, 'get', side_effect=lambda k,d=None: saved.get(k, d)), \\
                 patch.object(ui.settings, 'set', side_effect=lambda k,v: saved.__setitem__(k, v)):
                window = ui.MainWindow()
                register.assert_called_once_with(True)
                assert 'autostart_initialized' not in saved, saved
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

    def test_installed_windows_app_registers_only_when_the_user_asks(self):
        self.run_script('''
            from unittest.mock import patch
            from PySide6.QtWidgets import QApplication
            from keystow import ui
            app = QApplication([])
            with patch.object(ui.autostart, 'set_enabled') as register, \\
                 patch.object(ui.autostart, 'is_enabled', return_value=False), \\
                 patch.object(ui.autostart, 'available', return_value=True), \\
                 patch.object(ui.autostart, 'enable_by_default', return_value=False), \\
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
