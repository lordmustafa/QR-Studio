"""Save rendered QR codes to raster formats, PDF and vector SVG."""

from __future__ import annotations

import base64
import io
import math
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

from .renderer import (
    QRStyle,
    build_matrix,
    eye_origins,
    flatten,
    is_eye,
    load_logo,
    render,
)

FORMATS = ("PNG", "JPG", "SVG", "PDF", "WEBP", "BMP")
EXTENSIONS = {"PNG": ".png", "JPG": ".jpg", "SVG": ".svg", "PDF": ".pdf", "WEBP": ".webp", "BMP": ".bmp"}
DPI = 300


def format_from_path(path: str | Path, fallback: str = "PNG") -> str:
    ext = Path(path).suffix.lower()
    for fmt, e in EXTENSIONS.items():
        if ext == e or (fmt == "JPG" and ext == ".jpeg"):
            return fmt
    return fallback


def export(payload: str, style: QRStyle, path: str | Path, fmt: str | None = None) -> Path:
    """Render ``payload`` and write it to ``path``. Returns the final path."""
    path = Path(path)
    fmt = (fmt or format_from_path(path)).upper()
    if fmt not in FORMATS:
        raise ValueError(f"Unsupported format: {fmt}")
    if path.suffix.lower() not in (EXTENSIONS[fmt], ".jpeg" if fmt == "JPG" else EXTENSIONS[fmt]):
        path = path.with_suffix(EXTENSIONS[fmt])
    path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "SVG":
        path.write_text(to_svg(payload, style), encoding="utf-8")
        return path

    image = render(payload, style).image
    save_image(image, path, fmt, style)
    return path


def save_image(image: Image.Image, path: Path, fmt: str, style: QRStyle) -> None:
    flat_bg = "#ffffff" if style.transparent else style.bg
    if fmt == "PNG":
        image.save(path, "PNG", dpi=(DPI, DPI), optimize=True)
    elif fmt == "WEBP":
        image.save(path, "WEBP", lossless=True)
    elif fmt == "JPG":
        flatten(image, flat_bg).save(path, "JPEG", quality=95, dpi=(DPI, DPI), subsampling=0)
    elif fmt == "BMP":
        flatten(image, flat_bg).save(path, "BMP")
    elif fmt == "PDF":
        flatten(image, flat_bg).save(path, "PDF", resolution=DPI)


# --------------------------------------------------------------------------- SVG


def _n(v: float) -> str:
    return f"{round(v, 3):g}"


def _rrect(x: float, y: float, w: float, h: float, r: float,
           corners: tuple[bool, bool, bool, bool] = (True, True, True, True)) -> str:
    tl, tr, br, bl = (r if c else 0 for c in corners)
    d = f"M{_n(x + tl)},{_n(y)}H{_n(x + w - tr)}"
    if tr:
        d += f"A{_n(tr)},{_n(tr)} 0 0 1 {_n(x + w)},{_n(y + tr)}"
    d += f"V{_n(y + h - br)}"
    if br:
        d += f"A{_n(br)},{_n(br)} 0 0 1 {_n(x + w - br)},{_n(y + h)}"
    d += f"H{_n(x + bl)}"
    if bl:
        d += f"A{_n(bl)},{_n(bl)} 0 0 1 {_n(x)},{_n(y + h - bl)}"
    d += f"V{_n(y + tl)}"
    if tl:
        d += f"A{_n(tl)},{_n(tl)} 0 0 1 {_n(x + tl)},{_n(y)}"
    return d + "Z"


def _circle(cx: float, cy: float, r: float) -> str:
    return (f"M{_n(cx - r)},{_n(cy)}A{_n(r)},{_n(r)} 0 1 0 {_n(cx + r)},{_n(cy)}"
            f"A{_n(r)},{_n(r)} 0 1 0 {_n(cx - r)},{_n(cy)}Z")


def _eye_shape(x: float, y: float, s: float, style: str, radius: float) -> str:
    if style == "square":
        return f"M{_n(x)},{_n(y)}h{_n(s)}v{_n(s)}h{_n(-s)}Z"
    if style == "circle":
        return _circle(x + s / 2, y + s / 2, s / 2)
    if style == "leaf":
        return _rrect(x, y, s, s, radius, (True, False, True, False))
    return _rrect(x, y, s, s, radius)


def _module_paths(m: list[list[bool]], border: int, style: str) -> str:
    n = len(m)
    out: list[str] = []

    def dark(r: int, c: int) -> bool:
        return 0 <= r < n and 0 <= c < n and m[r][c] and not is_eye(r, c, n)

    if style in ("vbars", "hbars"):
        g = 0.1
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
                length = pos - start
                if vertical:
                    out.append(_rrect(border + line + g, border + start + g, 1 - 2 * g, length - 2 * g, 0.5 - g))
                else:
                    out.append(_rrect(border + start + g, border + line + g, length - 2 * g, 1 - 2 * g, 0.5 - g))
        return "".join(out)

    for r in range(n):
        for c in range(n):
            if not dark(r, c):
                continue
            x, y = border + c, border + r
            if style == "square":
                out.append(f"M{x},{y}h1v1h-1Z")
            elif style == "gapped":
                out.append(f"M{_n(x + 0.12)},{_n(y + 0.12)}h0.76v0.76h-0.76Z")
            elif style == "circle":
                out.append(_circle(x + 0.5, y + 0.5, 0.44))
            elif style == "diamond":
                out.append(f"M{_n(x + 0.5)},{y}L{x + 1},{_n(y + 0.5)}L{_n(x + 0.5)},{y + 1}L{x},{_n(y + 0.5)}Z")
            else:
                up, down, left, right = dark(r - 1, c), dark(r + 1, c), dark(r, c - 1), dark(r, c + 1)
                corners = (not up and not left, not up and not right, not down and not right, not down and not left)
                out.append(_rrect(x, y, 1, 1, 0.5, corners))
    return "".join(out)


