"""Draw the pictures used by the README and the GitHub Pages site.

Every QR code here is made by QR Studio's own renderer and points to the
project page, so the pictures also work as real, scannable examples.

    python packaging/make_docs_images.py

Writes into docs/assets/.
"""

from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from qr_studio.brand import logo  # noqa: E402
from qr_studio.renderer import QRStyle, render  # noqa: E402
from qr_studio.ui.create_page import PRESETS  # noqa: E402

OUT = os.path.join(ROOT, "docs", "assets")
URL = "https://github.com/lordmustafa/QR-Studio"

BOLD_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
REGULAR_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

INK = (17, 24, 39)
MUTED = (75, 85, 99)
PAGE = (248, 250, 252)
CARD = (255, 255, 255)
LINE = (226, 232, 240)


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for path in BOLD_FONTS if bold else REGULAR_FONTS:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def qr(style: dict, size: int, payload: str = URL) -> Image.Image:
    img = render(payload, QRStyle(**style), size=size).image.convert("RGBA")
    return img


def centered(draw: ImageDraw.ImageDraw, cx: float, y: float, text: str, fnt, fill) -> None:
    w = draw.textlength(text, font=fnt)
    draw.text((cx - w / 2, y), text, font=fnt, fill=fill)


def styles_gallery(logo_file: str) -> Image.Image:
    """The six quick styles plus a code with a logo and a caption."""
    items = [(name, dict(border=2, **PRESETS[name])) for name in PRESETS]
    items.append(("With logo", dict(border=2, **PRESETS["Ocean"], logo_path=logo_file, logo_scale=0.24)))
    items.append(("Caption & frame", dict(border=2, **PRESETS["Classic"], caption="Scan me",
                                          caption_color="#ffffff", frame=True, frame_color="#1d4ed8")))
    cols, cell, pad, label_h = 4, 300, 28, 46
    rows = (len(items) + cols - 1) // cols
    w = cols * cell + (cols + 1) * pad
    h = rows * (cell + label_h) + (rows + 1) * pad
    page = Image.new("RGBA", (w, h), PAGE + (255,))
    draw = ImageDraw.Draw(page)
    label = font(24, bold=True)
    for i, (name, style) in enumerate(items):
        r, c = divmod(i, cols)
        x = pad + c * (cell + pad)
        y = pad + r * (cell + label_h + pad)
        draw.rounded_rectangle([x, y, x + cell, y + cell + label_h], radius=22, fill=CARD, outline=LINE, width=2)
        code = qr(style, cell - 40)
        code.thumbnail((cell - 40, cell - 40), Image.Resampling.LANCZOS)
        page.alpha_composite(code, (x + (cell - code.width) // 2, y + 20 + (cell - 40 - code.height) // 2))
        centered(draw, x + cell / 2, y + cell + 4, name, label, INK)
    return page


def banner(width: int, height: int, title_size: int) -> Image.Image:
    """Wide picture with the logo, the name, a short tagline and a sample code."""
    page = Image.new("RGBA", (width, height), PAGE + (255,))
    draw = ImageDraw.Draw(page)
    s = height / 640
    mark = logo(int(150 * s))
    left = int(80 * s)
    page.alpha_composite(mark, (left, int(110 * s)))
    top = int(285 * s)
    draw.text((left, top), "QR Studio", font=font(title_size, bold=True), fill=INK)
    tag = font(int(40 * s))
    y = top + title_size + int(22 * s)
    for line in ("Free QR code generator", "for Windows and macOS"):
        draw.text((left, y), line, font=tag, fill=MUTED)
        y += int(50 * s)
    draw.text((left, y + int(14 * s)), "Offline · no ads · no sign-up", font=font(int(28 * s)), fill=(37, 99, 235))

    side = int(400 * s)
    x0 = width - side - int(80 * s)
    y0 = (height - side) // 2
    draw.rounded_rectangle([x0 - 24 * s, y0 - 24 * s, x0 + side + 24 * s, y0 + side + 24 * s],
                           radius=int(36 * s), fill=CARD, outline=LINE, width=2)
    code = qr(dict(border=2, **PRESETS["Ocean"]), side)
    code.thumbnail((side, side), Image.Resampling.LANCZOS)
    page.alpha_composite(code, (x0, y0))
    return page


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        logo_file = os.path.join(tmp, "logo.png")
        logo(512).save(logo_file)
        styles_gallery(logo_file).convert("RGB").save(os.path.join(OUT, "styles.png"), optimize=True)
        hero = qr(dict(border=2, **PRESETS["Ocean"], logo_path=logo_file, logo_scale=0.24), 720)
        hero.thumbnail((720, 720), Image.Resampling.LANCZOS)
        hero.convert("RGB").save(os.path.join(OUT, "hero.png"), optimize=True)
    logo(256).save(os.path.join(OUT, "logo.png"), optimize=True)
    logo(64).save(os.path.join(OUT, "favicon.png"), optimize=True)
    banner(1280, 640, 96).convert("RGB").save(os.path.join(OUT, "social-preview.png"), optimize=True)
    for name in ("styles.png", "hero.png", "logo.png", "favicon.png", "social-preview.png"):
        path = os.path.join(OUT, name)
        print(f"{name}: {Image.open(path).size}, {os.path.getsize(path) // 1024} KB")


if __name__ == "__main__":
    main()
