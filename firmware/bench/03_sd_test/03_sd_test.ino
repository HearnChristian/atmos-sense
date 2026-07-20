// Step 3 — microSD over SPI. SCK=11, MOSI=10, MISO=12, CS=13.
// Module VCC -> 5V (it has an AMS1117 LDO; 3V3 in makes init flaky).
// Card must be FAT32.
//
// Prints to BOTH the native-USB CDC (Serial) and UART0/bridge (Serial0) so the
// output shows up whichever USB-C jack the cable is in. Build with CDCOnBoot=cdc.

#include <SPI.h>
#include <SD.h>
#include "driver/gpio.h"

#define LOG(...) do { Serial.printf(__VA_ARGS__); Serial0.printf(__VA_ARGS__); } while (0)

// Bit-bang the SPI SD wake-up + CMD0 by hand and report the raw reply byte.
// Isolates MISO/comms faults from filesystem/library faults.
void rawProbe() {
  const int SCK = 11, MISO = 12, MOSI = 10, CS = 13;
  pinMode(CS, OUTPUT); pinMode(SCK, OUTPUT); pinMode(MOSI, OUTPUT); pinMode(MISO, INPUT_PULLUP);
  digitalWrite(CS, HIGH);

  SPI.begin(SCK, MISO, MOSI, CS);
  SPI.beginTransaction(SPISettings(400000, MSBFIRST, SPI_MODE0));

  // 80 clocks with CS high to let the card power up into SPI mode.
  for (int i = 0; i < 10; i++) SPI.transfer(0xFF);

  // CMD0 (GO_IDLE_STATE): 0x40, 4 arg bytes = 0, CRC 0x95.
  digitalWrite(CS, LOW);
  SPI.transfer(0x40); SPI.transfer(0); SPI.transfer(0);
  SPI.transfer(0);    SPI.transfer(0); SPI.transfer(0x95);
  uint8_t r = 0xFF;
  for (int i = 0; i < 8; i++) { r = SPI.transfer(0xFF); if (r != 0xFF) break; }
  digitalWrite(CS, HIGH);
  SPI.transfer(0xFF);
  SPI.endTransaction();

  // Also sample the raw MISO level with CS released, to catch a stuck line.
  pinMode(MISO, INPUT);
  LOG("CMD0 raw reply: 0x%02X   (idle MISO reads %d)\n", r, digitalRead(MISO));
}

void setup() {
  Serial.begin(115200);
  Serial0.begin(115200);
  delay(2000);

  LOG("\n=== SD test ===\n");
  LOG("pins: SCK=11 MISO=12 MOSI=10 CS=13   (VCC on 3V3 for this board)\n");

  SPI.begin(11, 12, 10, 13);  // SCK, MISO, MOSI, SS
  // Enable the internal pull-up on MISO WITHOUT disturbing the SPI pin mux.
  // Helps the level-shifter module's slow MISO settle before the HW SPI samples it.
  gpio_set_pull_mode(GPIO_NUM_12, GPIO_PULLUP_ONLY);

  // Single clean attempt at a slow, spec-friendly clock. No retry loop (re-begin
  // after a fail corrupts SPI state) and no rawProbe (that hangs post-fail).
  const uint32_t hz = 100000;
  if (!SD.begin(13, SPI, hz)) {
    LOG("SD.begin FAILED at %lu Hz (card answers CMD0 but library init won't complete).\n",
        (unsigned long)hz);
    return;
  }
  LOG("mounted at %lu Hz\n", (unsigned long)hz);

  uint8_t type = SD.cardType();
  const char* tname = type == CARD_MMC ? "MMC" :
                      type == CARD_SD  ? "SDSC" :
                      type == CARD_SDHC ? "SDHC" : "UNKNOWN";
  LOG("card type: %s\n", tname);
  LOG("card size: %llu MB\n", SD.cardSize() / (1024ULL * 1024ULL));
  LOG("FS used:   %llu MB of %llu MB\n",
      SD.usedBytes() / (1024ULL * 1024ULL), SD.totalBytes() / (1024ULL * 1024ULL));

  // List root so we can see the radio's OpenTX folders if present.
  LOG("--- root ---\n");
  File root = SD.open("/");
  for (File e = root.openNextFile(); e; e = root.openNextFile()) {
    LOG("  %s%s  %lu\n", e.name(), e.isDirectory() ? "/" : "", (unsigned long)e.size());
  }
  root.close();

  // Non-destructive write test: append one line, don't touch anything else.
  File f = SD.open("/atmos_probe.csv", FILE_APPEND);
  if (f) { f.println("hello,world"); f.close(); LOG("write OK -> /atmos_probe.csv\n"); }
  else   { LOG("write FAILED (card may be read-only/locked)\n"); }
}

void loop() {}
