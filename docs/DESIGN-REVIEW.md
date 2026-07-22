# Atmos full design review — 2026-07-19

Systematic audit of the netlist (`_Atmos_fresh.net`, 2026-07-14 = current
schematic), in order: components → footprints → wiring. Every IC pin and every
passive endpoint was traced. Verdict up front: **the circuit design is
fundamentally sound — textbook power-path, correct buses, thoughtful defaults —
but 3 fab-stopping bugs and a handful of part-choice issues must be fixed
before ordering boards.**

---

## 🔴 CRITICAL — would kill the first spin

### C1. ESP32 IO14 / IO15 / IO16 are NOT connected to the module
Nets named `IO14`, `IO15`, `IO16` contain only the peripheral + its resistor;
the ESP32 module pads (pin 22 = IO14, pin 8 = IO15, pin 9 = IO16) are
no-connects in the schematic:

| Net | What's on it | Consequence as-drawn |
|---|---|---|
| `IO16` | U9 TPS61023 **EN** + R13 100k pulldown | Boost **permanently disabled → +5V never comes up → PMS5003 dead** |
| `IO15` | U10 TPS22918 **ON** + R16 100k pulldown | PMS power switch uncontrollable |
| `IO14` | U11 MAX17048 **~ALERT** + R17 100k pullup | Alert IRQ unreadable (I²C polling still works) |

Classic KiCad label-not-attached error — IO5/6/7 immediately adjacent are done
correctly. **Fix: attach labels `IO14`/`IO15`/`IO16` to U1 pins 22/8/9.**

### C2. D1 power LED is reversed (and always-on)
Chain as drawn: +3V3 → R8 1k → D1 **cathode**; D1 **anode** → GND. The LED is
reverse-biased and will never light. Fix polarity. Also reconsider the design:
an always-on power LED burns ~1 mA 24/7 on a solar node — move it to a GPIO or
mark DNP for deployment.

### C3. PMS5003 connector pin order is mirrored vs the Plantower datasheet — VERIFY
The symbol wires pin 4=TX, 6=SET, 7=GND, **8=VCC**. Plantower's datasheet
numbers the sensor connector **1=VCC**, 2=GND, 3=SET, 4=RXD, **5=TXD**,
6=RESET, 7/8=NC — the exact mirror. Whether this is a bug depends on the
harness: a straight 1:1 PicoBlade cable would put VCC on a sensor NC pin
(sensor unpowered, no damage); some common PMS5003 pigtails are reversed,
which would make the current symbol correct.
**Action: when the PMS5003 + pigtail arrive, beep out sensor VCC (their pin 1)
to the board pad before first power, and renumber the symbol if needed. Do not
fab before this is resolved.**

---

## 🟠 HIGH — fix before fab

- **H1. L2 (boost inductor) is an RF part.** Coilcraft 1008HQ is an air-core
  RF series (sub-amp rating); TPS61023 has a 3.7 A switch and pulls >1 A from
  the battery at 5 V/600 mA. Replace with a 1 µH power inductor, Isat ≥ 2.5 A
  (e.g. Coilcraft XFL4020-102, Murata DFE322512). Value (1 µH) is correct;
  the part class/footprint is not.
