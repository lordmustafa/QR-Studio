---
title: Building QR Studio
description: Run QR Studio from source, run the tests, and build the Windows .exe and the macOS .app and .dmg with PyInstaller.
---

# Building QR Studio

QR Studio is a Python 3.10+ desktop app built with CustomTkinter. The packages it uses:

| Package | Why |
|---|---|
| `customtkinter` | the window and widgets |
| `qrcode` | the QR matrix (QR Studio draws the image itself) |
| `Pillow` | drawing, gradients, logos, export |
| `opencv-python-headless`, `numpy` | optional: reading codes and the automatic scan check |
| `arabic-reshaper`, `python-bidi` | optional: joined Arabic letters in captions when Pillow has no libraqm |
| `pyinstaller` | building the standalone apps |

Without the optional packages the app still runs, and turns the related features off.

## Run from source

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

On Windows use `.venv\Scripts\python` and `.venv\Scripts\pip`, or just double-click `run.bat`.
`run.sh` does the same on macOS and Linux.

Tk must be available. The python.org installers include it. On Debian and Ubuntu run
`sudo apt install python3-tk`. With Homebrew Python on macOS run `brew install python-tk`.

You can also start it as a module: `python -m qr_studio`.

## Tests

```bash
.venv/bin/python -m unittest discover tests
```

The tests cover payloads and field checks, rendering, every export format, valid SVG,
settings and history storage, and the batch helpers.

## Build the standalone apps

PyInstaller builds for the system it runs on. Build the Windows app on Windows and the Mac app on a Mac.

| System | Command | Result |
|---|---|---|
| Windows | `build_windows.bat` | `dist\QR Studio.exe`: one file that runs on Windows 10 and 11 |
| macOS | `./build_mac.sh` | `dist/QR Studio.app` and `dist/QR-Studio-<version>-macOS-<arch>.dmg` |

Both scripts create `.venv`, install `requirements-build.txt` and run `packaging/build.py`, which:

1. draws the app icon from `qr_studio/brand.py` (`.ico` on Windows, `.icns` on macOS),
2. runs PyInstaller (`--onefile` on Windows, an `.app` bundle on macOS),
3. on macOS, fills in `Info.plist`, signs the app ad hoc (`codesign -s -`) and makes the `.dmg`.

The Mac build matches the machine's processor: Apple Silicon (`arm64`) or Intel (`x86_64`).

### Check a build

`--selftest` renders, exports and reads back a code, opens and closes the window, then exits with
0 on success or 1 on failure. It writes a short report if you give a file name:

```bash
"dist/QR Studio.app/Contents/MacOS/QR Studio" --selftest report.txt
```

```bat
"dist\QR Studio.exe" --selftest report.txt
```

## GitHub Actions

`.github/workflows/build.yml` runs on every push to `main`, on version tags and by hand. It builds
on three runners: Windows, macOS Apple Silicon and macOS Intel. Each job runs the unit tests,
builds the app, runs `--selftest`, and keeps the result on the run page under **Artifacts**.

## Make a release

1. Update `__version__` in `qr_studio/__init__.py` and add the changes to `CHANGELOG.md`.
2. Commit, then tag and push:

   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. The workflow builds the three apps and attaches them to a GitHub release for that tag.

## Signing

The builds are not signed with a paid certificate, so Windows SmartScreen and macOS Gatekeeper
warn on first launch. To remove the warnings:

- **Windows:** sign `QR Studio.exe` with a code-signing certificate (`signtool sign`).
- **macOS:** sign with a Developer ID certificate and the hardened runtime, then notarize with
  `xcrun notarytool` and staple the ticket to the `.dmg`.

## Website and README pictures

The pictures in `docs/assets/` are made by the app's own renderer, so every code in them is real
and scannable:

```bash
.venv/bin/python packaging/make_docs_images.py
```

`docs/index.html` is the project website. GitHub Pages serves it from the `docs/` folder of `main`.
