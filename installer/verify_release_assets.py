"""Compare a draft release's asset metadata with the two staged installers."""
import hashlib
import json
from pathlib import Path
import sys

NAMES = {'KeyStowSetup.exe', 'KeyStowMac.dmg'}


def verify(release, directory):
    if release.get('draft') is not True or release.get('tag_name') != 'v1.0.2':
        raise ValueError('Expected an unpublished v1.0.2 draft')
    assets = release.get('assets', [])
    if len(assets) != 2 or {a.get('name') for a in assets} != NAMES:
        raise ValueError('Expected exactly both platform installers')
    for asset in assets:
        data = (Path(directory) / asset['name']).read_bytes()
        digest = 'sha256:' + hashlib.sha256(data).hexdigest()
        if not data or asset.get('state') != 'uploaded' or asset.get('size') != len(data) or asset.get('digest') != digest:
            raise ValueError('Asset metadata mismatch: ' + asset['name'])


if __name__ == '__main__':
    verify(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
    print('Both draft installer names, sizes and SHA256 digests match staged files')
