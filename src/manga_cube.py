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
SIDE = 224.0                  # the cube, every axis

# --- shell ---
WALL = 12.0
FLOOR = 16.0
CEIL = 14.0

# --- bevels ---
EDGE_CH = 12.0
CORNER_CH = 26.0

# --- the media ---
# The cube is solid but for the slots: one book-shaped pocket per volume,
# opening on the front face, so a volume slides in like a book into a slipcase.
BOOK_DEPTH = 127.0
BOOK_HEIGHT = 190.5
BOOK_THICK = 20.0
N_SLOTS = 6
SLOT_W = 21.0                 # book + 1 mm
SLOT_D = 124.0                # 3 mm shallower than the book, so it stands proud
SLOT_H = BOOK_HEIGHT + 3.5
SLOT_LEAD = 2.0               # chamfered lead-in at the slot mouth
DIV = 8.0                     # divider between slots
DIV_C = 16.0                  # centre divider: the x=0 seam runs down it

# --- hidden lightening chambers ---
# Behind the slot backs, invisible from outside, split by a solid rib at the
# tier plane so the cap dovetails have material to bite into. Without these the
# cube is about 8 litres of infill.
VOID_X = 80.0
VOID_Y = (-100.0, -34.0)
VOID_RIB = 24.0               # height of the solid rib left at the seam
VOID_GABLE = 20.0             # 45 deg roof and floor, so a chamber self-supports

# --- relief planes, shallowest to deepest ---
RELIEF_FRAME = 2.5            # castings, rails, seam straps
RELIEF_BEVEL = 4.0            # panel lip
RELIEF_FIELD = 6.0            # panel floor
RELIEF_VENT = 8.5             # louvers, sunk below the panel floor

# --- exterior detailing ---
# One panel per face, spanning both seams, rather than four tiles: detail that
# runs across a joint is what makes eight parts read as one object. The seams
# themselves get a scribed panel line instead of a wide cover strap.
POST_L = 24.0                 # corner castings
SEAM_W = 7.0                  # narrow strap sitting on each split
RAIL_H = 22.0                 # rails at the base and crown
PANEL_CHAMFER = 30.0
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
DT_X = 99.0                   # channels ride the solid side margins
TEN_AT = (-84.0, -48.0, 40.0, 76.0)   # two per cap octant; none spans a seam
FIT = 0.20

# --- vertical seam splines ---
KEY_D = 5.0                   # reach each side of the seam
KEY_NARROW = 4.5              # width at the seam
KEY_WIDE = 8.0                # width at the root, the part that locks
KEY_END = 8.0                 # shortfall at each end of a key

HX = HY = HZ = SIDE / 2.0
BIG = 900.0
FLOOR_Z = -HZ + FLOOR
CEIL_Z = FLOOR_Z + SLOT_H
SLOT_BACK = HX - SLOT_D       # y where the slots stop


