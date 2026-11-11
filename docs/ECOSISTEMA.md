# Ecosistema AgroCommish + AgroYachay

## Visión general

AgroCommish y AgroYachay son dos aplicaciones independientes que cubren fases distintas del ciclo de vida de un dispositivo IoT agrícola. Una prepara el hardware. La otra lo opera.

---

## Las dos aplicaciones

```
┌─────────────────────────────────┐      ┌─────────────────────────────────┐
│         AgroCommish             │      │           AgroYachay            │
│         (.exe desktop)          │      │         (plataforma web)        │
├─────────────────────────────────┤      ├─────────────────────────────────┤
│  Quién lo usa: Técnico/Fábrica  │      │  Quién lo usa: Agricultor       │
│  Cuándo: Una sola vez           │      │  Cuándo: Siempre, en producción │
│  Dónde: PC del taller           │      │  Dónde: Navegador / servidor    │
│  Requiere internet: NO (USB)    │      │  Requiere internet: SÍ          │
└─────────────────────────────────┘      └─────────────────────────────────┘
```

---

## Ciclo de vida completo del dispositivo

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                        FASE 1 — MANUFACTURA / TALLER                       ║
║                         (herramienta: AgroCommish)                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   Técnico conecta ESP32 por USB                                             ║
║          │                                                                   ║
║          ▼                                                                   ║
║   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ║
║   │   Paso 1    │   │   Paso 2    │   │   Paso 3    │   │   Paso 4    │   ║
║   │  Detectar   │──▶│  Flashear   │──▶│  Configurar │──▶│  Verificar  │   ║
║   │  ESP32 USB  │   │  firmware   │   │  WiFi+URL   │   │  sensores   │   ║
║   │  (hotplug)  │   │  (.bin)     │   │  por serial │   │  DHT11+FC28 │   ║
║   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   ║
║                                                                  │           ║
║                                                                  ▼           ║
║                                                         ┌─────────────┐    ║
║                                                         │   Paso 5    │    ║
║                                                         │   Activar   │    ║
║                                                         │ en TerraSen │    ║
║                                                         │  JWT + QR   │    ║
║                                                         └─────────────┘    ║
║                                                                  │           ║
║                    ESP32 listo para entregar ◀────────────────────┘          ║
╚══════════════════════════════════════════════════════════════════════════════╝

                              │  Se entrega al agricultor
                              ▼

╔══════════════════════════════════════════════════════════════════════════════╗
║                      FASE 2 — CAMPO / PRODUCCIÓN                           ║
║                        (plataforma: AgroYachay)                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   ESP32 en el cultivo                                                        ║
║          │                                                                   ║
║          │  envía datos cada X minutos (HTTP POST)                          ║
║          ▼                                                                   ║
║   ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐   ║
║   │    Backend       │     │    Base de datos  │     │    Frontend      │   ║
║   │    Flask         │────▶│    PostgreSQL     │────▶│    React         │   ║
║   │    JWT + API     │     │    histórico      │     │    dashboard     │   ║
║   └──────────────────┘     └──────────────────┘     └──────────────────┘   ║
║                                                              │               ║
║                                                              ▼               ║
║                                                     Agricultor ve:           ║
║                                                     • Gráficas en tiempo real║
║                                                     • Alertas de riego       ║
║                                                     • Historial de sensores  ║
║                                                     • Estado del dispositivo ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## Qué configura AgroCommish dentro del ESP32

Cuando el técnico completa los 5 pasos, el ESP32 queda grabado con:

```
┌─────────────────────────────────────────────────────────┐
│                   ESP32 — Memoria NVS                   │
├─────────────────────────────────────────────────────────┤
│  WiFi SSID      →  "MiRedAgrícola"                      │
│  WiFi Password  →  "contraseña"                         │
│  Server URL     →  "http://192.168.1.100:5000/api/..."  │
│  Temp offset    →  0.0 °C                               │
│  Hum offset     →  0.0 %                                │
│  SOIL_DRY       →  50   (ADC en aire)                   │
│  SOIL_WET       →  3200 (ADC en agua)                   │
│  Device ID      →  "AC-ESP32-7F3A"  (único por unidad)  │
└─────────────────────────────────────────────────────────┘
```

Todo esto sin tocar el código del firmware — AgroCommish escribe la configuración en la NVS (Non-Volatile Storage) del ESP32 vía serial JSON.

---

## Flujo de datos en producción

```
 DHT11 (GPIO 15)                FC-28 (GPIO 34)
 Temperatura + Humedad aire     Humedad del suelo
        │                              │
        └──────────────┬───────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │     ESP32       │
              │  Lee sensores   │
              │  cada X minutos │
              └────────┬────────┘
                       │  HTTP POST
                       │  { "temperatura": 22.4,
                       │    "humedad_aire": 58.2,
                       │    "humedad_suelo": 34.1,
                       │    "device_id": "AC-ESP32-7F3A" }
                       ▼
              ┌─────────────────┐
              │  AgroYachay     │
              │  Backend Flask  │
              │  /api/sensores  │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  PostgreSQL     │
              │  histórico de   │
              │  lecturas       │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  React frontend │
              │  dashboard del  │
              │  agricultor     │
              └─────────────────┘
```

---

## Conexión entre AgroCommish y AgroYachay — Paso 5

El Paso 5 es el puente entre las dos aplicaciones. AgroCommish hace el login por el técnico y registra el dispositivo en AgroYachay automáticamente:

```
AgroCommish (desktop)              Backend AgroYachay           Frontend AgroYachay
        │                                  │                            │
        │  1. POST /api/auth/login          │                            │
        │  { username, password }           │                            │
        │──────────────────────────────────▶│                            │
        │                                  │  verifica bcrypt            │
        │                                  │  genera JWT (24 h)          │
        │  2. 200 OK — { token, user }      │                            │
        │◀──────────────────────────────────│                            │
        │                                  │                            │
        │  3. webbrowser.open(             │                            │
        │     /auto-login                  │                            │
        │     #token=JWT                   │                            │
        │     &redirect=dispositivos )     │                            │
        │──────────────────────────────────────────────────────────────▶│
        │                                  │                            │
        │                                  │  4. GET /api/auth/profile  │
        │                                  │◀───────────────────────────│
        │                                  │  { user data }             │
        │                                  │───────────────────────────▶│
        │                                  │                            │
        │                                  │         5. Redirige a      │
        │                                  │            /dispositivos   │
        │                                  │                            │
```

El agricultor ve su dispositivo registrado en AgroYachay sin haber hecho nada — el técnico lo activó desde AgroCommish.

---

## Independencia entre las dos aplicaciones

```
┌──────────────────────────────────────────────────────────────┐
│                    AgroCommish                               │
│                                                              │
│  -  Funciona SIN internet (solo necesita USB + WiFi local)  │
│  -  Funciona SIN AgroYachay instalado                       │
│  -  Puede configurar ESP32 para cualquier backend HTTP       │
│  -  .exe standalone — sin instalar Python                   │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    AgroYachay                                │
│                                                              │
│  -  Funciona con dispositivos configurados manualmente      │
│  -  No depende de AgroCommish para recibir datos            │
│  -  Puede recibir datos de ESP32 configurados de otra forma │
└──────────────────────────────────────────────────────────────┘

         Se integran en el Paso 5 — pero cada uno es autónomo.
```

---

## Resumen en una frase

> **AgroCommish prepara el hardware una sola vez. AgroYachay lo opera para siempre.**

El técnico usa AgroCommish en el taller antes de entregar el dispositivo.
El agricultor usa AgroYachay en el campo todos los días sin saber que AgroCommish existió.
