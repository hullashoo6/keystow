"""Print the CHANGELOG.md section for one version.

Usage: python installer/release_notes.py <version> [<changelog file>]

The release workflow publishes that section as the release's notes, so the
changelog is the one place release notes are written. Fails if the version has
no section, or an empty one.
"""
from pathlib import Path
import re
import sys

HEADING = re.compile(r'^## v(\d+\.\d+\.\d+)\b.*$', re.MULTILINE)


def section(text, version):
    """The text under the "## v<version>" heading, or None if there is none."""
    headings = list(HEADING.finditer(text))
    for index, heading in enumerate(headings):
        if heading.group(1) == version:
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            return text[heading.end():end].strip()
    return None


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    changelog = Path(sys.argv[2]) if len(sys.argv) == 3 else Path(__file__).resolve().parents[1] / 'CHANGELOG.md'
    notes = section(changelog.read_text(encoding='utf-8'), sys.argv[1])
    if not notes:
        raise SystemExit(f'{changelog.name} has no notes under a "## v{sys.argv[1]}" heading')
    sys.stdout.reconfigure(encoding='utf-8')
    print(notes)
