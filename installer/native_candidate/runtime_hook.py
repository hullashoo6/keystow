"""Candidate-only diagnostics for the actual frozen application entrypoint.
No effect without explicit candidate flags. No network, publish or account tools.
"""
from pathlib import Path
import sys

if '--candidate-probe' in sys.argv or '--candidate-code-substitution' in sys.argv:
    from probe import check
    base=Path(sys._MEIPASS)
    check(base/'models/faster-whisper-base',base/'candidate-fixture/sample.npy',
          substitute='--candidate-code-substitution' in sys.argv)
    raise SystemExit(0)

if '--candidate-font-probe' in sys.argv:
    import json, os
    from PySide6 import QtGui
    app = QtGui.QGuiApplication([])
    font = app.font()
    info = QtGui.QFontInfo(font)
    raw = QtGui.QRawFont.fromFont(font)
    families = sorted(QtGui.QFontDatabase.families())
    ascii_chars = 'KeyStow Ready. Hold [Right Ctrl] anywhere to speak. 0123456789'
    requested_fonts = []
    for family in ('Segoe UI', 'Inter', 'sans-serif'):
        candidate_font = QtGui.QFont(family)
        candidate_info = QtGui.QFontInfo(candidate_font)
        candidate_raw = QtGui.QRawFont.fromFont(candidate_font)
        requested_fonts.append({'requested_family':family,
            'resolved_family':candidate_info.family(),
            'exact_match':candidate_info.exactMatch(),
            'raw_font_valid':candidate_raw.isValid(),
            'missing_ascii_characters':sorted(set(c for c in ascii_chars
                if not candidate_raw.supportsCharacter(ord(c))))})
    data = {
        'requested_style_fonts': requested_fonts,
        'mode': os.environ['CANDIDATE_FONT_MODE'],
        'platform': sys.platform, 'qt_platform': app.platformName(),
        'font_families': families, 'font_family_count': len(families),
        'default_requested_family': font.family(),
        'resolved_family': info.family(), 'resolved_style': info.styleName(),
        'exact_match': info.exactMatch(), 'raw_font_valid': raw.isValid(),
        'missing_ascii_characters': sorted(set(c for c in ascii_chars
             if not raw.supportsCharacter(ord(c)))),
        'qt_font_environment': {key:os.environ.get(key) for key in
             ('QT_QPA_PLATFORM','QT_QPA_FONTDIR','QT_FONT_DPI')},
        'application_font_changed': False,
        'visual_acceptance': False,
    }
    out = Path(os.environ['CANDIDATE_EVIDENCE_DIR'])
    (out/('font-probe-'+data['mode']+'.json')).write_text(
        json.dumps(data, indent=2), encoding='utf-8')
    print(json.dumps(data))
    raise SystemExit(0)

if '--candidate-ui-smoke' in sys.argv:
    import json,os,time
    from PySide6 import QtWidgets,QtCore
    real=QtWidgets.QApplication
    class ObservedApplication(real):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self._candidate_start=time.monotonic()
            self._candidate_observer=QtCore.QTimer(self)
            self._candidate_observer.setInterval(250)
            self._candidate_observer.timeout.connect(self._candidate_observe)
            self._candidate_observer.start()
        def _candidate_observe(self):
            out=Path(os.environ['CANDIDATE_EVIDENCE_DIR'])
            for window in self.topLevelWidgets():
                if window.windowTitle()!='KeyStow':continue
                labels=[x.text() for x in window.findChildren(QtWidgets.QLabel)]
                if any(x.startswith('Ready.') for x in labels):
                    self._candidate_observer.stop()
                    ok=window.grab().save(str(out/'ready-ui.png'))
                    (out/'ui-smoke.json').write_text(json.dumps({
                       'actual_entrypoint':True,'ready':True,'labels':labels,
                       'pixels_saved':ok,'keyboard_backend':os.environ.get('PYNPUT_BACKEND'),
                       'qt_platform':os.environ.get('QT_QPA_PLATFORM'),
                       'fresh_profile':True,'bundled_base_model':True,
                       'microphone_hotkey_paste_tray_login_acceptance':False},indent=2))
                    self.exit(0 if ok else 3);return
            if time.monotonic()-self._candidate_start>90:
                self._candidate_observer.stop()
                (out/'ui-smoke.json').write_text(json.dumps({'ready':False,'timeout_seconds':90}))
                self.exit(4)
    QtWidgets.QApplication=ObservedApplication
