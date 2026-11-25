"""KeyStow controller: one recording, model load or transcription at a time."""

import logging
import os
import queue
import sys
import threading
import time

from pynput import keyboard

from . import __version__, cleanup, config, crashlog, denoise, mac_input, settings, stats, timings
from .recorder import PushToTalkRecorder
from .transcriber import Transcriber
from .typer import type_text
from .ui import MainWindow, ModelLoader, hotkey_label, run_app

try:  # a stand-in typer (as in tests) may only provide type_text
    from .typer import capture_target, copy_text, deliver
except ImportError:
    capture_target = copy_text = deliver = None
try:  # likewise a stand-in transcriber
    from .transcriber import BUNDLED_MODEL, model_cached
except ImportError:
    BUNDLED_MODEL, model_cached = "base", None

# What the user sees when KeyStow deliberately did not paste (see win_delivery).
_MANUAL_MESSAGES = {
    "focus_changed": "You switched windows before the text was ready, so KeyStow did not paste it. "
                     "Click Copy, then paste it where you want it.",
    "keystow_focused": "Your text is ready. Click Copy, then paste it into your app.",
    "elevated": "That window runs as administrator, so Windows blocks KeyStow from pasting into it. "
                "Click Copy, then press Ctrl+V.",
    "modifier_held": "Shift, Alt or the Windows key was still held, so nothing was pasted. "
                     "Click Copy, then press Ctrl+V.",
    "keys_blocked": "Windows blocked the paste keys. Click Copy, then press Ctrl+V.",
    "clipboard_busy": "Another app was holding the clipboard, so nothing was pasted. "
                      "Click Copy, then press Ctrl+V.",
}
_MANUAL_DEFAULT = ("Your clipboard holds something KeyStow cannot safely put back, so it did not paste. "
                   "Click Copy, then press Ctrl+V.")

DEFAULT_HOTKEY = keyboard.Key.ctrl_r


def _resolve_hotkey(name: str):
    key = getattr(keyboard.Key, name, None)
    if key is not None:
        return key
    try:
        return keyboard.KeyCode.from_char(name)
    except Exception:  # noqa: BLE001
        return DEFAULT_HOTKEY


