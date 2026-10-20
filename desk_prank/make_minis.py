#!/usr/bin/env python3
"""Quarter-scale copies of everything on the desk, for the shrink-the-cubicle prank.

Every item is modelled at real-world size in millimetres (estimated from the
photo; see SIZES in the README) and scaled by SCALE on export, so a better tape
measure reading is a one-number change. Each STL is laid out in the
orientation it prints in on a 180 mm bed with no supports, except where the
README says otherwise.
"""
from __future__ import annotations
import argparse, math, os
import numpy as np
import manifold3d as m3
from manifold3d import Manifold as M, CrossSection as CS

SCALE = 0.25
SEG = 48
m3.set_circular_segments(SEG)
FONT = "DejaVu Sans"


# ---------------------------------------------------------------- primitives
def box(x0, x1, y0, y1, z0, z1):
    return M.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def cbox(sx, sy, sz, z0=0.0):
    """Box centred in x/y, sitting on z0."""
    return box(-sx / 2, sx / 2, -sy / 2, sy / 2, z0, z0 + sz)


def rbox(sx, sy, sz, r, z0=0.0):
    """Box with vertical edges rounded to r, centred in x/y."""
    r = min(r, sx / 2 - 0.01, sy / 2 - 0.01)
    return (CS.square([sx - 2 * r, sy - 2 * r], center=True).offset(r, m3.JoinType.Round)
            .extrude(sz).translate([0, 0, z0]))


def cyl(r, h, r2=None, z0=0.0, seg=SEG):
    return M.cylinder(h, r, r if r2 is None else r2, seg).translate([0, 0, z0])


def ell(rx, ry, rz, at=(0, 0, 0)):
    return M.sphere(1.0, SEG).scale([rx, ry, rz]).translate(list(at))


def hull(*parts):
    return M.batch_hull(list(parts))


def union(*parts):
    return M.batch_boolean(list(parts), m3.OpType.Add)


def above(part, z=0.0):
    return part.trim_by_plane([0, 0, 1], z)


def arch(radius, tube, deg=180):
    """Half torus standing in the xz plane, feet on z=0."""
    return (CS.circle(tube, 24).translate([radius, 0]).revolve(SEG, deg)
            .rotate([90, 0, 0]))


def text(s, size, height, weight="bold", family=FONT):
    """Extruded text centred on the origin, on z=0."""
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    tp = TextPath((0, 0), s, size=size, prop=FontProperties(family=family, weight=weight))
    polys = [p for p in tp.to_polygons(closed_only=True) if len(p) > 2]
    cs = CS(polys, m3.FillRule.EvenOdd)
    (x0, y0), (x1, y1) = np.array(cs.bounds()[:2]), np.array(cs.bounds()[2:])
    return cs.translate([-(x0 + x1) / 2, -(y0 + y1) / 2]).extrude(height)


# --------------------------------------------------------------- the desk top
def monitor_panel():
    """27-inch panel on its arm; prints standing up. Webcam clipped on top."""
    W, T, H = 615, 18, 365
    p = (CS.square([W - 30, H - 30], center=True).offset(15, m3.JoinType.Round)
         .extrude(T).rotate([-90, 0, 0]).translate([0, -T / 2, H / 2]))
    p = p - box(-W / 2 + 10, W / 2 - 10, -T / 2 - 1, -T / 2 + 2.5, 26, H - 10)      # glass
    p = p + rbox(320, 34, 210, 30).translate([0, T / 2, H / 2 - 105])           # back hump
    p = p - cyl(8.4, 45).rotate([-90, 0, 0]).translate([0, T / 2 - 4, 200])     # arm socket
    cam = rbox(95, 30, 28, 12).translate([0, -4, H]) + \
        cyl(7, 4).rotate([90, 0, 0]).translate([0, -19, H + 14])
    return p + cam


def monitor_arm():
    """Weighted foot, post and arm ending in the peg that the panel hangs on."""
    foot = cyl(105, 14)
    post = cyl(16, 305, z0=14)
    arm = hull(cyl(16, 30, z0=285), box(-14, 14, -150, -130, 285, 315),
               cyl(16, 1, z0=170))                         # gusset: no supports
    peg = cyl(7.5, 36).rotate([90, 0, 0]).translate([0, -128, 300])
    return foot + post + arm + peg


