"""Windows delivery logic against a simulated clipboard, plus the real-clipboard
script where it can run safely (a private window station or a CI machine).

The simulation models the Win32 rules the module relies on: one owner at a
time, EmptyClipboard notifying the previous owner, delayed rendering asking the
owner for data when an app reads it, and GetOpenClipboardWindow naming the
reader. It does not prove what any real app does with Ctrl+V.
"""
import ctypes
import json
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from keystow import win_delivery as wd  # noqa: E402

OWNER_HWND, APP_HWND, OTHER_HWND = 101, 202, 303
PIDS = {OWNER_HWND: 1, APP_HWND: 2, OTHER_HWND: 3}


class FakeClipboard:
    def __init__(self):
        self.owner = None
        self.open_by = None
        self.data = {}          # fmt -> bytes, or None while rendering is delayed
        self.memory = {}        # fake HGLOBAL -> ctypes buffer
        self.next_handle = 1000
        self.owner_object = None

    # memory
    def GlobalAlloc(self, flags, size):
        self.next_handle += 1
        self.memory[self.next_handle] = ctypes.create_string_buffer(size)
        return self.next_handle

    def GlobalLock(self, h):
        return ctypes.addressof(self.memory[h])

    def GlobalUnlock(self, h):
        return True

    def GlobalSize(self, h):
        return len(self.memory[h])

    def GlobalFree(self, h):
        self.memory.pop(h, None)

    # clipboard
    def OpenClipboard(self, hwnd):
        if self.open_by is not None:
            return False
        self.open_by = hwnd
        return True

    def CloseClipboard(self):
        self.open_by = None
        return True

    def EmptyClipboard(self):
        assert self.open_by is not None
        previous = self.owner
        self.data = {}
        self.owner = self.open_by
        if previous == OWNER_HWND and self.owner_object is not None:
            self.owner_object._wndproc(OWNER_HWND, wd.WM_DESTROYCLIPBOARD, 0, 0)
        return True

    def SetClipboardData(self, fmt, handle):
        assert self.open_by is not None or self.rendering
        self.data[fmt] = None if handle is None else bytes(self.memory.pop(handle))
        return handle or 1

    rendering = False

    def GetClipboardData(self, fmt):
        assert self.open_by is not None
        if fmt not in self.data:
            return None
        if self.data[fmt] is None and self.owner == OWNER_HWND:
            self.rendering = True
            try:
                self.owner_object._wndproc(OWNER_HWND, wd.WM_RENDERFORMAT, fmt, 0)
            finally:
                self.rendering = False
        raw = self.data.get(fmt)
        if raw is None:
            return None
        handle = self.GlobalAlloc(0, len(raw))
        ctypes.memmove(self.memory[handle], raw, len(raw))
        return handle

    def EnumClipboardFormats(self, fmt):
        formats = list(self.data)
        if fmt == 0:
            return formats[0] if formats else 0
        index = formats.index(fmt) + 1
        return formats[index] if index < len(formats) else 0

    def GetClipboardOwner(self):
        return self.owner

    def GetOpenClipboardWindow(self):
        return self.open_by

    def GetWindowThreadProcessId(self, hwnd, pid_ref):
        pid_ref._obj.value = PIDS.get(hwnd, 0)
        return 1

    def IsHungAppWindow(self, hwnd):
        return False

    def RegisterClipboardFormatW(self, name):
        return 0xC000 + sum(map(ord, name)) % 0x3000

    # what other apps do
    def app_write(self, hwnd, formats):
        assert self.OpenClipboard(hwnd)
        self.EmptyClipboard()
        self.data = dict(formats)
        self.CloseClipboard()

    def app_read(self, hwnd, fmt=wd.CF_UNICODETEXT):
        assert self.OpenClipboard(hwnd)
        try:
            handle = self.GetClipboardData(fmt)
            return None if handle is None else bytes(self.memory[handle])
        finally:
            self.CloseClipboard()


def text(s):
    return s.encode("utf-16-le") + b"\0\0"


