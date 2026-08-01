#!/usr/bin/env python3
"""Parametric 'loot cube' manga shelf sized for the Bambu Lab A1 mini.

A hollow, soft-bevelled cube with a drop-in slot in the top face and a display
window in the front face. Manga volumes stand upright on the floor of the cube;
because a Viz shonen volume (190.5 mm) is taller than the A1 mini's 180 mm build
height, the spines deliberately stand proud of the top face.

Everything below is driven by the PARAMETERS block. Change a number, re-run,
get a new STL.

    python3 src/manga_loot_cube.py --out stl/

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
BUILD = 180.0          # A1 mini build volume is 180 x 180 x 180
MARGIN = 1.0           # keep-off from the very edge of the plate

# --- overall body ---
CUBE = BUILD - 2 * MARGIN   # 178 mm exterior cube
WALL = 5.0                  # side / top wall thickness
FLOOR = 5.0                 # floor thickness (carries ~1.8 kg of books)

# --- 'Overwatch soft bevel' edge treatment ---
EDGE_CHAMFER = 9.0     # trim taken off each of the 12 cube edges
CORNER_CHAMFER = 17.0  # extra trim on each of the 8 corners

# --- the media we are holding ---
BOOK_DEPTH = 127.0     # 5"   page width  -> depth into the shelf
BOOK_HEIGHT = 190.5    # 7.5" trim height -> vertical
BOOK_THICK = 20.0      # typical Viz shonen spine
BOOK_CLEAR = 6.0       # slop added around the book footprint

# --- top drop-in slot ---
# SLOT_W is capped by the top edge chamfer: the flared mouth must land inside
# the flat part of the top face, i.e. SLOT_W/2 + OPEN_FLARE <= H - EDGE_CHAMFER.
# validate() enforces this.
SLOT_W = 140.0                        # across the spines -> 7 volumes
SLOT_D = BOOK_DEPTH + BOOK_CLEAR      # 133 mm front-to-back

# --- front display window ---
WIN_W = 140.0
WIN_LIP = 30.0         # solid lip below the window, stops books sliding out
WIN_TOP = 60.0         # z of the window's top edge, measured from cube centre
OPEN_FLARE = 5.0       # 45 degree flare on opening edges (self-supporting)

# --- funnel from the cavity up to the slot ---
# Stretches the taper so its underside sits clear of 45 degrees rather than
# exactly on it; at 1.0 the hull's epsilon slabs alone tip it to 45.02 deg.
TAPER_MARGIN = 1.20

# --- floor guide rails that keep the stack centred ---
RAIL_H = 8.0
RAIL_W = 4.0

# --- recessed face panels ---
PANEL_INSET = 24.0     # border from the cube's outer edge to the panel
PANEL_DEPTH = 1.6
GROOVE_W = 3.0         # the cross that splits each panel into quadrants
GROOVE_D = 1.2

# --- 'lid' seam: the band that reads as a loot box lid ---
# Wraps the whole perimeter at constant depth, chamfers included.
SEAM_Z = 70.0          # bottom of the seam, must clear the panels
SEAM_H = 2.5
SEAM_D = 1.2

H = CUBE / 2.0
BIG = CUBE * 4.0       # oversize used for cutting tools
THROAT = 5.0           # how far an opening cutter reaches past the inner face


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def box(xmin, xmax, ymin, ymax, zmin, zmax) -> Manifold:
    """Axis-aligned box from explicit bounds."""
    size = [xmax - xmin, ymax - ymin, zmax - zmin]
    centre = [(xmax + xmin) / 2, (ymax + ymin) / 2, (zmax + zmin) / 2]
    return Manifold.cube(size, True).translate(centre)


def keep_below(solid: Manifold, normal, offset) -> Manifold:
    """Intersect `solid` with the half-space  n_hat . x <= offset.

    `offset` is a true distance from the origin (the normal is normalised
    first), which is what makes the uniform-wall inset below exact: subtracting
    WALL from every offset offsets every face inward by exactly WALL.
    """
    n = np.asarray(normal, dtype=float)
    n = n / np.linalg.norm(n)
    return solid.trim_by_plane((-n).tolist(), -float(offset))


def bevel_planes(inset: float = 0.0):
    """The 12 edge + 8 corner cutting planes, each pulled in by `inset`.

    Yields (unit_normal, offset) pairs describing  n_hat . x <= offset.
    """
    # 12 edges: one plane per (axis pair, sign pair)
    for i, j in ((0, 1), (1, 2), (0, 2)):
        for si, sj in itertools.product((1, -1), repeat=2):
            n = np.zeros(3)
            n[i], n[j] = si, sj
            offset = (2 * H - EDGE_CHAMFER) / np.sqrt(2.0)
            yield n, offset - inset
    # 8 corners
    for signs in itertools.product((1, -1), repeat=3):
        n = np.array(signs, dtype=float)
        offset = (3 * H - CORNER_CHAMFER) / np.sqrt(3.0)
        yield n, offset - inset


def flared_cutter(w, h, axis, inner, outer, flare) -> Manifold:
    """A self-supporting opening cutter.

    Cuts a `w` x `h` aperture that flares outward by `flare` as it travels from
    the `inner` face plane to the `outer` face plane along `axis`. When
    flare == wall thickness the resulting underside sits at 45 degrees, so the
    opening bridges itself and needs no support.
    """
    def slab(width, height, a, b):
        lo, hi = min(a, b), max(a, b)
        if axis == 1:   # cutting through a +/-Y face
            return box(-width / 2, width / 2, lo, hi, -height / 2, height / 2)
        return box(-width / 2, width / 2, -height / 2, height / 2, lo, hi)

    eps = 0.01
    sign = 1.0 if outer > inner else -1.0
    mouth = Manifold.batch_hull([
        slab(w, h, inner, inner + sign * eps),
        slab(w + 2 * flare, h + 2 * flare, outer - sign * eps, outer),
    ])
    # Reach a little way past the inner face so the cut lands in open cavity
    # rather than on a coincident plane. This must stay *short*: run it deeper
    # and it punches out the wall on the far side of the box.
    throat = slab(w, h, inner, inner - sign * THROAT)
    return mouth + throat


def recessed_panel(axis: int, sign: int) -> Manifold:
    """Recessed panel plus its quadrant-splitting cross, for one face."""
    face = sign * H
    span = CUBE - 2 * PANEL_INSET

    def oriented(u, v, depth_from, depth_to):
        lo, hi = sorted((depth_from, depth_to))
        rng = {
            0: lambda: box(lo, hi, -u / 2, u / 2, -v / 2, v / 2),
            1: lambda: box(-u / 2, u / 2, lo, hi, -v / 2, v / 2),
            2: lambda: box(-u / 2, u / 2, -v / 2, v / 2, lo, hi),
        }
        return rng[axis]()

    panel = oriented(span, span, face, face - sign * PANEL_DEPTH)
    cross_depth = face - sign * (PANEL_DEPTH + GROOVE_D)
    cross = (oriented(GROOVE_W, span, face, cross_depth)
             + oriented(span, GROOVE_W, face, cross_depth))
    return panel + cross


# --------------------------------------------------------------------------
# the model
# --------------------------------------------------------------------------

def validate() -> list[str]:
    """Check the parameter set against printer + geometry limits.

    These are the constraints that are easy to violate by nudging one number,
    and that produce a model which still slices but prints or works badly.
    """
    problems = []
    flat = H - EDGE_CHAMFER   # half-extent of the flat area on any outer face

    # A flared opening must land inside the flat face, not run off the chamfer
    # and notch the cube's edge.
    for name, half in (("SLOT_W", SLOT_W / 2), ("SLOT_D", SLOT_D / 2),
                       ("WIN_W", WIN_W / 2), ("WIN_TOP", WIN_TOP)):
        if half + OPEN_FLARE > flat:
            problems.append(
                f"{name}: flared mouth reaches {half + OPEN_FLARE:.1f} mm but "
                f"the flat face ends at {flat:.1f} mm - it would breach the "
                f"edge chamfer")

    # The book has to drop through the slot.
    if SLOT_D < BOOK_DEPTH:
        problems.append(f"SLOT_D {SLOT_D} < book depth {BOOK_DEPTH}")
    if SLOT_W < BOOK_THICK:
        problems.append(f"SLOT_W {SLOT_W} < one spine {BOOK_THICK}")

    # Floor rails must sit outboard of the book footprint.
    if SLOT_D / 2 + RAIL_W > H - WALL:
        problems.append("floor rails collide with the cavity wall")

    # Openings must be self-supporting: the flare has to be at least as deep
    # as the wall it travels through, or the underside droops below 45 deg.
    if OPEN_FLARE < WALL:
        problems.append(
            f"OPEN_FLARE {OPEN_FLARE} < WALL {WALL}: opening undersides would "
            f"overhang past 45 deg and need support")

    # Panels must not run off the flat face either.
    if (CUBE - 2 * PANEL_INSET) / 2 > flat:
        problems.append("PANEL_INSET too small - panels overrun the chamfer")

    # The seam must clear the panels below it and the top face above it.
    if SEAM_Z < (CUBE - 2 * PANEL_INSET) / 2:
        problems.append("SEAM_Z cuts across the recessed panels")
    if SEAM_Z + SEAM_H > flat:
        problems.append("SEAM_Z + SEAM_H runs off the top edge chamfer")

    # Thinnest remaining wall is under the seam / panel groove stack.
    if WALL - max(PANEL_DEPTH + GROOVE_D, SEAM_D) < 2.0:
        problems.append("WALL too thin under the panel grooves")

    if CUBE > BUILD:
        problems.append(f"CUBE {CUBE} exceeds build volume {BUILD}")

    return problems


def outer_body(inset: float = 0.0) -> Manifold:
    """The bevelled cube, every face pulled in by `inset`.

    Because each bounding plane is offset by the same distance, `inset` is a
    true uniform offset of the whole convex solid - which is what makes both
    the constant-thickness wall and the constant-depth seam work.
    """
    side = CUBE - 2 * inset
    solid = Manifold.cube([side, side, side], True)
    for normal, offset in bevel_planes(inset=inset):
        solid = keep_below(solid, normal, offset)
    return solid


def build() -> Manifold:
    # 1. outer body: cube trimmed back by every bevel plane
    body = outer_body()

    # 2. inner cavity. Straight-walled up to the taper, then funnelled in to
    #    the top slot so the top face has no unsupported horizontal ledge.
    cav = H - WALL
    floor_z = -H + FLOOR
    taper_h = TAPER_MARGIN * max(cav - SLOT_D / 2, cav - SLOT_W / 2)
    taper_z = cav - taper_h

    lower = box(-cav, cav, -cav, cav, floor_z, taper_z)
    for normal, offset in bevel_planes(inset=WALL):
        if abs(normal[2]) < 1e-9:      # vertical edges only
            lower = keep_below(lower, normal, offset)

    funnel = Manifold.batch_hull([
        box(-cav, cav, -cav, cav, taper_z, taper_z + 0.01),
        box(-SLOT_W / 2, SLOT_W / 2, -SLOT_D / 2, SLOT_D / 2, cav - 0.01, cav),
    ])
    shell = body - (lower + funnel)

    # 3. openings
    shell -= flared_cutter(SLOT_W, SLOT_D, 2, cav, H, OPEN_FLARE)
    window = flared_cutter(WIN_W, WIN_TOP + H - FLOOR - WIN_LIP, 1,
                           cav, H, OPEN_FLARE)
    window = window.translate([0, 0, (WIN_TOP + (-H + FLOOR + WIN_LIP)) / 2])
    shell -= window

    # 4. floor rails that stop the stack drifting front-to-back. They sit
    #    *outboard* of the slot footprint, so the channel between them is
    #    exactly SLOT_D and nothing intrudes on the book.
    for s in (1, -1):
        y0, y1 = sorted((s * SLOT_D / 2, s * (SLOT_D / 2 + RAIL_W)))
        shell += box(-cav, cav, y0, y1, floor_z, floor_z + RAIL_H)

    # 5. face detailing on the two sides and the back.
    #    The bottom is left flat: it carries the load and it is the print's
    #    first layer, so a recess there costs strength and bed adhesion.
    for axis, sign in ((0, 1), (0, -1), (1, -1)):
        shell -= recessed_panel(axis, sign)

    # 6. the lid seam. Everything in this z-band that lies outside a body
    #    inset by SEAM_D gets removed, so the groove keeps a constant depth
    #    as it runs across the flats and around the corner chamfers.
    seam = (box(-BIG, BIG, -BIG, BIG, SEAM_Z, SEAM_Z + SEAM_H)
            - outer_body(inset=SEAM_D))
    shell -= seam

    return shell


def to_trimesh(solid: Manifold) -> trimesh.Trimesh:
    mesh = solid.to_mesh()
    verts = np.asarray(mesh.vert_properties)[:, :3]
    return trimesh.Trimesh(vertices=verts, faces=np.asarray(mesh.tri_verts),
                           process=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="stl", help="output directory")
    ap.add_argument("--name", default="manga_loot_cube_a1mini")
    args = ap.parse_args()

    problems = validate()
    if problems:
        raise SystemExit("invalid parameters:\n  - " + "\n  - ".join(problems))

    solid = build()
    mesh = to_trimesh(solid)
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, args.name + ".stl")
    mesh.export(path)

    lo = solid.bounding_box()
    capacity = int(SLOT_W // BOOK_THICK)
    print(f"wrote {path}")
    print(f"  triangles     : {solid.num_tri()}")
    print(f"  bounding box  : {lo[3]-lo[0]:.1f} x {lo[4]-lo[1]:.1f} x "
          f"{lo[5]-lo[2]:.1f} mm")
    print(f"  watertight    : {mesh.is_watertight}, "
          f"volume {solid.volume()/1000:.0f} cm^3")
    print(f"  capacity      : {capacity} x {BOOK_THICK:.0f} mm volumes")
    print(f"  spine proud by: "
          f"{BOOK_HEIGHT - (CUBE - FLOOR):.1f} mm above the top face")


if __name__ == "__main__":
    main()
