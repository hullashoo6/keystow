"""KeyStow UI: lives in the system tray, with a small window on demand (PySide6)."""

import sys

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QScrollArea,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from . import __version__, autostart, config, paths, settings, stats, tray_icons

# Palette and type from the website (docs/assets/site.css). Light only, as the
# site is: it declares color-scheme: light.
PAPER = "#ffffff"
MIST = "#f5f5f7"
INK = "#0d0d12"
INK_HOVER = "#2b2b34"
SLATE = "#5d5f69"     # 6.3:1 on white, 5.8:1 on mist
LINE = "#e4e4ea"
VIOLET = "#6f6cf2"    # accents, focus rings, outlines (about 4.1:1 on white: not for small text)
VIOLET_INK = "#5b57e0"  # violet that carries text or sits under white text (about 5.4:1)
ACCENT = VIOLET       # kept for the fallback icon
FONT = '"Instrument Sans", "Segoe UI", "Helvetica Neue", Arial, sans-serif'

if sys.platform == "darwin":
    # MacBook keyboards have no Right Ctrl; the first entry is the Mac default.
    HOTKEY_PRESETS = [
        ("Right Option", "alt_r"),
        ("Right Command", "cmd_r"),
        ("Right Shift", "shift_r"),
        ("Right Control", "ctrl_r"),
    ]
else:
    # Caps Lock is no longer offered: every dictation toggled the Caps state.
    # A key chosen earlier keeps working and shows under its own name.
    HOTKEY_PRESETS = [
        ("Right Ctrl", "ctrl_r"),
        ("Right Shift", "shift_r"),
        ("Right Alt", "alt_r"),
    ]
CUSTOM_KEY = "__custom__"

MODEL_CHOICES = ["base", "tiny", "small", "medium", "turbo", "large-v3"]
MODEL_LABELS = {
    "base": "Base (built in)",
    "tiny": "Tiny (fastest)",
    "small": "Small",
    "medium": "Medium",
    "turbo": "Turbo (accurate, slower)",
    "large-v3": "Large (slowest)",
}
_MODEL_NAME = {v: k for k, v in MODEL_LABELS.items()}
MODE_CHOICES = [("Hold the key while you speak", "hold"), ("Press to start, press to stop", "toggle")]


def hotkey_label(name: str) -> str:
    for label, key_name in HOTKEY_PRESETS:
        if key_name == name:
            return label
    return name.replace("_", " ").title()