def decoded(raw):
    return None if raw is None else raw.decode("utf-16-le").split("\0", 1)[0]


class OwnerLogicTest(unittest.TestCase):
    """The ownership and restore rules, one dictation at a time."""

    def setUp(self):
        self.clip = FakeClipboard()
        patcher = patch.object(wd, "W", self.clip)
        patcher.start()
        self.addCleanup(patcher.stop)
        owner = object.__new__(wd._Owner)
        owner.hwnd = OWNER_HWND
        owner._formats = {n: self.clip.RegisterClipboardFormatW(n)
                          for n in ("ExcludeClipboardContentFromMonitorProcessing",
                                    "CanIncludeInClipboardHistory", "CanUploadToCloudClipboard")}
        owner._pending = owner._carry = None
        owner._restoring = False
        owner._lost = threading.Event()
        owner.call = lambda fn, timeout=5.0: fn()
        self.clip.owner_object = self.owner = owner
        self.clip.app_write(APP_HWND, {wd.CF_UNICODETEXT: text("user clipboard")})

    def dictate(self, s, target=APP_HWND):
        self.assertEqual(self.owner.offer(s, PIDS[target]), "ok")
        self.owner.mark_sent()

    def test_target_read_confirms_and_previous_comes_back(self):
        self.dictate("Synthetic one.")
        self.assertEqual(decoded(self.clip.app_read(APP_HWND)), "Synthetic one.")
        self.assertTrue(self.owner.wait_confirmed(0))
        self.assertTrue(self.owner.restore_if_owned())
        self.assertEqual(decoded(self.clip.app_read(APP_HWND)), "user clipboard")

    def test_read_by_another_process_does_not_confirm(self):
        self.dictate("Synthetic two.")
        self.clip.app_read(OTHER_HWND)  # a clipboard manager ignoring the opt-out
        self.assertFalse(self.owner.wait_confirmed(0))

    def test_late_read_gets_the_new_dictation_not_an_old_value(self):
        self.dictate("Synthetic three.")
        self.assertFalse(self.owner.wait_confirmed(0))  # unconfirmed: nothing restored
        self.assertEqual(decoded(self.clip.app_read(APP_HWND)), "Synthetic three.")

    def test_after_unconfirmed_dictation_the_original_is_restored_not_the_old_dictation(self):
        self.dictate("Synthetic four.")          # never confirmed, left on the clipboard
        self.dictate("Synthetic five.")
        self.clip.app_read(APP_HWND)
        self.assertTrue(self.owner.restore_if_owned())
        self.assertEqual(decoded(self.clip.app_read(APP_HWND)), "user clipboard")

    def test_user_copy_even_identical_text_is_never_overwritten(self):
        self.dictate("Synthetic six.")
        self.clip.app_read(APP_HWND)
        self.clip.app_write(APP_HWND, {wd.CF_UNICODETEXT: text("Synthetic six.")})
        self.assertFalse(self.owner.restore_if_owned())
        self.assertEqual(decoded(self.clip.app_read(APP_HWND)), "Synthetic six.")

    def test_rich_and_private_formats_round_trip_exactly(self):
        html, private = 0xC101, 0xC202
        rich = {wd.CF_UNICODETEXT: text("rich"), html: b"<b>synthetic</b>\0", private: bytes(range(256))}
        self.clip.app_write(APP_HWND, rich)
        self.dictate("Synthetic seven.")
        self.clip.app_read(APP_HWND)
        self.owner.restore_if_owned()
        self.assertEqual(self.clip.data, rich)

    def test_dictation_is_marked_out_of_history_and_cloud_sync(self):
        self.dictate("Synthetic eight.")
        for fmt in self.owner._formats.values():
            self.assertIn(fmt, self.clip.data)

    def test_gdi_only_clipboard_is_refused_untouched(self):
        self.clip.app_write(APP_HWND, {wd.CF_PALETTE: b"", 0x0300: b"x"})
        before = dict(self.clip.data)
        self.assertTrue(self.owner.offer("Synthetic nine.", PIDS[APP_HWND]).startswith("clipboard_"))
        self.assertEqual(self.clip.data, before)

    def test_empty_clipboard_stays_empty(self):
        self.clip.app_write(APP_HWND, {})
        self.dictate("Synthetic ten.")
        self.clip.app_read(APP_HWND)
        self.owner.restore_if_owned()
        self.assertEqual(self.clip.data, {})


