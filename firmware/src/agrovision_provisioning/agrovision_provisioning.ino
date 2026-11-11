/*
 * ═══════════════════════════════════════════════════════════════
 *   AgroVision ESP32 — Firmware con WiFi Provisioning
 * ═══════════════════════════════════════════════════════════════
 *
 *  PRIMER USO (sin credenciales guardadas):
 *  ─────────────────────────────────────────
 *  1. El ESP32 crea una red WiFi llamada "AgroVision-Setup-XXXX"
 *  2. Conectar el celular/PC a esa red (sin contraseña)
 *  3. Se abre automáticamente el portal de configuración
 *     (o abrir navegador → 192.168.4.1)
 *  4. Seleccionar red WiFi, ingresar contraseña, guardar
 *  5. El ESP32 se conecta y empieza a enviar datos
 *  6. En el panel AgroVision, el dispositivo aparece como
 *     "Pendiente" — el usuario lo vincula a su cultivo
 *
 *  DESVINCULAR / RESET de fábrica:
 *  ─────────────────────────────────
 *  - Mantener presionado el botón BOOT (GPIO0) por 5 segundos
 *  - El LED parpadeará 5 veces y el dispositivo vuelve al
 *    modo de configuración (borra credenciales WiFi)
 *
 *  INDICADORES LED:
 *  ─────────────────
 *  - Parpadeo muy rápido (100ms): Modo Setup activo
 *  - Parpadeo lento (1000ms):     Conectando a WiFi
 *  - 1 parpadeo corto / 10s:      Enviando datos correctamente
 *  - 3 parpadeos rápidos:         Error al enviar
 *
 *  HARDWARE (pines por defecto — auto-detectables):
 *  ──────────
 *  DHT11:  VCC→3V3  DATA→GPIO15  GND→GND
 *  FC-28:  VCC→3V3  A0→GPIO34   GND→GND
 *  LED:    Ánodo→GPIO2 (LED integrado ESP32)
 *
 *  Si los sensores están en otros pines, el comando serial
 *  {"cmd":"detect_pins"} los localiza automáticamente (DHT11 en
 *  GPIOs digitales; FC-28 en ADC1) y los persiste en NVS.
 *  También se pueden fijar a mano con {"cmd":"set_pins",...}.
 *
 *  LIBRERÍAS REQUERIDAS (Gestor de librerías Arduino):
 *  ─────────────────────────────────────────────────────
 *  - ArduinoJson  (versión 6.x, by Benoit Blanchon)
 *  - DHT sensor library  (by Adafruit)
 *  - Adafruit Unified Sensor (dependencia de DHT)
 * ═══════════════════════════════════════════════════════════════
 */

#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <time.h>
#include "esp_mac.h"       // Para leer MAC desde eFuse sin depender del estado WiFi

// ─── Pines de hardware ───────────────────────────────────────
#define DHT_PIN          15
#define DHT_TYPE         DHT11
#define SOIL_PIN         34
#define LED_PIN           2
#define RESET_BTN_PIN     0   // Botón BOOT del ESP32

// ─── Calibración sensor DHT11 ────────────────────────────────
// Offsets de corrección para temperatura y humedad del aire.
// Si el sensor lee diferente a un termómetro/higrómetro de referencia,
// ajusta estos valores. Ej: si sensor lee 28°C y la realidad es 25°C → -3.0
// Ej: si sensor lee 70% humedad y la realidad es 65% → -5.0
#define TEMP_OFFSET       0.0   // °C  — ajustar tras comparar con referencia
#define HUM_AIRE_OFFSET   0.0   // %   — ajustar tras comparar con referencia

// ─── Calibración sensor de suelo FC-28 ───────────────────────
// El módulo FC-28 en configuración estándar:
//   EN AIRE (seco): AO ≈ 0–300   → debe mostrar 0%
//   EN AGUA (húmedo): AO ≈ 2800–4095 → debe mostrar 100%
// Si tu sensor lee al revés ajusta SOIL_DRY y SOIL_WET
#define SOIL_DRY         50   // ADC en aire/seco  — medido: ~25, margen ±25
#define SOIL_WET       3200   // ADC en agua/húmedo (FC-28 típico sumergido)

// ─── Configuración de red de Setup ───────────────────────────
#define SETUP_SSID_PREFIX  "AgroVision-Setup"
#define SETUP_PASS         ""          // Red abierta para fácil acceso
#define AP_IP_STR          "192.168.4.1"
#define DNS_PORT           53

// ─── Configuración NTP ───────────────────────────────────────
#define NTP_SERVER         "pool.ntp.org"
#define GMT_OFFSET_SEC     -18000      // UTC-5 Perú
#define DAYLIGHT_OFFSET    0

