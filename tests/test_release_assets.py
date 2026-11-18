"""Fail-closed release metadata gate; no GitHub mutation."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('verify_release_assets', Path(__file__).resolve().parents[1] / 'installer' / 'verify_release_assets.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ReleaseGateTest(unittest.TestCase):
    def test_only_exact_uploaded_draft_pair_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            assets = []
            for name in sorted(gate.NAMES):
                data = name.encode()
                (Path(directory) / name).write_bytes(data)
                assets.append({'name':name, 'size':len(data), 'digest':'sha256:' + hashlib.sha256(data).hexdigest(), 'state':'uploaded'})
            good = {'tag_name':'v1.0.2','draft':True,'assets':assets}
            gate.verify(good, directory)
            bad_cases = []
            for field, value in [('draft',False),('tag_name','v1.0.1'),('assets',assets[:1]),('assets',assets+assets[:1])]:
                bad = copy.deepcopy(good);bad[field]=value;bad_cases.append(bad)
            for field,value in [('size',0),('digest','sha256:wrong'),('state','starter'),('name','other.exe')]:
                bad=copy.deepcopy(good);bad['assets'][0][field]=value;bad_cases.append(bad)
            for bad in bad_cases:
                with self.assertRaises(ValueError):gate.verify(bad,directory)
