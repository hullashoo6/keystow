import os
import importlib.metadata as md,importlib.util,sys,tempfile,unittest
from pathlib import Path
r=Path(__file__).parents[1];sys.path.insert(0,str(r/'installer'))
from prepare_numpy_dependency import stage
class StageTests(unittest.TestCase):
    def setUp(self):self.source=Path(os.environ['KEYSTOW_PRISTINE_PACKAGE']) if 'KEYSTOW_PRISTINE_PACKAGE' in os.environ else Path(md.distribution('faster-whisper').locate_file('faster_whisper'))
    def test_reproduce_without_touching_source(self):
        before=(self.source/'audio.py').read_bytes()
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'staged';x=stage(self.source,out,'1.2.1')
            self.assertEqual(x['adapted_audio_sha256'],'7c07f715830e044386e75b1303851dbe6e0715f1302593bcc061f3a8876a1ae7')
            self.assertEqual((self.source/'audio.py').read_bytes(),before)
            with self.assertRaisesRegex(ValueError,'already'):stage(self.source,out,'1.2.1')
    def test_wrong_version_no_output(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'staged'
            with self.assertRaisesRegex(ValueError,'version'):stage(self.source,out,'1.2.0')
            self.assertFalse(out.exists())
