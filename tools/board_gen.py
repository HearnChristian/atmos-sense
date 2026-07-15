"""Generate Atmos.kicad_pcb from the netlist + floorplan (docs/PCB-PLAN.md).

Adapted from the radar toolchain's board_gen. Text-built 4-layer FR4 board
(SIG / GND / 3V3+VBAT pours / SIG), all parts embedded with pad nets bound
from the netlist, ICs/connectors at floorplan coordinates, passives
auto-clustered around their owner ICs. No routing — placement starting point.

Board grown from the ratified 65x50 to 74x56: the measured part footprints
(WROOM 18x25.5, microSD 16x18, coin holder 24x18, LoRa 18.5x16.5) do not fit
all-top-side on 65x50. Flag for Christian; revisit outline when a box is chosen.
"""
import re, os, math, uuid

D   = "/home/christian-thomas-hearn/Desktop/Atmos"
STD = "/snap/kicad/current/usr/share/kicad/footprints"
NET = D + "/_Atmos_fresh.net"
OUT = D + "/Atmos.kicad_pcb"

OX, OY = 40.0, 40.0          # page origin of board's top-left corner
BW, BH = 74.0, 56.0          # board size, mm

def nuid(): return str(uuid.uuid4())

# ---------- parse netlist ----------
ntxt = open(NET).read()
comps = {}
for ref, body in re.findall(r'\(comp \(ref "([^"]+)"\)(.*?)(?=\(comp \(ref|\(libparts)', ntxt, re.S):
    fp  = re.search(r'\(footprint "([^"]+)"\)', body)
    val = re.search(r'\(value "([^"]*)"\)', body)
    ts  = re.search(r'\(tstamps? "([^"]+)"\)', body)
    if not fp: continue
    comps[ref] = {"fp": fp.group(1), "value": val.group(1) if val else "",
                  "ts": (ts.group(1).split()[0] if ts else nuid())}

netcode = {}
padnet  = {}
names   = []
for name, body in re.findall(r'\(net \(code "\d+"\) \(name "([^"]+)"\)(.*?)(?=\(net \(code|\Z)', ntxt, re.S):
    if name not in netcode:
        netcode[name] = len(netcode) + 1; names.append(name)
    for r, p in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', body):
        padnet[(r, p)] = (netcode[name], name)

# ---------- fixed placement (board-local mm origin coords, from PCB-PLAN) ----------
FIXED = {
 "U1":(14.0,15.0,0),      # ESP32-S3-WROOM-1, top-left, antenna to top edge
 "U3":(34.0,10.0,0),      # DS3231 RTC, top-center (I2C)
 "U13":(44.0,10.0,0),     # SGP40 VOC, top-center (I2C, off switchers)
 "U7":(57.0,12.0,0),      # RFM95W LoRa, top-right
 "J2":(71.0, 6.0,0),      # BME280 breakout header, right edge top
 "J6":(68.5,25.0,0),      # SMA (LoRa antenna), right edge
 "J1":(71.0,31.5,0),      # AS3935 breakout header, right edge (tall)
 "SW1":(10.0,31.0,0),"SW2":(18.0,31.0,0),  # EN / IO0 buttons below MCU
 "BT1":(35.6,25.0,0),     # CR2032 coin holder, under DS3231 (RTC backup)
 "U12":(51.0,25.0,0),"U9":(56.0,25.0,0),"U5":(61.0,25.0,0),   # power cluster
 "U2":(51.0,30.0,0),"U10":(56.0,30.0,0),"U11":(61.0,30.0,0),
 "D4":(65.0,36.0,0),"L1":(52.0,36.0,0),"L2":(59.0,36.0,0),
 "U8":(13.0,35.0,0),      # USB ESD, below MCU on USB path
 "J4":(13.0,46.0,0),      # microSD, bottom-left
 "J3":(27.0,50.0,0),      # USB-C, bottom edge
 "U4":(42.0,50.0,0),      # PMS5003 PicoBlade, bottom
 "BT2":(54.0,48.0,0),     # Li-ion JST-PH, bottom
 "J5":(63.0,50.0,0),      # solar in JST-XH, bottom-right
}
ICS = set(FIXED)