- **H2. MPPT floor blocks USB charging.** Divider R10 33k / R12 10k sets the
  CN3791 input floor at 1.205 × 43/10 = **5.18 V**. USB via Q2 presents ~5.0 V
  — below the floor — so the charger throttles to ~zero: **USB charging won't
  work**. Options: (a) retune (R12 → 12k gives 4.52 V: USB charges fully;
  solar regulated ≥4.52 V — further below a 6 V panel's MPP, harvest tradeoff),
  (b) keep 5.18 V and accept solar-only charging (then Q2/R3 are dead weight),
  (c) separate USB charge path. Decide intent; (a) is the pragmatic pick.
- **H3. U13 SGP40 land is a placeholder** (DFN-6 2×2; real part is 2.44×2.44 mm).
  Known deviation; also the cause of the board's 1 remaining unrouted GND.
- **H4. U12 CN3791 footprint lacks the exposed pad** the real MSOP-10 has.
  Add EP + thermal vias (known deviation).
- **H5. J4 microSD is the Hirose DM3AT stand-in**, not the ratified GCT
  MEM2075 (not pad-compatible — known deviation).

## 🟡 MEDIUM

- **M1. No pullups on SD_CS or RFM95W NSS.** Both float at boot (ESP32 pads
  are high-Z until firmware runs) → possible MISO contention between SD and
  radio during init. Add 10 k to +3V3 on each.
- **M2. +5V_PMS has zero local capacitance.** The PMS5003 fan draws inrush
  bursts through a cable. Add 10–22 µF at U4. (TPS22918 CT = C16 1 nF soft-start
  helps, but is on the fast side — consider 10 nF too.)
- **M3. C15 (boost output) is a single 22 µF 0805** — X5R derates ~50 % at 5 V,
  leaving ~10 µF where the TPS61023 datasheet wants ≥20 µF effective. Use two.
- **M4. D6 solar clamp is marginal.** "8 V" zener in SOD-123: a "6 V" panel's
  cold Voc reaches 7.4–7.8 V (zener leakage knee), and SOD-123 can't sustain
  real clamp current. Consider an SMA-package TVS (e.g. SMAJ6.5A) sized to the
  actual panel, or verify panel Voc < 7 V.
- **M5. No UART header/testpoints on TXD0/RXD0.** Native-USB-only debug — and
  the bench already proved native USB CDC drops during deep sleep. A 3-pin
  TX/RX/GND header (or testpoints) will save real pain in sleep-cycle debug.
- **M6. AS3935 header assumes I²C mode** with SI/CS/EN floating. Preferred
  module is **Playing With Fusion SEN-39003** (I²C via Qwiic or header; load
  the printed antenna cal pF in firmware). SparkFun SEN-15441 is SPI-first.
  Verify pin map vs J1 when wiring — not a 1:1 pin-order assumption.
- **M7. AP2112K dropout note:** with VBATT < ~3.55 V under combined load
  (ESP32 + RFM TX + SD write ≈ 300 mA+), the 3V3 rail sags below 3.3 V.
  Parts all run to 3.0 V so it degrades gracefully — accepted tradeoff; a
  buck-boost is the upgrade path if brownouts appear.
- **M8. C12 (CN3791 VG cap) is 100 nF; datasheet typical is 1 µF** — verify
  and bump if needed. Also keep compensation network C8/R11 and CT cap C16
  physically tight to their ICs at layout.

## 🟢 LOW / BOM hygiene

- Q1/Q2/Q3 are generic "PMOS_Substrate" — pick a real MPN (e.g. AO3401A /
  DMG3415U; need Vgs ≥ ±8 V for the solar node). Symbol pin 4 "Bulk" has no
  pad on SOT-23 (harmless).
- D4 Schottky needs an MPN (SS34/B340A fine); F1 polyfuse needs a value
  (~750 mA hold suits a 2–3 W panel); F2 "3A" needs an MPN; SW1 value is empty;
  D5 designator skipped (cosmetic).
- MAX17048 CTG pin left NC — datasheet says connect to ground.
- CN3791 ~CHRG/~DONE status outputs tied to GND — harmless (open-drain) but
  wasted; could go to GPIOs or LEDs on a respin.
- No cap on VBUS (1–4.7 µF customary), only 100 nF on VSOL, none on DS3231
  VBAT (0.1 µF customary).
- D2/D3 are SOD-882 (1×0.6 mm, tough hand-soldering) — SOD-323 equivalents
  exist if hand-assembling.
- DS3231 ~INT/SQW unused — wiring it to an RTC-wake-capable pin would allow
  drift-free scheduled wakes (enhancement, current RTC-timer plan works).
- No test points on rails (+VBATT/+5V/+3V3) — nice-to-have for bring-up.
- R14 sits at the board edge (layout, from PCB notes) — move next to U9.

---

## ✅ Verified correct (checked pin-by-pin, don't re-audit)

- **Power path (LTC4412 dual-source) is textbook**: solar → Q1 ideal diode
  (D=VSOL/S=VIN_CHG orientation correct), USB → Q2 driven by STAT with R3 1M
  pull to VIN_CHG — USB auto-priority, correct FET polarity everywhere,
  no back-feed paths. Fuse-then-clamp order on solar input correct; battery
  fused (F2) at BT2.
- **CN3791 buck**: VCC=VIN_CHG (C7 10 µF input cap present ✓), DRV→Q3 gate,
  Q3 S/D orientation ✓, SW→L1 22 µH (Bourns SRN6045 ✓ proper power part)
  →CSP→R9 0.24 Ω (0.5 A charge ✓)→BAT; D4 freewheel K→SW/A→GND ✓; VG cap to
  VCC ✓; COM compensation C8 220 nF + R11 120 Ω to GND ✓; MPPT divider wired
  as a divider ✓ (setpoint value is the H2 issue, not the wiring).
- **TPS61023 boost**: L2 topology ✓ (VBATT→L2→SW), FB divider 750k/100k →
  5.1 V ✓, EN pulldown default-off ✓ (once C1 is fixed).
- **TPS22918**: QOD strapped to VOUT ✓, CT cap ✓, ON pulldown ✓.
- **MAX17048**: CELL=VDD=+VBATT ✓, QSTRT grounded ✓, EP grounded ✓, ALERT
  pullup ✓ (needs C1 fix to reach the MCU).
- **DS3231M**: SO-16 pinout correct incl. NC pins 5–12 grounded per datasheet,
  VBAT→CR2032, SDA/SCL correct pins.
- **I²C bus complete**: all five devices (RTC, fuel gauge, SGP40, AS3935 hdr,
  BME280 hdr) + R4/R5 4.7k pullups to +3V3 — matches bench firmware (SDA=IO8,
  SCL=IO9).
- **SPI map matches bench firmware exactly**: SCK=IO11, MOSI=IO10, MISO=IO12,
  SD_CS=IO13; RFM95W shares the bus with NSS=IO5, RESET=IO7, DIO0=IO6 (DIO0
  is the right IRQ for RadioHead; DIO1 only needed if LoRaWAN/LMIC later).
- **microSD in proper SPI mode**: DAT3/CD→CS, CMD→MOSI, DAT0→MISO, 3V3 supply,
  shield grounded, DAT1/2 NC ✓.
- **USB**: D+/D− on the S3's native USB pins via USBLC6 (pass-through pairing
  1/6 + 3/4 correct), both C-orientation pairs tied, CC1/CC2 5.1k pulldowns ✓,
  VBUS ESD ✓.
