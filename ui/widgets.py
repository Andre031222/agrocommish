import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from ui import theme as th
from ui.icons import icon

TONE_ICONS = {"success": "circle-check-big", "warn": "triangle-alert",
              "error": "x", "info": "info", "accent": "check"}


def load_logo(path: Path, size: int) -> "ctk.CTkImage | None":
    try:
        img = Image.open(path).convert("RGBA").resize((size * 2, size * 2), Image.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    except (OSError, ValueError):
        return None


def card(parent, **pack) -> ctk.CTkFrame:
    frame = ctk.CTkFrame(parent, fg_color=th.CARD, corner_radius=16, border_width=0)
    frame.pack(**({"fill": "x", "pady": (0, 14)} | pack))
    return frame


def separator(parent, **pack) -> ctk.CTkFrame:
    line = ctk.CTkFrame(parent, height=1, fg_color=th.SEP, corner_radius=0)
    line.pack(**({"fill": "x"} | pack))
    return line


def _with_icon(kw: dict, name, color, size=18) -> dict:
    if name:
        kw.setdefault("image", icon(name, size, color))
        kw.setdefault("compound", "left")
    return kw


def primary_button(parent, text, command, fonts, tone=th.ACCENT, hover=th.ACCENT_DK, icon_name=None, **kw):
    kw = _with_icon(kw, icon_name, th.ON_ACCENT)
    return ctk.CTkButton(parent, text=text, command=command, height=kw.pop("height", 46),
                         fg_color=tone, hover_color=hover, text_color=th.ON_ACCENT,
                         font=fonts.body_b, corner_radius=12, **kw)


def secondary_button(parent, text, command, fonts, icon_name=None, **kw):
    color = kw.pop("text_color", th.TEXT)
    kw = _with_icon(kw, icon_name, color)
    return ctk.CTkButton(parent, text=text, command=command, height=kw.pop("height", 42),
                         fg_color=th.INPUT, hover_color=th.HOVER, text_color=color,
                         border_width=1, border_color=th.SEP,
                         font=kw.pop("font", fonts.body), corner_radius=12, **kw)


def ghost_button(parent, text, command, fonts, icon_name=None, **kw):
    color = kw.pop("text_color", th.INFO)
    kw = _with_icon(kw, icon_name, color, 16)
    return ctk.CTkButton(parent, text=text, command=command, height=kw.pop("height", 34),
                         fg_color="transparent", hover_color=th.HOVER, text_color=color,
                         font=kw.pop("font", fonts.small), corner_radius=10, **kw)


def entry(parent, fonts, variable, placeholder="", **kw):
    return ctk.CTkEntry(parent, textvariable=variable, placeholder_text=placeholder,
                        height=kw.pop("height", 46), font=kw.pop("font", fonts.body),
                        fg_color=th.INPUT, border_color=th.SEP, border_width=1,
                        text_color=th.TEXT, placeholder_text_color=th.TEXT3,
                        corner_radius=12, **kw)


def eyebrow(parent, fonts, **kw) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, font=fonts.eyebrow, text_color=th.TEXT3, anchor="w", **kw)


class Banner(ctk.CTkFrame):

    def __init__(self, parent, fonts, tone="info", text=""):
        super().__init__(parent, corner_radius=12)
        self._icon = ctk.CTkLabel(self, text="", width=22)
        self._icon.pack(side="left", padx=(16, 0), pady=12, anchor="n")
        self.label = ctk.CTkLabel(self, text=text, font=fonts.small, justify="left",
                                  anchor="w", wraplength=720)
        self.label.pack(side="left", fill="x", expand=True, padx=(10, 16), pady=12)
        self.set(text, tone)

    def set(self, text: str, tone: str):
        fg, bg = th.TONES[tone]
        self.configure(fg_color=bg)
        self._icon.configure(image=icon(TONE_ICONS[tone], 18, fg))
        self.label.configure(text=text, text_color=fg)


