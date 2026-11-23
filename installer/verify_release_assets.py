"""Compare a draft release's asset metadata with the two staged installers.

Usage: python installer/verify_release_assets.py <releases json> <installer folder> <tag>

The release workflow uploads the installers to a draft release, asks GitHub
what it stored, and runs this before publishing. The JSON is either one
release or the list of releases; exactly one draft must carry the tag.
"""
import hashlib
import json
from pathlib import Path
import sys

NAMES = {'KeyStowSetup.exe', 'KeyStowMac.dmg'}


def select(releases, tag):
    drafts = [r for r in releases if r.get('draft') is True and r.get('tag_name') == tag]
    if len(drafts) != 1:
        raise ValueError(f'Expected one unpublished draft for {tag}, found {len(drafts)}')
    return drafts[0]


def verify(release, directory, tag):
    if release.get('draft') is not True or release.get('tag_name') != tag:
        raise ValueError(f'Expected an unpublished {tag} draft')
    assets = release.get('assets', [])
    if len(assets) != 2 or {a.get('name') for a in assets} != NAMES:
        raise ValueError('Expected exactly both platform installers')
    for asset in assets:
        data = (Path(directory) / asset['name']).read_bytes()
        digest = 'sha256:' + hashlib.sha256(data).hexdigest()
        if not data or asset.get('state') != 'uploaded' or asset.get('size') != len(data) or asset.get('digest') != digest:
            raise ValueError('Asset metadata mismatch: ' + asset['name'])


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    loaded = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    tag = sys.argv[3]
    verify(select(loaded, tag) if isinstance(loaded, list) else loaded, sys.argv[2], tag)
    print(f'Both {tag} draft installers match the built files in name, size and SHA-256')
