<!-- ============================================================
     HERO HEADER
     ============================================================ -->
<div align="center">

<img src="https://raw.githubusercontent.com/Andre031222/agrocommish/main/assets/logo.png" height="100" alt="AgroCommish logo"/>

# AgroCommish

### Plug-and-play desktop tool for end-to-end manufacturing &amp; commissioning of ESP32-based agricultural IoT sensor nodes

<p>
  <a href="https://doi.org/10.5281/zenodo.20655610"><img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20655610-1d4ed8?style=for-the-badge"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-2E7D32?style=for-the-badge"></a>
  <a href="https://github.com/Andre031222/agrocommish/releases/tag/v1.0.0"><img src="https://img.shields.io/badge/Release-v1.0.0-0F2444?style=for-the-badge&logo=github&logoColor=white"></a>
  <img src="https://img.shields.io/badge/SoftwareX-in%20preparation-616161?style=for-the-badge">
  <a href="https://github.com/Andre031222/agroyachay"><img src="https://img.shields.io/badge/Companion-AgroYachay-2E7D32?style=for-the-badge&logo=github&logoColor=white"></a>
</p>

<p>
  <a href="https://github.com/Andre031222/agrocommish/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/Andre031222/agrocommish/ci.yml?style=flat-square&label=CI"></a>
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-555?style=flat-square">
  <img src="https://img.shields.io/badge/Python-3.9%2B-64748b?style=flat-square&logo=python&logoColor=white">
</p>

<p align="center">
  <em>
    From a bare <b>ESP32</b> board to a flashed, provisioned, verified and
    cloud-registered sensor node in <b>minutes</b> &mdash; through a single
    five-step desktop wizard, without ever touching a terminal.
  </em>
</p>

<p align="center">
  <a href="https://github.com/Andre031222/agrocommish">
    <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=18&duration=2800&pause=900&color=2E7D32&center=true&vCenter=true&width=820&lines=detect+-%3E+flash+-%3E+configure+-%3E+verify+-%3E+activate;automatic+ESP32+chip+%26+sensor-pin+discovery;JSON-over-serial+provisioning+%2B+telemetry+capture;one+technician%2C+no+terminal%2C+~51s+per+unit;feeds+verified+nodes+to+the+AgroYachay+cloud">
  </a>
</p>

<img src="docs/screenshot.png" width="760" alt="AgroCommish five-step wizard"/>

</div>

---

## Tech stack

<div align="center">
  <img height="46" alt="Python"  src="https://raw.githubusercontent.com/devicons/devicon/master/icons/python/python-original.svg">
  <img height="46" alt="Arduino" src="https://raw.githubusercontent.com/devicons/devicon/master/icons/arduino/arduino-original.svg">
  &nbsp;
  <img src="https://img.shields.io/badge/ESP32-000000?style=flat-square&logo=espressif&logoColor=white">
  <img src="https://img.shields.io/badge/esptool-3C3C3C?style=flat-square">
  <img src="https://img.shields.io/badge/PyInstaller-FFD43B?style=flat-square&logo=python&logoColor=black">
</div>

---

## Authors

| Name | Institution |
| --- | --- |
| Richar Andre Vilca-Solorzano | Universidad Nacional del Altiplano de Puno, Peru |
| Dina Maribel Yana-Yucra | Universidad Nacional del Altiplano de Puno, Peru |
| Renato Quispe-Vargas | Universidad Nacional del Altiplano de Puno, Peru |
| Vladimiro Ibañez-Quispe | Universidad Nacional del Altiplano de Puno, Peru |
| Fred Torres-Cruz | Universidad Nacional del Altiplano de Puno, Peru |

**Faculty:** Ingeniería Estadística e Informática — Universidad Nacional del Altiplano (UNAP), Puno, Peru

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

AgroCommish is the device-side counterpart of the
**[AgroYachay](https://github.com/Andre031222/agroyachay)** cloud platform;
together they form an open, reproducible *device-to-decision* pipeline for
low-resource agriculture.

---

## Key Features

| Step | Function |
| --- | --- |
| 1. Detect | Automatic USB/COM port discovery with live hotplug monitoring; positive identification of CP210x, CH340/341, and FT232 bridges |
| 2. Flash | Full-erase firmware flashing via esptool (`--chip auto`: ESP32, S3, C6) with a phased progress indicator, followed by automatic discovery of the GPIO pins where the sensors are physically wired (persisted to device NVS) |
| 3. Configure | WiFi and ingestion-endpoint provisioning over a newline-framed JSON serial protocol; on-device network scanning with RSSI; pre-flight server reachability diagnostics; optional sensor calibration without recompiling |
| 4. Verify | Three-channel sensor verification (JSON command, passive USB telemetry listening, ingestion API polling) validated against physical and agronomic ranges; QR label generation; one-click telemetry export to CSV |
| 5. Activate | JWT-based auto-login into the **AgroYachay** web platform; the browser opens with the session already active |

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
│   ├── benchmark_comisionado.py # Unattended commissioning benchmark
│   ├── medir_tiempos.py         # Commissioning-time statistics from audit logs
│   └── take_screenshots_win.py  # Reproducible UI captures
├── data/                        # Reference datasets (telemetry + benchmark)
├── tests/
│   └── test_core.py             # Unit tests (pytest, 20 tests)
├── docs/
│   ├── README.es.md             # Documentation in Spanish
│   └── ECOSISTEMA.md            # AgroCommish + AgroYachay ecosystem overview
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
| `tools/benchmark_comisionado.py` | Unattended end-to-end commissioning benchmark (N timed runs with per-phase breakdown): `python tools/benchmark_comisionado.py COM5 SSID PASS 5` |
| `tools/medir_tiempos.py` | Per-unit commissioning-time statistics (mean, median, range) from the session audit logs |
| `tools/take_screenshots_win.py` | Reproducible UI captures for documentation |

Reference datasets recorded with these utilities on real hardware
(ESP32 + DHT11 + FC-28) are included under [`data/`](data/): a five-minute
telemetry capture and a five-run commissioning benchmark
(median 51.0 s per unit).

---

## Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

Continuous integration runs static analysis (pyflakes) and the full test
suite on Windows and Ubuntu with Python 3.11 and 3.12 on every push.

---

## Companion Ecosystem

| Project | Role | Reference |
| --- | --- | --- |
| **AgroCommish** (this repo) | Manufactures and commissions ESP32 sensor nodes (detect → flash → provision → verify → activate) | [![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20655610-1d4ed8?style=flat-square)](https://doi.org/10.5281/zenodo.20655610) |
| **[AgroYachay](https://github.com/Andre031222/agroyachay)** | Cloud decision platform: monitoring, LLM agronomy, yield/revenue, reports | [![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20829993-1d4ed8?style=flat-square)](https://doi.org/10.5281/zenodo.20829993) |

---

## Citation

If you use this software, please cite:

```bibtex
@software{vilca2026agrocommish,
  author  = {Vilca Solorzano, Richar Andre and Yana Yucra, Dina Maribel and
             Quispe Vargas, Renato and Iba{\~n}ez Quispe, Vladimiro and
             Torres Cruz, Fred},
  title   = {AgroCommish: A Plug-and-Play Desktop Tool for End-to-End
             Manufacturing and Commissioning of ESP32-Based Agricultural
             IoT Sensor Nodes},
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
See Spanish documentation in [`docs/README.es.md`](docs/README.es.md).

<div align="center">
<sub>Part of an open device-to-decision pipeline for Andean smallholder agriculture · Universidad Nacional del Altiplano (UNAP), Puno, Peru</sub>
</div>
