"""Recently saved or copied codes."""

from __future__ import annotations

from datetime import datetime
from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk
from PIL import Image

from ..renderer import QRStyle, render
from .widgets import BORDER, CARD_ALT, DANGER, MUTED, TEXT, Card, font, section_title

if TYPE_CHECKING:
    from .app import App

MAX_ROWS = 60
THUMB = 64


class HistoryPage(ctk.CTkFrame):
    def __init__(self, master, app: "App"):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.t = app.t
        self.rtl = app.t.rtl
        self._thumbs: dict[str, Image.Image] = {}
        self._build()

    def _build(self) -> None:
        t, rtl = self.t, self.rtl
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        title = section_title(header, t("history_title"), rtl)
        self.search = ctk.CTkEntry(header, width=260, height=34, corner_radius=8, font=font(13),
                                   placeholder_text=t("history_search"), justify="right" if rtl else "left")
        self.search.bind("<KeyRelease>", lambda _e: self.refresh())
        clear = ctk.CTkButton(header, text=t("history_clear"), width=110, height=34, corner_radius=8,
                              font=font(12), fg_color="transparent", border_width=1, border_color=BORDER,
                              text_color=DANGER, hover_color=CARD_ALT, command=self._clear)
        if rtl:
            title.pack(side="right")
            clear.pack(side="left")
            self.search.pack(side="left", padx=8)
        else:
            title.pack(side="left")
            clear.pack(side="right")
            self.search.pack(side="right", padx=8)

        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.grid(row=1, column=0, sticky="nsew")
        self.list.grid_columnconfigure(0, weight=1)

    def _thumb(self, entry) -> Image.Image | None:
        if entry.id not in self._thumbs:
            try:
                style = QRStyle.from_dict(entry.style)
                style.caption, style.frame = "", False
                self._thumbs[entry.id] = render(entry.payload, style, size=THUMB * 2, supersample=2).image
            except Exception:  # an old entry with data that no longer renders
                return None
        return self._thumbs[entry.id]

    def refresh(self) -> None:
        for child in self.list.winfo_children():
            child.destroy()
        query = self.search.get().strip().lower()
        entries = [e for e in self.app.history.entries
                   if not query or query in e.payload.lower() or query in self.t(f"type_{e.content_type}").lower()]
        if not entries:
            ctk.CTkLabel(self.list, text=self.t("history_empty"), font=font(14), text_color=MUTED
                         ).grid(row=0, column=0, pady=60)
            return
        for i, entry in enumerate(entries[:MAX_ROWS]):
            self._row(i, entry)

    def _row(self, index: int, entry) -> None:
        t, rtl = self.t, self.rtl
        row = Card(self.list, corner_radius=12)
        row.grid(row=index, column=0, sticky="ew", pady=4, padx=2)
        thumb_col, text_col, btn_col = (2, 1, 0) if rtl else (0, 1, 2)
        row.grid_columnconfigure(text_col, weight=1)

        thumb = self._thumb(entry)
        if thumb is not None:
            ctk.CTkLabel(row, text="", image=ctk.CTkImage(thumb, thumb, size=(THUMB, THUMB))
                         ).grid(row=0, column=thumb_col, rowspan=2, padx=12, pady=10)

        anchor = "e" if rtl else "w"
        when = datetime.fromtimestamp(entry.created).strftime("%Y-%m-%d %H:%M")
        ctk.CTkLabel(row, text=f"{t('tile_' + entry.content_type)}  ·  {when}", font=font(12, "bold"),
                     text_color=TEXT, anchor=anchor).grid(row=0, column=text_col, sticky="sew", pady=(12, 0))
        snippet = entry.payload.replace("\n", "  ⏎  ")
        snippet = snippet if len(snippet) <= 90 else snippet[:87] + "…"
        ctk.CTkLabel(row, text=snippet, font=font(12), text_color=MUTED, anchor=anchor, wraplength=320,
                     justify="right" if rtl else "left").grid(row=1, column=text_col, sticky="new", pady=(0, 12))

        buttons = ctk.CTkFrame(row, fg_color="transparent")
        buttons.grid(row=0, column=btn_col, rowspan=2, padx=12)
        open_btn = ctk.CTkButton(buttons, text=t("history_load"), width=70, height=30, corner_radius=8,
                                 font=font(12), command=lambda e=entry: self.app.load_entry(e))
        del_btn = ctk.CTkButton(buttons, text=t("history_delete"), width=70, height=30, corner_radius=8,
                                font=font(12), fg_color="transparent", border_width=1, border_color=BORDER,
                                text_color=DANGER, hover_color=CARD_ALT,
                                command=lambda e=entry: self._delete(e.id))
        for w in ((del_btn, open_btn) if rtl else (open_btn, del_btn)):
            w.pack(side="left", padx=3)

    def _delete(self, entry_id: str) -> None:
        self.app.history.remove(entry_id)
        self._thumbs.pop(entry_id, None)
        self.refresh()

    def _clear(self) -> None:
        if not self.app.history.entries:
            return
        if messagebox.askyesno(self.t("confirm"), self.t("history_clear_confirm"), parent=self):
            self.app.history.clear()
            self._thumbs.clear()
            self.refresh()
