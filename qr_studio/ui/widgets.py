"""Small reusable widgets and the colour palette of the app."""

from __future__ import annotations

from tkinter import colorchooser
from typing import Callable, Iterable

import customtkinter as ctk

from ..renderer import relative_luminance

# (light, dark) colour pairs
BG = ("#eef1f6", "#0f1218")
CARD = ("#ffffff", "#1a1f29")
CARD_ALT = ("#f6f8fb", "#222836")
BORDER = ("#e2e6ee", "#2b3242")
TEXT = ("#111827", "#e5e7eb")
MUTED = ("#6b7280", "#9ca3af")
ACCENT = ("#2563eb", "#3b82f6")
ACCENT_HOVER = ("#1d4ed8", "#2563eb")
SUCCESS = ("#047857", "#34d399")
WARNING = ("#b45309", "#fbbf24")
DANGER = ("#b91c1c", "#f87171")
SIDEBAR = ("#ffffff", "#141821")


# Quiet grey drop-downs: only the main action and the current choice use the accent colour.
MENU_STYLE = dict(fg_color=CARD_ALT, button_color=CARD_ALT, button_hover_color=BORDER, text_color=TEXT,
                  dropdown_fg_color=CARD, dropdown_hover_color=CARD_ALT, dropdown_text_color=TEXT)
SECONDARY_BUTTON = dict(fg_color="transparent", border_width=1, border_color=BORDER, text_color=TEXT,
                        hover_color=CARD_ALT)
LINK_BUTTON = dict(fg_color="transparent", hover_color=CARD_ALT, text_color=ACCENT, border_width=0)


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(size=size, weight=weight)


def text_on(color: str) -> str:
    try:
        return "#111111" if relative_luminance(color) > 0.45 else "#ffffff"
    except ValueError:
        return "#111111"


