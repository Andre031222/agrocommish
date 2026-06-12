import csv
import statistics
import sys
from datetime import datetime
from pathlib import Path

LOGS = (Path(sys.argv[1]) if len(sys.argv) > 1
        else Path(__file__).parent.parent / "logs")

HITOS = ["FLASH_INICIO", "FLASH_OK", "PINES_DETECTADOS",
         "CONFIG_OK", "TEST_OK", "LISTO"]


def cargar_eventos() -> list[dict]:
    eventos = []
    for archivo in sorted(LOGS.glob("sesion_*.csv")):
        with open(archivo, encoding='utf-8') as f:
            for fila in csv.DictReader(f):
                if fila.get("resultado") in HITOS:
                    eventos.append({
                        "ts":      datetime.fromisoformat(fila["timestamp"]),
                        "device":  fila.get("device_id", ""),
                        "evento":  fila["resultado"],
                        "sesion":  archivo.stem,
                    })
    return eventos


def medir() -> list[dict]:
    unidades = []
    inicio = None
    sesion_inicio = None
    for ev in cargar_eventos():
        if ev["evento"] == "FLASH_INICIO":
            inicio = ev["ts"]
            sesion_inicio = ev["sesion"]
        elif ev["evento"] == "LISTO" and inicio and ev["sesion"] == sesion_inicio:
            unidades.append({
                "device":   ev["device"] or "?",
                "inicio":   inicio,
                "fin":      ev["ts"],
                "segundos": (ev["ts"] - inicio).total_seconds(),
            })
            inicio = None
    return unidades


def main():
    unidades = medir()
    if not unidades:
        print("Sin unidades completas (FLASH_INICIO → LISTO) en", LOGS)
        return

    print(f"{'Device':<16} {'Inicio':<20} {'Fin':<20} {'min:seg':>8}")
    print("-" * 68)
    for u in unidades:
        m, s = divmod(int(u["segundos"]), 60)
        print(f"{u['device']:<16} {u['inicio'].strftime('%Y-%m-%d %H:%M:%S'):<20} "
              f"{u['fin'].strftime('%Y-%m-%d %H:%M:%S'):<20} {m:>5}:{s:02d}")

    tiempos = [u["segundos"] for u in unidades]
    print("-" * 68)
    print(f"n = {len(tiempos)}")
    print(f"media   = {statistics.mean(tiempos)/60:.2f} min")
    print(f"mediana = {statistics.median(tiempos)/60:.2f} min")
    print(f"min     = {min(tiempos)/60:.2f} min")
    print(f"max     = {max(tiempos)/60:.2f} min")
    if len(tiempos) > 1:
        print(f"desv    = {statistics.stdev(tiempos)/60:.2f} min")


if __name__ == "__main__":
    main()
