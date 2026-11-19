import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('inv',Path(__file__).parents[1]/'installer/check_native_inventory.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class InventoryTests(unittest.TestCase):
    def test_no_claim_without_inventory(self):
        for x in [{},{'platform':'windows','stage':'analysis','complete':True,'files':[]}]:
            with self.assertRaises(ValueError):m.check(x)
    def test_forbidden_names_both_platforms(self):
        for f in ['av','av.audio','av/_core.pyd','av.libs/avcodec-62.dll','libavcodec.61.dylib','swresample-5.dll','ffmpeg.exe']:
            with self.subTest(f=f),self.assertRaises(ValueError):m.check({'platform':'windows','stage':'frozen','complete':True,'files':[f]})
    def test_allow_inference_preserve_stage(self):
        x=m.check({'platform':'macos','stage':'analysis','complete':True,'files':['ctranslate2/_ext.so','libctranslate2.dylib','numpy/_core.so']});self.assertEqual(x['stage'],'analysis')