// ─── Temporización ───────────────────────────────────────────
#define SEND_INTERVAL_MS   10000       // 10 s entre envíos
#define WIFI_TIMEOUT_MS    20000       // 20 s máximo para conectar
#define RESET_HOLD_MS       5000       // Mantener BOOT 5 s para resetear
#define HTTP_TIMEOUT_MS     8000       // 8 s timeout HTTP

// ─── Clave NVS ───────────────────────────────────────────────
#define NVS_NS             "agrovision"
#define NVS_KEY_SSID       "wifi_ssid"
#define NVS_KEY_PASS       "wifi_pass"
#define NVS_KEY_SERVER     "server_url"
// Claves de calibracion (max 15 chars)
#define NVS_KEY_TEMP_OFF   "cal_temp"
#define NVS_KEY_HUM_OFF    "cal_hum"
#define NVS_KEY_SOIL_DRY   "cal_dry"
#define NVS_KEY_SOIL_WET   "cal_wet"
// Claves de pines detectados/configurados
#define NVS_KEY_PIN_DHT    "pin_dht"
#define NVS_KEY_PIN_SOIL   "pin_soil"

// ─── Estado global ───────────────────────────────────────────
enum DeviceState { STATE_SETUP, STATE_CONNECTING, STATE_RUNNING, STATE_ERROR };
DeviceState deviceState = STATE_SETUP;

DHT*         dht = nullptr;
WebServer    httpServer(80);
DNSServer    dnsServer;
Preferences  prefs;

String  esp32Id     = "";
String  wifiSSID    = "";
String  wifiPass    = "";
String  serverURL   = "";

// ─── Calibracion en tiempo de ejecucion (desde NVS) ──────────
// Los #define son solo los valores por defecto del primer arranque.
float calTempOffset = TEMP_OFFSET;
float calHumOffset  = HUM_AIRE_OFFSET;
int   calSoilDry    = SOIL_DRY;
int   calSoilWet    = SOIL_WET;

// ─── Pines en tiempo de ejecucion (desde NVS) ────────────────
// Los #define DHT_PIN / SOIL_PIN son solo defaults del primer arranque.
// El comando serial "detect_pins" puede re-detectarlos y persistirlos.
int   pinDht  = DHT_PIN;
int   pinSoil = SOIL_PIN;

// Pines candidatos para auto-deteccion (excluye 0=BOOT, 2=LED y pines
// de flash/strapping problematicos). El orden es por probabilidad.
const int DHT_CANDIDATES[]  = {15, 4, 5, 13, 14, 16, 17, 18, 19,
                               21, 22, 23, 25, 26, 27, 32, 33};
// Solo ADC1: ADC2 queda inutilizable con el WiFi AP del modo Setup
const int SOIL_CANDIDATES[] = {34, 35, 32, 33, 36, 39};

void initDht() {
  if (dht) delete dht;
  dht = new DHT(pinDht, DHT_TYPE);
  dht->begin();
}

unsigned long lastSendMs       = 0;
unsigned long resetBtnPressMs  = 0;
bool          resetBtnActive   = false;
bool          ntpSynced        = false;
bool          ledState         = false;
unsigned long lastLedToggle    = 0;

// ─── Buffer offline (hasta 10 lecturas si sin conexión) ──────
#define OFFLINE_BUF 10
struct Lectura { float temp; float humAire; int humSuelo; time_t ts; };
Lectura offlineBuffer[OFFLINE_BUF];
int offlineCount = 0;

// ═══════════════════════════════════════════════════════════════
//  HTML del portal de configuración — ver portal_html.h
// ═══════════════════════════════════════════════════════════════
#include "portal_html.h"
// ═══════════════════════════════════════════════════════════════
//  Utilidades: NVS / preferencias
// ═══════════════════════════════════════════════════════════════
void loadPrefs() {
  prefs.begin(NVS_NS, true);
  wifiSSID      = prefs.getString(NVS_KEY_SSID,   "");
  wifiPass      = prefs.getString(NVS_KEY_PASS,   "");
  serverURL     = prefs.getString(NVS_KEY_SERVER, "");
  // Calibracion — usa los #define como fallback si nunca se calibro
  calTempOffset = prefs.getFloat(NVS_KEY_TEMP_OFF, TEMP_OFFSET);
  calHumOffset  = prefs.getFloat(NVS_KEY_HUM_OFF,  HUM_AIRE_OFFSET);
  calSoilDry    = prefs.getInt(NVS_KEY_SOIL_DRY,   SOIL_DRY);
  calSoilWet    = prefs.getInt(NVS_KEY_SOIL_WET,   SOIL_WET);
  pinDht        = prefs.getInt(NVS_KEY_PIN_DHT,    DHT_PIN);
  pinSoil       = prefs.getInt(NVS_KEY_PIN_SOIL,   SOIL_PIN);
  prefs.end();
  Serial.printf("[NVS] Cal: T=%.1f H=%.1f DRY=%d WET=%d  Pines: DHT=%d SOIL=%d\n",
                calTempOffset, calHumOffset, calSoilDry, calSoilWet,
                pinDht, pinSoil);
}

