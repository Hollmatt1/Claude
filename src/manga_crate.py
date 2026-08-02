#!/usr/bin/env python3
"""Two-part sci-fi cargo crate for manga, sized for the Bambu Lab A1 mini.

A 178 x 178 x 205 mm industrial crate: corner castings, banded rails, X-braced
recessed panels, heavy latch blocks and a front viewing hatch. Prints as two
parts that lock with a short-travel sliding dovetail.

    body : 178 x 178 x 178 mm   (the plate's absolute maximum)
    lid  : 178 x 178 x  27 mm

Why two parts and why this shape: a Viz shonen volume is 190.5 mm tall and the
A1 mini tops out at 180 mm Z, so no single piece can enclose one standing up.
Splitting buys height, not width - each part still has to fit the 180 mm plate,
so the assembled crate is a cube-proportioned body with a lid rather than a
true cube.

Why the dovetail travel is short: the lid descends over spines that stand
19.5 mm above the body, so a full-length slide would drive the lid's walls
through the books. The lid drops on 10 mm forward, then slides home.

    python3 src/manga_crate.py --out stl

Requires: numpy, manifold3d, trimesh
"""

from __future__ import annotations

import argparse
import itertools
import os

import numpy as np
import trimesh
from manifold3d import Manifold

# --------------------------------------------------------------------------
# PARAMETERS (mm)
# --------------------------------------------------------------------------

# --- printer ---
BUILD = 180.0
MARGIN = 1.0

# --- overall ---
SIDE = BUILD - 2 * MARGIN     # 178 footprint
TOTAL_H = 205.0               # assembled height
SPLIT = 178.0                 # height of the body/lid seam == max printable Z

# --- shell ---
WALL = 10.0                   # must exceed the deepest relief with margin
FLOOR = 7.0
LID_TOP = 5.0                 # thickness of the lid's ceiling
RIM_W = 13.0                  # thickened wall at the top, carries the dovetail
RIM_BOT = 150.0               # height where the wall thickens
TAPER_H = 8.0                 # 45 deg funnel from cavity up into the rim

# --- bevels ---
EDGE_CH = 10.0
CORNER_CH = 22.0

# --- the media ---
BOOK_DEPTH = 127.0
BOOK_HEIGHT = 190.5
BOOK_THICK = 20.0
RAIL_GAP = 128.0              # floor rail channel: book depth + 1
RAIL_H = 8.0
RAIL_W = 4.0

# --- sliding dovetail lock ---
TRAVEL = 8.0                  # drop the lid this far forward, slide it back
DT_D = 6.0                    # dovetail depth
DT_TOP_W = 4.5                # width at the mouth
DT_BOT_W = 9.0                # width at the root (the undercut)
DT_X = 81.5                   # centreline; groove must stay inside the rim
TEN_L = 18.0                  # length of each tenon
TEN_AT = (-42.0, 0.0, 42.0)   # tenon centres, locked
FIT = 0.20                    # clearance, per side
SEAM_GAP = 0.2                # gap at the horizontal seam

# --- exterior detailing ---
POST_L = 26.0                 # corner casting, along each face
LATCH_W = 34.0
LATCH_Z = (162.0, 194.0)
PANEL_Z = (20.0, 166.0)       # main field panel
PANEL2_Z = (190.0, 200.0)     # short field strip breaking up the lid band
# Relief is cut *into* the 178 mm envelope rather than added onto a smaller
# body, so no detail can ever push the part past the build plate. Latch blocks
# sit at the envelope; everything else steps back from it.
RELIEF_FRAME = 2.0     # corner castings, rails, bolt heads
RELIEF_BEVEL = 3.2     # first step of the panel edge, reads as a machined lip
RELIEF_FIELD = 5.0     # floor of the recessed panels
RELIEF_VENT = 7.0      # louver slots, sunk below the panel floor
BRACE_W = 10.0
PANEL_CHAMFER = 22.0   # corner cut on the panels -> octagonal, not rectangular
BEVEL_STEP = 1.6       # how far the bevel lip stands outside the panel
VENT_N = 5             # louvers per bank
VENT_H = 5.0
VENT_PITCH = 9.0
BOLT_R = 3.2           # bolt heads on the corner castings
BOLT_Z = (28.0, 74.0, 120.0, 158.0)
STRIPE_W = 6.0         # hazard striping in the lid band
STRIPE_PITCH = 15.0
PLINTH = 2.5                  # base shadow groove depth
PLINTH_RIM = 14.0             # inset from the edge to the groove
PLINTH_W = 6.0                # groove width, narrow enough to bridge
CROWN_D = 2.5                 # depth of the crown grooves

