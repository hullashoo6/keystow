"""Default/upgrade semantics on real isolated settings files, not OS events."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from keystow import settings


class ActivationModeTest(unittest.TestCase):
    def test_mode_precedence_and_startup_never_rewrites_preferences(self):
        cases = [({},False), ({'hotkey':'shift_r'},True),
                 ({'hotkey':'ctrl_r'},True),
                 ({'activation_mode':'hold','hotkey':'shift_r'},False),
                 ({'activation_mode':'toggle'},True),
                 ({'activation_mode':[],'hotkey':[]},False)]
        with tempfile.TemporaryDirectory() as home:
            target=Path(home)/'settings.json'
            for data,expected in cases:
                for override in [None,'0','1']:
                    with self.subTest(data=data,override=override):
                        target.write_text(json.dumps(data))
                        before=target.read_bytes()
                        with patch.object(settings,'_PATH',str(target)), patch.dict(os.environ,{},clear=True):
                            if override is not None: os.environ['KEYSTOW_TOGGLE']=override
                            self.assertEqual(settings.toggle_mode(),expected if override is None else override!='0')
                        self.assertEqual(target.read_bytes(),before)

    def test_missing_file_means_hold_without_creating_settings(self):
        with tempfile.TemporaryDirectory() as home:
            target=Path(home)/'settings.json'
            with patch.object(settings,'_PATH',str(target)), patch.dict(os.environ,{},clear=True):
                self.assertFalse(settings.toggle_mode())
                self.assertFalse(target.exists())

    def test_explicit_mode_survives_new_key_and_restart_read(self):
        for mode in ['hold','toggle']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as home:
                target=Path(home)/'settings.json'
                with patch.object(settings,'_PATH',str(target)), patch.dict(os.environ,{},clear=True):
                    settings.set('activation_mode',mode)
                    settings.set('hotkey','shift_r')
                    self.assertEqual(settings.toggle_mode(),mode=='toggle')
                    self.assertEqual(settings.get('hotkey'),'shift_r')

    def test_custom_environment_key_preserves_legacy_mode_unless_overridden(self):
        with tempfile.TemporaryDirectory() as home, patch.object(settings,'_PATH',str(Path(home)/'absent.json')), patch.dict(os.environ,{'KEYSTOW_HOTKEY':'shift_r'},clear=True):
            self.assertTrue(settings.toggle_mode())
            os.environ['KEYSTOW_TOGGLE']='0'
            self.assertFalse(settings.toggle_mode())
