"""Candidate-only metadata and complete native architecture audit, before signing."""
from pathlib import Path
import plistlib
import subprocess
import sys

app = Path(sys.argv[1])
plist = app / 'Contents/Info.plist'
with plist.open('rb') as f:
    info = plistlib.load(f)
info.update(
    CFBundleIdentifier='com.keystow.app',
    CFBundleShortVersionString='1.0.6',
    CFBundleVersion='1.0.6',
    LSMinimumSystemVersion='14.0',
    NSMicrophoneUsageDescription='KeyStow listens while you hold your shortcut and turns your speech into text on this Mac. Audio is not saved or sent anywhere.',
)
with plist.open('wb') as f:
    plistlib.dump(info, f)
count = 0
for file in app.rglob('*'):
    if not file.is_file() or file.is_symlink():
        continue
    kind = subprocess.run(['file', '-b', str(file)], check=True, capture_output=True, text=True).stdout
    if 'Mach-O' not in kind:
        continue
    arches = set(subprocess.run(['lipo', '-archs', str(file)], check=True, capture_output=True, text=True).stdout.split())
    assert {'arm64', 'x86_64'} <= arches, f'Missing native slice: {file}: {arches}'
    count += 1
assert count > 10, f'Too few native files audited: {count}'
print(f'Audited {count} Mach-O files; each has arm64 and x86_64')
