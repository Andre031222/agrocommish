from core.lang import T
from ui import theme as th

PORT = "/dev/cu.usbserial-0001  —  CP2102 USB to UART Bridge Controller"
DEVICE_ID = "ESP32_0EBA38"

FLASH_LOG = [
    "esptool v5.2.0",
    "Connecting....",
    "Detecting chip type... ESP32",
    "Chip type:          ESP32-D0WD-V3 (revision v3.1)",
    "Features:           Wi-Fi, BT, Dual Core + LP Core, 240MHz",
    "Erasing flash (this may take a while)...",
    "Chip erase completed successfully in 9.8 seconds.",
    "Wrote 1123024 bytes (731451 compressed) at 0x00000000 in 21.4 seconds.",
    "Hash of data verified.",
]

NETWORKS = [
    {"ssid": "AgroLab-UNAP", "rssi": -42, "secure": True},
    {"ssid": "Invernadero-2", "rssi": -61, "secure": True},
    {"ssid": "Campo-Norte", "rssi": -70, "secure": True},
    {"ssid": "Huerto-Invitados", "rssi": -79, "secure": False},
]

SENSORS = [
    {"valor": 17.7, "unidad": "°C", "estado": "ok", "mensaje": "17.7 °C"},
    {"valor": 41.0, "unidad": "%", "estado": "ok", "mensaje": "41.0 %"},
    {"valor": 63.0, "unidad": "%", "estado": "ok", "mensaje": "63.0 %"},
]


def inject_demo(app):
    app._toast = lambda *args, **kwargs: None
    app._av_email.set("operador@agrolab.example")
    app._server_url.set("http://192.168.1.50:8099/api/sensores/lectura")
    app._puerto.set(PORT)
    app._set_port_status(True, PORT)

    for linea in FLASH_LOG:
        app._flash_linea(linea)
    app._flash_bar.set(1.0)
    app._lbl_flash_pct.configure(text="100 %")
    app._lbl_flash_fase.configure(text=T("s2_fase_listo"), text_color=th.SUCCESS)
    app._milestone("flash")

    app._device_id = DEVICE_ID
    app._render_net_cards(NETWORKS)
    app._select_net(NETWORKS[0]["ssid"])
    app._wifi_pass.set("demo-pass-123")
    msg, tone = app._interpretar_pines({"dht_pin": 15, "dht_state": "detected",
                                        "soil_pin": 34, "soil_state": "detected"})
    app._lbl_pins_st.configure(text=msg, text_color=th.TONES[tone][0])
    app._milestone("wifi")

    app._prepare_verify()
    app._show_sensor_results(SENSORS)
    app._render_qr(DEVICE_ID)
    app._show_step(0)
