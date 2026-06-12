import serial.tools.list_ports

ESP32_CHIPS = [
    'CP210', 'CP2102', 'CP2104', 'CP2109',
    'CH340', 'CH341', 'CH342',
    'Silicon Labs',
    'USB Serial', 'USB-SERIAL',
    'USB to UART', 'UART Bridge',
    'FT232', 'FTDI',
    'USB2SERIAL',
]

EXCLUIR = [
    'bluetooth',
    'bth',
    'modem',
    'virtual',
    'vmware',
    'virtualbox',
    'parallels',
    'irda',
    'infrared',
    'serie estándar sobre',
    'standard serial over',
    'wlan',
    'wifi',
]


def _es_bluetooth_o_virtual(texto: str) -> bool:
    t = texto.lower()
    return any(ex in t for ex in EXCLUIR)


def detectar_puertos() -> list[dict]:
    puertos = []
    for p in serial.tools.list_ports.comports():
        desc  = (p.description  or '').strip()
        mfr   = (p.manufacturer or '').strip()
        hwid  = (p.hwid         or '').strip()
        texto = f"{desc} {mfr} {hwid}"

        if _es_bluetooth_o_virtual(texto):
            continue

        es_esp32 = any(kw.lower() in texto.lower() for kw in ESP32_CHIPS)

        puertos.append({
            'port':        p.device,
            'descripcion': desc or p.device,
            'es_esp32':    es_esp32,
        })

    return sorted(puertos, key=lambda x: (not x['es_esp32'], x['port']))


def puertos_como_set() -> set[str]:
    return {p.device for p in serial.tools.list_ports.comports()}
