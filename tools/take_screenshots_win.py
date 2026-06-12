import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

_DEFAULT_DEST = _ROOT / "screenshots"
DEST = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_DEST
LANG = sys.argv[2] if len(sys.argv) > 2 else "en"
DEST.mkdir(parents=True, exist_ok=True)

if "--demo" not in sys.argv:
    sys.argv.append("--demo")

from PIL import ImageGrab          # noqa: E402
from core.lang import set_lang, get_lang  # noqa: E402
import app as agro_app             # noqa: E402

FAKE_PORT = "COM3  —  Silicon Labs CP210x USB to UART Bridge (COM3)"
FAKE_RESULTS = [
    {"valor": 22.4, "unidad": "°C", "estado": "ok", "mensaje": "22.4 °C"},
    {"valor": 58.2, "unidad": "%",  "estado": "ok", "mensaje": "58.2 %"},
    {"valor": 34.1, "unidad": "%",  "estado": "ok", "mensaje": "34.1 %"},
]
DEVICE_ID = "AC-ESP32-7F3A"

SEQUENCE = [
    (0, "fig2_wizard_overview.png"),
    (1, "fig3_step2_flash.png"),
    (2, "fig4_step3_configure.png"),
    (3, "fig5_step4_verify.png"),
    (4, "fig6_step5_activate.png"),
]


def _grab(app, name: str):
    app.update_idletasks()
    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    img.save(DEST / name)
    print(f"  Capturado: {name}  ({w}x{h})")


def _prepare_step(app, step: int):
    if step == 0:
        app._port_combo.configure(values=[FAKE_PORT])
        app._puerto.set(FAKE_PORT)
        app._set_port_status(None, "COM3  —  CP210x")
    elif step == 3:
        app._show_sensor_results(FAKE_RESULTS)
        app._render_qr(DEVICE_ID)
        app._lbl_did.configure(text=DEVICE_ID)


def _run_sequence(app, idx: int = 0):
    if idx >= len(SEQUENCE):
        print(f"\nListo. Capturas en: {DEST}")
        app.after(300, app.destroy)
        return
    step, name = SEQUENCE[idx]
    app._show_step(step, animated=False)
    app.after(150, lambda: _prepare_step(app, step))
    app.after(900, lambda: (_grab(app, name), _run_sequence(app, idx + 1)))


_orig_splash_done = agro_app.AgroFlasher._on_splash_done


def _patched_splash_done(self):
    _orig_splash_done(self)
    if get_lang() != LANG:
        set_lang(LANG)
        self.after(700, self._apply_lang)
    self.attributes("-topmost", True)
    self.after(1800, lambda: _run_sequence(self))


agro_app.AgroFlasher._on_splash_done = _patched_splash_done

if __name__ == "__main__":
    print(f"Capturando en '{LANG}' hacia: {DEST}")
    agro_app.main()
