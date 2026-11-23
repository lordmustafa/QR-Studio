"""Form definitions, validation and the text stored inside each kind of QR code.

Every content type lists its form fields. Each field says how it is checked
(``check``), whether it must be filled in (``required``) and which characters
can be typed into it (``allowed``). ``field_errors`` returns the problems per
field, so the form can show each message under its own field, and
``build_payload`` turns valid values into the QR text or raises
``PayloadError`` with a translation key.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote


class PayloadError(ValueError):
    """Raised when form values cannot be turned into a payload."""

    def __init__(self, key: str, field_key: str = ""):
        super().__init__(key)
        self.key = key
        self.field = field_key


# Characters a field accepts while typing (Arabic-Indic digits included).
_DIGITS = "0-9٠-٩۰-۹"
ALLOWED = {
    "phone": rf"[{_DIGITS}+\-\s().]*",
    "decimal": rf"[{_DIGITS}\-.,٫]*",
    "datetime": rf"[{_DIGITS}\-:/\sT]*",
}


@dataclass(frozen=True)
class Field:
    key: str
    kind: str = "entry"  # entry | password | text | combo | check
    options: tuple[str, ...] = ()
    default: str | bool = ""
    hint: str = ""  # translation key for the placeholder
    required: bool = False
    check: str = ""  # url | email | phone | whatsapp_phone | latitude | longitude | datetime | ssid | wifi_password
    allowed: str = ""  # key of ALLOWED


@dataclass(frozen=True)
class ContentType:
    key: str
    fields: tuple[Field, ...] = field(default_factory=tuple)


CONTENT_TYPES: dict[str, ContentType] = {
    "url": ContentType("url", (Field("url", hint="hint_url", required=True, check="url"),)),
    "text": ContentType("text", (Field("text", "text", required=True),)),
    "wifi": ContentType(
        "wifi",
        (
            Field("ssid", required=True, check="ssid"),
            Field("password", "password", check="wifi_password"),
            Field("security", "combo", ("WPA", "WEP", "nopass"), "WPA"),
            Field("hidden", "check", default=False),
        ),
    ),
    "vcard": ContentType(
        "vcard",
        (
            Field("first_name"),
            Field("last_name"),
            Field("organization"),
            Field("job_title"),
            Field("phone", hint="hint_phone", check="phone", allowed="phone"),
            Field("email", hint="hint_email", check="email"),
            Field("website", hint="hint_url", check="url"),
            Field("address"),
            Field("note", "text"),
        ),
    ),
    "email": ContentType(
        "email",
        (Field("email", hint="hint_email", required=True, check="email"), Field("subject"), Field("body", "text")),
    ),
    "sms": ContentType(
        "sms",
        (Field("phone", hint="hint_phone", required=True, check="phone", allowed="phone"), Field("message", "text")),
    ),
    "phone": ContentType("phone", (Field("phone", hint="hint_phone", required=True, check="phone", allowed="phone"),)),
    "whatsapp": ContentType(
        "whatsapp",
        (
            Field("phone", hint="hint_whatsapp", required=True, check="whatsapp_phone", allowed="phone"),
            Field("message", "text"),
        ),
    ),
    "geo": ContentType(
        "geo",
        (
            Field("latitude", hint="hint_lat", required=True, check="latitude", allowed="decimal"),
            Field("longitude", hint="hint_lon", required=True, check="longitude", allowed="decimal"),
            Field("maps_link", "check", default=False),
        ),
    ),
    "event": ContentType(
        "event",
        (
            Field("title", required=True),
            Field("start", hint="hint_datetime", required=True, check="datetime", allowed="datetime"),
            Field("end", hint="hint_datetime", check="datetime", allowed="datetime"),
            Field("location"),
            Field("description", "text"),
        ),
    ),
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
_HOST_RE = re.compile(r"^([\w-]+\.)+[\w-]{2,}$", re.UNICODE)
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")
_WESTERN = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫،", "01234567890123456789.,")


def western_digits(text: str) -> str:
    """Arabic-Indic digits (٠١٢ / ۰۱۲) and the Arabic decimal mark to ASCII."""
    return text.translate(_WESTERN)


def _clean(values: dict, key: str) -> str:
    value = values.get(key, "")
    return value.strip() if isinstance(value, str) else ""


def is_allowed(allowed: str, text: str) -> bool:
    """True when ``text`` only has characters the field accepts while typing."""
    pattern = ALLOWED.get(allowed)
    return pattern is None or re.fullmatch(pattern, text) is not None


# --------------------------------------------------------------------------- single-value checks


def normalize_phone(raw: str, keep_plus: bool = True) -> str:
    phone = re.sub(r"[\s\-().]", "", western_digits(raw))
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    digits = phone[1:] if phone.startswith("+") else phone
    if not digits.isdigit() or not 5 <= len(digits) <= 15:
        raise PayloadError("err_phone")
    if phone.startswith("+") and not keep_plus:
        return digits
    return phone


def normalize_url(raw: str) -> str:
    """Add https:// when no scheme is given; raise PayloadError for a link that cannot work."""
    url = raw.strip()
    if not url:
        raise PayloadError("err_empty")
    if any(ch.isspace() for ch in url):
        raise PayloadError("err_url")
    lower = url.lower()
    if lower.startswith(("http://", "https://")):
        pass
    elif lower.startswith(("http:", "https:")):  # "https:example.com"
        url = "https://" + url.split(":", 1)[1].lstrip("/")
    elif _SCHEME_RE.match(url) and not re.match(r"^[\w.-]+:\d", url):
        return url  # another scheme (mailto:, tel:, ...), not "host:port"
    else:
        url = "https://" + url
    if url.lower().startswith(("http://", "https://")):
        host = re.split(r"[/?#]", url.split("://", 1)[1], maxsplit=1)[0]
        host = host.rsplit("@", 1)[-1]  # drop user:password@
        if host.startswith("["):  # IPv6 literal
            host = host[1:].split("]", 1)[0]
        else:
            host = re.sub(r":\d+$", "", host)
        if not _valid_host(host):
            raise PayloadError("err_url")
    return url


