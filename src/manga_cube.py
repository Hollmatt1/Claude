#!/usr/bin/env python3
"""A true 216 mm sci-fi cargo cube for manga, printed in 12 parts.

The cube is 216 mm on every side, so no piece of it fits the A1 mini's
180 x 180 x 180 mm plate whole. It is split on all three axes into eight
108 mm octants, plus four spline keys.

Why eight and not two: any 2-way split of a cube over 180 mm leaves at least
one piece carrying a full-width cross-section, and the largest square that fits
inside a 180 mm cube is only ~191 mm. Splitting all three axes is the minimum
that works, and 2 x 2 x 2 is the coarsest such split.

How it locks, with no glue and no hardware:

  lower ring   four octants butt together, then four dovetail spline keys drop
               down the vertical seams. The keys are a bowtie in section, so
               neither side can pull away from the other. Once the cap is on,
               the keys are trapped.

  cap          each upper octant locks to the body on its own: set it down
               8 mm forward, slide it back, and two dovetail tenons run into a
               blind channel that stops it exactly flush. No cap piece depends
               on its neighbours to stay put, which is what lets a closed ring
               of four be assembled at all - they cannot all slide together.

    python3 src/manga_cube.py --out stl

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

BUILD = 180.0                 # A1 mini plate
SIDE = 216.0                  # the cube, every axis

# --- shell ---
WALL = 12.0                   # must exceed RELIEF_VENT with margin
FLOOR = 12.0
CEIL = 10.0

# --- bevels ---
EDGE_CH = 12.0
CORNER_CH = 26.0

# --- the media ---
BOOK_DEPTH = 127.0
BOOK_HEIGHT = 190.5
BOOK_THICK = 20.0
BAY = 130.0                   # curb pocket on the floor -> 6 volumes
CURB_H = 10.0
CURB_W = 6.0

# --- front hatch ---
WIN_W = 126.0
WIN_Z = (46.0, 170.0)   # centred on the face; leaves a real header and sill

# --- relief planes, shallowest to deepest ---
RELIEF_FRAME = 2.5            # castings, rails, seam straps
RELIEF_BEVEL = 4.0            # panel lip
RELIEF_FIELD = 6.0            # panel floor
RELIEF_VENT = 8.5             # louvers, sunk below the panel floor

# --- exterior detailing ---
POST_L = 34.0                 # corner castings
STRAP_W = 30.0                # straps covering the vertical seams
BAND_H = 30.0                 # band covering the horizontal seam
RAIL_H = 22.0                 # rails at the base and crown
PANEL_CHAMFER = 20.0
BEVEL_STEP = 1.8
BRACE_W = 11.0
VENT_N = 4
VENT_H = 5.0
VENT_PITCH = 9.0
BOLT_R = 3.4
STRIPE_W = 6.0
STRIPE_PITCH = 15.0
PLACARD = (56.0, 18.0)
PLACARD_D = 1.2

# --- tier lock: cap octants slide into blind dovetail channels ---
TRAVEL = 8.0
DT_D = 6.0
DT_TOP_W = 4.0
DT_BOT_W = 8.0
TEN_L = 18.0
TEN_AT = (-64.0, -28.0, 28.0, 64.0)   # none on y=0: a tenon may not span parts
FIT = 0.20

# --- vertical seam splines ---
KEY_D = 6.0                   # reach each side of the seam
KEY_NARROW = 5.0              # width at the seam
KEY_WIDE = 9.0                # width at the root, the part that locks
KEY_END = 6.0                 # shortfall at each end of a key

HX = HY = HZ = SIDE / 2.0
BIG = 900.0
CAV = HX - WALL               # 96
FLOOR_Z = -HZ + FLOOR
CEIL_Z = HZ - CEIL


def zc(height: float) -> float:
    """Height above the base -> centred z."""
    return height - HZ


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def box(xmin, xmax, ymin, ymax, zmin, zmax) -> Manifold:
    """Axis-aligned box; bounds are sorted so a reversed pair still yields the
    box rather than a negative-size cube, whose error state would propagate
    through every later boolean and silently empty the model."""
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
    """12 edge + 8 corner planes, each pulled in by `inset`."""
    for i, j in ((0, 1), (1, 2), (0, 2)):
        for si, sj in itertools.product((1, -1), repeat=2):
            n = np.zeros(3)
            n[i], n[j] = si, sj
            yield n, (2 * HX - EDGE_CH) / np.sqrt(2.0) - inset
    for signs in itertools.product((1, -1), repeat=3):
        yield (np.array(signs, dtype=float),
               (3 * HX - CORNER_CH) / np.sqrt(3.0) - inset)


def profile(inset: float = 0.0) -> Manifold:
    """The bevelled cube, offset uniformly by `inset`."""
    solid = Manifold.cube([2 * (HX - inset)] * 3, True)
    for n, d in bevel_planes(inset):
        solid = keep_below(solid, n, d)
    return solid


def skin(outer: float, inner: float) -> Manifold:
    """A layer of the outer surface, every face included."""
    return profile(outer) - profile(inner)


def skin_side(outer: float, inner: float) -> Manifold:
    """The same layer on the vertical faces only.

    profile() insets in Z too, so skin() carries full-width slabs at the top
    and bottom. Cutting with those shaves the crown and base; clipping them off
    in Z instead lands a cut plane exactly on the inset profile's end face,
    whose coincident surfaces detach the end slabs into separate bodies.
    Stacking shifted copies removes the end slabs outright.
    """
    core = profile(inner)
    reach = 2.0 * max(EDGE_CH, CORNER_CH)
    return profile(outer) - (core + core.translate([0, 0, reach])
                             + core.translate([0, 0, -reach]))


def cleanup(part: Manifold, name: str) -> Manifold:
    """Drop degenerate shells left by coincident-surface booleans.

    Where a cut lands exactly on an existing edge the boolean can leave
    hairline shells of nearly zero, or even negative, volume. They upset
    slicers. Keep the real body, but refuse to discard anything big enough to
    be an actual feature.
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


