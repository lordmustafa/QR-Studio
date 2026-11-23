"""Generate many QR codes at once from a list or a .txt / .csv file."""

from __future__ import annotations

import copy
import csv
import os
import queue
import re
import threading
from pathlib import Path
from tkinter import filedialog
from typing import TYPE_CHECKING

import customtkinter as ctk

from .. import system
from ..exporter import EXTENSIONS, FORMATS, export
from ..payloads import PayloadError, build_url
from .icons import icon
from .widgets import (
    ACCENT,
    ACCENT_HOVER,
    BORDER,
    CARD_ALT,
    DANGER,
    MENU_STYLE,
    MUTED,
    SECONDARY_BUTTON,
    SUCCESS,
    Card,
    ScrollCard,
    StepHeader,
    Toast,
    font,
    hint_label,
    responsive_split,
)

if TYPE_CHECKING:
    from .app import App


def safe_name(text: str, limit: int = 40) -> str:
    """A file name made from ``text``: letters (any script), digits, - and _."""
    text = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", "", text.strip())
    name = re.sub(r"[^\w\-]+", "_", text, flags=re.UNICODE).strip("_")
    return name[:limit] or "qr"


def read_items_file(path: str | Path) -> list[tuple[str, str]]:
    """Return (data, file name) pairs from a .txt or .csv file."""
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if path.suffix.lower() != ".csv":
        return [(line.strip(), "") for line in text.splitlines() if line.strip()]
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        return []
    header = [h.strip().lower() for h in rows[0]]
    if "data" in header:
        di = header.index("data")
        fi = header.index("filename") if "filename" in header else None
        items = []
        for row in rows[1:]:
            if len(row) > di and row[di].strip():
                name = row[fi].strip() if fi is not None and len(row) > fi else ""
                items.append((row[di].strip(), name))
        return items
    return [(row[0].strip(), "") for row in rows if row and row[0].strip()]