- **ESP32 strapping/PSRAM safe**: IO35–37 NC (required for octal PSRAM ✓),
  IO45/46 NC (safe defaults), IO0 button (internal pullup ok), EN with
  R2 10k + C6 1 µF + reset button ✓.
- **PMS5003 signal path**: TX→D2 ESD→IO18, SET→D3 ESD→IO17 — PicoBlade lines
  ESD-protected ✓ (pin numbering is the C3 verify).
- **SGP40**: VDD RC-filtered (R18 100 Ω + C21) ✓, VDDH direct 3V3 ✓, EP GND ✓.
- +3V3 rail: 7 distributed decoupling caps; load budget ~315 mA typ-peak vs
  AP2112K 600 mA ✓.

## Suggested fix order (schematic session)

1. Attach IO14/IO15/IO16 labels to U1 (C1) — 2 min, unblocks +5V/PMS.
2. Flip D1; decide GPIO-LED vs DNP (C2).
3. Retune MPPT divider R12 10k→12k (H2 option a) — or record decision.
4. Swap L2 to XFL4020-102ME + footprint (H1).
5. BOM hygiene pass: Q1-3/D4/D6/F1/F2 MPNs, SW1 value (LOW batch).
6. Rebuild U13 SGP40 + U12 EP + J4 MEM2075 lands (H3-H5, already docketed).
7. Add: SD_CS/NSS pullups, +5V_PMS bulk cap, 2nd 22 µF on +5V, UART testpoints
   (M1-M3, M5).
8. On arrival of parts: PMS pigtail beep-out (C3), AS3935 breakout jumpers (M6).

*Then re-export netlist, re-run board updates, and re-route the deltas.*
