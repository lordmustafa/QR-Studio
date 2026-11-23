"""Start QR Studio: python main.py

``--selftest [report.txt]`` checks a built app without showing it: it renders,
exports and reads back a QR code, opens and closes the window, then exits with
0 (all good) or 1. Used to verify the PyInstaller builds.
"""

import sys


def selftest(report_path: str | None) -> int:
    import tempfile
    import traceback
    from pathlib import Path

    lines = []
    try:
        from qr_studio import scanner
        from qr_studio.exporter import FORMATS, export
        from qr_studio.i18n import system_language
        from qr_studio.renderer import QRStyle, check_image, render

        payload = "https://example.com/مرحبا"
        style = QRStyle(module_style="rounded", fill_mode="diagonal", caption="امسح الكود", frame=True)
        render(payload, style, size=400)
        lines.append("render: ok")
        lines.append(f"scanner: {scanner.verify(check_image(payload, style), payload)}")
        with tempfile.TemporaryDirectory() as tmp:
            for fmt in FORMATS:
                export(payload, style, Path(tmp) / f"t.{fmt.lower()}", fmt)
        lines.append("export: ok")
        lines.append(f"system language: {system_language()}")

        import os

        os.environ.setdefault("QR_STUDIO_HOME", tempfile.mkdtemp())
        from qr_studio.ui.app import App

        app = App()
        app.update()
        app.destroy()
        lines.append("window: ok")
        ok = "scanner: match" in lines
    except Exception:
        lines.append(traceback.format_exc())
        ok = False
    lines.append("SELFTEST " + ("PASSED" if ok else "FAILED"))
    text = "\n".join(lines)
    if report_path:
        Path(report_path).write_text(text, encoding="utf-8")
    elif sys.stdout:
        print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        i = sys.argv.index("--selftest")
        sys.exit(selftest(sys.argv[i + 1] if len(sys.argv) > i + 1 else None))

    from qr_studio.ui.app import main

    main()