def keyboard():
    """Full-size 104-key board."""
    U = 19.05
    W, D = 440, 138
    body = hull(cbox(W, D, 18).translate([0, 0, 0]),
                cbox(W, 8, 26).translate([0, D / 2 - 4, 0]))
    keys = []
    x0, y0 = -W / 2 + 12, -D / 2 + 12          # front-left of the bottom row

    def key(xu, row, wu=1.0, hu=1.0):
        x = x0 + xu * U
        y = y0 + row * U
        w, d = wu * U - 2.5, hu * U - 2.5
        top = 20 + row * 1.3
        cap = hull(box(x, x + w, y, y + d, 12, 13), box(x + 2, x + w - 2, y + 2, y + d - 2, top, top + 0.5))
        keys.append(cap)

    rows = {  # row index: list of (width-in-units)
        1: [1.25, 1.25, 1.25, 6.25, 1.25, 1.25, 1.25, 1.25],
        2: [2.25] + [1] * 10 + [2.75],
        3: [1.75] + [1] * 11 + [2.25],
        4: [1.5] + [1] * 12 + [1.5],
        5: [1] * 13 + [2],
    }
    for r, widths in rows.items():
        x = 0.0
        for w in widths:
            key(x, r - 1, w)
            x += w
    for i, x in enumerate([0, 2, 3, 4, 5, 6.5, 7.5, 8.5, 9.5, 11, 12, 13, 14]):   # F row
        key(x, 5.25)
    nav = 15.25
    for c in range(3):
        key(nav + c, 3); key(nav + c, 4); key(nav + c, 5.25)
    key(nav + 1, 1); [key(nav + c, 0) for c in range(3)]                        # arrows
    pad = 18.5
    for c in range(4):
        for r in (2, 3, 4):
            if not (c == 3 and r in (2, 3)):
                key(pad + c, r)
    key(pad, 0, 2); key(pad + 2, 0); key(pad + 3, 0, 1, 2); key(pad + 3, 2, 1, 2)
    key(pad, 1); key(pad + 1, 1); key(pad + 2, 1)
    return body + union(*keys)


def mouse():
    shell = above(hull(ell(62, 33, 38, (0, -8, 0)), ell(48, 30, 30, (0, 32, 0))))
    shell = shell - box(-1.6, 1.6, -80, -10, 20, 60)                              # button split
    wheel = cyl(6.5, 5).rotate([0, 90, 0]).translate([-2.5, -24, 30])
    return shell + wheel


def desk_mat(half):
    """800 x 330 mat in two halves (a whole one is 200 mm at 1/4 - too big)."""
    mat = rbox(800, 330, 4, 18)
    keep = box(-401, 0, -200, 200, -1, 10) if half == 0 else box(0, 401, -200, 200, -1, 10)
    return mat ^ keep


def laptop():
    """14-inch laptop open at 110 degrees; the lid leans back 20 degrees, so no supports."""
    W, D = 320, 225
    base = rbox(W, D, 14, 10)
    base = base - box(-135, 135, -10, 95, 11, 20)                                # key well
    base = base - box(-50, 50, -100, -35, 12, 20)                                # trackpad
    lid = box(-W / 2, W / 2, 0, 9, 0, 222)
    lid = lid - box(-W / 2 + 12, W / 2 - 12, -1, 1.8, 14, 210)                 # screen
    lid = lid.rotate([-20, 0, 0]).translate([0, D / 2 - 9, 10])
    hinge = cyl(6, W - 40).rotate([0, 90, 0]).translate([-(W - 40) / 2, D / 2 - 6, 12])
    return base + lid + hinge


def sanitizer():
    """1 L pump bottle - print it in clear PETG for the full effect."""
    body = hull(rbox(96, 62, 160, 24), cyl(22, 4, z0=196))
    collar = cyl(21, 22, z0=198)
    stem = cyl(6.5, 26, z0=220)
    head = hull(cyl(15, 18, z0=244), box(-9, 9, -62, -50, 247, 260))
    nozzle = cyl(4, 14).rotate([90, 0, 0]).translate([0, -58, 250])
    label = box(-44, 44, -32, -30.5, 35, 140)
    return body - label + collar + stem + head + nozzle


