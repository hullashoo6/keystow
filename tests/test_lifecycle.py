"""Exercise actual controller transitions with controlled I/O failures.

These are component checks, not microphone, model accuracy or OS-paste tests.
"""
import importlib.util
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch


class Signal:
    def connect(self, callback):
        self.callback = callback


class Recorder:
    def __init__(self):
        self.starts = 0
        self.stops = 0
        self.fail_start = False
        self.fail_stop = False

    def start(self):
        if self.fail_start:
            raise RuntimeError("permission denied")
        self.starts += 1

    def stop(self):
        self.stops += 1
        if self.fail_stop:
            raise RuntimeError("device removed")
        return "audio"


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        key = types.SimpleNamespace(ctrl_r="ctrl_r")
        keyboard = types.SimpleNamespace(Key=key, KeyCode=types.SimpleNamespace(from_char=lambda x:x))
        self.window = Mock()
        for name in ['hotkey_selected','hotkey_capture_requested','record_toggled','record_pressed','record_released']:
            setattr(self.window, name, Signal())
        deps = {
            'pynput': types.SimpleNamespace(keyboard=keyboard),
            'keystow.recorder': types.SimpleNamespace(PushToTalkRecorder=Recorder),
            'keystow.transcriber': types.SimpleNamespace(Transcriber=Mock()),
            'keystow.typer': types.SimpleNamespace(type_text=Mock()),
            'keystow.ui': types.SimpleNamespace(MainWindow=object,ModelLoader=Mock(),hotkey_label=lambda x:x,run_app=Mock()),
        }
        self.deps = deps
        spec = importlib.util.spec_from_file_location('keystow._controller_under_test', Path(__file__).parents[1]/'keystow/app.py')
        self.module = importlib.util.module_from_spec(spec)
        # Explicit package attributes avoid leaked prior imports on repeat runs.
        import keystow
        with patch.dict(sys.modules, deps), patch.object(keystow, 'ui', deps['keystow.ui'], create=True):
            spec.loader.exec_module(self.module)
        self.settings = patch.object(self.module.settings, 'get', side_effect=lambda k,d=None:d)
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.writes = patch.object(self.module.settings, 'set')
        self.writes.start()
        self.addCleanup(self.writes.stop)
        self.addCleanup(patch.stopall)
        patch.object(self.module.stats, 'add_words').start()
        self.c = self.module.VoiceController(self.window)
        self.c.transcriber = Mock()
        self.c.transcriber.transcribe.return_value = 'second session'
        self.paste = self.module.type_text

    def finish(self):
        self.c._worker.join(3)
        self.assertFalse(self.c._worker.is_alive(), 'worker stuck')
        self.assertEqual(self.c._phase, 'idle')

    def test_processing_blocks_capture_model_switch_and_duplicate_stop(self):
        entered, release = threading.Event(), threading.Event()
        def infer(audio):
            entered.set()
            self.assertTrue(release.wait(3))
            return 'one session'
        self.c.transcriber.transcribe.side_effect = infer
        self.c.start_recording()
        self.c.start_recording()
        self.c.stop_recording()
        self.assertTrue(entered.wait(2))
        try:
            for _ in range(5):
                self.c.start_recording()
                self.c.stop_recording()
                self.c._on_press(self.c._hotkey)
                self.c._on_release(self.c._hotkey)
            self.assertFalse(self.c._load_model('turbo'))
            self.assertEqual(self.c.recorder.starts, 1)
            self.assertEqual(self.c.recorder.stops, 1)
            self.module.ModelLoader.assert_not_called()
        finally:
            release.set()
        self.finish()
        self.paste.assert_called_once_with('one session')

    def test_inference_failure_then_immediate_new_session(self):
        self.c.transcriber.transcribe.side_effect = [RuntimeError('inference failure'), 'recovered text']
        self.c.start_recording(); self.c.stop_recording(); self.finish()
        self.paste.assert_not_called()
        self.c.start_recording(); self.c.stop_recording(); self.finish()
        self.paste.assert_called_once_with('recovered text')
        self.window.show_transcript.assert_called_once_with('recovered text')

    def test_paste_failure_keeps_transcript_and_releases_session(self):
        self.paste.side_effect = RuntimeError('clipboard unavailable')
        self.c.start_recording(); self.c.stop_recording(); self.finish()
        self.window.show_transcript.assert_called_once_with('second session')
        self.assertIn("Paste or clipboard cleanup failed", self.window.set_state.call_args.args[0])
        self.paste.side_effect = None
        self.c.start_recording()
        self.assertEqual(self.c._phase, 'recording')

    def test_microphone_start_and_stop_failures_allow_retry(self):
        self.c.recorder.fail_start = True
        self.c.start_recording()
        self.assertEqual(self.c._phase, 'idle')
        self.c.recorder.fail_start = False
        self.c.start_recording()
        self.c.recorder.fail_stop = True
        self.c.stop_recording()
        self.assertEqual(self.c._phase, 'idle')
        self.c.recorder.fail_stop = False
        self.c.start_recording(); self.c.stop_recording(); self.finish()
        self.paste.assert_called_once()

    def test_quit_during_inference_discards_late_result_and_new_work(self):
        entered, release = threading.Event(), threading.Event()
        def infer(audio):
            entered.set()
            self.assertTrue(release.wait(3))
            return 'late result must not paste'
        self.c.transcriber.transcribe.side_effect = infer
        self.c.start_recording(); self.c.stop_recording()
        self.assertTrue(entered.wait(2))
        self.c.shutdown()
        self.assertFalse(self.c.can_exit())
        self.c.start_recording()
        self.assertEqual(self.c.recorder.starts, 1)
        release.set()
        self.c._worker.join(3)
        self.assertTrue(self.c.can_exit())
        self.assertEqual(self.c._phase, 'closing')
        self.paste.assert_not_called()
        self.window.show_transcript.assert_not_called()

    def test_quit_during_recording_discards_audio(self):
        self.c.start_recording()
        self.c.shutdown()
        self.c.stop_recording()
        self.assertEqual(self.c.recorder.stops, 1)
        self.paste.assert_not_called()
        self.assertTrue(self.c.can_exit())

    def test_stats_disk_failure_does_not_prevent_paste(self):
        self.module.stats.add_words.side_effect = OSError('read only disk')
        self.c.start_recording(); self.c.stop_recording(); self.finish()
        self.paste.assert_called_once_with('second session')

    def test_empty_transcript_never_pastes(self):
        self.c.transcriber.transcribe.return_value = ''
        self.c.start_recording(); self.c.stop_recording(); self.finish()
        self.paste.assert_not_called()

    def test_model_load_serialized_and_failure_retains_previous(self):
        old_model = self.c.transcriber
        loader = Mock(ready=Signal(), failed=Signal())
        self.module.ModelLoader.return_value = loader
        self.assertTrue(self.c._load_model('turbo'))
        self.c.start_recording()
        self.assertEqual(self.c.recorder.starts, 0)
        self.assertFalse(self.c._load_model('small'))
        loader.failed.callback('network offline')
        self.assertEqual(self.c._phase, 'idle')
        self.assertIs(self.c.transcriber, old_model)
        self.c.start_recording()
        self.assertEqual(self.c._phase, 'recording')


    def test_hold_repeat_and_duplicate_release_are_one_capture(self):
        self.c._toggle = False
        key = self.c._hotkey
        self.c._on_press(key)
        for _ in range(8): self.c._on_press(key)
        self.assertEqual(self.c.recorder.starts,1)
        self.assertEqual(self.c.recorder.stops,0)
        self.c._on_release('unrelated')
        self.assertEqual(self.c.recorder.stops,0)
        self.c._on_release(key); self.finish()
        self.c._on_release(key)
        self.assertEqual(self.c.recorder.stops,1)
        self.paste.assert_called_once_with('second session')

    def test_hold_failed_start_does_not_repeat_retry_until_release(self):
        self.c._toggle = False
        self.c.recorder.fail_start = True
        key = self.c._hotkey
        self.c._on_press(key)
        self.c.recorder.fail_start = False
        self.c._on_press(key)
        self.assertEqual(self.c.recorder.starts,0)
        self.c._on_release(key)
        self.assertEqual(self.c.recorder.stops,0)
        self.c._on_press(key); self.c._on_release(key); self.finish()
        self.paste.assert_called_once()

    def test_silent_hold_cycles_then_new_text_never_reuse_prior_result(self):
        self.c._toggle = False
        key = self.c._hotkey
        self.c.transcriber.transcribe.side_effect = ['prior', '', '', RuntimeError('inference failed'), 'new text']
        for _ in range(5):
            self.c._on_press(key); self.c._on_release(key); self.finish()
        self.assertEqual([call.args[0] for call in self.paste.call_args_list],['prior','new text'])
        self.assertEqual(self.c.recorder.starts,5)
        self.assertFalse(self.c._hotkey_down)

    def test_custom_capture_key_repeat_cannot_start_recording(self):
        self.c._toggle = False
        self.c.start_hotkey_capture()
        key = self.c._hotkey
        self.c._on_press(key)
        for _ in range(4): self.c._on_press(key)
        self.assertEqual(self.c.recorder.starts,0)
        self.c._on_release(key)
        self.assertEqual(self.c.recorder.stops,0)
        self.module.settings.set.assert_any_call('activation_mode','hold')
        self.c._on_press(key); self.c._on_release(key); self.finish()

    def test_shutdown_mid_hold_and_fresh_controller_start_idle(self):
        self.c._toggle = False
        key = self.c._hotkey
        self.c._on_press(key); self.c.shutdown()
        self.c._on_release(key); self.c._on_press(key)
        self.assertEqual(self.c.recorder.starts,1)
        self.assertEqual(self.c.recorder.stops,1)
        self.assertEqual(self.c._phase,'closing')
        self.assertFalse(self.c._hotkey_down)
        self.paste.assert_not_called()
        restarted = self.module.VoiceController(self.window)
        self.assertEqual(restarted._phase,'idle')
        self.assertFalse(restarted._hotkey_down)

    def test_explicit_toggle_still_requires_two_separate_presses(self):
        self.c._toggle = True
        key = self.c._hotkey
        self.c._on_press(key); self.c._on_press(key); self.c._on_release(key)
        self.assertEqual(self.c._phase,'recording')
        self.assertEqual(self.c.recorder.stops,0)
        self.c._on_press(key); self.c._on_release(key); self.finish()
        self.assertEqual(self.c.recorder.starts,1)
        self.assertEqual(self.c.recorder.stops,1)


    def test_hold_stop_failure_then_next_hold_recovers(self):
        self.c._toggle = False
        key = self.c._hotkey
        self.c._on_press(key)
        self.c.recorder.fail_stop = True
        self.c._on_release(key)
        self.assertEqual(self.c._phase,'idle')
        self.assertFalse(self.c._hotkey_down)
        self.paste.assert_not_called()
        self.c.recorder.fail_stop = False
        self.c._on_press(key); self.c._on_release(key); self.finish()
        self.paste.assert_called_once_with('second session')

    def test_key_pressed_while_processing_cannot_start_from_auto_repeat(self):
        self.c._toggle = False
        key = self.c._hotkey
        entered, release = threading.Event(), threading.Event()
        def infer(audio):
            entered.set()
            self.assertTrue(release.wait(3))
            return ''
        self.c.transcriber.transcribe.side_effect = infer
        self.c._on_press(key); self.c._on_release(key)
        self.assertTrue(entered.wait(2))
        self.c._on_press(key)  # ignored while processing, still physically down
        release.set(); self.finish()
        self.c._on_press(key)  # repeat after idle is not a new press
        self.assertEqual(self.c.recorder.starts,1)
        self.c._on_release(key)
        self.assertEqual(self.c.recorder.stops,1)
        self.c.transcriber.transcribe.side_effect = None
        self.c.transcriber.transcribe.return_value = 'fresh'
        self.c._on_press(key); self.c._on_release(key); self.finish()
        self.paste.assert_called_once_with('fresh')


if __name__ == '__main__':
    unittest.main()