class VoiceController:
    def __init__(self, window: MainWindow):
        self.window = window
        self.recorder = PushToTalkRecorder()
        self.transcriber = None
        # Held for state transitions, not for model inference. Both the Qt
        # thread and global-keyboard listener can request operations.
        self._state_lock = threading.RLock()
        # Hotkey bookkeeping only. The keyboard-hook thread takes this lock and
        # never the state lock, so slow microphone, disk or paste work on other
        # threads cannot stall system-wide key delivery.
        self._key_lock = threading.Lock()
        self._actions = None  # queue of hotkey actions once start() is called
        self._action_thread = None
        self._limit_token = None
        self._limit_timer = None
        self._phase = "idle"
        self._closing = False
        self._listener = None
        self._hotkey_down = False
        self._hotkey_blocked = False  # macOS has not allowed global key access
        self._capturing = False
        self._capture_release_key = None  # a just-chosen key, ignored until released
        self._capture_id = 0      # one id per recording; a result is delivered once
        self._delivered_id = None
        self._watch_token = None  # the hold-mode release watchdog for this recording
        self._from_key = False    # this recording was started by the activation key
        self._last_text = None    # latest result, memory only, for "Copy"
        self._layout_failed = False  # macOS: keyboard layout could not be prepared
        self._timing = None       # opt-in step timings for the current recording
        self._toggle = settings.toggle_mode()
        self._hotkey_name = settings.get("hotkey", config.HOTKEY)
        self._hotkey = _resolve_hotkey(self._hotkey_name)
        self._label = hotkey_label(self._hotkey_name)
        window._on_model_change = self._load_model
        window.hotkey_selected.connect(self.set_hotkey)
        window.hotkey_capture_requested.connect(self.start_hotkey_capture)
        copy_requested = getattr(window, "copy_requested", None)
        if copy_requested is not None:
            copy_requested.connect(self.copy_latest)
        # The window emits only the signals that fit the current mode.
        window.record_toggled.connect(self.toggle_recording)
        window.record_pressed.connect(self.start_recording)
        window.record_released.connect(self.stop_recording)
        mode_selected = getattr(window, "mode_selected", None)
        if mode_selected is not None:
            mode_selected.connect(self.set_mode)

    def start(self):
        self._load_model(config.MODEL_SIZE)
        self._start_dispatcher()
        if sys.platform == "win32":
            try:
                from . import win_delivery

                win_delivery.disable_power_throttling()
            except Exception:
                logging.exception("could not opt out of background power throttling")
        blocked = False
        if sys.platform == "darwin":
            # This runs on the main thread, the only one a Mac lets read the
            # keyboard layout: do it now, before the listener thread exists.
            if mac_input.prepare() is False:
                # The listener would read the layout on its own thread, which
                # ends the app on current macOS. Run without the shortcut and
                # say so; the window's button still works.
                with self._state_lock:
                    self._layout_failed = True
                    self._hotkey_blocked = True
                self._listener = None
                self._remove_leftovers()
                return
            if getattr(sys, "frozen", False):
                # macOS shows its own dialog, with a button to the setting.
                blocked = mac_input.accessibility_trusted(prompt=True) is False
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        if blocked:
            # Without Accessibility access macOS gives this app no keys, so a
            # listener could do nothing, and starting one makes macOS ask for
            # a second, different permission (Input Monitoring) as well.
            with self._state_lock:
                self._hotkey_blocked = True
        else:
            self._listener.start()
            self._watch_hotkey_access()
        self._remove_leftovers()

    def _watch_hotkey_access(self):
        """Tell a Mac user when the system is silently withholding the shortcut.

        macOS delivers global keys only to apps allowed under Accessibility,
        and reports nothing when it does not. The listener records whether the
        process is trusted shortly after it starts.
        """
        if sys.platform != "darwin":
            return

        def check():
            try:
                trusted = getattr(self._listener, "IS_TRUSTED", True)
                if trusted is not False:
                    return
                with self._state_lock:
                    self._hotkey_blocked = True
                    if self._phase == "idle" and not self._closing:
                        self.window.set_state(self._ready_message())
            except Exception:
                logging.exception("shortcut access check failed")

        timer = threading.Timer(3.0, check)
        timer.daemon = True
        timer.start()

    def _remove_leftovers(self):
        """Clear unpacked copies that earlier single-file builds left in temp."""
        if not getattr(sys, "frozen", False) or sys.platform != "win32":
            return

        def run():
            try:
                removed = cleanup.remove_leftover_unpack_dirs()
                if removed:
                    logging.info("removed %s leftover unpack folder(s) from earlier versions", removed)
            except Exception:
                logging.exception("leftover cleanup failed")

        threading.Thread(target=run, daemon=True, name="keystow-cleanup").start()

    def _start_dispatcher(self):
        """Run hotkey actions on their own thread, not the keyboard-hook thread.

        Windows silently removes a low-level keyboard hook whose thread does
        not answer in time, so opening or closing the microphone must never
        happen inside the hook callback.
        """
        if self._action_thread is not None:
            return
        actions = queue.SimpleQueue()
        thread = threading.Thread(target=self._run_actions, args=(actions,),
                                  daemon=True, name="keystow-hotkey")
        self._actions = actions
        self._action_thread = thread
        thread.start()

    def _run_actions(self, actions):
        while True:
            action = actions.get()
            if action is None:
                return
            try:
                action()
            except Exception:
                logging.exception("hotkey action failed")

    def _submit(self, action):
        """Queue a hotkey action, or run it inline before start() (tests)."""
        actions = self._actions
        if actions is None:
            action()
        else:
            actions.put(action)

    def _arm_limit(self):
        """Stop a forgotten recording instead of growing memory without bound."""
        self._cancel_limit()
        limit = config.MAX_RECORD_SECONDS
        if limit <= 0:
            return
        token = object()
        timer = threading.Timer(limit, self._limit_reached, args=(token,))
        timer.daemon = True
        self._limit_token = token
        self._limit_timer = timer
        timer.start()

    def _cancel_limit(self):
        timer, self._limit_timer = self._limit_timer, None
        self._limit_token = None
        if timer is not None:
            timer.cancel()

    def _limit_reached(self, token):
        with self._state_lock:
            # A timer from an earlier recording must not stop the current one.
            if self._limit_token is not token or self._phase != "recording":
                return
            logging.info("recording reached the %s second limit", config.MAX_RECORD_SECONDS)
            self.stop_recording()

    @staticmethod
    def _too_short(audio) -> bool:
        """True for a tap too brief to hold speech, such as a stray key press."""
        size = getattr(audio, "size", None)
        if not isinstance(size, int):
            return False
        return size < int(config.MIN_RECORD_SECONDS * config.SAMPLE_RATE)

    def set_hotkey(self, name: str):
        with self._state_lock:
            if self._phase != "idle":
                return
            key = _resolve_hotkey(name)
            # Persist before activating the new key. A failed write must not
            # leave the control/controller claiming a saved key that differs.
            try:
                settings.set("activation_mode", "toggle" if self._toggle else "hold")
                settings.set("hotkey", name)
            except OSError:
                logging.exception("activation key could not be saved")
                self.window.set_hotkey_label(self._hotkey_name)
                self.window.set_state("Could not save the shortcut. Your previous key is still selected.")
                return
            self._hotkey_name = name
            self._hotkey = key
            self._label = hotkey_label(name)
            self._hotkey_down = False
            self.window.set_hotkey_label(name)
            self.window.set_state(f"Shortcut set to {self._label}.")

    def set_mode(self, mode: str):
        """Hold the key while speaking, or press once to start and again to stop."""
        toggle = mode == "toggle"
        with self._state_lock:
            if self._phase != "idle" or toggle == self._toggle:
                self.window.set_mode(self._toggle)
                return
            try:
                settings.set("activation_mode", mode)
            except OSError:
                logging.exception("activation mode could not be saved")
                self.window.set_mode(self._toggle)
                self.window.set_state("Could not save that choice. The previous one is still in use.")
                return
            self._toggle = toggle
            with self._key_lock:
                self._hotkey_down = False
            self.window.set_mode(toggle)
            self.window.set_state(self._ready_message())

    def start_hotkey_capture(self):
        with self._state_lock:
            if self._phase != "idle":
                return
            self._capturing = True
            self.window.set_state("Press the key you want to use for dictation...", busy=False)

    def _load_model(self, model_size: str):
        # A model that is not on this computer yet is downloaded only after the
        # user agrees, with its size shown. Nothing downloads silently. Ask
        # before taking the state lock: the shortcut must not wait on a dialog.
        extra = {}
        if (self._phase == "idle" and model_cached is not None and getattr(sys, "frozen", False)
                and model_size != BUNDLED_MODEL and not model_cached(model_size)):
            ask = getattr(self.window, "confirm_download", None)
            if ask is None or not ask(model_size):
                self.window.set_model_selection(config.MODEL_SIZE)
                self.window.set_state(self._ready_message() if self.transcriber else
                                      "No model downloaded. Choose a model to continue.")
                return False
            extra = {"allow_download": True}
        with self._state_lock:
            if self._phase != "idle":
                self.window.set_model_selection(config.MODEL_SIZE)
                return False
            self._phase = "loading"
            if extra:
                self.window.set_state(f"Downloading the '{model_size}' model. Dictation stays on this "
                                      "computer; only the model file comes from the internet.", busy=True)
            else:
                self.window.set_state(f"Loading the '{model_size}' model...", busy=True)
            try:
                loader = ModelLoader(lambda: Transcriber(model_size=model_size, **extra))
                loader.ready.connect(lambda: self._model_ready(loader, model_size))
                loader.failed.connect(lambda msg: self._model_failed(loader, msg))
                self._loader = loader
                loader.start()
            except Exception as exc:  # failed even to start the loader
                self._phase = "idle"
                self.window.set_model_selection(config.MODEL_SIZE)
                self.window.set_state(f"Model failed to load: {exc}", busy=False)
                return False
            return True

    def _model_ready(self, loader: ModelLoader, model_size: str):
        with self._state_lock:
            if self._closing or loader is not self._loader:
                return
            self.transcriber = loader.transcriber
            config.MODEL_SIZE = model_size
            self.window.set_model_selection(model_size)
            self._phase = "idle"
            self.window.set_state(self._ready_message())

    def _model_failed(self, loader: ModelLoader, message: str):
        with self._state_lock:
            if self._closing or loader is not self._loader:
                return
            self._phase = "idle"
            self.window.set_model_selection(config.MODEL_SIZE)
            recovery = "Previous model is still ready." if self.transcriber else "Choose a model to retry."
            self.window.set_state(f"Model failed to load: {message}. {recovery}", busy=False)

    def _ready_message(self):
        if self._layout_failed:
            return ("KeyStow could not read your keyboard layout, so the shortcut is off for now. "
                    "Quit and reopen KeyStow to try again. Meanwhile you can dictate with the "
                    "button below and copy the text.")
        if self._hotkey_blocked:
            return ("Your Mac is blocking the shortcut. Allow KeyStow under System Settings > "
                    "Privacy & Security > Accessibility, then quit and reopen KeyStow.")
        verb = "Press" if self._toggle else "Hold"
        return f"Ready. {verb} {self._label} anywhere to speak."

    @staticmethod
    def _silent(audio) -> bool:
        """True when every sample is exactly zero: a muted or blocked microphone.

        A working microphone always carries some noise. macOS in particular
        hands an app silence, with no error, until the user allows the
        microphone.
        """
        size = getattr(audio, "size", None)
        if not isinstance(size, int) or size == 0:
            return False
        try:
            return not bool(audio.any())
        except Exception:
            return False

    @staticmethod
    def _silence_message() -> str:
        if sys.platform == "darwin":
            where = "System Settings > Privacy & Security > Microphone"
        else:
            where = "Settings > Privacy & security > Microphone"
        return ("No sound reached KeyStow. Check that your microphone is not muted "
                f"and that KeyStow is allowed to use it ({where}).")

    def _start_from_key(self):
        self.start_recording(from_key=True)

    def _key_state_reader(self):
        """A function telling whether a virtual key is physically held, or None."""
        if sys.platform == "win32":
            from . import win_delivery

            return win_delivery.key_down
        if sys.platform == "darwin":
            try:
                import Quartz

                state = Quartz.kCGEventSourceStateHIDSystemState
                return lambda vk: bool(Quartz.CGEventSourceKeyState(state, vk))
            except Exception:
                return None
        return None

    @staticmethod
    def _key_state_hidden() -> bool:
        """Windows may hide key state while a more privileged window is in front."""
        if sys.platform != "win32":
            return False
        try:
            from . import win_delivery

            front = win_delivery.capture_target()
            return front is None or win_delivery._target_is_more_privileged(front.pid)
        except Exception:
            return True

    def _watch_release(self, capture_id):
        """Catch a key release the system never reported.

        Windows skips a keyboard hook that answers late, so under load a
        release can be lost. The recording would then run on and swallow the
        next dictation, or stop at the time limit and paste much later. While
        recording from the key, check the physical key a few times a second.
        """
        vk = getattr(getattr(self._hotkey, "value", self._hotkey), "vk", None)
        held = self._key_state_reader() if isinstance(vk, int) else None
        if held is None:
            return
        token = object()
        self._watch_token = token

        def run():
            misses = 0
            while True:
                time.sleep(0.08)
                with self._state_lock:
                    if (self._watch_token is not token or self._phase != "recording"
                            or self._capture_id != capture_id):
                        return
                try:
                    down = held(vk)
                except Exception:
                    return
                misses = 0 if down else misses + 1
                if misses >= 2 and self._key_state_hidden():
                    misses = 0  # cannot tell; trust the normal release event
                if misses >= 2:
                    with self._key_lock:
                        missed = self._hotkey_down
                        self._hotkey_down = False
                    if missed:
                        logging.info("recovered a key release the system did not report")
                        self._submit(self.stop_recording)
                    return

        threading.Thread(target=run, daemon=True, name="keystow-release-watch").start()

    def copy_latest(self):
        """The user's explicit Copy of the latest dictation (kept in memory only)."""
        text = self._last_text
        if not text:
            self.window.set_state("Nothing to copy yet. Dictate first.")
            return
        try:
            ok = copy_text(text) if copy_text is not None else False
        except Exception:
            logging.exception("copy of the latest dictation failed")
            ok = False
        paste = "Command-V" if sys.platform == "darwin" else "Ctrl+V"
        self.window.set_state(f"Copied. Press {paste} where you want the text." if ok else
                              "Could not reach the clipboard. Try Copy again in a moment.")

    def start_recording(self, from_key: bool = False):
        with self._state_lock:
            if self._phase != "idle" or self.transcriber is None:
                return
            stream = None
            try:
                # Noise suppression runs while the user speaks, not after.
                if getattr(self.recorder, "supports_sink", False):
                    stream = denoise.start_streaming()
                if stream is not None:
                    self.recorder.start(sink=stream.push)
                else:
                    self.recorder.start()
                self._denoise_stream = stream
                self._phase = "recording"
                self._capture_id += 1
                self._from_key = from_key
                self._timing = timings.Dictation()
                self._arm_limit()
                if from_key and not self._toggle:
                    self._watch_release(self._capture_id)
                if self._toggle:
                    self.window.set_state(f"Listening... press {self._label} again to finish.", recording=True)
                else:
                    self.window.set_state("Listening... let go to finish.", recording=True)
            except Exception as exc:  # noqa: BLE001
                self._phase = "idle"
                self._discard_denoise(stream)
                self.window.set_state(f"Microphone error: {exc}. Check access and try again.")

    def _discard_denoise(self, stream=None):
        """Stop a streaming denoiser whose recording will not be transcribed."""
        stream = stream or getattr(self, "_denoise_stream", None)
        self._denoise_stream = None
        if stream is not None:
            try:
                stream.cancel()
            except Exception:
                logging.exception("noise suppression cleanup failed")

    def stop_recording(self):
        with self._state_lock:
            if self._phase != "recording":
                return
            # Reserve processing before releasing the state lock. No new
            # recording/model swap can slip between stop and worker launch.
            self._phase = "processing"
            self._cancel_limit()
            self._watch_token = None
            stream, self._denoise_stream = getattr(self, "_denoise_stream", None), None
            try:
                # The destination is the window in front when the user lets
                # go: the text goes there or, if focus moves, nowhere.
                target = None
                if capture_target is not None:
                    try:
                        target = capture_target()
                    except Exception:
                        logging.exception("could not read the foreground window")
                audio = self.recorder.stop()
                timing = getattr(self, "_timing", None)
                if timing is not None:
                    timing.mark("capture")
                if self._too_short(audio):
                    # A stray tap of the key, not speech: never run the model
                    # or paste anything for it.
                    self._phase = "idle"
                    self._discard_denoise(stream)
                    hint = "Press" if self._toggle else "Hold"
                    self.window.set_state(
                        f"Too short, so nothing was typed. {hint} {self._label} and speak.", busy=False)
                    return
                if self._silent(audio):
                    # Nothing was captured at all, so the model has nothing to
                    # hear. Say why instead of "didn't catch that".
                    self._phase = "idle"
                    self._discard_denoise(stream)
                    self.window.set_state(self._silence_message(), busy=False)
                    return
                model = self.transcriber
                self.window.set_state("Transcribing...", busy=True)
                worker = threading.Thread(target=self._transcribe_and_type,
                                          args=(audio, model, self._capture_id, target, timing, stream),
                                          daemon=True)
                self._worker = worker
                worker.start()
            except Exception as exc:  # noqa: BLE001
                logging.exception("recording stop or worker startup failed")
                self._phase = "idle"
                self._discard_denoise(stream)
                self.window.set_state(f"Couldn't finish recording: {exc}. Try again.", busy=False)

    def toggle_recording(self):
        with self._state_lock:
            if self._phase == "recording":
                self.stop_recording()
            elif self._phase == "idle":
                self.start_recording()

    def _key_name(self, key) -> str:
        name = getattr(key, "name", None)
        if name:
            return name
        return getattr(key, "char", None) or str(key)

    def _on_press(self, key):
        # Called on the keyboard-hook thread for every key on the system,
        # including the Ctrl+V this app injects to paste. Decide without the
        # state lock whether the key is ours, and never do slow work here.
        if self._closing:
            return
        if self._capture_release_key is not None and key == self._capture_release_key:
            return  # repeats of the key just chosen, until it is let go
        if not self._capturing and key != self._hotkey:
            return
        try:
            with self._key_lock:
                if self._capturing:
                    self._capturing = False
                    self._capture_release_key = key
                    name = self._key_name(key)
                    # Saving touches the disk: never on the keyboard-hook
                    # thread, which Windows drops if it answers too slowly.
                    self._submit(lambda: self.set_hotkey(name))
                    return
                if key != self._hotkey:
                    return
                if self._hotkey_down:
                    return  # OS auto-repeat is not a new physical press
                self._hotkey_down = True
            self._submit(self.toggle_recording if self._toggle else self._start_from_key)
        except Exception:
            logging.exception("hotkey press handler failed")

    def _on_release(self, key):
        if self._closing:
            return
        if self._capture_release_key is not None and key == self._capture_release_key:
            self._capture_release_key = None
            return
        if key != self._hotkey:
            return
        try:
            with self._key_lock:
                was_down = self._hotkey_down
                self._hotkey_down = False
            if was_down and not self._toggle:
                self._submit(self.stop_recording)
        except Exception:
            logging.exception("hotkey release handler failed")

    def shutdown(self):
        """Reject new work and prevent a late inference result from pasting.

        A running model load is not forcibly terminated. The UI keeps the Qt
        event loop alive until it finishes, avoiding QThread destruction.
        """
        with self._state_lock:
            if self._closing:
                return
            was_recording = self._phase == "recording"
            self._closing = True
            self._phase = "closing"
            self._last_text = None  # the latest dictation lives in memory only
            self._watch_token = None
            self._capturing = False
            self._hotkey_down = False
            self._cancel_limit()
            if was_recording:
                try:
                    self.recorder.stop()  # discard audio on explicit quit
                except Exception:
                    logging.exception("microphone cleanup during quit failed")
                self._discard_denoise()
            if self._listener is not None:
                self._listener.stop()
            if self._actions is not None:
                self._actions.put(None)  # let the hotkey action thread finish

    def can_exit(self):
        loader = getattr(self, "_loader", None)
        worker = getattr(self, "_worker", None)
        return (loader is None or not loader.isRunning()) and (worker is None or not worker.is_alive())

    def wait_for_shutdown(self):
        """Final safety net for an OS-triggered exit outside the tray path."""
        self.shutdown()
        loader = getattr(self, "_loader", None)
        if loader is not None and loader.isRunning():
            loader.wait()
        worker = getattr(self, "_worker", None)
        if worker is not None and worker is not threading.current_thread():
            worker.join()
        actions = self._action_thread
        if actions is not None and actions is not threading.current_thread():
            actions.join(timeout=2)

    def _is_closing(self) -> bool:
        with self._state_lock:
            return self._closing

    def _claim_delivery(self, capture_id) -> bool:
        """One recording, at most one insertion: the first claim wins."""
        with self._state_lock:
            if capture_id is not None and self._delivered_id == capture_id:
                return False
            self._delivered_id = capture_id
            return not self._closing

    def _outcome_message(self, outcome) -> str:
        verb = "Press" if self._toggle else "Hold"
        again = f"{verb} {self._label} to speak again."
        kind = getattr(outcome, "outcome", "requested")
        if kind == "confirmed":
            return f"Pasted. {again}"
        if kind == "unconfirmed":
            return ("Paste sent, but KeyStow could not confirm the app took it. The text is still "
                    "on the clipboard and shown below; check before you send.")
        if kind == "manual":
            return _MANUAL_MESSAGES.get(getattr(outcome, "reason", ""), _MANUAL_DEFAULT)
        return f"Paste requested. {again}"

    def _transcribe_and_type(self, audio, model, capture_id=None, target=None, timing=None,
                             stream=None):
        # Stay processing through paste. Quit wins over any result that has
        # not yet started insertion. Already-dispatched OS paste cannot undo.
        #
        # The phase stays "processing" until the end, which is what keeps a new
        # capture or model switch out. The state lock itself is NOT held across
        # disk, clipboard or key I/O: the injected paste keys pass through this
        # app's own keyboard hook, and no hotkey or UI thread may wait on them.
        result = "Didn't catch that - try again."
        facts = {"outcome": "none"}
        try:
            denoised = None
            if stream is not None:
                # Most of the noise suppression already happened while the
                # user spoke; this only finishes the last moments.
                try:
                    denoised = stream.finish(int(getattr(audio, "size", 0) or 0))
                except Exception:
                    logging.exception("streamed noise suppression failed; denoising the whole recording")
                if timing is not None:
                    timing.mark("denoise_tail")
            if not model:
                text = ""
            elif denoised is not None:
                text = model.transcribe(audio, denoised=denoised)
            else:
                text = model.transcribe(audio)
            if timing is not None:
                timing.mark("transcribe")
                steps = getattr(model, "last_timings", None)
                if isinstance(steps, dict):
                    timing.steps.extend((f"transcribe.{k}", v) for k, v in steps.items()
                                        if isinstance(v, (int, float)))
            if self._is_closing():
                return
            if text:
                self._last_text = text
                self.window.show_transcript(text)
                # Statistics are secondary; a disk error must not lose
                # otherwise usable dictation.
                try:
                    stats.add_words(len(text.split()))
                    self.window.refresh_stats()
                except Exception:
                    logging.exception("word statistics could not be saved")
                if timing is not None:
                    timing.mark("stats")
                if not self._claim_delivery(capture_id):
                    return
                try:
                    if deliver is not None:
                        outcome = deliver(text, target)
                    else:
                        type_text(text)
                        outcome = None
                    facts = {"outcome": getattr(outcome, "outcome", "requested"),
                             "reason": getattr(outcome, "reason", "") or "-",
                             "restored": bool(getattr(outcome, "restored", False))}
                    result = self._outcome_message(outcome)
                except Exception as exc:
                    facts = {"outcome": "error"}
                    if getattr(exc, "left_on_clipboard", False):
                        if getattr(exc, "reason", "accessibility") == "no_controller":
                            logging.warning("paste keys unavailable; text left on the clipboard")
                            result = ("KeyStow could not send the paste keys this time. The text is on "
                                      "the clipboard: press Command-V.")
                        else:
                            # A Mac without Accessibility access: no keys were sent.
                            logging.warning("paste blocked by macOS; text left on the clipboard")
                            result = ("Your Mac did not let KeyStow paste. The text is on the clipboard: "
                                      "press Command-V. To fix this, allow KeyStow under System Settings > "
                                      "Privacy & Security > Accessibility, then quit and reopen KeyStow.")
                    else:
                        logging.exception("typing failed")
                        result = "Paste or clipboard cleanup failed. Text may already be inserted; check the destination before retrying. Your transcript is shown below."
                if timing is not None:
                    timing.mark("deliver")
        except Exception as exc:
            logging.exception("transcription failed")
            result = f"Transcription failed: {exc}. Try again."
        finally:
            if timing is not None:
                timing.finish(samples=int(getattr(audio, "size", 0) or 0), **facts)
            with self._state_lock:
                if not self._closing:
                    self._phase = "idle"
                    self.window.set_state(result, busy=False)