def screen_box():
    """The black box with the little green screen and the aerial."""
    b = rbox(232, 168, 44, 10)
    b = b - box(-20, 90, -60, 40, 41, 50)                                       # screen
    b = b + box(-17, 87, -57, 37, 39, 42.5)
    b = b - box(-100, 60, -85, -82, 6, 14)                                      # front strip
    knuckle = cyl(9, 26, z0=10).translate([-104, 70, 0])
    aerial = cyl(5, 150, 3.5, z0=36).translate([-104, 70, 0])
    return b + knuckle + aerial


def _mesh_wall(part, axis_x, x, y0, y1, z0, z1, hole=11, pitch=17):
    """Punch a square grid of holes through a wall normal to x (or y)."""
    holes = []
    for yy in np.arange(y0, y1 - hole, pitch):
        for zz in np.arange(z0, z1 - hole, pitch):
            if axis_x:
                holes.append(box(x - 20, x + 20, yy, yy + hole, zz, zz + hole))
            else:
                holes.append(box(yy, yy + hole, x - 20, x + 20, zz, zz + hole))
    return part - union(*holes) if holes else part


def organizer_tray():
    """Mesh letter tray (the sorter stacks on top of it)."""
    W, D, H, t = 310, 240, 64, 6
    tray = cbox(W, D, H) - box(-W / 2 + t, W / 2 - t, -D / 2 + t, D / 2 - t, t, H + 1)
    tray = tray - box(-80, 80, -D / 2 - 1, -D / 2 + t + 1, 30, H + 1)           # finger notch
    for sx in (-1, 1):
        tray = _mesh_wall(tray, True, sx * (W / 2 - t / 2), -D / 2 + 18, D / 2 - 14, 14, H - 6)
    tray = _mesh_wall(tray, False, -D / 2 + t / 2, -W / 2 + 16, -86, 10, H - 6)
    tray = _mesh_wall(tray, False, -D / 2 + t / 2, 88, W / 2 - 14, 10, H - 6)
    return tray


def organizer_sorter():
    """Three-step mesh file sorter."""
    W, D, t = 310, 160, 6
    steps = [(-D / 2, 100), (-D / 2 + D / 3, 145), (-D / 2 + 2 * D / 3, 190)]
    side = hull(*[box(-W / 2, W / 2, y, y + D / 3, 0, h) for y, h in steps])
    s = side - box(-W / 2 + t, W / 2 - t, -D / 2 + t, D / 2 - t, t, 400)
    for y, h in steps:
        s = s + box(-W / 2, W / 2, y, y + t, 0, h)
    s = s + box(-W / 2, W / 2, D / 2 - t, D / 2, 0, 190)
    for sx in (-1, 1):
        s = _mesh_wall(s, True, sx * (W / 2 - t / 2), -D / 2 + 12, D / 2 - 12, 14, 180)
    s = _mesh_wall(s, False, D / 2 - t / 2, -W / 2 + 14, W / 2 - 14, 14, 180)
    return s


def pen_cup():
    cup = cyl(38, 100) - cyl(32, 100, z0=6)
    holes = [box(-6, 6, -60, 60, z, z + 11).rotate([0, 0, a]) for a in range(0, 180, 30)
             for z in (18, 40, 62)]
    cup = cup - union(*holes)
    pens = [cyl(4.5, 140, z0=6).rotate([dx * 0.6, dy * 0.6, 0]).translate([dx * 1.4, dy * 1.4, 0])
            for dx, dy in ((-10, 4), (8, 8), (2, -11))]
    return cup + (union(*pens) ^ cyl(36, 200))


def notebook():
    """Spiral notebook, closed."""
    nb = rbox(280, 215, 12, 6) - box(-128, 140, -100, 100, 11, 13)
    for y in np.arange(-96, 100, 12):
        coil = cyl(7, 3).rotate([90, 0, 0]).translate([-138, y + 1.5, 6])
        nb = nb + above(coil)
    return nb


