"""Patch Atmos.dsn (from the .orig clean export) for a 3-signal-layer stackup
that keeps ONE solid GND plane:
  - F.Cu   : signal
  - GND(In1): POWER  -> solid ground plane (return path preserved)
  - PWR(In2): signal -> 3rd routing layer (carries +3V3 + secondary power as copper)
  - B.Cu   : signal
Edits:
  1. GND layer (type signal) -> (type power); PWR stays signal
  2. drop GND plane polygons on F.Cu and B.Cu, AND the +3V3 plane on PWR
     (keep only GND-on-GND). Frees F.Cu/PWR/B.Cu for routing.
  3. default via padstack 0.48mm -> 0.6mm (fixes via_diameter DRC)
Reads Atmos.dsn.orig, writes Atmos.dsn.
"""
DSN  = "/home/christian-thomas-hearn/Desktop/Atmos/Atmos.dsn"
ORIG = DSN + ".orig"
lines = open(ORIG).read().split("\n")

out = []
cur_layer = None
skip_until_close = False
changed = {"type": 0, "plane_drop": 0, "via": 0}
for ln in lines:
    s = ln.strip()

    if skip_until_close:
        if s.endswith("))"):
            skip_until_close = False
        continue

    # drop GND-on-F.Cu, GND-on-B.Cu, and +3V3-on-PWR planes; keep GND-on-GND
    if (s.startswith("(plane GND (polygon F.Cu")
            or s.startswith("(plane GND (polygon B.Cu")
            or s.startswith("(plane +3V3 (polygon PWR")):
        changed["plane_drop"] += 1
        if not s.endswith("))"):
            skip_until_close = True
        continue

    if s.startswith("(layer "):
        cur_layer = s.split()[1].rstrip(")")

    # only GND becomes a power plane; PWR stays a signal routing layer
    if s == "(type signal)" and cur_layer == "GND":
        out.append(ln.replace("signal", "power"))
        changed["type"] += 1
        continue

    if s.startswith("(via ") and "Via[0-3]_480:200_um" in ln:
        out.append(ln.replace('"Via[0-3]_480:200_um"', '"Via[0-3]_600:400_um"'))
        changed["via"] += 1
        continue

    out.append(ln)

open(DSN, "w").write("\n".join(out))
print("patched:", changed)