def _self_test(arguments) -> int:
    """Release-build check of the packaged app: load the shipped model, run it.

    Opens no window and uses no microphone, shortcut or network. Exit code 0
    means the speech model inside the package loaded and turned one second of
    silence into no text, and on Windows that the noise-suppression library
    loaded. The release workflow runs this on the built app before publishing.
    """
    import json
    import platform

    report = {"ok": False, "version": __version__, "frozen": bool(getattr(sys, "frozen", False)),
              "platform": sys.platform, "machine": platform.machine()}
    code = 1
    try:
        import numpy as np

        from . import denoise
        from .transcriber import _resolve_model

        source = _resolve_model(config.MODEL_SIZE)
        report["model_source"] = source
        report["model_bundled"] = os.path.isdir(source)
        if report["frozen"] and not report["model_bundled"]:
            raise RuntimeError("the packaged app does not contain its speech model")
        model = Transcriber()
        text = model.transcribe(np.zeros(config.SAMPLE_RATE, dtype="float32"))
        report["silence_text"] = text
        report["noise_suppression_native"] = denoise._denoiser is not None and not denoise._unavailable
        if text != "":
            raise RuntimeError("silence produced text")
        if report["frozen"] and sys.platform == "win32" and not report["noise_suppression_native"]:
            raise RuntimeError("the noise-suppression library did not load")
        for argument in arguments:
            if argument.startswith("--self-test-audio="):
                from faster_whisper import decode_audio

                speech = decode_audio(argument.split("=", 1)[1], sampling_rate=config.SAMPLE_RATE)
                report["speech_text"] = model.transcribe(speech)
                if not report["speech_text"]:
                    raise RuntimeError("the speech sample produced no text")
        report["ok"] = True
        code = 0
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"{type(exc).__name__}: {exc}"
    for argument in arguments:
        if argument.startswith("--self-test-out="):
            try:
                with open(argument.split("=", 1)[1], "w", encoding="utf-8") as handle:
                    json.dump(report, handle, indent=2)
            except OSError:
                pass
    return code


def main() -> None:
    if "--self-test" in sys.argv[1:]:
        sys.exit(_self_test(sys.argv[1:]))
    crashlog.setup()
    run_app(VoiceController)
