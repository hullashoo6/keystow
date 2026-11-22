"""Leftover unpack-folder removal against real temporary folders.

The in-use protection relies on a Windows rule, so those cases run on Windows
only. No real temp directory or installed KeyStow is touched.
"""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


def load():
    source = Path(__file__).resolve().parents[1] / 'keystow' / 'cleanup.py'
    spec = importlib.util.spec_from_file_location('cleanup_under_test', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def remove_with_retries(path, seconds=10):
    deadline = time.monotonic() + seconds
    while os.path.exists(path) and time.monotonic() < deadline:
        shutil.rmtree(path, ignore_errors=True)
        if os.path.exists(path):
            time.sleep(0.25)


def unpack_dir(root, name, keystow=True, model=True):
    base = Path(root) / name
    base.mkdir(parents=True)
    if keystow:
        (base / 'keystow' / 'vendor').mkdir(parents=True)
        (base / 'keystow' / 'vendor' / 'rnnoise.dll').write_bytes(b'library')
    if model:
        (base / 'models' / 'faster-whisper-base').mkdir(parents=True)
        (base / 'models' / 'faster-whisper-base' / 'model.bin').write_bytes(b'model')
    return base


class CleanupTest(unittest.TestCase):
    def test_other_systems_are_left_alone(self):
        module = load()
        with tempfile.TemporaryDirectory() as temp:
            folder = unpack_dir(temp, '_MEI111')
            with patch.object(module.sys, 'platform', 'darwin'):
                self.assertEqual(module.remove_leftover_unpack_dirs(temp), 0)
            self.assertTrue(folder.exists())

    def test_missing_temp_directory_is_not_an_error(self):
        module = load()
        with patch.object(module.sys, 'platform', 'win32'):
            self.assertEqual(module.remove_leftover_unpack_dirs(os.path.join(tempfile.gettempdir(), 'keystow-no-such-dir')), 0)

    @unittest.skipUnless(sys.platform == 'win32', 'relies on the Windows open-file rename rule')
    def test_removes_only_abandoned_keystow_folders(self):
        module = load()
        with tempfile.TemporaryDirectory() as temp:
            abandoned = unpack_dir(temp, '_MEI111')
            another_program = unpack_dir(temp, '_MEI222', keystow=False)
            wrong_name = unpack_dir(temp, 'KeyStowBackup')
            open_file = unpack_dir(temp, '_MEI333')
            unfinished = Path(temp) / '_MEI444.keystow-remove'
            unfinished.mkdir()
            (unfinished / 'part').write_bytes(b'x')
            with open(open_file / 'keystow' / 'vendor' / 'rnnoise.dll', 'rb'):
                removed = module.remove_leftover_unpack_dirs(temp)
            self.assertEqual(removed, 2)
            self.assertFalse(abandoned.exists())
            self.assertFalse(unfinished.exists())
            self.assertTrue((another_program / 'models' / 'faster-whisper-base' / 'model.bin').exists())
            self.assertTrue((wrong_name / 'keystow' / 'vendor' / 'rnnoise.dll').exists())
            self.assertTrue((open_file / 'models' / 'faster-whisper-base' / 'model.bin').exists())

    @unittest.skipUnless(sys.platform == 'win32', 'relies on the Windows open-file rename rule')
    def test_folder_with_a_library_loaded_by_a_running_program_is_kept(self):
        module = load()
        system_library = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'version.dll'
        if not system_library.exists():
            self.skipTest('no system library to load')
        # Windows can keep a just-unloaded library locked for a moment after
        # its process ends, so this folder is removed with retries afterwards
        # instead of by a context manager that would fail the test on teardown.
        temp = tempfile.mkdtemp()
        self.addCleanup(remove_with_retries, temp)
        running = unpack_dir(temp, '_MEI555')
        library = running / 'keystow' / 'vendor' / 'loaded.dll'
        shutil.copyfile(system_library, library)
        holder = subprocess.Popen(
            [sys.executable, '-c',
             "import ctypes,sys,time; ctypes.WinDLL(sys.argv[1]); print('loaded', flush=True); time.sleep(60)",
             str(library)],
            stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), 'loaded')
            self.assertEqual(module.remove_leftover_unpack_dirs(temp), 0)
            self.assertTrue(library.exists())
            self.assertTrue((running / 'models' / 'faster-whisper-base' / 'model.bin').exists())
        finally:
            holder.kill()
            holder.wait(timeout=10)
            holder.stdout.close()

    @unittest.skipUnless(sys.platform == 'win32', 'relies on the Windows open-file rename rule')
    def test_a_single_file_build_never_removes_its_own_folder(self):
        module = load()
        with tempfile.TemporaryDirectory() as temp:
            own = unpack_dir(temp, '_MEI666')
            with patch.object(module.sys, '_MEIPASS', str(own), create=True):
                self.assertEqual(module.remove_leftover_unpack_dirs(temp), 0)
            self.assertTrue(own.exists())


if __name__ == '__main__':
    unittest.main()
