"""Review-only metadata contract. Never installs, builds or edits a distribution."""
import hashlib
import json
from collections import Counter
from email.parser import Parser
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

UPSTREAM = {
    'audio.py': '60a1d8638f718cbf6d245aed3e5a5aa61c1f822a0b0fe9b48a7c928d47c23909',
    'transcribe.py': '5d5ffb00018561d3d529b2c72e1d9f5fff055bea725f3cccc7c6c67f5cc8ffe4',
}
ADAPTED = dict(UPSTREAM, **{'audio.py': '7c07f715830e044386e75b1303851dbe6e0715f1302593bcc061f3a8876a1ae7'})
BOUNDARY = {
    'application_input': 'finite mono float32 NumPy waveform only',
    'dependency_file_decode': 'requires unavailable PyAV; unsupported by application',
    'installable': False,
    'frozen_verified': False,
}

def parse(text):
    msg = Parser().parsestr(text)
    for field in ('Metadata-Version', 'Name', 'Version', 'Requires-Python'):
        if len(msg.get_all(field, [])) != 1 or not msg[field].strip():
            raise ValueError('Missing or duplicate metadata field: ' + field)
    if canonicalize_name(msg['Name']) != 'faster-whisper' or msg['Version'] != '1.2.1':
        raise ValueError('Unexpected dependency identity')
    requirements = msg.get_all('Requires-Dist', [])
    if not requirements:
        raise ValueError('Missing requirements')
    keys = []
    for line in requirements:
        req = Requirement(line)
        keys.append((canonicalize_name(req.name), str(req.marker)))
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate requirement')
    return msg, requirements

def verify_sources(root, expected):
    for name, digest in expected.items():
        path = Path(root) / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Source hash mismatch: ' + name)

def reconcile(pristine_text, proposed_text, pristine_root, adapted_root, boundary):
    old, old_reqs = parse(pristine_text)
    new, new_reqs = parse(proposed_text)
    removed = [r for r in old_reqs if canonicalize_name(Requirement(r).name) == 'av']
    if removed != ['av>=11']:
        raise ValueError('Unexpected upstream PyAV requirement')
    if any(canonicalize_name(Requirement(r).name) == 'av' for r in new_reqs):
        raise ValueError('Adapted metadata still requires PyAV')
    if Counter(new_reqs) != Counter(r for r in old_reqs if r not in removed):
        raise ValueError('Non-PyAV requirement changed')
    # Preserve all nondependency metadata, not only Python compatibility.
    headers = lambda m: Counter((k.lower(), v) for k, v in m.items() if k.lower() != 'requires-dist')
    if headers(old) != headers(new) or old.get_payload() != new.get_payload():
        raise ValueError('Nondependency metadata changed')
    verify_sources(pristine_root, UPSTREAM)
    verify_sources(adapted_root, ADAPTED)
    if boundary != BOUNDARY:
        raise ValueError('Support boundary mismatch')
    return {
        'result': 'review-only metadata consistency PASS',
        'identity': 'faster-whisper 1.2.1',
        'removed_requirement': removed,
        'preserved_requirements': new_reqs,
        'requires_python': new['Requires-Python'],
        'source_hashes_verified': {'pristine': UPSTREAM, 'adapted': ADAPTED},
        'support_boundary': boundary,
        'distribution_modified': False,
        'installable_distribution_proven': False,
        'target_resolution_proven': False,
        'frozen_loader_proven': False,
        'native_absence_proven': False,
        'legal_clearance_proven': False,
        'hardware_acceptance_proven': False,
    }
