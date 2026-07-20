"""Stitch F.Cu GND islands to the In1 plane with vias, using an ALL-LAYER,
ALL-HOLE, edge-aware clearance test (a through-via must clear copper on every
layer + keep hole-to-hole spacing). Islands that can't take a via are dropped
by island-removal (no floating copper). +5V is left untouched.
"""
import pcbnew, math
from pcbnew import VECTOR2I, FromMM, ToMM
B="/home/christian-thomas-hearn/Desktop/Atmos/Atmos.kicad_pcb"
b=pcbnew.LoadBoard(B)
GND=b.FindNet("GND").GetNetCode()
XI,XA,YI,YA=41.0,113.0,41.0,95.0            # in-board margin
pcbnew.ZONE_FILLER(b).Fill(b.Zones())

# ---- obstacle snapshot (GetTracks cached once) ----
pads=[]
for fp in b.GetFootprints():
    for p in fp.Pads():
        pos=p.GetPosition(); s=p.GetSize()
        dr=ToMM(p.GetDrillSize().x)/2 if p.GetDrillSize().x>0 else 0.0
        pads.append((ToMM(pos.x),ToMM(pos.y),max(ToMM(s.x),ToMM(s.y))/2,dr,p.GetNetname()))
TRK=[]; VIA=[]
for t in list(b.GetTracks()):
    if t.Type()==pcbnew.PCB_VIA_T:
        vp=t.GetPosition(); VIA.append((ToMM(vp.x),ToMM(vp.y),ToMM(t.GetWidth())/2,ToMM(t.GetDrill())/2,t.GetNetname()))
    else:
        s=t.GetStart();e=t.GetEnd(); TRK.append((ToMM(s.x),ToMM(s.y),ToMM(e.x),ToMM(e.y),ToMM(t.GetWidth())/2,t.GetNetname()))

def dseg(px,py,ax,ay,bx,by):
    dx,dy=bx-ax,by-ay
    if dx==0 and dy==0: return math.hypot(px-ax,py-ay)
    t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-(ax+t*dx),py-(ay+t*dy))

COP=0.17; H2H=0.26
def clearance(px,py,vr,vdr):
    """min radial slack for a via of copper-radius vr / drill-radius vdr at (px,py);
    negative => violates. Also enforces in-board box."""
    if not (XI<=px<=XA and YI<=py<=YA): return -9
    m=9.9
    for (x,y,cr,dr,nn) in pads:
        d=math.hypot(px-x,py-y)
        if nn!="GND": m=min(m, d-(cr+vr+COP))
        if dr>0:      m=min(m, d-(dr+vdr+H2H))
    for (x,y,r,dr,nn) in VIA:
        d=math.hypot(px-x,py-y)
        if nn!="GND": m=min(m, d-(r+vr+COP))
        m=min(m, d-(dr+vdr+H2H))
    for (ax,ay,bx,by,hw,nn) in TRK:
        if nn=="GND": continue
        m=min(m, dseg(px,py,ax,ay,bx,by)-(hw+vr+COP))
    return m

def add_via(x,y,dia):
    v=pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(FromMM(x),FromMM(y)))
    v.SetDrill(FromMM(0.2)); v.SetWidth(FromMM(dia)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu); v.SetNetCode(GND); b.Add(v)
    VIA.append((x,y,dia/2,0.1,"GND"))

anchors=[(x,y) for (x,y,vr,dr,nn) in VIA if nn=="GND"]
for (x,y,cr,dr,nn) in pads:
    if nn=="GND" and dr>0: anchors.append((x,y))

added=skipped=noroom=0
for z in b.Zones():
    if z.GetLayer()!=pcbnew.F_Cu or z.GetNetname()!="GND": continue
    sps=z.GetFilledPolysList(pcbnew.F_Cu)
    for i in range(sps.OutlineCount()):
        oc=sps.Outline(i)
        xs=[ToMM(oc.CPoint(j).x) for j in range(oc.PointCount())]
        ys=[ToMM(oc.CPoint(j).y) for j in range(oc.PointCount())]
        if not xs: continue
        if any(min(xs)<=ax<=max(xs) and min(ys)<=ay<=max(ys) and
               sps.Contains(VECTOR2I(FromMM(ax),FromMM(ay)),i) for ax,ay in anchors):
            skipped+=1; continue
        # find the interior point with MAX clearance (try 0.45, then 0.4 via)
        best=None; yy=min(ys)+0.08
        while yy<max(ys)-0.08:
            xx=min(xs)+0.08
            while xx<max(xs)-0.08:
                if sps.Contains(VECTOR2I(FromMM(xx),FromMM(yy)),i):
                    c=clearance(xx,yy,0.225,0.1)
                    if best is None or c>best[0]: best=(c,xx,yy)
                xx+=0.1
            yy+=0.1
        if best and best[0]>=0:
            add_via(best[1],best[2],0.45); anchors.append((best[1],best[2])); added+=1
        else:
            # retry with a smaller 0.4mm via for tight islands
            best=None; yy=min(ys)+0.08
            while yy<max(ys)-0.08:
                xx=min(xs)+0.08
                while xx<max(xs)-0.08:
                    if sps.Contains(VECTOR2I(FromMM(xx),FromMM(yy)),i):
                        c=clearance(xx,yy,0.2,0.1)
                        if best is None or c>best[0]: best=(c,xx,yy)
                    xx+=0.1
                yy+=0.1
            if best and best[0]>=0:
                add_via(best[1],best[2],0.4); anchors.append((best[1],best[2])); added+=1
            else:
                noroom+=1

for z in b.Zones():
    if z.GetNetname()=="GND" and z.GetLayer() in (pcbnew.F_Cu,pcbnew.B_Cu):
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity()
print(f"stitch vias added={added} already-anchored={skipped} no-room(dropped)={noroom}")
print("unconnected pads:", b.GetConnectivity().GetUnconnectedCount(True))
pcbnew.SaveBoard(B,b); print("saved")
