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
- Routed: see **"V1 routing COMPLETE"** below — as of 2026-07-19 the board is
  ~99.85% routed (1 of ~660 connections open) with a solid GND plane.
  *(Original auto-router run only carried ~55%; the rest was finished with
  Freerouting — details below.)*

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

## V1 routing COMPLETE (2026-07-19, via Freerouting)

The board was finished with **Freerouting 2.2.4** (headless CLI, no GUI/sudo;
runs on a local Temurin JRE 25 in `~/opt/atmos-route/`). Key gotcha: Freerouting
**infinite-recurses on a partially-routed board** (`PolylineTrace.combine`), so
it must route a *clean* board. Flow (all scripts in `tools/`):
1. `strip_and_export.py` — remove signal tracks/vias (keep zones), export `Atmos.dsn`.
2. `patch_dsn_planes.py` — mark **In1(GND) as a `power` plane** (solid), leave
   **In2(PWR) as a signal layer**, drop the F.Cu/B.Cu GND plane polygons, default
   via → 0.6 mm. (Keeping *both* inner layers as planes leaves only 2 signal
   layers → Freerouting stalls at ~75 unrouted; freeing In2 fixes it.)
3. `~/opt/atmos-route/run_fr.sh` — Freerouting `-de Atmos.dsn -do Atmos.ses -mp 15`.
4. `import_ses.py` — strip + import the SES, refill zones.
5. `finish_gnd_clean.py` — stitch F.Cu GND pour islands to the In1 plane with
   vias (max-clearance point, **all-layer + hole-to-hole + edge aware**; 0.45 mm,
   0.4 mm fallback), island-removal on.
6. `route_plus5v.py` / `finish_last.py` — close the last stragglers.
7. min-via-diameter rule lowered 0.5 → **0.4 mm** in `.kicad_pro` (Freerouting
   emits 0.48 mm vias — standard, but tripped the old 0.5 mm min).

**Stackup as routed:** F.Cu (signal) · **In1 = solid GND plane** · In2 = +3V3
plane + power/signal routing (137 segs) · B.Cu (signal). GND return path is
intact; +3V3 distributed as copper on In2 — fine for this low-power node.

**Final state:** 533 F.Cu + 137 In2 + 31 B.Cu track segments; **107 vias**
(79×0.48 signal, 21×0.45 GND-stitch, 7×0.6 power). **0 shorts, 0 clearance,
0 hole-to-hole.** 1 connection open + a few benign edge/silk DRCs.

**The 1 open connection + things to fix on respin:**
- **U13 (SGP40) GND** — its GND pad island can't take a stitch via because U13
  is the **placeholder DFN footprint** (0.5 mm pitch, wrong land). Resolves when
  the real 2.44 mm SGP40 footprint is placed. (1 unconnected item.)
- **R14 placed at the board edge** → +5V trace from R14.2 starts in the edge-
  clearance zone (1 `copper_edge` DRC). Move R14 next to U9 (its boost converter)
  on respin. Routed anyway for V1 (F.Cu stub → B.Cu → +5V rail).
- Pre-existing edge-clearance on connector pads (J1/J2) and WROOM antenna
  courtyard (5) are expected; silkscreen overlaps are un-tidied ref-designators.

## Reproduce
```
python3 tools/board_gen.py                                   # placement
snap run --shell kicad.pcbnew -c 'python3 <abs>/tools/route_maze.py'    # signals
snap run --shell kicad.pcbnew -c 'python3 <abs>/tools/route_planes.py'  # planes
```
(`_Atmos_fresh.net` is the source netlist; regenerate with
`kicad-cli sch export netlist`.)