def legal_pad():
    """The yellow pad, with its glued header strip."""
    return cbox(216, 356, 10) + box(-108, 108, 146, 178, 0, 13)


def pen():
    """A pen lying down - hex barrel prints flat."""
    barrel = CS.circle(5.5, 6).extrude(140).rotate([0, 90, 0]).rotate([30, 0, 0])
    barrel = barrel.translate([-70, 0, 4.8])
    clip = box(-60, -20, -1.6, 1.6, 8, 11.5)
    tip = M.cylinder(14, 5, 1, 6).rotate([0, 90, 0]).rotate([30, 0, 0]).translate([70, 0, 4.8])
    return above(barrel + clip + tip)


def tumbler():
    """30 oz insulated tumbler with slider lid."""
    cup = cyl(36, 196, 50)
    lid = cyl(50, 16, 48, z0=196) - box(-12, 12, -48, -20, 208, 220)
    return cup + lid


def sticky_pad():
    return cbox(76, 76, 14) + cbox(76, 76, 1).rotate([0, 0, 4]).translate([1, 1, 14])


def power_brick():
    brick = rbox(120, 64, 32, 8)
    cord = cyl(4, 40).rotate([0, 90, 0]).translate([60, 0, 16])
    return above(brick + cord)


# --------------------------------------------------------------------- walls
def mets_towel():
    """Rally towel. Print orange, swap to blue/black at 1.0 mm for the letters."""
    t = rbox(381, 457, 4, 8)
    t = t + text("LET'S GO", 82, 2.4).translate([0, 110, 4])
    t = t + text("METS", 118, 2.4).translate([0, -20, 4])
    t = t + text("NY", 60, 2.4).translate([-110, -160, 4])
    return t


def license_plate(top="Florida", reg="LWA M93", bottom="SUNSHINE STATE"):
    """Novelty plate - edit the strings to match the real one."""
    p = rbox(305, 152, 4, 10)
    rim = rbox(305, 152, 2.4, 10, z0=4) - rbox(289, 136, 3, 6, z0=3.9)
    p = p + rim
    p = p + text(reg, 62, 2.4).translate([0, -2, 4])
    p = p + text(top, 20, 2.0, weight="normal").translate([0, 54, 4])
    p = p + text(bottom, 15, 2.0).translate([0, -55, 4])
    for x in (-80, 80):
        for y in (50, -50):
            p = p - cyl(4, 20, z0=-5).translate([x, y, 0])
    return p


def diploma():
    """Framed diploma, face up; it leans on the wall. Glue a 1/4 photo of the real
    one into the 0.75 mm pocket."""
    f = rbox(420, 340, 20, 3)
    f = f - box(-175, 175, -135, 135, 12, 21)                                   # matte
    f = f - box(-150, 150, -112, 112, 9, 13)                                    # paper pocket
    return f


def desk_frame():
    """Standing 5x7 frame next to the monitor - prints upright."""
    f = box(-75, 75, 0, 16, 0, 205)
    f = f - box(-60, 60, -1, 3, 22, 190)
    leg = hull(box(-30, 30, 16, 20, 0, 140), box(-30, 30, 16, 80, 0, 10))
    return f + leg


def photo_tile(w, h):
    """Flat photo/card for the cubicle wall; glue the 1/4 print into the pocket."""
    t = cbox(w, h, 5)
    return t - cbox(w - 10, h - 10, 3, z0=3)


def bobblehead():
    base = rbox(76, 76, 18, 8)
    legs = cyl(10, 55, 8, z0=18).translate([-12, 0, 0]) + cyl(10, 55, 8, z0=18).translate([12, 0, 0])
    body = hull(ell(30, 20, 18, (0, 0, 75)), ell(24, 18, 22, (0, 0, 108)))
    neck = cyl(8, 18, z0=124)
    head = ell(38, 36, 40, (0, 0, 168))
    helmet = above(ell(40, 38, 42, (0, 0, 172)), 172) + \
        (above(ell(30, 42, 6, (0, -18, 172)), 172) ^ box(-40, 40, -60, 0, 160, 180))
    bat = cyl(4, 40, z0=0) + cyl(4, 80, 7.5, z0=40)
    bat = bat.rotate([0, -20, 0]).translate([30, -8, 80])
    hands = ell(9, 9, 9, (30, -8, 86))
    return base + legs + body + neck + head + helmet + bat + hands


