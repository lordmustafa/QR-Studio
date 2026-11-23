"""Main window: sidebar navigation and the four pages."""

from __future__ import annotations

import copy
import sys

import customtkinter as ctk
from PIL import ImageTk

from ..brand import logo
from ..i18n import LANGUAGES, SYSTEM, Translator, resolve_language
from ..payloads import CONTENT_TYPES
from ..renderer import QRStyle
from ..storage import Config, History, HistoryEntry
from .batch_page import BatchPage
from .create_page import CreatePage
from .history_page import HistoryPage
from .scan_page import ScanPage
from .icons import WHITE, icon
from .widgets import ACCENT, ACCENT_HOVER, BG, BORDER, CARD_ALT, MENU_STYLE, MUTED, SIDEBAR, TEXT, font

PAGES = ("create", "batch", "scan", "history")
PAGE_ICONS = {"create": "＋", "batch": "▦", "scan": "⌕", "history": "↺"}
THEMES = ("system", "light", "dark")
DEFAULT_SIZE = (1360, 840)
MIN_SIZE = (620, 560)
COMPACT_BELOW = 1000  # window width under which the sidebar shows icons only
SIDEBAR_FULL = 220
SIDEBAR_COMPACT = 64
# Never written to disk: form values with these keys stay in memory only.
SECRET_FIELDS = {"password"}


