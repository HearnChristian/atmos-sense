/*
 * Atmospheric Sensing Node v1
 * Christian Hearn / Ridgemesh
 *
 * Hardware:
 *   ESP32 DevKit V1 (CP2102 variant)
 *   BME280 on I2C   (SDA=21, SCL=22, address 0x76 or 0x77)
 *   AS3935 on I2C   (shared bus, INT line on GPIO 4)
 *   microSD on SPI  (SCK=18, MISO=19, MOSI=23, CS=5)
 *
 * Build modes (toggle with the WOKWI_SIMULATION define below):
 *   Defined   -> Wokwi simulation. All sensors mocked in software.
 *                Serial output only; SD writes skipped. No external
 *                Wokwi Custom Chips required.
 *   Undefined -> Real hardware. Adafruit_BME280, SparkFun_AS3935,
 *                and SD libraries activate.
 *
 * Libraries required for hardware build:
 *   Adafruit BME280 Library
 *   Adafruit Unified Sensor
 *   SparkFun AS3935 Lightning Detector Arduino Library
 *   SD (built-in for ESP32 core)
 */

#define WOKWI_SIMULATION   // <-- comment out for real hardware build

#include <Wire.h>
#include <WiFi.h>
#include <time.h>

#ifndef WOKWI_SIMULATION
  #include <SPI.h>
  #include <SD.h>
  #include <Adafruit_Sensor.h>
  #include <Adafruit_BME280.h>
  #include "SparkFun_AS3935.h"
#endif

// ─── Pins ─────────────────────────────────────────────────
#define I2C_SDA       21
#define I2C_SCL       22
#define SD_CS          5
#define AS3935_INT     4
#define AS3935_ADDR 0x03   // SparkFun breakout default

// ─── Configuration ────────────────────────────────────────
const unsigned long LOG_INTERVAL_MS = 10000;  // 10 s

// In Wokwi, "Wokwi-GUEST" works with empty password.
// For real hardware, replace with your own SSID/password.
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASS = "";

// ─── Data structures ──────────────────────────────────────
struct AtmosReading {
  float temp_c;
  float rh_pct;
  float pressure_hpa;
  float alt_m;
};

struct LightningEvent {
  bool     occurred;
  uint8_t  event_type;   // 0=none, 1=lightning, 2=disturber, 3=noise
  uint8_t  distance_km;
  uint32_t energy;
};

// ─── Globals ──────────────────────────────────────────────
#ifndef WOKWI_SIMULATION
Adafruit_BME280   bme;
SparkFun_AS3935   lightning;
#endif

unsigned long lastLog = 0;
volatile bool lightning_interrupt_flag = false;

#ifdef WOKWI_SIMULATION
unsigned long sim_start_ms = 0;
unsigned long next_fake_strike_ms = 0;
float sim_pressure_state = 850.0;   // SLC baseline (~4200 ft)
#endif

// ─── Forward declarations ─────────────────────────────────
String        timestamp();
void          try_sync_time();
bool          sensors_init();
AtmosReading  read_atmosphere();
LightningEvent check_lightning();
void          log_csv_row(const AtmosReading&, const LightningEvent&);

#ifndef WOKWI_SIMULATION
void IRAM_ATTR on_lightning_interrupt();
#endif

// ─── Time handling ────────────────────────────────────────
String timestamp() {
  time_t now = time(nullptr);
  if (now < 1700000000) {                // NTP not yet synced
    char buf[24];
    sprintf(buf, "ms=%lu", millis());
    return String(buf);
  }
  struct tm tm_info;
  gmtime_r(&now, &tm_info);
  char buf[32];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tm_info);
  return String(buf);
}

void try_sync_time() {
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 8000) {
    delay(200);
  }
  if (WiFi.status() == WL_CONNECTED) {
    configTime(0, 0, "pool.ntp.org");
    Serial.println("# WiFi connected, NTP syncing");
  } else {
    Serial.println("# No WiFi; falling back to millis() timestamps");
  }
}

// ─── Sensor init ──────────────────────────────────────────
bool sensors_init() {
#ifdef WOKWI_SIMULATION
  Serial.println("# SIM MODE: synthetic sensors active");
  sim_start_ms = millis();
  next_fake_strike_ms = millis() + 30000 + random(0, 30000);
  return true;
#else
  Wire.begin(I2C_SDA, I2C_SCL);

  if (!bme.begin(0x76) && !bme.begin(0x77)) {
    Serial.println("# ERROR: BME280 not found at 0x76 or 0x77");
    return false;
  }
  Serial.println("# BME280 OK");

  if (!lightning.begin(Wire, AS3935_ADDR)) {
    Serial.println("# ERROR: AS3935 not found at I2C 0x03");
    return false;
  }
  lightning.setIndoorOutdoor(INDOOR);     // change to OUTDOOR for deployment
  lightning.setNoiseLevel(2);             // 1-7, raise if noisy environment
  lightning.watchdogThreshold(2);
  lightning.spikeRejection(2);
  lightning.lightningThreshold(1);        // strikes-before-issue: 1, 5, 9, or 16
  pinMode(AS3935_INT, INPUT);
  attachInterrupt(digitalPinToInterrupt(AS3935_INT),
                  on_lightning_interrupt, RISING);
  Serial.println("# AS3935 OK");

  if (!SD.begin(SD_CS)) {
    Serial.println("# WARN: SD init failed; logging to Serial only");
  } else {
    File f = SD.open("/atmos.csv", FILE_APPEND);
    if (f && f.size() == 0) {
      f.println("timestamp_utc,temp_c,rh_pct,pressure_hpa,alt_m,"
                "event_type,distance_km,energy");
    }
    if (f) f.close();
    Serial.println("# SD OK");
  }
  return true;
#endif
}

