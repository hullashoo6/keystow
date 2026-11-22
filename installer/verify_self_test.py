"""Run the packaged app's own check and require real speech recognition.

Usage: python installer/verify_self_test.py <packaged executable> <evidence dir>

The app is started with --self-test: no window, microphone, shortcut or network.
It must load the speech model that ships inside the package, turn silence into
no text, and transcribe the public-domain speech sample kept next to this file.
This is packaged-app evidence, not a real microphone or shortcut test.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

exe = Path(sys.argv[1]).resolve()
evidence = Path(sys.argv[2])
evidence.mkdir(parents=True, exist_ok=True)
sample = Path(__file__).resolve().parent / 'selftest' / 'jfk.flac'
report_path = (evidence / 'self-test.json').resolve()
if report_path.exists():
    report_path.unlink()

with tempfile.TemporaryDirectory() as home:
    # A private home keeps settings out of the picture, and the offline switch
    # means a missing bundled model fails here instead of quietly downloading.
    env = dict(os.environ, HOME=home, USERPROFILE=home, HF_HUB_OFFLINE='1')
    for name in ('KEYSTOW_MODEL', 'KEYSTOW_LANGUAGE', 'KEYSTOW_DEVICE', 'KEYSTOW_COMPUTE_TYPE'):
        env.pop(name, None)
    result = subprocess.run(
        [str(exe), '--self-test', f'--self-test-audio={sample}', f'--self-test-out={report_path}'],
        env=env, timeout=600)

report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
print(json.dumps(report, indent=2))
assert result.returncode == 0, f'self-test exit code {result.returncode}: {report.get("error")}'
assert report.get('ok') is True, report
assert report.get('frozen') is True, 'this must be run against the packaged app'
assert report.get('model_bundled') is True, report
assert report.get('silence_text') == '', report
speech = report.get('speech_text', '').lower()
assert 'ask' in speech and 'country' in speech, f'unexpected transcript: {speech!r}'
print('The packaged app loaded its own model and transcribed the speech sample.')
