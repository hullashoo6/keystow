"""Generate keystow.ico (Windows) and keystow.icns (Mac) from the soundwave glyph.

Run by CI before PyInstaller: python installer/make_icons.py
"""
import os

from PIL import Image, ImageDraw

BG = (18, 24, 38, 255)
G1 = (124, 140, 255)
G2 = (167, 139, 250)
HERE = os.path.dirname(os.path.abspath(__file__))


def gradient(size):
    g = Image.new("RGBA", (size, size))
    for x in range(size):
        t = x / max(size - 1, 1)
        g.paste(tuple(int(G1[i] + (G2[i] - G1[i]) * t) for i in range(3)) + (255,), (x, 0, x + 1, size))
    return g


def bars_mask(size):
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    hs = [int(h * size / 512) for h in (90, 160, 230, 280, 230, 160, 90)]
    bw, gap = int(34 * size / 512), int(22 * size / 512)
    x = (size - (len(hs) * bw + (len(hs) - 1) * gap)) // 2
    for hgt in hs:
        y0 = (size - hgt) // 2
        md.rounded_rectangle([x, y0, x + bw, y0 + hgt], radius=bw // 2, fill=255)
        x += bw + gap
    return mask


def main():
    size = 1024
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([size // 32, size // 32, size - size // 32, size - size // 32],
                        radius=int(size * 0.226), fill=BG)
    img.paste(gradient(size), (0, 0), bars_mask(size))
    img.save(os.path.join(HERE, "keystow.ico"),
             sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    img.save(os.path.join(HERE, "keystow.icns"),
             sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)])
    print("wrote keystow.ico + keystow.icns")


if __name__ == "__main__":
    main()