// ─── Atmospheric read ─────────────────────────────────────
AtmosReading read_atmosphere() {
  AtmosReading r;

#ifdef WOKWI_SIMULATION
  // Accelerated diurnal cycle: 1 real minute = 1 simulated hour.
  // Lets you see a full day's worth of data in 24 minutes.
  float elapsed_hours = (millis() - sim_start_ms) / 60000.0;
  float phase = fmod(elapsed_hours, 24.0) / 24.0 * 2.0 * PI;

  // Temperature: baseline 18C, +-8C, peak around "noon" (phase = pi/2).
  r.temp_c = 18.0 + 8.0 * sin(phase - PI/2);

  // Relative humidity: inversely correlated with temperature plus noise.
  r.rh_pct = 50.0 - 15.0 * sin(phase - PI/2) + (random(-200, 201) / 100.0);
  if (r.rh_pct < 5)   r.rh_pct = 5;
  if (r.rh_pct > 95)  r.rh_pct = 95;

  // Pressure: slow random walk around 850 hPa (SLC ~4200 ft elevation).
  sim_pressure_state += (random(-50, 51) / 100.0);
  if (sim_pressure_state < 840) sim_pressure_state = 840;
  if (sim_pressure_state > 860) sim_pressure_state = 860;
  r.pressure_hpa = sim_pressure_state;

  // Altitude from barometric formula, reference 1013.25 hPa.
  r.alt_m = 44330.0 * (1.0 - pow(r.pressure_hpa / 1013.25, 0.1903));
#else
  r.temp_c       = bme.readTemperature();
  r.rh_pct       = bme.readHumidity();
  r.pressure_hpa = bme.readPressure() / 100.0;
  r.alt_m        = bme.readAltitude(1013.25);
#endif

  return r;
}

// ─── Lightning event check ────────────────────────────────
#ifndef WOKWI_SIMULATION
void IRAM_ATTR on_lightning_interrupt() {
  lightning_interrupt_flag = true;
}
#endif

LightningEvent check_lightning() {
  LightningEvent e = {false, 0, 0, 0};

#ifdef WOKWI_SIMULATION
  if (millis() >= next_fake_strike_ms) {
    e.occurred = true;
    uint8_t roll = random(0, 100);
    if (roll < 60) {                       // 60% lightning
      e.event_type  = 1;
      e.distance_km = random(1, 40);
      e.energy      = random(100000, 2000000);
    } else if (roll < 90) {                // 30% disturber
      e.event_type = 2;
    } else {                               // 10% noise floor
      e.event_type = 3;
    }
    next_fake_strike_ms = millis() + 30000 + random(0, 60000);
  }
#else
  if (lightning_interrupt_flag) {
    lightning_interrupt_flag = false;
    delay(2);                              // datasheet settle time
    uint8_t source = lightning.readInterruptReg();
    e.occurred = true;
    if (source == 0x08) {                  // lightning
      e.event_type  = 1;
      e.distance_km = lightning.distanceToStorm();
      e.energy      = lightning.lightningEnergy();
    } else if (source == 0x04) {           // disturber
      e.event_type = 2;
    } else if (source == 0x01) {           // noise too high
      e.event_type = 3;
    }
  }
#endif

  return e;
}

// ─── Logging ──────────────────────────────────────────────
void log_csv_row(const AtmosReading& a, const LightningEvent& e) {
  String line = timestamp()                + "," +
                String(a.temp_c, 2)        + "," +
                String(a.rh_pct, 2)        + "," +
                String(a.pressure_hpa, 2)  + "," +
                String(a.alt_m, 2)         + "," +
                String(e.event_type)       + "," +
                String(e.distance_km)      + "," +
                String(e.energy);
  Serial.println(line);

#ifndef WOKWI_SIMULATION
  File f = SD.open("/atmos.csv", FILE_APPEND);
  if (f) {
    f.println(line);
    f.close();
  }
#endif
}

// ─── Setup / loop ─────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);
  randomSeed(analogRead(0));

  Serial.println("# Atmospheric Sensing Node v1");
#ifdef WOKWI_SIMULATION
  Serial.println("# Build: WOKWI SIMULATION");
#else
  Serial.println("# Build: HARDWARE");
#endif
  Serial.println("timestamp,temp_c,rh_pct,pressure_hpa,alt_m,"
                 "event_type,distance_km,energy");

  try_sync_time();

  if (!sensors_init()) {
    Serial.println("# FATAL: sensor init failed; halting");
    while (1) delay(1000);
  }
}

void loop() {
  // Event-driven lightning check, every iteration
  LightningEvent e = check_lightning();
  if (e.occurred) {
    AtmosReading a = read_atmosphere();
    log_csv_row(a, e);
  }

  // Periodic atmospheric reading
  if (millis() - lastLog >= LOG_INTERVAL_MS) {
    lastLog = millis();
    AtmosReading a = read_atmosphere();
    LightningEvent no_event = {false, 0, 0, 0};
    log_csv_row(a, no_event);
  }

  delay(10);
}
