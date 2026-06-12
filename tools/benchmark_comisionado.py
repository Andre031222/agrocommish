import csv
import socket
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.flasher import Flasher
from core.provisioner import Provisioner, esperar_dispositivo

CAMPOS = ['corrida', 'inicio', 'flash_s', 'arranque_s', 'pines_s',
          'config_s', 'verificacion_s', 'total_s',
          'device_id', 'pin_dht', 'pin_soil', 'temperatura_C']


def ip_local() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def correr_ciclo(n, puerto, fw, ssid, clave, servidor) -> dict:
    fila = {'corrida': n, 'inicio': datetime.now().isoformat(timespec='seconds')}
    t0 = time.time()

    print(f"\n[{n}] Flasheando (borrado completo + escritura)...")
    Flasher(puerto, fw).flashear(
        on_progress=lambda p: print(f"\r    escritura {p:3d} %", end=""))
    print()
    fila['flash_s'] = round(time.time() - t0, 1)

    t = time.time()
    print(f"[{n}] Esperando arranque...")
    esperar_dispositivo(puerto)
    fila['arranque_s'] = round(time.time() - t, 1)

    t = time.time()
    print(f"[{n}] Detectando pines de sensores...")
    with Provisioner(puerto, timeout=4.0) as p:
        r = p.detectar_pines(aplicar=True)
    fila['pines_s']  = round(time.time() - t, 1)
    fila['pin_dht']  = r.get('dht_pin')
    fila['pin_soil'] = r.get('soil_pin')
    print(f"    DHT11=GPIO{fila['pin_dht']}  FC-28=GPIO{fila['pin_soil']}")

    t = time.time()
    print(f"[{n}] Configurando WiFi + servidor...")
    with Provisioner(puerto) as p:
        r = p.configurar(ssid, clave, servidor)
    if not r.get('ok'):
        raise RuntimeError(f"config fallo: {r}")
    fila['config_s']  = round(time.time() - t, 1)
    fila['device_id'] = r.get('device_id', '')

    t = time.time()
    print(f"[{n}] Verificando sensores (reinicio + WiFi + lectura)...")
    fin = time.time() + 90
    lectura = None
    while time.time() < fin and lectura is None:
        try:
            with Provisioner(puerto, timeout=2.0) as p:
                try:
                    lectura = p.leer_sensores(timeout=3.0)
                except (TimeoutError, RuntimeError):
                    lectura = p.escuchar_datos(max_espera=15.0)
        except (TimeoutError, RuntimeError, OSError):
            time.sleep(2)
    if lectura is None:
        raise TimeoutError("sin lectura de verificacion en 90 s")
    fila['verificacion_s'] = round(time.time() - t, 1)
    fila['total_s']        = round(time.time() - t0, 1)
    fila['temperatura_C']  = lectura.get('temperatura')
    print(f"    {fila['temperatura_C']} C  ->  LISTO en {fila['total_s']} s")
    return fila


def main():
    if len(sys.argv) < 4:
        print("Uso: python tools/benchmark_comisionado.py PUERTO SSID CLAVE "
              "[N] [SERVIDOR] [FIRMWARE]")
        sys.exit(1)

    puerto   = sys.argv[1]
    ssid     = sys.argv[2]
    clave    = sys.argv[3]
    n_total  = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    servidor = (sys.argv[5] if len(sys.argv) > 5
                else f"http://{ip_local()}:5000/api/sensores/lectura")
    fw       = (Path(sys.argv[6]) if len(sys.argv) > 6
                else Path(__file__).parent.parent / "firmware" / "firmware.bin")

    destino = (Path(__file__).parent.parent / "logs" /
               f"benchmark_{datetime.now():%Y%m%d_%H%M%S}.csv")
    destino.parent.mkdir(exist_ok=True)

    print(f"Benchmark de comisionado: {n_total} corridas en {puerto}")
    print(f"SSID={ssid}  servidor={servidor}\nCSV -> {destino}")

    filas = []
    with open(destino, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for i in range(1, n_total + 1):
            fila = correr_ciclo(i, puerto, fw, ssid, clave, servidor)
            w.writerow(fila)
            f.flush()
            filas.append(fila)

    totales = [f['total_s'] for f in filas]
    print(f"\n{'='*52}\nResultados ({len(filas)} corridas):")
    print(f"{'fase':<14}{'media':>8}{'min':>8}{'max':>8}")
    for campo in ['flash_s', 'arranque_s', 'pines_s', 'config_s',
                  'verificacion_s', 'total_s']:
        vals = [f[campo] for f in filas]
        print(f"{campo:<14}{statistics.mean(vals):>8.1f}"
              f"{min(vals):>8.1f}{max(vals):>8.1f}")
    print(f"\ntotal  media={statistics.mean(totales)/60:.2f} min"
          f"  mediana={statistics.median(totales)/60:.2f} min"
          + (f"  desv={statistics.stdev(totales)/60:.2f} min"
             if len(totales) > 1 else ""))


if __name__ == "__main__":
    main()
