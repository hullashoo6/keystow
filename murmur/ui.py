"""Murmur UI: lives in the system tray, with a small window on demand (PySide6)."""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from . import autostart, config, settings, stats

ACCENT = "#6C5CE7"
BG = "#1E1E2E"
CARD = "#2A2A3C"
TEXT = "#F5F5F7"
MUTED = "#9C9CAF"

HOTKEY_PRESETS = [
    ("Right Ctrl", "ctrl_r"),
    ("Caps Lock", "caps_lock"),
    ("Right Shift", "shift_r"),
    ("Right Alt", "alt_r"),
]
CUSTOM_KEY = "__custom__"


def hotkey_label(name: str) -> str:
    for label, key_name in HOTKEY_PRESETS:
        if key_name == name:
            return label
    return name.replace("_", " ").title()

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


def _tray_icon(color: str) -> QIcon:
    """Draw a simple round tray icon in the given color."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(4, 4, 24, 24)
    painter.end()
    return QIcon(pixmap)


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
    """Tray-first app: status, a big talk button, transcript preview, on demand."""

    record_pressed = Signal()
    record_released = Signal()
    record_toggled = Signal()
    hotkey_selected = Signal(str)
    hotkey_capture_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Murmur")
        self.setMinimumWidth(360)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._toggle = config.TOGGLE_MODE
        self._hotkey_name = settings.get("hotkey", config.HOTKEY)
        self._hotkey_label = hotkey_label(self._hotkey_name)

        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Murmur")
        title.setObjectName("title")
        layout.addWidget(title)

        self.status = QLabel("Loading the speech model - first run downloads it, once.")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)

        self.record_btn = QPushButton()
        self.record_btn.setObjectName("record")
        self.record_btn.setMinimumHeight(64)
        self.record_btn.setEnabled(False)
        if self._toggle:
            self.record_btn.setText("Click to talk")
            self.record_btn.clicked.connect(self.record_toggled)
        else:
            self.record_btn.setText("Hold to talk")
            self.record_btn.pressed.connect(self.record_pressed)
            self.record_btn.released.connect(self.record_released)
        layout.addWidget(self.record_btn)

        self.hint = QLabel()
        self.hint.setObjectName("status")
        self.hint.setAlignment(Qt.AlignCenter)
        self._update_hint()
        layout.addWidget(self.hint)

        self.transcript = QLabel("Your words will appear here - and type themselves where your cursor is.")
        self.transcript.setObjectName("transcript")
        self.transcript.setWordWrap(True)
        layout.addWidget(self.transcript)

        self.stats_label = QLabel()
        self.stats_label.setObjectName("status")
        self.stats_label.setAlignment(Qt.AlignCenter)
        self.refresh_stats()
        layout.addWidget(self.stats_label)

        row = QHBoxLayout()
        row.addWidget(QLabel("Model"))
        self.model_box = QComboBox()
        self.model_box.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self.model_box.setCurrentText(config.MODEL_SIZE)
        self.model_box.setToolTip("Bigger = more accurate, slower. 'base' is a good start.")
        row.addWidget(self.model_box)

        row.addSpacing(12)
        row.addWidget(QLabel("Key"))
        self.hotkey_box = QComboBox()
        for label, key_name in HOTKEY_PRESETS:
            self.hotkey_box.addItem(label, key_name)
        self.hotkey_box.addItem("Custom key...", CUSTOM_KEY)
        idx = self.hotkey_box.findData(self._hotkey_name)
        self.hotkey_box.setCurrentIndex(idx if idx >= 0 else 0)
        self.hotkey_box.setToolTip("Press this key to start and stop listening.")
        self.hotkey_box.currentIndexChanged.connect(self._hotkey_combo_changed)
        row.addWidget(self.hotkey_box)
        row.addStretch()
        layout.addLayout(row)

        wrapper = QWidget()
        outer = QVBoxLayout(wrapper)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.addWidget(card)
        self.setCentralWidget(wrapper)

        self.model_box.currentTextChanged.connect(self._model_changed)
        self._on_model_change = None

        # --- system tray ---
        self._icon_idle = _tray_icon("#8a8aa0")
        self._icon_listening = _tray_icon(ACCENT)
        self.tray = QSystemTrayIcon(self._icon_idle, self)
        self.tray.setToolTip("Murmur")
        menu = QMenu()
        open_action = QAction("Open Murmur", self)
        open_action.triggered.connect(self.show_and_raise)
        menu.addAction(open_action)

        hotkey_menu = menu.addMenu("Activation key")
        group = QActionGroup(self)
        group.setExclusive(True)
        for label, key_name in HOTKEY_PRESETS:
            action = QAction(label, self, checkable=True)
            action.setChecked(key_name == self._hotkey_name)
            action.triggered.connect(lambda checked=False, k=key_name: self._hotkey_menu_pick(k))
            group.addAction(action)
            hotkey_menu.addAction(action)
        custom_action = QAction("Custom key...", self)
        custom_action.triggered.connect(self._hotkey_capture_pick)
        hotkey_menu.addAction(custom_action)
        self._hotkey_group = group

        self.autostart_action = QAction("Start with Windows", self)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(autostart.is_enabled())
        self.autostart_action.triggered.connect(self._toggle_autostart)
        menu.addAction(self.autostart_action)
        menu.addSeparator()
        quit_action = QAction("Quit Murmur", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    # --- hotkey selection ---

    def _hotkey_combo_changed(self, index):
        key_name = self.hotkey_box.itemData(index)
        if key_name == CUSTOM_KEY:
            self.hotkey_capture_requested.emit()
            self.show_and_raise()
            return
        self._hotkey_name = key_name
        self._hotkey_label = hotkey_label(key_name)
        self._update_hint()
        self.hotkey_selected.emit(key_name)

    def _hotkey_menu_pick(self, key_name):
        self._hotkey_name = key_name
        self._hotkey_label = hotkey_label(key_name)
        self._update_hint()
        idx = self.hotkey_box.findData(key_name)
        if idx >= 0:
            self.hotkey_box.setCurrentIndex(idx)
        else:
            self.hotkey_selected.emit(key_name)

    def _hotkey_capture_pick(self):
        self.hotkey_capture_requested.emit()
        self.show_and_raise()

    def set_hotkey_label(self, name: str):
        """Called by the controller after a hotkey change (e.g. custom capture)."""
        self._hotkey_name = name
        self._hotkey_label = hotkey_label(name)
        self._update_hint()
        idx = self.hotkey_box.findData(name)
        if idx >= 0:
            self.hotkey_box.blockSignals(True)
            self.hotkey_box.setCurrentIndex(idx)
            self.hotkey_box.blockSignals(False)
        for action in self._hotkey_group.actions():
            action.blockSignals(True)
        # presets only have checkable entries; custom keys leave all unchecked
        for action in self._hotkey_group.actions():
            action.blockSignals(False)

    def _update_hint(self):
        verb = "press" if self._toggle else "hold"
        self.hint.setText(f"or {verb} [{self._hotkey_label}] anywhere")

    # --- tray & window plumbing ---

    def _toggle_autostart(self, checked):
        try:
            autostart.set_enabled(checked)
        except OSError:
            self.autostart_action.setChecked(not checked)

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_and_raise()

    def show_and_raise(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        # Closing the window hides it to the tray; use Quit in the tray menu to exit.
        event.ignore()
        self.hide()

    def _model_changed(self, name):
        if self._on_model_change:
            self._on_model_change(name)

    def set_state(self, text: str, recording: bool = False, busy: bool = False):
        self.status.setText(text)
        if recording:
            self.record_btn.setText("Listening...")
        else:
            self.record_btn.setText("Click to talk" if self._toggle else "Hold to talk")
        self.record_btn.setEnabled(not busy)
        self.progress.setVisible(busy)
        self.tray.setIcon(self._icon_listening if recording else self._icon_idle)
        self.tray.setToolTip(f"Murmur - {'listening...' if recording else text}")

    def show_transcript(self, text: str):
        self.transcript.setText(text)

    def refresh_stats(self):
        self.stats_label.setText(
            f"Words dictated - today: {stats.today():,}  |  all time: {stats.total():,}"
        )


def run_app(controller_factory):
    """Start the Qt app. *controller_factory(window)* wires the voice logic."""
    import sys

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # keep running in the tray
    window = MainWindow()
    controller_factory(window)
    window.show()  # first launch shows the window; after that it hides to the tray
    sys.exit(app.exec())
