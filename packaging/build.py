"""Build QR Studio as a standalone app that runs without Python.

    Windows:  dist/QR Studio.exe              (one file)
    macOS:    dist/QR Studio.app + dist/QR-Studio-macOS-<arch>.dmg

PyInstaller cannot cross-compile: run this on Windows to get the .exe and on
macOS to get the .app. Use build_windows.bat / build_mac.sh, or the GitHub
Actions workflow in .github/workflows/build.yml, which builds both.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from qr_studio import __version__  # noqa: E402
from qr_studio.brand import logo  # noqa: E402

APP_NAME = "QR Studio"
BUNDLE_ID = "com.qrstudio.desktop"
BUILD = ROOT / "build"
DIST = ROOT / "dist"


def make_icon_png(size: int = 1024) -> Image.Image:
    """The app logo. macOS icons get the usual margin and soft shadow; Windows icons fill the square."""
    if sys.platform == "darwin":
        return logo(size, margin=0.09, shadow=True)
    return logo(size, margin=0.02)


def make_icons() -> Path:
    BUILD.mkdir(exist_ok=True)
    icon = make_icon_png()
    icon.save(BUILD / "icon.png")
    if sys.platform == "darwin":
        path = BUILD / "icon.icns"
        icon.save(path, "ICNS")
    else:
        path = BUILD / "icon.ico"
        icon.save(path, "ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return path


def pyinstaller_args(icon: Path) -> list[str]:
    args = [
        str(ROOT / "main.py"),
        "--name", APP_NAME,
        "--windowed",  # no console window
        "--noconfirm",
        "--clean",
        "--icon", str(icon),
        "--distpath", str(DIST),
        "--workpath", str(BUILD / "pyinstaller"),
        "--specpath", str(BUILD),
        "--collect-data", "customtkinter",  # themes and fonts
        "--hidden-import", "PIL._tkinter_finder",
        # Not used by the app; keeps the bundle smaller.
        "--exclude-module", "matplotlib",
        "--exclude-module", "pytest",
        "--exclude-module", "IPython",
    ]
    if sys.platform == "darwin":
        args += ["--osx-bundle-identifier", BUNDLE_ID]
    else:
        args += ["--onefile"]  # a single QR Studio.exe
    return args


def patch_info_plist(app: Path) -> None:
    import plistlib

    plist_path = app / "Contents" / "Info.plist"
    with plist_path.open("rb") as fh:
        info = plistlib.load(fh)
    info.update({
        "CFBundleDisplayName": APP_NAME,
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        "NSRequiresAquaSystemAppearance": False,  # allow dark mode
        "CFBundleLocalizations": ["en", "ar"],
    })
    with plist_path.open("wb") as fh:
        plistlib.dump(info, fh)
    # Editing Info.plist breaks the ad-hoc signature, so sign again.
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)


def make_dmg(app: Path) -> Path:
    staging = BUILD / "dmg"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    shutil.copytree(app, staging / app.name, symlinks=True)
    (staging / "Applications").symlink_to("/Applications")
    dmg = DIST / f"QR-Studio-{__version__}-macOS-{platform.machine()}.dmg"
    dmg.unlink(missing_ok=True)
    cmd = ["hdiutil", "create", "-volname", APP_NAME, "-srcfolder", str(staging), "-ov", "-format", "UDZO",
           str(dmg)]
    for attempt in range(4):  # hdiutil sometimes fails with "Resource busy"; a retry fixes it
        if subprocess.run(cmd).returncode == 0:
            return dmg
        time.sleep(2 + attempt * 2)
    raise RuntimeError("hdiutil could not create the DMG")


def main() -> None:
    import PyInstaller.__main__

    icon = make_icons()
    PyInstaller.__main__.run(pyinstaller_args(icon))
    if sys.platform == "darwin":
        app = DIST / f"{APP_NAME}.app"
        shutil.rmtree(DIST / APP_NAME, ignore_errors=True)  # loose copy; the .app has everything
        patch_info_plist(app)
        print(f"\nApp:  {app}\nDMG:  {make_dmg(app)}")
    else:
        print(f"\nEXE:  {DIST / (APP_NAME + '.exe')}")


if __name__ == "__main__":
    main()
