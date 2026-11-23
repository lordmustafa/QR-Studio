"""Read QR codes from images with OpenCV (optional dependency)."""

from __future__ import annotations

from PIL import Image, ImageOps

try:  # OpenCV is optional: without it the Scan page and scan check are disabled.
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the environment
    cv2 = None
    np = None
    AVAILABLE = False


def _prepare(img: Image.Image, max_side: int = 1400) -> "np.ndarray":
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        base = Image.new("RGBA", img.size, (255, 255, 255, 255))
        base.alpha_composite(img)
        img = base
    img = img.convert("RGB")
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    pad = max(8, img.width // 12)
    img = ImageOps.expand(img, border=pad, fill="white")
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)


def _detectors():
    yield cv2.QRCodeDetector()
    if hasattr(cv2, "QRCodeDetectorAruco"):
        yield cv2.QRCodeDetectorAruco()


def decode(img: Image.Image) -> list[str]:
    """Return every QR payload found in ``img`` (empty list if none)."""
    if not AVAILABLE:
        return []
    gray = _prepare(img)
    candidates = [gray, cv2.bitwise_not(gray)]  # also try inverted (light on dark) codes
    for frame in candidates:
        for detector in _detectors():
            try:
                ok, texts, _, _ = detector.detectAndDecodeMulti(frame)
                found = [t for t in texts if t] if ok else []
                if not found:
                    text, _, _ = detector.detectAndDecode(frame)
                    found = [text] if text else []
            except cv2.error:
                continue
            if found:
                return list(dict.fromkeys(found))
    return []


def verify(img: Image.Image, payload: str) -> str:
    """'match' if the payload is read back, 'read' if something else is read, else 'fail'.

    OpenCV cannot locate round finder patterns that phone cameras read fine,
    so callers should pass an image rendered with square eyes (see
    ``renderer.check_image``) to test the data modules, colours and logo.
    """
    if not AVAILABLE:
        return "unavailable"
    found = decode(img)
    if payload in found or payload.replace("\n", "\r\n") in found:
        return "match"
    return "read" if found else "fail"
