"""Murmur voice typing controller: toggle (or hold) hotkey -> transcribe -> type."""

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
        self._busy = threading.Lock()
        self._listener = None
        self._hotkey_down = False
        self._capturing = False
        self._toggle = config.TOGGLE_MODE
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

    # --- hotkey configuration ---

    def set_hotkey(self, name: str):
        self._hotkey_name = name
        self._hotkey = _resolve_hotkey(name)
        self._label = hotkey_label(name)
        settings.set("hotkey", name)
        self.window.set_hotkey_label(name)
        self.window.set_state(f"Activation key set to [{self._label}].")

    def start_hotkey_capture(self):
        self._capturing = True
        self.window.set_state("Press the key you want to use to talk...", busy=False)

    # --- model ---

    def _load_model(self, model_size: str):
        self.window.set_state(f"Loading the '{model_size}' model - first run downloads it, once.", busy=True)
        config.MODEL_SIZE = model_size
        loader = ModelLoader(lambda: Transcriber(model_size=model_size))
        loader.ready.connect(lambda: self._model_ready(loader))
        loader.failed.connect(lambda msg: self.window.set_state(f"Model failed to load: {msg}", busy=False))
        loader.start()
        self._loader = loader  # keep a reference

    def _model_ready(self, loader: ModelLoader):
        self.transcriber = loader.transcriber
        if self._toggle:
            self.window.set_state(f"Ready. Press [{self._label}] anywhere to speak.")
        else:
            self.window.set_state(f"Ready. Hold [{self._label}] anywhere and speak.")

    # --- recording ---

    def start_recording(self):
        if self.transcriber is None or self.recorder.is_recording:
            return
        try:
            self.recorder.start()
            if self._toggle:
                self.window.set_state(f"Listening... press [{self._label}] again to type.", recording=True)
            else:
                self.window.set_state("Listening... release to type.", recording=True)
        except Exception as exc:  # noqa: BLE001
            self.window.set_state(f"Microphone error: {exc}")

    def stop_recording(self):
        if not self.recorder.is_recording:
            return
        audio = self.recorder.stop()
        self.window.set_state("Transcribing...", busy=True)
        threading.Thread(target=self._transcribe_and_type, args=(audio,), daemon=True).start()

    def toggle_recording(self):
        if self.recorder.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    # --- hotkey handling ---

    def _key_name(self, key) -> str:
        name = getattr(key, "name", None)
        if name:
            return name
        char = getattr(key, "char", None)
        return char or str(key)

    def _on_press(self, key):
        # Runs on the keyboard-listener thread: never let an exception kill it.
        try:
            if self._capturing:
                self._capturing = False
                self.set_hotkey(self._key_name(key))
                return
            if key != self._hotkey:
                return
            if self._toggle:
                if not self._hotkey_down:
                    self._hotkey_down = True
                    self.toggle_recording()
            else:
                self.start_recording()
        except Exception:
            import logging

            logging.exception("hotkey press handler failed")

    def _on_release(self, key):
        try:
            if key != self._hotkey:
                return
            self._hotkey_down = False
            if not self._toggle:
                self.stop_recording()
        except Exception:
            import logging

            logging.exception("hotkey release handler failed")

    def _transcribe_and_type(self, audio):
        import logging

        try:
            text = self.transcriber.transcribe(audio) if self.transcriber else ""
        except Exception as exc:
            logging.exception("transcription failed")
            self.window.set_state(f"Transcription failed: {exc}", busy=False)
            return
        if text:
            stats.add_words(len(text.split()))
            self.window.show_transcript(text)
            self.window.refresh_stats()
            try:
                type_text(text)
            except Exception:
                logging.exception("typing failed")
                self.window.set_state("Couldn't type into the other app - text is above, copy it.")
                return
            if self._toggle:
                self.window.set_state(f"Typed. Press [{self._label}] to speak again.")
            else:
                self.window.set_state(f"Typed. Hold [{self._label}] to speak again.")
        else:
            self.window.set_state("Didn't catch that - try again.")


def main() -> None:
    crashlog.setup()
    run_app(VoiceController)