# rail -> owner IC for rail-only passives (bypass/bulk caps land near supply)
POWER_HINT = {
 "+3V3": "U2", "+5V": "U9", "+5V_PMS": "U10", "+VBATT": "U12",
 "VSOL": "U5", "VIN_CHG": "U12", "VBUS": "U8", "VBUS_USB": "U8",
}

# ---------- owner assignment for passives ----------
net_members = {}
for (r, p), (c, n) in padnet.items():
    net_members.setdefault(n, []).append((r, p))
def owner(ref):
    score = {}; rails = []
    for (r, p), (c, n) in padnet.items():
        if r != ref: continue
        mem = net_members[n]
        if n == "GND" or n.startswith("unconnected"): continue
        if len(mem) > 6:
            rails.append(n); continue
        for r2, _ in mem:
            if r2 != ref and r2 in ICS:
                score[r2] = score.get(r2, 0) + 1
    if score:
        return max(score, key=lambda k: (score[k], -int(re.sub(r'\D','',k) or 0)))
    for n in rails:
        if n in POWER_HINT: return POWER_HINT[n]
    return "U1"

# ---------- footprint bbox (courtyard preferred, else pads) ----------
def _fp_bbox(path):
    t = open(path).read()
    xs, ys = [], []
    for m in re.finditer(r'\(pad\s+"[^"]*"[^(]*\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+[-\d.]+)?\)\s*\(size\s+([-\d.]+)\s+([-\d.]+)\)', t):
        x, y, sx, sy = map(float, m.groups())
        xs += [x-sx/2, x+sx/2]; ys += [y-sy/2, y+sy/2]
    cxs, cys, dxs, dys = [], [], [], []
    for blk in re.finditer(r'\(fp_(?:line|rect|poly|circle|arc)(.*?)\(layer "([^"]+)"\)', t, re.S):
        body, layer = blk.groups()
        tx, ty = (cxs, cys) if layer.endswith("CrtYd") else (dxs, dys)
        for m in re.finditer(r'\((?:start|end|xy|center)\s+([-\d.]+)\s+([-\d.]+)\)', body):
            tx.append(float(m.group(1))); ty.append(float(m.group(2)))
    xs += cxs if cxs else dxs
    ys += cys if cys else dys
    if not xs: return (-1, -1, 1, 1)
    return (min(xs), min(ys), max(xs), max(ys))

_bbcache = {}
def bbox_of(ref):
    fpid = comps[ref]["fp"]
    if fpid not in _bbcache:
        _bbcache[fpid] = _fp_bbox(fp_path(fpid))
    return _bbcache[fpid]

# WROOM antenna courtyard is huge (48x41 = antenna air); use module body for
# collision so nothing thinks the whole top-left is occupied.
def collide_bbox(ref):
    if ref == "U1":
        t = open(fp_path(comps[ref]["fp"])).read()
        xs = []; ys = []
        for blk in re.finditer(r'\(fp_(?:line|rect|poly)(.*?)\(layer "F.Fab"\)', t, re.S):
            for m in re.finditer(r'\((?:start|end|xy)\s+([-\d.]+)\s+([-\d.]+)\)', blk.group(1)):
                xs.append(float(m.group(1))); ys.append(float(m.group(2)))
        for m in re.finditer(r'\(pad\s+"[^"]*"[^(]*\(at\s+([-\d.]+)\s+([-\d.]+)', t):
            xs.append(float(m.group(1))); ys.append(float(m.group(2)))
        return (min(xs), min(ys), max(xs), max(ys))
    return bbox_of(ref)

def radius_of(ref):
    x0, y0, x1, y1 = bbox_of(ref)
    return max(math.hypot(a, b) for a in (x0, x1) for b in (y0, y1)) + 0.25

RECTS = []      # bounding rects of everything placed (fixed + passives + keepouts)

def _rot_bbox(bb, rot):
    x0, y0, x1, y1 = bb
    if rot % 360 == 90:  return (y0, -x1, y1, -x0)
    if rot % 360 == 180: return (-x1, -y1, -x0, -y0)
    if rot % 360 == 270: return (-y1, x0, -y0, x1)
    return bb

def free_rect(x, y, bb, gap=0.3):
    x0, y0, x1, y1 = x+bb[0]-gap, y+bb[1]-gap, x+bb[2]+gap, y+bb[3]+gap
    if x0 < OX+0.8 or y0 < OY+0.8 or x1 > OX+BW-0.8 or y1 > OY+BH-0.8:
        return False
    for a0, b0, a1, b1 in RECTS:
        if x0 < a1 and x1 > a0 and y0 < b1 and y1 > b0:
            return False
    return True