void savePrefs(const String& ssid, const String& pass, const String& srv) {
  prefs.begin(NVS_NS, false);
  prefs.putString(NVS_KEY_SSID,   ssid);
  prefs.putString(NVS_KEY_PASS,   pass);
  prefs.putString(NVS_KEY_SERVER, srv);
  prefs.end();
}

void saveCalibration(float tempOff, float humOff, int soilDry, int soilWet) {
  prefs.begin(NVS_NS, false);
  prefs.putFloat(NVS_KEY_TEMP_OFF, tempOff);
  prefs.putFloat(NVS_KEY_HUM_OFF,  humOff);
  prefs.putInt(NVS_KEY_SOIL_DRY,   soilDry);
  prefs.putInt(NVS_KEY_SOIL_WET,   soilWet);
  prefs.end();
  // Actualiza globales inmediatamente — sin reinicio necesario
  calTempOffset = tempOff;
  calHumOffset  = humOff;
  calSoilDry    = soilDry;
  calSoilWet    = soilWet;
  Serial.printf("[CAL] Guardado: T=%.1f H=%.1f DRY=%d WET=%d\n",
                calTempOffset, calHumOffset, calSoilDry, calSoilWet);
}

void savePins(int newDht, int newSoil) {
  prefs.begin(NVS_NS, false);
  prefs.putInt(NVS_KEY_PIN_DHT,  newDht);
  prefs.putInt(NVS_KEY_PIN_SOIL, newSoil);
  prefs.end();
  bool dhtChanged = (newDht != pinDht);
  pinDht  = newDht;
  pinSoil = newSoil;
  if (dhtChanged || !dht) initDht();
  analogSetPinAttenuation(pinSoil, (adc_attenuation_t)3);
  Serial.printf("[PINES] Guardado: DHT=%d SOIL=%d\n", pinDht, pinSoil);
}

void clearPrefs() {
  prefs.begin(NVS_NS, false);
  prefs.clear();
  prefs.end();
  // Restaurar calibracion y pines a defaults de compilacion
  calTempOffset = TEMP_OFFSET;
  calHumOffset  = HUM_AIRE_OFFSET;
  calSoilDry    = SOIL_DRY;
  calSoilWet    = SOIL_WET;
  pinDht        = DHT_PIN;
  pinSoil       = SOIL_PIN;
  Serial.println("[RESET] Credenciales y calibracion borradas");
}

// ═══════════════════════════════════════════════════════════════
//  Generación de ID único por MAC (lee directamente del eFuse)
// ═══════════════════════════════════════════════════════════════
String buildDeviceId() {
  uint8_t mac[6];
  esp_efuse_mac_get_default(mac);   // Siempre disponible, no depende de WiFi
  char buf[24];
  snprintf(buf, sizeof(buf), "ESP32_%02X%02X%02X", mac[3], mac[4], mac[5]);
  return String(buf);
}

// ═══════════════════════════════════════════════════════════════
//  LED helpers
// ═══════════════════════════════════════════════════════════════
void blink(int n, int onMs = 150, int offMs = 100) {
  for (int i = 0; i < n; i++) {
    digitalWrite(LED_PIN, HIGH); delay(onMs);
    digitalWrite(LED_PIN, LOW);  delay(offMs);
  }
}

// Parpadeo no bloqueante en el loop (sólo modo SETUP)
void ledSetupTick() {
  if (millis() - lastLedToggle >= 150) {
    lastLedToggle = millis();
    ledState = !ledState;
    digitalWrite(LED_PIN, ledState);
  }
}

// ═══════════════════════════════════════════════════════════════
//  Sensor readings
// ═══════════════════════════════════════════════════════════════
bool leerSensores(float &temp, float &humAire, int &humSuelo) {
  if (!dht) initDht();
  float rawTemp = dht->readTemperature();
  float rawHum  = dht->readHumidity();

  if (isnan(rawTemp) || isnan(rawHum)) {
    Serial.println("[SENSOR] Error lectura DHT11");
    return false;
  }

  // Aplicar offsets de calibracion (desde NVS, ajustables sin recompilar)
  temp    = rawTemp + calTempOffset;
  humAire = constrain(rawHum + calHumOffset, 0.0, 100.0);

  Serial.printf("[DHT11] raw=%.1f°C/%.0f%%  calibrado=%.1f°C/%.0f%%  (offset T=%.1f H=%.1f)\n",
                rawTemp, rawHum, temp, humAire, calTempOffset, calHumOffset);

  // Promedio de 5 lecturas ADC para estabilizar el FC-28
  long rawSum = 0;
  for (int i = 0; i < 5; i++) { rawSum += analogRead(pinSoil); delay(5); }
  int raw = rawSum / 5;
  humSuelo = constrain(map(raw, calSoilDry, calSoilWet, 0, 100), 0, 100);
  Serial.printf("[SUELO] raw ADC=%d  →  humSuelo=%d%%  (DRY=%d WET=%d)\n",
                raw, humSuelo, calSoilDry, calSoilWet);

  return true;
}