def weld(mesh: trimesh.Trimesh, digits: int = 4) -> trimesh.Trimesh:
    """Collapse micro-slivers so the exported STL is watertight.

    Booleans between near-coincident surfaces - a spline groove meeting a
    panel edge - leave triangles with edges around 1e-5 mm, plus a few with a
    zero-length edge. The solid is still manifold, but a degenerate face
    duplicates an edge, so that edge is used four times and slicers see a
    mesh that is not watertight. Welding at 1e-4 mm, which is a five-hundredth
    of a layer, removes them without moving any real geometry.
    """
    mesh.merge_vertices(digits_vertex=digits)
    mesh.update_faces(mesh.area_faces > 1e-9)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices(digits_vertex=digits)
    return mesh


# --------------------------------------------------------------------------
# exterior
#
# All relief is CUT from the 216 mm envelope, so no detailing can push a piece
# past the plate. The corner castings, the rails, and the straps that hide the
# seams are simply the areas the recessed panels do not reach.
# --------------------------------------------------------------------------

def _face(axis, sign, u0, u1, z0, z1):
    """A region on one face: `u0`..`u1` across it, `z0`..`z1` up it."""
    if axis == 0:
        return box(sign * (HX - RELIEF_VENT - 2), sign * BIG, u0, u1,
                   zc(z0), zc(z1))
    return box(u0, u1, sign * (HY - RELIEF_VENT - 2), sign * BIG,
               zc(z0), zc(z1))


def _diamond(axis, z_mid, reach):
    """|u| + |z - z_mid| <= reach, in the plane of the face."""
    s = reach * np.sqrt(2.0)
    d = (Manifold.cube([BIG, s, s], True).rotate([45, 0, 0]) if axis == 0
         else Manifold.cube([s, BIG, s], True).rotate([0, 45, 0]))
    return d.translate([0, 0, z_mid])


def panel(axis, sign, u0, u1, z0, z1, grow=0.0):
    """An octagonal panel region: a rectangle with its corners cut back."""
    a0, a1 = u0 - grow, u1 + grow
    half = (a1 - a0) / 2
    b = (z1 - z0) / 2 + grow
    rect = _face(axis, sign, a0, a1, z0 - grow, z1 + grow)
    dia = _diamond(axis, zc((z0 + z1) / 2), half + b - PANEL_CHAMFER)
    off = (a0 + a1) / 2
    dia = dia.translate([0, off, 0] if axis == 0 else [off, 0, 0])
    return rect ^ dia


