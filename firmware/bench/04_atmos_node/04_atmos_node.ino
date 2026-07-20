// Step 4 (bench) — the Atmos node duty cycle: wake -> sense -> timestamp -> log -> deep sleep.
// Logs to SERIAL here (this DevKit's 5V rail is dead so no SD); the real deployment
// swaps the LOG line for an SD append and SLEEP_SEC for minutes. Everything else is real.
//
// I2C sensors: BME280 + DS3231 on VCC->3V3, GND, SDA->GPIO8, SCL->GPIO9.

#include <Wire.h>
#include <Adafruit_BME280.h>
#include <RTClib.h>

#define SLEEP_SEC 15                 // bench value; real node = 5*60 etc.
RTC_DATA_ATTR uint32_t bootCount = 0; // survives deep sleep, lost on full reset/power-cycle

Adafruit_BME280 bme;
RTC_DS3231 rtc;

#define LOG(...) do { Serial.printf(__VA_ARGS__); Serial0.printf(__VA_ARGS__); } while (0)

void setup() {
  Serial.begin(115200);
  Serial0.begin(115200);
  delay(300);                        // let UART settle after wake before printing
  bootCount++;

  Wire.begin(8, 9);
  bool haveBme = bme.begin(0x76);
  bool haveRtc = rtc.begin();
  if (haveRtc && rtc.lostPower()) rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));

  DateTime t = haveRtc ? rtc.now() : DateTime((uint32_t)0);
  char row[128];
  snprintf(row, sizeof(row), "%lu,%04d-%02d-%02dT%02d:%02d:%02d,%.2f,%.2f,%.2f",
           bootCount, t.year(), t.month(), t.day(), t.hour(), t.minute(), t.second(),
           haveBme ? bme.readTemperature() : NAN,
           haveBme ? bme.readHumidity() : NAN,
           haveBme ? bme.readPressure() / 100.0f : NAN);

  LOG("wake #%lu | %s%s%s\n", bootCount, row,
      haveBme ? "" : "  [BME280 not found]",
      haveRtc ? "" : "  [DS3231 not found]");
  LOG("  -> deep sleep %d s\n", SLEEP_SEC);

  Serial.flush();
  Serial0.flush();
  esp_sleep_enable_timer_wakeup((uint64_t)SLEEP_SEC * 1000000ULL);
  esp_deep_sleep_start();
}

void loop() {}