def hutch():
    """The open cube shelf on the desk. Exported lying on its back: no bridges."""
    W, D, H, t = 380, 300, 380, 18
    c = cbox(W, D, H) - box(-W / 2 + t, W / 2 - t, -D / 2 - 1, D / 2 - t, t, H - t)
    c = c + box(-W / 2, W / 2, -D / 2, D / 2, H / 2 - t / 2, H / 2 + t / 2)
    return c


# ------------------------------------------------------------- bags and things
def baseball_cap():
    crown = above(ell(96, 106, 100, (0, 10, 0)))
    button = ell(10, 10, 6, (0, 10, 99))
    brim = (CS.circle(1, SEG).scale([92, 78]).extrude(6).translate([0, -95, 0])
            - ell(96, 106, 100, (0, 10, 0)))
    seams = union(*[box(-1.2, 1.2, -120, 120, 0, 120).rotate([0, 0, a]) for a in (0, 60, 120)])
    crown = crown - (seams - ell(93, 103, 97, (0, 10, 0)))
    return crown + button + brim


def duffel():
    L, Wd, H, r = 560, 280, 290, 95
    pts = [ell(r, r, r, (sx * (L / 2 - r), sy * (Wd / 2 - r), z))
           for sx in (-1, 1) for sy in (-1, 1) for z in (r, H - r)]
    bag = hull(*pts, cbox(L - 120, Wd - 60, 2))
    bag = bag - box(-200, 200, -3, 3, H - 8, H + 5)                              # zip
    for x in (-110, 110):
        bag = bag + box(x - 22, x + 22, -Wd / 2 - 1, -Wd / 2 + 6, 20, 230)        # strap tabs
    handle = arch(70, 11) + arch(70, 11).translate([0, 0, 0])
    bag = bag + handle.translate([0, -22, H - 20]) + handle.translate([0, 22, H - 20])
    return above(bag)


def backpack():
    W, D, H, r = 300, 170, 450, 60
    pts = [ell(r, r, r, (sx * (W / 2 - r), sy * (D / 2 - r), z))
           for sx in (-1, 1) for sy in (-1, 1) for z in (r, H - r)]
    body = hull(*pts, cbox(W - 80, D - 40, 2))
    pocket = hull(*[ell(40, 40, 40, (sx * 85, -D / 2 + 5, z)) for sx in (-1, 1) for z in (60, 200)])
    straps = union(*[box(x - 25, x + 25, D / 2 - 4, D / 2 + 12, 60, 400) for x in (-70, 70)])
    loop = arch(32, 7).translate([0, 0, H - 8])
    zip_ = box(-120, 120, -2, 2, H - 4, H + 2).rotate([0, 0, 0])
    return above(body + pocket + straps + loop - zip_)


def sneaker(left=False):
    sole = hull(cyl(44, 30).translate([0, -98, 0]), cyl(52, 30).translate([5, 60, 0]),
                cyl(38, 30).translate([2, 108, 0]))
    upper = hull(ell(44, 48, 90, (0, -88, 28)), ell(50, 70, 66, (2, 10, 28)),
                 ell(42, 50, 38, (3, 95, 28)))
    upper = above(upper, 25)
    collar = ell(34, 52, 40, (0, -62, 120))
    tongue = hull(ell(26, 30, 10, (0, -25, 92)), ell(22, 20, 8, (1, 40, 70)))
    laces = union(*[box(-22, 22, y - 3, y + 3, 0, 200) ^ above(hull(ell(46, 72, 69, (2, 10, 28))), 0)
                    for y in (-10, 10, 30)])
    shoe = sole + upper - collar + tongue
    shoe = shoe - (box(-80, 80, -160, 150, 28, 31) - sole.scale([0.97, 0.97, 2]))  # sole line
    s = shoe + (laces - upper.scale([0.995, 0.995, 0.995]))
    return s.mirror([1, 0, 0]) if left else s


