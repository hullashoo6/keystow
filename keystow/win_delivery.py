"""Windows text delivery: paste one dictation into the window it was meant for.

Why this exists. The earlier approach copied the text, sent Ctrl+V, waited a
fixed 0.3 s and put the previous clipboard back. Nothing tells KeyStow when the
target app actually reads the clipboard, so a slow app could read after the
restore and paste the previous clipboard - which was itself an earlier
dictation whenever an earlier restore had been skipped.

What this module does instead:

* The dictation is offered with delayed rendering. Windows asks KeyStow's own
  hidden window for the text at the moment an app reads it, and reports which
  window has the clipboard open. A read by the target's process confirms the
  paste. Only then is the previous clipboard put back.
* No confirmed read, no restore: the dictation stays on the clipboard, so a
  late read still gets the right text. Restoring is what caused stale pastes.
* The previous clipboard is restored only if KeyStow still owns the clipboard,
  so anything the user copied in the meantime - even identical text - wins.
* The text is marked so Windows clipboard history and Cloud Clipboard skip it.
* Nothing is sent when the foreground window changed since the key release,
  when it is KeyStow itself, or when it runs with higher privileges (Windows
  would drop the keys silently). The caller then offers "Copy" instead.
* Nothing is ever retried: a paste that may have landed is never sent twice.
"""

import ctypes
import ctypes.wintypes as wt
import itertools
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from types import SimpleNamespace

# How long to wait for the target app to read the clipboard after Ctrl+V.
CONFIRM_TIMEOUT_SECONDS = 3.0
# After a confirmed read, keep the dictation available briefly for apps that
# read the clipboard more than once while handling one paste.
RESTORE_GRACE_SECONDS = 0.25
# Do not snapshot (and later restore) a previous clipboard larger than this.
SNAPSHOT_LIMIT_BYTES = 32 * 1024 * 1024

_class_numbers = itertools.count(1)

# Outcomes reported to the controller.
CONFIRMED = "confirmed"        # the target app read the dictation
UNCONFIRMED = "unconfirmed"    # keys were sent; no read was seen in time
MANUAL = "manual"              # nothing was sent; the user should paste

CF_TEXT, CF_BITMAP, CF_METAFILEPICT, CF_OEMTEXT, CF_DIB, CF_PALETTE = 1, 2, 3, 7, 8, 9
CF_UNICODETEXT, CF_ENHMETAFILE, CF_LOCALE, CF_DIBV5 = 13, 14, 16, 17
_GDI_FORMATS = {CF_BITMAP, CF_METAFILEPICT, CF_PALETTE, CF_ENHMETAFILE}
_SYNTHESIZED = {CF_TEXT, CF_OEMTEXT, CF_LOCALE}  # Windows rebuilds these from Unicode text

WM_DESTROY, WM_APP = 0x0002, 0x8000
WM_RENDERFORMAT, WM_RENDERALLFORMATS, WM_DESTROYCLIPBOARD = 0x0305, 0x0306, 0x0307
GMEM_MOVEABLE = 0x0002
HWND_MESSAGE = wt.HWND(-3)
INPUT_KEYBOARD, KEYEVENTF_KEYUP = 1, 0x0002
VK_CONTROL, VK_SHIFT, VK_MENU, VK_LWIN, VK_RWIN, VK_V = 0x11, 0x10, 0x12, 0x5B, 0x5C, 0x56
PROCESS_QUERY_LIMITED_INFORMATION, TOKEN_QUERY, TokenIntegrityLevel = 0x1000, 0x0008, 25
ProcessPowerThrottling, PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 4, 0x1


@dataclass
class Target:
    """The window that was in front when the user released the key."""
    hwnd: int
    pid: int


@dataclass
class Result:
    outcome: str
    reason: str = ""            # short machine-readable reason for MANUAL/UNCONFIRMED
    restored: bool = False      # the previous clipboard was put back
    details: dict = field(default_factory=dict)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _MOUSEINPUT(ctypes.Structure):  # only here to size the INPUT union correctly
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


class _POWER_THROTTLING_STATE(ctypes.Structure):
    _fields_ = [("Version", wt.ULONG), ("ControlMask", wt.ULONG), ("StateMask", wt.ULONG)]


_WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class _WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", _WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR)]


