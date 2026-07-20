"""Make a placement+planes-only DSN for Freerouting: remove all F/B.Cu signal
tracks and vias (which make Freerouting's combine() infinite-recurse), KEEP the
GND/+3V3 plane zones, export Atmos.dsn. Original board file is NOT modified.
Run:  snap run --shell kicad.pcbnew -c 'python3 <abs>/tools/strip_and_export.py'
"""
import pcbnew, os
SRC = "/home/christian-thomas-hearn/Desktop/Atmos/Atmos.kicad_pcb"
DSN = "/home/christian-thomas-hearn/Desktop/Atmos/Atmos.dsn"
b = pcbnew.LoadBoard(SRC)

tracks = list(b.GetTracks())          # includes PCB_TRACK and PCB_VIA
n_seg = n_via = 0
for t in tracks:
    if t.Type() == pcbnew.PCB_VIA_T: n_via += 1
    else: n_seg += 1
    b.Remove(t)
print(f"removed {n_seg} track segments + {n_via} vias")
print(f"zones kept: {b.GetAreaCount() if hasattr(b,'GetAreaCount') else len(list(b.Zones()))}")
print(f"footprints: {len(list(b.GetFootprints()))}")

# refill the plane zones so they still describe copper for the DSN
try:
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
except Exception as e:
    print("zone fill note:", e)

pcbnew.ExportSpecctraDSN(b, DSN)
print("DSN written:", os.path.exists(DSN), os.path.getsize(DSN), "bytes")
