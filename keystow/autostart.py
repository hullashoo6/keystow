"""Start at login: per-user Run key on Windows, LaunchAgent on macOS."""

import os
import plistlib
import tempfile
from xml.parsers.expat import ExpatError
import sys

_APP_NAME = "KeyStow"

# The sign-in entry passes this, so the app can start minimised instead of
# opening its window over whatever the user is doing after signing in.
STARTUP_ARGUMENT = "--startup"


def available() -> bool:
    """Only the installed app may register itself to start at login.

    From a source checkout sys.executable is the Python interpreter, so a login
    entry would open a bare interpreter at every sign-in instead of KeyStow.
    """
    return bool(getattr(sys, "frozen", False)) and sys.platform in ("darwin", "win32")


def enable_by_default() -> bool:
    """True where the app itself switches start at login on at its first run.

    Start at login is on by default. On Windows the installer offers it as a
    ticked option, so the app leaves that choice alone. A Mac is installed by
    dragging the app, with no installer to ask, so the installed app does it.
    """
    return available() and sys.platform == "darwin"


if sys.platform == "darwin":
    _PLIST = os.path.expanduser("~/Library/LaunchAgents/com.keystow.app.plist")
    def is_enabled() -> bool:
        try:
            with open(_PLIST, 'rb') as f:
                data = plistlib.load(f)
            arguments = data.get('ProgramArguments') if isinstance(data, dict) else None
            return (isinstance(data, dict) and data.get('Label') == 'com.keystow.app'
                    and data.get('RunAtLoad') is True
                    and isinstance(arguments, list) and bool(arguments)
                    and all(isinstance(arg, str) and arg for arg in arguments))
        except (OSError, ValueError, ExpatError):
            return False

    def set_enabled(enabled: bool) -> None:
        if enabled:
            directory = os.path.dirname(_PLIST)
            os.makedirs(directory, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='wb', dir=directory,
                                                 prefix='.keystow-login-', delete=False) as f:
                    temporary = f.name
                    plistlib.dump({'Label': 'com.keystow.app',
                                   'ProgramArguments': [sys.executable, STARTUP_ARGUMENT],
                                   'RunAtLoad': True}, f)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temporary, _PLIST)
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
        else:
            try:
                os.remove(_PLIST)
            except FileNotFoundError:
                pass

    def _is_current() -> bool:
        try:
            with open(_PLIST, 'rb') as f:
                data = plistlib.load(f)
            return data.get('ProgramArguments') == [sys.executable, STARTUP_ARGUMENT]
        except (OSError, ValueError, ExpatError, AttributeError):
            return True  # unreadable: leave it alone rather than guess
elif sys.platform == "win32":
    _RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def _command() -> str:
        # In the installed app sys.executable is the KeyStow.exe path.
        return f'"{sys.executable}" {STARTUP_ARGUMENT}'

    def _is_current() -> bool:
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
                value, _ = winreg.QueryValueEx(key, _APP_NAME)
            return value == _command()
        except (OSError, ImportError):
            return True  # unreadable: leave it alone rather than guess

    def is_enabled() -> bool:
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
                value, _ = winreg.QueryValueEx(key, _APP_NAME)
            return bool(value)
        except (OSError, FileNotFoundError, ImportError):
            return False

    def set_enabled(enabled: bool) -> None:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)
                except FileNotFoundError:
                    pass


else:

    def is_enabled() -> bool:
        return False

    def set_enabled(enabled: bool) -> None:
        raise OSError("start-at-login is not supported on this platform")

    def _is_current() -> bool:
        return True


def refresh() -> None:
    """Bring an existing sign-in entry up to date; never create one.

    Entries written by earlier versions lack the startup argument, and an entry
    can point at a folder the app has since moved from. Only the installed app
    rewrites it, and only when start at login is already on.
    """
    if available() and is_enabled() and not _is_current():
        set_enabled(True)
