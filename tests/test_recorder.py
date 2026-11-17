"""Stream ownership failure checks; PortAudio hardware is substituted."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch
import numpy as np


class RecorderCleanupTest(unittest.TestCase):
    def setUp(self):
        self.sd = types.SimpleNamespace(InputStream=Mock())
        spec = importlib.util.spec_from_file_location('keystow._recorder_check', Path(__file__).parents[1]/'keystow/recorder.py')
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'sounddevice':self.sd}):
            spec.loader.exec_module(self.module)
        self.recorder = self.module.PushToTalkRecorder()

    def test_failed_start_closes_stream_and_immediate_retry_works(self):
        bad, good = Mock(), Mock()
        bad.start.side_effect = RuntimeError('permission denied')
        self.sd.InputStream.side_effect = [bad,good]
        with self.assertRaises(RuntimeError):self.recorder.start()
        bad.close.assert_called_once()
        self.assertFalse(self.recorder.is_recording)
        self.assertIsNone(self.recorder._stream)
        self.recorder.start()
        self.assertTrue(self.recorder.is_recording)
        self.recorder.stop()
        good.close.assert_called_once()

    def test_failed_stop_still_closes_clears_audio_and_retries(self):
        bad,good = Mock(),Mock()
        bad.stop.side_effect = RuntimeError('device disconnected')
        self.sd.InputStream.side_effect = [bad,good]
        self.recorder.start()
        self.recorder._callback(np.ones((10,1),dtype=np.float32),10,None,None)
        with self.assertRaises(RuntimeError):self.recorder.stop()
        bad.close.assert_called_once()
        self.assertFalse(self.recorder.is_recording)
        self.assertEqual(self.recorder._frames,[])
        self.recorder.start(); self.recorder.stop()
        good.close.assert_called_once()

    def test_audio_delivered_once_then_discarded(self):
        stream=Mock();self.sd.InputStream.return_value=stream
        self.recorder.start();self.recorder.start()
        self.sd.InputStream.assert_called_once()
        self.recorder._callback(np.ones((10,1),dtype=np.float32),10,None,None)
        self.assertEqual(self.recorder.stop().tolist(),[1.0]*10)
        self.assertEqual(self.recorder.stop().size,0)
        stream.close.assert_called_once()
        self.assertEqual(self.recorder._frames,[])
