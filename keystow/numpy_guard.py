"""Local-only pre-import guard for a build-time-adapted dependency.

Does not patch, install, or import faster_whisper. Packaging must supply the
reviewed source before this module runs. A mismatch prevents startup.
"""
import hashlib
import importlib.util
import importlib.machinery
import sys
from pathlib import Path
import numpy as np


# These reviewed digests are part of guarded application code, not supplied by
# an independently replaceable adjacent manifest. This is an integrity check,
# not authentication against replacement of the whole executable.
_REVIEWED_SOURCES = {
    'audio.py': '7c07f715830e044386e75b1303851dbe6e0715f1302593bcc061f3a8876a1ae7',
    'transcribe.py': '5d5ffb00018561d3d529b2c72e1d9f5fff055bea725f3cccc7c6c67f5cc8ffe4',
}


def verify_dependency():
    if any(n == 'faster_whisper' or n.startswith('faster_whisper.') for n in sys.modules):
        raise RuntimeError('faster_whisper loaded before KeyStow guard')
    spec = importlib.util.find_spec('faster_whisper')
    if spec is None or not spec.submodule_search_locations:
        raise RuntimeError('Reviewed faster-whisper source is unavailable')
    roots = list(spec.submodule_search_locations)
    if len(roots) != 1:
        raise RuntimeError('Ambiguous faster-whisper package source')
    root = Path(roots[0])
    for name, digest in _REVIEWED_SOURCES.items():
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Unreviewed faster-whisper source: ' + name)
        if getattr(sys, 'frozen', False):
            module_name = 'faster_whisper.' + path.stem
            module_spec = importlib.machinery.PathFinder.find_spec(module_name, roots)
            if module_spec is None or not hasattr(module_spec.loader, 'get_code'):
                raise RuntimeError('Unsupported frozen dependency loader: ' + name)
            actual = module_spec.loader.get_code(module_name)
            if actual is None:
                raise RuntimeError('Missing frozen dependency code: ' + name)
            reviewed = compile(path.read_bytes(), actual.co_filename, 'exec',
                               dont_inherit=True, optimize=sys.flags.optimize)
            # Compare code objects, not marshal byte streams. Marshal reference
            # bookkeeping differs even when recursive code objects are equal.
            if actual != reviewed:
                raise RuntimeError('Unreviewed frozen dependency code: ' + name)
    return root


def validate_waveform(audio):
    if not isinstance(audio, np.ndarray):
        raise TypeError('KeyStow supports microphone NumPy waveforms only, not files or streams')
    if audio.ndim != 1 or audio.dtype != np.float32:
        raise ValueError('Expected a mono float32 NumPy waveform')
    if not np.isfinite(audio).all():
        raise ValueError('Waveform contains non-finite samples')
    return audio