// ═══════════════════════════════════════════════════════════════
//  NTP
// ═══════════════════════════════════════════════════════════════
void sincronizarNTP() {
  configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET, NTP_SERVER);
  struct tm t;
  int tries = 0;
  while (!getLocalTime(&t) && tries++ < 20) { delay(500); Serial.print("."); }
  Serial.println();
  ntpSynced = getLocalTime(&t);
  if (ntpSynced) Serial.println("[NTP] Sincronizado OK");
  else           Serial.println("[NTP] Sin sincronizar — se usará millis()");
}

time_t timestampActual() {
  struct tm t;
  if (ntpSynced && getLocalTime(&t)) return mktime(&t);
  return millis() / 1000;
}

// ═══════════════════════════════════════════════════════════════
//  HTTP POST al servidor
// ═══════════════════════════════════════════════════════════════
bool enviarLectura(float temp, float humAire, int humSuelo, time_t ts) {
  if (WiFi.status() != WL_CONNECTED) return false;
  if (serverURL.length() == 0) {
    Serial.println("[HTTP] serverURL vacía, no se envía");
    return false;
  }

  HTTPClient http;
  http.begin(serverURL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(HTTP_TIMEOUT_MS);

  JsonDocument doc;
  doc["esp32_id"]    = esp32Id;
  doc["temperatura"] = temp;
  doc["humedad_aire"]  = humAire;
  doc["humedad_suelo"] = humSuelo;
  doc["timestamp"]   = (long)ts;

  String body;
  serializeJson(doc, body);

  int code = http.POST(body);
  bool ok  = (code == 200 || code == 201);

  if (ok) {
    Serial.printf("[HTTP] OK %d → temp=%.1f hum=%.0f suelo=%d%%\n", code, temp, humAire, humSuelo);
    blink(1, 80, 0);   // parpadeo rápido de confirmación
  } else {
    Serial.printf("[HTTP] Error %d\n", code);
    blink(3, 80, 80);
  }
  http.end();
  return ok;
}

// ─── Reenvío del buffer offline ──────────────────────────────
void reenviarBuffer() {
  if (offlineCount == 0) return;
  Serial.printf("[BUFFER] Reenviando %d lecturas offline\n", offlineCount);
  int enviados = 0;
  for (int i = 0; i < offlineCount; i++) {
    if (enviarLectura(offlineBuffer[i].temp, offlineBuffer[i].humAire,
                      offlineBuffer[i].humSuelo, offlineBuffer[i].ts)) {
      enviados++;
    }
    delay(200);
  }
  offlineCount = 0;
  Serial.printf("[BUFFER] Reenviados %d / %d\n", enviados, offlineCount);
}

// ═══════════════════════════════════════════════════════════════
//  MODO SETUP — rutas del servidor web
// ═══════════════════════════════════════════════════════════════

// Redirige todo a la página principal (captive portal en iOS/Android)
void handleRedirect() {
  httpServer.sendHeader("Location", "http://192.168.4.1/", true);
  httpServer.send(302, "text/plain", "");
}

void handleRoot() {
  httpServer.send(200, "text/html", SETUP_HTML);
}

void handleScan() {
  // Escaneo sincrónico — se hace aquí para no bloquear el boot
  int n = WiFi.scanNetworks(false, true);   // sync, incluye redes ocultas
  if (n < 0) n = 0;
  JsonDocument doc;
  JsonArray nets = doc["networks"].to<JsonArray>();
  for (int i = 0; i < n && i < 12; i++) {
    JsonObject net = nets.add<JsonObject>();
    net["ssid"]   = WiFi.SSID(i);
    net["rssi"]   = WiFi.RSSI(i);
    net["secure"] = (WiFi.encryptionType(i) != WIFI_AUTH_OPEN);
  }
  String out;
  serializeJson(doc, out);
  httpServer.send(200, "application/json", out);
}

void handleInfo() {
  JsonDocument doc;
  doc["device_id"]  = esp32Id;
  doc["server_url"] = serverURL;
  String out;
  serializeJson(doc, out);
  httpServer.send(200, "application/json", out);
}

void handleSave() {
  if (!httpServer.hasArg("plain")) {
    httpServer.send(400, "application/json", "{\"success\":false,\"message\":\"Sin datos\"}");
    return;
  }
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, httpServer.arg("plain"));
  if (err) {
    httpServer.send(400, "application/json", "{\"success\":false,\"message\":\"JSON inválido\"}");
    return;
  }

  String newSSID = doc["ssid"].as<String>();
  String newPass = doc["pass"].as<String>();
  String newSrv  = doc["server_url"].as<String>();

  if (newSSID.length() == 0) {
    httpServer.send(400, "application/json", "{\"success\":false,\"message\":\"SSID requerido\"}");
    return;
  }

  savePrefs(newSSID, newPass, newSrv);
  httpServer.send(200, "application/json", "{\"success\":true}");

  Serial.println("[SETUP] Credenciales guardadas. Reiniciando en 2s...");
  blink(3, 200, 100);
  delay(2000);
  ESP.restart();
}

