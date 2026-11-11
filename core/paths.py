import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = BASE_DIR

FIRMWARE_DIR = BASE_DIR / "firmware"
LOGS_DIR = BASE_DIR / "logs"
LOGO = BUNDLE_DIR / "assets" / "logo.png"
ICON = BUNDLE_DIR / "assets" / "icon.ico"

_FW_BUNDLED = BUNDLE_DIR / "firmware" / "firmware.bin"
DEFAULT_FIRMWARE = _FW_BUNDLED if _FW_BUNDLED.exists() else FIRMWARE_DIR / "firmware.bin"
