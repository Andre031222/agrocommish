import os
import re
import subprocess
import sys
from pathlib import Path


class Flasher:

    BAUD       = 460800
    FLASH_ADDR = '0x0'

    def __init__(self, port: str, firmware_path: str | Path):
        self.port          = port
        self.firmware_path = str(firmware_path)

    def validar(self) -> tuple[bool, str]:
        if not os.path.exists(self.firmware_path):
            return False, f"Archivo no encontrado:\n{self.firmware_path}"
        size = os.path.getsize(self.firmware_path)
        if size < 4096:
            return False, f"Firmware muy pequeño ({size} bytes), probablemente corrupto."
        return True, f"Firmware OK  ({size / 1024:.1f} KB)"

    def flashear(self, on_output=None, on_progress=None):
        ok, msg = self.validar()
        if not ok:
            raise FileNotFoundError(msg)

        cmd = self._build_cmd()

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                shell=False,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "No se encontró esptool.\n"
                "Instala con:  pip install esptool"
            )

        for line in proc.stdout:
            line = line.rstrip()
            if on_output:
                on_output(line)
            if on_progress:
                m = re.search(r'(\d+)\s*%', line)
                if m:
                    on_progress(min(100, int(m.group(1))))

        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(
                f"esptool terminó con código {proc.returncode}.\n"
                "Verifica que el ESP32 esté en modo bootloader (mantén BOOT presionado\n"
                "mientras conectas el USB) o usa un cable de datos."
            )

        if on_progress:
            on_progress(100)

    def _build_cmd(self) -> list[str]:
        esptool = self._find_esptool()
        return [
            *esptool,
            '--chip',        'auto',
            '--port',        self.port,
            '--baud',        str(self.BAUD),
            '--before',      'default-reset',
            '--after',       'hard-reset',
            'write-flash',
            '--erase-all',
            '-z',
            '--flash-mode',  'dio',
            '--flash-freq',  '40m',
            '--flash-size',  'detect',
            self.FLASH_ADDR,
            self.firmware_path,
        ]

    def _find_esptool(self) -> list[str]:
        if getattr(sys, 'frozen', False):
            p = Path(sys._MEIPASS) / 'esptool.exe'
            if p.exists():
                return [str(p)]

        python_exe = sys.executable
        for carpeta in (Path(python_exe).parent / 'Scripts', Path(python_exe).parent):
            for name in ('esptool.exe', 'esptool.py', 'esptool'):
                p = carpeta / name
                if p.exists():
                    if name.endswith('.py'):
                        return [python_exe, str(p)]
                    return [str(p)]

        return ['esptool']
