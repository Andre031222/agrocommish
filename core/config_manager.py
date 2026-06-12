import json
import sys
from pathlib import Path


def _get_config_path() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / "config.json"
    return Path(__file__).parent.parent / "config.json"


_CONFIG_PATH = _get_config_path()

_DEFAULTS = {
    "server_url":    "",
    "last_ssid":     "",
    "last_firmware": "",
    "last_port":     "",
    "av_email":      "",
    "av_web_url":    "http://localhost:3000",
    "language":      "es",
}


def cargar() -> dict:
    try:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {**_DEFAULTS, **data}
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_DEFAULTS)


def guardar(**kwargs) -> None:
    current = cargar()
    current.update(kwargs)
    with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