def slot_near(oref, ref):
    bb = bbox_of(ref)
    bx, by, _ = FIXED[oref]
    cx, cy = OX+bx, OY+by
    cands = sorted((( (i*0.55)**2 + (j*0.55)**2, cx+i*0.55, cy+j*0.55)
                    for i in range(-130, 131) for j in range(-100, 101)
                    if OX <= cx+i*0.55 <= OX+BW and OY <= cy+j*0.55 <= OY+BH))
    for gap in (0.35, 0.2, 0.1):
        for _, x, y in cands:
            if free_rect(x, y, bb, gap):
                RECTS.append((x+bb[0], y+bb[1], x+bb[2], y+bb[3]))
                return x, y
    raise RuntimeError("no slot near " + oref)

# ---------- footprint embedding ----------
def fp_path(fpid):
    lib, name = fpid.split(":", 1)
    for base in (D, STD):
        p = f"{base}/{lib}.pretty/{name}.kicad_mod"
        if os.path.exists(p): return p
    raise FileNotFoundError(fpid)

def spans(txt, opener):
    out, i = [], 0
    while True:
        i = txt.find(opener, i)
        if i < 0: break
        d, j = 0, i
        while True:
            if txt[j] == '(': d += 1
            elif txt[j] == ')':
                d -= 1
                if d == 0: break
            j += 1
        out.append((i, j+1)); i = j
    return out

def embed(ref):
    c = comps[ref]
    fpid = c["fp"]; lib, name = fpid.split(":", 1)
    t = open(fp_path(fpid)).read()
    if ref in FIXED:
        bx, by, rot = FIXED[ref]; x, y = OX+bx, OY+by
    else:
        x, y = slot_near(owner(ref), ref); rot = 0
    t = t.replace(f'(footprint "{name}"', f'(footprint "{fpid}"', 1)
    t = re.sub(r'\t\(version \d+\)\n|\t\(generator "[^"]*"\)\n|\t\(generator_version "[^"]*"\)\n', '', t)
    t = t.replace('(layer "F.Cu")',
                  f'(layer "F.Cu")\n\t(uuid "{nuid()}")\n\t(at {x:.3f} {y:.3f} {rot})\n\t(path "/{c["ts"]}")', 1)
    if rot:
        def bump(m):
            return f'(at {m.group(1)} {m.group(2)} {float(m.group(3) or 0)+rot:g})' if m.group(3) is not None \
                   else f'(at {m.group(1)} {m.group(2)} {rot})'
        body_start = t.find('(path')
        head, body = t[:body_start], t[body_start:]
        body = re.sub(r'\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)', bump, body)
        t = head + body
    t = re.sub(r'\(property "Reference" "[^"]*"', f'(property "Reference" "{ref}"', t, count=1)
    t = re.sub(r'\(property "Value" "[^"]*"', f'(property "Value" "{c["value"]}"', t, count=1)
    t = t.replace('"REF**"', f'"{ref}"')
    out, last = [], 0
    for s, e in spans(t, '(pad'):
        blk = t[s:e]
        m = re.match(r'\(pad\s+"([^"]*)"', blk)
        if m and (ref, m.group(1)) in padnet:
            code, nname = padnet[(ref, m.group(1))]
            nname = nname.replace('"', '\\"')
            blk = blk[:-1].rstrip() + f'\n\t\t(net {code} "{nname}")\n\t)'
        out.append(t[last:s]); out.append(blk); last = e
    out.append(t[last:])
    t = "".join(out)
    t = re.sub(r'\(uuid "[0-9a-f-]+"\)', lambda m: f'(uuid "{nuid()}")', t)
    return "\t" + t.replace("\n", "\n\t").rstrip("\t")