def _gradient_def(style: QRStyle, size: float) -> str:
    stops = (f'<stop offset="0" stop-color="{style.fg}"/>'
             f'<stop offset="1" stop-color="{style.fg2}"/>')
    if style.fill_mode == "radial":
        c = _n(size / 2)
        return (f'<radialGradient id="fill" gradientUnits="userSpaceOnUse" cx="{c}" cy="{c}" r="{c}">'
                f"{stops}</radialGradient>")
    x2, y2 = {"linear_h": (size, 0), "linear_v": (0, size), "diagonal": (size, size)}[style.fill_mode]
    return (f'<linearGradient id="fill" gradientUnits="userSpaceOnUse" x1="0" y1="0" '
            f'x2="{_n(x2)}" y2="{_n(y2)}">{stops}</linearGradient>')


def to_svg(payload: str, style: QRStyle) -> str:
    """Vector version of ``render`` (same shapes, units are QR modules)."""
    matrix = build_matrix(payload, style.effective_ecc)
    n, border = matrix.count, style.border
    size = n + 2 * border
    fill = "url(#fill)" if style.fill_mode != "solid" else style.fg
    frame_color = style.eye_frame_color if style.custom_eyes else fill
    center_color = style.eye_center_color if style.custom_eyes else fill

    eye_frames, eye_centers = [], []
    for r, c in eye_origins(n):
        x, y = border + c, border + r
        eye_frames.append(_eye_shape(x, y, 7, style.eye_frame_style, 2.2) +
                          _eye_shape(x + 1, y + 1, 5, style.eye_frame_style, 1.4))
        eye_centers.append(_eye_shape(x + 2, y + 2, 3, style.eye_center_style, 1.0))

    body: list[str] = []
    if not style.transparent:
        body.append(f'<rect width="{size}" height="{size}" fill="{style.bg}"/>')
    body.append(f'<path fill="{fill}" d="{_module_paths(matrix.modules, border, style.module_style)}"/>')
    body.append(f'<path fill="{frame_color}" fill-rule="evenodd" d="{"".join(eye_frames)}"/>')
    body.append(f'<path fill="{center_color}" d="{"".join(eye_centers)}"/>')

    logo = load_logo(style.logo_path)
    if logo is not None:
        box = size * style.logo_scale
        logo.thumbnail((512, 512), Image.Resampling.LANCZOS)
        lw, lh = logo.size
        scale = box / max(lw, lh)
        w, h = lw * scale, lh * scale
        x, y = (size - w) / 2, (size - h) / 2
        if style.logo_background:
            pad = box * 0.12
            plate = "#ffffff" if style.transparent else style.bg
            body.append(f'<path fill="{plate}" d="{_rrect(x - pad, y - pad, w + 2 * pad, h + 2 * pad, pad * 1.6)}"/>')
        buf = io.BytesIO()
        logo.save(buf, "PNG")
        data = base64.b64encode(buf.getvalue()).decode("ascii")
        body.append(f'<image x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" '
                    f'href="data:image/png;base64,{data}"/>')

    qr_group = "".join(body)
    defs = f"<defs>{_gradient_def(style, size)}</defs>" if style.fill_mode != "solid" else ""
    caption = style.caption.strip()
    font_size = size * 0.075
    band = font_size * 2.0 if caption else 0
    text_attrs = (f'font-family="Arial, Helvetica, Tahoma, sans-serif" font-weight="bold" '
                  f'font-size="{_n(font_size)}" fill="{style.caption_color}" text-anchor="middle" '
                  f'dominant-baseline="central"')

    if style.frame:
        pad = size * 0.045
        tw = size + 2 * pad
        th = size + 2 * pad + (band - pad / 2 if caption else 0)
        plate = "#ffffff" if style.transparent else style.bg
        parts = [
            f'<path fill="{style.frame_color}" d="{_rrect(0, 0, tw, th, pad * 1.6)}"/>',
            f'<path fill="{plate}" d="{_rrect(pad, pad, size, size, pad * 0.9)}"/>',
            f'<g transform="translate({_n(pad)},{_n(pad)})">{qr_group}</g>',
        ]
        if caption:
            cy = pad + size + (th - pad - size) / 2
            parts.append(f'<text x="{_n(tw / 2)}" y="{_n(cy)}" {text_attrs}>{escape(caption)}</text>')
        width, height, content = tw, th, "".join(parts)
    else:
        content = qr_group
        width, height = size, size + band
        if caption:
            if not style.transparent:
                content = f'<rect width="{size}" height="{_n(height)}" fill="{style.bg}"/>' + content
            cy = size + band / 2 - band / 8
            content += f'<text x="{_n(size / 2)}" y="{_n(cy)}" {text_attrs}>{escape(caption)}</text>'

    px = style.size / size
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{math.ceil(width * px)}" height="{math.ceil(height * px)}" '
        f'viewBox="0 0 {_n(width)} {_n(height)}" shape-rendering="geometricPrecision">'
        f"{defs}{content}</svg>\n"
    )
