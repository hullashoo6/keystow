"""Candidate-only Windows AMD64 PortAudio collection filter with audit records."""
from pathlib import Path
import hashlib
import struct

KEEP = {'libportaudio64bit.dll', 'libportaudio64bit-asio.dll'}
REMOVE = {'libportaudio.dylib', 'libportaudio32bit.dll',
          'libportaudio32bit-asio.dll', 'libportaudioarm64.dll',
          'libportaudioarm64-asio.dll'}


def filter_portaudio(dist, target_platform, machine, save):
    if target_platform != 'win32':
        save('portaudio-filter.json', {'applied': False,
             'reason': 'Only Windows AMD64 collection is selected for filtering'})
        return
    assert machine.lower() in ('amd64', 'x86_64'), 'Unsupported Windows target'
    folder = Path(dist)/'_internal/_sounddevice_data/portaudio-binaries'
    assert folder.is_dir(), 'Collected PortAudio directory missing'

    def manifest():
        entries = []
        for path in sorted(folder.rglob('*')):
            assert not path.is_symlink(), 'Unexpected PortAudio symlink'
            if path.is_file():
                data = path.read_bytes()
                entries.append({'path':path.relative_to(dist).as_posix(),
                    'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest(),
                    'magic_hex':data[:4].hex()})
        return entries

    before = manifest()
    save('portaudio-before.json', {'complete_directory_manifest':True,
         'platform':target_platform, 'machine':machine, 'files':before})
    libraries = {p.name for p in folder.glob('libportaudio*.*')}
    assert libraries == KEEP | REMOVE, 'Unexpected PortAudio library collection'
    assert all(p.parent == folder and p.name in KEEP | REMOVE | {'README.md'}
               for p in folder.rglob('*') if p.is_file()), 'Unknown PortAudio file'
    for name in sorted(KEEP):
        data = (folder/name).read_bytes()
        assert data[:2] == b'MZ' and len(data) >= 64, 'Expected PE library'
        offset = struct.unpack_from('<I', data, 60)[0]
        assert data[offset:offset+4] == b'PE\0\0', 'Invalid PE header'
        assert struct.unpack_from('<H', data, offset+4)[0] == 0x8664, 'Not AMD64'
    removed = []
    for entry in before:
        if Path(entry['path']).name in REMOVE:
            removed.append(dict(entry, reason='Not loaded by sounddevice 0.5.6 Windows AMD64 fallback',
                native_links_inspected=False))
    save('portaudio-filter.json', {'applied':True, 'sounddevice_version':'0.5.6',
         'kept_library_names':sorted(KEEP), 'removed':removed,
         'boundary':'Removal record is not a native-link audit of removed files'})
    for name in sorted(REMOVE):
        (folder/name).unlink()
    after = manifest()
    save('portaudio-after.json', {'complete_directory_manifest':True,
         'platform':target_platform, 'machine':machine, 'files':after})
    assert {p.name for p in folder.glob('libportaudio*.*')} == KEEP
    before_kept = [e for e in before if Path(e['path']).name not in REMOVE]
    assert after == before_kept, 'Unexpected retained-file modification'
