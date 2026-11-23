"""QR code rendering: turns a payload and a ``QRStyle`` into a Pillow image.

The QR matrix comes from the ``qrcode`` package; drawing is done here so we
control module shapes, finder ("eye") shapes, gradients, logos and frames.
Shapes are drawn on a supersampled canvas and scaled down, which gives smooth
anti-aliased edges.
"""

from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass, fields, replace
from functools import lru_cache

import qrcode
from qrcode.exceptions import DataOverflowError
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFont, ImageOps, features

ECC_LEVELS = {
    "L": qrcode.constants.ERROR_CORRECT_L,
    "M": qrcode.constants.ERROR_CORRECT_M,
    "Q": qrcode.constants.ERROR_CORRECT_Q,
    "H": qrcode.constants.ERROR_CORRECT_H,
}
MODULE_STYLES = ("square", "rounded", "circle", "gapped", "diamond", "vbars", "hbars")
EYE_STYLES = ("square", "rounded", "circle", "leaf")
FILL_MODES = ("solid", "linear_h", "linear_v", "diagonal", "radial")
MAX_LOGO_SCALE = 0.30
MAX_CANVAS = 6000


class QRTooLongError(ValueError):
    """The payload does not fit in the largest QR version."""


@dataclass
class QRStyle:
    error_correction: str = "M"
    size: int = 1024
    border: int = 4
    module_style: str = "square"
    eye_frame_style: str = "square"
    eye_center_style: str = "square"
    fill_mode: str = "solid"
    fg: str = "#000000"
    fg2: str = "#2563eb"
    bg: str = "#ffffff"
    transparent: bool = False
    custom_eyes: bool = False
    eye_frame_color: str = "#000000"
    eye_center_color: str = "#000000"
    logo_path: str = ""
    logo_scale: float = 0.22
    logo_background: bool = True
    caption: str = ""
    caption_color: str = "#000000"
    frame: bool = False
    frame_color: str = "#111827"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "QRStyle":
        if not data:
            return cls()
        known = {f.name for f in fields(cls)}
        style = cls(**{k: v for k, v in data.items() if k in known})
        return style.sanitized()

    def sanitized(self) -> "QRStyle":
        """Clamp values loaded from disk or typed by the user."""
        if self.error_correction not in ECC_LEVELS:
            self.error_correction = "M"
        if self.module_style not in MODULE_STYLES:
            self.module_style = "square"
        if self.eye_frame_style not in EYE_STYLES:
            self.eye_frame_style = "square"
        if self.eye_center_style not in EYE_STYLES:
            self.eye_center_style = "square"
        if self.fill_mode not in FILL_MODES:
            self.fill_mode = "solid"
        self.size = int(min(max(int(self.size), 64), 4096))
        self.border = int(min(max(int(self.border), 0), 20))
        self.logo_scale = float(min(max(float(self.logo_scale), 0.05), MAX_LOGO_SCALE))
        for name in ("fg", "fg2", "bg", "eye_frame_color", "eye_center_color", "caption_color", "frame_color"):
            try:
                ImageColor.getrgb(getattr(self, name))
            except (ValueError, TypeError, AttributeError):
                setattr(self, name, QRStyle.__dataclass_fields__[name].default)
        if self.logo_path and not os.path.isfile(self.logo_path):
            self.logo_path = ""
        return self

    @property
    def effective_ecc(self) -> str:
        # A logo hides modules, so it needs the highest error correction.
        return "H" if self.logo_path else self.error_correction


@dataclass
class QRMatrix:
    modules: list[list[bool]]
    version: int
    ecc: str

    @property
    def count(self) -> int:
        return len(self.modules)


@dataclass
class RenderResult:
    image: Image.Image
    matrix: QRMatrix
    payload: str

    @property
    def byte_length(self) -> int:
        return len(self.payload.encode("utf-8"))


def rgb(color: str) -> tuple[int, int, int]:
    return ImageColor.getrgb(color)[:3]


