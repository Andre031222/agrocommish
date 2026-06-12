import json
import math
import re
import time
from datetime import datetime

import serial


class Provisioner:

    def __init__(self, port: str, baud: int = 115200, timeout: float = 10.0):
        self.port    = port
        self.baud    = baud
        self.timeout = timeout
        self._ser: serial.Serial | None = None

    def abrir(self, reintentos: int = 4):
        ultimo = None
        for _ in range(reintentos):
            s = serial.Serial()
            s.port          = self.port
            s.baudrate      = self.baud
            s.timeout       = self.timeout
            s.write_timeout = 3
            s.dtr = False
            s.rts = False
            try:
                s.open()
            except serial.SerialException as e:
                ultimo = e
                time.sleep(0.8)
                continue
            self._ser = s
            time.sleep(0.6)
            return

        msg = str(ultimo)
        if "PermissionError" in msg or "denegado" in msg or "denied" in msg.lower():
            raise RuntimeError(
                f"El puerto {self.port} está en uso por otro programa.\n"
                "Cierra el Monitor Serie de Arduino, otras instancias de "
                "AgroCommish o cualquier app que use ese puerto."
            )
        raise RuntimeError(msg)

    def cerrar(self):
        if self._ser and self._ser.is_open:
            self._ser.dtr = False
            self._ser.rts = False
            self._ser.close()
            self._ser = None

    def __enter__(self):
        self.abrir()
        return self

    def __exit__(self, *_):
        self.cerrar()

    def _cmd(self, cmd: dict, timeout: float = 12.0) -> dict:
        if not self._ser or not self._ser.is_open:
            raise RuntimeError("Puerto no abierto")

        self._ser.reset_input_buffer()
        payload = json.dumps(cmd, separators=(',', ':')) + '\n'
        self._ser.write(payload.encode('utf-8'))
        self._ser.flush()

        deadline = time.time() + timeout
        buf = b''
        while time.time() < deadline:
            chunk = self._ser.read(self._ser.in_waiting or 1)
            if chunk:
                buf += chunk
                if b'\n' in buf:
                    lines = buf.split(b'\n')
                    buf = lines[-1]
                    for line in lines[:-1]:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            return json.loads(line.decode('utf-8'))
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            continue
            else:
                time.sleep(0.05)

        raise TimeoutError(
            f"El ESP32 no respondió en {timeout:.0f}s.\n"
            "Verifica que el firmware esté grabado y el dispositivo encendido."
        )

    def identificar(self, timeout: float = 8.0) -> dict:
        return self._cmd({'cmd': 'identify'}, timeout=timeout)

    def escanear_wifi(self) -> list[dict]:
        r = self._cmd({'cmd': 'scan'}, timeout=18.0)
        return r.get('networks', [])

    def configurar(self, ssid: str, password: str, server: str) -> dict:
        return self._cmd({
            'cmd':    'config',
            'ssid':   ssid,
            'pass':   password,
            'server': server,
        }, timeout=14.0)

    def calibrar(self,
                 temp_offset: float = 0.0,
                 hum_offset:  float = 0.0,
                 soil_dry:    int   = 50,
                 soil_wet:    int   = 3200) -> dict:
        return self._cmd({
            'cmd':         'calibrate',
            'temp_offset': round(float(temp_offset), 2),
            'hum_offset':  round(float(hum_offset),  2),
            'soil_dry':    int(soil_dry),
            'soil_wet':    int(soil_wet),
        }, timeout=8.0)

    def leer_sensores(self, timeout: float = 10.0) -> dict:
        return self._cmd({'cmd': 'read_sensors'}, timeout=timeout)

    _RE_DATA  = re.compile(
        r'\[DATA\]\s*Temp=([\d.+-]+).*?HumAire=([\d.+-]+).*?HumSuelo=([\d.+-]+)')
    _RE_DHT   = re.compile(
        r'\[DHT11\]\s*raw=([\d.+-]+).*?/([\d.+-]+)%.*?calibrado=([\d.+-]+).*?/([\d.+-]+)%')
    _RE_SUELO = re.compile(r'\[SUELO\]\s*raw ADC=(\d+)\s*.*?humSuelo=(\d+)%')
    _RE_HTTP  = re.compile(r'\[HTTP\]\s*(OK\s*\d+|Error\s*-?\d+)')

    CAMPOS_TELEMETRIA = ['timestamp_pc', 'temperatura_C', 'humedad_aire_pct',
                         'humedad_suelo_pct', 'dht_temp_raw', 'dht_hum_raw',
                         'suelo_adc_raw', 'envio_http']

    def escuchar_datos(self, max_espera: float = 13.0) -> dict:
        if not self._ser or not self._ser.is_open:
            raise RuntimeError("Puerto no abierto")

        fin = time.time() + max_espera
        buf = b''
        dht_fallo = False
        while time.time() < fin:
            chunk = self._ser.read(self._ser.in_waiting or 1)
            if not chunk:
                time.sleep(0.05)
                continue
            buf += chunk
            while b'\n' in buf:
                linea, buf = buf.split(b'\n', 1)
                texto = linea.decode('utf-8', 'ignore')
                m = self._RE_DATA.search(texto)
                if m:
                    return {
                        'temperatura':   float(m.group(1)),
                        'humedad_aire':  float(m.group(2)),
                        'humedad_suelo': float(m.group(3)),
                    }
                if '[SENSOR] Error lectura DHT11' in texto:
                    dht_fallo = True

        if dht_fallo:
            return {'temperatura': float('nan'), 'humedad_aire': float('nan')}
        raise TimeoutError(
            "El ESP32 no transmitió lecturas por USB. "
            "Verifica que esté encendido y conectado al WiFi."
        )

    def capturar_telemetria(self, duracion_s: float = 65.0,
                            on_lectura=None) -> list[dict]:
        if not self._ser or not self._ser.is_open:
            raise RuntimeError("Puerto no abierto")

        filas: list[dict] = []
        pendiente = None
        ultimo: dict = {}
        fin = time.time() + duracion_s
        buf = b''

        def cerrar_pendiente():
            nonlocal pendiente
            if pendiente:
                filas.append(pendiente)
                if on_lectura:
                    on_lectura(len(filas), pendiente)
                pendiente = None

        while time.time() < fin:
            chunk = self._ser.read(self._ser.in_waiting or 1)
            if not chunk:
                time.sleep(0.05)
                continue
            buf += chunk
            while b'\n' in buf:
                linea, buf = buf.split(b'\n', 1)
                texto = linea.decode('utf-8', 'ignore').strip()

                m = self._RE_DHT.search(texto)
                if m:
                    ultimo['dht_temp_raw'] = m.group(1)
                    ultimo['dht_hum_raw']  = m.group(2)
                    continue
                m = self._RE_SUELO.search(texto)
                if m:
                    ultimo['suelo_adc_raw'] = m.group(1)
                    continue
                m = self._RE_DATA.search(texto)
                if m:
                    cerrar_pendiente()
                    pendiente = {
                        'timestamp_pc':      datetime.now().isoformat(timespec='seconds'),
                        'temperatura_C':     m.group(1),
                        'humedad_aire_pct':  m.group(2),
                        'humedad_suelo_pct': m.group(3),
                        'dht_temp_raw':      ultimo.get('dht_temp_raw', ''),
                        'dht_hum_raw':       ultimo.get('dht_hum_raw', ''),
                        'suelo_adc_raw':     ultimo.get('suelo_adc_raw', ''),
                        'envio_http':        '',
                    }
                    continue
                m = self._RE_HTTP.search(texto)
                if m and pendiente:
                    pendiente['envio_http'] = m.group(1).replace('  ', ' ')
                    cerrar_pendiente()

        cerrar_pendiente()
        return filas

    def detectar_pines(self, aplicar: bool = True) -> dict:
        return self._cmd({'cmd': 'detect_pins', 'apply': aplicar},
                         timeout=45.0)

    def configurar_pines(self, dht: int, soil: int) -> dict:
        return self._cmd({'cmd': 'set_pins',
                          'dht': int(dht), 'soil': int(soil)}, timeout=8.0)


