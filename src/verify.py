#!/usr/bin/env python3
"""Checks on the generated cube: geometry, clearances and printability.

    python3 src/verify.py

Exits non-zero if anything fails.
"""

from __future__ import annotations

import sys

import numpy as np
from manifold3d import Manifold

import manga_loot_cube as M

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not ok:
        FAILURES.append(name)


def solid_frac(shell: Manifold, point, edge=1.0) -> float:
    """Fraction of a small probe cube at `point` that is inside `shell`."""
    probe = Manifold.cube([edge] * 3, True).translate([float(v) for v in point])
    return (shell ^ probe).volume() / edge ** 3


def main() -> int:
    check("parameters valid", not M.validate(), str(M.validate()))

    shell = M.build()
    mesh = M.to_trimesh(shell)
    lo = shell.bounding_box()
    size = np.array(lo[3:]) - np.array(lo[:3])

    # ---- basic integrity -------------------------------------------------
    check("mesh is watertight", bool(mesh.is_watertight))
    check("single connected body", len(shell.decompose()) == 1,
          f"{len(shell.decompose())} bodies")
    check("fits the build volume", bool(np.all(size <= M.BUILD + 1e-6)),
          f"{size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm")
    check("cube is cubic", float(size.max() - size.min()) < 1e-6)

    # ---- the walls actually exist ---------------------------------------
    # Regression guard: an over-long opening cutter once deleted the floor and
    # the back wall while leaving the mesh watertight.
    walls = {
        "floor (front-left quadrant)": [-40, 40, -87],
        "floor (back-right quadrant)": [40, -40, -87],
        "back wall": [40, -86, 40],
        "left wall (panel land)": [-86, 40, 40],
        "right wall (panel land)": [86, -40, 40],
        "top border, beside slot": [78, 0, 85],
        "top border, in front of slot": [0, 75, 85],
        "front lip below window": [0, 86, -75],
        "front band above window": [0, 86, 70],
    }
    for label, p in walls.items():
        check(f"solid: {label}", solid_frac(shell, p) > 0.9)

    # ---- the openings actually open -------------------------------------
    voids = {
        "cavity centre": [0, 0, 0],
        "top slot": [0, 0, 87],
        "front window": [0, 86, 0],
        "book channel between rails": [0, 0, -80],
    }
    for label, p in voids.items():
        check(f"open: {label}", solid_frac(shell, p) < 0.1)

    # ---- the media fits --------------------------------------------------
    floor_z = -M.H + M.FLOOR
    stack = M.box(-M.SLOT_W / 2, M.SLOT_W / 2,
                  -M.BOOK_DEPTH / 2, M.BOOK_DEPTH / 2,
                  floor_z, floor_z + M.BOOK_HEIGHT)
    check("book stack clears the shell", (shell ^ stack).volume() < 1e-6,
          f"{(shell ^ stack).volume():.1f} mm^3 overlap")

    # a single volume must be able to drop vertically in through the slot
    one = M.box(-M.BOOK_THICK / 2, M.BOOK_THICK / 2,
                -M.BOOK_DEPTH / 2, M.BOOK_DEPTH / 2, floor_z, 400.0)
    check("drop-in path is clear", (shell ^ one).volume() < 1e-6)

    capacity = int(M.SLOT_W // M.BOOK_THICK)
    check("holds at least 6 volumes", capacity >= 6, f"{capacity} volumes")

    # ---- printability ----------------------------------------------------
    # A downward-facing surface steeper than 45 degrees needs support *unless*
    # it is shallow enough to bridge. Panel recesses and grooves are deliberate
    # 1-2 mm ledges, so the test is angle AND unsupported depth, not angle
    # alone. Depth is taken as the facet's smaller horizontal dimension.
    BRIDGE_OK = 2.5   # mm of unsupported horizontal run a nozzle spans happily

    tris = mesh.vertices[mesh.faces]
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    areas = np.linalg.norm(normals, axis=1) / 2.0
    with np.errstate(invalid="ignore"):
        nz = normals[:, 2] / np.linalg.norm(normals, axis=1)
    on_plate = tris[:, :, 2].max(axis=1) <= -M.H + 1e-6
    steep = (nz < -np.cos(np.radians(45.0)) - 1e-6) & ~on_plate

    # Unsupported run = the smallest altitude of the facet projected onto the
    # bed. A bounding box overstates it for slivers that run diagonally, which
    # is exactly what the seam groove does where it crosses a corner chamfer.
    flat_tris = tris[:, :, :2]
    e0 = flat_tris[:, 1] - flat_tris[:, 0]
    e1 = flat_tris[:, 2] - flat_tris[:, 0]
    area2d = np.abs(e0[:, 0] * e1[:, 1] - e0[:, 1] * e1[:, 0]) / 2.0
    edges = np.stack([
        np.linalg.norm(flat_tris[:, 1] - flat_tris[:, 0], axis=1),
        np.linalg.norm(flat_tris[:, 2] - flat_tris[:, 1], axis=1),
        np.linalg.norm(flat_tris[:, 0] - flat_tris[:, 2], axis=1),
    ], axis=1)
    longest = np.maximum(edges.max(axis=1), 1e-9)
    depth = 2.0 * area2d / longest
    bad = steep & (depth > BRIDGE_OK)
    check("no overhangs needing support", not bad.any(),
          f"{areas[bad].sum():.0f} mm^2 over {int(bad.sum())} facets")
    ledges = steep & ~bad
    if ledges.any():
        print(f"      ({int(ledges.sum())} shallow ledges <= {BRIDGE_OK} mm "
              f"deep, bridged not supported - panel recesses and grooves)")

    # ---- report ----------------------------------------------------------
    print()
    print(f"exterior        : {size[0]:.0f} x {size[1]:.0f} x {size[2]:.0f} mm")
    print(f"material volume : {shell.volume() / 1000:.0f} cm^3 solid "
          f"(~{shell.volume() / 1000 * 1.24:.0f} g of PLA at 100% infill)")
    print(f"capacity        : {capacity} x {M.BOOK_THICK:.0f} mm volumes")
    print(f"spine stands    : {M.BOOK_HEIGHT - (M.CUBE - M.FLOOR):.1f} mm "
          f"proud of the top face")

    if FAILURES:
        print(f"\n{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