def _valid_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return bool(_HOST_RE.match(host))


def parse_number(raw: str) -> float:
    return float(western_digits(raw).replace(",", ".").strip())


def ical_datetime(raw: str) -> str:
    raw = western_digits(raw).strip().replace("/", "-")
    for fmt, out in (
        ("%Y-%m-%d %H:%M", "%Y%m%dT%H%M%S"),
        ("%Y-%m-%dT%H:%M", "%Y%m%dT%H%M%S"),
        ("%Y-%m-%d", "%Y%m%d"),
    ):
        try:
            return datetime.strptime(raw, fmt).strftime(out)
        except ValueError:
            continue
    raise PayloadError("err_datetime")


def _check_value(check: str, value: str, values: dict) -> str | None:
    """Error key for one non-empty value, or None when it is fine."""
    try:
        if check == "url":
            normalize_url(value)
        elif check == "email":
            if not _EMAIL_RE.match(value):
                return "err_email"
        elif check == "phone":
            normalize_phone(value)
        elif check == "whatsapp_phone":
            phone = normalize_phone(value)
            if not phone.startswith("+") and phone.startswith("0"):
                return "err_whatsapp_cc"  # wa.me needs the country code, not a local 0...
        elif check == "latitude":
            if not -90 <= parse_number(value) <= 90:
                return "err_lat"
        elif check == "longitude":
            if not -180 <= parse_number(value) <= 180:
                return "err_lon"
        elif check == "datetime":
            ical_datetime(value)
        elif check == "ssid":
            if len(value.encode("utf-8")) > 32:
                return "err_ssid_long"
    except PayloadError as err:
        return err.key
    except ValueError:
        return "err_lat" if check == "latitude" else "err_lon" if check == "longitude" else "err_type"
    return None


def _wifi_password_error(values: dict) -> str | None:
    security = values.get("security") or "WPA"
    password = values.get("password", "") or ""
    if security == "nopass":
        return None
    if not password:
        return "err_wifi_password"
    if security == "WPA" and not 8 <= len(password) <= 63:
        return "err_wpa_length"
    if security == "WEP":
        is_hex = re.fullmatch(r"[0-9a-fA-F]+", password) is not None
        if not (len(password) in (5, 13) or (is_hex and len(password) in (10, 26))):
            return "err_wep_length"
    return None


def field_errors(content_type: str, values: dict) -> dict[str, str]:
    """{field key: error key} for every field with a problem, in form order."""
    ctype = CONTENT_TYPES[content_type]
    errors: dict[str, str] = {}
    for f in ctype.fields:
        if f.kind in ("check", "combo"):
            continue
        raw = values.get(f.key, "")
        value = raw if f.kind == "text" else (raw.strip() if isinstance(raw, str) else "")
        if f.check == "wifi_password":
            error = _wifi_password_error(values)
        elif not (value.strip() if isinstance(value, str) else value):
            error = "err_required" if f.required else None
        else:
            error = _check_value(f.check, value, values) if f.check else None
        if error:
            errors[f.key] = error

    # rules that look at more than one field
    if content_type == "vcard" and not any(_clean(values, k) for k in ("first_name", "last_name", "organization")):
        errors = {"first_name": "err_name", **errors}
    if content_type == "event" and "start" not in errors and "end" not in errors and _clean(values, "end"):
        if ical_datetime(_clean(values, "end")) < ical_datetime(_clean(values, "start")):
            errors["end"] = "err_event_order"
    return errors


