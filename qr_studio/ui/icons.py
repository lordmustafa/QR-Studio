"""Line icons drawn with Pillow, so they look the same on Windows, macOS and Linux
(emoji render differently, or not at all, in Tk on each system)."""

from __future__ import annotations

from functools import lru_cache

import customtkinter as ctk
from PIL import Image, ImageDraw

LIGHT = "#374151"
DARK = "#d1d5db"
WHITE = "#ffffff"
_S = 96 * 4  # drawing canvas (supersampled, scaled down at the end)
_W = 26  # stroke width on the canvas


def _rect(d, box, r=40, **kw):
    d.rounded_rectangle(box, radius=r, outline=kw.get("c"), width=_W)


def _line(d, pts, c):
    d.line(pts, fill=c, width=_W, joint="curve")
    for x, y in (pts[0], pts[-1]):
        d.ellipse([x - _W / 2, y - _W / 2, x + _W / 2, y + _W / 2], fill=c)


def _dot(d, x, y, r, c):
    d.ellipse([x - r, y - r, x + r, y + r], fill=c)


def _url(d, c):
    # two chain links at 45°
    link = Image.new("L", (_S, _S), 0)
    ld = ImageDraw.Draw(link)
    ld.rounded_rectangle([60, 140, 230, 244], radius=52, outline=255, width=_W)
    ld.rounded_rectangle([154, 140, 324, 244], radius=52, outline=255, width=_W)
    return link.rotate(45, resample=Image.Resampling.BICUBIC)


def _text(d, c):
    _rect(d, [86, 50, 298, 334], 34, c=c)
    for y, x2 in ((130, 250), (190, 250), (250, 200)):
        _line(d, [(134, y), (x2, y)], c)


def _wifi(d, c):
    for r in (150, 100, 50):
        d.arc([192 - r, 250 - r, 192 + r, 250 + r], 225, 315, fill=c, width=_W)
    _dot(d, 192, 262, 20, c)


def _vcard(d, c):
    _rect(d, [40, 80, 344, 304], 34, c=c)
    _dot(d, 128, 160, 30, c)
    d.arc([78, 196, 178, 290], 180, 360, fill=c, width=_W)
    _line(d, [(214, 160), (300, 160)], c)
    _line(d, [(214, 220), (280, 220)], c)


def _email(d, c):
    _rect(d, [44, 90, 340, 294], 30, c=c)
    _line(d, [(70, 118), (192, 210), (314, 118)], c)


def _sms(d, c):
    _rect(d, [50, 70, 334, 260], 50, c=c)
    _line(d, [(110, 260), (90, 320), (170, 262)], c)
    for x in (130, 192, 254):
        _dot(d, x, 165, 18, c)


def _phone(d, c):
    _rect(d, [116, 40, 268, 344], 34, c=c)
    _line(d, [(170, 296), (214, 296)], c)


def _whatsapp(d, c):
    d.ellipse([60, 52, 324, 316], outline=c, width=_W)
    _line(d, [(98, 268), (70, 336), (146, 304)], c)
    d.arc([128, 120, 256, 248], 30, 150, fill=c, width=_W)


def _geo(d, c):
    d.pieslice([92, 40, 292, 240], 150, 30, fill=None, outline=c, width=_W)
    d.arc([92, 40, 292, 240], 150, 30, fill=c, width=_W)
    _line(d, [(105, 190), (192, 340), (279, 190)], c)
    d.ellipse([152, 100, 232, 180], outline=c, width=_W)


def _event(d, c):
    _rect(d, [50, 70, 334, 330], 34, c=c)
    _line(d, [(62, 150), (322, 150)], c)
    _line(d, [(130, 40), (130, 100)], c)
    _line(d, [(254, 40), (254, 100)], c)
    for x in (130, 192, 254):
        for y in (210, 270):
            _dot(d, x, y, 15, c)


def _create(d, c):
    _rect(d, [60, 60, 324, 324], 60, c=c)
    _line(d, [(192, 130), (192, 254)], c)
    _line(d, [(130, 192), (254, 192)], c)


def _batch(d, c):
    for x, y in ((60, 60), (210, 60), (60, 210), (210, 210)):
        _rect(d, [x, y, x + 114, y + 114], 26, c=c)


def _scan(d, c):
    for (x, y), (dx, dy) in (((60, 60), (1, 1)), ((324, 60), (-1, 1)), ((60, 324), (1, -1)), ((324, 324), (-1, -1))):
        _line(d, [(x, y + dy * 80), (x, y), (x + dx * 80, y)], c)
    _line(d, [(100, 192), (284, 192)], c)


def _history(d, c):
    d.ellipse([56, 56, 328, 328], outline=c, width=_W)
    _line(d, [(192, 110), (192, 192), (250, 236)], c)


def _logo(d, c):
    _rect(d, [50, 70, 334, 314], 34, c=c)
    _dot(d, 136, 146, 26, c)
    _line(d, [(70, 290), (160, 210), (220, 260), (270, 214), (320, 262)], c)


def _download(d, c):
    _line(d, [(192, 50), (192, 236)], c)
    _line(d, [(116, 166), (192, 242), (268, 166)], c)
    _line(d, [(70, 260), (70, 320), (314, 320), (314, 260)], c)


def _copy(d, c):
    _rect(d, [120, 50, 334, 270], 30, c=c)
    _line(d, [(84, 120), (60, 120), (60, 334), (262, 334), (262, 310)], c)


_DRAW = {
    "url": _url, "text": _text, "wifi": _wifi, "vcard": _vcard, "email": _email, "sms": _sms,
    "phone": _phone, "whatsapp": _whatsapp, "geo": _geo, "event": _event,
    "create": _create, "batch": _batch, "scan": _scan, "history": _history,
    "logo": _logo, "download": _download, "copy": _copy,
}


@lru_cache(maxsize=128)
def icon_image(name: str, color: str, px: int = 48) -> Image.Image:
    canvas = Image.new("RGBA", (_S, _S), (0, 0, 0, 0))
    mask_or_none = _DRAW[name](ImageDraw.Draw(canvas), color)
    if isinstance(mask_or_none, Image.Image):  # drawn as a mask (rotated shapes)
        fill = Image.new("RGBA", (_S, _S), color)
        canvas.paste(fill, (0, 0), mask_or_none)
    return canvas.resize((px, px), Image.Resampling.LANCZOS)


def icon(name: str, size: int = 24, light: str = LIGHT, dark: str = DARK) -> ctk.CTkImage:
    """A themed CTkImage (``size`` in CustomTkinter units, drawn at 2x for sharp edges)."""
    return ctk.CTkImage(icon_image(name, light, size * 2), icon_image(name, dark, size * 2), size=(size, size))


NAMES = tuple(_DRAW)
