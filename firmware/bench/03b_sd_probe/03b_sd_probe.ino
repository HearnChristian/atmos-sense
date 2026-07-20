// Standalone SD SPI probe — pure GPIO bit-bang, no SPI peripheral, no SD library.
// Cannot hang or conflict with library state. Sends CMD0 by hand, reports the reply.
//
// Wiring (same as the SD module): SCK=11, MISO=12, MOSI=10, CS=13, VCC=5V, GND=GND.

#define SCK 11
#define MISO 12
#define MOSI 10
#define CS 13

#define LOG(...) do { Serial.printf(__VA_ARGS__); Serial0.printf(__VA_ARGS__); } while (0)

// One SPI-mode-0 byte, MSB first, bit-banged. Fixed loop counts — no blocking waits.
uint8_t xfer(uint8_t out) {
  uint8_t in = 0;
  for (int i = 7; i >= 0; i--) {
    digitalWrite(MOSI, (out >> i) & 1);
    digitalWrite(SCK, HIGH);
    delayMicroseconds(3);
    in = (in << 1) | (digitalRead(MISO) & 1);
    digitalWrite(SCK, LOW);
    delayMicroseconds(3);
  }
  return in;
}

void setup() {
  Serial.begin(115200);
  Serial0.begin(115200);
  delay(2000);

  pinMode(SCK, OUTPUT);
  pinMode(MOSI, OUTPUT);
  pinMode(CS, OUTPUT);
  pinMode(MISO, INPUT_PULLUP);
  digitalWrite(SCK, LOW);
  digitalWrite(MOSI, HIGH);
  digitalWrite(CS, HIGH);

  LOG("\n=== SD raw probe (bit-bang) ===\n");
  LOG("idle MISO (CS high, pull-up on): %d  <- expect 1 if card drives/releases the line\n",
      digitalRead(MISO));

  // 80+ clocks with CS high and MOSI high to bring the card into SPI mode.
  for (int i = 0; i < 12; i++) xfer(0xFF);

  // CMD0 (GO_IDLE_STATE): 0x40 | 0, arg=0, CRC=0x95.
  digitalWrite(CS, LOW);
  xfer(0x40); xfer(0x00); xfer(0x00); xfer(0x00); xfer(0x00); xfer(0x95);
  uint8_t r = 0xFF;
  for (int i = 0; i < 10; i++) { r = xfer(0xFF); if (r != 0xFF) break; }
  digitalWrite(CS, HIGH);
  xfer(0xFF);

  LOG("CMD0 reply: 0x%02X\n", r);
  LOG("  0x01 = card responded, SPI wiring is GOOD (fault is library/format)\n");
  LOG("  0xFF = no response: MISO never pulled low -> card not seated / not powered (VCC) / MISO not connected\n");
  LOG("  0x00 = MISO stuck LOW -> wired to GND, or MISO/MOSI swapped\n");

  // Sanity: drive MOSI low/high and confirm the pin toggles (proves our outputs move).
  LOG("(MOSI drive test: set LOW then HIGH — for scope/DMM if needed)\n");
}

void loop() {}