def _bind():
    """Load the Win32 functions with explicit pointer-sized signatures."""
    u = ctypes.WinDLL("user32", use_last_error=True)
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    a = ctypes.WinDLL("advapi32", use_last_error=True)
    g = ctypes.WinDLL("gdi32", use_last_error=True)
    H, P, B, U, D = wt.HANDLE, ctypes.c_void_p, wt.BOOL, wt.UINT, wt.DWORD
    sig = {
        (u, "OpenClipboard"): (B, [wt.HWND]), (u, "CloseClipboard"): (B, []),
        (u, "EmptyClipboard"): (B, []), (u, "GetClipboardOwner"): (wt.HWND, []),
        (u, "GetOpenClipboardWindow"): (wt.HWND, []),
        (u, "EnumClipboardFormats"): (U, [U]), (u, "GetClipboardData"): (H, [U]),
        (u, "SetClipboardData"): (H, [U, H]), (u, "RegisterClipboardFormatW"): (U, [wt.LPCWSTR]),
        (u, "GetClipboardSequenceNumber"): (D, []), (u, "GetForegroundWindow"): (wt.HWND, []),
        (u, "GetWindowThreadProcessId"): (D, [wt.HWND, ctypes.POINTER(D)]),
        (u, "IsHungAppWindow"): (B, [wt.HWND]), (u, "GetAsyncKeyState"): (ctypes.c_short, [ctypes.c_int]),
        (u, "SendInput"): (U, [U, P, ctypes.c_int]),
        (u, "RegisterClassW"): (wt.ATOM, [P]),
        (u, "CreateWindowExW"): (wt.HWND, [D, wt.LPCWSTR, wt.LPCWSTR, D, ctypes.c_int, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, P]),
        (u, "DefWindowProcW"): (ctypes.c_ssize_t, [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]),
        (u, "GetMessageW"): (B, [P, wt.HWND, U, U]), (u, "TranslateMessage"): (B, [P]),
        (u, "DispatchMessageW"): (ctypes.c_ssize_t, [P]),
        (u, "PostMessageW"): (B, [wt.HWND, U, wt.WPARAM, wt.LPARAM]),
        (u, "DestroyWindow"): (B, [wt.HWND]), (u, "PostQuitMessage"): (None, [ctypes.c_int]),
        (k, "GlobalAlloc"): (H, [U, ctypes.c_size_t]), (k, "GlobalLock"): (P, [H]),
        (k, "GlobalUnlock"): (B, [H]), (k, "GlobalSize"): (ctypes.c_size_t, [H]),
        (k, "GlobalFree"): (H, [H]), (k, "GetModuleHandleW"): (wt.HMODULE, [wt.LPCWSTR]),
        (k, "OpenProcess"): (H, [D, B, D]), (k, "CloseHandle"): (B, [H]),
        (k, "GetCurrentProcess"): (H, []), (k, "GetCurrentProcessId"): (D, []),
        (k, "SetProcessInformation"): (B, [H, ctypes.c_int, P, D]),
        (a, "OpenProcessToken"): (B, [H, D, ctypes.POINTER(H)]),
        (a, "GetTokenInformation"): (B, [H, ctypes.c_int, P, D, ctypes.POINTER(D)]),
        (a, "GetSidSubAuthorityCount"): (ctypes.POINTER(ctypes.c_ubyte), [P]),
        (a, "GetSidSubAuthority"): (ctypes.POINTER(D), [P, D]),
        (g, "CopyEnhMetaFileW"): (H, [H, wt.LPCWSTR]),
    }
    ns = {}
    for (dll, name), (restype, argtypes) in sig.items():
        fn = getattr(dll, name)
        fn.restype, fn.argtypes = restype, argtypes
        ns[name] = fn
    return SimpleNamespace(**ns)


W = _bind() if os.name == "nt" else None


class _Unsafe(Exception):
    """The previous clipboard holds something KeyStow cannot put back faithfully."""


def capture_target():
    """The foreground window and its process, or None when nothing is in front."""
    hwnd = W.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wt.DWORD(0)
    W.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return Target(int(hwnd), int(pid.value))


def key_down(vk: int) -> bool:
    """Whether a key is physically held right now (works for left/right modifiers)."""
    return bool(W.GetAsyncKeyState(int(vk)) & 0x8000)