class SplashScreen:

    def __init__(self, master, fonts, logo_path: Path, subtitle: str, steps, on_done):
        self._on_done = on_done
        w, h = 440, 300
        self._win = ctk.CTkToplevel(master)
        self._win.overrideredirect(True)
        self._win.configure(fg_color=th.BG)
        x = (self._win.winfo_screenwidth() - w) // 2
        y = (self._win.winfo_screenheight() - h) // 2
        self._win.geometry(f"{w}x{h}+{x}+{y}")

        box = ctk.CTkFrame(self._win, fg_color=th.BG, corner_radius=20,
                           border_width=1, border_color=th.SEP)
        box.pack(fill="both", expand=True)
        logo = load_logo(logo_path, 64)
        if logo:
            self._logo = logo
            ctk.CTkLabel(box, image=logo, text="").pack(pady=(40, 0))
        ctk.CTkLabel(box, text="AgroCommish", font=fonts.title, text_color=th.TEXT).pack(pady=(14, 0))
        ctk.CTkLabel(box, text=subtitle, font=fonts.small, text_color=th.TEXT3).pack()
        self._bar = ctk.CTkProgressBar(box, width=300, height=4, corner_radius=2,
                                       fg_color=th.SEP, progress_color=th.ACCENT)
        self._bar.set(0)
        self._bar.pack(pady=(26, 0))
        self._lbl = ctk.CTkLabel(box, text="", font=fonts.caption, text_color=th.TEXT3)
        self._lbl.pack(pady=(10, 0))

        self._win.lift()
        self._win.update()
        for delay, progress, text in steps:
            self._win.after(delay, lambda p=progress, t=text: self._tick(p, t))

    def _tick(self, progress: float, text):
        if not self._win.winfo_exists():
            return
        if text is None:
            self._win.destroy()
            self._on_done()
            return
        inicio = self._bar.get()
        th.animate(self._win, 200, lambda e: self._bar.set(inicio + (progress - inicio) * e))
        self._lbl.configure(text=text)


class Toast:

    _active: "Toast | None" = None

    def __init__(self, master, fonts, tone: str, title: str, detail: str = "", ms: int = 3200):
        if Toast._active:
            Toast._active.close()
        Toast._active = self
        self._master = master
        self._alive = True
        fg, bg = th.TONES.get(tone, th.TONES["info"])

        self._frame = ctk.CTkFrame(master, fg_color=th.BG, corner_radius=14,
                                   border_width=1, border_color=th.SEP)
        row = ctk.CTkFrame(self._frame, fg_color="transparent")
        row.pack(padx=14, pady=12)
        ctk.CTkLabel(row, text="", image=icon(TONE_ICONS.get(tone, "info"), 18, fg), width=34,
                     height=34, fg_color=bg, corner_radius=17).pack(side="left", anchor="n")
        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", padx=(12, 4))
        ctk.CTkLabel(col, text=title, font=fonts.body_b, text_color=th.TEXT, anchor="w").pack(anchor="w")
        if detail:
            ctk.CTkLabel(col, text=detail, font=fonts.small, text_color=th.TEXT3, anchor="w",
                         justify="left", wraplength=340).pack(anchor="w")

        self._frame.place(relx=0.985, y=-100, anchor="ne")
        self._slide(-100, 18, lambda: master.after(ms, self._leave))

    def _slide(self, y0: int, y1: int, on_done=None):
        def frame(e):
            if self._alive:
                self._frame.place_configure(y=int(y0 + (y1 - y0) * e))
        th.animate(self._frame, 240, frame, on_done)

    def _leave(self):
        if self._alive:
            self._slide(18, -100, self.close)

    def close(self):
        if not self._alive:
            return
        self._alive = False
        if Toast._active is self:
            Toast._active = None
        try:
            self._frame.destroy()
        except tk.TclError:
            pass