// ─── Inicio del modo Setup ────────────────────────────────────
void startSetupMode() {
  deviceState = STATE_SETUP;
  Serial.println("\n[SETUP] === Modo configuración activo ===");

  // Modo AP — no hacer scan aquí para evitar bloquear el watchdog
  WiFi.mode(WIFI_AP_STA);
  delay(100);   // Pequeña pausa para que el modo se estabilice

  // Crear AP
  String apSSID = String(SETUP_SSID_PREFIX) + "-" + esp32Id.substring(7);
  WiFi.softAPConfig(IPAddress(192,168,4,1), IPAddress(192,168,4,1), IPAddress(255,255,255,0));
  WiFi.softAP(apSSID.c_str(), SETUP_PASS);

  Serial.println("[SETUP] Red WiFi creada: " + apSSID);
  Serial.println("[SETUP] Portal en http://192.168.4.1");

  // DNS para captive portal (redirige todo a 192.168.4.1)
  dnsServer.start(DNS_PORT, "*", IPAddress(192,168,4,1));

  // Rutas del servidor web
  httpServer.on("/",              HTTP_GET,  handleRoot);
  httpServer.on("/scan",          HTTP_GET,  handleScan);
  httpServer.on("/info",          HTTP_GET,  handleInfo);
  httpServer.on("/save",          HTTP_POST, handleSave);

  // Rutas captive portal para iOS, Android, Windows
  httpServer.on("/generate_204",         HTTP_GET, handleRedirect);
  httpServer.on("/hotspot-detect.html",  HTTP_GET, handleRoot);
  httpServer.on("/ncsi.txt",             HTTP_GET, handleRedirect);
  httpServer.on("/connecttest.txt",      HTTP_GET, handleRedirect);
  httpServer.on("/redirect",             HTTP_GET, handleRedirect);
  httpServer.onNotFound(handleRedirect);

  httpServer.begin();
  Serial.println("[SETUP] Servidor HTTP listo");
}

// ═══════════════════════════════════════════════════════════════
//  MODO NORMAL — conexión a WiFi del usuario
// ═══════════════════════════════════════════════════════════════
bool conectarWiFi() {
  deviceState = STATE_CONNECTING;
  Serial.printf("[WiFi] Conectando a '%s'...\n", wifiSSID.c_str());

  WiFi.mode(WIFI_STA);
  WiFi.begin(wifiSSID.c_str(), wifiPass.c_str());

  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < WIFI_TIMEOUT_MS) {
    // Parpadeo lento mientras conecta
    if (millis() - lastLedToggle > 500) {
      lastLedToggle = millis();
      ledState = !ledState;
      digitalWrite(LED_PIN, ledState);
    }
    delay(50);
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[WiFi] Conectado! IP: %s\n", WiFi.localIP().toString().c_str());
    blink(2, 200, 150);
    sincronizarNTP();
    deviceState = STATE_RUNNING;
    return true;
  }

  Serial.println("[WiFi] Error: no se pudo conectar");
  return false;
}

// ═══════════════════════════════════════════════════════════════
//  Verificación del botón de reset (BOOT / GPIO0)
// ═══════════════════════════════════════════════════════════════
void checkResetButton() {
  if (digitalRead(RESET_BTN_PIN) == LOW) {
    if (!resetBtnActive) {
      resetBtnActive   = true;
      resetBtnPressMs  = millis();
      Serial.println("[RESET] Botón pulsado — mantener 5s para resetear...");
    } else if (millis() - resetBtnPressMs >= RESET_HOLD_MS) {
      Serial.println("[RESET] Reset solicitado por el usuario");
      blink(5, 100, 100);
      clearPrefs();
      delay(500);
      ESP.restart();
    }
  } else {
    resetBtnActive = false;
  }
}