def disable_power_throttling() -> bool:
    """Opt out of Windows' background "power throttling" (EcoQoS).

    KeyStow usually runs minimised. Windows may then run it on efficiency
    cores or at reduced clock speed, which makes transcription noticeably
    slower. KeyStow is idle between dictations, so opting out costs nothing
    while it waits.
    """
    state = _POWER_THROTTLING_STATE(1, PROCESS_POWER_THROTTLING_EXECUTION_SPEED, 0)
    return bool(W.SetProcessInformation(W.GetCurrentProcess(), ProcessPowerThrottling,
                                        ctypes.byref(state), ctypes.sizeof(state)))


def _integrity_level(pid: int):
    """The process integrity RID, or "denied" when Windows will not say, or None."""
    process = W.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not process:
        return None
    try:
        token = wt.HANDLE()
        if not W.OpenProcessToken(process, TOKEN_QUERY, ctypes.byref(token)):
            return "denied" if ctypes.get_last_error() == 5 else None
        try:
            need = wt.DWORD(0)
            W.GetTokenInformation(token, TokenIntegrityLevel, None, 0, ctypes.byref(need))
            buffer = ctypes.create_string_buffer(max(need.value, 64))
            if not W.GetTokenInformation(token, TokenIntegrityLevel, buffer, need, ctypes.byref(need)):
                return None
            sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]  # TOKEN_MANDATORY_LABEL.Label.Sid
            count = W.GetSidSubAuthorityCount(sid)[0]
            return int(W.GetSidSubAuthority(sid, count - 1)[0])
        finally:
            W.CloseHandle(token)
    finally:
        W.CloseHandle(process)


def _target_is_more_privileged(pid: int) -> bool:
    """Windows silently drops keys sent to a window that runs with more privilege."""
    theirs = _integrity_level(pid)
    if theirs == "denied":
        return True  # an elevated process refuses this query from a normal one
    ours = _integrity_level(os.getpid())
    return isinstance(theirs, int) and isinstance(ours, int) and theirs > ours


def _modifiers_released(timeout: float = 0.5) -> bool:
    """Wait briefly for Shift/Alt/Windows to be let go so Ctrl+V stays Ctrl+V."""
    deadline = time.monotonic() + timeout
    while True:
        if not any(key_down(vk) for vk in (VK_SHIFT, VK_MENU, VK_LWIN, VK_RWIN)):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.02)


def _open_clipboard(hwnd, timeout: float = 0.5) -> bool:
    """Another app may hold the clipboard open for a moment; retry briefly."""
    deadline = time.monotonic() + timeout
    while not W.OpenClipboard(hwnd):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.01)
    return True


def _global_from_bytes(data: bytes):
    handle = W.GlobalAlloc(GMEM_MOVEABLE, max(len(data), 1))
    if not handle:
        return None
    pointer = W.GlobalLock(handle)
    if not pointer:
        W.GlobalFree(handle)
        return None
    try:
        ctypes.memmove(pointer, data, len(data))
    finally:
        W.GlobalUnlock(handle)
    return handle


def _set_bytes(fmt: int, data: bytes) -> bool:
    handle = _global_from_bytes(data)
    if handle is None:
        return False
    if not W.SetClipboardData(fmt, handle):
        W.GlobalFree(handle)  # ownership passes to Windows only on success
        return False
    return True


