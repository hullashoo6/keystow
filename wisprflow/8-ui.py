"""Minimal floating UI for Wispr Flow Alternative (PySide6)."""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import config

ACCENT = "#6C5CE7"
BG = "#1E1E2E"
CARD = "#2A2A3C"
TEXT = "#F5F5F7"
MUTED = "#9C9CAF"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Segoe UI", "Inter", sans-serif;
}}
#card {{
    background-color: {CARD};
    border-radius: 14px;
}}
QLabel#title {{
    font-size: 18px;
    font-weight: 600;
}}
QLabel#status {{
    color: {MUTED};
    font-size: 13px;
}}
QLabel#transcript {{
    font-size: 15px;
}}
QPushButton#record {{
    background-color: {ACCENT};
    color: white;
    border: none;
    border-radius: 32px;
    font-size: 16px;
    font-weight: 600;
}}
QPushButton#record:pressed {{
    background-color: #5848c2;
}}
QPushButton#record:disabled {{
    background-color: #44445a;
    color: {MUTED};
}}
QComboBox {{
    background-color: {CARD};
    border: none;
    border-radius: 6px;
    padding: 4px 8px;
}}
QProgressBar {{
    background-color: {CARD};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 4px;
}}
"""


class ModelLoader(QThread):
    """Loads the Whisper model off the UI thread."""

    ready = Signal()
    failed = Signal(str)

    def __init__(self, transcriber_factory):
        super().__init__()
        self._factory = transcriber_factory
        self.transcriber = None

    def run(self):
        try:
            self.transcriber = self._factory()
            self.ready.emit()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    """One small window: status, a big record button, transcript preview."""

    record_pressed = Signal()
    record_released = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wispr Flow Alternative")
        self.setMinimumWidth(360)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._label_map = {
            "ctrl_r": "Right Ctrl",
            "ctrl_l": "Left Ctrl",
            "alt_r": "Right Alt",
            "alt_l": "Left Alt",
        }

        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Wispr Flow Alternative")
        title.setObjectName("title")
        layout.addWidget(title)

        self.status = QLabel("Loading the speech model - first run downloads it, once.")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)

        self.record_btn = QPushButton("Hold to talk")
        self.record_btn.setObjectName("record")
        self.record_btn.setMinimumHeight(64)
        self.record_btn.setEnabled(False)
        self.record_btn.pressed.connect(self.record_pressed)
        self.record_btn.released.connect(self.record_released)
        layout.addWidget(self.record_btn)

        hint = QLabel(f"or hold [{self._label_map.get(config.HOTKEY, config.HOTKEY)}] anywhere")
        hint.setObjectName("status")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        self.transcript = QLabel("Your words will appear here - and type themselves where your cursor is.")
        self.transcript.setObjectName("transcript")
        self.transcript.setWordWrap(True)
        layout.addWidget(self.transcript)

        row = QHBoxLayout()
        row.addWidget(QLabel("Model"))
        self.model_box = QComboBox()
        self.model_box.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self.model_box.setCurrentText(config.MODEL_SIZE)
        self.model_box.setToolTip("Bigger = more accurate, slower. 'base' is a good start.")
        row.addWidget(self.model_box)
        row.addStretch()
        layout.addLayout(row)

        wrapper = QWidget()
        outer = QVBoxLayout(wrapper)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.addWidget(card)
        self.setCentralWidget(wrapper)

        self.model_box.currentTextChanged.connect(self._model_changed)
        self._on_model_change = None

    def _model_changed(self, name):
        if self._on_model_change:
            self._on_model_change(name)

    def set_state(self, text: str, recording: bool = False, busy: bool = False):
        self.status.setText(text)
        self.record_btn.setText("Listening..." if recording else "Hold to talk")
        self.record_btn.setEnabled(not busy)
        self.progress.setVisible(busy)

    def show_transcript(self, text: str):
        self.transcript.setText(text)


def run_app(controller_factory):
    """Start the Qt app. *controller_factory(window)* wires the voice logic."""
    import sys

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    controller = controller_factory(window)
    controller.start()
    window.show()
    sys.exit(app.exec())
