import importlib.metadata as md
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('reconcile', BASE/'installer/reconcile_metadata.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class MetadataContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = Path(os.environ['KEYSTOW_PRISTINE_METADATA']).read_text() if 'KEYSTOW_PRISTINE_METADATA' in os.environ else md.distribution('faster-whisper').read_text('METADATA')
        cls.new = ''.join(line for line in cls.old.splitlines(keepends=True) if line.strip() != 'Requires-Dist: av>=11')
        cls.pristine = Path(os.environ['KEYSTOW_PRISTINE_PACKAGE']) if 'KEYSTOW_PRISTINE_PACKAGE' in os.environ else Path(md.distribution('faster-whisper').locate_file('faster_whisper'))
        cls._temp = tempfile.TemporaryDirectory()
        cls.adapted = Path(cls._temp.name)/'faster_whisper'
        shutil.copytree(cls.pristine,cls.adapted)
        sys.path.insert(0,str(BASE/'installer'))
        from guarded_source import guarded_audio_source
        (cls.adapted/'audio.py').write_text(guarded_audio_source('1.2.1',(cls.pristine/'audio.py').read_bytes(),(cls.pristine/'transcribe.py').read_bytes()),encoding='utf-8',newline='')
    @classmethod
    def tearDownClass(cls):
        cls._temp.cleanup()
    def run_contract(self, new=None, **kwargs):
        args = dict(pristine_text=self.old, proposed_text=self.new if new is None else new,
                    pristine_root=self.pristine, adapted_root=self.adapted, boundary=dict(m.BOUNDARY))
        args.update(kwargs)
        return m.reconcile(**args)
    def test_valid_review_only(self):
        report = self.run_contract()
        self.assertFalse(report['installable_distribution_proven'])
        self.assertEqual(len(report['preserved_requirements']), 10)
    def test_non_av_constraint_change(self):
        with self.assertRaisesRegex(ValueError, 'Non-PyAV'):
            self.run_contract(self.new.replace('ctranslate2<5,>=4.0', 'ctranslate2>=4.0'))
    def test_av_reintroduced(self):
        with self.assertRaisesRegex(ValueError, 'still requires PyAV'):
            self.run_contract(self.old)
    def test_missing_metadata(self):
        with self.assertRaisesRegex(ValueError, 'metadata field'):
            self.run_contract('')
    def test_duplicate_requirement(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate requirement'):
            self.run_contract(self.new.replace('Requires-Dist: tqdm', 'Requires-Dist: tqdm\nRequires-Dist: tqdm'))
    def test_new_dependency(self):
        with self.assertRaisesRegex(ValueError, 'Non-PyAV'):
            self.run_contract(self.new.replace('Requires-Dist: tqdm', 'Requires-Dist: tqdm\nRequires-Dist: unexpected-package'))
    def test_python_compatibility_change(self):
        with self.assertRaisesRegex(ValueError, 'Nondependency'):
            self.run_contract(self.new.replace('Requires-Python: >=3.9', 'Requires-Python: >=3.10'))
    def test_adapted_source_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'audio.py').write_text('wrong source')
            with self.assertRaisesRegex(ValueError, 'Source hash mismatch'):
                self.run_contract(adapted_root=root)
    def test_pristine_source_mismatch(self):
        with self.assertRaisesRegex(ValueError, 'Source hash mismatch'):
            self.run_contract(pristine_root=self.adapted)
    def test_support_boundary_change(self):
        with self.assertRaisesRegex(ValueError, 'Support boundary'):
            self.run_contract(boundary=dict(m.BOUNDARY, installable=True))
    def test_optional_extra_preserved(self):
        with self.assertRaisesRegex(ValueError, 'Non-PyAV'):
            self.run_contract(''.join(line for line in self.new.splitlines(keepends=True) if 'transformers[torch]' not in line))
    def test_duplicate_identity(self):
        with self.assertRaisesRegex(ValueError, 'metadata field'):
            self.run_contract(self.new.replace('Version: 1.2.1', 'Version: 1.2.1\nVersion: 1.2.1'))

if __name__ == '__main__': unittest.main()