def _snapshot():
    """Copy every clipboard format so it can be put back exactly. Clipboard is open.

    Raises _Unsafe when something cannot be copied faithfully: device-dependent
    GDI objects with no portable twin, private handle formats, an owner that is
    not responding (asking it to render would hang), or very large contents.
    """
    owner = W.GetClipboardOwner()
    if owner and W.IsHungAppWindow(owner):
        raise _Unsafe("owner_not_responding")
    formats, fmt = [], 0
    while True:
        fmt = W.EnumClipboardFormats(fmt)
        if not fmt:
            break
        formats.append(fmt)
    present, items, total = set(formats), [], 0
    for fmt in formats:
        if fmt in _SYNTHESIZED or fmt == CF_PALETTE:
            continue
        if fmt == CF_BITMAP and (CF_DIB in present or CF_DIBV5 in present):
            continue
        if fmt == CF_METAFILEPICT and CF_ENHMETAFILE in present:
            continue
        if fmt == CF_ENHMETAFILE:
            handle = W.GetClipboardData(fmt)
            copy = W.CopyEnhMetaFileW(handle, None) if handle else None
            if handle and not copy:
                raise _Unsafe("metafile")
            if copy:
                items.append((fmt, "emf", copy))
            continue
        if fmt in _GDI_FORMATS or 0x80 <= fmt <= 0x8E or 0x200 <= fmt <= 0x3FF:
            raise _Unsafe(f"format_{fmt}")
        handle = W.GetClipboardData(fmt)
        if not handle:
            continue  # the owner could not render this one; skip it
        size = W.GlobalSize(handle)
        total += size
        if total > SNAPSHOT_LIMIT_BYTES:
            raise _Unsafe("too_large")
        pointer = W.GlobalLock(handle)
        if not pointer:
            raise _Unsafe(f"unlockable_{fmt}")
        try:
            items.append((fmt, "bytes", ctypes.string_at(pointer, size)))
        finally:
            W.GlobalUnlock(handle)
    return items


def _put_back(items) -> None:
    """Write a snapshot back. The clipboard is open and has just been emptied."""
    for fmt, kind, data in items:
        if kind == "emf":
            W.SetClipboardData(fmt, data)
        else:
            _set_bytes(fmt, data)


