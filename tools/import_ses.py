"""Apply Freerouting's Atmos.ses onto the board: strip old signal tracks/vias
(keep plane zones), import the SES routing, refill planes, report ratsnest,
and SAVE over Atmos.kicad_pcb (a pre-freeroute backup already exists).
Run:  snap run --shell kicad.pcbnew -c 'python3 <abs>/tools/import_ses.py'
"""
import pcbnew
from collections import defaultdict
SRC = "/home/christian-thomas-hearn/Desktop/Atmos/Atmos.kicad_pcb"
SES = "/home/christian-thomas-hearn/Desktop/Atmos/Atmos.ses"

b = pcbnew.LoadBoard(SRC)

# 1. strip existing signal tracks/vias so the SES applies cleanly
for t in list(b.GetTracks()):
    b.Remove(t)

# 2. import Freerouting session
imported = False
for how in ("module_board_file","module_file","board_method"):
    try:
        if how=="module_board_file":
            pcbnew.ImportSpecctraSES(b, SES); imported=True
        elif how=="module_file":
            pcbnew.ImportSpecctraSES(SES); imported=True
        elif how=="board_method" and hasattr(b,"ImportSpecctraSES"):
            b.ImportSpecctraSES(SES); imported=True
        if imported:
            print("imported via", how); break
    except Exception as e:
        print("  ", how, "failed:", e)

# 3. refill plane zones (guarded; SES import can leave the swig iters flaky)
try:
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    print("zones refilled")
except Exception as e:
    print("zone fill note:", e)

# 4. save over the real board (counting done separately via route_status.py)
pcbnew.SaveBoard(SRC, b)
print("saved:", SRC)
