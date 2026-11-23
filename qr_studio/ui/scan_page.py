"""Read QR codes from image files or the clipboard."""

from __future__ import annotations

import webbrowser
from tkinter import filedialog
from typing import TYPE_CHECKING

import customtkinter as ctk
from PIL import Image, ImageGrab, UnidentifiedImageError

from .. import scanner
from .icons import WHITE, icon
from .widgets import (
    ACCENT,
    ACCENT_HOVER,
    BORDER,
    CARD_ALT,
    DANGER,
    LINK_BUTTON,
    MUTED,
    SECONDARY_BUTTON,
    SUCCESS,
    Card,
    Toast,
    font,
    section_title,
)

if TYPE_CHECKING:
    from .app import App


class ScanPage(ctk.CTkFrame):
    def __init__(self, master, app: "App"):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.t = app.t
        self.rtl = app.t.rtl
        self.results: list[str] = []
        self._image: Image.Image | None = None
        self._build()

    def _build(self) -> None:
        t, rtl = self.t, self.rtl

        # picker: always visible
        left = self.left = Card(self)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)
        section_title(left, t("scan_title"), rtl).grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        self.stage = ctk.CTkFrame(left, fg_color=CARD_ALT, corner_radius=16)
        self.stage.grid(row=1, column=0, sticky="nsew", padx=20, pady=6)
        self.stage.grid_rowconfigure(0, weight=1)
        self.stage.grid_columnconfigure(0, weight=1)
        hint = t("scan_drop_hint") if scanner.AVAILABLE else t("scan_unavailable")
        self.image_label = ctk.CTkLabel(self.stage, text=hint, image=icon("scan", 56), compound="top",
                                        font=font(15), text_color=MUTED)
        self.image_label.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        self.stage.bind("<Configure>", lambda _e: self._show_image())

        buttons = ctk.CTkFrame(left, fg_color="transparent")
        buttons.grid(row=2, column=0, pady=(10, 4))
        state = "normal" if scanner.AVAILABLE else "disabled"
        open_btn = ctk.CTkButton(buttons, text=t("scan_open"), image=icon("logo", 18, WHITE, WHITE), height=44,
                                 width=170, corner_radius=12, font=font(14, "bold"), fg_color=ACCENT,
                                 hover_color=ACCENT_HOVER, command=self._open, state=state)
        paste_btn = ctk.CTkButton(buttons, text=t("scan_paste"), image=icon("copy", 18), height=44, width=190,
                                  corner_radius=12, font=font(14), command=self._paste, state=state,
                                  **SECONDARY_BUTTON)
        for i, w in enumerate((paste_btn, open_btn) if rtl else (open_btn, paste_btn)):
            w.grid(row=0, column=i, padx=5)
        self.status = ctk.CTkLabel(left, text="", font=font(13), text_color=MUTED, anchor="center")
        self.status.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 16))

        # results: shown after a code was found
        right = self.right = Card(self)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        self.result_title = section_title(right, "", rtl)
        self.result_title.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        self.textbox = ctk.CTkTextbox(right, font=font(15), wrap="word", border_width=1, border_color=BORDER,
                                      corner_radius=12)
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=4)
        self.actions = ctk.CTkFrame(right, fg_color="transparent")
        self.actions.grid(row=2, column=0, pady=(10, 4))
        self.link_btn = ctk.CTkButton(self.actions, text=t("scan_open_link"), image=icon("url", 18, WHITE, WHITE),
                                      height=44, width=150, corner_radius=12, font=font(14, "bold"),
                                      fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._open_link)
        self.copy_btn = ctk.CTkButton(self.actions, text=t("copy_text"), image=icon("copy", 18), height=44,
                                      width=140, corner_radius=12, font=font(14), command=self._copy,
                                      **SECONDARY_BUTTON)
        self.edit_btn = ctk.CTkButton(right, text=t("scan_edit"), height=32, font=font(13), command=self._edit,
                                      **LINK_BUTTON)
        self.edit_btn.grid(row=3, column=0)
        self.toast = Toast(right, rtl)
        self.toast.grid(row=4, column=0, sticky="ew", padx=20, pady=(4, 16))

        self._stacked: bool | None = None
        self._has_results = False
        self.bind("<Configure>", self._on_resize)
        self._layout(False)

    def _on_resize(self, event) -> None:
        if event.width > 1:
            scale = getattr(self, "_get_widget_scaling", lambda: 1.0)()
            self._layout(event.width / scale < 760)

    def _layout(self, stacked: bool, force: bool = False) -> None:
        if stacked == self._stacked and not force:
            return
        self._stacked = stacked
        for card in (self.left, self.right):
            card.grid_forget()
        for i in range(2):
            self.grid_columnconfigure(i, weight=0, uniform="")
            self.grid_rowconfigure(i, weight=0, uniform="")
        if not self._has_results:
            self.grid_columnconfigure(0, weight=1)
            self.grid_rowconfigure(0, weight=1)
            self.left.grid(row=0, column=0, sticky="nsew")
        elif stacked:
            self.grid_columnconfigure(0, weight=1)
            self.grid_rowconfigure(0, weight=1, uniform="rows")
            self.grid_rowconfigure(1, weight=1, uniform="rows")
            self.left.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
            self.right.grid(row=1, column=0, sticky="nsew")
        else:
            left_col, right_col = (1, 0) if self.rtl else (0, 1)
            self.grid_rowconfigure(0, weight=1)
            self.grid_columnconfigure((0, 1), weight=1, uniform="cols")
            self.left.grid(row=0, column=left_col, sticky="nsew", padx=(12, 0) if self.rtl else (0, 12))
            self.right.grid(row=0, column=right_col, sticky="nsew")

    def _show_image(self) -> None:
        if self._image is None:
            return
        box_w = max(120, self.stage.winfo_width() - 40)
        box_h = max(120, self.stage.winfo_height() - 40)
        w, h = self._image.size
        scale = min(box_w / w, box_h / h, 1.0)
        size = (max(1, int(w * scale)), max(1, int(h * scale)))
        self.image_label.configure(image=ctk.CTkImage(self._image, self._image, size=size), text="")

    def _open(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff"),
                                    ("All files", "*.*")])
        if not path:
            return
        try:
            with Image.open(path) as im:
                self._load(im.copy())
        except (OSError, UnidentifiedImageError):
            self.status.configure(text=self.t("logo_failed"), text_color=DANGER)

    def _paste(self) -> None:
        try:
            data = ImageGrab.grabclipboard()
        except (OSError, NotImplementedError):
            data = None
        if isinstance(data, list) and data:
            try:
                with Image.open(data[0]) as im:
                    data = im.copy()
            except (OSError, UnidentifiedImageError):
                data = None
        if not isinstance(data, Image.Image):
            self.status.configure(text=self.t("scan_no_clipboard"), text_color=DANGER)
            return
        self._load(data)

    def _load(self, image: Image.Image) -> None:
        self._image = image
        self._show_image()
        self.results = scanner.decode(image)
        self.textbox.delete("1.0", "end")
        if self.results:
            self.textbox.insert("1.0", "\n\n———\n\n".join(self.results))
            self.result_title.configure(text=self.t("scan_found", count=len(self.results)))
            self.status.configure(text="✓ " + self.t("scan_found", count=len(self.results)), text_color=SUCCESS)
        else:
            self.status.configure(text=self.t("scan_none"), text_color=DANGER)
        self._has_results = bool(self.results)
        self._layout(bool(self._stacked), force=True)
        self._update_buttons()

    def _first(self) -> str:
        return self.results[0] if self.results else ""

    def _update_buttons(self) -> None:
        """Show only the actions that make sense: "Open link" only for links."""
        is_link = self._first().lower().startswith(("http://", "https://"))
        for w in (self.link_btn, self.copy_btn):
            w.grid_forget()
        shown = [self.link_btn, self.copy_btn] if is_link else [self.copy_btn]
        for i, w in enumerate(reversed(shown) if self.rtl else shown):
            w.grid(row=0, column=i, padx=5)

    def _copy(self) -> None:
        self.clipboard_clear()
        self.clipboard_append("\n".join(self.results))
        self.toast.show(self.t("copied_text"), SUCCESS)

    def _open_link(self) -> None:
        if self._first():
            webbrowser.open(self._first())

    def _edit(self) -> None:
        text = self._first()
        if not text:
            return
        if text.lower().startswith(("http://", "https://")):
            self.app.open_in_creator("url", {"url": text})
        else:
            self.app.open_in_creator("text", {"text": text})