def book(w, d, t):
    b = cbox(w, d, t)
    b = b - box(-w / 2 + 6, w / 2 + 1, -d / 2 - 1, d / 2 + 1, 3, t - 3)
    return b + box(-w / 2 + 6, w / 2 - 4, -d / 2 + 4, d / 2 - 4, 3, t - 3)


def book_stack():
    return union(book(240, 170, 32),
                 book(228, 160, 26).rotate([0, 0, 7]).translate([4, 2, 32]),
                 book(200, 140, 36).rotate([0, 0, -5]).translate([-6, 0, 58]))


def boxed_set():
    """The blue box on the shelf."""
    b = rbox(240, 120, 130, 4)
    return b - box(-110, 110, -61, -58, 20, 110)


def tshirt_stack():
    """The folded white shirt on the desk."""
    s = rbox(300, 230, 22, 18) + rbox(296, 226, 22, 18, z0=22)
    s = s - box(-160, 160, -1.5, 1.5, 40, 50)                                   # fold
    collar = above(ell(55, 34, 10, (0, 95, 44)), 44) - ell(42, 24, 12, (0, 95, 44))
    return s + collar


# --------------------------------------------------------------------- chair
def chair_base():
    """Five-star base; exported upside down so the legs print flat on the bed."""
    TOP = 110
    hub = cyl(45, 50, z0=TOP - 50)
    parts = [hub]
    for i in range(5):
        a = math.radians(i * 72)
        c, s = math.cos(a), math.sin(a)
        leg = hull(box(20, 40, -26, 26, TOP - 40, TOP), box(290, 312, -20, 20, TOP - 26, TOP))
        wheel = (cyl(29, 24).rotate([90, 0, 0]).translate([0, 12, 30]) +
                 box(-22, 22, -16, 16, 40, TOP - 20))
        parts += [leg.rotate([0, 0, i * 72]), wheel.translate([300, 0, 0]).rotate([0, 0, i * 72])]
    base = union(*parts) - cyl(13, 45, z0=TOP - 44)
    return base


def chair_column():
    """Gas lift with the tilt mechanism on top; pegs at both ends."""
    return union(cyl(12, 40, z0=-40), cyl(25, 220), cyl(14, 120, z0=220),
                 cyl(14, 50, 70, z0=300), box(-75, 75, -70, 70, 350, 368), cyl(12, 34, z0=368))


def chair_seat():
    """Seat and back in one piece; seat underside flat on the bed."""
    seat = hull(rbox(490, 470, 40, 70), rbox(470, 450, 70, 60))
    seat = seat - above(ell(200, 190, 30, (0, -10, 82)), 0)                    # dish
    back = (CS.square([440 - 120, 540 - 120], center=True).offset(60, m3.JoinType.Round)
            .extrude(30).rotate([-90, 0, 0]).translate([0, 0, 290]))
    back = back.rotate([-8, 0, 0]).translate([0, 225, 40])
    spine = hull(box(-70, 70, 190, 240, 0, 60), box(-50, 50, 236, 266, 200, 260))
    sock = cyl(13, 36, z0=-1)
    return seat + back + spine - sock


