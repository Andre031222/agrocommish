import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core import config_manager, detector
from core.flasher import Flasher
from core.lang import STRINGS
from core.provisioner import Provisioner, validar_lecturas


class TestValidarLecturas:

    def test_lecturas_normales(self):
        r = validar_lecturas({'temperatura': 22.4, 'humedad_aire': 58.2,
                              'humedad_suelo': 34.1})
        assert [x['estado'] for x in r] == ['ok', 'ok', 'ok']

    def test_valores_faltantes(self):
        r = validar_lecturas({})
        assert all(x['estado'] == 'error' for x in r)
        assert all(x['valor'] is None for x in r)

    def test_nan_es_error(self):
        r = validar_lecturas({'temperatura': float('nan'),
                              'humedad_aire': float('nan'),
                              'humedad_suelo': 10})
        assert r[0]['estado'] == 'error'
        assert 'NaN' in r[0]['mensaje']
        assert r[2]['estado'] == 'ok'

    def test_fuera_de_rango_fisico(self):
        r = validar_lecturas({'temperatura': 80.0, 'humedad_aire': 50,
                              'humedad_suelo': 50})
        assert r[0]['estado'] == 'error'

    def test_advertencia_agronomica(self):
        r = validar_lecturas({'temperatura': 2.0, 'humedad_aire': 50,
                              'humedad_suelo': 50})
        assert r[0]['estado'] == 'warn'

    def test_valor_invalido(self):
        r = validar_lecturas({'temperatura': 'abc', 'humedad_aire': 50,
                              'humedad_suelo': 50})
        assert r[0]['estado'] == 'error'


class TestDetector:

    def test_excluye_bluetooth_y_virtuales(self):
        assert detector._es_bluetooth_o_virtual("Standard Serial over Bluetooth")
        assert detector._es_bluetooth_o_virtual("VMware Virtual Serial")
        assert not detector._es_bluetooth_o_virtual("Silicon Labs CP210x")

    def test_detectar_puertos_ordena_esp32_primero(self, monkeypatch):
        class FakePort:
            def __init__(self, device, description):
                self.device = device
                self.description = description
                self.manufacturer = ""
                self.hwid = ""

        fakes = [FakePort("COM1", "Puerto serie generico"),
                 FakePort("COM5", "Silicon Labs CP210x USB to UART Bridge"),
                 FakePort("COM3", "Bluetooth link over serial")]
        monkeypatch.setattr(detector.serial.tools.list_ports, "comports",
                            lambda: fakes)
        puertos = detector.detectar_puertos()
        assert [p['port'] for p in puertos] == ["COM5", "COM1"]
        assert puertos[0]['es_esp32'] is True


class TestProtocoloSerial:

    class FakeSerial:
        def __init__(self, respuesta: bytes):
            self.is_open = True
            self._datos = respuesta
            self.in_waiting = len(respuesta)
            self.escrito = b''

        def reset_input_buffer(self):
            pass

        def write(self, data):
            self.escrito += data

        def flush(self):
            pass

        def read(self, n):
            datos, self._datos = self._datos[:n], self._datos[n:]
            self.in_waiting = len(self._datos)
            return datos

    def _con_respuesta(self, respuesta: bytes) -> Provisioner:
        p = Provisioner("FAKE")
        p._ser = self.FakeSerial(respuesta)
        return p

    def test_respuesta_json_simple(self):
        p = self._con_respuesta(b'{"ok":true,"device_id":"ESP32_AB"}\n')
        r = p._cmd({'cmd': 'identify'}, timeout=1.0)
        assert r == {'ok': True, 'device_id': 'ESP32_AB'}
        assert p._ser.escrito == b'{"cmd":"identify"}\n'

    def test_ignora_lineas_de_log_antes_del_json(self):
        p = self._con_respuesta(b'[BOOT] arrancando\n[NVS] Cal: T=0\n{"ok":true}\n')
        assert p._cmd({'cmd': 'x'}, timeout=1.0) == {'ok': True}

    def test_timeout_sin_respuesta(self):
        p = self._con_respuesta(b'')
        with pytest.raises(TimeoutError):
            p._cmd({'cmd': 'x'}, timeout=0.2)

    def test_regex_telemetria(self):
        m = Provisioner._RE_DATA.search(
            "[DATA] Temp=23.5°C  HumAire=60%  HumSuelo=45%")
        assert m.groups() == ('23.5', '60', '45')
        m = Provisioner._RE_SUELO.search(
            "[SUELO] raw ADC=1850  →  humSuelo=55%  (DRY=50 WET=3200)")
        assert m.groups() == ('1850', '55')
        m = Provisioner._RE_HTTP.search("[HTTP] Error 404")
        assert m.group(1) == "Error 404"


class TestFlasher:

    def test_firmware_inexistente(self, tmp_path):
        ok, _ = Flasher("COM1", tmp_path / "no_existe.bin").validar()
        assert not ok

    def test_firmware_muy_pequeno(self, tmp_path):
        fw = tmp_path / "fw.bin"
        fw.write_bytes(b'\x00' * 100)
        ok, msg = Flasher("COM1", fw).validar()
        assert not ok
        assert "pequeño" in msg

    def test_firmware_valido(self, tmp_path):
        fw = tmp_path / "fw.bin"
        fw.write_bytes(b'\x00' * 8192)
        ok, _ = Flasher("COM1", fw).validar()
        assert ok

    def test_comando_usa_chip_auto_y_borrado(self, tmp_path):
        fw = tmp_path / "fw.bin"
        fw.write_bytes(b'\x00' * 8192)
        cmd = Flasher("COM7", fw)._build_cmd()
        assert 'auto' in cmd
        assert '--erase-all' in cmd
        assert 'COM7' in cmd


class TestIdiomas:

    def test_paridad_es_en(self):
        assert set(STRINGS['es']) == set(STRINGS['en'])

    def test_claves_usadas_existen(self):
        src = (ROOT / "app.py").read_text(encoding='utf-8')
        usadas = set(re.findall(r"T\(['\"]([a-z0-9_]+)['\"]", src))
        assert usadas <= set(STRINGS['es'])


class TestConfigManager:

    def test_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config_manager, "_CONFIG_PATH",
                            tmp_path / "config.json")
        config_manager.guardar(last_port="COM9", language="en")
        cfg = config_manager.cargar()
        assert cfg["last_port"] == "COM9"
        assert cfg["language"] == "en"

    def test_defaults_si_no_existe(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config_manager, "_CONFIG_PATH",
                            tmp_path / "nada.json")
        cfg = config_manager.cargar()
        assert cfg["language"] == "es"
        assert math.isfinite(len(cfg))