STYLESHEET = f"""
QMainWindow, QWidget#page {{
    background-color: {PAPER};
}}
QWidget {{
    color: {INK};
    font-family: {FONT};
    font-size: 14px;
}}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 22px; font-weight: 600; }}
QLabel#version {{ color: {SLATE}; font-size: 12px; }}
QLabel#badge {{
    background-color: {PAPER};
    border: 1px solid {LINE};
    border-radius: 11px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 600;
}}
QLabel#badge[state="listening"] {{ color: #ffffff; background-color: {VIOLET_INK}; border-color: {VIOLET_INK}; }}
QLabel#badge[state="working"] {{ color: {VIOLET_INK}; border-color: {VIOLET}; }}
QLabel#badge[state="attention"] {{ color: #8a1c1f; background-color: #fdecec; border-color: #f3c1c2; }}
QLabel#badge[state="done"] {{ color: #1f6b3a; background-color: #e9f6ee; border-color: #bfe3cc; }}
QLabel#status {{ color: {SLATE}; font-size: 14px; }}
QLabel#hint, QLabel#stats, QLabel#small {{ color: {SLATE}; font-size: 12px; }}
QLabel#sectionLabel {{ color: {SLATE}; font-size: 12px; font-weight: 600; }}
QLabel#transcript {{ font-size: 16px; }}
QFrame#panel {{
    background-color: {MIST};
    border: 1px solid {LINE};
    border-radius: 16px;
}}
QFrame#welcome {{
    background-color: {PAPER};
    border: 1px solid {VIOLET};
    border-radius: 16px;
}}
QPushButton {{
    font-family: {FONT};
}}
QPushButton#record {{
    background-color: {INK};
    color: #ffffff;
    border: none;
    border-radius: 28px;
    font-size: 16px;
    font-weight: 600;
    padding: 0 28px;
}}
QPushButton#record:hover {{ background-color: {INK_HOVER}; }}
QPushButton#record[listening="true"] {{ background-color: {VIOLET_INK}; }}
QPushButton#record:focus {{ border: 3px solid {VIOLET}; }}
QPushButton#record:disabled {{ background-color: {LINE}; color: {SLATE}; }}
QPushButton#quiet {{
    background-color: {PAPER};
    color: {INK};
    border: 1px solid {LINE};
    border-radius: 16px;
    padding: 6px 16px;
    font-weight: 600;
}}
QPushButton#quiet:hover {{ border-color: {SLATE}; }}
QPushButton#quiet:focus {{ border: 2px solid {VIOLET}; }}
QPushButton#quiet:disabled {{ color: #a3a5ad; border-color: {LINE}; }}
QComboBox {{
    background-color: {PAPER};
    border: 1px solid {LINE};
    border-radius: 10px;
    padding: 6px 10px;
    min-height: 20px;
}}
QComboBox:hover {{ border-color: {SLATE}; }}
QComboBox:focus {{ border: 2px solid {VIOLET}; }}
QComboBox:disabled {{ color: #a3a5ad; background-color: {MIST}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: {PAPER};
    border: 1px solid {LINE};
    selection-background-color: {MIST};
    selection-color: {INK};
    outline: none;
}}
QCheckBox {{ background: transparent; spacing: 8px; }}
QCheckBox:focus {{ color: {VIOLET_INK}; }}
QMenu {{
    background-color: {PAPER};
    border: 1px solid {LINE};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{ padding: 6px 28px 6px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background-color: {MIST}; }}
QMenu::item:disabled {{ color: {SLATE}; }}
QToolTip {{ background-color: {INK}; color: #ffffff; border: none; padding: 4px 8px; }}
QProgressBar {{ background-color: {LINE}; border: none; border-radius: 2px; max-height: 4px; }}
QProgressBar::chunk {{ background-color: {VIOLET}; border-radius: 2px; }}
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
    copy_requested = Signal()
    mode_selected = Signal(str)  # "hold" or "toggle"
    _sig_state = Signal(str, bool, bool)
    _sig_mode = Signal(bool)
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
        # Not always-on-top: KeyStow should never sit over, or take focus
        # from, the app the user is dictating into.

        self._toggle = settings.toggle_mode()
        self._hotkey_name = settings.get("hotkey", config.HOTKEY)
        self._hotkey_label = hotkey_label(self._hotkey_name)
        self._recording = False

        page = QWidget()
        page.setObjectName("page")
        card = QWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header: the website's mark and name.
        header = QHBoxLayout()
        header.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(QPixmap.fromImage(tray_icons.render(64, "app")).scaled(
            30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setAccessibleName("KeyStow logo")
        header.addWidget(logo)
        title = QLabel("KeyStow")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        version = QLabel(f"v{__version__}")
        version.setObjectName("version")
        header.addWidget(version)
        layout.addLayout(header)

        # Status: a badge naming the state in words, and what to do next.
        status_panel = QFrame()
        status_panel.setObjectName("panel")
        status_box = QVBoxLayout(status_panel)
        status_box.setContentsMargins(16, 12, 16, 14)
        status_box.setSpacing(6)
        badge_row = QHBoxLayout()
        self.badge = QLabel("Loading")
        self.badge.setObjectName("badge")
        self.badge.setProperty("state", "working")
        self.badge.setAccessibleName("KeyStow state")
        badge_row.addWidget(self.badge)
        badge_row.addStretch()
        status_box.addLayout(badge_row)
        self.status = QLabel("Loading the built-in speech model...")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Status")
        status_box.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName("Working")
        status_box.addWidget(self.progress)
        self.storage_warning = QLabel()
        self.storage_warning.setObjectName("small")
        self.storage_warning.setWordWrap(True)
        if paths.startup_storage_error() is not None:
            self.storage_warning.setText(
                "Local storage could not be opened at startup. Settings and word counts "
                "may not be saved. Check your .keystow folder, then restart KeyStow."
            )
        self.storage_warning.setVisible(bool(self.storage_warning.text()))
        status_box.addWidget(self.storage_warning)
        if sys.platform == "darwin":
            # macOS gives no global keys, paste or microphone audio to an app
            # until the user allows it, and shows no error when it is blocked.
            mac_note = QLabel(
                "KeyStow needs two permissions on a Mac: Microphone, and Accessibility "
                "(for the shortcut and for pasting). Allow both under System Settings > "
                "Privacy & Security, then quit and reopen KeyStow."
            )
            mac_note.setObjectName("small")
            mac_note.setWordWrap(True)
            status_box.addWidget(mac_note)
        layout.addWidget(status_panel)

        # The talk button. Hold it, or click once to start and again to stop
        # (mode below); Space works the same way from the keyboard.
        self.record_btn = QPushButton()
        self.record_btn.setObjectName("record")
        self.record_btn.setMinimumHeight(56)
        self.record_btn.setEnabled(False)
        self.record_btn.setAccessibleName("Talk")
        self.record_btn.pressed.connect(self._record_pressed)
        self.record_btn.released.connect(self._record_released)
        self.record_btn.clicked.connect(self._record_clicked)
        layout.addWidget(self.record_btn)
        self.hint = QLabel()
        self.hint.setObjectName("hint")
        self.hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.hint)

        # First run: one successful dictation without learning any settings.
        self.welcome = QFrame()
        self.welcome.setObjectName("welcome")
        welcome_box = QVBoxLayout(self.welcome)
        welcome_box.setContentsMargins(16, 12, 16, 12)
        welcome_box.setSpacing(6)
        welcome_title = QLabel("Try it now")
        welcome_title.setObjectName("sectionLabel")
        welcome_box.addWidget(welcome_title)
        self.welcome_text = QLabel()
        self.welcome_text.setWordWrap(True)
        welcome_box.addWidget(self.welcome_text)
        got_it = QPushButton("Got it")
        got_it.setObjectName("quiet")
        got_it.setAccessibleName("Hide the getting-started tip")
        got_it.clicked.connect(lambda _checked=False: self._dismiss_welcome())
        got_row = QHBoxLayout()
        got_row.addStretch()
        got_row.addWidget(got_it)
        welcome_box.addLayout(got_row)
        self.welcome.setVisible(not settings.get("welcome_done"))
        layout.addWidget(self.welcome)

        # Latest result, kept in memory only, with Copy for recovery.
        result_panel = QFrame()
        result_panel.setObjectName("panel")
        result_box = QVBoxLayout(result_panel)
        result_box.setContentsMargins(16, 12, 16, 12)
        result_box.setSpacing(6)
        result_label = QLabel("Latest dictation")
        result_label.setObjectName("sectionLabel")
        result_box.addWidget(result_label)
        self.transcript = QLabel("Your latest dictation appears here. KeyStow pastes it where your cursor is.")
        self.transcript.setObjectName("transcript")
        self.transcript.setWordWrap(True)
        self.transcript.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.transcript.setAccessibleName("Latest dictation")
        result_box.addWidget(self.transcript)
        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setObjectName("quiet")
        self.copy_btn.setEnabled(False)
        self.copy_btn.setAccessibleName("Copy latest dictation")
        self.copy_btn.setToolTip("Put your latest dictation on the clipboard to paste it yourself.")
        self.copy_btn.clicked.connect(lambda _checked=False: self.copy_requested.emit())
        copy_row = QHBoxLayout()
        copy_row.addStretch()
        copy_row.addWidget(self.copy_btn)
        result_box.addLayout(copy_row)
        layout.addWidget(result_panel)

        # Settings.
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        self.hotkey_box = QComboBox()
        for label, key_name in HOTKEY_PRESETS:
            self.hotkey_box.addItem(label, key_name)
        if self.hotkey_box.findData(self._hotkey_name) < 0:
            # A key chosen earlier (including one no longer offered) stays shown.
            self.hotkey_box.addItem(self._hotkey_label, self._hotkey_name)
        self.hotkey_box.addItem("Choose another key...", CUSTOM_KEY)
        self.hotkey_box.setCurrentIndex(max(0, self.hotkey_box.findData(self._hotkey_name)))
        self.hotkey_box.setAccessibleName("Shortcut key")
        self.hotkey_box.currentIndexChanged.connect(self._hotkey_combo_changed)
        self.mode_box = QComboBox()
        for label, mode in MODE_CHOICES:
            self.mode_box.addItem(label, mode)
        self.mode_box.setCurrentIndex(self.mode_box.findData("toggle" if self._toggle else "hold"))
        self.mode_box.setAccessibleName("How the shortcut works")
        self.mode_box.setToolTip("Press to start and stop suits anyone who finds holding a key hard.")
        self.mode_box.currentIndexChanged.connect(self._mode_combo_changed)
        self.model_box = QComboBox()
        self.model_box.addItems([MODEL_LABELS.get(m, m) for m in MODEL_CHOICES])
        self.model_box.setCurrentText(MODEL_LABELS.get(config.MODEL_SIZE, config.MODEL_SIZE))
        self.model_box.setAccessibleName("Speech model")
        self.model_box.setToolTip("Base is built in and works offline. Larger models download once, "
                                  "after you agree, and are slower on most computers.")
        for row, (text, widget) in enumerate((("Shortcut", self.hotkey_box), ("Mode", self.mode_box),
                                              ("Model", self.model_box))):
            label = QLabel(text)
            label.setObjectName("sectionLabel")
            label.setBuddy(widget)
            grid.addWidget(label, row, 0)
            grid.addWidget(widget, row, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        self.noise_box = QCheckBox("Reduce background noise")
        self._noise_saved = settings.get("noise_suppression", True)
        self.noise_box.setChecked(self._noise_saved)
        self.noise_box.setToolTip("Cleans fan and street noise out of the recording before it is "
                                  "transcribed, on this computer.")
        self.noise_box.toggled.connect(self._save_noise_preference)
        layout.addWidget(self.noise_box)
        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        self.stats_label.setObjectName("stats")
        self.stats_label.setAlignment(Qt.AlignCenter)
        self._do_refresh_stats()
        layout.addWidget(self.stats_label)

        # Centred and capped in width, so it stays tidy when maximised.
        outer = QVBoxLayout(page)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.addStretch()
        center_row = QHBoxLayout()
        center_row.addStretch()
        card.setMaximumWidth(560)
        card.setMinimumWidth(340)
        center_row.addWidget(card, 1)
        center_row.addStretch()
        outer.addLayout(center_row)
        outer.addStretch()
        # Scrolls rather than clips when the window is small or text is large.
        scroller = QScrollArea()
        scroller.setObjectName("page")
        scroller.setFrameShape(QFrame.NoFrame)
        scroller.setWidgetResizable(True)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroller.setWidget(page)
        self.setCentralWidget(scroller)
        self.setMinimumSize(360, 420)
        self._card = card
        # Start with focus on the page, not the talk button: the focus ring
        # then appears only when someone moves through the window by keyboard.
        page.setFocusPolicy(Qt.ClickFocus)
        page.setFocus()
        self._apply_mode()

        self.model_box.currentTextChanged.connect(self._model_changed)
        self._on_model_change = None

        # --- system tray ---
        self._icon_idle = tray_icons.icon("idle", fallback=lambda: _tray_icon("#8a8aa0"))
        self._icon_listening = tray_icons.icon("listening", fallback=lambda: _tray_icon(ACCENT))
        self.tray = QSystemTrayIcon(self._icon_idle, self)
        self.tray.setToolTip("KeyStow")
        menu = QMenu()
        version_action = QAction(f"KeyStow {__version__}", self)
        version_action.setEnabled(False)
        menu.addAction(version_action)
        open_action = QAction("Open KeyStow", self)
        open_action.triggered.connect(self.show_and_raise)
        menu.addAction(open_action)
        self.copy_action = QAction("Copy last dictation", self)
        self.copy_action.setEnabled(False)
        self.copy_action.triggered.connect(lambda _checked=False: self.copy_requested.emit())
        menu.addAction(self.copy_action)

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
        # Start at login is on by default and can be switched off here. The
        # Windows installer sets it (a ticked option). The installed Mac app
        # sets it once, at its first run; the saved marker means that turning
        # it off afterwards stays off.
        if autostart.enable_by_default() and not settings.get("autostart_initialized"):
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
        self._sig_mode.connect(self._do_set_mode)

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
        self.hotkey_box.blockSignals(True)
        idx = self.hotkey_box.findData(name)
        if idx < 0:
            # A key captured with "Choose another key..." gets its own entry.
            idx = self.hotkey_box.findData(CUSTOM_KEY)
            self.hotkey_box.insertItem(idx, hotkey_label(name), name)
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
        key = self._hotkey_label
        if self._toggle:
            self.hint.setText(f"or press {key} anywhere to start, and again to stop")
            self.welcome_text.setText(
                f"1. Click into any text box, such as Notepad or an email.\n"
                f"2. Press {key} once and say a sentence.\n"
                f"3. Press {key} again. Your words appear where the cursor is.")
        else:
            self.hint.setText(f"or hold {key} anywhere while you speak")
            self.welcome_text.setText(
                f"1. Click into any text box, such as Notepad or an email.\n"
                f"2. Hold {key} and say a sentence.\n"
                f"3. Let go. Your words appear where the cursor is.")

    # --- talk button and mode ---

    def _apply_mode(self):
        self.record_btn.setText(self._button_text())
        self._update_hint()

    def _button_text(self) -> str:
        if self._recording:
            return "Stop" if self._toggle else "Release to finish"
        return "Click to talk" if self._toggle else "Hold to talk"

    def _record_pressed(self):
        if not self._toggle:
            self.record_pressed.emit()

    def _record_released(self):
        if not self._toggle:
            self.record_released.emit()

    def _record_clicked(self, _checked=False):
        if self._toggle:
            self.record_toggled.emit()

    def _mode_combo_changed(self, index):
        mode = self.mode_box.itemData(index)
        if mode in ("hold", "toggle"):
            self.mode_selected.emit(mode)

    def set_mode(self, toggle: bool):
        """The controller confirmed (and saved) a mode; may come from any thread."""
        self._sig_mode.emit(bool(toggle))

    def _do_set_mode(self, toggle: bool):
        self._toggle = toggle
        self.mode_box.blockSignals(True)
        self.mode_box.setCurrentIndex(self.mode_box.findData("toggle" if toggle else "hold"))
        self.mode_box.blockSignals(False)
        self._apply_mode()

    def _dismiss_welcome(self):
        self.welcome.hide()
        try:
            settings.set("welcome_done", True)
        except OSError:
            pass  # shown again next start; harmless

    @staticmethod
    def _state_kind(text: str, recording: bool, busy: bool):
        """A word and a style for the badge, so state never relies on colour alone."""
        if recording:
            return "Listening", "listening"
        if busy:
            return ("Loading" if "model" in text.lower() else "Working"), "working"
        lowered = text.lower()
        if text.startswith("Pasted"):
            return "Pasted", "done"
        if text.startswith("Copied"):
            return "Copied", "done"
        if any(w in lowered for w in ("accessibility", "allowed to use it", "blocking the shortcut",
                                      "keyboard layout")):
            return "Needs permission" if "layout" not in lowered else "Shortcut off", "attention"
        if "could not confirm" in lowered:
            return "Check the text", "attention"
        if any(w in lowered for w in ("did not paste", "click copy", "nothing was pasted",
                                      "blocks keystow", "blocked the paste")):
            return "Not pasted", "attention"
        if any(w in lowered for w in ("failed", "couldn't", "could not", "error", "no sound", "missing")):
            return "Problem", "attention"
        if lowered.startswith("too short") or lowered.startswith("didn't catch"):
            return "Nothing heard", "attention"
        return "Ready", ""

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
        if checked and not autostart.available():
            # Run from source, the login entry would launch bare Python.
            self.autostart_action.setChecked(False)
            self.set_state("Start at login works in the installed app, not when run from source.")
            return
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
        # Closing means quit, not a hidden microphone/listener in the tray.
        # Keep Qt alive only while in-flight workers finish safely.
        event.accept()
        self.quit_requested.emit()

    def _model_changed(self, text):
        if self._on_model_change:
            self._on_model_change(_MODEL_NAME.get(text, text))

    def set_state(self, text: str, recording: bool = False, busy: bool = False):
        self._sig_state.emit(text, recording, busy)

    def _fit(self):
        """Give the card the height its wrapped text needs at the current width.

        Qt's main-window layout does not pass height-for-width through, so
        two-line messages were squeezed into one line at narrow widths.
        """
        card = getattr(self, "_card", None)
        if card is not None and card.layout() is not None:
            card.setMinimumHeight(card.layout().heightForWidth(max(card.width(), 1)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._fit)

    @staticmethod
    def _restyle(widget, name: str, value: str):
        """Change a style property and make Qt apply the matching rules."""
        if widget.property(name) != value:
            widget.setProperty(name, value)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _announce(self, message: str):
        """Tell screen readers about the new state without moving focus."""
        self.status.setAccessibleDescription(message)
        try:
            from PySide6.QtGui import QAccessible, QAccessibleAnnouncementEvent

            QAccessible.updateAccessibility(QAccessibleAnnouncementEvent(self.status, message))
        except Exception:  # noqa: BLE001 - older Qt: the description change still helps
            pass

    def _do_set_state(self, text: str, recording: bool, busy: bool):
        self.status.setText(text)
        word, kind = self._state_kind(text, recording, busy)
        self.badge.setText(word)
        self._restyle(self.badge, "state", kind)
        self._recording = recording
        self._restyle(self.record_btn, "listening", "true" if recording else "false")
        self.record_btn.setText(self._button_text())
        self.record_btn.setEnabled(not busy)
        self._announce(f"{word}. {text}")
        if word == "Pasted" and not self.welcome.isHidden():
            self._dismiss_welcome()  # the first dictation worked; the tip has done its job
        editable = not (busy or recording)
        self.model_box.setEnabled(editable)
        self.hotkey_box.setEnabled(editable)
        self.mode_box.setEnabled(editable)
        self.noise_box.setEnabled(editable)
        self._hotkey_group.setEnabled(editable)
        self._custom_key_action.setEnabled(editable)
        self.progress.setVisible(busy)
        self.tray.setIcon(self._icon_listening if recording else self._icon_idle)
        self.tray.setToolTip(f"KeyStow - {'listening...' if recording else text}")
        QTimer.singleShot(0, self._fit)

    # Approximate download sizes of the optional faster-whisper models.
    MODEL_DOWNLOAD_SIZES = {"tiny": "75 MB", "small": "480 MB", "medium": "1.5 GB",
                            "large-v3": "3 GB", "turbo": "1.6 GB"}

    def confirm_download(self, model_size: str) -> bool:
        """Ask before KeyStow downloads a model. Runs on the Qt thread."""
        size = self.MODEL_DOWNLOAD_SIZES.get(model_size, "a large file")
        answer = QMessageBox.question(
            self, "Download a speech model?",
            f"The '{model_size}' model is not on this computer yet. KeyStow will download it "
            f"once from Hugging Face (about {size}).\n\nYour voice is still processed only on "
            "this computer; the download is just the model file. Download now?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return answer == QMessageBox.Yes

    def show_transcript(self, text: str):
        self._sig_transcript.emit(text)

    def _do_show_transcript(self, text: str):
        self.transcript.setText(text)
        self.copy_btn.setEnabled(bool(text))
        self.copy_action.setEnabled(bool(text))
        QTimer.singleShot(0, self._fit)

    def refresh_stats(self):
        self._sig_stats.emit()

    def _do_refresh_stats(self):
        if paths.startup_storage_error() is not None:
            self.stats_label.setText("Word counts unavailable.")
            return
        self.stats_label.setText(f"{stats.today():,} words today  ·  {stats.total():,} all time")


def _load_brand_font() -> bool:
    """Load Instrument Sans (SIL OFL 1.1, shipped with its licence in fonts/).

    If it cannot be loaded, the stylesheet falls back to Segoe UI / the
    system font, as the website does.
    """
    import os

    from PySide6.QtGui import QFontDatabase

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "InstrumentSans-Variable.ttf")
    return os.path.isfile(path) and QFontDatabase.addApplicationFont(path) >= 0


def run_app(controller_factory):
    """Start the Qt app. *controller_factory(window)* wires the voice logic."""
    import sys

    app = QApplication(sys.argv)
    _load_brand_font()
    app.setQuitOnLastWindowClosed(False)  # request_quit owns safe worker cleanup
    from .single_instance import InstanceGuard
    guard = InstanceGuard()
    try:
        if not guard.acquire():
            guard.activate_existing()
            return 0  # never construct a second recorder or global key listener
        window = MainWindow()
        guard.listen(window.show_and_raise)
    except OSError as exc:
        guard.release()
        QMessageBox.critical(None, "KeyStow could not start", str(exc))
        return 1
    # Keep ownership alive for the complete event loop and worker shutdown.
    app._keystow_instance_guard = guard
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

    quitting = False

    def request_quit():
        nonlocal quitting
        if quitting:
            return
        quitting = True
        controller.shutdown()
        window.set_state("Finishing the current task before quitting...", busy=True)
        shutdown_timer.start()
        finish_quit_if_idle()

    window.quit_requested.connect(request_quit)
    shutdown_timer.timeout.connect(finish_quit_if_idle)
    try:
        autostart.refresh()
    except OSError:
        pass  # the sign-in entry stays as it was; the tray toggle still works
    # Started by the sign-in entry: stay out of the way, minimised. Opened by
    # the user: show the window.
    if autostart.STARTUP_ARGUMENT in sys.argv[1:]:
        window.showMinimized()
    else:
        window.show()
    try:
        result = app.exec()
    finally:
        controller.wait_for_shutdown()
        guard.release()
    sys.exit(result)
