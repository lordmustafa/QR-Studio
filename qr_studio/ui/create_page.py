"""The main page, laid out as three simple steps and a live preview.

1. What is the code for?   (big tiles: link, Wi-Fi, contact ...)
2. Enter the details       (only the fields of the chosen type)
3. Choose a look           (ready-made styles, two colours, a logo;
                            everything else is under "More options")

The preview card has one main action (Download) and two small ones (copy).
"""

from __future__ import annotations

import os
from datetime import datetime
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk
from PIL import Image

from .. import scanner, system
from ..exporter import EXTENSIONS, FORMATS, export
from ..payloads import CONTENT_TYPES, PayloadError, build_payload, field_errors, is_allowed, is_blank
from ..renderer import (
    EYE_STYLES,
    FILL_MODES,
    MAX_LOGO_SCALE,
    MODULE_STYLES,
    QRStyle,
    QRTooLongError,
    check_image,
    contrast_ratio,
    load_logo,
    relative_luminance,
    render,
)
from .icons import WHITE, icon
from .widgets import (
    ACCENT,
    ACCENT_HOVER,
    BORDER,
    CARD_ALT,
    DANGER,
    LINK_BUTTON,
    MENU_STYLE,
    MUTED,
    SECONDARY_BUTTON,
    SUCCESS,
    TEXT,
    WARNING,
    Card,
    check_box,
    Choice,
    ColorButton,
    Row,
    StepHeader,
    Toast,
    font,
    hint_label,
    section_title,
)

if TYPE_CHECKING:
    from .app import App

PREVIEW_RENDER_PX = 1000
TWO_COLUMNS_MIN = 760  # page width (CTk units) for editor and preview side by side
EXPORT_SIZES = ("256", "512", "1024", "2048", "4096")

PRESETS: dict[str, dict] = {
    "Classic": dict(fg="#000000", bg="#ffffff", fill_mode="solid", module_style="square",
                    eye_frame_style="square", eye_center_style="square", custom_eyes=False),
    "Ocean": dict(fg="#1d4ed8", fg2="#0891b2", bg="#ffffff", fill_mode="diagonal", module_style="rounded",
                  eye_frame_style="rounded", eye_center_style="rounded", custom_eyes=False),
    "Sunset": dict(fg="#e11d48", fg2="#d97706", bg="#ffffff", fill_mode="linear_v", module_style="circle",
                   eye_frame_style="rounded", eye_center_style="circle", custom_eyes=False),
    "Forest": dict(fg="#065f46", fg2="#65a30d", bg="#ffffff", fill_mode="radial", module_style="gapped",
                   eye_frame_style="leaf", eye_center_style="leaf", custom_eyes=False),
    "Royal": dict(fg="#4c1d95", fg2="#be185d", bg="#ffffff", fill_mode="linear_h", module_style="rounded",
                  eye_frame_style="circle", eye_center_style="circle", custom_eyes=True,
                  eye_frame_color="#be185d", eye_center_color="#4c1d95"),
    "Ink": dict(fg="#111827", bg="#fefce8", fill_mode="solid", module_style="vbars",
                eye_frame_style="rounded", eye_center_style="square", custom_eyes=True,
                eye_frame_color="#111827", eye_center_color="#a16207"),
}
_PRESET_THUMBS: dict[str, Image.Image] = {}


def preset_thumbnail(name: str) -> Image.Image:
    if name not in _PRESET_THUMBS:
        style = QRStyle(border=1, **PRESETS[name])
        _PRESET_THUMBS[name] = render("QR Studio", style, size=112, supersample=2).image
    return _PRESET_THUMBS[name]


