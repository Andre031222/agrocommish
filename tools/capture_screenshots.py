import json
import sys
from pathlib import Path

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import core.config_manager as config_manager
from ui.window import AgroCommish

NAMES = ("step1", "step2", "step3", "step4", "step5")


def capture(app, destino: Path, nombre: str):
    app.update_idletasks()
    app.update()
    x, y = app.winfo_rootx(), app.winfo_rooty()
    caja = (x, y, x + app.winfo_width(), y + app.winfo_height())
    ImageGrab.grab(bbox=caja, all_screens=True).save(destino / f"{nombre}.png")
    print(destino / f"{nombre}.png")


def run(destino: Path, appearance: str, language: str):
    destino.mkdir(parents=True, exist_ok=True)
    cfg = destino / f".config_{appearance}_{language}.json"
    cfg.write_text(json.dumps({"appearance": appearance, "language": language}), encoding="utf-8")
    config_manager._CONFIG_PATH = cfg
    app = AgroCommish(demo=True)
    app.attributes("-topmost", True)
    sufijo = f"-{appearance}" + ("" if language == "en" else f"-{language}")
    t = 2200
    for n, nombre in enumerate(NAMES):
        app.after(t, lambda n=n: app._show_step(n))
        app.after(t + 700, lambda nombre=nombre: capture(app, destino, nombre + sufijo))
        t += 1100
    app.after(t, lambda: app._show_step(2))
    app.after(t + 300, app._toggle_sidebar)
    app.after(t + 1000, lambda: capture(app, destino, "sidebar-collapsed" + sufijo))
    app.after(t + 1400, app.destroy)
    app.mainloop()
    cfg.unlink(missing_ok=True)


if __name__ == "__main__":
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "img"
    modo = sys.argv[2] if len(sys.argv) > 2 else "light"
    idioma = sys.argv[3] if len(sys.argv) > 3 else "en"
    run(salida, modo, idioma)
