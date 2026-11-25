"""Generate keystow.ico (Windows) and keystow.icns (Mac) from the website logo.

Run by CI before PyInstaller: python installer/make_icons.py
The pixels come from keystow/tray_icons.py, which renders docs/assets/logo.svg,
so the installer, the app and the website show exactly the same mark.
"""
import io
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from keystow.tray_icons import render  # noqa: E402

ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)  # 125%/150% scaling uses 20/24/40
ICNS_SIZES = (16, 32, 64, 128, 256, 512, 1024)


def pil(size: int) -> Image.Image:
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    render(size, "app").save(buffer, "PNG")
    return Image.open(io.BytesIO(bytes(buffer.data()))).convert("RGBA")


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841
    images = {s: pil(s) for s in sorted(set(ICO_SIZES) | set(ICNS_SIZES))}
    # Each size rendered on its own (not scaled down from 1024) so small
    # icons stay crisp.
    images[256].save(os.path.join(HERE, "keystow.ico"), sizes=[(s, s) for s in ICO_SIZES],
                     append_images=[images[s] for s in ICO_SIZES if s != 256])
    images[1024].save(os.path.join(HERE, "keystow.icns"),
                      append_images=[images[s] for s in ICNS_SIZES if s != 1024])
    images[256].save(os.path.join(HERE, "keystow-256.png"))
    print("wrote keystow.ico, keystow.icns and keystow-256.png from logo.svg")


if __name__ == "__main__":
    main()
