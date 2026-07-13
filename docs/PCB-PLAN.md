# Atmos PCB — Pre-Layout Plan (proposal, needs ratification)

Schematic is complete (73 parts / 94 nets). Before board generation these
decisions need sign-off, mirroring the radar project's flow.

## 1. Stackup — recommendation: 4-layer

| | 2-layer | 4-layer (recommended) |
|---|---|---|
| Cost (JLC, 65×50) | ~$5 | ~$15 |
| RF ground for WROOM + RFM95W | compromised, careful pours | solid L2 GND under both radios |
| Switcher loops (TPS61023 boost, CN3791 MPPT) | workable, big loops | tight return paths |
| Routing effort | high (this board has 3 power domains) | moderate |

Two radios + two switchers on one small board is exactly the case where
the $10 delta buys real margin. Proposed: **SIG / GND / 3V3+VBAT pours / SIG**,
standard 1.6 mm FR4 — no exotic materials (915 MHz and WiFi antennas are
both on modules, not board-printed).

## 2. Floorplan (board ≈ 65 × 50 mm, all SMD top side)

```
+--------------------------------------------------------------+
| [WROOM-1 antenna ->EDGE KEEPOUT]              [RFM95W]  (J6) |
|  U1 ESP32-S3                                   LoRa    u.FL/ |
|                                                         SMA  |
|  J3 USB-C   U8 ESD                     U13 SGP40 (slots?)    |
|  J4 microSD                            J1/J2 hdrs (AS3935,   |
|  SW1/SW2                                        BME280 ext)  |
|                                                              |
|  U2 LDO  U10 loadsw  U9 boost5V   U4/PMS5003 connector       |
|  U12 MPPT  U5 pwr-path  U11 gauge  J5 solar  BT1/BT2 batt    |
+--------------------------------------------------------------+
```

- WROOM antenna section overhangs or gets a full keepout (no copper all
  layers) at the top-left edge per Espressif UG; RFM95W antenna feed to
  J6 at the opposite corner for radio-radio isolation.
- USB-C + microSD + buttons on the left/user edge.
- Power cluster (solar in, MPPT, battery, power path, gauge, boost) along
  the bottom edge; MPPT inductor loop kept off the radio half.
- SGP40 (VOC) placed away from the boost converter and LDO with slot
  isolation to be decided (self-heating parts skew VOC/temperature).
- BME280 and AS3935 are on external breakouts (J2/J1 headers) — the
  lightning sensor especially wants distance from the switchers.

## 3. Blocker: 60 unassigned footprints

- 41 passives → default 0603 (0805 for bulk caps), same as radar flow.
- Semis with known packages (D4 Schottky, Q1-3 PMOS, D1 LED, D6 zener,
  F1/F2 fuses) → straightforward picks, I'll propose in the pass.
- **Connector decisions (need your input):**
  - J3 USB-C: HRO TYPE-C-31-M-12 (the cheap 16-pin, KiCad stock fp)?
  - J4 microSD: push-push (e.g. GCT MEM2075) or hinged?
  - BT1/BT2 battery: JST-PH 2-pin right-angle?
  - J5 solar input: JST-PH or barrel jack?
  - PMS5003: its mating 1.25 mm 8-pin (PicoBlade-style) header?
  - J6 LoRa antenna: u.FL (compact) or SMA edge (robust)?
  - J1/J2 breakout headers: 2.54 mm sockets?
- U7 RFM95W and SW1 also lack footprints (RFM95W = 16×16 castellated,
  I can build it; SW1 needs a part pick).

## 4. Open questions before board-gen

1. Ratify 4-layer, ~65×50 mm, and the floorplan above?
2. Enclosure/mounting: hole pattern, corner radii, max height constraints?
   (Outdoor/solar suggests an IP-rated box — which one?)
3. Connector picks from §3.
4. PMS5003 mounted off-board via cable (assumed) or board-carried?

Once ratified, the radar toolchain (board_gen / route_pcb / route_signals /
route_finish) gets pointed at this project.