def straps() -> Manifold:
    """Everything held at the full envelope: seam straps, tier band, bolts.

    The vertical seams and the horizontal seam land under these, so what would
    otherwise be a visible split line reads as a strap bolted over a joint.
    """
    out = box(-STRAP_W / 2, STRAP_W / 2, -BIG, BIG, -BIG, BIG)          # x=0
    out += box(-BIG, BIG, -STRAP_W / 2, STRAP_W / 2, -BIG, BIG)         # y=0
    out += box(-BIG, BIG, -BIG, BIG, -BAND_H / 2, BAND_H / 2)           # z=0
    out += box(-BIG, BIG, -BIG, BIG, -HZ, -HZ + RAIL_H)                 # base
    out += box(-BIG, BIG, -BIG, BIG, HZ - RAIL_H, HZ)                   # crown

    for axis in (0, 1):
        for sign in (1, -1):
            for u in (HX - POST_L / 2, -(HX - POST_L / 2)):
                for h in (34.0, 92.0, 124.0, 182.0):
                    c = Manifold.cylinder(60.0, BOLT_R, BOLT_R, 24, True)
                    c = (c.rotate([0, 90, 0]).translate([sign * HX, u, zc(h)])
                         if axis == 0 else
                         c.rotate([90, 0, 0]).translate([u, sign * HY, zc(h)]))
                    out += c
    return out


def field_regions():
    """Panel bevels, panel floors, louvers, and detail left standing proud."""
    # Four panels per face: two tiers of two, in the quadrants left between the
    # base/crown rails, the seam band across the middle, the vertical seam
    # straps, and the corner castings. Heights are above the base.
    u_in, u_out = STRAP_W / 2, HX - POST_L
    z_bands = [(RAIL_H, HZ - BAND_H / 2),
               (HZ + BAND_H / 2, 2 * HZ - RAIL_H)]

    bevels = fields = vents = keeps = None

    def add(acc, r):
        return r if acc is None else acc + r

    for axis, sign in ((0, 1), (0, -1), (1, -1), (1, 1)):
        for tier, (z0, z1) in enumerate(z_bands):
            for su in (1, -1):
                a, b = (su * u_in, su * u_out)
                a, b = min(a, b), max(a, b)
                bevels = add(bevels, panel(axis, sign, a, b, z0, z1,
                                           grow=BEVEL_STEP))
                pan = panel(axis, sign, a, b, z0, z1)
                fields = add(fields, pan)

                if tier == 0:
                    # X-brace across the lower panels
                    for (ua, za), (ub, zb) in (((a, z0), (b, z1)),
                                               ((a, z1), (b, z0))):
                        ends = [_face(axis, sign, uu - BRACE_W / 2,
                                      uu + BRACE_W / 2,
                                      zz - BRACE_W / 2, zz + BRACE_W / 2)
                                for uu, zz in ((ua, za), (ub, zb))]
                        keeps = add(keeps, Manifold.batch_hull(ends) ^ pan)
                else:
                    # louver bank in the upper panels
                    base = z0 + 18
                    for i in range(VENT_N):
                        zv = base + i * VENT_PITCH
                        vents = add(vents, _face(axis, sign, a + 10, b - 10,
                                                 zv, zv + VENT_H) ^ pan)
    return bevels, fields, vents, keeps


def hazard_band():
    """45 degree striping cut into the base and crown rails."""
    out = None
    for axis, sign in itertools.product((0, 1), (1, -1)):
        for z0, z1 in ((4.0, RAIL_H - 4.0), (2 * HZ - RAIL_H + 4.0, 2 * HZ - 4.0)):
            h = z1 - z0
            u = -HX - h
            while u < HX + h:
                ends = [_face(axis, sign, uu - STRIPE_W / 2, uu + STRIPE_W / 2,
                              zz - STRIPE_W / 2, zz + STRIPE_W / 2)
                        for uu, zz in ((u, z0), (u + h, z1))]
                rib = Manifold.batch_hull(ends)
                out = rib if out is None else out + rib
                u += STRIPE_PITCH
    return out


# --------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------

