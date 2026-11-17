"""Voice typing controller: hotkey + record button -> transcribe -> type."""

import threading

from pynput import keyboard

from . import config
from .recorder import PushToTalkRecorder
from .transcriber import Transcriber
from .typer import type_text
from .ui import MainWindow, ModelLoader, run_app

HOTKEY = getattr(keyboard.Key, config.HOTKEY, keyboard.Key.ctrl_r)
QUIT_KEY = keyboard.Key.esc


class VoiceController:
    def __init__(self, window: MainWindow):
        self.window = window
        self.recorder = PushToTalkRecorder()
        self.transcriber = None
        self._busy = threading.Lock()
        self._listener = None
        window._on_model_change = self._load_model
        window.record_pressed.connect(self.start_recording)
        window.record_released.connect(self.stop_recording)

    def start(self):
        self._load_model(config.MODEL_SIZE)
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._listener.start()

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
        self.window.set_state(
            f"Ready. Hold [{self.window._label_map.get(config.HOTKEY, config.HOTKEY)}] anywhere and speak."
        )

    # --- recording ---

    def start_recording(self):
        if self.transcriber is None or self.recorder.is_recording:
            return
        try:
            self.recorder.start()
            self.window.set_state("Listening... release to type.", recording=True)
        except Exception as exc:  # noqa: BLE001
            self.window.set_state(f"Microphone error: {exc}")

    def stop_recording(self):
        if not self.recorder.is_recording:
            return
        audio = self.recorder.stop()
        self.window.set_state("Transcribing...", busy=True)
        threading.Thread(target=self._transcribe_and_type, args=(audio,), daemon=True).start()

    def _on_press(self, key):
        if key == HOTKEY:
            self.start_recording()

    def _on_release(self, key):
        if key == HOTKEY:
            self.stop_recording()
        elif key == QUIT_KEY:
            self.window.close()
        return True

    def _transcribe_and_type(self, audio):
        with self._busy:
            text = self.transcriber.transcribe(audio) if self.transcriber else ""
            if text:
                self.window.show_transcript(text)
                type_text(text)
                self.window.set_state(
                    f"Typed. Hold [{self.window._label_map.get(config.HOTKEY, config.HOTKEY)}] to speak again."
                )
            else:
                self.window.set_state("Didn't catch that - try again.")


def main() -> None:
    run_app(VoiceController)
