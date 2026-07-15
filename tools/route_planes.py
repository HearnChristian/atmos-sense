"""Atmos routing Phase A: power/ground planes via pcbnew.

  In1.Cu = solid GND plane      In2.Cu = solid +3V3 plane
  F.Cu / B.Cu = GND pours (open areas)
Connect every GND pad to the GND plane (pour + stitching via at pad),
every +3V3 pad to the +3V3 plane (via + short F.Cu stub), then fill.

Run:  snap run --shell kicad.pcbnew -c 'python3 <this>'  (needs the snap pcbnew).
"""
import math, pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

BOARD = "/home/christian-thomas-hearn/Desktop/Atmos/Atmos.kicad_pcb"
OX, OY, BW, BH = 40.0, 40.0, 74.0, 56.0

b = pcbnew.LoadBoard(BOARD)
def mm(x, y): return VECTOR2I(FromMM(x), FromMM(y))
def net(name):
    n = b.FindNet(name); assert n, "no net " + name
    return n

def add_zone(layer, netname, pts, prio=0, clearance=0.2, minw=0.2):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer); z.SetNetCode(net(netname).GetNetCode())
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(FromMM(clearance)); z.SetMinThickness(FromMM(minw))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    o = z.Outline(); o.NewOutline()
    for x, y in pts: o.Append(FromMM(x), FromMM(y))
    b.Add(z); return z

def add_via(x, y, netname, drill=0.3, dia=0.6):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(mm(x, y)); v.SetDrill(FromMM(drill)); v.SetWidth(FromMM(dia))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNetCode(net(netname).GetNetCode()); b.Add(v)

def add_track(x0, y0, x1, y1, w, layer, netname):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(mm(x0, y0)); t.SetEnd(mm(x1, y1))
    t.SetWidth(FromMM(w)); t.SetLayer(layer); t.SetNetCode(net(netname).GetNetCode())
    b.Add(t)

# ---- collect pads + obstacles ----
gnd_pads, v3_pads = [], []
obstacles = []   # (x,y,r,net) keep-out for non-target-net pads
for fp in b.GetFootprints():
    for p in fp.Pads():
        pos = p.GetPosition(); x, y = ToMM(pos.x), ToMM(pos.y)
        s = p.GetSize(); r = max(ToMM(s.x), ToMM(s.y)) / 2
        nn = p.GetNetname()
        if nn == "GND":   gnd_pads.append((x, y, r))
        elif nn == "+3V3": v3_pads.append((x, y, r))
        obstacles.append((x, y, r, nn))

# existing copper from the signal router (vias + tracks) — must be dodged
existing_vias = []   # (x,y)
existing_tracks = [] # (x0,y0,x1,y1,net,halfw)
for t in b.Tracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        pos = t.GetPosition(); existing_vias.append((ToMM(pos.x), ToMM(pos.y)))
    else:
        s = t.GetStart(); e = t.GetEnd()
        existing_tracks.append((ToMM(s.x),ToMM(s.y),ToMM(e.x),ToMM(e.y),
                                t.GetNetname(), ToMM(t.GetWidth())/2))

def _seg_d(px,py,x0,y0,x1,y1):
    dx,dy=x1-x0,y1-y0; L2=dx*dx+dy*dy
    u=0.0 if L2==0 else max(0.0,min(1.0,((px-x0)*dx+(py-y0)*dy)/L2))
    return math.hypot(px-(x0+u*dx), py-(y0+u*dy))

placed_vias = []   # (x,y)
def clear_spot(x, y, want_net, need=0.55):
    if x < OX+0.9 or x > OX+BW-0.9 or y < OY+0.9 or y > OY+BH-0.9: return False
    for (ox, oy) in placed_vias + existing_vias:      # hole-to-hole
        if (x-ox)**2 + (y-oy)**2 < 0.62**2: return False
    for (ox, oy, orr, onn) in obstacles:
        if onn == want_net: continue
        if (x-ox)**2 + (y-oy)**2 < (orr+need)**2: return False
    for (x0,y0,x1,y1,tn,hw) in existing_tracks:       # via(0.3r)+clr vs foreign track
        if tn == want_net: continue
        if _seg_d(x,y,x0,y0,x1,y1) < 0.3 + hw + 0.22: return False
    return True

def stub_clear(px, py, vx, vy, netname, w=0.25):
    """F.Cu stub pad->via must not graze a foreign pad."""
    L = math.hypot(vx-px, vy-py); n = max(2, int(L/0.15)); half = w/2 + 0.15
    for i in range(n+1):
        t=i/n; x=px+(vx-px)*t; y=py+(vy-py)*t
        for (ox,oy,orr,onn) in obstacles:
            if onn == netname: continue
            if (x-ox)**2+(y-oy)**2 < (orr+half)**2: return False
    return True

def connect_pad(px, py, pr, netname, need_stub):
    """place a via near the pad reaching the inner plane; stub on F.Cu if needed."""
    for rad in (pr+0.55, pr+0.8, pr+1.1, pr+1.5):
        for ang in range(0, 360, 20):
            a = math.radians(ang)
            vx, vy = px+rad*math.cos(a), py+rad*math.sin(a)
            if not clear_spot(vx, vy, netname): continue
            if need_stub and not stub_clear(px, py, vx, vy, netname): continue
            add_via(vx, vy, netname)
            placed_vias.append((vx, vy))
            if need_stub:
                add_track(px, py, vx, vy, 0.25, pcbnew.F_Cu, netname)
            return True
    return False

# ---- zones ---- (inset 0.5 keeps plane copper off the board edge)
inset = 0.5
rect = [(OX+inset,OY+inset),(OX+BW-inset,OY+inset),(OX+BW-inset,OY+BH-inset),(OX+inset,OY+BH-inset)]
add_zone(pcbnew.In1_Cu, "GND",  rect, prio=0, clearance=0.2)
add_zone(pcbnew.In2_Cu, "+3V3", rect, prio=0, clearance=0.2)
add_zone(pcbnew.F_Cu,   "GND",  rect, prio=0, clearance=0.25)
add_zone(pcbnew.B_Cu,   "GND",  rect, prio=0, clearance=0.25)

# ---- connect pads to planes ----
ng = sum(connect_pad(x, y, r, "GND",  need_stub=False) for (x, y, r) in gnd_pads)
n3 = sum(connect_pad(x, y, r, "+3V3", need_stub=True)  for (x, y, r) in v3_pads)

# ---- coarse GND stitching grid for plane integrity ----
gx = OX+4
while gx < OX+BW-4:
    gy = OY+4
    while gy < OY+BH-4:
        if clear_spot(gx, gy, "GND", need=0.6):
            add_via(gx, gy, "GND"); placed_vias.append((gx, gy))
        gy += 6.0
    gx += 6.0

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(BOARD, b)
print(f"planes poured. GND pads viaed {ng}/{len(gnd_pads)}, +3V3 pads viaed {n3}/{len(v3_pads)}, total vias {len(placed_vias)}")
