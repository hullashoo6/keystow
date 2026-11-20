"""KeyStow UI: lives in the system tray, with a small window on demand (PySide6)."""

import sys
import os

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
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

from . import autostart, config, paths, settings, stats, tray_icons

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

MODEL_CHOICES = ["tiny", "base", "small", "medium", "large-v3", "turbo"]
MODEL_LABELS = {"turbo": "turbo - best accuracy"}
_MODEL_NAME = {v: k for k, v in MODEL_LABELS.items()}


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
QLabel {{
    background-color: transparent;
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
    border: 1px solid #3A3A4E;
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 18px;
    color: {TEXT};
}}
QComboBox:disabled {{
    color: {MUTED};
    border-color: #343447;
    background-color: #252535;
}}
QCheckBox {{
    background-color: transparent;
}}
QComboBox:hover {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {MUTED};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {CARD};
    color: {TEXT};
    border: 1px solid #3A3A4E;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {ACCENT};
    selection-color: white;
    outline: none;
}}
QMenu {{
    background-color: {CARD};
    color: {TEXT};
    border: 1px solid #3A3A4E;
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 6px 28px 6px 12px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background-color: {ACCENT};
    color: white;
}}
QToolTip {{
    background-color: {CARD};
    color: {TEXT};
    border: 1px solid #3A3A4E;
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

    quit_requested = Signal()
    record_pressed = Signal()
    record_released = Signal()
    record_toggled = Signal()
    hotkey_selected = Signal(str)
    hotkey_capture_requested = Signal()
    _sig_state = Signal(str, bool, bool)
    _sig_transcript = Signal(str)
    _sig_stats = Signal()
    _sig_hotkey = Signal(str)
    _sig_model = Signal(str)

    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLESHEET)
        self.setWindowTitle("KeyStow")
        self.setWindowIcon(tray_icons.icon("app", fallback=lambda: _tray_icon(ACCENT)))
        self.setMinimumWidth(360)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._toggle = settings.toggle_mode()
        self._hotkey_name = settings.get("hotkey", config.HOTKEY)
        self._hotkey_label = hotkey_label(self._hotkey_name)

        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(12)

        title = QLabel("KeyStow")
        title.setObjectName("title")
        layout.addWidget(title)

        self.status = QLabel("Loading the speech model. The base model is bundled with the installer.")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.storage_warning = QLabel()
        self.storage_warning.setObjectName("status")
        self.storage_warning.setWordWrap(True)
        if paths.startup_storage_error() is not None:
            self.storage_warning.setText(
                "Local storage could not be opened at startup. Settings and word counts "
                "may not be saved. Check your .keystow path, then restart KeyStow."
            )
        if self.storage_warning.text():
            self.storage_warning.setMinimumHeight(self.storage_warning.heightForWidth(280))
        self.storage_warning.setVisible(bool(self.storage_warning.text()))
        layout.addWidget(self.storage_warning)

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
        self.transcript.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        layout.addWidget(self.transcript)

        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        self.stats_label.setObjectName("status")
        self.stats_label.setAlignment(Qt.AlignCenter)
        self._do_refresh_stats()
        layout.addWidget(self.stats_label)

        row = QHBoxLayout()
        row.addWidget(QLabel("Model"))
        self.model_box = QComboBox()
        self.model_box.addItems([MODEL_LABELS.get(m, m) for m in MODEL_CHOICES])
        self.model_box.setCurrentText(MODEL_LABELS.get(config.MODEL_SIZE, config.MODEL_SIZE))
        self.model_box.setToolTip("'base' comes built in. 'turbo' is the accuracy pick - downloads once.")
        row.addWidget(self.model_box)

        row.addSpacing(12)
        row.addWidget(QLabel("Key"))
        self.hotkey_box = QComboBox()
        for label, key_name in HOTKEY_PRESETS:
            self.hotkey_box.addItem(label, key_name)
        self.hotkey_box.addItem("Custom key...", CUSTOM_KEY)
        idx = self.hotkey_box.findData(self._hotkey_name)
        self.hotkey_box.setCurrentIndex(idx if idx >= 0 else 0)
        self.hotkey_box.setToolTip("Press once to start, again to stop." if self._toggle
                                   else "Hold this key to speak; release to stop and type.")
        self.hotkey_box.currentIndexChanged.connect(self._hotkey_combo_changed)
        row.addWidget(self.hotkey_box)
        row.addStretch()
        layout.addLayout(row)

        opts = QHBoxLayout()
        self.noise_box = QCheckBox("Suppress background noise (fans, hum)")
        self._noise_saved = settings.get("noise_suppression", True)
        self.noise_box.setChecked(self._noise_saved)
        self.noise_box.setToolTip("Cleans up mic noise before transcribing. Leave on.")
        if os.environ.get("KEYSTOW_PRIVATE_TEST_NO_DENOISE") == "1":
            self.noise_box.setChecked(False)
            self.noise_box.setEnabled(False)
            self.noise_box.setText("Noise suppression unavailable in this private test")
            self.noise_box.setToolTip("This private test retains ordinary dictation but omits the optional denoiser.")
        self.noise_box.toggled.connect(self._save_noise_preference)
        opts.addWidget(self.noise_box)
        opts.addStretch()
        layout.addLayout(opts)

        wrapper = QWidget()
        outer = QVBoxLayout(wrapper)
        outer.setContentsMargins(16, 16, 16, 16)
        # Keep the card centered and capped at a comfortable width when the
        # window is maximized, instead of stretching edge to edge.
        outer.addStretch()
        center_row = QHBoxLayout()
        center_row.addStretch()
        card.setMaximumWidth(520)
        center_row.addWidget(card)
        center_row.addStretch()
        outer.addLayout(center_row)
        outer.addStretch()
        self.setCentralWidget(wrapper)

        self.model_box.currentTextChanged.connect(self._model_changed)
        self._on_model_change = None

        # --- system tray ---
        self._icon_idle = tray_icons.icon("idle", fallback=lambda: _tray_icon("#8a8aa0"))
        self._icon_listening = tray_icons.icon("listening", fallback=lambda: _tray_icon(ACCENT))
        self.tray = QSystemTrayIcon(self._icon_idle, self)
        self.tray.setToolTip("KeyStow")
        menu = QMenu()
        open_action = QAction("Open KeyStow", self)
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
        self._custom_key_action = custom_action
        hotkey_menu.addAction(custom_action)
        self._hotkey_group = group

        label = "Start at login" if sys.platform == "darwin" else "Start with Windows"
        self.autostart_action = QAction(label, self)
        self.autostart_action.setCheckable(True)
        if not settings.get("autostart_initialized"):
            # First run: default to starting at login so KeyStow is always there.
            try:
                autostart.set_enabled(True)
                settings.set("autostart_initialized", True)
            except OSError:
                # Registration or marker persistence may fail independently.
                # Keep UI startup usable; an absent marker remains retryable.
                pass
        self.autostart_action.setChecked(autostart.is_enabled())
        self.autostart_action.triggered.connect(self._toggle_autostart)
        menu.addAction(self.autostart_action)
        menu.addSeparator()
        quit_action = QAction("Quit KeyStow", self)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        # Worker threads (hotkey listener, transcription) must not touch
        # widgets directly - these queued signals marshal to the GUI thread.
        self._sig_state.connect(self._do_set_state)
        self._sig_transcript.connect(self._do_show_transcript)
        self._sig_stats.connect(self._do_refresh_stats)
        self._sig_hotkey.connect(self._do_set_hotkey_label)
        self._sig_model.connect(self._do_set_model_selection)

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
        """Marshal hotkey-listener updates onto the Qt thread."""
        self._sig_hotkey.emit(name)

    def _do_set_hotkey_label(self, name: str):
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
        for action in self._hotkey_group.actions():
            action.setChecked(action.text() == hotkey_label(name))
        for action in self._hotkey_group.actions():
            action.blockSignals(False)

    def set_model_selection(self, name: str):
        self._sig_model.emit(name)

    def _do_set_model_selection(self, name: str):
        self.model_box.blockSignals(True)
        self.model_box.setCurrentText(MODEL_LABELS.get(name, name))
        self.model_box.blockSignals(False)

    def _update_hint(self):
        verb = "press" if self._toggle else "hold"
        self.hint.setText(f"or {verb} [{self._hotkey_label}] anywhere")

    # --- tray & window plumbing ---

    def _save_noise_preference(self, checked):
        try:
            settings.set("noise_suppression", bool(checked))
            self._noise_saved = bool(checked)
        except OSError:
            self.noise_box.blockSignals(True)
            self.noise_box.setChecked(self._noise_saved)
            self.noise_box.blockSignals(False)
            self.storage_warning.setText(
                "Could not save the noise setting. Your previous setting is still selected. "
                "Check your .keystow path, then restart KeyStow."
            )
            self.storage_warning.show()

    def _toggle_autostart(self, checked):
        try:
            autostart.set_enabled(checked)
        except OSError:
            self.autostart_action.setChecked(not checked)
            self.set_state("Could not change start at login. Your previous choice is still selected.")

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

    def _model_changed(self, text):
        if self._on_model_change:
            self._on_model_change(_MODEL_NAME.get(text, text))

    def set_state(self, text: str, recording: bool = False, busy: bool = False):
        self._sig_state.emit(text, recording, busy)

    def _do_set_state(self, text: str, recording: bool, busy: bool):
        self.status.setText(text)
        if recording:
            self.record_btn.setText("Stop and type" if self._toggle else "Release to type")
        else:
            self.record_btn.setText("Click to talk" if self._toggle else "Hold to talk")
        self.record_btn.setEnabled(not busy)
        editable = not (busy or recording)
        self.model_box.setEnabled(editable)
        self.hotkey_box.setEnabled(editable)
        self.noise_box.setEnabled(editable)
        self._hotkey_group.setEnabled(editable)
        self._custom_key_action.setEnabled(editable)
        self.progress.setVisible(busy)
        self.tray.setIcon(self._icon_listening if recording else self._icon_idle)
        self.tray.setToolTip(f"KeyStow - {'listening...' if recording else text}")

    def show_transcript(self, text: str):
        self._sig_transcript.emit(text)

    def _do_show_transcript(self, text: str):
        self.transcript.setText(text)

    def refresh_stats(self):
        self._sig_stats.emit()

    def _do_refresh_stats(self):
        if paths.startup_storage_error() is not None:
            self.stats_label.setText("Word counts unavailable.")
            return
        self.stats_label.setText(
            f"Words dictated - today: {stats.today():,}  |  all time: {stats.total():,}"
        )


def run_app(controller_factory):
    """Start the Qt app. *controller_factory(window)* wires the voice logic."""
    import sys

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # keep running in the tray
    window = MainWindow()
    # Keep the controller (and its worker/listener references) alive for the
    # entire Qt event loop. Construction alone does not start dictation.
    controller = controller_factory(window)
    controller.start()
    shutdown_timer = QTimer(window)
    shutdown_timer.setInterval(100)

    def finish_quit_if_idle():
        if controller.can_exit():
            shutdown_timer.stop()
            app.quit()

    def request_quit():
        controller.shutdown()
        window.set_state("Finishing the current task before quitting...", busy=True)
        shutdown_timer.start()
        finish_quit_if_idle()

    window.quit_requested.connect(request_quit)
    shutdown_timer.timeout.connect(finish_quit_if_idle)
    app.aboutToQuit.connect(controller.wait_for_shutdown)
    window.show()  # first launch shows the window; after that it hides to the tray
    sys.exit(app.exec())