class BatchPage(ctk.CTkFrame):
    def __init__(self, master, app: "App"):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.t = app.t
        self.rtl = app.t.rtl
        self._imported: list[tuple[str, str]] = []
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.folder = app.config_data.save_dir
        self._build()

    def _build(self) -> None:
        t, rtl = self.t, self.rtl
        anchor = "e" if rtl else "w"
        side = "right" if rtl else "left"
        other = "left" if rtl else "right"

        # 1. the list of links or texts
        left = Card(self)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(2, weight=1)
        StepHeader(left, 1, t("batch_step_items"), rtl).grid(row=0, column=0, sticky=anchor, padx=20, pady=(18, 4))
        help_label = hint_label(left, t("batch_items_hint"), rtl, wrap=420)
        help_label.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        scale = getattr(left, "_get_widget_scaling", lambda: 1.0)
        left.bind("<Configure>", lambda e: e.width > 1 and help_label.configure(
            wraplength=max(180, int(e.width / scale()) - 50)))
        self.textbox = ctk.CTkTextbox(left, font=font(14), wrap="none", border_width=1, border_color=BORDER,
                                      corner_radius=12)
        self.textbox.grid(row=2, column=0, sticky="nsew", padx=20, pady=4)
        self.textbox.bind("<KeyRelease>", lambda _e: self._update_count())
        bottom = ctk.CTkFrame(left, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", padx=20, pady=(8, 18))
        self.count_label = ctk.CTkLabel(bottom, text=t("batch_count", count=0), font=font(13), text_color=MUTED)
        imp = ctk.CTkButton(bottom, text=t("batch_import"), image=icon("text", 16), height=34, corner_radius=10,
                            font=font(13), command=self._import, **SECONDARY_BUTTON)
        imp.pack(side=side)
        self.count_label.pack(side=other)

        # 2. settings and 3. start
        right = ScrollCard(self, width=330)
        responsive_split(self, left, right, breakpoint=800, rtl=rtl, second_width=370)
        pad = dict(fill="x", padx=18)
        StepHeader(right, 2, t("batch_step_options"), rtl).pack(anchor=anchor, padx=18, pady=(18, 10))

        def label(key: str) -> None:
            ctk.CTkLabel(right, text=t(key), font=font(13), text_color=MUTED, anchor=anchor).pack(**pad, pady=(10, 4))

        label("batch_mode")
        modes = [t("batch_mode_text"), t("batch_mode_url")]
        self.mode_var = ctk.StringVar(value=modes[0])
        ctk.CTkSegmentedButton(right, values=list(reversed(modes)) if rtl else modes, variable=self.mode_var,
                               height=34, font=font(13)).pack(**pad)
        self._mode_labels = dict(zip(modes, ("text", "url")))

        label("batch_format")
        self.format_menu = ctk.CTkOptionMenu(right, values=list(FORMATS), height=34, corner_radius=10,
                                             font=font(13), **MENU_STYLE)
        self.format_menu.set(self.app.config_data.export_format)
        self.format_menu.pack(**pad)

        label("batch_folder")
        self.folder_btn = ctk.CTkButton(right, text="", height=34, corner_radius=10, font=font(13), anchor=anchor,
                                        command=self._choose_folder, **SECONDARY_BUTTON)
        self.folder_btn.pack(**pad)
        self._show_folder()
        hint_label(right, t("batch_uses_design"), rtl, wrap=300).pack(**pad, pady=(14, 0))

        StepHeader(right, 3, t("batch_step_go"), rtl).pack(anchor=anchor, padx=18, pady=(22, 10))
        self.start_btn = ctk.CTkButton(right, text=t("batch_start"), height=46, corner_radius=12,
                                       font=font(16, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                       command=self._start)
        self.start_btn.pack(**pad)
        self.run_box = ctk.CTkFrame(right, fg_color="transparent")  # shown only while working
        self.progress = ctk.CTkProgressBar(self.run_box, height=10, corner_radius=5)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(12, 4))
        self.progress_label = ctk.CTkLabel(self.run_box, text="", font=font(13), text_color=MUTED, anchor=anchor)
        self.progress_label.pack(fill="x")
        self.stop_btn = ctk.CTkButton(self.run_box, text=t("batch_cancel"), height=30, font=font(13),
                                      fg_color="transparent", hover_color=CARD_ALT, text_color=DANGER,
                                      command=self._stop.set)
        self.stop_btn.pack(anchor=anchor)
        self.toast = Toast(right, rtl)
        self.toast.label.configure(wraplength=200)
        self.toast.pack(**pad, pady=(8, 16))

    def _show_folder(self) -> None:
        name = os.path.basename(self.folder.rstrip("/\\")) or self.folder
        self.folder_btn.configure(text=f"  {name}", image=icon("batch", 16))

    # ------------------------------------------------------------------ input
    def _lines(self) -> list[str]:
        return [ln.strip() for ln in self.textbox.get("1.0", "end-1c").splitlines() if ln.strip()]

    def _update_count(self) -> None:
        self.count_label.configure(text=self.t("batch_count", count=len(self._lines())))

    def _import(self) -> None:
        path = filedialog.askopenfilename(parent=self, filetypes=[("Text / CSV", "*.txt *.csv"), ("All", "*.*")])
        if not path:
            return
        try:
            self._imported = read_items_file(path)
        except OSError as exc:
            self.toast.show(str(exc), DANGER)
            return
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", "\n".join(d for d, _ in self._imported))
        self._update_count()

    def _items(self) -> list[tuple[str, str]]:
        lines = self._lines()
        if self._imported and [d for d, _ in self._imported] == lines:
            return list(self._imported)
        return [(line, "") for line in lines]

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self, initialdir=self.folder)
        if folder:
            self.folder = folder
            self._show_folder()

    # ------------------------------------------------------------------ worker
    def _start(self) -> None:
        items = self._items()
        if not items:
            self.toast.show(self.t("batch_empty"), DANGER)
            return
        self._stop.clear()
        self.start_btn.configure(state="disabled")
        self.run_box.pack(fill="x", padx=18, after=self.start_btn)
        self.progress.set(0)
        style = copy.deepcopy(self.app.style)
        args = (items, self._mode_labels[self.mode_var.get()], self.format_menu.get(), Path(self.folder), style)
        self._thread = threading.Thread(target=self._work, args=args, daemon=True)
        self._thread.start()
        self.after(60, self._poll)

    def _work(self, items, mode, fmt, folder: Path, style) -> None:
        ok = failed = 0
        used: set[str] = set()
        for index, (data, name) in enumerate(items, 1):
            if self._stop.is_set():
                break
            try:
                payload = build_url({"url": data}) if mode == "url" else data
                base = safe_name(name) if name else f"{index:03d}_{safe_name(data)}"
                candidate, n = base, 2
                while candidate in used or (folder / (candidate + EXTENSIONS[fmt])).exists():
                    candidate, n = f"{base}-{n}", n + 1
                used.add(candidate)
                export(payload, style, folder / (candidate + EXTENSIONS[fmt]), fmt)
                ok += 1
            except (PayloadError, ValueError, OSError):
                failed += 1
            self._queue.put(("progress", index, len(items)))
        self._queue.put(("done", ok, failed))

    def _poll(self) -> None:
        try:
            while True:
                msg = self._queue.get_nowait()
                if msg[0] == "progress":
                    _, done, total = msg
                    self.progress.set(done / total)
                    self.progress_label.configure(text=self.t("batch_progress", done=done, total=total))
                else:
                    _, ok, failed = msg
                    self._finish(ok, failed)
                    return
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(60, self._poll)

    def _finish(self, ok: int, failed: int) -> None:
        self.start_btn.configure(state="normal")
        self.run_box.pack_forget()
        self.app.config_data.save_dir = self.folder
        folder = self.folder
        self.toast.show(self.t("batch_done", ok=ok, failed=failed), SUCCESS if not failed else DANGER,
                        action=(self.t("open_folder"), lambda: system.open_folder(folder)), timeout=None)
