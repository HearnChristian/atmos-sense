# Bench bring-up firmware

ESP32-S3 sketches used to validate sense→timestamp→log→sleep on real parts
(ESP32-S3-DevKitC-1 N16R8, BME280, DS3231, microSD module) before trusting
the PCB. Steps 1–4 complete as of 2026-07-19. This is a separate, earlier
draft from `../v1/sketch.ino` (a Wokwi-simulation-only sketch with a
different pinout) — these are the ones actually run on hardware.

Run with `./atmos-flash.sh <sketch-name>` (needs `arduino-cli` + the esp32
core + Adafruit BME280/BusIO/Unified Sensor + RTClib installed).

**FQBN (load-bearing):**
```
esp32:esp32:esp32s3:CDCOnBoot=default,FlashSize=16M,PSRAM=opi
```
Board defaults (4MB flash / PSRAM off) read PSRAM back as 0 on this N16R8
module. `CDCOnBoot=default` routes `Serial` to UART0, which is the port
this board's USB bridge (WCH `1a86:55d3`, enumerates as `/dev/ttyACM0`)
actually carries — `CDCOnBoot=cdc` sends output to the native-USB port
instead, which has no cable in it, so sketch output silently vanishes.

**Wiring:** I2C SDA=IO8 SCL=IO9. SPI SCK=IO11 MOSI=IO10 MISO=IO12 CS=IO13.
microSD module VCC → **3V3** on this board (the 5V/VBUS pin doesn't deliver
through the WCH bridge USB jack).

## Sketches, in bring-up order

| Sketch | Validates |
|---|---|
| `01_bringup` | Flash/PSRAM sanity (`arduino-cli` + FQBN correct) |
| `02_i2c_scan` | I2C bus, expect 0x76 (BME280) + 0x68 (DS3231) |
| `02b_sensor_read` | Functional sensor reads, not just address ACK |
| `03_sd_test` | microSD hardware-SPI mount — **fails on this bench**; card + wiring proven good by `03b_sd_probe`, but a cheap level-shifter module's MISO can't settle fast enough for ESP32 hardware SPI. Untried fix: external 10kΩ pull-up on MISO (GPIO12)→3V3. |
| `03b_sd_probe` | Pure bit-bang CMD0 probe, no SPI peripheral/library — isolates card/wiring faults from library faults |
| `04_sd_softspi` | SD via SdFat software SPI, as a fallback around the hardware-SPI issue |
| `04_atmos_node` | Full integrated node: wake → sense → timestamp → log → deep sleep. Validated over 4 cycles; `RTC_DATA_ATTR` boot counter survives deep sleep, confirming real deep-sleep wakes. Logs to Serial here (bench 5V rail is dead); real deployment swaps the log line for an SD append. |

Real Atmos PCB uses a proper microSD socket, so the SD flakiness above is a
breadboard-module problem, not a design flaw.
