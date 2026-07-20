// Read the SD card via SdFat with SOFTWARE (bit-banged) SPI.
// Hardware SPI can't handle this level-shifter module's slow MISO, but the
// bit-bang probe proved the card responds — so bit-bang the whole bus.
// Requires SdFatConfig.h: SPI_DRIVER_SELECT 2.
//
// Wiring: SCK=11, MISO=12, MOSI=10, CS=13, VCC=3V3, GND=GND.

#include "SdFat.h"

#define CS_PIN   13
#define MISO_PIN 12
#define MOSI_PIN 10
#define SCK_PIN  11

#define LOG(...) do { Serial.printf(__VA_ARGS__); Serial0.printf(__VA_ARGS__); } while (0)

SoftSpiDriver<MISO_PIN, MOSI_PIN, SCK_PIN> softSpi;
#define SD_CONFIG SdSpiConfig(CS_PIN, DEDICATED_SPI, SD_SCK_MHZ(0), &softSpi)

SdFat32 sd;

// Open-in-place idiom: File32 has no copy ctor, so never assign/return by value.
void listDir(File32& dir, int depth) {
  File32 f;
  while (f.openNext(&dir, O_RDONLY)) {
    char name[64];
    f.getName(name, sizeof(name));
    for (int i = 0; i < depth; i++) LOG("  ");
    if (f.isDir()) { LOG("%s/\n", name); if (depth < 1) listDir(f, depth + 1); }
    else           { LOG("%s  (%lu bytes)\n", name, (unsigned long)f.fileSize()); }
    f.close();
  }
}

void setup() {
  Serial.begin(115200);
  Serial0.begin(115200);
  delay(2000);

  LOG("\n=== SD via software SPI (SdFat) ===\n");

  if (!sd.begin(SD_CONFIG)) {
    LOG("SdFat begin FAILED. ");
    if (sd.card()->errorCode()) LOG("card errorCode=0x%02X data=0x%02X\n",
        sd.card()->errorCode(), sd.card()->errorData());
    else LOG("no card error -> likely not FAT32 (SdFat32 needs FAT16/32, not exFAT)\n");
    return;
  }

  uint32_t mb = sd.card()->sectorCount() / 2048;
  LOG("mounted OK. card %lu MB, FAT type %d\n", (unsigned long)mb, sd.vol()->fatType());
  LOG("--- root (2 levels) ---\n");
  File32 root;
  root.open("/", O_RDONLY);
  listDir(root, 0);
  root.close();

  // Non-destructive write test.
  File32 f;
  if (f.open("/atmos_probe.txt", O_WRONLY | O_CREAT | O_APPEND)) {
    f.println("atmos was here"); f.close(); LOG("write OK -> /atmos_probe.txt\n");
  } else {
    LOG("write failed\n");
  }
}

void loop() {}