// ═══════════════════════════════════════════════════════════════
//  SETUP
// ═══════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  delay(200);

  Serial.println("\n╔═══════════════════════════════════╗");
  Serial.println("║  AgroVision ESP32 — Iniciando...  ║");
  Serial.println("╚═══════════════════════════════════╝");

  // Inicializar pines
  pinMode(LED_PIN,      OUTPUT);
  pinMode(RESET_BTN_PIN, INPUT_PULLUP);
  digitalWrite(LED_PIN, LOW);

  // Generar ID único desde eFuse (no requiere WiFi iniciado)
  esp32Id = buildDeviceId();
  Serial.println("[ID] Device ID: " + esp32Id);

  // Cargar configuración guardada (incluye pines detectados) ANTES
  // de inicializar los sensores, para usar los pines correctos
  loadPrefs();

  // Inicializar sensores en los pines cargados desde NVS
  initDht();
  analogSetPinAttenuation(pinSoil, (adc_attenuation_t)3);  // 11dB/12dB — 0 a 3.3V

  if (wifiSSID.length() == 0) {
    // Sin credenciales → modo configuración
    Serial.println("[BOOT] Sin credenciales WiFi → iniciando modo Setup");
    startSetupMode();
  } else {
    // Con credenciales → conectar
    Serial.println("[BOOT] Credenciales encontradas → conectando a WiFi");
    Serial.println("[BOOT] SSID: " + wifiSSID);
    Serial.println("[BOOT] Server: " + serverURL);

    if (!conectarWiFi()) {
      Serial.println("[BOOT] No se pudo conectar. Entrando a modo Setup...");
      clearPrefs();
      startSetupMode();
    }
  }
}

// ═══════════════════════════════════════════════════════════════
//  AUTO-DETECCIÓN DE PINES — escanea GPIOs candidatos e identifica
//  dónde están conectados el DHT11 y el FC-28
// ═══════════════════════════════════════════════════════════════

// Mide un pin ADC: media y dispersion (max-min) de 16 muestras
void medirAdc(int pin, int &mean, int &spread) {
  analogSetPinAttenuation(pin, (adc_attenuation_t)3);
  long sum = 0; int mn = 4095, mx = 0;
  for (int i = 0; i < 16; i++) {
    int v = analogRead(pin);
    sum += v;
    if (v < mn) mn = v;
    if (v > mx) mx = v;
    delay(4);
  }
  mean   = sum / 16;
  spread = mx - mn;
}

// Prueba el protocolo DHT en un pin. Devuelve true si responde con
// una temperatura valida. Reintenta una vez (el DHT11 muestrea a 1 Hz).
bool probarDht(int pin) {
  DHT probe(pin, DHT_TYPE);
  probe.begin();
  delay(80);
  float t = probe.readTemperature();
  if (isnan(t)) {
    delay(1100);
    t = probe.readTemperature();
  }
  return !isnan(t) && t > -40.0 && t < 80.0;
}

