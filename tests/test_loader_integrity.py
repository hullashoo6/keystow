import importlib.util,json,sys,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('code_inspection',Path(__file__).parents[1]/'installer/inspect_dependency_code.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class CodeIntegrityTests(unittest.TestCase):
    def test_inspects_without_import(self):
        x=m.inspect_code();self.assertNotIn('faster_whisper',sys.modules);self.assertTrue(m.verify_code(x,x))
    def test_abi_mismatch_refused(self):
        x=m.inspect_code();y=dict(x,python_cache_tag='different')
        with self.assertRaisesRegex(RuntimeError,'ABI'):m.verify_code(x,y)
    def test_code_mismatch_refused(self):
        x=m.inspect_code();y=json.loads(json.dumps(x));y['modules']['faster_whisper.audio']='bad'
        with self.assertRaisesRegex(RuntimeError,'code mismatch'):m.verify_code(x,y)
    def test_incomplete_manifest_refused(self):
        x=m.inspect_code();y=dict(x,modules={})
        with self.assertRaisesRegex(RuntimeError,'Incomplete'):m.verify_code(x,y)