class App(ctk.CTk):
    def __init__(self):
        self.config_data = Config.load()
        ctk.set_appearance_mode(self.config_data.theme)
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=BG)

        self.history = History()
        self.style = QRStyle.from_dict(self.config_data.style)
        self.content_type = self.config_data.content_type if self.config_data.content_type in CONTENT_TYPES else "url"
        self.values: dict[str, dict] = {k: dict(v) for k, v in self.config_data.values.items()
                                        if isinstance(v, dict)}
        self.current_page = "create"
        self.t = Translator(resolve_language(self.config_data.language))

        self.title("QR Studio")
        self._initial_geometry()
        self._set_icon()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        mod = "Command" if sys.platform == "darwin" else "Control"
        self.bind_all(f"<{mod}-s>", lambda _e: self._shortcut_save())
        self.build()
        self.bind("<Configure>", self._on_window_resize, add="+")

    # ------------------------------------------------------------------ layout
    def _scaling(self) -> float:
        getter = getattr(self, "_get_window_scaling", None)
        return getter() if getter else 1.0

    def _initial_geometry(self) -> None:
        """Fit the first window into the screen (laptops can be smaller than the default)."""
        scale = self._scaling()
        screen_w = int(self.winfo_screenwidth() / scale)
        screen_h = int(self.winfo_screenheight() / scale)
        width = max(MIN_SIZE[0], min(DEFAULT_SIZE[0], screen_w - 60))
        height = max(MIN_SIZE[1], min(DEFAULT_SIZE[1], screen_h - 110))
        self.geometry(f"{width}x{height}+{max(0, (screen_w - width) // 2)}+{max(0, (screen_h - height) // 3)}")
        self.minsize(*MIN_SIZE)

    def build(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        rtl = self.t.rtl
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0 if not rtl else 1)
        self.grid_columnconfigure(1, weight=1 if not rtl else 0)

        self.sidebar = ctk.CTkFrame(self, fg_color=SIDEBAR, corner_radius=0, border_width=0)
        self.sidebar.grid(row=0, column=1 if rtl else 0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.pack_propagate(False)

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=0 if rtl else 1, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.pages = {}
        self._compact = None
        self._set_compact(self._wants_compact(self.winfo_width()))

        self.pages = {
            "create": CreatePage(self.container, self),
            "batch": BatchPage(self.container, self),
            "scan": ScanPage(self.container, self),
            "history": HistoryPage(self.container, self),
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")
        self.show_page(self.current_page)

    def _wants_compact(self, width: int) -> bool:
        return 1 < width / self._scaling() < COMPACT_BELOW

    def _on_window_resize(self, event) -> None:
        if event.widget is self:
            self._set_compact(self._wants_compact(event.width))

    def _set_compact(self, compact: bool) -> None:
        """Full sidebar with labels, or a narrow icon bar on small windows."""
        if compact == self._compact:
            return
        self._compact = compact
        self.sidebar.configure(width=SIDEBAR_COMPACT if compact else SIDEBAR_FULL)
        pad = 12 if compact else 22
        self.container.grid(padx=pad, pady=pad)
        for child in self.sidebar.winfo_children():
            child.destroy()
        self._build_sidebar()
        if self.pages:
            self.show_page(self.current_page)

    def _build_sidebar(self) -> None:
        t, rtl, compact = self.t, self.t.rtl, self._compact
        bar = self.sidebar
        anchor = "e" if rtl else "w"
        icon_img = ctk.CTkImage(self._icon_image, self._icon_image, size=(36, 36) if compact else (40, 40))

        if compact:
            ctk.CTkLabel(bar, text="", image=icon_img).pack(pady=(20, 22))
        else:
            brand = ctk.CTkFrame(bar, fg_color="transparent")
            brand.pack(fill="x", padx=18, pady=(24, 26))
            brand_icon = ctk.CTkLabel(brand, text="", image=icon_img)
            titles = ctk.CTkFrame(brand, fg_color="transparent")
            ctk.CTkLabel(titles, text=t("app_title"), font=font(19, "bold"), text_color=TEXT, anchor=anchor
                         ).pack(fill="x")
            ctk.CTkLabel(titles, text=t("app_subtitle"), font=font(11), text_color=MUTED, anchor=anchor
                         ).pack(fill="x")
            brand_icon.pack(side="right" if rtl else "left")
            titles.pack(side="right" if rtl else "left", padx=10, fill="x", expand=True)

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for name in PAGES:
            btn = ctk.CTkButton(bar, text="" if compact else t("nav_" + name), image=icon(name, 20),
                                compound="right" if rtl else "left", anchor="center" if compact else anchor,
                                height=42, width=44 if compact else 140, corner_radius=10, font=font(14),
                                fg_color="transparent", text_color=TEXT, hover_color=CARD_ALT,
                                command=lambda n=name: self.show_page(n))
            btn.pack(fill="x", padx=10 if compact else 12, pady=3)
            self.nav_buttons[name] = btn

        bottom = ctk.CTkFrame(bar, fg_color="transparent")
        if compact:
            # Icon buttons: cycle the theme, switch the language.
            bottom.pack(side="bottom", fill="x", padx=10, pady=16)
            ctk.CTkFrame(bottom, height=1, fg_color=BORDER).pack(fill="x", pady=(0, 10))
            theme_icons = {"system": "◐", "light": "☀", "dark": "☾"}
            nxt = THEMES[(THEMES.index(self.config_data.theme) + 1) % len(THEMES)]
            small = dict(height=36, width=44, corner_radius=10, fg_color="transparent", border_width=1,
                         border_color=BORDER, text_color=TEXT, hover_color=CARD_ALT)
            ctk.CTkButton(bottom, text=theme_icons[self.config_data.theme], font=font(16),
                          command=lambda: self._cycle_theme(nxt), **small).pack(fill="x", pady=3)
            other = "en" if self.t.language == "ar" else "ar"
            ctk.CTkButton(bottom, text="EN" if other == "en" else "ع", font=font(14, "bold"),
                          command=lambda: self.set_language(other), **small).pack(fill="x", pady=3)
            return

        bottom.pack(side="bottom", fill="x", padx=18, pady=20)
        ctk.CTkFrame(bottom, height=1, fg_color=BORDER).pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(bottom, text=t("appearance"), font=font(12), text_color=MUTED, anchor=anchor).pack(fill="x")
        theme_labels = [t(f"theme_{m}") for m in THEMES]
        theme = ctk.CTkOptionMenu(bottom, values=theme_labels, height=32, corner_radius=8, font=font(13),
                                  **MENU_STYLE, command=lambda v: self.set_theme(THEMES[theme_labels.index(v)]))
        theme.set(t(f"theme_{self.config_data.theme}"))
        theme.pack(fill="x", pady=(4, 12))
        ctk.CTkLabel(bottom, text=t("language"), font=font(12), text_color=MUTED, anchor=anchor).pack(fill="x")
        lang_keys = [SYSTEM, *LANGUAGES]
        names = [t("lang_system"), *LANGUAGES.values()]
        lang = ctk.CTkOptionMenu(bottom, values=names, height=32, corner_radius=8, font=font(13),
                                 **MENU_STYLE, command=lambda v: self.set_language(lang_keys[names.index(v)]))
        lang.set(names[lang_keys.index(self.config_data.language)])
        lang.pack(fill="x", pady=(4, 0))

    def _cycle_theme(self, mode: str) -> None:
        self.set_theme(mode)
        self._compact = None  # rebuild the icon bar so the theme icon updates
        self._set_compact(True)

    def show_page(self, name: str) -> None:
        self.current_page = name
        page = self.pages[name]
        page.tkraise()
        if name == "history":
            page.refresh()
        for key, btn in self.nav_buttons.items():
            active = key == name
            btn.configure(image=icon(key, 20, WHITE, WHITE) if active else icon(key, 20),
                          fg_color=ACCENT if active else "transparent",
                          hover_color=ACCENT_HOVER if active else CARD_ALT,
                          text_color="#ffffff" if active else TEXT,
                          font=font(14, "bold" if active else "normal"))

    # ------------------------------------------------------------------ settings
    def set_theme(self, mode: str) -> None:
        self.config_data.theme = mode
        ctk.set_appearance_mode(mode)
        self.save_config()

    def set_language(self, setting: str) -> None:
        """``setting`` is "system", "ar" or "en"."""
        if setting == self.config_data.language:
            return
        self.config_data.language = setting
        self.save_config()
        language = resolve_language(setting)
        if language != self.t.language:
            self.t = Translator(language)
            self.after(10, self.build)

    def save_config(self) -> None:
        cfg = self.config_data
        cfg.style = self.style.to_dict()
        cfg.content_type = self.content_type
        cfg.values = {k: {f: v for f, v in vals.items() if f not in SECRET_FIELDS}
                      for k, vals in self.values.items()}
        try:
            cfg.save()
        except OSError:
            pass

    # ------------------------------------------------------------------ actions shared by pages
    def remember(self, payload: str) -> None:
        values = {k: v for k, v in self.values.get(self.content_type, {}).items() if k not in SECRET_FIELDS}
        try:
            self.history.add(self.content_type, values, payload, self.style.to_dict())
        except OSError:
            pass

    def load_entry(self, entry: HistoryEntry) -> None:
        self.style = QRStyle.from_dict(copy.deepcopy(entry.style))
        self.open_in_creator(entry.content_type, entry.values)

    def open_in_creator(self, content_type: str, values: dict) -> None:
        if content_type not in CONTENT_TYPES:
            content_type = "text"
        self.content_type = content_type
        self.values[content_type] = dict(values)
        self.current_page = "create"
        self.build()

    def _shortcut_save(self) -> None:
        if self.current_page == "create":
            self.pages["create"].save()

    def _set_icon(self) -> None:
        self._icon_image = logo(256)
        try:
            self._icon_photo = ImageTk.PhotoImage(self._icon_image)
            self.iconphoto(True, self._icon_photo)
        except Exception:  # some window managers refuse icons
            pass

    def _on_close(self) -> None:
        self.save_config()
        self.destroy()


def main() -> None:
    app = App()
    app.mainloop()
