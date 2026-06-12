import csv
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.provisioner import Provisioner


def capturar(puerto: str, duracion_s: float, destino: Path) -> int:
    destino.parent.mkdir(parents=True, exist_ok=True)
    print(f"Capturando de {puerto} durante {duracion_s:.0f} s -> {destino}")

    with open(destino, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=Provisioner.CAMPOS_TELEMETRIA)
        w.writeheader()

        def al_recibir(n, fila):
            w.writerow(fila)
            f.flush()
            print(f"  [{n}] {fila['temperatura_C']} C  "
                  f"{fila['humedad_aire_pct']} %aire  "
                  f"{fila['humedad_suelo_pct']} %suelo  "
                  f"ADC={fila['suelo_adc_raw']}  "
                  f"HTTP={fila['envio_http']}")

        with Provisioner(puerto, timeout=1.0) as p:
            filas = p.capturar_telemetria(duracion_s, on_lectura=al_recibir)

    print(f"\nListo: {len(filas)} lecturas guardadas en {destino}")
    return len(filas)


if __name__ == "__main__":
    puerto   = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    duracion = float(sys.argv[2]) if len(sys.argv) > 2 else 300
    destino  = (Path(sys.argv[3]) if len(sys.argv) > 3
                else Path(__file__).parent.parent / "logs" /
                f"datos_recibidos_{datetime.now():%Y%m%d_%H%M%S}.csv")
    capturar(puerto, duracion, destino)
