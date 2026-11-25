"""Gather the licences of the third-party software that ships in the installers.

Usage: python installer/collect_licenses.py <output folder> [--partial]

The release workflow runs this in the Python environment the app is built
from, before PyInstaller. It writes:

  <output>/THIRD-PARTY-NOTICES.txt   what is included, its licence and source
  <output>/LICENSE.txt               KeyStow's own licence
  <output>/texts/                    full texts of the common licences
  <output>/packages/<name>-<ver>/    the licence files each package carries

Every distribution installed in the build environment is listed, except the
tools that only build or check the installers. That errs towards listing
something that is not shipped, never the reverse. --partial skips the check
that the main libraries are present, for trying the script outside a build.
"""
import importlib.metadata as metadata
from pathlib import Path
import re
import shutil
import sys
import sysconfig

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# Used to make or check the installers; not put inside them.
BUILD_ONLY = {'pip', 'setuptools', 'wheel', 'pyinstaller', 'pyinstaller-hooks-contrib',
              'altgraph', 'macholib', 'pefile', 'pywin32-ctypes', 'pillow', 'psutil'}
# If one of these is missing the script is not running in the build environment.
# PyAV ("av") is removed before the build (installer/stubs/av replaces it), and
# Qt comes from PySide6-Essentials only.
EXPECTED = {'pyside6-essentials', 'pynput', 'faster-whisper', 'ctranslate2', 'numpy',
            'onnxruntime', 'sounddevice', 'pyperclip', 'tokenizers', 'huggingface-hub'}
LICENCE_FILE = re.compile(r'(licen[cs]e|copying|notice|authors|copyright)', re.IGNORECASE)


def normalise(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def licence_of(dist):
    meta = dist.metadata
    expression = meta.get('License-Expression')
    if expression:
        return expression
    classifiers = [c.split('::')[-1].strip() for c in meta.get_all('Classifier') or []
                   if c.startswith('License ::')]
    if classifiers:
        return '; '.join(dict.fromkeys(classifiers))
    declared = (meta.get('License') or '').strip()
    # Some packages put the whole licence text in this field.
    return declared.splitlines()[0][:80] if declared else 'see the package'


def source_of(dist):
    meta = dist.metadata
    urls = {}
    for entry in meta.get_all('Project-URL') or []:
        label, _, url = entry.partition(',')
        urls[label.strip().lower()] = url.strip()
    for label in ('source', 'source code', 'repository', 'homepage', 'home'):
        if urls.get(label):
            return urls[label]
    return (meta.get('Home-page') or next(iter(urls.values()), '')
            or f'https://pypi.org/project/{meta["Name"]}/')


def copy_licence_files(dist, target):
    """Copy the licence files a package carries in its metadata folder."""
    copied = 0
    for entry in dist.files or []:
        parts = entry.parts
        if len(parts) < 2 or not parts[0].endswith(('.dist-info', '.egg-info')):
            continue
        inside = parts[1:]
        if not (LICENCE_FILE.search(inside[-1]) or any(p.lower() in ('licenses', 'license_files') for p in inside[:-1])):
            continue
        source = Path(dist.locate_file(entry))
        if not source.is_file():
            continue
        destination = target.joinpath(*inside)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        copied += 1
    return copied


def python_licence():
    for candidate in (Path(sys.base_prefix) / 'LICENSE.txt',
                      Path(sysconfig.get_paths()['stdlib']) / 'LICENSE.txt'):
        if candidate.is_file():
            return candidate
    return None


def collect(output, partial=False):
    output = Path(output)
    if output.exists():
        shutil.rmtree(output)
    packages = output / 'packages'
    packages.mkdir(parents=True)
    shutil.copyfile(ROOT / 'LICENSE', output / 'LICENSE.txt')
    shutil.copytree(HERE / 'license-texts', output / 'texts')
    runtime = python_licence()
    if runtime:
        shutil.copyfile(runtime, output / 'texts' / 'Python-LICENSE.txt')
    (packages / 'pyrnnoise').mkdir()
    shutil.copyfile(ROOT / 'keystow' / 'vendor' / 'LICENSE.pyrnnoise', packages / 'pyrnnoise' / 'LICENSE.txt')

    rows, seen = [], set()
    for dist in sorted(metadata.distributions(), key=lambda d: normalise(d.metadata['Name'] or '')):
        name = dist.metadata['Name']
        key = normalise(name or '')
        if not name or key in BUILD_ONLY or key in seen:
            continue
        seen.add(key)
        folder = f'{key}-{dist.version}'
        carried = copy_licence_files(dist, packages / folder)
        rows.append((name, dist.version, licence_of(dist), source_of(dist), folder if carried else None))

    missing = EXPECTED - seen
    if missing and not partial:
        raise SystemExit('Not installed here, so the notices would be incomplete: ' + ', '.join(sorted(missing)))

    lines = [(HERE / 'third-party-notes.txt').read_text(encoding='utf-8').rstrip(), '',
             'Python packages in this build', '-----------------------------', '']
    for name, version, licence, source, folder in rows:
        lines += [f'{name} {version}', f'    Licence: {licence}', f'    Source:  {source}',
                  f'    Text:    packages/{folder}/' if folder
                  else '    Text:    not carried by the package; see its source and the texts folder', '']
    (output / 'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(lines), encoding='utf-8')
    with_text = sum(1 for row in rows if row[4])
    print(f'{len(rows)} packages listed, {with_text} with their own licence files, in {output}')
    return rows


if __name__ == '__main__':
    arguments = [a for a in sys.argv[1:] if a != '--partial']
    if len(arguments) != 1:
        raise SystemExit(__doc__)
    collect(arguments[0], partial='--partial' in sys.argv[1:])
