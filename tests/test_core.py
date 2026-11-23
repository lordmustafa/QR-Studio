"""Tests for payload builders, rendering, export, storage and batch helpers.

Run with:  python -m unittest discover tests   (or: pytest)
"""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QR_STUDIO_HOME", tempfile.mkdtemp())

from PIL import Image  # noqa: E402

from qr_studio import scanner  # noqa: E402
from qr_studio.exporter import FORMATS, export, to_svg  # noqa: E402
from qr_studio.payloads import PayloadError, build_payload  # noqa: E402
from qr_studio.renderer import (  # noqa: E402
    EYE_STYLES,
    FILL_MODES,
    MODULE_STYLES,
    QRStyle,
    QRTooLongError,
    check_image,
    contrast_ratio,
    render,
)
from qr_studio.storage import Config, History  # noqa: E402
from qr_studio.ui.batch_page import read_items_file, safe_name  # noqa: E402


class PayloadTests(unittest.TestCase):
    def test_url_adds_scheme(self):
        self.assertEqual(build_payload("url", {"url": "example.com"}), "https://example.com")
        self.assertEqual(build_payload("url", {"url": "http://a.io"}), "http://a.io")

    def test_empty_and_invalid(self):
        for ctype, values, key in [
            ("url", {"url": " "}, "err_empty"),
            ("url", {"url": "a b"}, "err_url"),
            ("text", {"text": ""}, "err_empty"),
            ("email", {"email": "nope"}, "err_email"),
            ("phone", {"phone": "12"}, "err_phone"),
            ("geo", {"latitude": "100", "longitude": "1"}, "err_lat"),
            ("geo", {"latitude": "10", "longitude": "-200"}, "err_lon"),
            ("url", {"url": "/menu"}, "err_url"),
            ("url", {"url": "example"}, "err_url"),
            ("wifi", {"ssid": "x", "password": "short", "security": "WPA"}, "err_wpa_length"),
            ("whatsapp", {"phone": "0770 123 4567"}, "err_whatsapp_cc"),
            ("vcard", {"note": "only a note"}, "err_name"),
            ("wifi", {"ssid": "x", "security": "WPA"}, "err_wifi_password"),
            ("event", {"title": "x", "start": "tomorrow"}, "err_datetime"),
            ("event", {"title": "x", "start": "2026-01-02", "end": "2026-01-01"}, "err_event_order"),
        ]:
            with self.assertRaises(PayloadError) as ctx:
                build_payload(ctype, values)
            self.assertEqual(ctx.exception.key, key, (ctype, values))

    def test_field_errors_and_typing_filters(self):
        from qr_studio.payloads import field_errors, is_allowed

        self.assertEqual(field_errors("wifi", {"ssid": "", "security": "nopass"}), {"ssid": "err_required"})
        self.assertEqual(field_errors("email", {"email": "a@b.co", "subject": ""}), {})
        self.assertEqual(field_errors("vcard", {"first_name": "Ali", "phone": "12", "email": "x"}),
                         {"phone": "err_phone", "email": "err_email"})
        self.assertTrue(is_allowed("phone", "+964 (770) ١٢٣-45"))
        self.assertFalse(is_allowed("phone", "07abc"))
        self.assertFalse(is_allowed("decimal", "33.3x"))

    def test_arabic_digits_and_links(self):
        self.assertEqual(build_payload("geo", {"latitude": "٣٣٫٣", "longitude": "٤٤٫٣٦"}), "geo:33.3,44.36")
        self.assertEqual(build_payload("phone", {"phone": "٠٧٧٠١٢٣٤٥٦٧"}), "tel:07701234567")
        self.assertEqual(build_payload("url", {"url": "localhost:3000/x"}), "https://localhost:3000/x")
        self.assertEqual(build_payload("url", {"url": "mailto:a@b.co"}), "mailto:a@b.co")

    def test_wifi_escaping(self):
        payload = build_payload("wifi", {"ssid": 'My;Net', "password": 'p:a,s"s\\', "security": "WPA",
                                         "hidden": True})
        self.assertEqual(payload, 'WIFI:T:WPA;S:My\\;Net;P:p\\:a\\,s\\"s\\\\;H:true;;')
        self.assertEqual(build_payload("wifi", {"ssid": "Open", "security": "nopass"}), "WIFI:T:nopass;S:Open;;")

    def test_vcard(self):
        payload = build_payload("vcard", {"first_name": "Ali", "last_name": "Hassan", "phone": "0770 123 4567",
                                          "email": "ali@example.com", "note": "a,b;c\nd"})
        self.assertIn("BEGIN:VCARD", payload)
        self.assertIn("N:Hassan;Ali;;;", payload)
        self.assertIn("TEL;TYPE=CELL:07701234567", payload)
        self.assertIn("NOTE:a\\,b\\;c\\nd", payload)

    def test_messages(self):
        self.assertEqual(build_payload("email", {"email": "a@b.co", "subject": "Hi there"}),
                         "mailto:a@b.co?subject=Hi%20there")
        self.assertEqual(build_payload("sms", {"phone": "+964 770", "message": "yo"}), "SMSTO:+964770:yo")
        self.assertEqual(build_payload("whatsapp", {"phone": "00964 770 1234", "message": "مرحبا"}),
                         "https://wa.me/9647701234?text=%D9%85%D8%B1%D8%AD%D8%A8%D8%A7")
        self.assertEqual(build_payload("phone", {"phone": "(0770) 123-45"}), "tel:077012345")

    def test_geo_and_event(self):
        self.assertEqual(build_payload("geo", {"latitude": "33.3", "longitude": "44.4"}), "geo:33.3,44.4")
        self.assertEqual(build_payload("geo", {"latitude": "33.3", "longitude": "44.4", "maps_link": True}),
                         "https://maps.google.com/?q=33.3,44.4")
        event = build_payload("event", {"title": "Party", "start": "2026-12-31 18:30", "end": "2026-12-31 23:00"})
        self.assertIn("DTSTART:20261231T183000", event)
        self.assertIn("DTEND:20261231T230000", event)


