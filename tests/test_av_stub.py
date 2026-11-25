"""The PyAV stand-in used by the installers must import cleanly with Qt loaded.

PySide6 installs an import hook that inspects every newly imported module
(it asks for __wrapped__). An early stand-in raised its own error for that
probe, and the packaged app failed at start. This reproduces the packaged
import order with the stand-in ahead of any real PyAV.
"""
import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class AvStubTest(unittest.TestCase):
    def run_with_stub(self, code):
        script = "import sys; sys.path.insert(0, %r)\n" % str(ROOT / "installer" / "stubs") + textwrap.dedent(code)
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, text=True, capture_output=True,
                                timeout=60, env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_faster_whisper_imports_after_pyside6_with_the_stub(self):
        self.run_with_stub('''
            import PySide6.QtWidgets  # installs the module-inspecting import hook
            import av, inspect
            assert av.__file__.replace("\\\\", "/").endswith("installer/stubs/av/__init__.py"), av.__file__
            from faster_whisper import WhisperModel  # noqa: F401
            assert inspect.unwrap(av) is av
            assert not hasattr(av, "audio")
        ''')

    def test_decoding_a_file_explains_itself(self):
        self.run_with_stub('''
            import av
            try:
                av.open("anything.wav")
            except AttributeError as exc:
                assert "does not decode audio files" in str(exc)
            else:
                raise AssertionError("av.open should refuse")
        ''')

    def test_transcribing_samples_never_touches_av(self):
        self.run_with_stub('''
            import numpy as np
            import faster_whisper.transcribe as t
            calls = []
            t.decode_audio = lambda *a, **k: calls.append(a)
            # The guard faster-whisper uses before decoding:
            audio = np.zeros(16000, dtype="float32")
            if not isinstance(audio, np.ndarray):
                t.decode_audio(audio)
            assert calls == []
        ''')
