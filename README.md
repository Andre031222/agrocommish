# AgroCommish: An Integrated Desktop Tool for End-to-End Manufacturing and Commissioning of ESP32-Based Agricultural IoT Devices

**Status:** Manuscript in preparation for SoftwareX (Elsevier)
**Software DOI:** [10.5281/zenodo.20655610](https://doi.org/10.5281/zenodo.20655610)
**License:** [MIT](LICENSE)
**Latest release:** [v1.0.0](https://github.com/Andre031222/agrocommish/releases/tag/v1.0.0) (standalone Windows executable + firmware)

[![CI](https://img.shields.io/github/actions/workflow/status/Andre031222/agrocommish/ci.yml?style=flat-square&label=CI)](https://github.com/Andre031222/agrocommish/actions/workflows/ci.yml)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20655610-1d4ed8?style=flat-square)](https://doi.org/10.5281/zenodo.20655610)
[![License: MIT](https://img.shields.io/badge/License-MIT-15803d?style=flat-square)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-64748b?style=flat-square)](https://www.python.org/)

---

## Authors

| Name | Institution |
| --- | --- |
| Richar Andre Vilca-Solorzano | Universidad Nacional del Altiplano de Puno, Peru |
| Dina Maribel Yana-Yucra | Universidad Nacional del Altiplano de Puno, Peru |
| Renato Quispe-Vargas | Universidad Nacional del Altiplano de Puno, Peru |
| Fred Torres-Cruz | Universidad Nacional del Altiplano de Puno, Peru |

**Faculty:** Ingenieria Estadistica e Informatica — Universidad Nacional del Altiplano (UNA), Puno, Peru

---

## Overview

Deploying ESP32-based sensor nodes at scale requires a repeatable manufacturing
workflow executable by technicians with limited software expertise. The
conventional approach fragments this workflow across multiple disconnected
tools: command-line flashers, custom provisioning scripts, hand-written serial
monitor sessions, and manual cloud registration. Each transition introduces
error-prone steps and increases the field failure rate of deployed nodes.

**AgroCommish** integrates the complete commissioning pipeline for ESP32 +
DHT11 + FC-28 agricultural sensor nodes into a single five-step desktop
wizard. A technician takes a bare ESP32 board to a fully flashed, provisioned,
verified, and cloud-registered sensor node in minutes — without touching a
terminal. A systematic comparison against 13 publicly available tools shows
that no prior tool covers the full pipeline.

![AgroCommish wizard](docs/screenshot.png)

---

## Key Features

| Step | Function |
| --- | --- |
| 1. Detect | Automatic USB/COM port discovery with live hotplug monitoring; positive identification of CP210x, CH340/341, and FT232 bridges |
| 2. Flash | Full-erase firmware flashing via esptool (`--chip auto`: ESP32, S3, C6) with a phased progress indicator, followed by automatic discovery of the GPIO pins where the sensors are physically wired (persisted to device NVS) |
| 3. Configure | WiFi and ingestion-endpoint provisioning over a newline-framed JSON serial protocol; on-device network scanning with RSSI; pre-flight server reachability diagnostics; optional sensor calibration without recompiling |
| 4. Verify | Three-channel sensor verification (JSON command, passive USB telemetry listening, ingestion API polling) validated against physical and agronomic ranges; QR label generation; one-click telemetry export to CSV |
| 5. Activate | JWT-based auto-login into the TerraSense web platform; the browser opens with the session already active |

Additional capabilities: bilingual English/Spanish interface switchable at
runtime, per-milestone commissioning audit logs (CSV), toast notifications,
and a standalone telemetry capture utility for building validation datasets.

### Automatic sensor pin discovery

After flashing, AgroCommish issues a `detect_pins` command. The firmware
probes the DHT11 single-wire protocol across 17 candidate digital GPIOs and
scans the six ADC1 channels for the characteristic signal of the FC-28
analogue output (mean and dispersion heuristics over 16 samples per pin),
persists the discovered pin map to non-volatile storage, and reports it to
the operator — eliminating wiring-dependent configuration entirely.

---

## Repository Structure

```text
agrocommish/
│
├── app.py                       # GUI application (five-step wizard)
├── core/                        # Hardware-agnostic core modules
│   ├── detector.py              # USB/COM enumeration and ESP32 identification
│   ├── flasher.py               # esptool subprocess driver (full-erase, chip auto)
│   ├── provisioner.py           # JSON-over-serial protocol + telemetry capture
│   ├── config_manager.py        # Session persistence (config.json)
│   ├── qr_generator.py          # QR label generation
│   └── lang.py                  # EN/ES runtime internationalisation
├── firmware/
│   └── INSTRUCCIONES.txt        # Firmware build instructions (Arduino IDE)
├── tools/
│   ├── capturar_datos.py        # USB telemetry recorder (calibrated + raw ADC)
│   ├── medir_tiempos.py         # Commissioning-time statistics from audit logs
│   └── take_screenshots_win.py  # Reproducible UI captures
├── tests/
│   └── test_core.py             # Unit tests (pytest, 20 tests)
├── docs/
│   ├── README.es.md             # Documentation in Spanish
│   └── ECOSISTEMA.md            # AgroCommish + TerraSense ecosystem overview
├── .github/workflows/ci.yml     # CI: pyflakes + pytest on Windows/Ubuntu
├── AgroCommish.spec             # PyInstaller build definition
├── build.bat                    # One-command executable build
├── CITATION.cff                 # Citation metadata
└── requirements.txt
```

---

## Installation

### Option A — Windows binary (no installation required)

Download `AgroCommish.exe` and `firmware.bin` from the
[latest release](https://github.com/Andre031222/agrocommish/releases) and
arrange them as:

```text
AgroCommish.exe
firmware/firmware.bin
```

### Option B — From source

```bash
git clone https://github.com/Andre031222/agrocommish.git
cd agrocommish
pip install -r requirements.txt
python app.py
```

Requires Python 3.9 or later. Tested on Windows 10/11; core modules are
platform-independent (Linux/macOS supported from source).

### Building the executable

```bat
build.bat
```

Produces a standalone `dist/AgroCommish.exe` via PyInstaller.

---

## Firmware

The companion ESP32 firmware (Arduino) implements the JSON serial protocol
(`identify`, `scan`, `config`, `calibrate`, `read_sensors`, `detect_pins`,
`set_pins`), a captive-portal fallback for browser-based provisioning, NVS
persistence of all configuration, an offline telemetry buffer, and periodic
HTTP delivery. Build instructions are in
[`firmware/INSTRUCCIONES.txt`](firmware/INSTRUCCIONES.txt); a precompiled
`firmware.bin` ships with each release.

---

## Companion Tools

| Tool | Purpose |
| --- | --- |
| `tools/capturar_datos.py` | Record live USB telemetry (calibrated values, raw DHT11 readings, raw 12-bit ADC, HTTP delivery status) to CSV: `python tools/capturar_datos.py COM5 300 out.csv` |
| `tools/medir_tiempos.py` | Per-unit commissioning-time statistics (mean, median, range) from the session audit logs |
| `tools/take_screenshots_win.py` | Reproducible UI captures for documentation |

---

## Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

Continuous integration runs static analysis (pyflakes) and the full test
suite on Windows and Ubuntu with Python 3.11 and 3.12 on every push.

---

## Citation

If you use this software, please cite:

```bibtex
@software{vilca2026agrocommish,
  author  = {Vilca Solorzano, Richar Andre and Yana Yucra, Dina Maribel and
             Quispe Vargas, Renato and Torres Cruz, Fred},
  title   = {AgroCommish: An Integrated Desktop Tool for End-to-End
             Manufacturing and Commissioning of ESP32-Based Agricultural
             IoT Devices},
  year    = {2026},
  version = {1.0.0},
  doi     = {10.5281/zenodo.20655610},
  url     = {https://github.com/Andre031222/agrocommish}
}
```

Citation metadata is also available in [`CITATION.cff`](CITATION.cff)
(GitHub: "Cite this repository").

---

## License

This project is licensed under the [MIT License](LICENSE).

## Documentation in Spanish

See [`docs/README.es.md`](docs/README.es.md).
