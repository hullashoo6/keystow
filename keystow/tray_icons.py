"""Window, tray and installer icons, all rendered from the website's logo.svg.

LOGO_SVG is the exact text of docs/assets/logo.svg (a test keeps them equal),
so the app, the installers and the website show the same mark. Nothing here
is redrawn by hand: variants only remove the background square (for the Mac
menu bar's monochrome template) or add a recording dot (listening).
"""

import re
import sys

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer

LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="16 16 480 480" role="img" aria-label="KeyStow">
<defs><linearGradient id="wave" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="512" y2="0"><stop offset="0" stop-color="#7c8cff"/><stop offset="1" stop-color="#a78bfa"/></linearGradient></defs>
<rect x="16" y="16" width="480" height="480" rx="116" fill="#ededf1"/>
<g fill="url(#wave)">
<rect x="71" y="211" width="34" height="90" rx="17"/>
<rect x="127" y="176" width="34" height="160" rx="17"/>
<rect x="183" y="141" width="34" height="230" rx="17"/>
<rect x="239" y="116" width="34" height="280" rx="17"/>
<rect x="295" y="141" width="34" height="230" rx="17"/>
<rect x="351" y="176" width="34" height="160" rx="17"/>
<rect x="407" y="211" width="34" height="90" rx="17"/>
</g>
</svg>
"""

# The recording dot: red is the convention, and the dot itself is the cue,
# so the state does not depend on colour alone.
DOT = QColor("#e5484d")


def _bars_only(svg: str, color: str) -> str:
    """The logo without its background square, bars in one flat colour."""
    svg = re.sub(r'<rect x="16" y="16"[^>]*/>\s*', "", svg)
    return svg.replace('fill="url(#wave)"', f'fill="{color}"')


def render(size: int, variant: str = "app") -> QImage:
    """variant: "app" (full logo), "listening" (logo + dot), "template" or
    "template-listening" (Mac menu bar: black bars, no square)."""
    svg = LOGO_SVG if not variant.startswith("template") else _bars_only(LOGO_SVG, "#000000")
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(painter, QRectF(0, 0, size, size))
    if variant.endswith("listening"):
        d = size * 0.42
        rect = QRectF(size - d - size * 0.02, size - d - size * 0.02, d, d)
        painter.setPen(QPen(QColor("#ffffff"), max(1.0, size * 0.06)))
        painter.setBrush(QColor("#000000") if variant.startswith("template") else DOT)
        painter.drawEllipse(rect)
    painter.end()
    return image


def _icon(variant: str, sizes=(16, 20, 24, 32, 40, 48, 64, 128, 256)) -> QIcon:
    icon = QIcon()
    for s in sizes:
        icon.addPixmap(QPixmap.fromImage(render(s, variant)))
    return icon


def icon(name: str, fallback=None) -> QIcon:
    """"app", "idle" or "listening". On a Mac the tray icons follow the menu bar."""
    try:
        if sys.platform == "darwin" and name in ("idle", "listening"):
            result = _icon("template" if name == "idle" else "template-listening", sizes=(18, 36))
            result.setIsMask(True)  # macOS tints template images for light/dark menu bars
            return result
        return _icon("listening" if name == "listening" else "app")
    except Exception:  # noqa: BLE001 - an icon must never stop the app starting
        return fallback() if fallback else QIcon()
