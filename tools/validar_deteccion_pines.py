import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.provisioner import Provisioner, esperar_dispositivo

CAMPOS = ['timestamp', 'placa', 'device_id', 'condicion', 'repeticion',
          'dht_real', 'dht_detectado', 'dht_state', 'dht_resultado',
          'soil_real', 'soil_detectado', 'soil_state', 'soil_resultado',
          'duracion_s']

ACUMULADO = Path(__file__).parent.parent / "logs" / "deteccion_acumulado.csv"


def clasificar(real: int, detectado: int) -> str:
    if real < 0:
        return 'TN' if detectado < 0 else 'FP'
    if detectado == real:
        return 'TP'
    if detectado < 0:
        return 'FN'
    return 'FP_PIN'


def una_medicion(puerto, n, placa, device_id, condicion, dht_real, soil_real):
    t0 = time.time()
    with Provisioner(puerto, timeout=6.0) as p:
        r = p.detectar_pines(aplicar=False)

    dht_det  = r.get('dht_pin', -1)
    soil_det = r.get('soil_pin', -1)

    fila = {
        'timestamp':     datetime.now().isoformat(timespec='seconds'),
        'placa':         placa,
        'device_id':     device_id,
        'condicion':     condicion,
        'repeticion':    n,
        'dht_real':      dht_real,
        'dht_detectado': dht_det,
        'dht_state':     r.get('dht_state', ''),
        'dht_resultado': clasificar(dht_real, dht_det),
        'soil_real':      soil_real,
        'soil_detectado': soil_det,
        'soil_state':     r.get('soil_state', ''),
        'soil_resultado': clasificar(soil_real, soil_det),
        'duracion_s':     round(time.time() - t0, 2),
    }
    return fila, r.get('soil_scan', [])


def main():
    if len(sys.argv) < 6:
        print("Uso: python tools/validar_deteccion_pines.py PUERTO PLACA "
              "PIN_DHT_REAL PIN_SOIL_REAL CONDICION [N]")
        print("  usa -1 cuando el sensor NO esta conectado")
        print("  ej: python tools/validar_deteccion_pines.py COM5 A 15 34 "
              "tierra_humeda 20")
        sys.exit(1)

    puerto    = sys.argv[1]
    placa     = sys.argv[2]
    dht_real  = int(sys.argv[3])
    soil_real = int(sys.argv[4])
    condicion = sys.argv[5]
    n_total   = int(sys.argv[6]) if len(sys.argv) > 6 else 20

    marca   = f"{datetime.now():%Y%m%d_%H%M%S}"
    carpeta = Path(__file__).parent.parent / "logs"
    carpeta.mkdir(exist_ok=True)
    destino = carpeta / f"deteccion_{placa}_{condicion}_{marca}.csv"
    crudo   = carpeta / f"scan_{placa}_{condicion}_{marca}.jsonl"

    print("Validacion de deteccion de pines")
    print(f"  placa={placa}  condicion={condicion}  N={n_total}")
    print(f"  esperado: DHT11=GPIO{dht_real}  FC-28=GPIO{soil_real}")
    print("  (-1 = sensor no conectado)\n")

    print("Verificando que el dispositivo este en modo Setup...")
    try:
        ident = esperar_dispositivo(puerto)
    except TimeoutError as e:
        print(f"ERROR: el dispositivo no responde ({e})")
        print("El firmware solo atiende comandos serial en modo Setup.")
        print("Si ya tiene WiFi configurado, vuelve a flashearlo primero.")
        sys.exit(1)

    device_id = ident.get('device_id', '')
    print(f"  OK  device_id={device_id}\n")

    filas = []
    with open(destino, 'w', newline='', encoding='utf-8') as f, \
         open(crudo, 'w', encoding='utf-8') as fj:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for i in range(1, n_total + 1):
            fila, scan = una_medicion(puerto, i, placa, device_id,
                                      condicion, dht_real, soil_real)
            w.writerow(fila)
            f.flush()
            fj.write(json.dumps({'repeticion': i, 'placa': placa,
                                 'condicion': condicion, 'scan': scan}) + "\n")
            fj.flush()
            filas.append(fila)
            print(f"[{i:3d}/{n_total}] "
                  f"DHT11 GPIO{fila['dht_detectado']:<3} {fila['dht_resultado']:<6} | "
                  f"FC-28 GPIO{fila['soil_detectado']:<3} "
                  f"{fila['soil_state']:<10} {fila['soil_resultado']}")

    nuevo = not ACUMULADO.exists()
    with open(ACUMULADO, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if nuevo:
            w.writeheader()
        w.writerows(filas)

    print(f"\n{'='*58}")
    for sensor in ('dht', 'soil'):
        res = [f[f'{sensor}_resultado'] for f in filas]
        nombre = 'DHT11' if sensor == 'dht' else 'FC-28'
        print(f"{nombre:<7} " + "  ".join(
            f"{k}={res.count(k)}" for k in ('TP', 'TN', 'FN', 'FP', 'FP_PIN')
            if res.count(k)))
    print(f"\nCSV   -> {destino}")
    print(f"scan  -> {crudo}")
    print(f"acum  -> {ACUMULADO}")


if __name__ == "__main__":
    main()