# --- front hatch ---
WIN_W = 116.0
WIN_Z = (42.0, 140.0)
WIN_FLARE = 5.0
PLACARD = (62.0, 20.0)        # recessed label plate above the hatch
PLACARD_Z = 154.0
PLACARD_D = 1.2

HX = HY = SIDE / 2.0
HZ = TOTAL_H / 2.0
BIG = 900.0


def zc(height: float) -> float:
    """Height above the base -> centred z."""
    return height - HZ


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def box(xmin, xmax, ymin, ymax, zmin, zmax) -> Manifold:
    """Axis-aligned box. Bounds are sorted, so passing a face's outward
    direction (e.g. -86 .. -900) yields the box rather than a negative-size
    cube, whose error state would otherwise propagate through every later
    boolean and silently empty the model."""
    xmin, xmax = sorted((xmin, xmax))
    ymin, ymax = sorted((ymin, ymax))
    zmin, zmax = sorted((zmin, zmax))
    return Manifold.cube([xmax - xmin, ymax - ymin, zmax - zmin], True).translate(
        [(xmax + xmin) / 2, (ymax + ymin) / 2, (zmax + zmin) / 2])


def keep_below(solid: Manifold, normal, offset) -> Manifold:
    n = np.asarray(normal, dtype=float)
    n = n / np.linalg.norm(n)
    return solid.trim_by_plane((-n).tolist(), -float(offset))


def bevel_planes(inset: float):
    """12 edge + 8 corner planes for the box, each pulled in by `inset`."""
    h = (HX, HY, HZ)
    for i, j in ((0, 1), (1, 2), (0, 2)):
        for si, sj in itertools.product((1, -1), repeat=2):
            n = np.zeros(3)
            n[i], n[j] = si, sj
            yield n, (h[i] + h[j] - EDGE_CH) / np.sqrt(2.0) - inset
    for signs in itertools.product((1, -1), repeat=3):
        yield (np.array(signs, dtype=float),
               (HX + HY + HZ - CORNER_CH) / np.sqrt(3.0) - inset)


def profile(inset: float = 0.0) -> Manifold:
    """The bevelled outer solid, offset uniformly by `inset`.

    Negative values grow it, which is how raised detail keeps the bevelled
    silhouette instead of poking through it as a square lump.
    """
    solid = Manifold.cube([2 * (HX - inset), 2 * (HY - inset),
                           2 * (HZ - inset)], True)
    for n, d in bevel_planes(inset):
        solid = keep_below(solid, n, d)
    return solid


def skin(outer: float, inner: float) -> Manifold:
    """A constant-thickness layer of the outer surface, `outer`..`inner` deep.

    Wraps every face, ends included - use it only for detail on the crown or
    the base.
    """
    return profile(outer) - profile(inner)


def skin_side(outer: float, inner: float) -> Manifold:
    """The same layer, but on the vertical faces only.

    profile() insets in Z as well, so skin() carries a full-width slab at the
    top and bottom of the solid. Cutting with those slabs shaves the crown and
    base - and clipping them off in Z instead lands a cut plane exactly on the
    inset profile's end face, whose coincident surfaces detach the end slabs
    into separate bodies. Stacking shifted copies of the core removes the end
    slabs from the skin outright, so neither happens.
    """
    core = profile(inner)
    # Far enough that each shifted copy presents its full-width middle at the
    # real end faces, but not so far that a gap opens between the copies.
    reach = 2.0 * max(EDGE_CH, CORNER_CH)
    return profile(outer) - (core + core.translate([0, 0, reach])
                             + core.translate([0, 0, -reach]))


def band(z0: float, z1: float) -> Manifold:
    return box(-BIG, BIG, -BIG, BIG, zc(z0), zc(z1))


def dovetail(x_centre, y0, y1, top_w, bot_w, z_bot, z_top) -> Manifold:
    """Trapezoid prism, narrow at the top - the undercut that does the locking."""
    eps = 0.01
    return Manifold.batch_hull([
        box(x_centre - bot_w / 2, x_centre + bot_w / 2, y0, y1,
            zc(z_bot), zc(z_bot + eps)),
        box(x_centre - top_w / 2, x_centre + top_w / 2, y0, y1,
            zc(z_top - eps), zc(z_top)),
    ])