def relative_luminance(color: str) -> float:
    def channel(v: int) -> float:
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = rgb(color)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(c1: str, c2: str) -> float:
    l1, l2 = relative_luminance(c1), relative_luminance(c2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def build_matrix(payload: str, ecc: str = "M") -> QRMatrix:
    if not payload:
        raise ValueError("empty payload")
    qr = qrcode.QRCode(error_correction=ECC_LEVELS[ecc], border=0)
    qr.add_data(payload)
    try:
        qr.make(fit=True)
    except (DataOverflowError, ValueError) as exc:
        raise QRTooLongError(str(exc)) from exc
    return QRMatrix(qr.get_matrix(), qr.version, ecc)


def is_eye(r: int, c: int, n: int) -> bool:
    return (r < 7 and c < 7) or (r < 7 and c >= n - 7) or (r >= n - 7 and c < 7)


def eye_origins(n: int) -> tuple[tuple[int, int], ...]:
    """Top-left (row, col) of the three finder patterns."""
    return ((0, 0), (0, n - 7), (n - 7, 0))


# --------------------------------------------------------------------------- drawing


def _draw_modules(draw: ImageDraw.ImageDraw, m: list[list[bool]], b: int, off: int, style: str) -> None:
    n = len(m)

    def dark(r: int, c: int) -> bool:
        return 0 <= r < n and 0 <= c < n and m[r][c] and not is_eye(r, c, n)

    if style in ("vbars", "hbars"):
        g = max(1, round(b * 0.1))
        radius = (b - 2 * g) // 2
        vertical = style == "vbars"
        for line in range(n):
            pos = 0
            while pos < n:
                r, c = (pos, line) if vertical else (line, pos)
                if not dark(r, c):
                    pos += 1
                    continue
                start = pos
                while pos < n and dark(*((pos, line) if vertical else (line, pos))):
                    pos += 1
                end = pos  # exclusive
                if vertical:
                    box = [off + line * b + g, off + start * b + g, off + (line + 1) * b - 1 - g, off + end * b - 1 - g]
                else:
                    box = [off + start * b + g, off + line * b + g, off + end * b - 1 - g, off + (line + 1) * b - 1 - g]
                draw.rounded_rectangle(box, radius=radius, fill=255)
        return

    gap = max(1, round(b * 0.12))
    dot_gap = max(0, round(b * 0.06))
    for r in range(n):
        for c in range(n):
            if not dark(r, c):
                continue
            x, y = off + c * b, off + r * b
            if style == "square":
                draw.rectangle([x, y, x + b - 1, y + b - 1], fill=255)
            elif style == "gapped":
                draw.rectangle([x + gap, y + gap, x + b - 1 - gap, y + b - 1 - gap], fill=255)
            elif style == "circle":
                draw.ellipse([x + dot_gap, y + dot_gap, x + b - 1 - dot_gap, y + b - 1 - dot_gap], fill=255)
            elif style == "diamond":
                h = b / 2
                draw.polygon([(x + h, y), (x + b, y + h), (x + h, y + b), (x, y + h)], fill=255)
            else:  # rounded: round a corner only where both neighbours are empty
                up, down, left, right = dark(r - 1, c), dark(r + 1, c), dark(r, c - 1), dark(r, c + 1)
                # Start from a dot, then square off every corner that touches a neighbour.
                # (Pillow's rounded_rectangle(corners=...) breaks on small boxes.)
                h = b // 2
                draw.ellipse([x, y, x + b - 1, y + b - 1], fill=255)
                if up or left:
                    draw.rectangle([x, y, x + h, y + h], fill=255)
                if up or right:
                    draw.rectangle([x + b - 1 - h, y, x + b - 1, y + h], fill=255)
                if down or right:
                    draw.rectangle([x + b - 1 - h, y + b - 1 - h, x + b - 1, y + b - 1], fill=255)
                if down or left:
                    draw.rectangle([x, y + b - 1 - h, x + h, y + b - 1], fill=255)


def _shape(draw: ImageDraw.ImageDraw, box: list[int], style: str, radius: int, fill: int) -> None:
    if style == "square":
        draw.rectangle(box, fill=fill)
    elif style == "circle":
        draw.ellipse(box, fill=fill)
    elif style == "leaf":
        draw.rounded_rectangle(box, radius=radius, fill=fill, corners=(True, False, True, False))
    else:
        draw.rounded_rectangle(box, radius=radius, fill=fill)


def _draw_eyes(frame: ImageDraw.ImageDraw, center: ImageDraw.ImageDraw, n: int, b: int, off: int,
               frame_style: str, center_style: str) -> None:
    for r, c in eye_origins(n):
        x, y = off + c * b, off + r * b
        outer = [x, y, x + 7 * b - 1, y + 7 * b - 1]
        hole = [x + b, y + b, x + 6 * b - 1, y + 6 * b - 1]
        inner = [x + 2 * b, y + 2 * b, x + 5 * b - 1, y + 5 * b - 1]
        _shape(frame, outer, frame_style, int(b * 2.2), 255)
        _shape(frame, hole, frame_style, int(b * 1.4), 0)
        _shape(center, inner, center_style, int(b * 1.0), 255)


def _gradient(size: int, c1: str, c2: str, mode: str) -> Image.Image:
    if mode == "linear_v":
        g = Image.linear_gradient("L")
    elif mode == "linear_h":
        g = Image.linear_gradient("L").transpose(Image.Transpose.ROTATE_90)
    elif mode == "diagonal":
        v = Image.linear_gradient("L")
        h = v.transpose(Image.Transpose.ROTATE_90)
        g = ImageChops.add(v, h, scale=2.0)
    else:  # radial
        g = Image.radial_gradient("L")
    g = g.resize((size, size), Image.Resampling.BILINEAR)
    return ImageOps.colorize(g, rgb(c1), rgb(c2))


def _fill(size: int, style: QRStyle) -> Image.Image:
    if style.fill_mode == "solid":
        return Image.new("RGB", (size, size), rgb(style.fg))
    return _gradient(size, style.fg, style.fg2, style.fill_mode)


@lru_cache(maxsize=8)
def _load_logo(path: str, mtime: float) -> Image.Image:
    with Image.open(path) as im:
        return im.convert("RGBA")


def load_logo(path: str) -> Image.Image | None:
    if not path or not os.path.isfile(path):
        return None
    try:
        return _load_logo(path, os.path.getmtime(path)).copy()
    except (OSError, ValueError):
        return None


def _paste_logo(img: Image.Image, style: QRStyle) -> None:
    logo = load_logo(style.logo_path)
    if logo is None:
        return
    size = img.width
    box_px = int(size * style.logo_scale)
    logo.thumbnail((box_px, box_px), Image.Resampling.LANCZOS)
    lw, lh = logo.size
    cx, cy = size // 2, size // 2
    if style.logo_background:
        pad = max(2, int(box_px * 0.12))
        plate = "#ffffff" if style.transparent else style.bg
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            [cx - lw // 2 - pad, cy - lh // 2 - pad, cx + (lw - lw // 2) + pad, cy + (lh - lh // 2) + pad],
            radius=int(pad * 1.6),
            fill=rgb(plate) + (255,),
        )
    img.alpha_composite(logo, (cx - lw // 2, cy - lh // 2))


# --------------------------------------------------------------------------- caption / frame

_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/GeezaPro.ttc",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
)


@lru_cache(maxsize=16)
def load_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def shape_text(text: str) -> str:
    """Prepare right-to-left text (Arabic, Hebrew) for Pillow.

    With libraqm Pillow shapes text itself. Without it we fall back to the
    optional ``arabic-reshaper`` + ``python-bidi`` packages when installed.
    """
    if features.check("raqm") or not any("\u0590" <= ch <= "\u08ff" for ch in text):
        return text
    try:
        import arabic_reshaper  # type: ignore
        from bidi.algorithm import get_display  # type: ignore
    except ImportError:
        return text
    return get_display(arabic_reshaper.reshape(text))


def _fit_font(text: str, max_width: int, start: int) -> ImageFont.ImageFont:
    size = start
    font = load_font(size)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    while size > 8 and probe.textlength(text, font=font) > max_width:
        size = int(size * 0.9)
        font = load_font(size)
    return font


def _decorate(img: Image.Image, style: QRStyle) -> Image.Image:
    text = shape_text(style.caption.strip())
    if not text and not style.frame:
        return img
    w = img.width
    font_size = max(10, int(w * 0.075))
    band = int(font_size * 2.0) if text else 0
    bg = (0, 0, 0, 0) if style.transparent else rgb(style.bg) + (255,)

    if not style.frame:
        out = Image.new("RGBA", (w, w + band), bg)
        out.alpha_composite(img, (0, 0))
        font = _fit_font(text, int(w * 0.9), font_size)
        ImageDraw.Draw(out).text((w // 2, w + band // 2 - band // 8), text, font=font,
                                 fill=rgb(style.caption_color), anchor="mm")
        return out

    pad = max(4, int(w * 0.045))
    total_w = w + 2 * pad
    total_h = w + 2 * pad + (band - pad // 2 if text else 0)
    out = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(out)
    draw.rounded_rectangle([0, 0, total_w - 1, total_h - 1], radius=int(pad * 1.6),
                           fill=rgb(style.frame_color) + (255,))
    plate = (255, 255, 255, 255) if style.transparent else bg
    draw.rounded_rectangle([pad, pad, pad + w - 1, pad + w - 1], radius=int(pad * 0.9), fill=plate)
    out.alpha_composite(img, (pad, pad))
    if text:
        font = _fit_font(text, int(total_w * 0.88), font_size)
        cy = pad + w + (total_h - pad - w) // 2
        draw.text((total_w // 2, cy), text, font=font, fill=rgb(style.caption_color), anchor="mm")
    return out


# --------------------------------------------------------------------------- public API


def render(payload: str, style: QRStyle, size: int | None = None, supersample: int | None = None) -> RenderResult:
    """Render ``payload`` with ``style``.

    ``size`` overrides ``style.size`` (the width of the QR square in pixels,
    frame and caption are added around it).
    """
    matrix = build_matrix(payload, style.effective_ecc)
    n = matrix.count
    total = n + 2 * style.border
    target = int(size or style.size)
    ss = supersample or (3 if target <= 1200 else 2)
    b = max(2, math.ceil(target * ss / total))
    while total * b > MAX_CANVAS and b > 2:
        b -= 1
    canvas = total * b
    off = style.border * b

    module_mask = Image.new("L", (canvas, canvas), 0)
    frame_mask = Image.new("L", (canvas, canvas), 0)
    center_mask = Image.new("L", (canvas, canvas), 0)
    _draw_modules(ImageDraw.Draw(module_mask), matrix.modules, b, off, style.module_style)
    _draw_eyes(ImageDraw.Draw(frame_mask), ImageDraw.Draw(center_mask), n, b, off,
               style.eye_frame_style, style.eye_center_style)

    fill = _fill(canvas, style)
    if style.custom_eyes:
        frame_fill = Image.new("RGB", (canvas, canvas), rgb(style.eye_frame_color))
        center_fill = Image.new("RGB", (canvas, canvas), rgb(style.eye_center_color))
    else:
        frame_fill = center_fill = fill

    bg = (0, 0, 0, 0) if style.transparent else rgb(style.bg) + (255,)
    img = Image.new("RGBA", (canvas, canvas), bg)
    img.paste(fill, (0, 0), module_mask)
    img.paste(frame_fill, (0, 0), frame_mask)
    img.paste(center_fill, (0, 0), center_mask)
    if canvas != target:
        img = img.resize((target, target), Image.Resampling.LANCZOS)

    _paste_logo(img, style)
    img = _decorate(img, style)
    return RenderResult(img, matrix, payload)


def check_image(payload: str, style: QRStyle, size: int = 600) -> Image.Image:
    """Image used for the automatic scan check.

    Same modules, colours, logo and quiet zone as the real code, but with
    standard square finder patterns, because OpenCV's detector cannot find
    rounded ones (phone scanners can). Caption and frame are left out.
    """
    probe = replace(style, eye_frame_style="square", eye_center_style="square", caption="", frame=False)
    return render(payload, probe, size=size, supersample=2).image


def flatten(img: Image.Image, background: str = "#ffffff") -> Image.Image:
    """Return an RGB copy with transparency composited on ``background``."""
    if img.mode != "RGBA":
        return img.convert("RGB")
    base = Image.new("RGBA", img.size, rgb(background) + (255,))
    base.alpha_composite(img)
    return base.convert("RGB")