class RenderTests(unittest.TestCase):
    payload = "https://example.com/مرحبا"

    def test_every_shape_and_fill_reads_back(self):
        if not scanner.AVAILABLE:
            self.skipTest("OpenCV not installed")
        for module in MODULE_STYLES:
            for fill in FILL_MODES:
                style = QRStyle(module_style=module, fill_mode=fill, fg="#1e3a8a", fg2="#0e7490")
                self.assertEqual(scanner.verify(check_image(self.payload, style), self.payload), "match",
                                 (module, fill))

    def test_eye_styles_render(self):
        for eye in EYE_STYLES:
            img = render(self.payload, QRStyle(eye_frame_style=eye, eye_center_style=eye), size=300).image
            self.assertEqual(img.size, (300, 300))

    def test_logo_forces_high_ecc_and_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            logo = Path(tmp) / "logo.png"
            Image.new("RGB", (80, 80), "#e11d48").save(logo)
            style = QRStyle(logo_path=str(logo), logo_scale=0.25, error_correction="L")
            result = render(self.payload, style, size=600)
            self.assertEqual(result.matrix.ecc, "H")
            if scanner.AVAILABLE:
                self.assertEqual(scanner.verify(result.image, self.payload), "match")

    def test_caption_and_frame_change_size(self):
        img = render("hi", QRStyle(caption="Scan me", frame=True), size=400).image
        self.assertGreater(img.height, img.width)
        self.assertGreater(img.width, 400)

    def test_transparent(self):
        img = render("hi", QRStyle(transparent=True), size=200).image
        self.assertEqual(img.getpixel((1, 1))[3], 0)

    def test_too_long(self):
        with self.assertRaises(QRTooLongError):
            render("x" * 5000, QRStyle(error_correction="H"))

    def test_contrast(self):
        self.assertAlmostEqual(contrast_ratio("#000000", "#ffffff"), 21.0, places=1)

    def test_style_sanitizing(self):
        style = QRStyle.from_dict({"module_style": "bogus", "size": 99999, "fg": "not a color", "extra": 1})
        self.assertEqual(style.module_style, "square")
        self.assertEqual(style.size, 4096)
        self.assertEqual(style.fg, "#000000")