# --------------------------------------------------------------------------
# exterior
#
# All relief is CUT from the 178 mm envelope. The corner castings and the
# horizontal rails are simply the areas the field panels do not reach, so no
# amount of detailing can push a part past the build plate.
# --------------------------------------------------------------------------

def latch_blocks() -> Manifold:
    """The four clamp blocks. These sit at the full envelope."""
    z0, z1 = LATCH_Z
    out = None
    for axis in (0, 1):
        for sign in (1, -1):
            if axis == 0:
                r = box(sign * (HX - 20), sign * BIG,
                        -LATCH_W / 2, LATCH_W / 2, zc(z0), zc(z1))
            else:
                r = box(-LATCH_W / 2, LATCH_W / 2,
                        sign * (HY - 20), sign * BIG, zc(z0), zc(z1))
            out = r if out is None else out + r
    return out


def bolt_heads() -> Manifold:
    """Bolt heads down the corner castings, left standing at the envelope."""
    out = None
    for axis in (0, 1):
        for sign in (1, -1):
            for u in (HX - POST_L / 2, -(HX - POST_L / 2)):
                for h in BOLT_Z:
                    c = Manifold.cylinder(40.0, BOLT_R, BOLT_R, 24, True)
                    if axis == 0:
                        c = c.rotate([0, 90, 0]).translate(
                            [sign * HX, u, zc(h)])
                    else:
                        c = c.rotate([90, 0, 0]).translate(
                            [u, sign * HY, zc(h)])
                    out = c if out is None else out + c
    return out


def _face_box(axis, sign, u0, u1, z0, z1):
    """A region on one face, spanning `u0`..`u1` across it and `z0`..`z1` up."""
    if axis == 0:
        return box(sign * (HX - RELIEF_VENT - 2), sign * BIG,
                   u0, u1, zc(z0), zc(z1))
    return box(u0, u1, sign * (HY - RELIEF_VENT - 2), sign * BIG,
               zc(z0), zc(z1))


def _diamond(axis, z_mid, reach):
    """|u| + |z - z_mid| <= reach, in the plane of the given face."""
    s = reach * np.sqrt(2.0)
    if axis == 0:
        d = Manifold.cube([BIG, s, s], True).rotate([45, 0, 0])
    else:
        d = Manifold.cube([s, BIG, s], True).rotate([0, 45, 0])
    return d.translate([0, 0, z_mid])


def panel(axis, sign, u_half, z0, z1, grow=0.0):
    """An octagonal panel region: rectangle with its corners cut back."""
    a = u_half + grow
    b = (z1 - z0) / 2 + grow
    z_mid = zc((z0 + z1) / 2)
    rect = _face_box(axis, sign, -a, a, z0 - grow, z1 + grow)
    return rect ^ _diamond(axis, z_mid, a + b - PANEL_CHAMFER)


def diagonal_ribs(axis, sign, u_half, z0, z1):
    """Hazard striping: parallel 45 degree ribs across a band."""
    h = z1 - z0
    out = None
    u = -u_half - h
    while u < u_half + h:
        ends = [_face_box(axis, sign, uu - STRIPE_W / 2, uu + STRIPE_W / 2,
                          zz - STRIPE_W / 2, zz + STRIPE_W / 2)
                for uu, zz in ((u, z0), (u + h, z1))]
        rib = Manifold.batch_hull(ends)
        out = rib if out is None else out + rib
        u += STRIPE_PITCH
    return out


