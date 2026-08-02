#!/usr/bin/env python3
"""A true 264 mm loot-crate cube for manga, printed in 12 parts.

The cube is 264 mm on every side, so no piece of it fits the A1 mini's
180 x 180 x 180 mm plate whole. It is split on all three axes into eight
octants, plus four spline keys.

The exterior copies crate C from the reference art: light corner posts and a
deep top cap band standing at the envelope, field panels recessed between them
carrying a latch plate, a louver recess and small label placards.

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
SIDE = 264.0                  # the cube, every axis

# --- shell ---
WALL = 12.0
FLOOR = 34.0
CEIL = 36.0

# --- bevels ---
EDGE_CH = 18.0                # loot-box soft bevel: big and even
CORNER_CH = 40.0

# --- the media ---
# The cube is solid but for the slots: one book-shaped pocket per volume,
# opening on the front face, so a volume slides in like a book into a slipcase.
BOOK_DEPTH = 127.0
BOOK_HEIGHT = 190.5
BOOK_THICK = 20.0
N_BOOKS = 10                  # pressed together, no dividers
SLOT_W = N_BOOKS * BOOK_THICK + 2.0
SLOT_D = 124.0                # 3 mm shallower than the book, so it stands proud
SLOT_H = BOOK_HEIGHT + 3.5
SLOT_LEAD = 2.0               # chamfered lead-in at the slot mouth

# --- hidden lightening chambers ---
# Behind the slot backs, invisible from outside, split by a solid rib at the
# tier plane so the cap dovetails have material to bite into. Without these the
# cube is about 8 litres of infill.
VOID_X = 112.0
VOID_Y = (-118.0, -22.0)
VOID_RIB = 26.0               # height of the solid rib left at the seam
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
# The post arm is capped by the pocket only on the faces the pocket opens
# through. The side faces have no such limit, so the posts go much deeper there
# and read like the reference's castings.
POST_FRONT = 31.0             # arm on the +/-Y faces, capped by the pocket
POST_SIDE = 46.0              # arm on the +/-X faces, free
COVER_T = 3.0                 # corner posts are separate slide-on covers, so
COVER_FIT = 0.25              # they can be printed in the contrast colour
SEAM_W = 6.0                  # strap sitting on each split
SEAM_Z = 176.0                # the tier split, at two thirds height: this is
                              # the lid line, which is what a loot box reads by
# Crate C from the reference: light corner posts and a deep top cap band
# standing at the envelope, yellow field panels recessed between them, a latch
# plate on the centre of each face, and small label placards.
BASE_H = 26.0                 # foot band
# The whole cap tier is the light lid, so the tier split and the colour split
# are the same line and the field panels live entirely in the base tier.
PANEL_R = 18.0                # rounded panel corners
BEVEL_STEP = 2.0
BOLT_R = 3.4
PLATE = (84.0, 26.0)          # raised latch plate on the centre of a face
PLATE_Z = 132.0
VENT = (120.0, 16.0)          # wide shallow louver recess low on the panel
VENT_Z = 58.0
VENT_D = 2.5
PLACARD = (34.0, 16.0)        # small label plate
PLACARD_Z = 162.0
PLACARD_U = 52.0
PLACARD_D = 1.4

# --- tier lock: cap octants slide into blind dovetail channels ---
TRAVEL = 8.0
DT_D = 6.0
DT_TOP_W = 4.0
DT_BOT_W = 8.0
TEN_L = 18.0
DT_X = 122.0                   # channels ride the solid side margins
TEN_AT = (-100.0, -56.0, 48.0, 92.0)   # two per cap octant; none spans a seam
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
SLOT_BACK = HX - SLOT_D       # y where the slot stops
BLOCK = SLOT_W / 2            # half-width of the pocket
MARGIN = HX - BLOCK           # solid margin either side


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

def post_arm(axis):
    """How far the corner post reaches in across this face."""
    return POST_SIDE if axis == 0 else POST_FRONT


def seam_ribs() -> Manifold:
    """A strap standing on each split, on every face.

    Wide cover straps once chopped every face into four tiles and made the cube
    read as eight boxes; these are narrow and stand at the envelope, so they
    cover the butt joint while the panel behind them runs the full face. The
    horizontal one sits at the lid line.

    A groove will not do the job: the faces are already stepped back further
    than the groove is deep, so it would cut nothing on the frame and a buried
    slot inside the panels.
    """
    g = box(-SEAM_W / 2, SEAM_W / 2, -BIG, BIG, -BIG, BIG)
    g += box(-BIG, BIG, -SEAM_W / 2, SEAM_W / 2, -BIG, BIG)
    g += box(-BIG, BIG, -BIG, BIG, zc(SEAM_Z) - SEAM_W / 2,
             zc(SEAM_Z) + SEAM_W / 2)
    return g


def bolt_heads() -> Manifold:
    """Bolt heads on the corner castings, left standing at the envelope."""
    out = None
    for axis in (0, 1):
        for sign in (1, -1):
            arm = post_arm(axis)
            for u in (HX - arm / 2, -(HX - arm / 2)):
                for h in (BASE_H / 2, 96.0, SEAM_Z - 20.0,
                          SEAM_Z + (SIDE - SEAM_Z) / 2):
                    c = Manifold.cylinder(60.0, BOLT_R, BOLT_R, 24, True)
                    c = (c.rotate([0, 90, 0]).translate([sign * HX, u, zc(h)])
                         if axis == 0 else
                         c.rotate([90, 0, 0]).translate([u, sign * HY, zc(h)]))
                    out = c if out is None else out + c
    return out


def _face(axis, sign, u0, u1, z0, z1):
    """A region on one face: `u0`..`u1` across it, `z0`..`z1` up it."""
    if axis == 0:
        return box(sign * (HX - RELIEF_VENT - 2), sign * BIG, u0, u1,
                   zc(z0), zc(z1))
    return box(u0, u1, sign * (HY - RELIEF_VENT - 2), sign * BIG,
               zc(z0), zc(z1))


def rounded(axis, sign, u0, u1, z0, z1, r, grow=0.0):
    """A rounded-corner panel region on one face.

    Loot boxes use radiused panels, not chamfered ones - swapping the octagon
    for a stadium shape is most of what softens the crate into a loot box.
    """
    a0, a1, b0, b1 = u0 - grow, u1 + grow, z0 - grow, z1 + grow
    cyls = []
    for uu in (a0 + r, a1 - r):
        for zz in (b0 + r, b1 - r):
            c = Manifold.cylinder(BIG, r, r, 48, True)
            c = (c.rotate([0, 90, 0]).translate([0, uu, zc(zz)]) if axis == 0
                 else c.rotate([90, 0, 0]).translate([uu, 0, zc(zz)]))
            cyls.append(c)
    return Manifold.batch_hull(cyls) ^ _face(axis, sign, a0, a1, b0, b1)


def face_panel(axis, sign, grow=0.0):
    """The recessed field panel: everything the posts and bands do not cover.

    It stops at the tier split, because the whole cap tier is the light lid.
    """
    u = HX - post_arm(axis)
    return rounded(axis, sign, -u, u, BASE_H, SEAM_Z, PANEL_R, grow)


def plate(axis, sign):
    """The raised latch plate on the centre of a face."""
    w, h = PLATE
    return rounded(axis, sign, -w / 2, w / 2, PLATE_Z - h / 2, PLATE_Z + h / 2, 8.0)


def vent(axis, sign):
    """A wide, shallow louver recess low on the field panel."""
    w, h = VENT
    return rounded(axis, sign, -w / 2, w / 2, VENT_Z - h / 2, VENT_Z + h / 2, 6.0)


def placard(axis, sign):
    """Two small label plates, as on the reference crate."""
    w, h = PLACARD
    out = None
    for u in (PLACARD_U, -PLACARD_U):
        r = rounded(axis, sign, u - w / 2, u + w / 2,
                    PLACARD_Z - h / 2, PLACARD_Z + h / 2, 4.0)
        out = r if out is None else out + r
    return out


def post_region(sx, sy, shrink=0.0):
    """The L-shaped corner post: what neither face panel reaches.

    Each arm is confined to the face it belongs to. Taking the two half-spaces
    unrestricted instead sweeps the middle of the opposite face into the post,
    which is field, not casting.
    """
    # Wide enough to reach past the edge chamfer. The chamfer truncates the
    # corner, so a band only as deep as the cover leaves the two arms meeting
    # nowhere and the cover comes out as two loose pieces.
    d = EDGE_CH + COVER_T + 2.0
    arm_y = box(sx * (HX - POST_FRONT + shrink), sx * BIG,
                sy * (HY - d), sy * BIG, -BIG, BIG)       # on the +/-Y face
    arm_x = box(sx * (HX - d), sx * BIG,
                sy * (HY - POST_SIDE + shrink), sy * BIG, -BIG, BIG)
    return arm_y + arm_x


def post_cover(sx, sy, part=True):
    """The slide-on cover for one corner post, or the rebate that receives it.

    A tier-based colour split cannot reach the posts - they run the full
    height. Making them separate covers can. Each drops down over its rebated
    corner and is then trapped by the cap landing on top of it, so it needs no
    glue, like everything else here.
    """
    if part:
        return (skin(0.0, COVER_T) ^ post_region(sx, sy, shrink=COVER_FIT)
                ^ box(-BIG, BIG, -BIG, BIG,
                      zc(BASE_H + COVER_FIT), zc(SEAM_Z)))
    return (skin(0.0, COVER_T + 0.2) ^ post_region(sx, sy)
            ^ box(-BIG, BIG, -BIG, BIG, zc(BASE_H), zc(SEAM_Z)))


# --------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------

def build_assembly() -> Manifold:
    solid = profile()

    # step the vertical faces back, sparing only the bolt heads
    spared = bolt_heads() + seam_ribs()

    # everything steps back to the frame plane except the bolt heads and the
    # latch plates, which stay at the envelope like the reference crate's
    faces = ((0, 1), (0, -1), (1, -1))
    plates = None
    for axis, sign in faces:
        pl = plate(axis, sign)
        plates = pl if plates is None else plates + pl
    solid -= skin_side(0.0, RELIEF_FRAME) - spared - plates

    # the field panel: bevel lip, then floor. What it does not reach becomes
    # the corner posts, the foot band and the deep top cap.
    bevels = fields = None
    for axis, sign in faces:
        b = face_panel(axis, sign, grow=BEVEL_STEP)
        f = face_panel(axis, sign)
        bevels = b if bevels is None else bevels + b
        fields = f if fields is None else fields + f
    solid -= (skin_side(RELIEF_FRAME, RELIEF_BEVEL) ^ bevels) - spared - plates
    solid -= (skin_side(RELIEF_BEVEL, RELIEF_FIELD) ^ fields) - spared - plates

    # louver recess low on each panel, label plates high on it
    for axis, sign in faces:
        solid -= ((vent(axis, sign) ^ face_panel(axis, sign))
                  ^ skin_side(RELIEF_FIELD, RELIEF_FIELD + VENT_D))
        solid -= ((placard(axis, sign) ^ face_panel(axis, sign))
                  ^ skin_side(RELIEF_FIELD, RELIEF_FIELD + PLACARD_D))

    # crown grooves, narrow enough to bridge when a cap octant prints crown-down
    crown = (box(-66, 66, -66, 66, zc(SIDE - 6), BIG)
             - box(-58, 58, -58, 58, zc(SIDE - 6), BIG))
    for y in (-28, 0, 28):
        crown += box(-54, 54, y - 4, y + 4, zc(SIDE - 6), BIG)
    solid -= crown ^ skin(0.0, 2.5)

    # --- the book pocket: one wide slot, volumes pressed together ---
    # No dividers: the books are their own spacers, and a divider would put a
    # line on the front face for every volume.
    slot = box(-SLOT_W / 2, SLOT_W / 2, SLOT_BACK, HX - SLOT_LEAD,
               FLOOR_Z, CEIL_Z)
    slot += Manifold.batch_hull([
        box(-SLOT_W / 2, SLOT_W / 2, HX - SLOT_LEAD, HX - SLOT_LEAD + 0.01,
            FLOOR_Z, CEIL_Z),
        box(-SLOT_W / 2 - SLOT_LEAD, SLOT_W / 2 + SLOT_LEAD,
            HX + 1 - 0.01, HX + 1, FLOOR_Z - SLOT_LEAD, CEIL_Z + SLOT_LEAD),
    ])
    solid -= slot

    # --- hidden chambers behind the slots, with a solid rib at the seam ---
    # Gabled top and bottom: a flat-roofed chamber is 5000 mm^2 of ceiling with
    # nothing under it, and it is buried, so support could never be removed.
    # A 45 degree roof prints itself, in either part's orientation.
    sz = zc(SEAM_Z)
    for z0, z1, gable_top in ((FLOOR_Z + 14, sz - VOID_RIB / 2, True),
                              (sz + VOID_RIB / 2, CEIL_Z - 14, False)):
        y0, y1 = VOID_Y
        height = z1 - z0
        # A 45 degree gable can only close over a span of twice its own rise.
        # The upper chamber is short and deep, so it gets split into strips
        # narrow enough to roof themselves; one wide chamber would overrun its
        # own height and leave a flat roof with nothing under it.
        strips = max(1, int(np.ceil((y1 - y0) / (2 * 0.85 * height))))
        width = (y1 - y0) / strips
        g = width / 2 * 1.15

        for i in range(strips):
            a = y0 + i * width
            b = a + width
            ym = (a + b) / 2

            def full(lo, hi, a=a, b=b):
                return box(-VOID_X, VOID_X, a, b, lo, hi)

            def ridge(lo, hi, ym=ym):
                return box(-VOID_X, VOID_X, ym - 0.01, ym + 0.01, lo, hi)

            if gable_top:
                cav = full(z0, z1 - g) + Manifold.batch_hull(
                    [full(z1 - g, z1 - g + 0.01), ridge(z1 - 0.01, z1)])
            else:
                cav = Manifold.batch_hull(
                    [ridge(z0, z0 + 0.01),
                     full(z0 + g - 0.01, z0 + g)]) + full(z0 + g, z1)
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
    lo0, lo1 = -HZ + KEY_END, zc(SEAM_Z) - KEY_END
    band = (SLOT_BACK + VOID_Y[1]) / 2       # solid strip behind the pocket
    return [
        (0, band, lo0, lo1),               # behind the pocket, ahead of the void
        (0, -(HY - WALL / 2), lo0, lo1),   # back wall
        (1, 110.0, lo0, lo1),              # +X margin, clear of the channels
        (1, -110.0, lo0, lo1),             # -X margin
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
                            DT_TOP_W + 2 * FIT, DT_BOT_W + 2 * FIT,
                            zc(SEAM_Z) - DT_D, zc(SEAM_Z) + 0.01)
            po = box(x - DT_BOT_W / 2 - FIT, x + DT_BOT_W / 2 + FIT,
                     c + TRAVEL - TEN_L / 2 - 0.4, c + TRAVEL + TEN_L / 2 + 0.4,
                     zc(SEAM_Z) - DT_D, zc(SEAM_Z) + 0.01)
            t = dovetail_y(x, c - TEN_L / 2, c + TEN_L / 2,
                           DT_TOP_W, DT_BOT_W, zc(SEAM_Z) - DT_D, zc(SEAM_Z))
            t += box(x - DT_TOP_W / 2, x + DT_TOP_W / 2,
                     c - TEN_L / 2, c + TEN_L / 2,
                     zc(SEAM_Z) - 0.5, zc(SEAM_Z) + 1.5)
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

    sz = zc(SEAM_Z)
    lower = solid ^ box(-BIG, BIG, -BIG, BIG, -BIG, sz)
    upper = solid ^ box(-BIG, BIG, -BIG, BIG, sz, BIG)
    lower -= body_cut + grooves
    for sx, sy in itertools.product((1, -1), repeat=2):
        lower -= post_cover(sx, sy, part=False)
    upper += tenons

    for sx, sy in itertools.product((1, -1), repeat=2):
        quad = box(0 if sx > 0 else -BIG, BIG if sx > 0 else 0,
                   0 if sy > 0 else -BIG, BIG if sy > 0 else 0, -BIG, BIG)
        nx = "R" if sx > 0 else "L"
        ny = "F" if sy > 0 else "B"
        parts[f"base_{ny}{nx}"] = cleanup(lower ^ quad, f"base_{ny}{nx}")
        parts[f"cap_{ny}{nx}"] = cleanup(upper ^ quad, f"cap_{ny}{nx}")
        parts[f"post_{ny}{nx}"] = cleanup(post_cover(sx, sy),
                                         f"post_{ny}{nx}")

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
    print(f"\ntotal {total/1000:.0f} cm^3 solid across {len(split_parts())} parts")


if __name__ == "__main__":
    main()