# ---------- board skeleton: 4-layer FR4 (JLC 1.6mm) ----------
def header():
    nets = '\n'.join(f'\t(net {i+1} "{n}")' for i, n in enumerate(names))
    return f'''(kicad_pcb
\t(version 20241229)
\t(generator "pcbnew")
\t(generator_version "9.0")
\t(general
\t\t(thickness 1.6)
\t\t(legacy_teardrops no)
\t)
\t(paper "A4")
\t(title_block
\t\t(title "Atmos Environmental Sensor Node")
\t\t(date "2026-07-14")
\t\t(rev "A")
\t\t(comment 1 "4-layer FR4 1.6mm: SIG / GND / 3V3+VBAT / SIG")
\t)
\t(layers
\t\t(0 "F.Cu" signal)
\t\t(1 "In1.Cu" signal "GND")
\t\t(2 "In2.Cu" signal "PWR")
\t\t(3 "B.Cu" signal)
\t\t(11 "F.Paste" user)
\t\t(13 "F.SilkS" user "F.Silkscreen")
\t\t(15 "F.Mask" user)
\t\t(10 "B.Paste" user)
\t\t(12 "B.SilkS" user "B.Silkscreen")
\t\t(14 "B.Mask" user)
\t\t(5 "Cmts.User" user "User.Comments")
\t\t(17 "Dwgs.User" user "User.Drawings")
\t\t(25 "Edge.Cuts" user)
\t\t(27 "Margin" user)
\t\t(29 "F.CrtYd" user "F.Courtyard")
\t\t(28 "B.CrtYd" user "B.Courtyard")
\t\t(31 "F.Fab" user)
\t\t(30 "B.Fab" user)
\t)
\t(setup
\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "PP-013GXtc") (epsilon_r 4.05) (loss_tangent 0.017))
\t\t\t(layer "In1.Cu" (type "copper") (thickness 0.0152))
\t\t\t(layer "dielectric 2" (type "core") (thickness 1.065) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
\t\t\t(layer "In2.Cu" (type "copper") (thickness 0.0152))
\t\t\t(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "PP-013GXtc") (epsilon_r 4.05) (loss_tangent 0.017))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t)
\t\t(pad_to_mask_clearance 0)
\t\t(allow_soldermask_bridges_in_footprints yes)
\t)
\t(net 0 "")
{nets}
'''

def edges():
    r = OX+BW; b = OY+BH
    g = []
    g.append(f'\t(gr_rect (start {OX} {OY}) (end {r} {b}) (stroke (width 0.1) (type solid)) (fill no) (layer "Edge.Cuts") (uuid "{nuid()}"))')
    # 4x M3 mounting holes, 3.5mm from corners (NPTH 3.2mm as Edge.Cuts circles)
    for mx, my in ((3.5,3.5),(BW-3.5,3.5),(3.5,BH-3.5),(BW-3.5,BH-3.5)):
        cx, cy = OX+mx, OY+my
        g.append(f'\t(gr_circle (center {cx} {cy}) (end {cx+1.6} {cy}) (stroke (width 0.1) (type solid)) (fill no) (layer "Edge.Cuts") (uuid "{nuid()}"))')
    g.append(f'\t(gr_text "Atmos  REV A" (at {OX+BW/2} {OY+BH-1.6} 0) (layer "F.SilkS") (uuid "{nuid()}") (effects (font (size 1 1) (thickness 0.15))))')
    return "\n".join(g)

# ---------- seed RECTS: FIXED courtyards + halos + antenna keepout ----------
HALO = 0.4
HALO_BIG = {"U1":0.8, "U7":0.7, "U3":0.6, "J1":0.5, "J3":0.5, "J4":0.5, "BT1":0.5}
for _r, (_x, _y, _rot) in FIXED.items():
    x0, y0, x1, y1 = _rot_bbox(collide_bbox(_r), _rot)
    h = HALO_BIG.get(_r, HALO)
    RECTS.append((OX+_x+x0-h, OY+_y+y0-h, OX+_x+x1+h, OY+_y+y1+h))
# WROOM antenna near-field keepout (right of the module, top edge): no passives
RECTS.append((OX+23.0, OY+0.0, OX+40.0, OY+9.0))

def _area(r):
    x0, y0, x1, y1 = bbox_of(r)
    return (x1 - x0) * (y1 - y0)
order = list(FIXED) + sorted([r for r in comps if r not in FIXED],
                             key=lambda r: (-_area(r), r[0], int(re.sub(r'\D','',r) or 0)))
blocks = [embed(r) for r in order]
open(OUT, "w").write(header() + "\n".join(blocks) + "\n" + edges() + "\n)\n")
print(f"wrote {OUT}: {len(blocks)} footprints, {len(names)} nets")
