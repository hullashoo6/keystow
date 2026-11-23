"""Fail-closed release gates: asset metadata, release notes, version details.

No GitHub call and nothing published.
"""
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / 'installer'


def load(name):
    spec = importlib.util.spec_from_file_location(name, INSTALLER / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load('verify_release_assets')
notes = load('release_notes')
version_file = load('make_version_file')


class ReleaseGateTest(unittest.TestCase):
    def test_only_exact_uploaded_draft_pair_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            assets = []
            for name in sorted(gate.NAMES):
                data = name.encode()
                (Path(directory) / name).write_bytes(data)
                assets.append({'name':name, 'size':len(data), 'digest':'sha256:' + hashlib.sha256(data).hexdigest(), 'state':'uploaded'})
            good = {'tag_name':'v1.0.7','draft':True,'assets':assets}
            gate.verify(good, directory, 'v1.0.7')
            bad_cases = []
            for field, value in [('draft',False),('tag_name','v1.0.6'),('assets',assets[:1]),('assets',assets+assets[:1])]:
                bad = copy.deepcopy(good);bad[field]=value;bad_cases.append(bad)
            for field,value in [('size',0),('digest','sha256:wrong'),('state','starter'),('name','other.exe')]:
                bad=copy.deepcopy(good);bad['assets'][0][field]=value;bad_cases.append(bad)
            for bad in bad_cases:
                with self.assertRaises(ValueError):gate.verify(bad,directory,'v1.0.7')

    def test_exactly_one_draft_must_carry_the_tag(self):
        draft = {'tag_name':'v1.0.7','draft':True}
        published = {'tag_name':'v1.0.7','draft':False}
        other = {'tag_name':'v1.0.6','draft':True}
        self.assertIs(gate.select([published, other, draft], 'v1.0.7'), draft)
        for releases in ([], [published], [other], [draft, dict(draft)]):
            with self.assertRaises(ValueError):gate.select(releases, 'v1.0.7')


class ReleaseNotesTest(unittest.TestCase):
    TEXT = '# Changelog\n\nIntro.\n\n## v1.0.7\n\nNewest notes.\n\n- one\n\n## v1.0.6 - 2026-11-22\n\nOlder notes.\n\n## v1.0.5\n\n'

    def test_each_version_gets_only_its_own_section(self):
        self.assertEqual(notes.section(self.TEXT, '1.0.7'), 'Newest notes.\n\n- one')
        self.assertEqual(notes.section(self.TEXT, '1.0.6'), 'Older notes.')

    def test_missing_or_empty_sections_are_not_notes(self):
        self.assertIsNone(notes.section(self.TEXT, '1.0.8'))
        self.assertIsNone(notes.section(self.TEXT, '1.0'))
        self.assertEqual(notes.section(self.TEXT, '1.0.5'), '')

    def test_the_real_changelog_has_notes_for_the_version_in_the_source(self):
        root = INSTALLER.parent
        init = (root / 'keystow' / '__init__.py').read_text(encoding='utf-8')
        version = init.split('__version__ = "')[1].split('"')[0]
        text = (root / 'CHANGELOG.md').read_text(encoding='utf-8')
        self.assertTrue(notes.section(text, version), f'CHANGELOG.md has no notes for v{version}')


class VersionFileTest(unittest.TestCase):
    def test_version_lands_in_both_number_and_text_fields(self):
        text = version_file.render('1.0.7')
        self.assertEqual(text.count('(1, 0, 7, 0)'), 2)
        self.assertIn("StringStruct('FileVersion', '1.0.7')", text)
        self.assertIn("StringStruct('ProductVersion', '1.0.7')", text)

    def test_anything_but_three_numbers_is_refused(self):
        for bad in ('1.0', 'v1.0.7', '1.0.7-beta', ''):
            with self.assertRaises(ValueError):version_file.render(bad)
