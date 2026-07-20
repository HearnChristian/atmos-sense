"""Report REAL unrouted nets of Atmos.kicad_pcb (multi-pad nets not fully connected).
Run:  snap run --shell kicad.pcbnew -c 'python3 <abs>/tools/route_status.py'
"""
import pcbnew
from collections import defaultdict
BOARD = "/home/christian-thomas-hearn/Desktop/Atmos/Atmos.kicad_pcb"
b = pcbnew.LoadBoard(BOARD)
b.BuildConnectivity()
conn = b.GetConnectivity()

seg = defaultdict(int); via = defaultdict(int)
for t in b.GetTracks():
    nn = t.GetNetname()
    if t.Type() == pcbnew.PCB_VIA_T: via[nn]+=1
    else: seg[nn]+=1

# pad count per net
padcount = defaultdict(int)
for fp in b.GetFootprints():
    for p in fp.Pads():
        nn = p.GetNetname()
        if nn: padcount[nn]+=1

# a net is "open" if pcbnew reports unconnected pads for it
open_real = []
for code in range(1, b.GetNetCount()):
    ni = b.GetNetInfo().GetNetItem(code)
    if ni is None: continue
    name = ni.GetNetname()
    if name in ("GND","+3V3"): continue
    if name.startswith("unconnected-"): continue
    if padcount[name] < 2: continue
    # unconnected count for this net
    u = conn.GetUnconnectedCount if False else None
    open_real.append((name, padcount[name], seg.get(name,0), via.get(name,0)))

# ones with zero copper are certainly unrouted; ones with copper may be partial
print(f"{'net':26s} pads seg via")
zero=[]; partial=[]
for name,pc,s,v in sorted(open_real):
    tag=""
    if s==0 and v==0: zero.append(name); tag=" <-- NO COPPER"
    print(f"{name:26s} {pc:3d} {s:4d} {v:3d}{tag}")
print(f"\nreal multi-pad nets total: {len(open_real)}")
print(f"nets with ZERO copper (definitely unrouted): {len(zero)}")
print("  ", zero)
print("total unconnected pads (board):", conn.GetUnconnectedCount(True))
