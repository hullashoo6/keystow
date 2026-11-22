"""Per-platform defaults: the Mac key and its labels, and the sign-in command.

Simulated platforms, not real Mac hardware or a real sign-in.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, platform, environment=None):
    spec = importlib.util.spec_from_file_location(f'{name}_under_test_{platform}', ROOT / 'keystow' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    with patch('sys.platform', platform), patch.dict(os.environ, environment or {}):
        if not environment:
            os.environ.pop('KEYSTOW_HOTKEY', None)
        spec.loader.exec_module(module)
    return module


class DefaultKeyTest(unittest.TestCase):
    def test_mac_default_is_a_key_macbooks_have(self):
        self.assertEqual(load('config', 'darwin').HOTKEY, 'alt_r')

    def test_windows_default_is_unchanged(self):
        self.assertEqual(load('config', 'win32').HOTKEY, 'ctrl_r')

    def test_a_key_chosen_in_the_environment_still_wins(self):
        self.assertEqual(load('config', 'darwin', {'KEYSTOW_HOTKEY': 'shift_r'}).HOTKEY, 'shift_r')

    def test_mac_window_offers_mac_keys_with_mac_names(self):
        script = textwrap.dedent('''
            import sys
            from PySide6.QtWidgets import QApplication  # load Qt as the real platform
            real = sys.platform
            sys.platform = "darwin"
            try:
                from keystow import ui
            finally:
                sys.platform = real
            assert ui.HOTKEY_PRESETS[0] == ("Right Option", "alt_r"), ui.HOTKEY_PRESETS
            assert ("Right Command", "cmd_r") in ui.HOTKEY_PRESETS, ui.HOTKEY_PRESETS
            assert ("Right Shift", "shift_r") in ui.HOTKEY_PRESETS, ui.HOTKEY_PRESETS
            assert ui.hotkey_label("alt_r") == "Right Option"
            assert ui.config.HOTKEY == "alt_r", ui.config.HOTKEY
        ''')
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, QT_QPA_PLATFORM='offscreen', HOME=home, USERPROFILE=home)
            env.pop('KEYSTOW_HOTKEY', None)
            result = subprocess.run([sys.executable, '-c', script], env=env, cwd=str(ROOT),
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class SignInCommandTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32', 'the Windows sign-in entry')
    def test_windows_entry_asks_for_a_minimised_start(self):
        module = load('autostart', 'win32')
        with patch('sys.executable', r'C:\Apps\Key Stow\KeyStow.exe'):
            self.assertEqual(module._command(), r'"C:\Apps\Key Stow\KeyStow.exe" --startup')


if __name__ == '__main__':
    unittest.main()
