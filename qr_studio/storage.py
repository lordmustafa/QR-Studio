"""Settings and history, stored as JSON in the user's home folder."""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_DIR = Path(os.environ.get("QR_STUDIO_HOME", Path.home() / ".qr_studio"))
CONFIG_FILE = APP_DIR / "config.json"
HISTORY_FILE = APP_DIR / "history.json"
HISTORY_LIMIT = 200


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file first so a crash never leaves a half-written file.
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


@dataclass
class Config:
    theme: str = "system"  # system | light | dark
    language: str = "system"  # system (follow the OS) | ar | en
    version: int = 2
    save_dir: str = str(Path.home() / "Pictures")
    export_format: str = "PNG"
    content_type: str = "url"
    style: dict = field(default_factory=dict)
    values: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "Config":
        data = _read_json(path, {})
        if not isinstance(data, dict):
            data = {}
        known = cls.__dataclass_fields__.keys()
        if data.get("version", 1) < 2:
            # Version 1 had no "system" choice; start following the OS language.
            data["language"] = "system"
        cfg = cls(**{k: v for k, v in data.items() if k in known})
        cfg.version = 2
        if cfg.theme not in ("system", "light", "dark"):
            cfg.theme = "system"
        if cfg.language not in ("system", "en", "ar"):
            cfg.language = "system"
        if not Path(cfg.save_dir).is_dir():
            cfg.save_dir = str(Path.home())
        return cfg

    def save(self, path: Path = CONFIG_FILE) -> None:
        _write_json(path, asdict(self))


@dataclass
class HistoryEntry:
    content_type: str
    values: dict
    payload: str
    style: dict
    created: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)


class History:
    def __init__(self, path: Path = HISTORY_FILE):
        self.path = path
        raw = _read_json(path, [])
        self.entries: list[HistoryEntry] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                self.entries.append(HistoryEntry(**item))
            except TypeError:
                continue

    def add(self, content_type: str, values: dict, payload: str, style: dict) -> HistoryEntry:
        # Same content again: move it to the top instead of duplicating it.
        self.entries = [e for e in self.entries if not (e.payload == payload and e.content_type == content_type)]
        entry = HistoryEntry(content_type, dict(values), payload, dict(style))
        self.entries.insert(0, entry)
        del self.entries[HISTORY_LIMIT:]
        self.save()
        return entry

    def remove(self, entry_id: str) -> None:
        self.entries = [e for e in self.entries if e.id != entry_id]
        self.save()

    def clear(self) -> None:
        self.entries = []
        self.save()

    def save(self) -> None:
        _write_json(self.path, [asdict(e) for e in self.entries])
