// Step 1 — ESP32-S3 bring-up. Expect "Flash: 16 MB, PSRAM: 8 MB".
// PSRAM 0 => wrong PSRAM mode; N16R8 needs OPI PSRAM.

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.printf("Flash: %u MB, PSRAM: %u MB\n",
                ESP.getFlashChipSize() >> 20, ESP.getPsramSize() >> 20);
}

void loop() {}
