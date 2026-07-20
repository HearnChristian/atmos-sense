"""Census of track copper per layer + via sizes on the saved board."""
import pcbnew
from collections import defaultdict, Counter
b = pcbnew.LoadBoard("/home/christian-thomas-hearn/Desktop/Atmos/Atmos.kicad_pcb")
laynames = {pcbnew.F_Cu:"F.Cu", pcbnew.B_Cu:"B.Cu", pcbnew.In1_Cu:"In1(GND)", pcbnew.In2_Cu:"In2(PWR)"}
seg_by_layer = Counter()
seg_nets_on_inner = defaultdict(set)
viadia = Counter()
nvia = 0
for t in b.GetTracks():
    if t.Type()==pcbnew.PCB_VIA_T:
        nvia += 1
        viadia[round(pcbnew.ToMM(t.GetWidth()),3)] += 1
        continue
    ly = t.GetLayer()
    seg_by_layer[laynames.get(ly, str(ly))] += 1
    if ly in (pcbnew.In1_Cu, pcbnew.In2_Cu):
        seg_nets_on_inner[laynames.get(ly)].add(t.GetNetname())
print("=== track segments per layer ===")
for k,v in seg_by_layer.most_common(): print(f"  {k:10s} {v}")
print("=== SIGNAL nets with copper on inner plane layers ===")
for ly, nets in seg_nets_on_inner.items():
    real = sorted(n for n in nets if n not in ("GND","+3V3"))
    print(f"  {ly}: {len(real)} non-plane nets -> {real}")
print(f"=== vias: {nvia} total, diameters(mm): {dict(viadia)} ===")
