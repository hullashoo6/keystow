"""Real Windows clipboard checks, run in a private window station.

A window station has its own clipboard, so nothing here can read or change
the clipboard of the person using the computer. Run as a separate process
(test_win_delivery.py does that); prints one JSON report and exits.
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import threading
import time

u = ctypes.WinDLL("user32", use_last_error=True)
u.CreateWindowStationW.restype = wt.HANDLE
u.CreateWindowStationW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p]
u.SetProcessWindowStation.argtypes = [wt.HANDLE]
u.CreateDesktopW.restype = wt.HANDLE
u.CreateDesktopW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, ctypes.c_void_p, wt.DWORD, wt.DWORD, ctypes.c_void_p]
u.SetThreadDesktop.argtypes = [wt.HANDLE]

u.GetProcessWindowStation.restype = wt.HANDLE
u.GetUserObjectInformationW.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD,
                                         ctypes.POINTER(wt.DWORD)]


def _station_name():
    name = ctypes.create_unicode_buffer(256)
    u.GetUserObjectInformationW(u.GetProcessWindowStation(), 2, name, 512, None)  # UOI_NAME
    return name.value


# Must happen before this process makes any window or clipboard call.
isolated = False
station = u.CreateWindowStationW(f"KeyStowTest{os.getpid()}", 0, 0x37F, None)
if station and u.SetProcessWindowStation(station):
    desktop = u.CreateDesktopW("Default", None, None, 0, 0x10000000, None)  # GENERIC_ALL
    isolated = bool(desktop and u.SetThreadDesktop(desktop)
                    and _station_name() == f"KeyStowTest{os.getpid()}")
# Never touch a person's clipboard: without a private station, run only on a
# throwaway CI machine (GitHub Actions), whose clipboard belongs to nobody.
if not isolated and os.environ.get("GITHUB_ACTIONS") != "true":
    print(json.dumps({"skipped": f"no private clipboard here (station {_station_name()!r})"}))
    sys.exit(0)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from keystow import win_delivery as wd  # noqa: E402

W = wd.W
W.GetClipboardData.restype = wt.HANDLE

# A stand-in "other app": its own window on this (main) thread.
APP = W.CreateWindowExW(0, "STATIC", "pretend app", 0, 0, 0, 0, 0, wd.HWND_MESSAGE, None, None, None)
HTML = W.RegisterClipboardFormatW("HTML Format")
PRIVATE = W.RegisterClipboardFormatW("KeyStowTest Private Bytes")


def app_write(formats):
    assert wd._open_clipboard(APP)
    try:
        W.EmptyClipboard()
        for fmt, data in formats.items():
            assert wd._set_bytes(fmt, data)
    finally:
        W.CloseClipboard()


def text(s):
    return s.encode("utf-16-le") + b"\0\0"


def app_read(fmt=wd.CF_UNICODETEXT):
    assert wd._open_clipboard(APP)
    try:
        handle = W.GetClipboardData(fmt)
        if not handle:
            return None
        pointer = W.GlobalLock(handle)
        try:
            raw = ctypes.string_at(pointer, W.GlobalSize(handle))
        finally:
            W.GlobalUnlock(handle)
    finally:
        W.CloseClipboard()
    if fmt == wd.CF_UNICODETEXT:
        return raw.decode("utf-16-le").split("\0", 1)[0]
    return raw


def app_formats():
    assert wd._open_clipboard(APP)
    try:
        found, fmt = [], 0
        while True:
            fmt = W.EnumClipboardFormats(fmt)
            if not fmt:
                return found
            found.append(fmt)
    finally:
        W.CloseClipboard()


report = {}
owner = wd._Owner()
me = os.getpid()


def offer(s):
    status = owner.call(lambda: owner.offer(s, me))
    owner.mark_sent()
    return status


# 1. Confirmed read, then the previous text comes back.
app_write({wd.CF_UNICODETEXT: text("synthetic user clipboard")})
report["offer_ok"] = offer("Synthetic dictation one.")
report["read_gets_dictation"] = app_read() == "Synthetic dictation one."
report["confirmed_by_read"] = owner.wait_confirmed(1)
report["restored"] = owner.call(owner.restore_if_owned)
report["previous_back"] = app_read() == "synthetic user clipboard"

# 2. Nobody reads in time: no restore, and a late read still gets the dictation.
offer("Synthetic dictation two.")
report["unread_not_confirmed"] = not owner.wait_confirmed(0.3)
time.sleep(0.5)
report["late_read_gets_dictation_not_previous"] = app_read() == "Synthetic dictation two."

# 3. The next dictation after an unconfirmed one restores the user's text, not dictation two.
offer("Synthetic dictation three.")
app_read()
owner.wait_confirmed(1)
owner.call(owner.restore_if_owned)
report["chain_restores_original_not_old_dictation"] = app_read() == "synthetic user clipboard"

# 4. The user copies something (even identical text) meanwhile: theirs wins.
offer("Synthetic dictation four.")
app_read()
app_write({wd.CF_UNICODETEXT: text("Synthetic dictation four.")})
report["user_copy_not_overwritten"] = (owner.call(owner.restore_if_owned) is False
                                       and app_read() == "Synthetic dictation four.")

# 5. Rich and private formats survive byte for byte.
rich = {wd.CF_UNICODETEXT: text("rich source"), HTML: b"Version:0.9\r\n<b>synthetic</b>\0",
        PRIVATE: bytes(range(256)) * 4}
app_write(rich)
offer("Synthetic dictation five.")
report["privacy_formats_present"] = all(owner._formats[n] in app_formats() for n in owner._formats)
app_read()
owner.wait_confirmed(1)
owner.call(owner.restore_if_owned)
report["rich_formats_restored"] = (app_read(HTML).startswith(rich[HTML])
                                   and app_read(PRIVATE)[:1024] == rich[PRIVATE]
                                   and app_read() == "rich source")

# 6. An empty clipboard stays empty after the round trip.
app_write({})
offer("Synthetic dictation six.")
app_read()
owner.wait_confirmed(1)
owner.call(owner.restore_if_owned)
report["empty_stays_empty"] = app_formats() == []

# 7. Explicit copy puts plain text there, marked private.
owner.call(lambda: owner.copy_plain("Synthetic copied text."))
report["copy_plain"] = app_read() == "Synthetic copied text."

print(json.dumps(report))
