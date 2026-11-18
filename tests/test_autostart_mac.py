"""LaunchAgent file semantics under simulated darwin, not launchd acceptance."""
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch


def mac_module():
    source = Path(__file__).resolve().parents[1] / 'keystow' / 'autostart.py'
    spec = importlib.util.spec_from_file_location('autostart_mac_under_test', source)
    module = importlib.util.module_from_spec(spec)
    with patch('sys.platform', 'darwin'):
        spec.loader.exec_module(module)
    return module


class MacLoginFileTest(unittest.TestCase):
    def test_special_path_roundtrips_valid_plist(self):
        module = mac_module()
        with tempfile.TemporaryDirectory() as home:
            module._PLIST = str(Path(home) / 'agents' / 'keystow.plist')
            executable = '/Applications/Tools & Work/KeyStow.app/Contents/MacOS/KeyStow'
            with patch('sys.executable', executable):
                module.set_enabled(True)
            data = plistlib.loads(Path(module._PLIST).read_bytes())
            self.assertEqual(data['ProgramArguments'], [executable])
            self.assertTrue(data['RunAtLoad'])
            self.assertTrue(module.is_enabled())
            with patch('sys.executable', executable):
                module.set_enabled(True)
            self.assertEqual(plistlib.loads(Path(module._PLIST).read_bytes()), data)
            module.set_enabled(False)
            module.set_enabled(False)
            self.assertFalse(module.is_enabled())

    def test_write_failure_preserves_last_good_plist(self):
        import builtins
        module = mac_module()
        with tempfile.TemporaryDirectory() as home:
            module._PLIST = str(Path(home) / 'keystow.plist')
            original = plistlib.dumps({'Label':'com.keystow.app','ProgramArguments':['/old/KeyStow'],'RunAtLoad':True})
            Path(module._PLIST).write_bytes(original)
            real_open = builtins.open
            class Interrupted:
                def __enter__(self):
                    self.file = real_open(module._PLIST, 'w')
                    return self
                def write(self, data):
                    self.file.write(data[:20])
                    self.file.flush()
                    raise OSError('synthetic interrupted write')
                def __exit__(self, *args):
                    self.file.close()
            def open_file(path, mode='r', *args, **kwargs):
                if str(path) == module._PLIST and 'w' in mode:
                    return Interrupted()
                return real_open(path, mode, *args, **kwargs)
            # Direct destination writes must not happen. A staged writer can
            # complete normally and publish a new valid entry instead.
            with patch('builtins.open', side_effect=open_file):
                try:
                    module.set_enabled(True)
                except OSError:
                    pass
            raw = Path(module._PLIST).read_bytes()
            self.assertTrue(raw == original or plistlib.loads(raw)['Label'] == 'com.keystow.app')

    def test_publication_failure_preserves_last_good_plist(self):
        module = mac_module()
        with tempfile.TemporaryDirectory() as home:
            module._PLIST = str(Path(home) / 'keystow.plist')
            original = plistlib.dumps({'Label':'com.keystow.app','ProgramArguments':['/old/KeyStow'],'RunAtLoad':True})
            Path(module._PLIST).write_bytes(original)
            with patch.object(module.os, 'replace', side_effect=OSError('synthetic failed publish')):
                with self.assertRaises(OSError):
                    module.set_enabled(True)
            self.assertEqual(Path(module._PLIST).read_bytes(), original)
            self.assertEqual(sorted(p.name for p in Path(home).iterdir()), ['keystow.plist'])
            module.set_enabled(True)
            self.assertTrue(module.is_enabled())

    def test_invalid_file_is_not_reported_enabled(self):
        module = mac_module()
        with tempfile.TemporaryDirectory() as home:
            module._PLIST = str(Path(home) / 'keystow.plist')
            for data in [b'', b'<plist>', plistlib.dumps({}), plistlib.dumps({'Label':'another.app','ProgramArguments':['/app'],'RunAtLoad':True})]:
                Path(module._PLIST).write_bytes(data)
                self.assertFalse(module.is_enabled())
