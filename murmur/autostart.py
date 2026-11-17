"""Start at login: per-user Run key on Windows, LaunchAgent on macOS."""

import os
import sys

_APP_NAME = "Murmur"

if sys.platform == "darwin":
    _PLIST = os.path.expanduser("~/Library/LaunchAgents/com.murmur.app.plist")
    _PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.murmur.app</string>
  <key>ProgramArguments</key><array><string>{exe}</string></array>
  <key>RunAtLoad</key><true/>
</dict>
</plist>
"""

    def is_enabled() -> bool:
        return os.path.exists(_PLIST)

    def set_enabled(enabled: bool) -> None:
        if enabled:
            os.makedirs(os.path.dirname(_PLIST), exist_ok=True)
            with open(_PLIST, "w", encoding="utf-8") as f:
                f.write(_PLIST_TEMPLATE.format(exe=sys.executable))
        else:
            try:
                os.remove(_PLIST)
            except FileNotFoundError:
                pass
elif sys.platform == "win32":
    _RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def _command() -> str:
        # PyInstaller onefile: sys.executable is the Murmur.exe path.
        return f'"{sys.executable}"'

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
