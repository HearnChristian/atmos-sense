# Atmos PCB V1 — build notes (auto-generated 2026-07-14)

First board generated from the schematic with the radar-derived toolchain
(`tools/board_gen.py` → `tools/route_maze.py` → `tools/route_planes.py`, driven
through the snap `pcbnew` Python API). Intended as a V1 to review before/after
breadboarding — **not fab-ready as-is** (see open items).

## What's on the board
- 73 parts, 94 nets, **4-layer FR4 1.6 mm**: F.Cu / GND (In1) / +3V3 (In2) / B.Cu.
- Placement: WROOM top-left (antenna to edge) and RFM95W top-right for radio
  isolation; DS3231 + CR2032 backup centered; power cluster (CN3791/TPS61023/
  LTC4412/TPS22918/MAX17048) right-center; USB-C + microSD bottom-left; sensor
  breakout headers (AS3935/BME280) on the right edge; 4× M3 corner mounting holes.
- Routed: **GND plane (all)**, **+3V3 plane (18/21 pads)**, **17 signal nets**.
  ~55% of connections carried; **0 shorts**. Remaining ratsnest is the
  board-spanning buses (I²C SCL/SDA, SPI SD_*, USB D±) and secondary power
  (+VBATT, +5V, VIN_CHG, VSOL) — finish with KiCad's interactive router.

## Decisions / deviations to review (IMPORTANT)
1. **Board grew 65×50 → 74×56 mm.** The ratified 65×50 can't hold the measured
   parts all-top-side (WROOM 18×25.5, microSD 16×18, Keystone-3034 coin holder
   24×18, RFM95W 18.5×16.5). Revisit outline when an enclosure is chosen, or
   shrink parts (SMD coin holder, smaller µSD).
2. **6 IC footprints were dangling references** in the schematic (the vendor
   `.kicad_mod` files no longer exist on disk). Remapped to standard-library
   equivalents by package — verify pinout before fab:
   - U4 PMS5003 → `Molex_PicoBlade_53398-0871_1x08` (matches the ratified
     off-board connector; only pins 4/6/7/8 = TX/SET/GND/5V are wired)
   - U9 TPS61023 → `SOT-563` · U10 TPS22918 → `SOT-23-6`
   - U11 MAX17048 → `DFN-8-1EP_2x2mm_P0.5mm` · U12 CN3791 → `MSOP-10_3x3mm_P0.5mm`
   - U13 SGP40 → `DFN-6-1EP_2x2mm_P0.5mm` (**approximate** — real SGP40 is
     2.44×2.44 mm; rebuild the land before fab)
3. **microSD**: ratified part was GCT MEM2075 (no KiCad stock footprint) →
   substituted **Hirose DM3AT-SF-PEJM5** push-push as a V1 stand-in. Not
   pad-compatible with MEM2075 — pick the final part and rebuild.
4. **CN3791 (U12)** uses plain MSOP-10 with **no thermal exposed pad** because
   the schematic symbol has no EP pin. A charger wants the EP grounded — add an
   EP pin + thermal vias before fab.
5. **Design rules** set to JLC-realistic: 0.127 mm clearance, 0.15 mm PWR
   clearance, 0.2 mm min hole, 0.3 mm edge (`Atmos.kicad_pro`).

## Known DRC (all benign or expected)
- silk overlaps / silk-over-copper: reference designators not yet tidied.
- copper-edge: edge connectors (USB-C, µSD, JST, SMA) sit at the board edge.
- 5 courtyard overlaps: the WROOM's 48×41 antenna-clearance courtyard (air).
- ~6 track-near-resistor-pad clearances: minor, clean up during route finishing.

## Reproduce
```
python3 tools/board_gen.py                                   # placement
snap run --shell kicad.pcbnew -c 'python3 <abs>/tools/route_maze.py'    # signals
snap run --shell kicad.pcbnew -c 'python3 <abs>/tools/route_planes.py'  # planes
```
(`_Atmos_fresh.net` is the source netlist; regenerate with
`kicad-cli sch export netlist`.)