class DeliverDecisionTest(unittest.TestCase):
    """deliver() sends nothing when it cannot be sure where the text would go."""

    def setUp(self):
        self.target = wd.Target(hwnd=APP_HWND, pid=4242)
        self.owner = SimpleNamespace(
            call=lambda fn, timeout=5.0: fn(), offer=lambda text, pid: "ok",
            restored=0, mark_sent=lambda: None, wait_confirmed=lambda t: True, reads=lambda: [])

        def restore():
            self.owner.restored += 1
            return True
        self.owner.restore_if_owned = restore
        self.sent = []
        for name, value in {
            "_get_owner": lambda: self.owner,
            "capture_target": lambda: self.target,
            "_target_is_more_privileged": lambda pid: False,
            "_modifiers_released": lambda timeout=0.5: True,
            "_send_ctrl_v": lambda: self.sent.append(1) or 4,
            "RESTORE_GRACE_SECONDS": 0,
        }.items():
            p = patch.object(wd, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_confirmed_paste_restores(self):
        result = wd.deliver("Synthetic text.", self.target)
        self.assertEqual((result.outcome, result.restored, len(self.sent)), (wd.CONFIRMED, True, 1))

    def test_focus_change_sends_nothing(self):
        with patch.object(wd, "capture_target", lambda: wd.Target(OTHER_HWND, 9)):
            result = wd.deliver("Synthetic text.", self.target)
        self.assertEqual((result.outcome, result.reason, self.sent), (wd.MANUAL, "focus_changed", []))

    def test_keystow_itself_in_front_sends_nothing(self):
        result = wd.deliver("Synthetic text.", wd.Target(APP_HWND, os.getpid()))
        self.assertEqual((result.outcome, result.reason, self.sent), (wd.MANUAL, "keystow_focused", []))

    def test_elevated_target_sends_nothing(self):
        with patch.object(wd, "_target_is_more_privileged", lambda pid: True):
            result = wd.deliver("Synthetic text.", self.target)
        self.assertEqual((result.reason, self.sent), ("elevated", []))

    def test_no_confirmed_read_leaves_text_and_does_not_restore(self):
        self.owner.wait_confirmed = lambda t: False
        result = wd.deliver("Synthetic text.", self.target)
        self.assertEqual((result.outcome, self.owner.restored, len(self.sent)), (wd.UNCONFIRMED, 0, 1))

    def test_blocked_keys_give_the_clipboard_back_and_never_retry(self):
        with patch.object(wd, "_send_ctrl_v", lambda: self.sent.append(1) or 0):
            result = wd.deliver("Synthetic text.", self.target)
        self.assertEqual((result.reason, self.owner.restored, len(self.sent)), ("keys_blocked", 1, 1))

    def test_unsafe_previous_clipboard_sends_nothing(self):
        self.owner.offer = lambda text, pid: "clipboard_format_768"
        result = wd.deliver("Synthetic text.", self.target)
        self.assertEqual((result.outcome, self.sent), (wd.MANUAL, []))


@unittest.skipUnless(os.name == "nt", "Windows clipboard")
class RealClipboardTest(unittest.TestCase):
    """Real Win32 clipboard; skips itself unless that clipboard belongs to nobody."""

    def test_real_clipboard_round_trips(self):
        script = Path(__file__).with_name("win_clipboard_isolated.py")
        out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        report = json.loads(out.stdout.strip().splitlines()[-1])
        if "skipped" in report:
            self.skipTest(report["skipped"])
        self.assertEqual({k: v for k, v in report.items() if v not in (True, "ok")}, {})


if __name__ == "__main__":
    unittest.main()
