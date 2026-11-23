"""Platform helpers: copy an image to the clipboard, reveal a file."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image


def copy_image(img: Image.Image) -> bool:
    """Put ``img`` on the system clipboard. Returns False when not supported."""
    tmp = Path(tempfile.gettempdir()) / "qr_studio_clipboard.png"
    img.save(tmp, "PNG")
    try:
        if sys.platform == "darwin":
            script = f'set the clipboard to (read (POSIX file "{tmp}") as «class PNGf»)'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True, timeout=10)
            return True
        if sys.platform.startswith("win"):
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
                f"[System.Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile('{tmp}'))"
            )
            subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps],
                           check=True, capture_output=True, timeout=15)
            return True
        if shutil.which("wl-copy"):
            with open(tmp, "rb") as fh:
                subprocess.run(["wl-copy", "--type", "image/png"], stdin=fh, check=True, timeout=10)
            return True
        if shutil.which("xclip"):
            subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png", "-i", str(tmp)],
                           check=True, timeout=10)
            return True
    except (OSError, subprocess.SubprocessError):
        return False
    return False


def reveal(path: str | Path) -> None:
    """Show ``path`` in Finder / Explorer / the file manager."""
    path = Path(path)
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        elif sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path if path.is_dir() else path.parent)])
    except OSError:
        pass


def open_folder(path: str | Path) -> None:
    path = Path(path)
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError:
        pass