def field_regions() -> tuple[Manifold, Manifold, Manifold, Manifold]:
    """Panel bevels, panel floors, louver slots, and the detail left standing."""
    u = HX - POST_L
    bevels = fields = vents = keeps = None

    def add(acc, r):
        return r if acc is None else acc + r

    for axis, sign in ((0, 1), (0, -1), (1, -1), (1, 1)):
        z0, z1 = PANEL_Z
        bevels = add(bevels, panel(axis, sign, u, z0, z1, grow=BEVEL_STEP))
        fields = add(fields, panel(axis, sign, u, z0, z1))

        b0, b1 = PANEL2_Z
        bevels = add(bevels, panel(axis, sign, u, b0, b1, grow=BEVEL_STEP))
        band = panel(axis, sign, u, b0, b1)
        fields = add(fields, band)
        keeps = add(keeps, diagonal_ribs(axis, sign, u, b0, b1) ^ band)

        pan = panel(axis, sign, u, z0, z1)
        if (axis, sign) == (1, 1):
            # the front carries the hatch; vent it below the opening instead
            base = WIN_Z[0] - 4 - VENT_N * VENT_PITCH
        else:
            base = z0 + 12
            for (ua, za), (ub, zb) in ([(-u, z0 + 40), (u, z1)],
                                       [(-u, z1), (u, z0 + 40)]):
                ends = [_face_box(axis, sign, uu - BRACE_W / 2, uu + BRACE_W / 2,
                                  zz - BRACE_W / 2, zz + BRACE_W / 2)
                        for uu, zz in ((ua, za), (ub, zb))]
                keeps = add(keeps, Manifold.batch_hull(ends) ^ pan)

        for i in range(VENT_N):
            zv = base + i * VENT_PITCH
            slot = _face_box(axis, sign, -u + 14, u - 14, zv, zv + VENT_H) ^ pan
            vents = add(vents, slot)

    return bevels, fields, vents, keeps


# --------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------

def build_assembly() -> Manifold:
    solid = profile()

    # step the vertical faces back, sparing the latch blocks and bolt heads
    solid -= skin_side(0.0, RELIEF_FRAME) - (latch_blocks() + bolt_heads())

    # panels: a shallow bevel lip, then the panel floor, then the louvers,
    # with braces and hazard striping left standing at the frame plane
    bevels, fields, vents, keeps = field_regions()
    solid -= (skin_side(RELIEF_FRAME, RELIEF_BEVEL) ^ bevels) - keeps
    solid -= (skin_side(RELIEF_BEVEL, RELIEF_FIELD) ^ fields) - keeps
    solid -= skin_side(RELIEF_FIELD, RELIEF_VENT) ^ vents

    # label placard, recessed into the front panel
    solid -= (box(-PLACARD[0] / 2, PLACARD[0] / 2, HY - 8, BIG,
                  zc(PLACARD_Z - PLACARD[1] / 2), zc(PLACARD_Z + PLACARD[1] / 2))
              ^ skin_side(RELIEF_FIELD, RELIEF_FIELD + PLACARD_D))

    # crown of the lid: an outline groove and grip slots rather than one broad
    # pocket. The lid prints crown-down, so a wide recess here would be an
    # unsupported ceiling over the plate; narrow grooves bridge instead.
    top = zc(TOTAL_H - 6)
    crown = (box(-55, 55, -55, 55, top, BIG) - box(-48, 48, -48, 48, top, BIG))
    for y in (-20, 0, 20):
        crown += box(-45, 45, y - 4, y + 4, top, BIG)
    solid -= crown ^ skin(0.0, CROWN_D)

    # base shadow line: a perimeter groove, not a full-area recess, which would
    # leave the floor bridging ~150 mm on the layers above it
    r0, r1 = HX - PLINTH_RIM, HX - PLINTH_RIM - PLINTH_W
    solid -= (box(-r0, r0, -r0, r0, zc(-1), zc(PLINTH))
              - box(-r1, r1, -r1, r1, zc(-1), zc(PLINTH)))

    # --- cavity ---
    cav = HX - WALL
    rim = HX - RIM_W
    lower = box(-cav, cav, -cav, cav, zc(FLOOR), zc(RIM_BOT))
    for n, d in bevel_planes(WALL):
        if abs(n[2]) < 1e-9:
            lower = keep_below(lower, n, d)
    funnel = Manifold.batch_hull([
        box(-cav, cav, -cav, cav, zc(RIM_BOT), zc(RIM_BOT + 0.01)),
        box(-rim, rim, -rim, rim, zc(RIM_BOT + TAPER_H - 0.01),
            zc(RIM_BOT + TAPER_H)),
    ])
    upper = box(-rim, rim, -rim, rim, zc(RIM_BOT + TAPER_H),
                zc(TOTAL_H - LID_TOP))
    solid -= lower + funnel + upper

    # --- front hatch, flared in Z so its head bridges itself ---
    wz0, wz1 = WIN_Z
    flare = WALL * 1.25
    mouth = Manifold.batch_hull([
        box(-WIN_W / 2, WIN_W / 2, cav, cav + 0.01, zc(wz0), zc(wz1)),
        box(-WIN_W / 2, WIN_W / 2, HX - 0.01, HX,
            zc(wz0 - flare), zc(wz1 + flare)),
    ])
    throat = box(-WIN_W / 2, WIN_W / 2, cav - WALL, cav, zc(wz0), zc(wz1))
    solid -= mouth + throat

    # --- floor rails keeping the stack centred ---
    for s_ in (1, -1):
        y0, y1 = sorted((s_ * RAIL_GAP / 2, s_ * (RAIL_GAP / 2 + RAIL_W)))
        solid += box(-cav, cav, y0, y1, zc(FLOOR - 1), zc(FLOOR + RAIL_H))

    return solid