class _Owner:
    """A hidden window, on its own thread, that owns KeyStow's clipboard data.

    All clipboard work happens on this thread. Windows sends WM_RENDERFORMAT
    here, synchronously, when any app reads the dictation, so the message loop
    must keep running; nothing here blocks for long.
    """

    CLASS_NAME = "KeyStowClipboardOwner"

    def __init__(self):
        self._calls = queue.SimpleQueue()
        self._started = threading.Event()
        self._proc = _WNDPROC(self._wndproc)  # keep the callback alive
        self.hwnd = None
        self._formats = None
        self._pending = None     # the dictation currently offered
        self._carry = None       # the user's clipboard from before an unrestored dictation
        self._restoring = False
        self._lost = threading.Event()
        thread = threading.Thread(target=self._run, name="keystow-clipboard", daemon=True)
        thread.start()
        if not self._started.wait(5) or not self.hwnd:
            raise OSError("KeyStow's clipboard window could not start")

    def _run(self):
        instance = W.GetModuleHandleW(None)
        # A class per instance: a window class sends every window's messages
        # to the procedure it was registered with, so a replacement thread
        # must never share the class of one that stopped answering.
        self._class_name = f"{self.CLASS_NAME}{next(_class_numbers)}"
        wc = _WNDCLASSW()
        wc.lpfnWndProc = self._proc
        wc.hInstance = instance
        wc.lpszClassName = self._class_name
        W.RegisterClassW(ctypes.byref(wc))
        self.hwnd = W.CreateWindowExW(0, self._class_name, "KeyStow clipboard", 0, 0, 0, 0, 0,
                                      HWND_MESSAGE, None, instance, None)
        self._formats = {
            name: W.RegisterClipboardFormatW(name)
            for name in ("ExcludeClipboardContentFromMonitorProcessing",
                         "CanIncludeInClipboardHistory", "CanUploadToCloudClipboard")
        }
        self._started.set()
        if not self.hwnd:
            return
        msg = wt.MSG()
        while W.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            W.TranslateMessage(ctypes.byref(msg))
            W.DispatchMessageW(ctypes.byref(msg))

    def call(self, fn, timeout: float = 5.0):
        """Run fn on the clipboard thread and return its result."""
        box = {"done": threading.Event()}
        self._calls.put((fn, box))
        W.PostMessageW(self.hwnd, WM_APP, 0, 0)
        if not box["done"].wait(timeout):
            raise TimeoutError("the clipboard thread did not respond")
        if "error" in box:
            raise box["error"]
        return box.get("value")

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_APP:
                while True:
                    try:
                        fn, box = self._calls.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        box["value"] = fn()
                    except BaseException as exc:  # noqa: BLE001 - handed back to the caller
                        box["error"] = exc
                    box["done"].set()
                return 0
            if msg == WM_RENDERFORMAT:
                self._render(int(wparam))
                return 0
            if msg == WM_RENDERALLFORMATS:
                self._render_all()
                return 0
            if msg == WM_DESTROYCLIPBOARD:
                if not self._restoring:
                    self._lost.set()  # someone else (usually the user) copied something
                return 0
        except Exception:
            logging.exception("clipboard window message failed")
        return W.DefWindowProcW(hwnd, msg, wparam, lparam)

    # --- runs on the clipboard thread -------------------------------------

    def _text_bytes(self, text: str) -> bytes:
        return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-16-le") + b"\0\0"

    def _mark_private(self) -> None:
        """Ask clipboard history, Cloud Clipboard and clipboard managers to skip this."""
        zero = (0).to_bytes(4, "little")
        _set_bytes(self._formats["ExcludeClipboardContentFromMonitorProcessing"], zero)
        _set_bytes(self._formats["CanIncludeInClipboardHistory"], zero)
        _set_bytes(self._formats["CanUploadToCloudClipboard"], zero)

    def _render(self, fmt: int) -> None:
        pending = self._pending
        if pending is None or fmt != CF_UNICODETEXT:
            return
        requester = W.GetOpenClipboardWindow()
        pid = wt.DWORD(0)
        if requester:
            W.GetWindowThreadProcessId(requester, ctypes.byref(pid))
        pending["reads"].append((time.monotonic(), int(pid.value)))
        _set_bytes(CF_UNICODETEXT, pending["data"])
        if pending["sent"] and pid.value and pid.value == pending["target_pid"]:
            pending["confirmed"].set()

    def _render_all(self) -> None:
        """KeyStow is exiting while still owning a dictation: render it for real."""
        pending = self._pending
        if pending is None or not _open_clipboard(self.hwnd):
            return
        try:
            if W.GetClipboardOwner() == self.hwnd:
                _set_bytes(CF_UNICODETEXT, pending["data"])
        finally:
            W.CloseClipboard()

    def offer(self, text: str, target_pid: int) -> str:
        """Put the dictation on the clipboard, rendered on demand. Returns "ok" or a reason."""
        if not _open_clipboard(self.hwnd):
            return "clipboard_busy"
        try:
            if W.GetClipboardOwner() == self.hwnd and self._carry is not None:
                # The clipboard still holds an earlier dictation that was never
                # confirmed. What to restore later is what the user had before it,
                # never that earlier dictation.
                previous = self._carry
            else:
                try:
                    previous = _snapshot()
                except _Unsafe as exc:
                    return f"clipboard_{exc}"
            self._restoring = True
            try:
                if not W.EmptyClipboard():
                    return "clipboard_busy"
            finally:
                self._restoring = False
            self._lost.clear()
            self._pending = {"data": self._text_bytes(text), "target_pid": target_pid, "sent": False,
                             "reads": [], "confirmed": threading.Event()}
            self._carry = previous
            W.SetClipboardData(CF_UNICODETEXT, None)  # delayed rendering: we hear about the read
            self._mark_private()
            return "ok"
        finally:
            W.CloseClipboard()

    def restore_if_owned(self) -> bool:
        """Put the user's previous clipboard back, unless they copied something since."""
        previous, self._carry = self._carry, None
        if self._lost.is_set() or W.GetClipboardOwner() != self.hwnd or previous is None:
            self._pending = None
            return False
        if not _open_clipboard(self.hwnd):
            self._carry = previous  # try again after the next dictation
            return False
        try:
            self._restoring = True
            try:
                W.EmptyClipboard()
            finally:
                self._restoring = False
            self._pending = None
            _put_back(previous)
            return True
        finally:
            W.CloseClipboard()

    def copy_plain(self, text: str) -> bool:
        """An explicit "Copy" by the user: plain text, kept out of history and sync."""
        if not _open_clipboard(self.hwnd):
            return False
        try:
            self._restoring = True
            try:
                W.EmptyClipboard()
            finally:
                self._restoring = False
            self._pending, self._carry = None, None
            ok = _set_bytes(CF_UNICODETEXT, self._text_bytes(text))
            self._mark_private()
            return ok
        finally:
            W.CloseClipboard()

    # --- called from the delivering thread -------------------------------

    def mark_sent(self) -> None:
        if self._pending is not None:
            self._pending["sent"] = True

    def wait_confirmed(self, timeout: float) -> bool:
        pending = self._pending
        return bool(pending and pending["confirmed"].wait(timeout))

    def reads(self):
        pending = self._pending
        return list(pending["reads"]) if pending else []