def build_assembly() -> Manifold:
    solid = profile()

    keep_proud = straps()
    solid -= skin_side(0.0, RELIEF_FRAME) - keep_proud

    bevels, fields, vents, keeps = field_regions()
    solid -= (skin_side(RELIEF_FRAME, RELIEF_BEVEL) ^ bevels) - keeps
    solid -= (skin_side(RELIEF_BEVEL, RELIEF_FIELD) ^ fields) - keeps
    solid -= skin_side(RELIEF_FIELD, RELIEF_VENT) ^ vents

    # hazard striping recessed into the base and crown rails
    rails = (box(-BIG, BIG, -BIG, BIG, -HZ, -HZ + RAIL_H)
             + box(-BIG, BIG, -BIG, BIG, HZ - RAIL_H, HZ))
    solid -= (skin_side(RELIEF_FRAME, RELIEF_FIELD)
              ^ rails - hazard_band() - straps())

    # placard above the hatch
    solid -= (box(-PLACARD[0] / 2, PLACARD[0] / 2, HY - 8, BIG,
                  zc(202.0 - PLACARD[1] / 2), zc(202.0 + PLACARD[1] / 2))
              ^ skin_side(RELIEF_FRAME, RELIEF_FRAME + PLACARD_D))

    # crown grooves; narrow so they bridge when a cap octant prints crown-down
    crown = (box(-64, 64, -64, 64, zc(2 * HZ - 6), BIG)
             - box(-56, 56, -56, 56, zc(2 * HZ - 6), BIG))
    for y in (-26, 0, 26):
        crown += box(-52, 52, y - 4, y + 4, zc(2 * HZ - 6), BIG)
    solid -= crown ^ skin(0.0, 2.5)

    # --- cavity ---
    cavity = box(-CAV, CAV, -CAV, CAV, FLOOR_Z, CEIL_Z)
    for n, d in bevel_planes(WALL):
        if abs(n[2]) < 1e-9:
            cavity = keep_below(cavity, n, d)
    solid -= cavity

    # --- front hatch, flared in Z so its head bridges itself ---
    wz0, wz1 = WIN_Z
    flare = WALL * 1.25
    solid -= Manifold.batch_hull([
        box(-WIN_W / 2, WIN_W / 2, CAV, CAV + 0.01, zc(wz0), zc(wz1)),
        box(-WIN_W / 2, WIN_W / 2, HX - 0.01, HX,
            zc(wz0 - flare), zc(wz1 + flare)),
    ]) + box(-WIN_W / 2, WIN_W / 2, CAV - WALL, CAV, zc(wz0), zc(wz1))

    # --- floor curb locating the stack ---
    curb = (box(-BAY / 2 - CURB_W, BAY / 2 + CURB_W,
                -BAY / 2 - CURB_W, BAY / 2 + CURB_W,
                FLOOR_Z - 1, FLOOR_Z + CURB_H)
            - box(-BAY / 2, BAY / 2, -BAY / 2, BAY / 2,
                  FLOOR_Z - 2, FLOOR_Z + CURB_H + 1))
    solid += curb

    return solid


# --------------------------------------------------------------------------
# splitting into printable parts
# --------------------------------------------------------------------------

def dovetail_y(x_c, y0, y1, top_w, bot_w, z_bot, z_top) -> Manifold:
    """Trapezoid prism running along Y, narrow at the top - the undercut."""
    eps = 0.01
    return Manifold.batch_hull([
        box(x_c - bot_w / 2, x_c + bot_w / 2, y0, y1, z_bot, z_bot + eps),
        box(x_c - top_w / 2, x_c + top_w / 2, y0, y1, z_top - eps, z_top),
    ])


def spline(axis, u_c, z0, z1, narrow, wide, reach) -> Manifold:
    """A bowtie spline running along Z, straddling the seam at axis == 0.

    Widest at both roots and pinched at the seam, so neither piece can pull
    away sideways.
    """
    eps = 0.01
    slabs = []
    for d, w in ((-reach, wide), (0.0, narrow), (reach, wide)):
        if axis == 0:
            slabs.append(box(d - eps, d + eps, u_c - w / 2, u_c + w / 2, z0, z1))
        else:
            slabs.append(box(u_c - w / 2, u_c + w / 2, d - eps, d + eps, z0, z1))
    return (Manifold.batch_hull(slabs[:2]) + Manifold.batch_hull(slabs[1:]))


def seam_keys():
    """Where a spline runs, as (axis, u_centre, z0, z1) in centred coords.

    The x=0 seam only carries a spline where the front wall survives the hatch,
    hence the short one in the sill.
    """
    # Anchor at the base, not at FLOOR_Z: the walls are solid all the way down,
    # and starting at the floor line leaves the sill run barely 2 mm long.
    wall_c = HX - WALL / 2
    lo0, lo1 = -HZ + KEY_END, -KEY_END
    runs = [
        (0, -wall_c, lo0, lo1),                        # back wall
        (1, wall_c, lo0, lo1),                         # +X wall
        (1, -wall_c, lo0, lo1),                        # -X wall
        (0, wall_c, lo0, zc(WIN_Z[0]) - KEY_END),      # front sill
    ]
    return runs