def split_parts(assembly: Manifold) -> tuple[Manifold, Manifold]:
    body = assembly ^ box(-BIG, BIG, -BIG, BIG, -BIG, zc(SPLIT))
    lid = assembly ^ box(-BIG, BIG, -BIG, BIG, zc(SPLIT + SEAM_GAP), BIG)

    # dovetail: undercut channel in the body's shoulder, with a drop-in pocket
    # at the forward end of each tenon's travel.
    for sx in (1, -1):
        x = sx * DT_X
        channel = dovetail(x, -55.0, 65.0, DT_TOP_W + 2 * FIT,
                           DT_BOT_W + 2 * FIT, SPLIT - DT_D, SPLIT + 0.01)
        pockets = None
        for c in TEN_AT:
            # spans exactly where the tenon lands when dropped in, so it can
            # descend clear of the undercut before sliding home
            p = box(x - DT_BOT_W / 2 - FIT, x + DT_BOT_W / 2 + FIT,
                    c + TRAVEL - TEN_L / 2 - 0.4, c + TRAVEL + TEN_L / 2 + 0.4,
                    zc(SPLIT - DT_D), zc(SPLIT + 0.01))
            pockets = p if pockets is None else pockets + p
        body -= channel + pockets

        for c in TEN_AT:
            y0, y1 = c - TEN_L / 2, c + TEN_L / 2
            lid += dovetail(x, y0, y1, DT_TOP_W, DT_BOT_W,
                            SPLIT - DT_D + SEAM_GAP, SPLIT + SEAM_GAP)
            # stub reaching up into the lid: without the overlap the tenon only
            # touches the underside and stays a separate body
            lid += box(x - DT_TOP_W / 2, x + DT_TOP_W / 2, y0, y1,
                       zc(SPLIT + SEAM_GAP - 0.5), zc(SPLIT + SEAM_GAP + 1.5))

    return cleanup(body, "body"), cleanup(lid, "lid")


def cleanup(part: Manifold, name: str) -> Manifold:
    """Drop degenerate shells left behind by coincident-surface booleans.

    Where a cut lands exactly on an existing edge - a hazard rib ending on a
    panel's chamfer, a bevel meeting the corner castings - the boolean can
    leave hairline shells of nearly zero, or even negative, volume. They are
    not printable geometry and they upset slicers, so keep the real body; but
    refuse to discard anything big enough to be an actual feature.
    """
    comps = sorted(part.decompose(), key=lambda m: m.volume(), reverse=True)
    if len(comps) <= 1:
        return part
    debris = sum(abs(c.volume()) for c in comps[1:])
    if debris > 100.0:
        raise SystemExit(f"{name}: {debris:.1f} mm^3 in {len(comps)-1} extra "
                         f"bodies - too big to be boolean debris, investigate")
    return comps[0]


def to_trimesh(solid: Manifold) -> trimesh.Trimesh:
    mesh = solid.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3],
                           faces=np.asarray(mesh.tri_verts), process=False)


def print_ready(body: Manifold, lid: Manifold) -> tuple[Manifold, Manifold]:
    """Drop each part onto z=0. The lid prints inverted, crown to the plate."""
    body = body.translate([0, 0, -body.bounding_box()[2]])
    lid = lid.rotate([180, 0, 0])
    return body, lid.translate([0, 0, -lid.bounding_box()[2]])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="stl")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    body, lid = split_parts(build_assembly())
    for name, part in zip(("body", "lid"), print_ready(body, lid)):
        mesh = to_trimesh(part)
        path = os.path.join(args.out, f"manga_crate_{name}.stl")
        mesh.export(path)
        bb = part.bounding_box()
        print(f"{path}: {bb[3]-bb[0]:.1f} x {bb[4]-bb[1]:.1f} x {bb[5]-bb[2]:.1f}"
              f" mm, {part.volume()/1000:.0f} cm^3, watertight={mesh.is_watertight}")


if __name__ == "__main__":
    main()