class CreatePage(ctk.CTkFrame):
    def __init__(self, master, app: "App"):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.t = app.t
        self.rtl = app.t.rtl
        self._render_job = None
        self._check_job = None
        self._payload: str | None = None
        self._preview_image: Image.Image | None = None
        self._box = 380
        self._layout: str | None = None
        self._tab = "edit"
        self._more_open = False
        self._tile_cols = 0
        self._preset_cols = 0
        self._active_preset: str | None = None
        self.inputs: dict[str, tuple[str, object]] = {}

        self.editor = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.preview_card = Card(self)
        self.tabs = ctk.CTkSegmentedButton(self, height=36, font=font(14, "bold"), command=self._on_tab)

        self._build_editor()
        self._build_preview()
        self.bind("<Configure>", self._on_resize)
        self._apply_layout("two")
        self.schedule_render(10)

    # ------------------------------------------------------------------ helpers
    @property
    def style(self) -> QRStyle:
        return self.app.style

    def _anchor(self) -> str:
        return "e" if self.rtl else "w"

    def _side(self) -> str:
        return "right" if self.rtl else "left"

    def _scaling(self) -> float:
        getter = getattr(self, "_get_widget_scaling", None)
        return getter() if getter else 1.0

    # ------------------------------------------------------------------ responsive layout
    def _on_resize(self, event) -> None:
        # CTkFrame.bind listens on its inner canvas, which always fills the frame.
        if event.width > 1:
            width = event.width / self._scaling()
            self._apply_layout("two" if width >= TWO_COLUMNS_MIN else "one")

    def _apply_layout(self, layout: str, force: bool = False) -> None:
        if layout == self._layout and not force:
            return
        self._layout = layout
        for widget in (self.editor, self.preview_card, self.tabs):
            widget.grid_forget()
        for c in range(2):
            self.grid_columnconfigure(c, weight=0, minsize=0, uniform="")
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        if layout == "two":
            editor_col, preview_col = (1, 0) if self.rtl else (0, 1)
            self.grid_columnconfigure(editor_col, weight=5, uniform="cols")
            self.grid_columnconfigure(preview_col, weight=4, uniform="cols")
            self.editor.grid(row=0, column=editor_col, rowspan=2, sticky="nsew")
            self.preview_card.grid(row=0, column=preview_col, rowspan=2, sticky="nsew",
                                   padx=(0, 16) if self.rtl else (16, 0))
            return

        labels = [self.t("tab_edit"), self.t("preview")]
        self.tabs.configure(values=list(reversed(labels)) if self.rtl else labels)
        self.tabs.set(self.t("tab_edit") if self._tab == "edit" else self.t("preview"))
        self.grid_columnconfigure(0, weight=1)
        self.tabs.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        (self.editor if self._tab == "edit" else self.preview_card).grid(row=1, column=0, sticky="nsew")

    def _on_tab(self, label: str) -> None:
        self._tab = "edit" if label == self.t("tab_edit") else "preview"
        self._apply_layout("one", force=True)

    def _on_editor_resize(self, event) -> None:
        width = event.width / self._scaling()
        # Only column counts that divide the tiles evenly: 10 types -> 5 per row, 6 styles -> 6 or 3.
        tile_cols = 5
        preset_cols = 6 if width - 40 >= 6 * 84 else 3
        if tile_cols != self._tile_cols:
            self._tile_cols = tile_cols
            self._grid_tiles(self.type_tiles, tile_cols)
        if preset_cols != self._preset_cols:
            self._preset_cols = preset_cols
            self._grid_tiles(self.preset_tiles, preset_cols)

    def _grid_tiles(self, tiles: list, cols: int) -> None:
        if not tiles:
            return
        parent = tiles[0].master
        for c in range(6):
            parent.grid_columnconfigure(c, weight=1 if c < cols else 0, uniform="tile" if c < cols else "")
        for i, tile in enumerate(tiles):
            col = cols - 1 - i % cols if self.rtl else i % cols
            tile.grid(row=i // cols, column=col, padx=4, pady=4, sticky="ew")

    # ------------------------------------------------------------------ editor: the three steps
    def _section(self) -> Card:
        card = Card(self.editor, corner_radius=16)
        card.pack(fill="x", pady=(0, 14), padx=(0, 6) if not self.rtl else (6, 0))
        return card

    def _build_editor(self) -> None:
        t = self.t
        # 1. type
        card = self._section()
        StepHeader(card, 1, t("step_type"), self.rtl).pack(anchor=self._anchor(), padx=20, pady=(18, 12))
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=(0, 16))
        self.type_tiles: list[ctk.CTkButton] = []
        for key in CONTENT_TYPES:
            tile = ctk.CTkButton(grid, text=t(f"tile_{key}"), compound="top", height=74, corner_radius=12,
                                 font=font(13), command=lambda k=key: self._on_type_change(k))
            tile.key = key  # type: ignore[attr-defined]
            self.type_tiles.append(tile)
        self._paint_type_tiles()
        card.bind("<Configure>", self._on_editor_resize)

        # 2. details
        card = self._section()
        StepHeader(card, 2, t("step_content"), self.rtl).pack(anchor=self._anchor(), padx=20, pady=(18, 4))
        self.fields_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.fields_frame.pack(fill="x", padx=8, pady=(0, 16))
        self._build_fields()

        # 3. look
        self.style_card = self._section()
        self.preset_tiles: list[ctk.CTkButton] = []
        self._build_style()

    def _paint_type_tiles(self) -> None:
        for tile in self.type_tiles:
            selected = tile.key == self.app.content_type  # type: ignore[attr-defined]
            tile.configure(
                image=icon(tile.key, 26, WHITE, WHITE) if selected else icon(tile.key, 26),  # type: ignore
                fg_color=ACCENT if selected else CARD_ALT,
                hover_color=ACCENT_HOVER if selected else BORDER,
                text_color="#ffffff" if selected else TEXT,
            )

    def _on_type_change(self, key: str) -> None:
        if key == self.app.content_type:
            return
        self.app.content_type = key
        self._paint_type_tiles()
        self._build_fields()
        self.schedule_render()

    # ------------------------------------------------------------------ step 2: fields
    def _build_fields(self) -> None:
        """One block per field: label, input, and an error line that shows only when needed."""
        t = self.t
        for child in self.fields_frame.winfo_children():
            child.destroy()
        self.inputs.clear()
        self._errors_ui: dict[str, tuple[ctk.CTkLabel, object]] = {}
        self._touched: set[str] = set()
        ctype = CONTENT_TYPES[self.app.content_type]
        values = self.app.values.setdefault(ctype.key, {})
        first_widget = None

        for f in ctype.fields:
            block = ctk.CTkFrame(self.fields_frame, fg_color="transparent")
            block.pack(fill="x", padx=12, pady=(12, 0))
            label_text = t(f"f_{f.key}") + (" *" if f.required else "")
            if f.kind == "check":
                var = ctk.BooleanVar(value=bool(values.get(f.key, f.default)))
                check_box(block, label_text, var, self._on_input, self.rtl).pack(anchor=self._anchor())
                self.inputs[f.key] = ("check", var)
                continue

            ctk.CTkLabel(block, text=label_text, font=font(13), text_color=MUTED,
                         anchor=self._anchor()).pack(fill="x", pady=(0, 4))
            if f.kind == "combo":
                var = ctk.StringVar(value=str(values.get(f.key, f.default)))
                ctk.CTkSegmentedButton(block, values=list(f.options), variable=var, height=34, font=font(13),
                                       command=lambda _v: self._on_input()).pack(fill="x")
                self.inputs[f.key] = ("combo", var)
                continue

            if f.kind == "text":
                widget = ctk.CTkTextbox(block, height=110, wrap="word", font=font(14), border_width=1,
                                        border_color=BORDER, corner_radius=10)
                widget.insert("1.0", values.get(f.key, ""))
                inner = widget._textbox
                kind = "text"
            else:
                ltr_field = bool(f.hint) or f.kind == "password"
                widget = ctk.CTkEntry(block, height=40, corner_radius=10, font=font(14), border_color=BORDER,
                                      placeholder_text=t(f.hint) if f.hint else "",
                                      show="•" if f.kind == "password" else "",
                                      justify="right" if self.rtl and not ltr_field else "left")
                if values.get(f.key):
                    widget.insert(0, values[f.key])
                inner = widget._entry
                kind = "entry"
                if f.allowed:
                    # Block characters that never belong in this field (letters in a phone number ...).
                    check = self.register(lambda text, a=f.allowed: is_allowed(a, text))
                    inner.configure(validate="key", validatecommand=(check, "%P"))
            widget.pack(fill="x")
            self.inputs[f.key] = (kind, widget)
            first_widget = first_widget or widget

            # Any change of the text (typing, deleting, paste, cut, undo) updates the code.
            inner.bind("<KeyRelease>", lambda _e: self._on_input(), add=True)
            for event in ("<<Paste>>", "<<Cut>>", "<<Clear>>", "<<Undo>>", "<<Redo>>"):
                inner.bind(event, lambda _e: self.after(1, self._on_input), add=True)
            inner.bind("<FocusOut>", lambda _e, k=f.key: self._touch(k), add=True)

            error = ctk.CTkLabel(block, text="", font=font(12), text_color=DANGER, anchor=self._anchor(),
                                 justify="right" if self.rtl else "left", wraplength=380)
            self._errors_ui[f.key] = (error, widget)

            if f.kind == "password":
                show_var = ctk.BooleanVar(value=False)
                check_box(block, t("show_password"), show_var,
                          lambda e=widget, v=show_var: e.configure(show="" if v.get() else "•"),
                          self.rtl, size=16, font_size=12).pack(anchor=self._anchor(), pady=(6, 0))

        if first_widget is not None:
            self.after(60, first_widget.focus_set)

    def _read_inputs(self) -> dict:
        values = {}
        for key, (kind, widget) in self.inputs.items():
            values[key] = widget.get("1.0", "end-1c") if kind == "text" else widget.get()
        return values

    def _on_input(self) -> None:
        self.app.values[self.app.content_type] = self._read_inputs()
        self._show_field_errors()
        self.schedule_render(120)

    def _touch(self, key: str) -> None:
        """A field was left: from now on its problems are shown (and cleared) as the user types."""
        if key not in self._touched:
            self._touched.add(key)
            self._show_field_errors()
            self.schedule_render(10)

    def _show_field_errors(self) -> dict[str, str]:
        values = self.app.values.get(self.app.content_type, {})
        errors = field_errors(self.app.content_type, values)
        for key, (label, widget) in self._errors_ui.items():
            message = errors.get(key) if key in self._touched else None
            if message:
                label.configure(text=self.t(message))
                if not label.winfo_ismapped():
                    label.pack(fill="x", pady=(4, 0), after=widget)
                widget.configure(border_color=DANGER)
            else:
                label.pack_forget()
                widget.configure(border_color=BORDER)
        return errors

    # ------------------------------------------------------------------ step 3: look
    def _build_style(self) -> None:
        card = self.style_card
        for child in card.winfo_children():
            child.destroy()
        t, s, rtl = self.t, self.style, self.rtl
        pad = dict(fill="x", padx=20)

        StepHeader(card, 3, t("step_style"), rtl).pack(anchor=self._anchor(), padx=20, pady=(18, 12))

        # ready-made styles, shown as real mini QR codes
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=16)
        self.preset_tiles = []
        for name in PRESETS:
            thumb = preset_thumbnail(name)
            selected = name == self._active_preset
            tile = ctk.CTkButton(grid, text=t(f"preset_{name}"), compound="top", height=96, corner_radius=12,
                                 image=ctk.CTkImage(thumb, thumb, size=(56, 56)), font=font(12),
                                 fg_color=CARD_ALT, hover_color=BORDER, text_color=TEXT,
                                 border_width=2, border_color=ACCENT if selected else CARD_ALT,
                                 command=lambda n=name: self._apply_preset(n))
            self.preset_tiles.append(tile)
        self._grid_tiles(self.preset_tiles, self._preset_cols or 6)

        # the two colours most people change
        colors = ctk.CTkFrame(card, fg_color="transparent")
        colors.pack(**pad, pady=(16, 4))
        for i, (label_key, attr) in enumerate((("code_color", "fg"), ("color_bg", "bg"))):
            box = ctk.CTkFrame(colors, fg_color="transparent")
            ctk.CTkLabel(box, text=t(label_key), font=font(13), text_color=MUTED,
                         anchor=self._anchor()).pack(fill="x")
            ColorButton(box, getattr(s, attr), lambda c, a=attr: self._set(a, c), width=130
                        ).pack(anchor=self._anchor(), pady=(4, 0))
            box.grid(row=0, column=(1 - i) if rtl else i, sticky="ew")
        colors.grid_columnconfigure((0, 1), weight=1)

        # logo
        logo_row = ctk.CTkFrame(card, fg_color="transparent")
        logo_row.pack(**pad, pady=(14, 4))
        if s.logo_path:
            logo = load_logo(s.logo_path)
            if logo is not None:
                logo.thumbnail((64, 64))
                h = max(1, 32 * logo.height // max(1, logo.width))
                ctk.CTkLabel(logo_row, text="", image=ctk.CTkImage(logo, logo, size=(32, h))
                             ).pack(side=self._side())
            ctk.CTkLabel(logo_row, text=os.path.basename(s.logo_path), font=font(13), text_color=TEXT
                         ).pack(side=self._side(), padx=10)
            ctk.CTkButton(logo_row, text=t("change_logo"), width=70, height=32, font=font(13),
                          command=self._choose_logo, **LINK_BUTTON).pack(side=self._side())
            ctk.CTkButton(logo_row, text=t("remove_logo"), width=70, height=32, font=font(13),
                          command=self._remove_logo, fg_color="transparent", hover_color=CARD_ALT,
                          text_color=DANGER).pack(side=self._side())
        else:
            ctk.CTkButton(logo_row, text=t("add_logo"), image=icon("logo", 18), height=36, corner_radius=10,
                          font=font(13), command=self._choose_logo, **SECONDARY_BUTTON).pack(side=self._side())

        # everything else, folded away
        arrow = "▾" if self._more_open else ("◂" if rtl else "▸")
        label = t("fewer_options" if self._more_open else "more_options")
        ctk.CTkButton(card, text=f"{arrow}  {label}" if rtl else f"{label}  {arrow}", height=36,
                      font=font(14, "bold"), anchor=self._anchor(), command=self._toggle_more, **LINK_BUTTON
                      ).pack(**pad, pady=(14, 4 if self._more_open else 16))
        if self._more_open:
            self._build_more(card)

    def _toggle_more(self) -> None:
        self._more_open = not self._more_open
        self._build_style()

    def _build_more(self, card) -> None:
        t, s, rtl = self.t, self.style, self.rtl
        body = ctk.CTkFrame(card, fg_color="transparent", corner_radius=12, border_width=1, border_color=BORDER)
        body.pack(fill="x", padx=16, pady=(0, 16))
        pad = dict(fill="x", padx=14)

        def group(title_key: str, first: bool = False) -> None:
            section_title(body, t(title_key), rtl).pack(**pad, pady=(14 if first else 18, 6))

        group("colors", first=True)
        self._choice_row(body, "fill_mode", [(m, t(f"fill_{m}")) for m in FILL_MODES], s.fill_mode,
                         lambda v: self._set("fill_mode", v, rebuild=True))
        if s.fill_mode != "solid":
            self._color_row(body, "color_fg2", "fg2")
        self._check(body, "transparent", "transparent")

        group("shapes")
        self._choice_row(body, "module_style", [(m, t(f"style_{m}")) for m in MODULE_STYLES], s.module_style,
                         lambda v: self._set("module_style", v))
        eye_opts = [(m, t(f"style_{m}")) for m in EYE_STYLES]
        self._choice_row(body, "eye_frame_style", eye_opts, s.eye_frame_style,
                         lambda v: self._set("eye_frame_style", v))
        self._choice_row(body, "eye_center_style", eye_opts, s.eye_center_style,
                         lambda v: self._set("eye_center_style", v))
        self._check(body, "custom_eyes", "custom_eyes", rebuild=True)
        if s.custom_eyes:
            self._color_row(body, "eye_frame_color", "eye_frame_color")
            self._color_row(body, "eye_center_color", "eye_center_color")

        if s.logo_path:
            group("logo")
            self._slider_row(body, "logo_size", 5, MAX_LOGO_SCALE * 100, int(s.logo_scale * 100), "%",
                             lambda v: self._set("logo_scale", v / 100))
            self._check(body, "logo_background", "logo_background")

        group("frame_caption")
        caption = ctk.CTkEntry(body, height=36, corner_radius=8, font=font(14), placeholder_text=t("caption_hint"),
                               justify="right" if rtl else "left")
        if s.caption:
            caption.insert(0, s.caption)
        caption.bind("<KeyRelease>", lambda _e: self._set("caption", caption.get()))
        caption.pack(**pad, pady=(0, 4))
        self._color_row(body, "caption_color", "caption_color")
        self._check(body, "frame", "frame", rebuild=True)
        if s.frame:
            self._color_row(body, "frame_color", "frame_color")

        group("quality_size")
        row = Row(body, t("ecc"), rtl)
        ecc = ctk.CTkSegmentedButton(row, values=["L", "M", "Q", "H"], width=160, font=font(13, "bold"),
                                     command=lambda v: self._set("error_correction", v))
        ecc.set(s.effective_ecc)
        if s.logo_path:
            ecc.configure(state="disabled")
        row.place_control(ecc)
        row.pack(**pad, pady=4)
        hint_label(body, t("logo_ecc_note") if s.logo_path else t("ecc_help"), rtl, wrap=340).pack(**pad)
        self._slider_row(body, "margin", 0, 10, s.border, "", lambda v: self._set("border", int(v)))
        row = Row(body, t("export_size"), rtl)
        size_menu = ctk.CTkOptionMenu(row, values=list(EXPORT_SIZES), width=120, height=32, corner_radius=8,
                                      font=font(13), command=lambda v: self._set("size", int(v), render=False),
                                      **MENU_STYLE)
        size_menu.set(str(s.size) if str(s.size) in EXPORT_SIZES else "1024")
        row.place_control(size_menu)
        row.pack(**pad, pady=4)

        ctk.CTkButton(body, text=t("reset_design"), height=32, font=font(13), anchor=self._anchor(),
                      command=self._reset_design, fg_color="transparent", hover_color=CARD_ALT, text_color=DANGER
                      ).pack(**pad, pady=(14, 12))

    def _choice_row(self, master, label_key, options, value, on_change) -> None:
        row = Row(master, self.t(label_key), self.rtl)
        row.place_control(Choice(row, options, value, on_change, width=170))
        row.pack(fill="x", padx=14, pady=4)

    def _color_row(self, master, label_key: str, attr: str) -> None:
        row = Row(master, self.t(label_key), self.rtl)
        row.place_control(ColorButton(row, getattr(self.style, attr), lambda c, a=attr: self._set(a, c)))
        row.pack(fill="x", padx=14, pady=4)

    def _check(self, master, label_key: str, attr: str, rebuild: bool = False) -> None:
        var = ctk.BooleanVar(value=bool(getattr(self.style, attr)))
        check_box(master, self.t(label_key), var, lambda: self._set(attr, var.get(), rebuild=rebuild),
                  self.rtl).pack(anchor=self._anchor(), padx=14, pady=5)

    def _slider_row(self, master, label_key, lo, hi, value, unit, on_change) -> None:
        row = Row(master, self.t(label_key), self.rtl)
        holder = ctk.CTkFrame(row, fg_color="transparent")
        value_label = ctk.CTkLabel(holder, text=f"{int(value)}{unit}", width=40, font=font(13), text_color=MUTED)

        def changed(v):
            value_label.configure(text=f"{int(round(v))}{unit}")
            on_change(round(v))

        slider = ctk.CTkSlider(holder, from_=lo, to=hi, number_of_steps=int(hi - lo), width=130, command=changed)
        slider.set(value)
        for w in ((value_label, slider) if self.rtl else (slider, value_label)):
            w.pack(side="left")
        row.place_control(holder)
        row.pack(fill="x", padx=14, pady=4)

    def _set(self, attr: str, value, rebuild: bool = False, render: bool = True) -> None:
        setattr(self.style, attr, value)
        if attr not in ("size", "caption", "border", "logo_scale") and self._active_preset:
            self._active_preset = None
            rebuild = True  # drop the highlight from the preset tile
        if rebuild:
            self._build_style()
        if render:
            self.schedule_render()

    def _apply_preset(self, name: str) -> None:
        for key, value in PRESETS[name].items():
            setattr(self.style, key, value)
        self._active_preset = name
        self._build_style()
        self.schedule_render()

    def _reset_design(self) -> None:
        fresh = QRStyle(size=self.style.size)
        for key, value in fresh.to_dict().items():
            setattr(self.style, key, value)
        self._active_preset = "Classic"
        self._build_style()
        self.schedule_render()

    def _choose_logo(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title=self.t("add_logo"),
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.ico"), ("All files", "*.*")],
        )
        if not path:
            return
        if load_logo(path) is None:
            messagebox.showerror(self.t("error"), self.t("logo_failed"), parent=self)
            return
        self.style.logo_path = path
        self._build_style()
        self.schedule_render()

    def _remove_logo(self) -> None:
        self.style.logo_path = ""
        self._build_style()
        self.schedule_render()

    # ------------------------------------------------------------------ preview card
    def _build_preview(self) -> None:
        t = self.t
        card = self.preview_card
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)

        self.stage = ctk.CTkFrame(card, fg_color=CARD_ALT, corner_radius=16)
        self.stage.grid(row=0, column=0, sticky="nsew", padx=20, pady=(20, 10))
        self.stage.grid_rowconfigure(0, weight=1)
        self.stage.grid_columnconfigure(0, weight=1)
        # Two labels that take turns: the code picture, or a message. The picture label always has
        # an image: setting a CTkLabel's image to None leaves the Tk label pointing at a deleted
        # picture, and the next update failed ("image doesn't exist"), which froze the preview.
        blank = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        self._qr_image = ctk.CTkImage(blank, blank, size=(1, 1))
        self.qr_label = ctk.CTkLabel(self.stage, text="", image=self._qr_image)
        self.message_label = ctk.CTkLabel(self.stage, text=t("placeholder_preview"), font=font(15),
                                          text_color=MUTED, wraplength=320)
        self.qr_label.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        self.message_label.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        self.qr_label.grid_remove()
        self.stage.bind("<Configure>", self._on_stage_resize)

        self.status_label = ctk.CTkLabel(card, text="", font=font(13), anchor="center", wraplength=380)
        self.status_label.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 6))

        # main action: download, with the file type beside it
        main = ctk.CTkFrame(card, fg_color="transparent")
        main.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 0))
        fmt = self.app.config_data.export_format
        self.format_menu = ctk.CTkOptionMenu(main, values=list(FORMATS), width=92, height=46, corner_radius=12,
                                             font=font(14, "bold"), command=lambda _v: self._label_download(),
                                             **MENU_STYLE)
        self.format_menu.set(fmt if fmt in FORMATS else "PNG")
        self.save_btn = ctk.CTkButton(main, text="", image=icon("download", 20, WHITE, WHITE), height=46,
                                      corner_radius=12, font=font(16, "bold"), fg_color=ACCENT,
                                      hover_color=ACCENT_HOVER, text_color="#ffffff",
                                      text_color_disabled="#dbe4ff", command=self.save)
        self._label_download()
        main.grid_columnconfigure(1 if self.rtl else 0, weight=1)
        self.save_btn.grid(row=0, column=1 if self.rtl else 0, sticky="ew")
        self.format_menu.grid(row=0, column=0 if self.rtl else 1, padx=(0, 8) if self.rtl else (8, 0))

        # small actions
        small = ctk.CTkFrame(card, fg_color="transparent")
        small.grid(row=3, column=0, pady=(8, 0))
        self.copy_img_btn = ctk.CTkButton(small, text=t("copy_image"), image=icon("copy", 16), width=130, height=34,
                                          font=font(13), command=self.copy_image, **LINK_BUTTON)
        self.copy_txt_btn = ctk.CTkButton(small, text=t("copy_text"), image=icon("text", 16), width=130, height=34,
                                          font=font(13), command=self.copy_text, **LINK_BUTTON)
        for i, w in enumerate((self.copy_txt_btn, self.copy_img_btn) if self.rtl else
                              (self.copy_img_btn, self.copy_txt_btn)):
            w.grid(row=0, column=i, padx=4)

        self.toast = Toast(card, self.rtl)
        self.toast.grid(row=4, column=0, sticky="ew", padx=20, pady=(4, 14))
        self._set_actions_enabled(False)
        card.bind("<Configure>", self._on_preview_resize)

    def _label_download(self) -> None:
        self.save_btn.configure(text=f"  {self.t('download')} {self.format_menu.get()}")

    def _on_preview_resize(self, event) -> None:
        if event.width > 1:
            wrap = max(200, int(event.width / self._scaling()) - 50)
            self.status_label.configure(wraplength=wrap)
            self.toast.label.configure(wraplength=max(160, wrap - 130))

    def _set_actions_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for btn in (self.save_btn, self.copy_img_btn, self.copy_txt_btn):
            btn.configure(state=state)

    def _on_stage_resize(self, event) -> None:
        box = max(120, int(min(event.width, event.height) / self._scaling()) - 40)
        if abs(box - self._box) > 4:
            self._box = box
            self._show_image()

    def _show_image(self) -> None:
        img = self._preview_image
        if img is None:
            return
        w, h = img.size
        scale = min(self._box / w, self._box / h)
        size = (max(1, int(w * scale)), max(1, int(h * scale)))
        self._qr_image = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        self.qr_label.configure(image=self._qr_image)
        self.message_label.grid_remove()
        self.qr_label.grid()

    def _clear_preview(self, message: str, color=MUTED) -> None:
        self._payload = None
        self._preview_image = None
        self.qr_label.grid_remove()
        self.message_label.configure(text=message, text_color=color)
        self.message_label.grid()
        self.status_label.configure(text="")
        self._set_actions_enabled(False)

    # ------------------------------------------------------------------ rendering
    def schedule_render(self, delay: int = 160) -> None:
        if self._render_job:
            self.after_cancel(self._render_job)
        self._render_job = self.after(delay, self._render)

    def _render(self) -> None:
        self._render_job = None
        values = self.app.values.get(self.app.content_type, {})
        try:
            payload = build_payload(self.app.content_type, values)
        except PayloadError as err:
            if is_blank(self.app.content_type, values):
                self._clear_preview(self.t("placeholder_preview"))
            elif err.field in getattr(self, "_touched", set()):
                self._clear_preview(self.t("fix_fields"), WARNING)  # the field itself says what is wrong
            else:
                self._clear_preview(self.t("complete_fields"))  # still typing: no red yet
            return
        try:
            result = render(payload, self.style, size=PREVIEW_RENDER_PX, supersample=2)
        except QRTooLongError:
            self._clear_preview(self.t("err_too_long"), DANGER)
            return
        except Exception as exc:  # never leave the preview stuck on an old picture
            self._clear_preview(f"{self.t('error')}: {exc}", DANGER)
            return

        self._payload = payload
        self._preview_image = result.image
        self._show_image()
        self._set_actions_enabled(True)
        warning = self._contrast_warning()
        if warning:
            self.status_label.configure(text=warning, text_color=WARNING)
        else:
            self.status_label.configure(text=self.t("status_checking"), text_color=MUTED)
        if self._check_job:
            self.after_cancel(self._check_job)
        self._check_job = self.after(250, lambda p=payload: self._run_check(p, warning))

    def _contrast_warning(self) -> str:
        s = self.style
        bg = "#ffffff" if s.transparent else s.bg
        colors = [s.fg] + ([s.fg2] if s.fill_mode != "solid" else [])
        if s.custom_eyes:
            colors += [s.eye_frame_color, s.eye_center_color]
        if any(relative_luminance(c) > relative_luminance(bg) for c in colors):
            return self.t("warn_inverted")
        worst = min(contrast_ratio(c, bg) for c in colors)
        if worst < 3:
            return self.t("warn_contrast", ratio=f"{worst:.1f}")
        return ""

    def _run_check(self, payload: str, warning: str) -> None:
        self._check_job = None
        if payload != self._payload:
            return
        if not scanner.AVAILABLE:
            if not warning:
                self.status_label.configure(text="")
            return
        result = scanner.verify(check_image(payload, self.style), payload)
        if result == "match":
            if not warning:
                self.status_label.configure(text=self.t("status_ready"), text_color=SUCCESS)
        else:
            self.status_label.configure(text=self.t(f"check_{result}"), text_color=WARNING)

    # ------------------------------------------------------------------ actions
    def save(self) -> None:
        if not self._payload:
            return
        fmt = self.format_menu.get()
        ext = EXTENSIONS[fmt]
        name = f"qr-{self.app.content_type}-{datetime.now():%Y%m%d-%H%M%S}{ext}"
        path = filedialog.asksaveasfilename(
            parent=self, initialdir=self.app.config_data.save_dir, initialfile=name,
            defaultextension=ext, filetypes=[(fmt, f"*{ext}")],
        )
        if not path:
            return
        try:
            final = export(self._payload, self.style, path, fmt)
        except Exception as exc:  # show any save problem to the user
            messagebox.showerror(self.t("error"), self.t("save_failed", error=exc), parent=self)
            return
        self.app.config_data.save_dir = str(final.parent)
        self.app.config_data.export_format = fmt
        self.app.remember(self._payload)
        self.toast.show(self.t("saved_to", path=final.name), SUCCESS,
                        action=(self.t("show_in_folder"), lambda: system.reveal(final)), timeout=12000)

    def copy_image(self) -> None:
        if not self._payload:
            return
        image = render(self._payload, self.style).image
        if system.copy_image(image):
            self.app.remember(self._payload)
            self.toast.show(self.t("copied_image"), SUCCESS)
        else:
            self.toast.show(self.t("copy_failed"), WARNING)

    def copy_text(self) -> None:
        if not self._payload:
            return
        self.clipboard_clear()
        self.clipboard_append(self._payload)
        self.toast.show(self.t("copied_text"), SUCCESS)
