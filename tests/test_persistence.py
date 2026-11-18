"""Real filesystem persistence/migration checks using isolated temp folders."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from keystow import paths, settings, stats


class PersistenceTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)

    def test_legacy_migration_preserves_files_and_existing_destination(self):
        old, new = self.home/'.murmur', self.home/'.keystow'
        old.mkdir()
        (old/'settings.json').write_text('{"hotkey":"shift_r"}')
        (old/'stats.json').write_text('{"total":12,"days":{}}')
        with patch.object(paths, '_OLD', str(old)), patch.object(paths, '_DIR', str(new)):
            self.assertEqual(paths.data_dir(), str(new))
            self.assertFalse(old.exists())
            self.assertEqual(json.loads((new/'stats.json').read_text())['total'],12)
            old.mkdir(); (old/'settings.json').write_text('{"hotkey":"ctrl_r"}')
            paths.data_dir()
            self.assertEqual(json.loads((new/'settings.json').read_text())['hotkey'],'shift_r')

    def test_migration_copy_fallback_preserves_source(self):
        old, new = self.home/'.murmur', self.home/'.keystow'
        old.mkdir(); (old/'stats.json').write_text('{"total":12}')
        with patch.object(paths, '_OLD', str(old)), patch.object(paths, '_DIR', str(new)), patch.object(paths.os,'replace',side_effect=OSError('cross-device')):
            paths.data_dir()
            self.assertEqual((old/'stats.json').read_bytes(), (new/'stats.json').read_bytes())

    def test_bad_json_types_do_not_crash_read_or_update(self):
        target=self.home/'data.json'
        for content in ['[]','null','"text"','{bad','{"hotkey":[],"noise_suppression":"false","days":[],"total":"many"}']:
            with self.subTest(content=content):
                target.write_text(content)
                with patch.object(settings,'_PATH',str(target)):
                    self.assertEqual(settings.get('hotkey','ctrl_r'),'ctrl_r')
                    self.assertFalse(settings.get('noise_suppression',False))
                    settings.set('hotkey','shift_r')
                    self.assertEqual(settings.get('hotkey'),'shift_r')
                target.write_text(content)
                with patch.object(stats,'_PATH',str(target)):
                    self.assertEqual(stats.total(),0)
                    self.assertEqual(stats.today(),0)
                    stats.add_words(4)
                    self.assertEqual(stats.total(),4)
                    self.assertEqual(stats.today(),4)

    def test_interrupted_atomic_replace_preserves_last_good_file(self):
        for module in [settings,stats]:
            with self.subTest(module=module.__name__):
                target=self.home/'data.json'
                original='{"hotkey":"shift_r","total":12,"days":{}}'
                target.write_text(original)
                with patch.object(module,'_PATH',str(target)), patch.object(module.os,'replace',side_effect=OSError('disk unavailable')):
                    with self.assertRaises(OSError):
                        if module is settings:module.set('hotkey','ctrl_r')
                        else:module.add_words(3)
                self.assertEqual(target.read_text(),original)
                self.assertEqual(list(self.home.iterdir()),[target])

    def test_partial_copy_never_publishes_and_next_launch_retries(self):
        import shutil
        old, new = self.home/'.murmur', self.home/'.keystow'
        old.mkdir()
        (old/'settings.json').write_text('{"hotkey":"shift_r","future":{"version":2}}')
        (old/'stats.json').write_text('{"total":12,"days":{}}')
        original = {p.name:p.read_bytes() for p in old.iterdir()}
        def partial(source, target):
            Path(target).mkdir()
            shutil.copy2(Path(source)/'settings.json', Path(target)/'settings.json')
            raise OSError('interrupted copy')
        with patch.object(paths,'_OLD',str(old)), patch.object(paths,'_DIR',str(new)), patch.object(paths,'_FALLBACK',None,create=True):
            with patch.object(paths.os,'replace',side_effect=OSError('cross-device')), patch.object(paths.shutil,'copytree',side_effect=partial):
                self.assertEqual(paths.data_dir(),str(old))
            self.assertFalse(new.exists())
            self.assertEqual(list(self.home.iterdir()),[old])
            self.assertEqual({p.name:p.read_bytes() for p in old.iterdir()},original)
            # All modules must choose the same store even after the fault clears.
            self.assertEqual(paths.data_dir(),str(old))
            # Simulate a new process, retaining the actual filesystem.
            paths._FALLBACK = None
            with patch.object(paths.os,'replace',side_effect=OSError('cross-device')):
                self.assertEqual(paths.data_dir(),str(new))
            self.assertEqual({p.name:p.read_bytes() for p in new.iterdir()},original)
            self.assertEqual(paths.data_dir(),str(new))
            self.assertEqual({p.name:p.read_bytes() for p in new.iterdir()},original)
            self.assertEqual(sorted(p.name for p in self.home.iterdir()),['.keystow','.murmur'])

    def test_copy_publish_failure_uses_legacy_without_partial_destination(self):
        old, new = self.home/'.murmur', self.home/'.keystow'
        old.mkdir(); (old/'stats.json').write_text('{"total":12}')
        with patch.object(paths,'_OLD',str(old)), patch.object(paths,'_DIR',str(new)), patch.object(paths,'_FALLBACK',None,create=True), patch.object(paths.os,'replace',side_effect=OSError('cross-device')), patch.object(paths.os,'rename',side_effect=OSError('publish denied')):
            self.assertEqual(paths.data_dir(),str(old))
            self.assertFalse(new.exists())
            self.assertEqual(list(self.home.iterdir()),[old])
            self.assertEqual(json.loads((old/'stats.json').read_text())['total'],12)

    def test_settings_update_preserves_unknown_fields(self):
        target=self.home/'settings.json'
        target.write_text('{"hotkey":"shift_r","future":{"nested":[1,2]}}')
        with patch.object(settings,'_PATH',str(target)):
            settings.set('noise_suppression',False)
        self.assertEqual(json.loads(target.read_text())['future'],{'nested':[1,2]})
