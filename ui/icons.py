from functools import lru_cache

import customtkinter as ctk
from PIL import Image

from core.paths import BUNDLE_DIR

_DIR = BUNDLE_DIR / "assets" / "icons" / "png"


@lru_cache(maxsize=None)
def _mask(name: str) -> Image.Image:
    return Image.open(_DIR / f"{name}.png").convert("RGBA").getchannel("A")


def _tint(name: str, color: str) -> Image.Image:
    mask = _mask(name)
    img = Image.new("RGBA", mask.size, color)
    img.putalpha(mask)
    return img


@lru_cache(maxsize=None)
def blank(size: int) -> ctk.CTkImage:
    vacio = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    return ctk.CTkImage(light_image=vacio, dark_image=vacio, size=(size, size))


@lru_cache(maxsize=None)
def icon(name: str, size: int, color) -> ctk.CTkImage:
    light, dark = color if isinstance(color, tuple) else (color, color)
    return ctk.CTkImage(light_image=_tint(name, light), dark_image=_tint(name, dark),
                        size=(size, size))