def is_blank(content_type: str, values: dict) -> bool:
    """True when the user has not typed anything yet."""
    keys = [f.key for f in CONTENT_TYPES[content_type].fields if f.kind not in ("check", "combo")]
    return not any(isinstance(values.get(k), str) and values[k].strip() for k in keys)


# --------------------------------------------------------------------------- escaping and builders


def escape_wifi(value: str) -> str:
    for ch in '\\;,:"':
        value = value.replace(ch, "\\" + ch)
    return value


def escape_vcard(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def build_url(values: dict) -> str:
    return normalize_url(_clean(values, "url"))


def build_text(values: dict) -> str:
    return values.get("text", "")


def build_wifi(values: dict) -> str:
    security = values.get("security") or "WPA"
    parts = [f"T:{security}", f"S:{escape_wifi(_clean(values, 'ssid'))}"]
    if security != "nopass":
        parts.append(f"P:{escape_wifi(values.get('password', ''))}")
    if values.get("hidden"):
        parts.append("H:true")
    return "WIFI:" + ";".join(parts) + ";;"


def build_vcard(values: dict) -> str:
    first = _clean(values, "first_name")
    last = _clean(values, "last_name")
    org = _clean(values, "organization")
    full_name = " ".join(p for p in (first, last) if p) or org
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{escape_vcard(last)};{escape_vcard(first)};;;",
        f"FN:{escape_vcard(full_name)}",
    ]
    if org:
        lines.append(f"ORG:{escape_vcard(org)}")
    if title := _clean(values, "job_title"):
        lines.append(f"TITLE:{escape_vcard(title)}")
    if phone := _clean(values, "phone"):
        lines.append(f"TEL;TYPE=CELL:{normalize_phone(phone)}")
    if email := _clean(values, "email"):
        lines.append(f"EMAIL;TYPE=INTERNET:{email}")
    if website := _clean(values, "website"):
        lines.append(f"URL:{normalize_url(website)}")
    if address := _clean(values, "address"):
        lines.append(f"ADR;TYPE=WORK:;;{escape_vcard(address)};;;;")
    if note := _clean(values, "note"):
        lines.append(f"NOTE:{escape_vcard(note)}")
    lines.append("END:VCARD")
    return "\n".join(lines)


def build_email(values: dict) -> str:
    query = []
    if subject := _clean(values, "subject"):
        query.append("subject=" + quote(subject))
    if body := _clean(values, "body"):
        query.append("body=" + quote(body))
    return f"mailto:{_clean(values, 'email')}" + ("?" + "&".join(query) if query else "")


def build_sms(values: dict) -> str:
    return f"SMSTO:{normalize_phone(_clean(values, 'phone'))}:{_clean(values, 'message')}"


def build_phone(values: dict) -> str:
    return "tel:" + normalize_phone(_clean(values, "phone"))


def build_whatsapp(values: dict) -> str:
    phone = normalize_phone(_clean(values, "phone"), keep_plus=False)
    message = _clean(values, "message")
    return f"https://wa.me/{phone}" + ("?text=" + quote(message) if message else "")


def build_geo(values: dict) -> str:
    lat = parse_number(_clean(values, "latitude"))
    lon = parse_number(_clean(values, "longitude"))
    if values.get("maps_link"):
        return f"https://maps.google.com/?q={lat},{lon}"
    return f"geo:{lat},{lon}"


def build_event(values: dict) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "BEGIN:VEVENT",
        f"SUMMARY:{escape_vcard(_clean(values, 'title'))}",
        f"DTSTART:{ical_datetime(_clean(values, 'start'))}",
    ]
    if end := _clean(values, "end"):
        lines.append(f"DTEND:{ical_datetime(end)}")
    if location := _clean(values, "location"):
        lines.append(f"LOCATION:{escape_vcard(location)}")
    if description := _clean(values, "description"):
        lines.append(f"DESCRIPTION:{escape_vcard(description)}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\n".join(lines)


BUILDERS = {
    "url": build_url,
    "text": build_text,
    "wifi": build_wifi,
    "vcard": build_vcard,
    "email": build_email,
    "sms": build_sms,
    "phone": build_phone,
    "whatsapp": build_whatsapp,
    "geo": build_geo,
    "event": build_event,
}


def build_payload(content_type: str, values: dict) -> str:
    """Return the QR payload for ``content_type`` or raise ``PayloadError``."""
    if content_type not in BUILDERS:
        raise PayloadError("err_type")
    if is_blank(content_type, values):
        raise PayloadError("err_empty")
    errors = field_errors(content_type, values)
    if errors:
        key, error = next(iter(errors.items()))
        raise PayloadError(error, key)
    return BUILDERS[content_type](values)