class ExportTests(unittest.TestCase):
    def test_all_formats(self):
        style = QRStyle(size=256, caption="QR", frame=True, fill_mode="radial", module_style="rounded",
                        eye_frame_style="leaf")
        with tempfile.TemporaryDirectory() as tmp:
            for fmt in FORMATS:
                path = export("hello", style, Path(tmp) / f"code.{fmt.lower()}", fmt)
                self.assertTrue(path.exists() and path.stat().st_size > 0, fmt)
            path = export("hello", style, Path(tmp) / "noext", "PNG")
            self.assertEqual(path.suffix, ".png")

    def test_svg_is_valid_xml(self):
        import xml.dom.minidom

        for module in MODULE_STYLES:
            svg = to_svg("hello <&> مرحبا", QRStyle(module_style=module, caption="a<b", fill_mode="linear_h"))
            xml.dom.minidom.parseString(svg.encode("utf-8"))


class StorageTests(unittest.TestCase):
    def test_config_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            cfg = Config(theme="dark", language="ar")
            cfg.save(path)
            loaded = Config.load(path)
            self.assertEqual((loaded.theme, loaded.language), ("dark", "ar"))
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(Config.load(path).theme, "system")

    def test_language_follows_system(self):
        import json

        from qr_studio import i18n

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            self.assertEqual(Config.load(path).language, "system")
            # Old (version 1) files are moved to the system language once.
            path.write_text(json.dumps({"language": "ar"}), encoding="utf-8")
            self.assertEqual(Config.load(path).language, "system")
            Config(language="en").save(path)
            self.assertEqual(Config.load(path).language, "en")

        original = i18n._system_language_codes
        try:
            i18n._system_language_codes = lambda: ["fr-FR", "ar-IQ"]
            self.assertEqual(i18n.resolve_language("system"), "ar")
            i18n._system_language_codes = lambda: ["de_DE"]
            self.assertEqual(i18n.resolve_language("system"), "en")
            self.assertEqual(i18n.resolve_language("ar"), "ar")
        finally:
            i18n._system_language_codes = original

    def test_history_dedupes(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = History(Path(tmp) / "h.json")
            history.add("url", {"url": "a"}, "https://a", {})
            history.add("url", {"url": "b"}, "https://b", {})
            history.add("url", {"url": "a"}, "https://a", {})
            self.assertEqual([e.payload for e in history.entries], ["https://a", "https://b"])
            reloaded = History(Path(tmp) / "h.json")
            self.assertEqual(len(reloaded.entries), 2)


class BatchTests(unittest.TestCase):
    def test_safe_name(self):
        self.assertEqual(safe_name("https://example.com/a b?c"), "example_com_a_b_c")
        self.assertEqual(safe_name("مرحبا بكم"), "مرحبا_بكم")
        self.assertEqual(safe_name("///"), "qr")

    def test_read_csv_and_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "a.csv"
            csv_path.write_text("Data,filename\nhttps://a.com,first\nhello,\n", encoding="utf-8")
            self.assertEqual(read_items_file(csv_path), [("https://a.com", "first"), ("hello", "")])
            txt = Path(tmp) / "a.txt"
            txt.write_text("one\n\n two \n", encoding="utf-8")
            self.assertEqual(read_items_file(txt), [("one", ""), ("two", "")])


if __name__ == "__main__":
    unittest.main()
