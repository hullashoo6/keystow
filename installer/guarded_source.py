"""Isolated review candidate, not installed or wired into KeyStow."""
import ast
import hashlib
from pathlib import Path

HASHES = {
    'audio': '60a1d8638f718cbf6d245aed3e5a5aa61c1f822a0b0fe9b48a7c928d47c23909',
    'transcribe': '5d5ffb00018561d3d529b2c72e1d9f5fff055bea725f3cccc7c6c67f5cc8ffe4',
}

def guarded_audio_source(version, audio_bytes, transcribe_bytes):
    if version != '1.2.1':
        raise ValueError('Unsupported faster-whisper version; review required')
    for name, data in [('audio', audio_bytes), ('transcribe', transcribe_bytes)]:
        if hashlib.sha256(data).hexdigest() != HASHES[name]:
            raise ValueError(f'Unexpected faster-whisper {name} source; review required')
    source = audio_bytes.decode('utf-8')
    tree = ast.parse(source)
    imports = [n for n in tree.body if isinstance(n, ast.Import) and any(a.name == 'av' for a in n.names)]
    if len(imports) != 1 or len(imports[0].names) != 1:
        raise ValueError('Unexpected av import shape')
    targets = {'decode_audio', '_ignore_invalid_frames', '_group_frames'}
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in targets]
    if {n.name for n in functions} != targets:
        raise ValueError('Unexpected decoder function shape')
    lines = source.splitlines(keepends=True)
    edits = [(imports[0].lineno - 1, imports[0].end_lineno, '')]
    for fn in functions:
        first = fn.body[0]
        is_doc = isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str)
        at = first.end_lineno if is_doc else first.lineno - 1
        edits.append((at, at, '    import av\n'))
    for start, end, replacement in sorted(edits, reverse=True):
        lines[start:end] = [replacement] if replacement else []
    result = ''.join(lines)
    compile(result, '<guarded faster_whisper.audio>', 'exec')
    return result
