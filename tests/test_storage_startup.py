"""Actual subprocess/filesystem obstruction checks, without hardware claims."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


class StorageStartupTest(unittest.TestCase):
    def run_script(self, home, script):
        result = subprocess.run([sys.executable, '-c', textwrap.dedent(script)],
                                env=dict(os.environ, HOME=str(home), USERPROFILE=str(home), QT_QPA_PLATFORM='offscreen',
                                         PYTHONPATH=os.pathsep.join(p for p in sys.path if p)),
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_obstructed_directory_ui_and_repair_preserve_original(self):
        with tempfile.TemporaryDirectory() as home:
            obstruction = Path(home)/'.keystow'
            obstruction.write_text('original data: do not delete')
            self.run_script(home, '''
                from pathlib import Path
                import os
                from unittest.mock import patch
                from PySide6.QtWidgets import QApplication
                from keystow import paths, settings, stats, crashlog, ui
                p = Path.home()/'.keystow'
                assert paths.data_dir() == str(p)
                assert isinstance(paths.startup_storage_error(), OSError)
                assert crashlog.setup() is None
                app = QApplication([])
                with patch.object(ui.autostart, 'set_enabled'), patch.object(ui.autostart, 'is_enabled', return_value=False):
                    w = ui.MainWindow()
                w.show()
                w.show_transcript('fictional test transcript')
                w.set_state('Ready for the next dictation.')
                app.processEvents()
                assert w.transcript.text() == 'fictional test transcript'
                assert 'startup' in w.storage_warning.text()
                assert w.storage_warning.isVisible()
                assert 'unavailable' in w.stats_label.text()
                w.noise_box.setChecked(False)
                assert w.noise_box.isChecked()  # failed write must not show unsaved off
                assert 'Could not save' in w.storage_warning.text()
                assert p.read_text() == 'original data: do not delete'
                # User repairs the obstruction, not the application.
                p.rename(p.with_name('.keystow-preserved'))
                w.noise_box.setChecked(False)
                assert not w.noise_box.isChecked()
                assert settings.get('noise_suppression') is False
                settings.set('hotkey', 'shift_r')
                stats.add_words(4)
                assert settings.get('hotkey') == 'shift_r'
                assert stats.total() == 4
                assert paths.startup_storage_error() is not None
                w.tray.hide(); w.hide()
            ''')
            self.assertEqual(Path(home, '.keystow-preserved').read_text(), 'original data: do not delete')
            self.run_script(home, '''
                from keystow import paths, settings, stats
                assert paths.startup_storage_error() is None
                assert settings.get('hotkey') == 'shift_r'
                assert stats.total() == 4
            ''')

    def test_permission_failure_during_initialization_is_not_redirected(self):
        with tempfile.TemporaryDirectory() as home:
            self.run_script(home, '''
                import os
                from unittest.mock import patch
                with patch('os.makedirs', side_effect=PermissionError('injected permission denial')):
                    from keystow import paths, settings, stats, crashlog
                assert paths.data_dir() == os.path.join(os.path.expanduser('~'), '.keystow')
                assert isinstance(paths.startup_storage_error(), PermissionError)
                assert settings.get('hotkey', 'ctrl_r') == 'ctrl_r'
            ''')

    def test_normal_writable_startup_has_no_storage_warning(self):
        with tempfile.TemporaryDirectory() as home:
            self.run_script(home, '''
                from unittest.mock import patch
                from PySide6.QtWidgets import QApplication
                from keystow import paths, ui
                app = QApplication([])
                with patch.object(ui.autostart, 'set_enabled'), patch.object(ui.autostart, 'is_enabled', return_value=False):
                    w = ui.MainWindow()
                assert paths.startup_storage_error() is None
                assert not w.storage_warning.text()
                assert '0 words today' in w.stats_label.text()
                w.tray.hide()
            ''')

    def test_autostart_failure_is_visible_and_retry_succeeds(self):
        with tempfile.TemporaryDirectory() as home:
            self.run_script(home, '''
                from unittest.mock import patch
                from PySide6.QtWidgets import QApplication
                from keystow import ui
                app = QApplication([])
                with patch.object(ui.autostart, 'set_enabled'), patch.object(ui.autostart, 'is_enabled', return_value=False):
                    w = ui.MainWindow()
                # The installed app: from source, enabling is refused outright.
                with patch.object(ui.autostart, 'available', return_value=True), \
                     patch.object(ui.autostart, 'set_enabled', side_effect=OSError('registration denied')):
                    w.autostart_action.setChecked(True)
                    w._toggle_autostart(True)
                app.processEvents()
                assert not w.autostart_action.isChecked()
                assert 'Could not change' in w.status.text()
                with patch.object(ui.autostart, 'available', return_value=True), \
                     patch.object(ui.autostart, 'set_enabled') as write:
                    w.autostart_action.setChecked(True)
                    w._toggle_autostart(True)
                    write.assert_called_once_with(True)
                assert w.autostart_action.isChecked()
                w.tray.hide()
            ''')
