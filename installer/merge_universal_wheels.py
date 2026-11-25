"""Prepare universal wheels from the two native, pinned wheel sets. macOS only."""
import argparse
import pathlib
import subprocess
from packaging.utils import parse_wheel_filename

p = argparse.ArgumentParser()
p.add_argument('arm'); p.add_argument('intel'); p.add_argument('output')
a = p.parse_args()

def index(folder):
    result = {}
    for path in pathlib.Path(folder).rglob('*.whl'):
        name, version, _, tags = parse_wheel_filename(path.name)
        key = (name, str(version))
        if key in result:
            raise RuntimeError(f'Duplicate wheel: {key}')
        result[key] = (path, tags)
    return result

arm, intel = index(a.arm), index(a.intel)
assert arm.keys() == intel.keys(), f'Package sets differ: {arm.keys() ^ intel.keys()}'
out = pathlib.Path(a.output); out.mkdir(parents=True, exist_ok=True)
for key in sorted(arm):
    ap, at = arm[key]; xp, xt = intel[key]
    pure = all(t.platform == 'any' for t in at)
    universal = all(t.platform.endswith('_universal2') for t in at)
    if pure or universal:
        import shutil
        # Matching pure/universal wheels should be byte-identical downloads.
        assert ap.read_bytes() == xp.read_bytes(), f'Different shared wheel: {key}'
        shutil.copy2(ap, out / ap.name)
    else:
        subprocess.run(['delocate-merge', str(ap), str(xp), '-w', str(out)], check=True)
print(f'Prepared {len(arm)} universal/pure wheels')
