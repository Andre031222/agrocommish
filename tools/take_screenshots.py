import subprocess
import sys
import threading
import time
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

_DEFAULT_DEST = _ROOT / "screenshots"
DEST = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_DEST
DEST.mkdir(parents=True, exist_ok=True)

import app as agro_app


def screenshot(name: str, delay: float = 0.5):
    time.sleep(delay)
    out = DEST / name
    r = subprocess.run(
        ["import", "-window", "AgroCommish", str(out)],
        capture_output=True, timeout=5
    )
    if r.returncode != 0:
        subprocess.run(
            ["import", "-window", "root", str(out)],
            capture_output=True, timeout=5
        )
    print(f"  Capturado: {out.name}")


_orig_on_splash_done = agro_app.AgroFlasher._on_splash_done


def _patched_on_splash_done(self):
    _orig_on_splash_done(self)
    threading.Thread(target=_auto_capture, args=(self,), daemon=True).start()


def _auto_capture(app_instance):
    time.sleep(0.8)

    print("[1/5] Step 1 - Detectar")
    screenshot("fig_step1_detect.png", delay=0.3)

    print("[2/5] Step 2 - Flashear")
    app_instance.after(0, lambda: app_instance._show_step(1))
    screenshot("fig_step2_flash.png", delay=0.6)

    print("[3/5] Step 3 - Configurar")
    app_instance.after(0, lambda: app_instance._show_step(2))
    screenshot("fig_step3_configure.png", delay=0.6)

    print("[4/5] Step 4 - Verificar")
    app_instance.after(0, lambda: app_instance._show_step(3))
    time.sleep(0.5)
    fake_results = [
        {"valor": 22.4, "unidad": "°C", "estado": "ok",  "mensaje": "22.4 °C"},
        {"valor": 58.2, "unidad": "%",  "estado": "ok",  "mensaje": "58.2 %"},
        {"valor": 34.1, "unidad": "%",  "estado": "ok",  "mensaje": "34.1 %"},
    ]
    app_instance.after(0, lambda: app_instance._show_sensor_results(fake_results))
    app_instance.after(0, lambda: app_instance._render_qr("AV-ESP32-7F3A"))
    screenshot("fig_step4_verify.png", delay=1.0)

    print("[5/5] Step 5 - Activar")
    app_instance.after(0, lambda: app_instance._show_step(4))
    screenshot("fig_step5_activate.png", delay=0.6)

    print("[+] Overview desde Step 1")
    app_instance.after(0, lambda: app_instance._show_step(0))
    screenshot("fig_wizard_overview.png", delay=0.6)

    print("\nTodas las capturas guardadas en:")
    print(f"  {DEST}")

    time.sleep(0.5)
    app_instance.after(0, app_instance.destroy)


agro_app.AgroFlasher._on_splash_done = _patched_on_splash_done

if __name__ == "__main__":
    print("Iniciando AgroCommish para captura de screenshots...")
    print(f"Destino: {DEST}")
    agro_app.main()