# --------------------------------------------------------------------- export
ITEMS = {
    # name: (builder, print rotation, preview colour)
    "monitor_panel": (monitor_panel, None, (0.15, 0.15, 0.17)),
    "monitor_arm": (monitor_arm, None, (0.55, 0.56, 0.58)),
    "keyboard": (keyboard, None, (0.12, 0.12, 0.13)),
    "mouse": (mouse, None, (0.12, 0.12, 0.13)),
    "desk_mat_left": (lambda: desk_mat(0), None, (0.08, 0.10, 0.18)),
    "desk_mat_right": (lambda: desk_mat(1), None, (0.08, 0.10, 0.18)),
    "laptop": (laptop, None, (0.18, 0.18, 0.2)),
    "screen_box": (screen_box, None, (0.1, 0.1, 0.1)),
    "power_brick": (power_brick, None, (0.1, 0.1, 0.1)),
    "hand_sanitizer": (sanitizer, None, (0.78, 0.86, 0.80)),
    "tumbler": (tumbler, None, (0.55, 0.55, 0.55)),
    "organizer_tray": (organizer_tray, None, (0.15, 0.15, 0.15)),
    "organizer_sorter": (organizer_sorter, None, (0.15, 0.15, 0.15)),
    "pen_cup": (pen_cup, None, (0.15, 0.15, 0.15)),
    "spiral_notebook": (notebook, None, (0.2, 0.2, 0.22)),
    "legal_pad": (legal_pad, None, (0.95, 0.80, 0.25)),
    "pen": (pen, None, (0.15, 0.25, 0.6)),
    "sticky_pad": (sticky_pad, None, (0.98, 0.9, 0.35)),
    "mets_towel": (mets_towel, None, (0.98, 0.45, 0.08)),
    "license_plate": (license_plate, None, (0.92, 0.92, 0.9)),
    "diploma_frame": (diploma, None, (0.12, 0.1, 0.1)),
    "desk_photo_frame": (desk_frame, None, (0.85, 0.85, 0.82)),
    "photo_4x6": (lambda: photo_tile(152, 102), None, (0.8, 0.8, 0.8)),
    "baseball_card": (lambda: photo_tile(64, 89), None, (0.8, 0.8, 0.8)),
    "poster_8x10": (lambda: photo_tile(203, 254), None, (0.8, 0.8, 0.8)),
    "bobblehead": (bobblehead, None, (0.85, 0.75, 0.6)),
    "hutch_shelf": (hutch, [-90, 0, 0], (0.85, 0.85, 0.85)),
    "book_stack": (book_stack, None, (0.6, 0.35, 0.25)),
    "boxed_set": (boxed_set, None, (0.15, 0.3, 0.7)),
    "tshirt_stack": (tshirt_stack, None, (0.95, 0.95, 0.95)),
    "baseball_cap": (baseball_cap, None, (0.1, 0.1, 0.15)),
    "duffel_bag": (duffel, None, (0.08, 0.08, 0.08)),
    "backpack": (backpack, None, (0.1, 0.1, 0.1)),
    "sneaker_left": (lambda: sneaker(True), None, (0.92, 0.92, 0.9)),
    "sneaker_right": (sneaker, None, (0.92, 0.92, 0.9)),
    "chair_base": (chair_base, [180, 0, 0], (0.2, 0.2, 0.2)),
    "chair_column": (chair_column, None, (0.25, 0.25, 0.25)),
    "chair_seat": (chair_seat, None, (0.35, 0.36, 0.38)),
}

BED = 180.0


def to_print(part, rot, scale=SCALE):
    p = part.scale([scale] * 3)
    if rot:
        p = p.rotate(rot)
    (x0, y0, z0, x1, y1, z1) = p.bounding_box()
    return p.translate([-(x0 + x1) / 2, -(y0 + y1) / 2, -z0])


def to_trimesh(part):
    import trimesh
    mesh = part.to_mesh()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts),
                           process=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "stl"))
    ap.add_argument("--scale", type=float, default=SCALE)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    print(f"{'part':20s} {'x':>7s} {'y':>7s} {'z':>7s}  (mm, printed)")
    bad = []
    for name, (fn, rot, _) in ITEMS.items():
        if args.only and name not in args.only:
            continue
        p = to_print(fn(), rot, args.scale)
        x0, y0, z0, x1, y1, z1 = p.bounding_box()
        size = (x1 - x0, y1 - y0, z1 - z0)
        flag = "" if max(size) <= BED else "  <-- bigger than the bed"
        if flag:
            bad.append(name)
        assert p.status() == m3.Error.NoError and len(p.decompose()) == 1, name
        print(f"{name:20s} {size[0]:7.1f} {size[1]:7.1f} {size[2]:7.1f}{flag}")
        to_trimesh(p).export(os.path.join(args.out, f"{name}.stl"))
    if bad:
        raise SystemExit(f"too big for a {BED:.0f} mm bed: {bad}")


if __name__ == "__main__":
    main()
