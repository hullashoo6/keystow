"""Mac keyboard preparation: the layout is read once, on the preparing thread.

Simulated pynput modules on every system, and one check against the real
pynput on a real Mac. Not a real-hardware test of the shortcut or of pasting.
"""
import contextlib
import importlib.util
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load():
    """A fresh copy of the module, so one test's cached state cannot leak."""
    spec = importlib.util.spec_from_file_location('mac_input_under_test', ROOT / 'keystow' / 'mac_input.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakePynput:
    """Stands in for pynput's Mac modules and records which thread reads the layout."""

    def __init__(self, broken=False, layout=b'layout-bytes'):
        self.reads = []
        self.controllers = []
        outer = self

        @contextlib.contextmanager
        def keycode_context():
            outer.reads.append(threading.current_thread().name)
            if broken:
                raise OSError('no keyboard layout')
            yield ('keyboard-type', layout)

        def get_unicode_to_keycode_map():
            raise AssertionError('the letter table was built from a missing layout')

        self.original = keycode_context
        util = types.ModuleType('pynput._util.darwin')
        util.keycode_context = keycode_context
        util.get_unicode_to_keycode_map = get_unicode_to_keycode_map
        keyboard_darwin = types.ModuleType('pynput.keyboard._darwin')
        keyboard_darwin.keycode_context = keycode_context
        keyboard_darwin.get_unicode_to_keycode_map = get_unicode_to_keycode_map
        self.table = get_unicode_to_keycode_map

        class Controller:
            def __init__(self):
                outer.controllers.append(threading.current_thread().name)
                # Like the real one, building it looks the layout up.
                with util.keycode_context() as context:
                    self.context = context

        class KeyCode:
            @classmethod
            def from_vk(cls, vk):
                return ('vk', vk)

        keyboard = types.ModuleType('pynput.keyboard')
        keyboard.Controller, keyboard.KeyCode, keyboard._darwin = Controller, KeyCode, keyboard_darwin
        util_package = types.ModuleType('pynput._util')
        util_package.darwin = util
        package = types.ModuleType('pynput')
        package.keyboard, package._util = keyboard, util_package
        self.util, self.keyboard_darwin, self.keyboard = util, keyboard_darwin, keyboard
        self.modules = {'pynput': package, 'pynput._util': util_package, 'pynput._util.darwin': util,
                        'pynput.keyboard': keyboard, 'pynput.keyboard._darwin': keyboard_darwin}


class PrepareTest(unittest.TestCase):
    def test_other_systems_are_left_alone(self):
        module = load()
        with patch.object(sys, 'platform', 'win32'), \
             patch.dict(sys.modules, {'pynput': None, 'HIServices': None}):
            self.assertFalse(module.prepare())
            self.assertIsNone(module.controller())
            self.assertIsNone(module.accessibility_trusted())
            self.assertIsNone(module.accessibility_trusted(prompt=True))

    def test_layout_is_read_once_on_the_preparing_thread_and_never_again(self):
        fake, module = FakePynput(), load()
        seen = []

        def background():
            with fake.util.keycode_context() as context:
                seen.append(context)
            with fake.keyboard_darwin.keycode_context() as context:
                seen.append(context)
            seen.append(fake.keyboard.Controller().context)

        with patch.dict(sys.modules, fake.modules), patch.object(sys, 'platform', 'darwin'):
            self.assertTrue(module.prepare())
            self.assertTrue(module.prepare())  # a second call changes nothing
            worker = threading.Thread(target=background, name='listener')
            worker.start()
            worker.join(5)
        here = threading.current_thread().name
        self.assertEqual(fake.reads, [here])
        self.assertEqual(seen, [('keyboard-type', b'layout-bytes')] * 3)
        self.assertEqual(fake.controllers, [here, 'listener'])
        self.assertEqual(module.controller().context, ('keyboard-type', b'layout-bytes'))

    def test_unreadable_layout_is_logged_and_leaves_pynput_as_it_was(self):
        fake, module = FakePynput(broken=True), load()
        with patch.dict(sys.modules, fake.modules), patch.object(sys, 'platform', 'darwin'), \
             self.assertLogs(level='ERROR') as logs:
            self.assertFalse(module.prepare())
        self.assertIn('keyboard layout', logs.output[0])
        self.assertIs(fake.util.keycode_context, fake.original)
        self.assertIs(fake.keyboard_darwin.keycode_context, fake.original)
        self.assertIsNone(module.controller())

    def test_a_usable_layout_leaves_the_letter_table_to_pynput(self):
        fake, module = FakePynput(), load()
        with patch.dict(sys.modules, fake.modules), patch.object(sys, 'platform', 'darwin'):
            self.assertTrue(module.prepare())
        self.assertIs(fake.util.get_unicode_to_keycode_map, fake.table)
        self.assertIs(fake.keyboard_darwin.get_unicode_to_keycode_map, fake.table)

    def test_a_missing_layout_gives_pynput_an_empty_letter_table(self):
        fake, module = FakePynput(layout=None), load()
        with patch.dict(sys.modules, fake.modules), patch.object(sys, 'platform', 'darwin'):
            self.assertTrue(module.prepare())
        self.assertEqual(fake.util.get_unicode_to_keycode_map(), {})
        self.assertEqual(fake.keyboard_darwin.get_unicode_to_keycode_map(), {})
        self.assertIsNotNone(module.controller())

    def test_paste_key_is_the_physical_v_key(self):
        fake, module = FakePynput(), load()
        with patch.dict(sys.modules, fake.modules):
            self.assertEqual(module.paste_key(), ('vk', 9))
        with patch.dict(sys.modules, {'pynput': None, 'pynput.keyboard': None}):
            self.assertIsNone(module.paste_key())


class AccessibilityTest(unittest.TestCase):
    def services(self, trusted):
        asked = []
        module = types.ModuleType('HIServices')
        module.AXIsProcessTrusted = lambda: trusted
        module.kAXTrustedCheckOptionPrompt = 'AXTrustedCheckOptionPrompt'
        module.AXIsProcessTrustedWithOptions = lambda options: (asked.append(options), trusted)[1]
        return module, asked

    def test_reports_what_macos_says_and_prompts_only_when_asked(self):
        for trusted in (True, False):
            services, asked = self.services(trusted)
            with patch.dict(sys.modules, {'HIServices': services}), patch.object(sys, 'platform', 'darwin'):
                module = load()
                self.assertIs(module.accessibility_trusted(), trusted)
                self.assertEqual(asked, [])
                self.assertIs(module.accessibility_trusted(prompt=True), trusted)
                self.assertEqual(asked, [{'AXTrustedCheckOptionPrompt': True}])

    def test_a_failed_question_is_unknown_not_blocked(self):
        with patch.dict(sys.modules, {'HIServices': None}), patch.object(sys, 'platform', 'darwin'), \
             self.assertLogs(level='ERROR'):
            self.assertIsNone(load().accessibility_trusted())


@unittest.skipUnless(sys.platform == 'darwin', 'needs the real pynput on a real Mac')
class RealPynputTest(unittest.TestCase):
    def test_real_pynput_never_reads_the_layout_off_the_preparing_thread(self):
        from pynput._util import darwin as util_darwin
        from pynput.keyboard import _darwin as keyboard_darwin

        originals = (util_darwin.keycode_context, keyboard_darwin.keycode_context,
                     util_darwin.get_unicode_to_keycode_map, keyboard_darwin.get_unicode_to_keycode_map)

        def restore():
            (util_darwin.keycode_context, keyboard_darwin.keycode_context,
             util_darwin.get_unicode_to_keycode_map, keyboard_darwin.get_unicode_to_keycode_map) = originals

        self.addCleanup(restore)
        readers = []
        carbon = util_darwin.CarbonExtra

        def watched(name):
            real = getattr(carbon, name)

            def call(*arguments):
                readers.append((name, threading.current_thread().name))
                return real(*arguments)

            return call

        for name in ('TISCopyCurrentKeyboardInputSource',
                     'TISCopyCurrentASCIICapableKeyboardLayoutInputSource',
                     'TISGetInputSourceProperty'):
            watcher = patch.object(carbon, name, watched(name))
            watcher.start()
            self.addCleanup(watcher.stop)

        module = load()
        self.assertTrue(module.prepare())
        self.assertTrue(readers, 'the layout was never read')
        here = threading.current_thread().name
        self.assertEqual({thread for _name, thread in readers}, {here})
        readers.clear()
        result = {}

        def background():
            from pynput.keyboard import Controller

            result['map'] = util_darwin.get_unicode_to_keycode_map()
            with keyboard_darwin.keycode_context() as context:
                result['context'] = context
            result['controller'] = Controller()

        worker = threading.Thread(target=background, name='worker')
        worker.start()
        worker.join(30)
        self.assertFalse(worker.is_alive(), 'the worker did not finish')
        self.assertEqual(readers, [], 'Text Input Sources was used off the preparing thread')
        self.assertIsInstance(result.get('map'), dict)
        self.assertIn('controller', result)
        self.assertIsNotNone(module.controller())
        self.assertEqual(module.paste_key().vk, 9)


if __name__ == '__main__':
    unittest.main()

# CI re-run marker, 24 Nov: no change to the tests; added only to start a new check run.
