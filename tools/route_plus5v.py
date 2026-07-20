"""Finish the one dangling +5V connection: R14.2 -> existing +5V copper at
(97.28,43.96), routed on the near-empty B.Cu with a via at each end.
"""
import pcbnew, math
from pcbnew import VECTOR2I, FromMM, ToMM
B = "/home/christian-thomas-hearn/Desktop/Atmos/Atmos.kicad_pcb"
b = pcbnew.LoadBoard(B)
NET = b.FindNet("+5V").GetNetCode()
START = (110.03, 42.45)     # R14.2
GOAL  = (97.28, 43.96)      # existing +5V F.Cu vertex

# obstacles on B.Cu path: non-+5V pads (any that reach B.Cu) + non-+5V B.Cu tracks + vias
pads=[]; btrk=[]; vias=[]
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname()=="+5V": continue
        if p.IsOnLayer(pcbnew.B_Cu):
            pos=p.GetPosition(); s=p.GetSize()
            pads.append((ToMM(pos.x),ToMM(pos.y),max(ToMM(s.x),ToMM(s.y))/2))
for t in b.GetTracks():
    if t.Type()==pcbnew.PCB_VIA_T:
        vp=t.GetPosition(); vias.append((ToMM(vp.x),ToMM(vp.y),ToMM(t.GetWidth())/2, t.GetNetname()))
    elif t.GetLayer()==pcbnew.B_Cu and t.GetNetname()!="+5V":
        s=t.GetStart();e=t.GetEnd(); btrk.append((ToMM(s.x),ToMM(s.y),ToMM(e.x),ToMM(e.y),ToMM(t.GetWidth())/2))

def dseg(px,py,ax,ay,bx,by):
    dx,dy=bx-ax,by-ay
    if dx==0 and dy==0: return math.hypot(px-ax,py-ay)
    t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-(ax+t*dx),py-(ay+t*dy))

W=0.3; CLR=0.2
def seg_clear(x0,y0,x1,y1):
    L=math.hypot(x1-x0,y1-y0); n=max(2,int(L/0.3))
    for k in range(n+1):
        t=k/n; x=x0+(x1-x0)*t; y=y0+(y1-y0)*t
        for (px,py,pr) in pads:
            if math.hypot(x-px,y-py) < pr+W/2+CLR: return False
        for (vx,vy,vr,vn) in vias:
            if vn=="+5V": continue
            if math.hypot(x-vx,y-vy) < vr+W/2+CLR: return False
        for (ax,ay,bx,by,hw) in btrk:
            if dseg(x,y,ax,ay,bx,by) < hw+W/2+CLR: return False
    return True

def add_via(x,y):
    v=pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(FromMM(x),FromMM(y)))
    v.SetDrill(FromMM(0.3)); v.SetWidth(FromMM(0.6)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu); v.SetNetCode(NET); b.Add(v)
def add_trk(x0,y0,x1,y1):
    t=pcbnew.PCB_TRACK(b); t.SetStart(VECTOR2I(FromMM(x0),FromMM(y0)))
    t.SetEnd(VECTOR2I(FromMM(x1),FromMM(y1))); t.SetWidth(FromMM(W))
    t.SetLayer(pcbnew.B_Cu); t.SetNetCode(NET); b.Add(t)

# try straight, then L-paths through a midpoint
paths=[[START,GOAL],
       [START,(GOAL[0],START[1]),GOAL],
       [START,(START[0],GOAL[1]),GOAL]]
for my in (39.5,40.0,45.5,47.0):
    paths.append([START,(START[0],my),(GOAL[0],my),GOAL])
chosen=None
for path in paths:
    if all(seg_clear(*p,*q) for p,q in zip(path,path[1:])):
        chosen=path; break
if chosen:
    add_via(*START)
    for p,q in zip(chosen,chosen[1:]): add_trk(*p,*q)
    add_via(*GOAL)
    print("routed +5V via B.Cu:", [(round(x,2),round(y,2)) for x,y in chosen])
    pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity()
    print("unconnected pads now:", b.GetConnectivity().GetUnconnectedCount(True))
    pcbnew.SaveBoard(B,b); print("saved")
else:
    print("no clear B.Cu path found; leave +5V for manual")