def esperar_dispositivo(port: str, max_espera: float = 18.0) -> dict:
    fin = time.time() + max_espera
    ultimo_error = "sin respuesta"
    while time.time() < fin:
        try:
            with Provisioner(port, timeout=2.0) as p:
                r = p.identificar(timeout=3.0)
                if r.get('ok'):
                    return r
        except (TimeoutError, RuntimeError, OSError) as e:
            ultimo_error = str(e)
        time.sleep(1.0)
    raise TimeoutError(ultimo_error)


SENSOR_SPECS = [
    {
        'key':      'temperatura',
        'nombre':   'DHT11 — Temperatura',
        'unidad':   '°C',
        'min':      -5.0,
        'max':      60.0,
        'warn_min':  5.0,
        'warn_max': 45.0,
    },
    {
        'key':      'humedad_aire',
        'nombre':   'DHT11 — Humedad del aire',
        'unidad':   '%',
        'min':       5.0,
        'max':      100.0,
        'warn_min':  20.0,
        'warn_max':  95.0,
    },
    {
        'key':      'humedad_suelo',
        'nombre':   'FC-28 — Humedad del suelo',
        'unidad':   '%',
        'min':       0.0,
        'max':      100.0,
        'warn_min':  1.0,
        'warn_max':  99.0,
    },
]


def validar_lecturas(data: dict) -> list[dict]:
    resultados = []

    for spec in SENSOR_SPECS:
        raw    = data.get(spec['key'])
        estado = 'error'
        valor  = None
        msg    = ''

        if raw is None:
            msg = 'No recibido en la respuesta del ESP32'
        elif isinstance(raw, float) and math.isnan(raw):
            msg = 'NaN — sensor no conectado o fallo de lectura'
        else:
            try:
                valor = float(raw)
            except (TypeError, ValueError):
                msg = f'Valor inválido: {raw!r}'
            else:
                if valor < spec['min'] or valor > spec['max']:
                    msg = (f'Fuera de rango físico ({valor:.1f} {spec["unidad"]}) '
                           f'Esperado {spec["min"]}..{spec["max"]}')
                elif valor < spec['warn_min'] or valor > spec['warn_max']:
                    estado = 'warn'
                    msg    = (f'{valor:.1f} {spec["unidad"]} '
                              f'Fuera del rango agrícola normal')
                else:
                    estado = 'ok'
                    msg    = f'{valor:.1f} {spec["unidad"]}'

        resultados.append({
            'sensor':  spec['nombre'],
            'valor':   valor,
            'unidad':  spec['unidad'],
            'estado':  estado,
            'mensaje': msg,
        })

    return resultados
