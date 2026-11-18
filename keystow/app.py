"""KeyStow controller: one recording, model load or transcription at a time."""

import logging
import threading

from pynput import keyboard

from . import config, crashlog, settings, stats
from .recorder import PushToTalkRecorder
from .transcriber import Transcriber
from .typer import type_text
from .ui import MainWindow, ModelLoader, hotkey_label, run_app

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
        self._phase = "idle"
        self._closing = False
        self._listener = None
        self._hotkey_down = False
        self._capturing = False
        self._toggle = settings.toggle_mode()
        self._hotkey_name = settings.get("hotkey", config.HOTKEY)
        self._hotkey = _resolve_hotkey(self._hotkey_name)
        self._label = hotkey_label(self._hotkey_name)
        window._on_model_change = self._load_model
        window.hotkey_selected.connect(self.set_hotkey)
        window.hotkey_capture_requested.connect(self.start_hotkey_capture)
        if self._toggle:
            window.record_toggled.connect(self.toggle_recording)
        else:
            window.record_pressed.connect(self.start_recording)
            window.record_released.connect(self.stop_recording)

    def start(self):
        self._load_model(config.MODEL_SIZE)
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._listener.start()

    def set_hotkey(self, name: str):
        with self._state_lock:
            if self._phase != "idle":
                return
            self._hotkey_name = name
            self._hotkey = _resolve_hotkey(name)
            self._label = hotkey_label(name)
            self._hotkey_down = False
            # Save mode first, so a new hold-mode key is never mistaken for
            # a pre-hold-default legacy customization after restart.
            settings.set("activation_mode", "toggle" if self._toggle else "hold")
            settings.set("hotkey", name)
            self.window.set_hotkey_label(name)
            self.window.set_state(f"Activation key set to [{self._label}].")

    def start_hotkey_capture(self):
        with self._state_lock:
            if self._phase != "idle":
                return
            self._capturing = True
            self.window.set_state("Press the key you want to use to talk...", busy=False)

    def _load_model(self, model_size: str):
        with self._state_lock:
            if self._phase != "idle":
                self.window.set_model_selection(config.MODEL_SIZE)
                return False
            self._phase = "loading"
            self.window.set_state(f"Loading '{model_size}' - non-bundled models need a download.", busy=True)
            try:
                loader = ModelLoader(lambda: Transcriber(model_size=model_size))
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
        verb = "Press" if self._toggle else "Hold"
        return f"Ready. {verb} [{self._label}] anywhere to speak."

    def start_recording(self):
        with self._state_lock:
            if self._phase != "idle" or self.transcriber is None:
                return
            try:
                self.recorder.start()
                self._phase = "recording"
                if self._toggle:
                    self.window.set_state(f"Listening... press [{self._label}] again to type.", recording=True)
                else:
                    self.window.set_state("Listening... release to type.", recording=True)
            except Exception as exc:  # noqa: BLE001
                self._phase = "idle"
                self.window.set_state(f"Microphone error: {exc}. Check access and try again.")

    def stop_recording(self):
        with self._state_lock:
            if self._phase != "recording":
                return
            # Reserve processing before releasing the state lock. No new
            # recording/model swap can slip between stop and worker launch.
            self._phase = "processing"
            try:
                audio = self.recorder.stop()
                model = self.transcriber
                self.window.set_state("Transcribing...", busy=True)
                worker = threading.Thread(target=self._transcribe_and_type,
                                          args=(audio, model), daemon=True)
                self._worker = worker
                worker.start()
            except Exception as exc:  # noqa: BLE001
                logging.exception("recording stop or worker startup failed")
                self._phase = "idle"
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
        try:
            with self._state_lock:
                if self._closing:
                    return
                if self._capturing:
                    self._capturing = False
                    self.set_hotkey(self._key_name(key))
                    # Consume capture key repeats until its matching release.
                    self._hotkey_down = key == self._hotkey
                    return
                if key != self._hotkey:
                    return
                if self._hotkey_down:
                    return  # OS auto-repeat is not a new physical press
                self._hotkey_down = True
                if self._toggle:
                    self.toggle_recording()
                else:
                    self.start_recording()
        except Exception:
            logging.exception("hotkey press handler failed")

    def _on_release(self, key):
        try:
            with self._state_lock:
                if self._closing:
                    return
                if key != self._hotkey:
                    return
                was_down = self._hotkey_down
                self._hotkey_down = False
                if was_down and not self._toggle:
                    self.stop_recording()
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
            self._capturing = False
            self._hotkey_down = False
            if was_recording:
                try:
                    self.recorder.stop()  # discard audio on explicit quit
                except Exception:
                    logging.exception("microphone cleanup during quit failed")
            if self._listener is not None:
                self._listener.stop()

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

    def _transcribe_and_type(self, audio, model):
        # Stay processing through paste. Quit wins over any result that has
        # not yet started insertion. Already-dispatched OS paste cannot undo.
        result = "Didn't catch that - try again."
        try:
            text = model.transcribe(audio) if model else ""
            with self._state_lock:
                if self._closing:
                    return
                if text:
                    self.window.show_transcript(text)
                    # Statistics are secondary; a disk error must not lose
                    # otherwise usable dictation.
                    try:
                        stats.add_words(len(text.split()))
                        self.window.refresh_stats()
                    except Exception:
                        logging.exception("word statistics could not be saved")
                    try:
                        type_text(text)
                    except Exception:
                        logging.exception("typing failed")
                        result = "Couldn't paste into the other app. Your transcript is shown below."
                    else:
                        verb = "Press" if self._toggle else "Hold"
                        result = f"Paste requested. {verb} [{self._label}] to speak again."
        except Exception as exc:
            logging.exception("transcription failed")
            result = f"Transcription failed: {exc}. Try again."
        finally:
            with self._state_lock:
                if not self._closing:
                    self._phase = "idle"
                    self.window.set_state(result, busy=False)


def main() -> None:
    crashlog.setup()
    run_app(VoiceController)