def split_parts() -> dict[str, Manifold]:
    solid = build_assembly()
    parts: dict[str, Manifold] = {}

    # --- tier lock: blind channels in the body, tenons on the cap ---
    channels = pockets = None
    for sx in (1, -1):
        x = sx * (HX - WALL / 2)
        for c in TEN_AT:
            ch = dovetail_y(x, c - TEN_L / 2 - 0.4, c + TRAVEL + TEN_L / 2 + 0.4,
                            DT_TOP_W + 2 * FIT, DT_BOT_W + 2 * FIT,
                            -DT_D, 0.01)
            po = box(x - DT_BOT_W / 2 - FIT, x + DT_BOT_W / 2 + FIT,
                     c + TRAVEL - TEN_L / 2 - 0.4, c + TRAVEL + TEN_L / 2 + 0.4,
                     -DT_D, 0.01)
            channels = ch if channels is None else channels + ch
            pockets = po if pockets is None else pockets + po

    body_cut = channels + pockets
    tenons = None
    for sx in (1, -1):
        x = sx * (HX - WALL / 2)
        for c in TEN_AT:
            t = dovetail_y(x, c - TEN_L / 2, c + TEN_L / 2,
                           DT_TOP_W, DT_BOT_W, -DT_D, 0.0)
            t += box(x - DT_TOP_W / 2, x + DT_TOP_W / 2,
                     c - TEN_L / 2, c + TEN_L / 2, -0.5, 1.5)
            tenons = t if tenons is None else tenons + t

    # --- spline grooves ---
    grooves = None
    for axis, u_c, z0, z1 in seam_keys():
        g = spline(axis, u_c, z0, z1, KEY_NARROW + 2 * FIT,
                   KEY_WIDE + 2 * FIT, KEY_D + FIT)
        grooves = g if grooves is None else grooves + g

    lower = solid ^ box(-BIG, BIG, -BIG, BIG, -BIG, 0.0)
    upper = solid ^ box(-BIG, BIG, -BIG, BIG, 0.0, BIG)
    lower -= body_cut + grooves
    upper += tenons

    for sx, sy in itertools.product((1, -1), repeat=2):
        quad = box(0 if sx > 0 else -BIG, BIG if sx > 0 else 0,
                   0 if sy > 0 else -BIG, BIG if sy > 0 else 0, -BIG, BIG)
        nx = "R" if sx > 0 else "L"
        ny = "F" if sy > 0 else "B"
        parts[f"base_{ny}{nx}"] = cleanup(lower ^ quad, f"base_{ny}{nx}")
        parts[f"cap_{ny}{nx}"] = cleanup(upper ^ quad, f"cap_{ny}{nx}")

    for i, (axis, u_c, z0, z1) in enumerate(seam_keys(), start=1):
        parts[f"key_{i}"] = spline(axis, u_c, z0 + FIT, z1 - FIT,
                                   KEY_NARROW, KEY_WIDE, KEY_D)
    return parts


def print_ready(name: str, part: Manifold) -> Manifold:
    """Cap octants print crown-down; everything else as it sits."""
    if name.startswith("cap"):
        part = part.rotate([180, 0, 0])
    return part.translate([0, 0, -part.bounding_box()[2]])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="stl")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    total = 0.0
    for name, part in split_parts().items():
        ready = print_ready(name, part)
        mesh = weld(to_trimesh(ready))
        path = os.path.join(args.out, f"cube_{name}.stl")
        mesh.export(path)
        bb = ready.bounding_box()
        total += part.volume()
        fits = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]) <= BUILD
        print(f"{path:32s} {bb[3]-bb[0]:6.1f} x {bb[4]-bb[1]:6.1f} x "
              f"{bb[5]-bb[2]:6.1f}  {part.volume()/1000:7.1f} cm^3  "
              f"{'fits' if fits else 'TOO BIG'}"
              f"{'' if mesh.is_watertight else '  NOT WATERTIGHT'}")
    print(f"\ntotal {total/1000:.0f} cm^3 solid across 12 parts")


if __name__ == "__main__":
    main()
