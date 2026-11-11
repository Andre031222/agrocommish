import sys
import time
import tkinter.font as tkfont

import customtkinter as ctk

BG          = ("#FFFFFF", "#000000")
SIDEBAR     = ("#FAFAFC", "#0B0B0D")
CARD        = ("#F5F5F7", "#1C1C1E")
INPUT       = ("#FFFFFF", "#2C2C2E")
HOVER       = ("#EBEBF0", "#2C2C2E")
SEP         = ("#E5E5EA", "#2C2C2E")
TEXT        = ("#1D1D1F", "#F5F5F7")
TEXT2       = ("#3C3C43", "#D1D1D6")
TEXT3       = ("#6E6E73", "#98989D")
OFF         = ("#C7C7CC", "#48484A")
ON_ACCENT   = ("#FFFFFF", "#FFFFFF")

ACCENT      = ("#2E7D32", "#30D158")
ACCENT_DK   = ("#24642A", "#28B14A")
ACCENT_BG   = ("#E7F4E8", "#10261A")
INFO        = ("#0A66C2", "#64A8FF")
INFO_BG     = ("#EAF3FF", "#0E1E33")
SUCCESS     = ("#1E8E3E", "#30D158")
SUCCESS_BG  = ("#E8F5EC", "#0F2618")
WARN        = ("#B26A00", "#FF9F0A")
WARN_BG     = ("#FFF4E0", "#2B1E07")
DANGER      = ("#C62828", "#FF453A")
DANGER_BG   = ("#FDECEC", "#2D0F0E")
TERMINAL    = ("#F6F8FA", "#0D1117")
TERMINAL_FG = ("#24292F", "#C9D1D9")

TONES = {
    "success": (SUCCESS, SUCCESS_BG),
    "warn":    (WARN, WARN_BG),
    "error":   (DANGER, DANGER_BG),
    "info":    (INFO, INFO_BG),
    "accent":  (ACCENT, ACCENT_BG),
}

APPEARANCES = ("system", "light", "dark")

_SANS = ("SF Pro Text", ".AppleSystemUIFont", "Segoe UI Variable Text",
         "Segoe UI", "Inter", "Ubuntu", "Helvetica Neue", "Helvetica", "Arial")
_MONO = ("SF Mono", "Menlo", "Cascadia Mono", "Consolas", "JetBrains Mono",
         "DejaVu Sans Mono", "Courier New")

_SCALE = 1.0 if sys.platform == "darwin" else 0.82


class Fonts:

    def __init__(self):
        familias = set(tkfont.families())
        sans = next((f for f in _SANS if f in familias), "TkDefaultFont")
        mono = next((f for f in _MONO if f in familias), "TkFixedFont")

        def f(size, weight="normal", family=sans):
            return ctk.CTkFont(family=family, size=round(size * _SCALE), weight=weight)

        self.display  = f(28, "bold")
        self.title    = f(24, "bold")
        self.headline = f(17, "bold")
        self.body     = f(16)
        self.body_b   = f(16, "bold")
        self.small    = f(14)
        self.caption  = f(13)
        self.eyebrow  = f(12, "bold")
        self.mono     = f(13, family=mono)
        self.mono_l   = f(18, "bold", family=mono)


def ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def animate(widget, duration_ms: int, on_frame, on_done=None, easing=ease_out):
    inicio = time.perf_counter()

    def frame():
        if not widget.winfo_exists():
            return
        t = min(1.0, (time.perf_counter() - inicio) * 1000 / duration_ms)
        on_frame(easing(t))
        if t < 1.0:
            widget.after(16, frame)
        elif on_done:
            on_done()

    frame()


def apply_appearance(mode: str) -> None:
    ctk.set_appearance_mode(mode if mode in APPEARANCES else "system")
