"""Atmos signal routing via a gridded A* maze router (pcbnew).

Runs on the placement-only board BEFORE planes. Each pad gets a via escape to
B.Cu; consecutive pads of a net are joined by an A* path on a 0.4mm B.Cu grid
(obstacles = THT pads, foreign vias, already-routed foreign tracks, inflated
for clearance). Short nets try a direct F.Cu path first (no via). Remaining
GND/+3V3 go to planes afterwards (route_planes.py).

Run:  snap run --shell kicad.pcbnew -c 'python3 <this>'
"""
import math, heapq, pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

BOARD = "/home/christian-thomas-hearn/Desktop/Atmos/Atmos.kicad_pcb"
OX, OY, BW, BH = 40.0, 40.0, 74.0, 56.0
GRID = 0.4                                  # cell size mm
NX, NY = int(BW/GRID)+1, int(BH/GRID)+1
def gx(x): return int(round((x-OX)/GRID))
def gy(y): return int(round((y-OY)/GRID))
def wx(i):  return OX + i*GRID
def wy(j):  return OY + j*GRID

b = pcbnew.LoadBoard(BOARD)
def mm(x,y): return VECTOR2I(FromMM(x),FromMM(y))
def netcode(name): return b.FindNet(name).GetNetCode()

POWER = {"+VBATT":0.5,"VIN_CHG":0.5,"VSOL":0.5,"+5V":0.5,"+5V_PMS":0.4,
         "VBUS":0.5,"MPPT":0.4,"CSP":0.4,"COM":0.4,"FB_BOOST":0.25,"Net-(BT1-+)":0.3}
SIGW = 0.2

# occupancy grid: None=free, else owner net name; borders blocked
BLOCK = "#"
grid = [[None]*NX for _ in range(NY)]
for i in range(NX):          # 2-cell (0.8mm) border keeps copper off the edge
    for k in (0,1,NY-2,NY-1): grid[k][i]=BLOCK
for j in range(NY):
    for k in (0,1,NX-2,NX-1): grid[j][k]=BLOCK

_ledger=None   # when a list, records grid/copper changes for per-net rollback
def _set(i,j,val):
    if _ledger is not None: _ledger.append(("cell",(i,j,grid[j][i])))
    grid[j][i]=val
def block_disc(cx,cy,r,owner=BLOCK):
    i0,i1=max(0,gx(cx-r)),min(NX-1,gx(cx+r))
    j0,j1=max(0,gy(cy-r)),min(NY-1,gy(cy+r))
    for j in range(j0,j1+1):
        for i in range(i0,i1+1):
            if (wx(i)-cx)**2+(wy(j)-cy)**2 <= r*r:
                if grid[j][i] is None or owner==BLOCK: _set(i,j,owner)

# --- THT pads block B.Cu for every net ---
pads_b=[]; pads_f=[]
for fp in b.GetFootprints():
    for p in fp.Pads():
        pos=p.GetPosition(); s=p.GetSize()
        x,y,r=ToMM(pos.x),ToMM(pos.y),max(ToMM(s.x),ToMM(s.y))/2
        rec=(x,y,r,p.GetNetname())
        if p.IsOnLayer(pcbnew.F_Cu): pads_f.append(rec)
        if p.IsOnLayer(pcbnew.B_Cu):
            pads_b.append(rec); block_disc(x,y,r+0.35)

vias=[]
_ledger=None   # when a list, records (kind,payload) for rollback of the current net
def _rec(kind,payload):
    if _ledger is not None: _ledger.append((kind,payload))
def add_via(x,y,name,dia=0.6,drl=0.3):
    v=pcbnew.PCB_VIA(b); v.SetPosition(mm(x,y)); v.SetDrill(FromMM(drl)); v.SetWidth(FromMM(dia))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu)
    v.SetNetCode(netcode(name)); b.Add(v); vias.append((x,y))
    block_disc(x,y,dia/2+0.2,name)
    _rec("item",v); _rec("via",(x,y))
def add_track(x0,y0,x1,y1,w,layer,name):
    t=pcbnew.PCB_TRACK(b); t.SetStart(mm(x0,y0)); t.SetEnd(mm(x1,y1))
    t.SetWidth(FromMM(w)); t.SetLayer(layer); t.SetNetCode(netcode(name)); b.Add(t)
    _rec("item",t)

def via_ok(x,y,name,keep=0.42,dia=0.6):
    if x<OX+0.8 or x>OX+BW-0.8 or y<OY+0.8 or y>OY+BH-0.8: return False
    for (vx,vy) in vias:
        if (x-vx)**2+(y-vy)**2 < (dia/2+0.35)**2: return False
    for (px,py,pr,pn) in pads_f+pads_b:
        if pn==name: continue
        if (x-px)**2+(y-py)**2 < (pr+keep)**2: return False
    return True

_esc={}
def escape(px,py,pr,name,w):
    key=(round(px,3),round(py,3),name)
    if key in _esc: return _esc[key]
    for (dia,drl,vk) in ((0.6,0.3,0.42),(0.5,0.25,0.36)):
        for rad in (pr+0.5,pr+0.7,pr+0.95,pr+1.25,pr+1.6,pr+2.1):
            for ang in range(0,360,15):
                a=math.radians(ang); vx,vy=px+rad*math.cos(a),py+rad*math.sin(a)
                if via_ok(vx,vy,name,vk,dia):
                    add_via(vx,vy,name,dia,drl); add_track(px,py,vx,vy,max(w,0.2),pcbnew.F_Cu,name)
                    _esc[key]=(vx,vy); return (vx,vy)
    _esc[key]=None; return None

