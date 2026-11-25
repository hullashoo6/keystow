"""The app shows the website's mark and type, and the icons render."""
import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


def normalised(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").strip().splitlines())


class BrandTest(unittest.TestCase):
    def test_embedded_logo_is_the_website_logo(self):
        source = (ROOT / "keystow" / "tray_icons.py").read_text(encoding="utf-8")
        start = source.index('LOGO_SVG = """') + len('LOGO_SVG = """')
        embedded = source[start:source.index('"""', start)]
        site = (ROOT / "docs" / "assets" / "logo.svg").read_text(encoding="utf-8")
        self.assertEqual(normalised(embedded), normalised(site))

    def test_font_ships_with_its_licence(self):
        fonts = ROOT / "keystow" / "fonts"
        self.assertTrue((fonts / "InstrumentSans-Variable.ttf").is_file())
        self.assertIn("SIL Open Font License", (fonts / "OFL.txt").read_text(encoding="utf-8"))

    def test_icons_and_font_load_in_qt(self):
        script = textwrap.dedent('''
            from PySide6.QtWidgets import QApplication
            from PySide6.QtGui import QFontDatabase
            from keystow import tray_icons, ui
            app = QApplication([])
            assert ui._load_brand_font()
            assert "Instrument Sans" in QFontDatabase.families()
            for variant in ("app", "listening", "template", "template-listening"):
                image = tray_icons.render(32, variant)
                assert not image.isNull()
                # Something was drawn: not a blank transparent square.
                assert any(image.pixelColor(x, 16).alpha() for x in range(32)), variant
            # Listening differs from idle by its shape (the dot), not only colour.
            idle, listening = tray_icons.render(32, "app"), tray_icons.render(32, "listening")
            assert idle.pixelColor(26, 26) != listening.pixelColor(26, 26)
            for name in ("app", "idle", "listening"):
                assert not tray_icons.icon(name).isNull()
        ''')
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, text=True,
                                capture_output=True, timeout=30,
                                env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