def slot_centres():
    """x of each slot, laid out symmetrically about the wide centre divider."""
    out, c = [], DIV_C / 2 + SLOT_W / 2
    for _ in range(N_SLOTS // 2):
        out += [c, -c]
        c += SLOT_W + DIV
    return sorted(out)


SLOT_X = slot_centres()
BLOCK = max(SLOT_X) + SLOT_W / 2      # half-width of the slot block
MARGIN = HX - BLOCK                   # solid margin either side


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


def mesh_report(mesh: trimesh.Trimesh) -> tuple[int, bool]:
    """(boundary edge count, winding consistent) - the checks that matter.

    Not `is_watertight`. Booleans on near-coincident surfaces leave the odd
    point-pinch: two cones of surface meeting at a single vertex. Manifold
    emits two vertex indices at that point, which is correct; trimesh's loader
    merges them and then reports the mesh as not watertight even though it is
    a closed, correctly-oriented surface with no hole anywhere. Counting
    boundary edges measures the thing we actually care about.

    Welding the mesh to appease that test made things worse - collapsing near
    vertices turned pinches into genuine holes - so the export stays raw.
    """
    import collections
    counts = collections.Counter(map(tuple, mesh.edges_sorted))
    return sum(1 for v in counts.values() if v == 1), bool(mesh.is_winding_consistent)


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


def seam_ribs() -> Manifold:
    """A narrow strap standing on each split, on every face.

    The joints used to hide under 30 mm cover straps, which chopped every face
    into four tiles and made the cube read as eight boxes. These are 7 mm and
    stand at the envelope, so they cover the butt joint while the panel, its
    X-brace and its louvers still run the full width of the face behind them.

    A groove will not do the job: the faces are already stepped back further
    than the groove is deep, so it would cut nothing on the frame and a buried
    slot inside the panels.
    """
    g = box(-SEAM_W / 2, SEAM_W / 2, -BIG, BIG, -BIG, BIG)
    g += box(-BIG, BIG, -SEAM_W / 2, SEAM_W / 2, -BIG, BIG)
    g += box(-BIG, BIG, -BIG, BIG, -SEAM_W / 2, SEAM_W / 2)
    return g


def bolt_heads() -> Manifold:
    """Bolt heads down the corner castings, left standing at the envelope."""
    out = None
    for axis in (0, 1):
        for sign in (1, -1):
            for u in (HX - POST_L / 2, -(HX - POST_L / 2)):
                for h in (36.0, 96.0, 128.0, 188.0):
                    c = Manifold.cylinder(60.0, BOLT_R, BOLT_R, 24, True)
                    c = (c.rotate([0, 90, 0]).translate([sign * HX, u, zc(h)])
                         if axis == 0 else
                         c.rotate([90, 0, 0]).translate([u, sign * HY, zc(h)]))
                    out = c if out is None else out + c
    return out


def face_panel(axis, sign, grow=0.0):
    """The single big octagonal panel filling one face."""
    u = HX - POST_L
    return panel(axis, sign, -u, u, RAIL_H, SIDE - RAIL_H, grow=grow)


def brace(axis, sign):
    """A full-face X, corner to corner. It crosses both seams, which is the
    point: continuous detail is what ties the eight octants together."""
    u = HX - POST_L
    z0, z1 = RAIL_H, SIDE - RAIL_H
    pan = face_panel(axis, sign)
    out = None
    for (ua, za), (ub, zb) in (((-u, z0), (u, z1)), ((-u, z1), (u, z0))):
        ends = [_face(axis, sign, uu - BRACE_W / 2, uu + BRACE_W / 2,
                      zz - BRACE_W / 2, zz + BRACE_W / 2)
                for uu, zz in ((ua, za), (ub, zb))]
        rib = Manifold.batch_hull(ends) ^ pan
        out = rib if out is None else out + rib
    return out


def louvers(axis, sign):
    """A single bank spanning the whole panel, crossing the vertical seam."""
    u = HX - POST_L - 16
    out = None
    base = SIDE / 2 - (VENT_N * VENT_PITCH) / 2
    for i in range(VENT_N):
        zv = base + i * VENT_PITCH
        sl = _face(axis, sign, -u, u, zv, zv + VENT_H) ^ face_panel(axis, sign)
        out = sl if out is None else out + sl
    return out


def hazard_band():
    """45 degree striping cut into the base and crown rails."""
    out = None
    for axis, sign in itertools.product((0, 1), (1, -1)):
        for z0, z1 in ((4.0, RAIL_H - 4.0), (SIDE - RAIL_H + 4.0, SIDE - 4.0)):
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

    # step the vertical faces back, sparing only the bolt heads
    spared = bolt_heads() + seam_ribs()
    solid -= skin_side(0.0, RELIEF_FRAME) - spared

    # one panel per face: bevel lip, then floor, with the X standing proud
    # no panel on the front: it is almost all slot, and the slot walls would
    # land tangent to the panel steps, pinching the mesh
    faces = ((0, 1), (0, -1), (1, -1))
    bevels = fields = braces = vents = None
    for axis, sign in faces:
        b = face_panel(axis, sign, grow=BEVEL_STEP)
        f = face_panel(axis, sign)
        bevels = b if bevels is None else bevels + b
        fields = f if fields is None else fields + f
        if axis == 0:                       # X on the sides
            r = brace(axis, sign)
            braces = r if braces is None else braces + r
        elif sign < 0:                      # louvers on the back
            v = louvers(axis, sign)
            vents = v if vents is None else vents + v

    solid -= (skin_side(RELIEF_FRAME, RELIEF_BEVEL) ^ bevels) - braces - spared
    solid -= (skin_side(RELIEF_BEVEL, RELIEF_FIELD) ^ fields) - braces - spared
    solid -= (skin_side(RELIEF_FIELD, RELIEF_VENT) ^ vents) - spared

    # striping in the rails, and a placard on the back
    rails = (box(-BIG, BIG, -BIG, BIG, -HZ, -HZ + RAIL_H)
             + box(-BIG, BIG, -BIG, BIG, HZ - RAIL_H, HZ))
    solid -= (skin_side(RELIEF_FRAME, RELIEF_FIELD) ^ rails
              - hazard_band() - spared)
    solid -= (box(-PLACARD[0] / 2, PLACARD[0] / 2, -BIG, -(HY - 8),
                  zc(SIDE / 2 - PLACARD[1] / 2), zc(SIDE / 2 + PLACARD[1] / 2))
              ^ skin_side(RELIEF_FIELD, RELIEF_FIELD + PLACARD_D))

    # crown grooves, narrow enough to bridge when a cap octant prints crown-down
    crown = (box(-66, 66, -66, 66, zc(SIDE - 6), BIG)
             - box(-58, 58, -58, 58, zc(SIDE - 6), BIG))
    for y in (-28, 0, 28):
        crown += box(-54, 54, y - 4, y + 4, zc(SIDE - 6), BIG)
    solid -= crown ^ skin(0.0, 2.5)

    # --- the book slots: the only voids that show ---
    # Each gets a lead-in chamfer at the mouth, so a volume starts into a tight
    # slot without catching, and so the mouth is not a sharp three-plane corner
    # for the boolean to pinch on.
    for cx in SLOT_X:
        slot = box(cx - SLOT_W / 2, cx + SLOT_W / 2,
                   SLOT_BACK, HX - SLOT_LEAD, FLOOR_Z, CEIL_Z)
        slot += Manifold.batch_hull([
            box(cx - SLOT_W / 2, cx + SLOT_W / 2, HX - SLOT_LEAD,
                HX - SLOT_LEAD + 0.01, FLOOR_Z, CEIL_Z),
            box(cx - SLOT_W / 2 - SLOT_LEAD, cx + SLOT_W / 2 + SLOT_LEAD,
                HX + 1 - 0.01, HX + 1,
                FLOOR_Z - SLOT_LEAD, CEIL_Z + SLOT_LEAD),
        ])
        solid -= slot

    # --- hidden chambers behind the slots, with a solid rib at the seam ---
    # Gabled top and bottom: a flat-roofed chamber is 5000 mm^2 of ceiling with
    # nothing under it, and it is buried, so support could never be removed.
    # A 45 degree roof prints itself, in either part's orientation.
    for z0, z1, gable_top in ((FLOOR_Z + 14, -VOID_RIB / 2, True),
                              (VOID_RIB / 2, CEIL_Z - 14, False)):
        y0, y1 = VOID_Y
        ym = (y0 + y1) / 2
        g = (y1 - y0) / 2 * 1.15      # slope clear of 45, not exactly on it

        def full(a, b):
            return box(-VOID_X, VOID_X, y0, y1, a, b)

        def ridge(a, b):
            return box(-VOID_X, VOID_X, ym - 0.01, ym + 0.01, a, b)

        # The roof slopes along the chamber's short axis - across its 66 mm
        # depth, not its 160 mm width - because only the short span can close
        # to a ridge at 45 degrees within the height available.
        if gable_top:
            cav = full(z0, z1 - g) + Manifold.batch_hull(
                [full(z1 - g, z1 - g + 0.01), ridge(z1 - 0.01, z1)])
        else:
            cav = Manifold.batch_hull(
                [ridge(z0, z0 + 0.01), full(z0 + g - 0.01, z0 + g)]) + full(z0 + g, z1)
        solid -= cav

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


def spline(axis, u_c, z0, z1, narrow, wide, reach, waist=0.75) -> Manifold:
    """A bowtie spline running along Z, straddling a seam at axis == 0.

    Widest at both roots and pinched in the middle, so neither piece can pull
    away sideways. The pinch is a parallel-sided band `2 * waist` across rather
    than a knife edge: the split plane runs right down it, and a knife edge
    there leaves 0.01 mm slivers that make the exported mesh unmergeable.
    """
    def slab(d, w, t=0.01):
        if axis == 0:
            return box(d - t, d + t, u_c - w / 2, u_c + w / 2, z0, z1)
        return box(u_c - w / 2, u_c + w / 2, d - t, d + t, z0, z1)

    mid = (box(-waist, waist, u_c - narrow / 2, u_c + narrow / 2, z0, z1)
           if axis == 0 else
           box(u_c - narrow / 2, u_c + narrow / 2, -waist, waist, z0, z1))
    return (Manifold.batch_hull([slab(-reach, wide), slab(-waist, narrow)])
            + mid
            + Manifold.batch_hull([slab(waist, narrow), slab(reach, wide)]))


def seam_keys():
    """Where a spline runs, as (axis, u_centre, z0, z1) in centred coords.

    Each must sit in material that is solid over the whole run: the centre
    divider and the back wall for the x=0 seam, the side margins for y=0.
    """
    lo0, lo1 = -HZ + KEY_END, -KEY_END
    return [
        (0, 40.0, lo0, lo1),          # centre divider, in front of the slots
        (0, -(HY - WALL / 2), lo0, lo1),   # back wall
        (1, HX - MARGIN / 2 - 6.5, lo0, lo1),    # +X margin
        (1, -(HX - MARGIN / 2 - 6.5), lo0, lo1),  # -X margin
    ]


def split_parts() -> dict[str, Manifold]:
    solid = build_assembly()
    parts: dict[str, Manifold] = {}

    # --- tier lock: blind channels in the body, tenons on the cap ---
    channels = pockets = tenons = None
    for sx in (1, -1):
        x = sx * DT_X
        for c in TEN_AT:
            ch = dovetail_y(x, c - TEN_L / 2 - 0.4, c + TRAVEL + TEN_L / 2 + 0.4,
                            DT_TOP_W + 2 * FIT, DT_BOT_W + 2 * FIT, -DT_D, 0.01)
            po = box(x - DT_BOT_W / 2 - FIT, x + DT_BOT_W / 2 + FIT,
                     c + TRAVEL - TEN_L / 2 - 0.4, c + TRAVEL + TEN_L / 2 + 0.4,
                     -DT_D, 0.01)
            t = dovetail_y(x, c - TEN_L / 2, c + TEN_L / 2,
                           DT_TOP_W, DT_BOT_W, -DT_D, 0.0)
            t += box(x - DT_TOP_W / 2, x + DT_TOP_W / 2,
                     c - TEN_L / 2, c + TEN_L / 2, -0.5, 1.5)
            channels = ch if channels is None else channels + ch
            pockets = po if pockets is None else pockets + po
            tenons = t if tenons is None else tenons + t
    body_cut = channels + pockets

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
        mesh = to_trimesh(ready)
        path = os.path.join(args.out, f"cube_{name}.stl")
        mesh.export(path)
        bb = ready.bounding_box()
        bnd, wind = mesh_report(mesh)
        total += part.volume()
        fits = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]) <= BUILD
        print(f"{path:32s} {bb[3]-bb[0]:6.1f} x {bb[4]-bb[1]:6.1f} x "
              f"{bb[5]-bb[2]:6.1f}  {part.volume()/1000:7.1f} cm^3  "
              f"{'fits' if fits else 'TOO BIG'}"
              f"{'' if bnd == 0 and wind else '  MESH PROBLEM'}")
    print(f"\ntotal {total/1000:.0f} cm^3 solid across 12 parts")


if __name__ == "__main__":
    main()