def passable(i,j,name):
    if i<0 or i>=NX or j<0 or j>=NY: return False
    c=grid[j][i]; return c is None or c==name

def astar(start,goal,name):
    si,sj=start; gi,gj=goal
    openh=[(0,si,sj)]; came={}; gsc={(si,sj):0}
    NB=[(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
    while openh:
        f,i,j=heapq.heappop(openh)
        if (i,j)==(gi,gj):
            path=[(i,j)]
            while (i,j) in came: i,j=came[(i,j)]; path.append((i,j))
            return path[::-1]
        for di,dj in NB:
            ni,nj=i+di,j+dj
            if not passable(ni,nj,name): continue
            if di and dj:  # no diagonal corner-cutting through blocked cells
                if not passable(i+di,j,name) or not passable(i,j+dj,name): continue
            step=1.41 if di and dj else 1.0
            ng=gsc[(i,j)]+step
            if ng<gsc.get((ni,nj),1e9):
                gsc[(ni,nj)]=ng; came[(ni,nj)]=(i,j)
                h=math.hypot(ni-gi,nj-gj)
                heapq.heappush(openh,(ng+h,ni,nj))
    return None

def mark_path(path,name,w):
    inf=1 if w<=0.3 else 2
    for (i,j) in path:
        for dj in range(-inf,inf+1):
            for di in range(-inf,inf+1):
                ii,jj=i+di,j+dj
                if 0<=ii<NX and 0<=jj<NY and grid[jj][ii] is None:
                    _set(ii,jj,name)

def lay_track(path,name,w):
    # simplify collinear runs then emit B.Cu segments
    pts=[(wx(i),wy(j)) for (i,j) in path]
    simp=[pts[0]]
    for k in range(1,len(pts)-1):
        ax,ay=simp[-1]; bx,by=pts[k]; cx,cy=pts[k+1]
        if (bx-ax)*(cy-by)==(by-ay)*(cx-bx):  # collinear
            continue
        simp.append(pts[k])
    simp.append(pts[-1])
    for p,q in zip(simp,simp[1:]):
        add_track(p[0],p[1],q[0],q[1],w,pcbnew.B_Cu,name)

# F.Cu direct for short nets (no via) — quick check against F.Cu pads
def fcu_direct(A,B,name,w):
    ax,ay,ar=A; bx,by,br=B
    if math.hypot(bx-ax,by-ay)>9: return False
    def clear(x0,y0,x1,y1):
        L=math.hypot(x1-x0,y1-y0); n=max(2,int(L/0.3)); half=w/2+0.28
        for k in range(n+1):
            t=k/n; x=x0+(x1-x0)*t; y=y0+(y1-y0)*t
            for (px,py,pr,pn) in pads_f:
                if pn==name: continue
                if (x-px)**2+(y-py)**2<(pr+half)**2: return False
        return True
    for path in ([(ax,ay),(bx,by)],[(ax,ay),(bx,ay),(bx,by)],[(ax,ay),(ax,by),(bx,by)]):
        if all(clear(p[0],p[1],q[0],q[1]) for p,q in zip(path,path[1:])):
            for p,q in zip(path,path[1:]): add_track(p[0],p[1],q[0],q[1],w,pcbnew.F_Cu,name)
            return True
    return False

def route_edge(A,B,name,w):
    if fcu_direct(A,B,name,w): return True
    va=escape(A[0],A[1],A[2],name,w); vb=escape(B[0],B[1],B[2],name,w)
    if not (va and vb): return False
    s=(gx(va[0]),gy(va[1])); g=(gx(vb[0]),gy(vb[1]))
    # free the endpoints for this net
    for (ci,cj) in (s,g):
        if 0<=ci<NX and 0<=cj<NY and grid[cj][ci]==BLOCK: return False
    path=astar(s,g,name)
    if not path: return False
    mark_path(path,name,w); lay_track(path,name,w)
    return True

# ---- collect nets, route shortest first ----
skip={"GND","+3V3"}
netpads={}
for fp in b.GetFootprints():
    for p in fp.Pads():
        nn=p.GetNetname()
        if not nn or nn in skip or nn.startswith("unconnected"): continue
        pos=p.GetPosition(); s=p.GetSize()
        netpads.setdefault(nn,[]).append((ToMM(pos.x),ToMM(pos.y),max(ToMM(s.x),ToMM(s.y))/2))

done=fail=0; failed=[]
for nn in sorted(netpads,key=lambda k:len(netpads[k])):
    pl=netpads[nn]
    if len(pl)<2: continue
    w=POWER.get(nn,SIGW)
    order=[pl[0]]; rest=pl[1:]
    while rest:
        lx,ly,_=order[-1]; rest.sort(key=lambda p:(p[0]-lx)**2+(p[1]-ly)**2); order.append(rest.pop(0))
    _ledger=[]; _esc.clear()
    ok=all(route_edge(order[i],order[i+1],nn,w) for i in range(len(order)-1))
    if ok:
        done+=1
    else:
        fail+=1; failed.append(nn)
        # roll back this net's copper + grid marks so it leaves no orphans
        for kind,payload in reversed(_ledger):
            if kind=="item": b.Remove(payload)
            elif kind=="via":
                try: vias.remove(payload)
                except ValueError: pass
            elif kind=="cell":
                i,j,old=payload; grid[j][i]=old
    _ledger=None

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(BOARD,b)
print(f"maze routed nets fully: {done}  partial: {fail}")
if failed: print("partial:", sorted(failed))