// ═══════════════════════════════════════════════════════════════
//  SERIAL PROVISIONING — comandos JSON vía USB (modo Setup)
// ═══════════════════════════════════════════════════════════════
void handleSerialCommand() {
  if (!Serial.available()) return;

  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;

  JsonDocument req;
  DeserializationError err = deserializeJson(req, line);
  if (err) {
    Serial.println("{\"ok\":false,\"error\":\"JSON invalido\"}");
    return;
  }

  String cmd = req["cmd"].as<String>();

  // ── identify ──────────────────────────────────────────────────
  if (cmd == "identify") {
    JsonDocument resp;
    resp["ok"]        = true;
    resp["device_id"] = esp32Id;
    resp["mode"]      = (deviceState == STATE_SETUP) ? "setup" : "running";
    resp["firmware"]  = "1.2";
    resp["pin_dht"]   = pinDht;
    resp["pin_soil"]  = pinSoil;
    String out;
    serializeJson(resp, out);
    Serial.println(out);
    return;
  }

  // ── scan ──────────────────────────────────────────────────────
  if (cmd == "scan") {
    int n = WiFi.scanNetworks(false, true);
    if (n < 0) n = 0;
    JsonDocument resp;
    resp["ok"] = true;
    JsonArray nets = resp["networks"].to<JsonArray>();
    for (int i = 0; i < n && i < 15; i++) {
      JsonObject net = nets.add<JsonObject>();
      net["ssid"]   = WiFi.SSID(i);
      net["rssi"]   = WiFi.RSSI(i);
      net["secure"] = (WiFi.encryptionType(i) != WIFI_AUTH_OPEN);
    }
    String out;
    serializeJson(resp, out);
    Serial.println(out);
    return;
  }

  // ── config ────────────────────────────────────────────────────
  if (cmd == "config") {
    String newSSID = req["ssid"].as<String>();
    String newPass = req["pass"].as<String>();
    String newSrv  = req["server"].as<String>();

    if (newSSID.length() == 0) {
      Serial.println("{\"ok\":false,\"error\":\"ssid requerido\"}");
      return;
    }

    savePrefs(newSSID, newPass, newSrv);

    JsonDocument resp;
    resp["ok"]        = true;
    resp["device_id"] = esp32Id;
    String out;
    serializeJson(resp, out);
    Serial.println(out);

    Serial.println("[SERIAL] Credenciales guardadas. Reiniciando en 1.5s...");
    delay(1500);
    ESP.restart();
    return;
  }

  // ── calibrate — ajusta offsets y los guarda en NVS ───────────
  if (cmd == "calibrate") {
    float newTempOff = req["temp_offset"] | calTempOffset;
    float newHumOff  = req["hum_offset"]  | calHumOffset;
    int   newDry     = req["soil_dry"]    | calSoilDry;
    int   newWet     = req["soil_wet"]    | calSoilWet;

    if (newDry >= newWet) {
      Serial.println("{\"ok\":false,\"error\":\"soil_dry debe ser menor que soil_wet\"}");
      return;
    }
    saveCalibration(newTempOff, newHumOff, newDry, newWet);

    JsonDocument resp;
    resp["ok"]          = true;
    resp["temp_offset"] = calTempOffset;
    resp["hum_offset"]  = calHumOffset;
    resp["soil_dry"]    = calSoilDry;
    resp["soil_wet"]    = calSoilWet;
    String out;
    serializeJson(resp, out);
    Serial.println(out);
    return;
  }

  // ── read_sensors — lectura inmediata para test de fabrica ────
  if (cmd == "read_sensors") {
    float temp, humAire;
    int   humSuelo;
    bool  ok = leerSensores(temp, humAire, humSuelo);

    JsonDocument resp;
    resp["ok"]           = true;
    resp["device_id"]    = esp32Id;

    if (ok && !isnan(temp) && !isnan(humAire)) {
      resp["temperatura"]   = serialized(String(temp, 1));
      resp["humedad_aire"]  = serialized(String(humAire, 1));
    } else {
      resp["temperatura"]   = (char*)nullptr;   // null → NaN en Python
      resp["humedad_aire"]  = (char*)nullptr;
    }
    resp["humedad_suelo"] = humSuelo;
    resp["pin_dht"]       = pinDht;
    resp["pin_soil"]      = pinSoil;

    String out;
    serializeJson(resp, out);
    Serial.println(out);
    return;
  }

  // ── detect_pins — escanea GPIOs e identifica DHT11 y FC-28 ───
  // Para detectar el FC-28 con seguridad conviene que el sensor
  // este en tierra/agua o tocando las puntas (lectura > 400 ADC).
  // req: {"cmd":"detect_pins","apply":true}
  if (cmd == "detect_pins") {
    bool apply = req["apply"] | true;
    JsonDocument resp;
    resp["ok"] = true;

    // 1) Escaneo analogico pasivo (no perturba los pines)
    JsonArray scan = resp["soil_scan"].to<JsonArray>();
    int bestSoil = -1, bestSoilSpread = 99999;
    int maybeSoil = -1, maybeSoilSpread = 99999;
    int soilMeans[6];
    for (size_t i = 0; i < sizeof(SOIL_CANDIDATES)/sizeof(int); i++) {
      int pin = SOIL_CANDIDATES[i], mean, spread;
      medirAdc(pin, mean, spread);
      soilMeans[i] = mean;
      JsonObject o = scan.add<JsonObject>();
      o["pin"] = pin; o["mean"] = mean; o["spread"] = spread;
      Serial.printf("[DETECT] ADC GPIO%d: mean=%d spread=%d\n", pin, mean, spread);
      // Senal activa y estable → FC-28 en tierra/agua/tocado
      if (mean >= 400 && mean <= 4094 && spread <= 800 && spread < bestSoilSpread) {
        bestSoil = pin; bestSoilSpread = spread;
      }
      // Senal baja pero estable y no nula → posible FC-28 en aire
      if (mean >= 15 && mean < 400 && spread <= 150 && spread < maybeSoilSpread) {
        maybeSoil = pin; maybeSoilSpread = spread;
      }
    }
    int soilFound = (bestSoil >= 0) ? bestSoil : maybeSoil;
    resp["soil_pin"]   = (soilFound >= 0) ? soilFound : -1;
    resp["soil_state"] = (bestSoil >= 0) ? "detected"
                       : (maybeSoil >= 0) ? "maybe_air" : "not_found";

    // 2) Escaneo DHT (protocolo digital). Se omite el pin del FC-28
    //    y cualquier ADC con senal activa para no forzar salidas.
    int dhtFound = -1;
    for (size_t i = 0; i < sizeof(DHT_CANDIDATES)/sizeof(int); i++) {
      int pin = DHT_CANDIDATES[i];
      if (pin == soilFound) continue;
      bool skip = false;
      for (size_t j = 0; j < sizeof(SOIL_CANDIDATES)/sizeof(int); j++)
        if (SOIL_CANDIDATES[j] == pin && soilMeans[j] >= 400) skip = true;
      if (skip) continue;
      Serial.printf("[DETECT] Probando DHT11 en GPIO%d...\n", pin);
      if (probarDht(pin)) { dhtFound = pin; break; }
    }
    resp["dht_pin"]   = (dhtFound >= 0) ? dhtFound : -1;
    resp["dht_state"] = (dhtFound >= 0) ? "detected" : "not_found";

    // 3) Aplicar y persistir lo encontrado
    bool applied = false;
    if (apply && (dhtFound >= 0 || soilFound >= 0)) {
      savePins(dhtFound  >= 0 ? dhtFound  : pinDht,
               soilFound >= 0 ? soilFound : pinSoil);
      applied = true;
    } else {
      initDht();   // re-inicializa el DHT actual tras el sondeo
    }
    resp["applied"]   = applied;
    resp["pin_dht"]   = pinDht;
    resp["pin_soil"]  = pinSoil;

    String out;
    serializeJson(resp, out);
    Serial.println(out);
    return;
  }

  // ── set_pins — fija pines manualmente y los persiste en NVS ──
  // req: {"cmd":"set_pins","dht":15,"soil":34}
  if (cmd == "set_pins") {
    int newDht  = req["dht"]  | pinDht;
    int newSoil = req["soil"] | pinSoil;

    bool dhtOk = false;
    for (size_t i = 0; i < sizeof(DHT_CANDIDATES)/sizeof(int); i++)
      if (DHT_CANDIDATES[i] == newDht) dhtOk = true;
    bool soilOk = false;
    for (size_t i = 0; i < sizeof(SOIL_CANDIDATES)/sizeof(int); i++)
      if (SOIL_CANDIDATES[i] == newSoil) soilOk = true;

    if (!dhtOk || !soilOk) {
      Serial.println("{\"ok\":false,\"error\":\"pin invalido (DHT: GPIO digital valido, SOIL: solo ADC1 32-39)\"}");
      return;
    }
    savePins(newDht, newSoil);

    JsonDocument resp;
    resp["ok"]       = true;
    resp["pin_dht"]  = pinDht;
    resp["pin_soil"] = pinSoil;
    String out;
    serializeJson(resp, out);
    Serial.println(out);
    return;
  }

  // ── comando desconocido ───────────────────────────────────────
  Serial.println("{\"ok\":false,\"error\":\"comando desconocido\"}");
}