class Card(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", CARD)
        kwargs.setdefault("corner_radius", 16)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", BORDER)
        super().__init__(master, **kwargs)


class ScrollCard(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", CARD)
        kwargs.setdefault("corner_radius", 16)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", BORDER)
        super().__init__(master, **kwargs)


class Row(ctk.CTkFrame):
    """A label on one side and a control on the other (mirrored for RTL)."""

    def __init__(self, master, label: str, rtl: bool = False, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.rtl = rtl
        self.grid_columnconfigure(1 if rtl else 0, weight=1)
        self.label = ctk.CTkLabel(self, text=label, font=font(13), text_color=TEXT,
                                  anchor="e" if rtl else "w")
        self.label.grid(row=0, column=1 if rtl else 0, sticky="ew", padx=(0, 0))

    def place_control(self, widget) -> None:
        widget.grid(row=0, column=0 if self.rtl else 1, sticky="e" if not self.rtl else "w")


def section_title(master, text: str, rtl: bool = False) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=text, font=font(14, "bold"), text_color=TEXT,
                        anchor="e" if rtl else "w")


def hint_label(master, text: str, rtl: bool = False, wrap: int = 280) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=text, font=font(12), text_color=MUTED, wraplength=wrap,
                        justify="right" if rtl else "left", anchor="e" if rtl else "w")


class ColorButton(ctk.CTkButton):
    """A swatch that opens the system colour picker."""

    def __init__(self, master, color: str, on_change: Callable[[str], None], width: int = 112, **kwargs):
        self.color = color
        self._on_change = on_change
        super().__init__(master, width=width, height=30, corner_radius=8, border_width=1,
                         border_color=BORDER, command=self._pick, font=font(12, "bold"), **kwargs)
        self._paint()

    def _paint(self) -> None:
        self.configure(text=self.color.upper(), fg_color=self.color, hover_color=self.color,
                       text_color=text_on(self.color))

    def set(self, color: str) -> None:
        self.color = color
        self._paint()

    def _pick(self) -> None:
        _, hex_color = colorchooser.askcolor(color=self.color, parent=self.winfo_toplevel())
        if hex_color:
            self.set(hex_color)
            self._on_change(hex_color)


class Choice(ctk.CTkOptionMenu):
    """Option menu that shows translated labels but reports keys."""

    def __init__(self, master, options: Iterable[tuple[str, str]], value: str,
                 on_change: Callable[[str], None], width: int = 160, **kwargs):
        self._keys = [k for k, _ in options]
        self._labels = [label for _, label in options]
        self._on_change = on_change
        style = {**MENU_STYLE, **kwargs}
        super().__init__(master, values=self._labels, width=width, height=32, corner_radius=8,
                         command=self._changed, dynamic_resizing=False, font=font(13), **style)
        self.set_key(value)

    def set_key(self, key: str) -> None:
        if key in self._keys:
            self.set(self._labels[self._keys.index(key)])

    def get_key(self) -> str:
        label = self.get()
        return self._keys[self._labels.index(label)] if label in self._labels else self._keys[0]

    def _changed(self, label: str) -> None:
        self._on_change(self._keys[self._labels.index(label)])


class Toast(ctk.CTkFrame):
    """A one-line status message with an optional action button."""

    def __init__(self, master, rtl: bool = False):
        super().__init__(master, fg_color="transparent")
        self.rtl = rtl
        self.label = ctk.CTkLabel(self, text="", font=font(12), text_color=MUTED, wraplength=380,
                                  justify="right" if rtl else "left", anchor="e" if rtl else "w")
        self.label.pack(side="right" if rtl else "left", fill="x", expand=True)
        self.button: ctk.CTkButton | None = None
        self._job = None

    def show(self, text: str, color=MUTED, action: tuple[str, Callable[[], None]] | None = None,
             timeout: int | None = 6000) -> None:
        self.label.configure(text=text, text_color=color)
        if self.button is not None:
            self.button.destroy()
            self.button = None
        if action:
            self.button = ctk.CTkButton(self, text=action[0], command=action[1], width=110, height=26,
                                        fg_color="transparent", border_width=1, border_color=BORDER,
                                        text_color=TEXT, hover_color=CARD_ALT, font=font(12))
            self.button.pack(side="left" if self.rtl else "right", padx=6)
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        if timeout:
            self._job = self.after(timeout, self.clear)

    def clear(self) -> None:
        self._job = None
        if not self.winfo_exists():
            return
        self.label.configure(text="")
        if self.button is not None:
            self.button.destroy()
            self.button = None

    def destroy(self) -> None:
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        super().destroy()


def responsive_split(page, first, second, breakpoint: int, rtl: bool = False,
                     second_width: int | None = None) -> None:
    """Lay out two cards side by side, or stacked when ``page`` is narrower than ``breakpoint``.

    ``second_width`` fixes the side-by-side width of ``second`` (otherwise both share the width).
    """
    state = {"stacked": None}

    def scaling() -> float:
        getter = getattr(page, "_get_widget_scaling", None)
        return getter() if getter else 1.0

    def apply(stacked: bool) -> None:
        if state["stacked"] == stacked:
            return
        state["stacked"] = stacked
        for card in (first, second):
            card.grid_forget()
        for i in range(2):
            page.grid_columnconfigure(i, weight=0, minsize=0, uniform="")
            page.grid_rowconfigure(i, weight=0, uniform="")
        if stacked:
            page.grid_columnconfigure(0, weight=1)
            page.grid_rowconfigure(0, weight=1, uniform="rows")
            page.grid_rowconfigure(1, weight=1, uniform="rows")
            first.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
            second.grid(row=1, column=0, sticky="nsew")
            return
        first_col, second_col = (1, 0) if rtl else (0, 1)
        page.grid_rowconfigure(0, weight=1)
        if second_width:
            page.grid_columnconfigure(first_col, weight=1)
            page.grid_columnconfigure(second_col, weight=0, minsize=int(second_width * scaling()))
        else:
            page.grid_columnconfigure(first_col, weight=1, uniform="cols")
            page.grid_columnconfigure(second_col, weight=1, uniform="cols")
        first.grid(row=0, column=first_col, sticky="nsew", padx=(12, 0) if rtl else (0, 12))
        second.grid(row=0, column=second_col, sticky="nsew")

    def on_configure(event) -> None:
        # CTkFrame.bind listens on its inner canvas, which always fills the frame.
        if event.width > 1:
            apply(event.width / scaling() < breakpoint)

    page.bind("<Configure>", on_configure)
    apply(False)


class StepHeader(ctk.CTkFrame):
    """A numbered step title: (1) What is the code for?"""

    def __init__(self, master, number: int, title: str, rtl: bool = False):
        super().__init__(master, fg_color="transparent")
        badge = ctk.CTkLabel(self, text=str(number), width=26, height=26, corner_radius=13, fg_color=ACCENT,
                             text_color="#ffffff", font=font(13, "bold"))
        label = ctk.CTkLabel(self, text=title, font=font(16, "bold"), text_color=TEXT)
        side = "right" if rtl else "left"
        badge.pack(side=side)
        label.pack(side=side, padx=10)


def check_box(master, text: str, variable, command, rtl: bool = False, size: int = 20,
              font_size: int = 13) -> ctk.CTkFrame:
    """A checkbox whose box sits on the reading side: left in English, right in Arabic."""
    holder = ctk.CTkFrame(master, fg_color="transparent")
    box = ctk.CTkCheckBox(holder, text="", width=size, variable=variable, command=command,
                          checkbox_width=size, checkbox_height=size)
    label = ctk.CTkLabel(holder, text=text, font=font(font_size), text_color=TEXT, cursor="hand2")

    def toggle(_event=None):
        box.toggle()  # toggle() also runs ``command``

    label.bind("<Button-1>", toggle)
    side = "right" if rtl else "left"
    box.pack(side=side)
    label.pack(side=side, padx=(0, 6) if rtl else (6, 0))
    return holder
