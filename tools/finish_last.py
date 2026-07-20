"""Close the last two connections:
  A) +5V: R14.2 -> existing +5V copper, routed on B.Cu via a grid A*, with F.Cu
     escape stubs + vias placed clear of the board edge.
  B) U13 GND island -> nearest anchored GND, via a thin 0.25mm F.Cu jumper.
Grid A* adapted from route_maze. Cache GetTracks once (swig).
"""
import pcbnew, math, heapq
from pcbnew import VECTOR2I, FromMM, ToMM
B="/home/christian-thomas-hearn/Desktop/Atmos/Atmos.kicad_pcb"
b=pcbnew.LoadBoard(B)
P5=b.FindNet("+5V").GetNetCode(); GND=b.FindNet("GND").GetNetCode()
pcbnew.ZONE_FILLER(b).Fill(b.Zones())

OX,OY,BW,BH=40.0,40.0,74.0,56.0
G=0.35; NX,NY=int(BW/G)+1,int(BH/G)+1
def gx(x):return int(round((x-OX)/G))
def gy(y):return int(round((y-OY)/G))
def wx(i):return OX+i*G
def wy(j):return OY+j*G

pads=[]; vias=[]; trk=[]
for fp in b.GetFootprints():
    for p in fp.Pads():
        pos=p.GetPosition(); s=p.GetSize()
        dr=ToMM(p.GetDrillSize().x)/2 if p.GetDrillSize().x>0 else 0.0
        pads.append((ToMM(pos.x),ToMM(pos.y),max(ToMM(s.x),ToMM(s.y))/2,dr,p.GetNetname(),
                     p.IsOnLayer(pcbnew.F_Cu),p.IsOnLayer(pcbnew.B_Cu)))
for t in list(b.GetTracks()):
    if t.Type()==pcbnew.PCB_VIA_T:
        vp=t.GetPosition(); vias.append((ToMM(vp.x),ToMM(vp.y),ToMM(t.GetWidth())/2,ToMM(t.GetDrill())/2,t.GetNetname()))
    else:
        s=t.GetStart();e=t.GetEnd()
        trk.append((ToMM(s.x),ToMM(s.y),ToMM(e.x),ToMM(e.y),ToMM(t.GetWidth())/2,t.GetLayer(),t.GetNetname()))
def dseg(px,py,ax,ay,bx,by):
    dx,dy=bx-ax,by-ay
    if dx==0 and dy==0:return math.hypot(px-ax,py-ay)
    u=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-(ax+u*dx),py-(ay+u*dy))

def add_via(x,y,net,dia=0.6,drl=0.3):
    v=pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(FromMM(x),FromMM(y)))
    v.SetDrill(FromMM(drl)); v.SetWidth(FromMM(dia)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu); v.SetNetCode(net); b.Add(v)
    vias.append((x,y,dia/2,drl/2,"+5V" if net==P5 else "GND"))
def add_trk(x0,y0,x1,y1,net,layer,w):
    t=pcbnew.PCB_TRACK(b); t.SetStart(VECTOR2I(FromMM(x0),FromMM(y0)))
    t.SetEnd(VECTOR2I(FromMM(x1),FromMM(y1))); t.SetWidth(FromMM(w)); t.SetLayer(layer)
    t.SetNetCode(net); b.Add(t)
    trk.append((x0,y0,x1,y1,w/2,layer,"+5V" if net==P5 else "GND"))

# --- build B.Cu occupancy grid for +5V (block non-+5V B.Cu tracks, all pads, all vias, edge) ---
def build_grid(layer,mynet,w):
    grid=[[False]*NX for _ in range(NY)]
    for i in range(NX):
        for k in (0,1,NY-2,NY-1):
            if 0<=k<NY: grid[k][i]=True
    for j in range(NY):
        for k in (0,1,NX-2,NX-1): grid[j][k]=True
    half=w/2+0.2
    def blk(cx,cy,rad):
        i0,i1=max(0,gx(cx-rad)),min(NX-1,gx(cx+rad))
        j0,j1=max(0,gy(cy-rad)),min(NY-1,gy(cy+rad))
        for j in range(j0,j1+1):
            for i in range(i0,i1+1):
                if (wx(i)-cx)**2+(wy(j)-cy)**2<=rad*rad: grid[j][i]=True
    for (x,y,cr,dr,nn,onf,onb) in pads:
        if nn==mynet: continue
        onlayer = onf if layer==pcbnew.F_Cu else onb
        if onlayer or dr>0: blk(x,y,cr+half)
    for (x,y,vr,dr,nn) in vias:
        if nn==mynet: continue
        blk(x,y,vr+half)
    for (ax,ay,bx,by,hw,ly,nn) in trk:
        if nn==mynet or ly!=layer: continue
        L=math.hypot(bx-ax,by-ay); n=max(1,int(L/G))
        for k in range(n+1):
            t=k/n; blk(ax+(bx-ax)*t,ay+(by-ay)*t,hw+half)
    return grid
