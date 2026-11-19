import hashlib,importlib.util,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from keystow.numpy_guard import verify_dependency

class GuardTests(unittest.TestCase):
    def test_reviewed_source_passes(self):
        self.assertTrue((verify_dependency()/'audio.py').is_file())
    def test_loaded_dependency_refused(self):
        with patch.dict(sys.modules,{'faster_whisper':types.ModuleType('faster_whisper')}):
            with self.assertRaisesRegex(RuntimeError,'before'):verify_dependency()
    def test_child_module_bypass_refused(self):
        with patch.dict(sys.modules,{'faster_whisper.audio':types.ModuleType('faster_whisper.audio')}):
            with self.assertRaisesRegex(RuntimeError,'before'):verify_dependency()
    def test_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'audio.py').write_text('changed source')
            with patch('keystow.numpy_guard.importlib.util.find_spec',return_value=types.SimpleNamespace(submodule_search_locations=[d])):
                with self.assertRaisesRegex(RuntimeError,'Unreviewed'):verify_dependency()
    def test_missing_package_refused(self):
        with patch('keystow.numpy_guard.importlib.util.find_spec',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'unavailable'):verify_dependency()
    def test_ambiguous_package_refused(self):
        with patch('keystow.numpy_guard.importlib.util.find_spec',return_value=types.SimpleNamespace(submodule_search_locations=['a','b'])):
            with self.assertRaisesRegex(RuntimeError,'Ambiguous'):verify_dependency()
