"""Write the Windows version details that go into KeyStow.exe.

Usage: python installer/make_version_file.py <version> <output file>

PyInstaller reads the file with --version-file. Without it KeyStow.exe shows
no version, product or publisher in its Properties or in Task Manager.
"""
from pathlib import Path
import re
import sys

TEMPLATE = """\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({numbers}),
    prodvers=({numbers}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'KeyStow'),
        StringStruct('FileDescription', 'KeyStow'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'KeyStow'),
        StringStruct('LegalCopyright', 'Copyright (c) 2026 hullashoo6. MIT licence.'),
        StringStruct('OriginalFilename', 'KeyStow.exe'),
        StringStruct('ProductName', 'KeyStow'),
        StringStruct('ProductVersion', '{version}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def render(version):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError(f'Version must look like 1.0.7, not {version!r}')
    numbers = ', '.join(version.split('.') + ['0'])
    return TEMPLATE.format(numbers=numbers, version=version)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    Path(sys.argv[2]).write_text(render(sys.argv[1]), encoding='utf-8')
    print(f'Wrote version details for {sys.argv[1]} to {sys.argv[2]}')