def astar(grid,s,gcell):
    si,sj=s; gi,gj=gcell
    oh=[(0,si,sj)]; came={}; gs={(si,sj):0}
    NB=[(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
    while oh:
        f,i,j=heapq.heappop(oh)
        if (i,j)==(gi,gj):
            path=[(i,j)]
            while (i,j) in came:i,j=came[(i,j)];path.append((i,j))
            return path[::-1]
        for di,dj in NB:
            ni,nj=i+di,j+dj
            if not(0<=ni<NX and 0<=nj<NY) or grid[nj][ni]: continue
            if di and dj and (grid[j][ni] or grid[nj][i]): continue
            ng=gs[(i,j)]+(1.41 if di and dj else 1.0)
            if ng<gs.get((ni,nj),1e9):
                gs[(ni,nj)]=ng; came[(ni,nj)]=(i,j)
                heapq.heappush(oh,(ng+math.hypot(ni-gi,nj-gj),ni,nj))
    return None
def emit(path,net,layer,w):
    pts=[(wx(i),wy(j)) for i,j in path]; simp=[pts[0]]
    for k in range(1,len(pts)-1):
        ax,ay=simp[-1]; bx,by=pts[k]; cx,cy=pts[k+1]
        if (bx-ax)*(cy-by)==(by-ay)*(cx-bx): continue
        simp.append(pts[k])
    simp.append(pts[-1])
    for p,q in zip(simp,simp[1:]): add_trk(*p,*q,net,layer,w)

def via_clear(px,py,vr=0.3,vdr=0.15):
    if not(41<=px<=113 and 41<=py<=95): return False
    for (x,y,cr,dr,nn,onf,onb) in pads:
        d=math.hypot(px-x,py-y)
        if nn!="+5V" and d<cr+vr+0.17: return False
        if dr>0 and d<dr+vdr+0.26: return False
    for (x,y,r,dr,nn) in vias:
        d=math.hypot(px-x,py-y)
        if nn!="+5V" and d<r+vr+0.17: return False
        if d<dr+vdr+0.26: return False
    return True

# ===== A) +5V =====
R14=(110.03,42.45); GOAL=(97.28,43.96); W=0.3
# escape via must head INWARD (toward goal, i.e. left) and stay clear of the
# right-edge features (x<=108.5); then B.Cu A* to GOAL, via up at GOAL.
grid=build_grid(pcbnew.B_Cu,"+5V",W); fg=build_grid(pcbnew.F_Cu,"+5V",W)
def fcu_stub_clear(ax,ay,bx,by):
    L=math.hypot(bx-ax,by-ay); n=max(1,int(L/G))
    for k in range(n+1):
        t=k/n; xx,yy=ax+(bx-ax)*t,ay+(by-ay)*t
        if fg[gy(yy)][gx(xx)]: return False
    return True
esc=None
cands=[(108.0,42.45),(107.5,43.2),(107.0,44.0),(108.0,44.5),(106.5,42.6),
       (107.0,41.6),(105.5,43.5),(106.0,45.0),(108.3,43.6)]
for (ex,ey) in cands:
    if ex<=108.5 and via_clear(ex,ey) and not grid[gy(ey)][gx(ex)] and fcu_stub_clear(*R14,ex,ey):
        esc=(ex,ey); break
p5_ok=False
if esc and via_clear(*GOAL):
    path=astar(grid,(gx(esc[0]),gy(esc[1])),(gx(GOAL[0]),gy(GOAL[1])))
    if path:
        add_trk(*R14,*esc,P5,pcbnew.F_Cu,W); add_via(*esc,P5)
        emit(path,P5,pcbnew.B_Cu,W); add_via(*GOAL,P5)
        p5_ok=True
print("+5V routed:",p5_ok, "escape:",esc and (round(esc[0],1),round(esc[1],1)))

# ===== B) U13 GND: drop a GND via in open area near U13, jumper it to U13.7 =====
U13=[(83.03,50.00),(84.00,50.00)]   # U13.2, U13.7 GND pads
gnd_ok=False
gf=build_grid(pcbnew.F_Cu,"GND",0.25)
# search a via_clear GND spot within ~3mm of U13, prefer below/beside (open area)
via_spot=None
for rad in (1.8,2.2,2.6,3.0,3.4):
    for ang in range(0,360,15):
        vx=84.0+rad*math.cos(math.radians(ang)); vy=50.0+rad*math.sin(math.radians(ang))
        if via_clear(vx,vy,0.225,0.1) and not gf[gy(vy)][gx(vx)]:
            via_spot=(vx,vy); break
    if via_spot: break
if via_spot:
    for src in U13:
        path=astar(gf,(gx(src[0]),gy(src[1])),(gx(via_spot[0]),gy(via_spot[1])))
        if path:
            emit(path,GND,pcbnew.F_Cu,0.25); add_via(*via_spot,GND,0.45,0.2); gnd_ok=True
            print("U13 GND: via at",(round(via_spot[0],1),round(via_spot[1],1)),"jumper from",src)
            break
print("U13 GND routed:",gnd_ok)

for z in b.Zones():
    if z.GetNetname()=="GND" and z.GetLayer() in (pcbnew.F_Cu,pcbnew.B_Cu):
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity()
print("unconnected pads:", b.GetConnectivity().GetUnconnectedCount(True))
pcbnew.SaveBoard(B,b); print("saved")
