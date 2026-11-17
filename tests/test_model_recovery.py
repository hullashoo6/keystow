"""Connected Qt/controller model-failure recovery, with peripheral I/O replaced."""
import os
import subprocess
import sys
import textwrap
import unittest


class ModelRecoveryJourneyTest(unittest.TestCase):
    def test_failed_download_returns_ui_and_next_session_to_existing_model(self):
        script = textwrap.dedent('''
            import importlib.util
            import sys
            import types
            from pathlib import Path
            from unittest.mock import Mock, patch
            from PySide6.QtCore import QObject, Signal
            from PySide6.QtWidgets import QApplication
            from keystow import ui

            class Loader(QObject):
                ready = Signal()
                failed = Signal(str)
                def __init__(self, factory):
                    super().__init__()
                def start(self):
                    pass
            recorder = Mock()
            recorder.stop.return_value = "audio"
            paste = Mock()
            keyboard = types.SimpleNamespace(Key=types.SimpleNamespace(ctrl_r="ctrl_r"))
            deps = {
                "pynput": types.SimpleNamespace(keyboard=keyboard),
                "keystow.recorder": types.SimpleNamespace(PushToTalkRecorder=lambda:recorder),
                "keystow.transcriber": types.SimpleNamespace(Transcriber=Mock()),
                "keystow.typer": types.SimpleNamespace(type_text=paste),
            }
            spec = importlib.util.spec_from_file_location("keystow._connected_check", Path("keystow/app.py"))
            controller_module = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, deps):
                spec.loader.exec_module(controller_module)
            app = QApplication([])
            with patch.object(ui.autostart, "set_enabled"), \\
                 patch.object(ui.autostart, "is_enabled", return_value=False), \\
                 patch.object(ui.settings, "get", side_effect=lambda k,d=None:d), \\
                 patch.object(ui.settings, "set"), \\
                 patch.object(controller_module, "ModelLoader", Loader), \\
                 patch.object(controller_module.stats, "add_words"):
                window = ui.MainWindow()
                controller = controller_module.VoiceController(window)
                old_model = Mock()
                old_model.transcribe.return_value = "recovered dictation"
                controller.transcriber = old_model
                controller_module.config.MODEL_SIZE = "base"
                window.set_state("Ready.")
                app.processEvents()
                window.model_box.setCurrentText(ui.MODEL_LABELS["turbo"])
                app.processEvents()
                assert controller._phase == "loading"
                assert not window.model_box.isEnabled()
                controller._loader.failed.emit("download interrupted")
                app.processEvents()
                assert window.model_box.currentText() == "base"
                assert window.model_box.isEnabled()
                assert window.hotkey_box.isEnabled()
                assert "Previous model" in window.status.text()
                assert controller.transcriber is old_model
                controller.start_recording()
                app.processEvents()
                assert window.record_btn.text() == "Stop and type"
                controller.stop_recording()
                controller._worker.join(3)
                app.processEvents()
                assert controller._phase == "idle"
                old_model.transcribe.assert_called_once_with("audio")
                paste.assert_called_once_with("recovered dictation")
                assert window.transcript.text() == "recovered dictation"
                assert window.model_box.currentText() == "base"
                assert window.model_box.isEnabled()
        ''')
        result = subprocess.run([sys.executable, '-c', script],
                                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
