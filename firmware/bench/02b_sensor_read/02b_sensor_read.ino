// Step 2b — functional read of BME280 + DS3231 (no SD needed).
// Proves the sensors return real data and the RTC actually ticks,
// beyond the address scan. Prints once a second.

#include <Wire.h>
#include <Adafruit_BME280.h>
#include <RTClib.h>

Adafruit_BME280 bme;
RTC_DS3231 rtc;

void setup() {
  Serial.begin(115200);
  Wire.begin(8, 9);
  delay(1500);

  if (!bme.begin(0x76)) Serial.println("BME280 not found at 0x76");
  if (!rtc.begin())     Serial.println("DS3231 not found at 0x68");

  if (rtc.lostPower()) {
    Serial.println("RTC lost power -> seeding from build time");
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }
}

void loop() {
  DateTime t = rtc.now();
  Serial.printf("%04d-%02d-%02dT%02d:%02d:%02d  |  %.2f C  %.1f %%RH  %.1f hPa\n",
                t.year(), t.month(), t.day(), t.hour(), t.minute(), t.second(),
                bme.readTemperature(), bme.readHumidity(), bme.readPressure() / 100.0f);
  delay(1000);
}