_owner = None
_owner_lock = threading.Lock()


def _get_owner() -> _Owner:
    global _owner
    with _owner_lock:
        if _owner is None:
            _owner = _Owner()
        return _owner


def _abandon_owner(owner) -> None:
    """Stop using a clipboard thread that stopped answering.

    Emptying the clipboard makes Windows notify the previous owner and wait
    for it. An app that is busy and not processing messages can therefore
    hold KeyStow's clipboard thread. Rather than stay stuck, use a new
    thread next time; the old one finishes on its own once the app answers.
    """
    global _owner
    with _owner_lock:
        if _owner is owner:
            _owner = None
    logging.warning("clipboard thread did not respond; starting a new one next time")


def _key_inputs(events):
    array = (_INPUT * len(events))()
    for i, (vk, flags) in enumerate(events):
        array[i].type = INPUT_KEYBOARD
        array[i].u.ki = _KEYBDINPUT(vk, 0, flags, 0, 0)
    return array


def _send_ctrl_v() -> int:
    """Send Ctrl+V as one batch. Returns how many of the 4 key events Windows took."""
    events = [(VK_CONTROL, 0), (VK_V, 0), (VK_V, KEYEVENTF_KEYUP), (VK_CONTROL, KEYEVENTF_KEYUP)]
    sent = W.SendInput(len(events), _key_inputs(events), ctypes.sizeof(_INPUT))
    if 0 < sent < len(events):
        # Never leave Ctrl or V held down in the user's session.
        ups = [(VK_V, KEYEVENTF_KEYUP), (VK_CONTROL, KEYEVENTF_KEYUP)]
        W.SendInput(len(ups), _key_inputs(ups), ctypes.sizeof(_INPUT))
    return int(sent)


def deliver(text: str, target) -> Result:
    """Paste text into target at most once, and report what is known about it."""
    if not text:
        return Result(MANUAL, "empty")
    if target is None:
        return Result(MANUAL, "no_target")
    if target.pid == os.getpid():
        return Result(MANUAL, "keystow_focused")
    now = capture_target()
    if now is None or now.hwnd != target.hwnd:
        return Result(MANUAL, "focus_changed")
    if _target_is_more_privileged(target.pid):
        return Result(MANUAL, "elevated")
    if not _modifiers_released():
        return Result(MANUAL, "modifier_held")
    owner = _get_owner()
    progress = {"sent": False}
    try:
        return _deliver_with(owner, text, target, progress)
    except TimeoutError:
        _abandon_owner(owner)
        if progress["sent"]:
            return Result(UNCONFIRMED, "clipboard_busy")
        return Result(MANUAL, "clipboard_busy")


def _deliver_with(owner, text, target, progress) -> Result:
    status = owner.call(lambda: owner.offer(text, target.pid))
    if status != "ok":
        return Result(MANUAL, status)
    now = capture_target()
    if now is None or now.hwnd != target.hwnd:
        owner.call(owner.restore_if_owned)  # nothing was sent; give the clipboard back
        return Result(MANUAL, "focus_changed")
    owner.mark_sent()
    sent = _send_ctrl_v()
    progress["sent"] = sent > 0
    if sent == 0:
        owner.call(owner.restore_if_owned)
        return Result(MANUAL, "keys_blocked")
    if sent < 4:
        return Result(UNCONFIRMED, "keys_partial", details={"sent": sent})
    if not owner.wait_confirmed(CONFIRM_TIMEOUT_SECONDS):
        # Leave the dictation on the clipboard: a late read must get this text,
        # not whatever was there before.
        return Result(UNCONFIRMED, "no_read_seen", details={"reads": len(owner.reads())})
    time.sleep(RESTORE_GRACE_SECONDS)
    restored = owner.call(owner.restore_if_owned)
    return Result(CONFIRMED, restored=bool(restored))


def copy_text(text: str) -> bool:
    """Put text on the clipboard because the user asked for it."""
    owner = _get_owner()
    try:
        return bool(owner.call(lambda: owner.copy_plain(text)))
    except TimeoutError:
        _abandon_owner(owner)
        return False
