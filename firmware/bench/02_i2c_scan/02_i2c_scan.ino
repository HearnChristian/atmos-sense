// Step 2 — I2C scan on SDA=IO8, SCL=IO9.
// Expect 0x76 (BME280) and 0x68 (DS3231).
// 0x57 is the AT24C32 EEPROM some DS3231 modules carry — harmless.

#include <Wire.h>

void setup() {
  Serial.begin(115200);
  Wire.begin(8, 9);
  delay(2000);

  uint8_t found = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.printf("0x%02X\n", a);
      found++;
    }
  }
  Serial.printf("%u device(s)\n", found);
}

void loop() {}
