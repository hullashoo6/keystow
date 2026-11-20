"""Frozen-process ownership/close test, not microphone or dictation acceptance."""
import ctypes
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import psutil

exe=Path(sys.argv[1]).resolve()
evidence=Path(sys.argv[2]);evidence.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as home:
    env=dict(os.environ,HOME=home,USERPROFILE=home)
    output=(evidence/'frozen-process.log').open('w')
    p=subprocess.Popen([str(exe)],env=env,stdout=output,stderr=subprocess.STDOUT)
    tracked=set([p.pid])
    def family():
        try:return psutil.Process(p.pid).children(recursive=True)
        except psutil.Error:return []
    try:
        deadline=time.monotonic()+120
        if sys.platform=='win32':
            from ctypes import wintypes
            found=[]
            callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
            def scan(hwnd,param):
                pid=wintypes.DWORD();ctypes.windll.user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
                if pid.value in tracked:
                    buf=ctypes.create_unicode_buffer(512);ctypes.windll.user32.GetWindowTextW(hwnd,buf,512)
                    if buf.value=='KeyStow':found.append(hwnd)
                return True
            callback=callback_type(scan)
            while time.monotonic()<deadline and p.poll() is None:
                tracked.update(c.pid for c in family());ctypes.windll.user32.EnumWindows(callback,0)
                if found:break
                time.sleep(.2)
            assert found,'Frozen app did not create its real KeyStow window'
        else:
            time.sleep(10);tracked.update(c.pid for c in family())
        assert p.poll() is None,'Primary exited during startup'
        # Second guarded copy must exit without creating another dictation owner.
        start=time.monotonic()
        secondary=subprocess.run([str(exe)],env=env,stdout=output,stderr=subprocess.STDOUT,timeout=45)
        assert secondary.returncode==0,secondary.returncode
        duplicate_seconds=time.monotonic()-start
        assert p.poll() is None,'Secondary launch terminated primary'
        tracked.update(c.pid for c in family())
        before=[{'pid':pid,'name':psutil.Process(pid).name()} for pid in sorted(tracked) if psutil.pid_exists(pid)]
        start=time.monotonic()
        if sys.platform=='win32':
            assert ctypes.windll.user32.PostMessageW(found[0],0x0010,0,0),'WM_CLOSE failed'
            close_action='WM_CLOSE on actual frozen Qt window'
        else:
            # Apple-event Quit is native OS integration, window Close is covered
            # separately by real Qt component tests on this same macOS runner.
            subprocess.run(['osascript','-e','tell application "KeyStow" to quit'],check=True,timeout=20)
            close_action='native Apple-event Quit; window Close covered by Qt test'
        assert p.wait(timeout=120)==0
        deadline=time.monotonic()+10
        while any(psutil.pid_exists(pid) for pid in tracked) and time.monotonic()<deadline:time.sleep(.2)
        remaining=[pid for pid in tracked if psutil.pid_exists(pid)]
        assert not remaining,remaining
        result={'architecture':platform.machine(),'frozen_executable':str(exe),'duplicate_exit':secondary.returncode,'duplicate_seconds':duplicate_seconds,'close_action':close_action,'close_seconds':time.monotonic()-start,'processes_before_close':before,'remaining_tracked_processes':remaining,'real_microphone_hotkey_paste_acceptance':False}
        (evidence/'frozen-processes.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2))
    finally:
        for process in reversed(family()):
            try:process.kill()
            except psutil.Error:pass
        if p.poll() is None:p.kill();p.wait(timeout=10)
        output.close()
