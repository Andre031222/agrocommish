# AgroCommish — Herramienta de Fabricación

Aplicación de escritorio (.exe) para desarrolladores y fabricantes.
Configura ESP32 + DHT11 + FC-28 de forma masiva antes de entregar el hardware al usuario final.

---

## Este producto vs el sistema web

| | `AgroCommish` | `TerraSense` |
| --- | --- | --- |
| **Quién lo usa** | Desarrollador / Fábrica | Usuario final (agricultor) |
| **Dónde corre** | PC del técnico | Servidor / cloud |
| **Cuándo se usa** | Una vez, antes de entregar el hardware | Siempre, en producción |
| **Qué configura** | El microprocesador ESP32 | La cuenta y los cultivos |
| **Requiere internet** | No (solo USB) | Sí |

---

## Flujo del técnico (5 pasos)

```text
Paso 1 — Detectar
  Conecta el ESP32 por USB → se detecta automáticamente (hotplug)

Paso 2 — Flashear
  Borra la flash completa y graba el firmware .bin con esptool
  Al reiniciar: identifica el dispositivo y AUTO-DETECTA en qué
  pines están conectados el DHT11 y el FC-28 (se guardan en NVS)

Paso 3 — Configurar
  Envía por serial: WiFi + URL del servidor (con verificación previa
  de que el servidor responde desde esta PC)
  Opcional: calibración de offsets y re-detección manual de pines

Paso 4 — Verificar
  Test automático en 3 niveles: comando serial → escucha pasiva de
  telemetría USB → consulta a la API del servidor
  Genera QR con el device_id · Exporta telemetría a CSV
  Marca como LISTO → registra hitos con timestamp en el log CSV

Paso 5 — Activar  ← integración con TerraSense
  Inicia sesión con credenciales del sistema web
  Obtiene un JWT y abre el navegador con auto-login → /dispositivos
```

---

## Sensores soportados

| Sensor | Pin por defecto | Lecturas | Rango normal |
| --- | --- | --- | --- |
| DHT11 | GPIO 15 (auto-detectable) | Temperatura (°C) | 5 – 45 °C |
| DHT11 | GPIO 15 (auto-detectable) | Humedad del aire (%) | 20 – 95 % |
| FC-28 | GPIO 34 (auto-detectable, solo ADC1: 32–39) | Humedad del suelo (%) | 0 – 100 % |

### Auto-detección de pines

Tras flashear, la app envía `{"cmd":"detect_pins"}` al firmware: este escanea
los GPIOs digitales buscando el protocolo del DHT11 y los pines ADC1 buscando
la señal del FC-28, persiste lo encontrado en NVS y la app muestra los pines
reales en la tabla de verificación. Para que el FC-28 se detecte con confianza
debe estar en tierra o con las puntas tocadas (señal > 400 ADC); en aire se
reporta como "posible" y conviene repetir con el botón 🔍 Detectar pines.

### Calibración (opcional)

Los offsets se guardan en la NVS del ESP32 (memoria no volátil).
No requieren recompilar el firmware. Efectivos inmediatamente.

| Parámetro | Por defecto | Descripción |
| --- | --- | --- |
| `TEMP_OFFSET` | 0.0 | Corrección en °C para DHT11 |
| `HUM_OFFSET` | 0.0 | Corrección en % para humedad del aire |
| `SOIL_DRY` | 50 | ADC del FC-28 en seco (en aire) |
| `SOIL_WET` | 3200 | ADC del FC-28 sumergido en agua |

---

## Instalación y uso

### Modo desarrollo (sin compilar)

```bash
pip install -r requirements.txt
python app.py
```

### Generar el .exe para distribuir

```bat
build.bat
```

El `.exe` se genera en `dist\AgroCommish.exe`. Para distribuir solo necesitas
`AgroCommish.exe` y `firmware\firmware.bin` en la misma carpeta.

---

## Obtener el firmware.bin

1. Abre el sketch `agrovision_provisioning.ino` en Arduino IDE 2.x
2. Instala las librerías: `ArduinoJson`, `DHT sensor library`, `Adafruit Unified Sensor`
3. Selecciona placa: **ESP32 Dev Module**
4. Menú: **Boceto → Exportar binario compilado**
5. Copia el `.bin` *merged* generado a `firmware/firmware.bin`

Ver detalles en [`firmware/INSTRUCCIONES.txt`](../firmware/INSTRUCCIONES.txt).

---

## Herramientas de línea de comandos

| Herramienta | Uso |
| --- | --- |
| `tools/capturar_datos.py` | Captura telemetría USB a CSV: `python tools/capturar_datos.py COM5 300 salida.csv` |
| `tools/medir_tiempos.py` | Estadísticas de tiempo de comisionado por unidad desde los logs de sesión |
| `tools/take_screenshots_win.py` | Capturas reproducibles de la interfaz |

---

## Integración con TerraSense (Paso 5)

AgroCommish hace `POST /api/auth/login` con las credenciales del técnico,
recibe un JWT y abre el navegador en `/auto-login#token=JWT&redirect=dispositivos`;
el frontend valida el token, lo guarda en `localStorage` y redirige a
**Dispositivos**, donde el equipo recién comisionado aparece como pendiente de
vincular a un cultivo. El diagrama completo del ecosistema y del flujo de
datos en producción está en [`ECOSISTEMA.md`](ECOSISTEMA.md).

Ambas aplicaciones son independientes: AgroCommish puede configurar el ESP32
contra cualquier backend HTTP, y TerraSense acepta dispositivos configurados
por otros medios.
