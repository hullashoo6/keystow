"""Controlled clipboard/key dispatch failures, not actual OS paste acceptance."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock,patch


class TyperTest(unittest.TestCase):
    def setUp(self):
        self.clipboard='previous'
        self.events=[]
        self.keyboard=Mock()
        self.keyboard.press.side_effect=lambda k:self.events.append(('press',k))
        self.keyboard.release.side_effect=lambda k:self.events.append(('release',k))
        class ClipboardError(Exception):pass
        self.clip=types.SimpleNamespace(paste=lambda:self.clipboard,copy=self.copy,PyperclipException=ClipboardError)
        self.keys=types.SimpleNamespace(ctrl='ctrl',cmd='cmd')
        deps={'pyperclip':self.clip,'pynput':types.ModuleType('pynput'),
              'pynput.keyboard':types.SimpleNamespace(Controller=lambda:self.keyboard,Key=self.keys)}
        spec=importlib.util.spec_from_file_location('typer_under_test',Path(__file__).parents[1]/'keystow/typer.py')
        self.m=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,deps):spec.loader.exec_module(self.m)
        p=patch.object(self.m.time,'sleep');self.sleep=p.start();self.addCleanup(p.stop)

    def copy(self,text):self.clipboard=text

    def test_dispatch_failure_releases_keys_and_restores_owned_clipboard(self):
        def press(key):
            self.events.append(('press',key))
            if key=='v':raise RuntimeError('dispatch failed')
        self.keyboard.press.side_effect=press
        with self.assertRaisesRegex(RuntimeError,'dispatch failed'):self.m.type_text('new')
        self.assertEqual(self.events[-2:],[('release','v'),('release','ctrl')])
        self.assertEqual(self.clipboard,'previous')

    def test_new_user_clipboard_value_is_not_overwritten(self):
        def during_delay(seconds):
            if ('release','ctrl') in self.events:self.clipboard='new user copy'
        self.sleep.side_effect=during_delay
        self.m.type_text('new')
        self.assertEqual(self.clipboard,'new user copy')

    def test_success_restores_previous_text_and_dispatches_once(self):
        self.m.type_text('unicode text')
        self.assertEqual(self.events,[('press','ctrl'),('press','v'),('release','v'),('release','ctrl')])
        self.assertEqual(self.clipboard,'previous')

    def test_modifier_release_failure_still_attempts_cleanup_and_recovery(self):
        attempts=[]
        def release(key):
            attempts.append(key)
            if key=='ctrl' and attempts.count('ctrl')==1:raise RuntimeError('release failed')
        self.keyboard.release.side_effect=release
        with self.assertRaisesRegex(RuntimeError,'release failed'):self.m.type_text('new')
        self.assertEqual(attempts,['v','ctrl','ctrl'])
        self.assertEqual(self.clipboard,'previous')

    def test_restore_failure_is_not_silent_success(self):
        def copy(text):
            if text=='previous':raise self.clip.PyperclipException('restore denied')
            self.clipboard=text
        self.clip.copy=copy
        with self.assertRaisesRegex(RuntimeError,'cleanup failed'):self.m.type_text('new')
        self.assertEqual(self.events.count(('press','v')),1)

    def test_clipboard_read_failure_still_allows_request_without_restore(self):
        self.clip.paste=Mock(side_effect=self.clip.PyperclipException('read failed'))
        self.m.type_text('new')
        self.assertEqual(self.clipboard,'new')
        self.assertEqual(self.events.count(('press','v')),1)

    def test_clipboard_write_failure_dispatches_no_keys_and_next_attempt_works(self):
        self.clip.copy=Mock(side_effect=self.clip.PyperclipException('write failed'))
        with self.assertRaises(self.clip.PyperclipException):self.m.type_text('new')
        self.assertEqual(self.events,[])
        self.clip.copy=self.copy
        self.m.type_text('retry')
        self.assertEqual(self.clipboard,'previous')

    def test_mac_modifier_and_disabled_restore(self):
        with patch.object(self.m.sys,'platform','darwin'):self.m.type_text('new',restore_clipboard=False)
        self.assertEqual(self.events[0],('press','cmd'))
        self.assertEqual(self.clipboard,'new')

    def test_interruption_before_dispatch_preserves_new_copy_and_original_error(self):
        def interrupt(seconds):
            self.clipboard='user copied during cancellation'
            raise RuntimeError('cancelled before dispatch')
        self.sleep.side_effect=interrupt
        with self.assertRaisesRegex(RuntimeError,'cancelled before dispatch'):self.m.type_text('new')
        self.assertEqual(self.events,[])
        self.assertEqual(self.clipboard,'user copied during cancellation')
        self.sleep.side_effect=None
        self.m.type_text('retry')
        self.assertEqual(self.events.count(('press','v')),1)
        self.assertEqual(self.clipboard,'user copied during cancellation')

    def test_dispatch_error_not_masked_by_restore_error(self):
        self.keyboard.press.side_effect=RuntimeError('primary dispatch failure')
        def copy(text):
            if text=='previous':raise self.clip.PyperclipException('secondary restore failure')
            self.clipboard=text
        self.clip.copy=copy
        with self.assertRaisesRegex(RuntimeError,'primary dispatch failure'):self.m.type_text('new')
        self.assertEqual(self.events,[('release','ctrl')])