// ═══════════════════════════════════════════════════════════════
//  LOOP
// ═══════════════════════════════════════════════════════════════
void loop() {
  // Siempre monitorear botón de reset y comandos serial (USB)
  checkResetButton();
  handleSerialCommand();

  if (deviceState == STATE_SETUP) {
    // ── Modo Setup: atender peticiones HTTP y DNS ──────────────
    dnsServer.processNextRequest();
    httpServer.handleClient();
    ledSetupTick();   // parpadeo rápido del LED
    return;
  }

  // ── Modo Normal ────────────────────────────────────────────────

  // Reconexión automática si se pierde WiFi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Conexión perdida, reconectando...");
    deviceState = STATE_CONNECTING;
    if (!conectarWiFi()) {
      // Si falla, esperar 30s y reintentar
      Serial.println("[WiFi] Reintentando en 30s...");
      delay(30000);
      return;
    }
    reenviarBuffer();   // Reenviar datos guardados offline
  }

  // Envío periódico de datos
  if (millis() - lastSendMs >= SEND_INTERVAL_MS) {
    lastSendMs = millis();

    float temp, humAire;
    int   humSuelo;

    if (!leerSensores(temp, humAire, humSuelo)) {
      Serial.println("[SENSOR] Lectura inválida, omitiendo");
      blink(3, 50, 50);
      return;
    }

    Serial.printf("[DATA] Temp=%.1f°C  HumAire=%.0f%%  HumSuelo=%d%%\n",
                  temp, humAire, humSuelo);

    time_t ts = timestampActual();

    if (!enviarLectura(temp, humAire, humSuelo, ts)) {
      // Guardar en buffer offline
      if (offlineCount < OFFLINE_BUF) {
        offlineBuffer[offlineCount++] = { temp, humAire, humSuelo, ts };
        Serial.printf("[BUFFER] Guardado offline (%d/%d)\n", offlineCount, OFFLINE_BUF);
      } else {
        Serial.println("[BUFFER] Buffer lleno, lectura descartada");
      }
    }
  }
}
