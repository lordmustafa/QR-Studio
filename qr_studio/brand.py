"""The QR Studio logo, drawn in code so every size stays sharp.

A rounded square in the app's accent blue with a simple white QR mark:
three rounded corner "eyes" and four rounded dots. The same drawing is used
for the sidebar, the window icon and the Windows / macOS app icons.
"""

from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

ACCENT_TOP = "#3b82f6"  # matches the UI accent (dark mode)
ACCENT_BOTTOM = "#1d4ed8"  # matches the UI accent hover
MARK = (255, 255, 255, 255)
_SS = 4  # draw 4x larger, then scale down for smooth edges


def _gradient(size: int) -> Image.Image:
    """Diagonal gradient, lighter at the top-left."""
    v = Image.linear_gradient("L")
    h = v.transpose(Image.Transpose.ROTATE_90)
    diagonal = ImageChops.add(v, h, scale=2.0).resize((size, size), Image.Resampling.BILINEAR)
    return ImageOps.colorize(diagonal, ACCENT_TOP, ACCENT_BOTTOM).convert("RGBA")


def _mark(draw: ImageDraw.ImageDraw, x0: float, y0: float, g: float) -> None:
    """White QR mark inside the square (x0, y0, g x g)."""
    eye = g * 0.40  # outer size of a corner eye
    ring = eye * 0.17  # ring thickness
    dot = eye * 0.40  # centre of an eye
    gap = g - 2 * eye  # space between eyes

    def eye_at(x: float, y: float) -> None:
        draw.rounded_rectangle([x, y, x + eye, y + eye], radius=eye * 0.32, fill=MARK)
        inner = ring
        draw.rounded_rectangle([x + inner, y + inner, x + eye - inner, y + eye - inner],
                               radius=eye * 0.20, fill=(0, 0, 0, 0))
        off = (eye - dot) / 2
        draw.rounded_rectangle([x + off, y + off, x + off + dot, y + off + dot], radius=dot * 0.32, fill=MARK)

    eye_at(x0, y0)
    eye_at(x0 + eye + gap, y0)
    eye_at(x0, y0 + eye + gap)

    # four data dots in the free corner, in the same rhythm as the eyes
    cell = eye / 2
    d = cell * 0.70
    bx, by = x0 + eye + gap, y0 + eye + gap
    for cx in (0, 1):
        for cy in (0, 1):
            px = bx + cx * cell + (cell - d) / 2
            py = by + cy * cell + (cell - d) / 2
            draw.rounded_rectangle([px, py, px + d, py + d], radius=d * 0.34, fill=MARK)


@lru_cache(maxsize=16)
def logo(size: int = 512, margin: float = 0.0, shadow: bool = False) -> Image.Image:
    """The logo as an RGBA image of ``size`` px.

    ``margin`` leaves empty space around the tile (macOS icons use about 0.09);
    ``shadow`` adds a soft shadow under the tile, like other macOS app icons.
    """
    big = size * _SS
    pad = int(big * margin)
    tile = big - 2 * pad
    radius = int(tile * 0.27)

    canvas = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        offset = int(tile * 0.025)
        ImageDraw.Draw(sh).rounded_rectangle([pad, pad + offset, pad + tile, pad + tile + offset],
                                             radius=radius, fill=(0, 0, 0, 90))
        canvas = sh.filter(ImageFilter.GaussianBlur(tile * 0.03))

    mask = Image.new("L", (tile, tile), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, tile - 1, tile - 1], radius=radius, fill=255)
    canvas.paste(_gradient(tile), (pad, pad), mask)

    # soft light on the top half gives the tile a little depth
    shine = Image.new("RGBA", (tile, tile), (255, 255, 255, 0))
    fade = Image.linear_gradient("L").resize((tile, tile)).point(lambda v: int(max(0, 128 - v) * 0.22))
    shine.putalpha(Image.composite(fade, Image.new("L", (tile, tile), 0), mask))
    canvas.alpha_composite(shine, (pad, pad))

    # The mark is drawn on its own layer so the holes in the eyes show the blue tile.
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    g = tile * 0.54
    _mark(ImageDraw.Draw(layer), pad + (tile - g) / 2, pad + (tile - g) / 2, g)
    canvas.alpha_composite(layer)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)
