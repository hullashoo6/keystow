"""Exercise actual controller transitions with controlled I/O failures.

These are component checks, not microphone, model accuracy or OS-paste tests.
"""
import importlib.util
from pathlib import Path
import sys
import threading
import time
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

    def test_hotkey_write_failure_preserves_active_key_and_allows_retry(self):
        old_name, old_key = self.c._hotkey_name, self.c._hotkey
        with patch.object(self.module.settings, 'set', side_effect=OSError('storage blocked')):
            self.c.set_hotkey('shift_r')
        self.assertEqual(self.c._hotkey_name, old_name)
        self.assertEqual(self.c._hotkey, old_key)
        self.window.set_hotkey_label.assert_called_with(old_name)
        self.assertIn('Could not save', self.window.set_state.call_args.args[0])
        with patch.object(self.module.settings, 'set', side_effect=[None, OSError('second write blocked')]):
            self.c.set_hotkey('shift_r')
        self.assertEqual(self.c._hotkey_name, old_name)
        self.assertEqual(self.c._hotkey, old_key)
        self.c.set_hotkey('shift_r')
        self.assertEqual(self.c._hotkey_name, 'shift_r')

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

    def test_three_unguarded_controllers_each_paste_the_same_utterance(self):
        # Regression reproducer for releases that let three processes listen.
        # No physical microphone or OS paste is claimed here.
        controllers=[self.c]+[self.module.VoiceController(Mock()) for _ in range(2)]
        for c in controllers:
            c.transcriber=self.c.transcriber
            c._transcribe_and_type('same microphone utterance',c.transcriber)
        self.assertEqual(self.paste.call_count,3)
        self.assertEqual([call.args[0] for call in self.paste.call_args_list],['second session']*3)


    def test_redelivered_press_release_events_during_processing_do_not_retype(self):
        self.c._toggle=False
        entered,release=threading.Event(),threading.Event()
        def infer(audio):
            entered.set()
            self.assertTrue(release.wait(3))
            return 'one utterance'
        self.c.transcriber.transcribe.side_effect=infer
        key=self.c._hotkey
        self.c._on_press(key);self.c._on_release(key)
        self.assertTrue(entered.wait(2))
        for _ in range(3):
            self.c._on_press(key);self.c._on_release(key)
        release.set();self.finish()
        self.assertEqual(self.c.recorder.starts,1)
        self.assertEqual(self.c.recorder.stops,1)
        self.paste.assert_called_once_with('one utterance')

    def test_own_paste_chord_cannot_reenter_recording_even_if_custom_hotkey_matches(self):
        for hotkey in ['ctrl','v','cmd']:
            with self.subTest(hotkey=hotkey):
                self.c._hotkey=hotkey
                self.c._hotkey_down=False
                self.c._phase='processing'
                def paste(text):
                    for key in ['ctrl','v']:
                        self.c._on_press(key)
                    for key in ['v','ctrl']:
                        self.c._on_release(key)
                self.paste.side_effect=paste
                self.c._transcribe_and_type('audio',self.c.transcriber)
                self.assertEqual(self.c.recorder.starts,0)
                self.assertEqual(self.c.recorder.stops,0)
        self.assertEqual(self.paste.call_count,3)

    # --- keyboard-hook thread must never wait on slow work -----------------

    def hold_state_lock(self):
        """Occupy the state lock from another thread, as slow I/O would."""
        held, release = threading.Event(), threading.Event()
        def hold():
            with self.c._state_lock:
                held.set()
                release.wait(3)
        thread = threading.Thread(target=hold)
        thread.start()
        self.assertTrue(held.wait(2))
        def free():
            release.set()
            thread.join(3)
        self.addCleanup(free)
        return free

    def wait_for_paste(self):
        deadline = time.monotonic() + 3
        while self.paste.call_count < 1 and time.monotonic() < deadline:
            time.sleep(0.01)

    def test_other_keys_never_wait_on_the_state_lock(self):
        # The hook sees every key on the system. If an unrelated key waited
        # here, Windows would time the hook out and silently remove it.
        self.hold_state_lock()
        done = threading.Event()
        def keys():
            for key in ['a', 'ctrl', 'v']:
                self.c._on_press(key)
                self.c._on_release(key)
            done.set()
        threading.Thread(target=keys, daemon=True).start()
        self.assertTrue(done.wait(1), 'unrelated key blocked on the state lock')

    def test_hotkey_callbacks_return_while_state_lock_is_busy(self):
        self.c._toggle = False
        self.c._start_dispatcher()
        self.addCleanup(self.c.shutdown)
        free = self.hold_state_lock()
        key = self.c._hotkey
        done = threading.Event()
        def keys():
            self.c._on_press(key)
            self.c._on_release(key)
            done.set()
        threading.Thread(target=keys, daemon=True).start()
        self.assertTrue(done.wait(1), 'hotkey callback blocked on the state lock')
        self.assertEqual(self.c.recorder.starts, 0)  # queued, not run on the hook thread
        free()
        # The queued press and release then run in order, once.
        self.wait_for_paste()
        self.finish()
        self.assertEqual((self.c.recorder.starts, self.c.recorder.stops), (1, 1))
        self.paste.assert_called_once_with('second session')

    def test_paste_runs_without_the_state_lock(self):
        # The injected paste keys re-enter this app's own keyboard hook, so no
        # other thread may be locked out while the paste is in flight.
        seen = []
        def paste(text):
            def probe():
                got = self.c._state_lock.acquire(timeout=1)
                if got:
                    self.c._state_lock.release()
                seen.append(got)
            thread = threading.Thread(target=probe)
            thread.start()
            thread.join(3)
        self.paste.side_effect = paste
        self.c._phase = 'processing'
        self.c._transcribe_and_type('audio', self.c.transcriber)
        self.assertEqual(seen, [True])
        self.assertEqual(self.c._phase, 'idle')

    def test_stray_tap_is_discarded_without_inference_or_paste(self):
        import numpy as np
        self.c._toggle = False
        key = self.c._hotkey
        self.c.recorder.stop = lambda: np.zeros(1600, dtype='float32')  # 0.1 s
        self.c._on_press(key)
        self.c._on_release(key)
        self.assertEqual(self.c._phase, 'idle')
        self.c.transcriber.transcribe.assert_not_called()
        self.paste.assert_not_called()
        self.assertFalse(hasattr(self.c, '_worker'))
        # A real utterance straight afterwards still works.
        self.c.recorder.stop = lambda: np.full(16000, 0.1, dtype='float32')  # 1 s
        self.c._on_press(key)
        self.c._on_release(key)
        self.finish()
        self.paste.assert_called_once_with('second session')

    def test_dead_silent_capture_explains_the_microphone_instead_of_transcribing(self):
        import numpy as np
        self.c._toggle = False
        key = self.c._hotkey
        # Exact zeros for a whole second: a muted or blocked microphone.
        self.c.recorder.stop = lambda: np.zeros(16000, dtype='float32')
        self.c._on_press(key)
        self.c._on_release(key)
        self.assertEqual(self.c._phase, 'idle')
        self.c.transcriber.transcribe.assert_not_called()
        self.paste.assert_not_called()
        message = self.window.set_state.call_args.args[0]
        self.assertIn('No sound reached KeyStow', message)
        self.assertIn('Microphone', message)
        # Quiet but real audio is still transcribed.
        quiet = np.zeros(16000, dtype='float32')
        quiet[8000] = 0.001
        self.c.recorder.stop = lambda: quiet
        self.c._on_press(key)
        self.c._on_release(key)
        self.finish()
        self.paste.assert_called_once_with('second session')

    def start_as(self, platform, frozen, trusted, order=None):
        """Run start() as the given system would, with stand-ins for the OS."""
        listener = Mock()
        mac = Mock()
        mac.accessibility_trusted.return_value = trusted
        if order is not None:
            listener.start.side_effect = lambda: order.append('listener')
            mac.prepare.side_effect = lambda: order.append('layout')
        self.module.keyboard.Listener = Mock(return_value=listener)
        self.c._watch_hotkey_access = Mock()
        with patch.object(self.module, 'sys', types.SimpleNamespace(platform=platform, frozen=frozen)), \
             patch.object(self.module, 'mac_input', mac):
            self.c.start()
        self.addCleanup(self.c.shutdown)
        return listener, mac

    def test_mac_start_reads_the_layout_before_the_listener_and_asks_for_access(self):
        order = []
        listener, mac = self.start_as('darwin', True, True, order)
        self.assertEqual(order, ['layout', 'listener'])
        mac.accessibility_trusted.assert_called_once_with(prompt=True)
        self.c._watch_hotkey_access.assert_called_once()
        self.assertFalse(self.c._hotkey_blocked)

    def test_mac_without_accessibility_starts_no_listener_and_says_why(self):
        listener, mac = self.start_as('darwin', True, False)
        mac.prepare.assert_called_once()
        listener.start.assert_not_called()
        self.c._watch_hotkey_access.assert_not_called()
        self.assertTrue(self.c._hotkey_blocked)
        self.assertIn('Accessibility', self.c._ready_message())
        self.c.shutdown()  # an unstarted listener must not break quitting

    def use_delivery(self, outcome='confirmed', reason=''):
        result = types.SimpleNamespace(outcome=outcome, reason=reason, restored=outcome == 'confirmed')
        deliver = Mock(return_value=result)
        for name, value in {'deliver': deliver, 'capture_target': Mock(return_value='front window'),
                            'copy_text': Mock(return_value=True)}.items():
            patch.object(self.module, name, value).start()
        return deliver

    def test_text_goes_to_the_window_in_front_at_release(self):
        deliver = self.use_delivery()
        self.c.start_recording(); self.c.stop_recording(); self.finish()
        deliver.assert_called_once_with('second session', 'front window')
        self.assertTrue(self.window.set_state.call_args.args[0].startswith('Pasted.'))

    def test_one_recording_is_delivered_at_most_once(self):
        deliver = self.use_delivery()
        self.c._transcribe_and_type('audio', self.c.transcriber, 7, 'front window')
        self.c._transcribe_and_type('audio', self.c.transcriber, 7, 'front window')
        deliver.assert_called_once()

    def test_not_pasting_says_why_and_copy_recovers_the_text(self):
        self.use_delivery('manual', 'focus_changed')
        self.c.start_recording(); self.c.stop_recording(); self.finish()
        self.assertIn('switched windows', self.window.set_state.call_args.args[0])
        self.c.copy_latest()
        self.module.copy_text.assert_called_once_with('second session')
        self.assertIn('Copied', self.window.set_state.call_args.args[0])

    def test_unconfirmed_paste_is_reported_not_retried(self):
        deliver = self.use_delivery('unconfirmed', 'no_read_seen')
        self.c.start_recording(); self.c.stop_recording(); self.finish()
        deliver.assert_called_once()
        self.assertIn('could not confirm', self.window.set_state.call_args.args[0])

    def test_missed_key_release_is_recovered_by_the_watchdog(self):
        self.use_delivery()
        self.c._hotkey = types.SimpleNamespace(value=types.SimpleNamespace(vk=0xA3))
        self.c._key_state_reader = lambda: (lambda vk: False)  # key is physically up
        self.c._key_state_hidden = lambda: False
        with self.c._key_lock:
            self.c._hotkey_down = True  # ...but the release event never arrived
        self.c._start_from_key()
        deadline = time.monotonic() + 2
        while self.c._phase == 'recording' and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertNotEqual(self.c._phase, 'recording')
        self.finish()
        self.assertFalse(self.c._hotkey_down)

    def test_button_recording_is_not_cut_short_by_the_watchdog(self):
        self.c._hotkey = types.SimpleNamespace(value=types.SimpleNamespace(vk=0xA3))
        self.c._key_state_reader = lambda: (lambda vk: False)
        self.c.start_recording()  # from the window's button: the key is not involved
        time.sleep(0.3)
        self.assertEqual(self.c._phase, 'recording')
        self.c.shutdown()

    def streaming_recorder(self, audio):
        class SinkRecorder:
            supports_sink = True
            def __init__(self): self.sink = 'unset'
            def start(self, sink=None): self.sink = sink
            def stop(self): return audio
        self.c.recorder = SinkRecorder()
        stream = Mock()
        stream.finish.return_value = 'denoised audio'
        patch.object(self.module.denoise, 'start_streaming', return_value=stream).start()
        return stream

    def test_noise_suppression_streams_during_recording_and_feeds_the_model(self):
        audio = types.SimpleNamespace(size=16000, any=lambda: True)
        stream = self.streaming_recorder(audio)
        self.c.start_recording()
        self.assertIs(self.c.recorder.sink, stream.push)
        self.c.stop_recording(); self.finish()
        stream.finish.assert_called_once_with(16000)
        self.c.transcriber.transcribe.assert_called_once_with(audio, denoised='denoised audio')

    def test_a_tap_cancels_the_streaming_denoiser(self):
        stream = self.streaming_recorder(types.SimpleNamespace(size=10, any=lambda: True))
        self.c.start_recording(); self.c.stop_recording()
        stream.cancel.assert_called_once()
        stream.finish.assert_not_called()

    def test_a_failed_stream_falls_back_to_denoising_the_whole_recording(self):
        audio = types.SimpleNamespace(size=16000, any=lambda: True)
        stream = self.streaming_recorder(audio)
        stream.finish.side_effect = RuntimeError('native failure')
        self.c.start_recording(); self.c.stop_recording(); self.finish()
        self.c.transcriber.transcribe.assert_called_once_with(audio)

    def test_quit_forgets_the_latest_dictation(self):
        self.use_delivery()
        self.c.start_recording(); self.c.stop_recording(); self.finish()
        self.assertEqual(self.c._last_text, 'second session')
        self.c.shutdown()
        self.assertIsNone(self.c._last_text)

    def test_mac_layout_failure_starts_no_listener_instead_of_crashing(self):
        # A listener would read the layout on its own thread: fatal on macOS.
        listener = Mock()
        mac = Mock()
        mac.prepare.return_value = False
        self.module.keyboard.Listener = Mock(return_value=listener)
        with patch.object(self.module, 'sys', types.SimpleNamespace(platform='darwin', frozen=True)), \
             patch.object(self.module, 'mac_input', mac):
            self.c.start()
        self.addCleanup(self.c.shutdown)
        self.module.keyboard.Listener.assert_not_called()
        self.assertTrue(self.c._layout_failed)
        self.assertIn('keyboard layout', self.c._ready_message())

    def test_mac_source_run_prepares_the_layout_without_a_system_prompt(self):
        listener, mac = self.start_as('darwin', False, False)
        mac.prepare.assert_called_once()
        mac.accessibility_trusted.assert_not_called()
        listener.start.assert_called_once()

    def test_windows_start_never_touches_the_mac_helpers(self):
        listener, mac = self.start_as('win32', False, None)
        mac.prepare.assert_not_called()
        mac.accessibility_trusted.assert_not_called()
        listener.start.assert_called_once()
        self.assertFalse(self.c._hotkey_blocked)

    def test_blocked_mac_paste_says_the_text_is_on_the_clipboard(self):
        class Blocked(RuntimeError):
            left_on_clipboard = True
        self.paste.side_effect = Blocked('macOS is not letting KeyStow paste')
        self.c.start_recording()
        self.c.stop_recording()
        self.finish()
        message = self.window.set_state.call_args.args[0]
        self.assertIn('clipboard', message)
        self.assertIn('Accessibility', message)
        self.assertNotIn('may already be inserted', message)

    def test_blocked_mac_shortcut_replaces_the_ready_message(self):
        self.assertIn('anywhere to speak', self.c._ready_message())
        self.c._hotkey_blocked = True
        message = self.c._ready_message()
        self.assertIn('Accessibility', message)
        self.assertNotIn('anywhere to speak', message)

    def test_self_test_flag_runs_the_check_and_never_opens_the_app(self):
        with patch.object(self.module.sys, 'argv', ['KeyStow', '--self-test', '--self-test-out=report.json']), \
             patch.object(self.module, '_self_test', return_value=7) as check, \
             patch.object(self.module.crashlog, 'setup') as logging_setup:
            with self.assertRaises(SystemExit) as stopped:
                self.module.main()
        self.assertEqual(stopped.exception.code, 7)
        check.assert_called_once_with(['--self-test', '--self-test-out=report.json'])
        self.module.run_app.assert_not_called()
        logging_setup.assert_not_called()

    def test_recording_limit_stops_and_transcribes_once(self):
        self.c._toggle = True
        with patch.object(self.module.config, 'MAX_RECORD_SECONDS', 0.05):
            self.c.toggle_recording()
            self.wait_for_paste()
        self.finish()
        self.assertEqual((self.c.recorder.starts, self.c.recorder.stops), (1, 1))
        self.paste.assert_called_once_with('second session')

    def test_stale_limit_timer_cannot_stop_a_later_recording(self):
        self.c.start_recording()
        stale = self.c._limit_token
        self.c.stop_recording()
        self.finish()
        self.c.start_recording()
        self.c._limit_reached(stale)
        self.assertEqual(self.c._phase, 'recording')
        self.c.stop_recording()
        self.finish()

if __name__ == '__main__':
    unittest.main()
