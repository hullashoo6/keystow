"""Isolated logging startup faults, no private log collection."""
import logging
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from keystow import crashlog


class CrashLogTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)
        self.before=list(logging.getLogger().handlers)
        self.level=logging.getLogger().level
        self.original_hooks=(sys.excepthook,threading.excepthook)
        self.patches=[patch.object(crashlog,'_handler',None,create=True),patch.object(crashlog,'_fault_file',None,create=True),patch.object(crashlog,'_LOG_DIR',str(self.home/'logs')),patch.object(crashlog.faulthandler,'enable')]
        for p in self.patches:p.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for h in list(logging.getLogger().handlers):
            if h not in self.before:logging.getLogger().removeHandler(h);h.close()
        if getattr(crashlog,'_fault_file',None):crashlog._fault_file.close()
        logging.getLogger().setLevel(self.level)
        sys.excepthook,threading.excepthook=self.original_hooks
        for p in reversed(self.patches):p.stop()

    def test_existing_file_in_log_directory_does_not_block_startup(self):
        target=self.home/'logs';target.write_text('existing unrelated file')
        self.assertIsNone(crashlog.setup())
        self.assertEqual(target.read_text(),'existing unrelated file')
        self.assertEqual(list(self.home.iterdir()),[target])
        target.unlink()
        self.assertIsNotNone(crashlog.setup())

    def test_unwritable_log_file_is_best_effort_without_new_destination(self):
        with patch.object(crashlog.logging.handlers,'RotatingFileHandler',side_effect=PermissionError('denied')):
            self.assertIsNone(crashlog.setup())
        self.assertIsNone(crashlog._handler)

    def test_repeated_setup_does_not_add_handlers_or_reopen_native_trace(self):
        first=crashlog.setup();handler=crashlog._handler;fault=crashlog._fault_file
        self.assertEqual(crashlog.setup(),first)
        self.assertIs(crashlog._handler,handler)
        self.assertIs(crashlog._fault_file,fault)
        crashlog.faulthandler.enable.assert_called_once()
        self.assertEqual(logging.getLogger().handlers.count(handler),1)

    def test_per_dictation_lines_from_the_speech_library_stay_out_of_the_log(self):
        speech=logging.getLogger('faster_whisper');before=speech.level
        self.addCleanup(speech.setLevel,before)
        result=crashlog.setup()
        speech.info('Processing audio with duration 00:02.834')
        speech.warning('synthetic speech-library warning')
        crashlog._handler.flush()
        written=Path(result).read_text()
        self.assertNotIn('Processing audio',written)
        self.assertIn('synthetic speech-library warning',written)

    def test_native_fault_trace_failure_preserves_ordinary_logging(self):
        crashlog.faulthandler.enable.side_effect=RuntimeError('not available')
        result=crashlog.setup()
        self.assertIsNotNone(result)
        self.assertIsNone(crashlog._fault_file)
        logging.warning('synthetic test diagnostic')
        crashlog._handler.flush()
        self.assertIn('synthetic test diagnostic',Path(result).read_text())
