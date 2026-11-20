"""Real process lock lifetime. Does not claim real microphone or OS paste."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT='''
import sys,time
from pathlib import Path
from keystow.single_instance import InstanceGuard
g=InstanceGuard(sys.argv[1])
if not g.acquire():
 print('SECONDARY',flush=True)
 sys.exit(0)
print('PRIMARY',flush=True)
if sys.argv[2]=='probe':
 g.release()
 sys.exit(0)
while not (Path(sys.argv[1])/'stop').exists():time.sleep(.02)
g.release()
'''

class InstanceProcessTest(unittest.TestCase):
    def spawn(self,d,mode):
        return subprocess.Popen([sys.executable,'-u','-c',SCRIPT,d,mode],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

    def probe(self,d):
        p=self.spawn(d,'probe');out,err=p.communicate(timeout=10)
        self.assertEqual(p.returncode,0,err)
        return out.strip()

    def test_second_process_exits_and_clean_quit_allows_restart(self):
        with tempfile.TemporaryDirectory() as d:
            sentinel=Path(d)/'settings.json';sentinel.write_bytes(b'{"hotkey":"ctrl_r","activation_mode":"hold"}')
            p=self.spawn(d,'hold')
            try:
                self.assertEqual(p.stdout.readline().strip(),'PRIMARY')
                for _ in range(3):self.assertEqual(self.probe(d),'SECONDARY')
                Path(d,'stop').touch();p.communicate(timeout=10)
                self.assertEqual(p.returncode,0)
                self.assertEqual(self.probe(d),'PRIMARY')
                self.assertEqual(sentinel.read_bytes(),b'{"hotkey":"ctrl_r","activation_mode":"hold"}')
            finally:
                if p.poll() is None:p.kill();p.communicate(timeout=10)

    def test_crashed_owner_releases_process_lock_for_restart(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.spawn(d,'hold')
            try:
                self.assertEqual(p.stdout.readline().strip(),'PRIMARY')
                self.assertEqual(self.probe(d),'SECONDARY')
                p.kill();p.communicate(timeout=10)
                self.assertEqual(self.probe(d),'PRIMARY')
            finally:
                if p.poll() is None:p.kill();p.communicate(timeout=10)

    def test_duplicate_run_app_never_constructs_controller(self):
        script='''
import tempfile
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QApplication
from keystow import ui
from keystow.single_instance import InstanceGuard
with tempfile.TemporaryDirectory() as d:
 primary=InstanceGuard(d);assert primary.acquire()
 factory=Mock()
 with patch('keystow.single_instance.paths.data_dir',return_value=d),patch.object(ui,'MainWindow') as window:
  assert ui.run_app(factory)==0
  factory.assert_not_called();window.assert_not_called()
 assert primary.owned
 primary.release()
'''
        r=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_secondary_launch_hands_focus_to_primary_without_taking_lock(self):
        script='''
import tempfile
from PySide6.QtCore import QCoreApplication,QTimer
from keystow.single_instance import InstanceGuard
app=QCoreApplication([])
with tempfile.TemporaryDirectory() as d:
 primary=InstanceGuard(d);assert primary.acquire()
 received=[]
 primary.listen(lambda: (received.append(True),app.quit()))
 secondary=InstanceGuard(d);assert not secondary.acquire()
 assert secondary.activate_existing()
 QTimer.singleShot(3000,app.quit)
 app.exec()
 assert received==[True],received
 assert primary.owned and not secondary.owned
 primary.release()
 assert secondary.acquire()
 secondary.release()
'''
        r=subprocess.run([sys.executable,'-c',script],cwd=ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_failed_handoff_still_never_constructs_controller(self):
        script='''
import tempfile
from unittest.mock import Mock,patch
from keystow import ui
from keystow.single_instance import InstanceGuard
with tempfile.TemporaryDirectory() as d:
 primary=InstanceGuard(d);assert primary.acquire()
 factory=Mock()
 with patch('keystow.single_instance.paths.data_dir',return_value=d),patch.object(ui,'MainWindow') as window:
  assert ui.run_app(factory)==0
  factory.assert_not_called();window.assert_not_called()
 primary.release()
'''
        r=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_window_close_shuts_down_controller_and_process(self):
        script='''
from unittest.mock import patch
import tempfile
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from keystow import ui
calls=[]
class Controller:
 def __init__(self,w):self.w=w;self.idle=False
 def start(self):QTimer.singleShot(50,self.w.close)
 def shutdown(self):calls.append('shutdown');QTimer.singleShot(50,self.done)
 def done(self):self.idle=True
 def can_exit(self):return self.idle
 def wait_for_shutdown(self):calls.append('joined')
with tempfile.TemporaryDirectory() as d,patch('keystow.single_instance.paths.data_dir',return_value=d),patch.object(ui.autostart,'set_enabled'),patch.object(ui.autostart,'is_enabled',return_value=False):
 try:ui.run_app(Controller)
 except SystemExit as exc:assert exc.code==0
 assert calls==['shutdown','joined'],calls
 g=__import__('keystow.single_instance',fromlist=['InstanceGuard']).InstanceGuard(d)
 assert g.acquire(),'close left the instance lock owned'
 g.release()
'''
        r=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
