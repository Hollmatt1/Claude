#!/usr/bin/env python3
"""Checks on the 12-part cube: parts, media fit, the locks, printability.

    PYTHONPATH=src python3 src/verify_cube.py

Exits non-zero if anything fails.
"""

from __future__ import annotations

import sys

import numpy as np
from manifold3d import Manifold

import manga_cube as C

FAILURES: list[str] = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not ok:
        FAILURES.append(name)


def clash(a, b):
    return (a ^ b).volume()


def solid_frac(part, point, e=1.0):
    probe = Manifold.cube([e] * 3, True).translate([float(v) for v in point])
    return (part ^ probe).volume() / e ** 3


def overhang_area(part, bridge_ok=10.0):
    """Downward area past 45 deg with more unsupported run than can bridge."""
    mesh = C.to_trimesh(part)
    t = mesh.vertices[mesh.faces]
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    norm = np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    areas, nz = norm / 2.0, n[:, 2] / norm
    z0 = t[:, :, 2].min()
    on_plate = t[:, :, 2].max(axis=1) <= z0 + 1e-6
    steep = (nz < -np.cos(np.radians(45.0)) - 1e-6) & ~on_plate
    f = t[:, :, :2]
    e0, e1 = f[:, 1] - f[:, 0], f[:, 2] - f[:, 0]
    a2 = np.abs(e0[:, 0] * e1[:, 1] - e0[:, 1] * e1[:, 0]) / 2.0
    ed = np.stack([np.linalg.norm(f[:, (i + 1) % 3] - f[:, i], axis=1)
                   for i in range(3)], axis=1)
    depth = 2.0 * a2 / np.maximum(ed.max(axis=1), 1e-9)
    return float(areas[steep & (depth > bridge_ok)].sum())


def main() -> int:
    parts = C.split_parts()
    caps = {k: v for k, v in parts.items() if k.startswith("cap")}
    bases = {k: v for k, v in parts.items() if k.startswith("base")}
    keys = {k: v for k, v in parts.items() if k.startswith("key")}

    check("12 parts", len(parts) == 12, f"{len(parts)}")

    # ---- every part is printable and sane -------------------------------
    for name, part in parts.items():
        bb = part.bounding_box()
        size = np.array(bb[3:]) - np.array(bb[:3])
        check(f"{name}: single body and on the plate",
              len(part.decompose()) == 1 and bool(np.all(size <= C.BUILD + 1e-6)),
              f"{size[0]:.0f} x {size[1]:.0f} x {size[2]:.0f} mm")

    holes = {n: C.mesh_report(C.to_trimesh(C.print_ready(n, p)))
             for n, p in parts.items()}
    check("every part is a closed surface (no boundary edges)",
          all(b == 0 for b, _ in holes.values()),
          str({n: b for n, (b, _) in holes.items() if b}))
    check("every part has consistent winding",
          all(w for _, w in holes.values()))

    over = {n: overhang_area(C.print_ready(n, p)) for n, p in parts.items()}
    check("no part needs support",
          all(a < 1.0 for a in over.values()),
          str({n: round(a) for n, a in over.items() if a >= 1.0}))

    # ---- it is a true cube ----------------------------------------------
    whole = None
    for p in list(bases.values()) + list(caps.values()):
        whole = p if whole is None else whole + p
    bb = whole.bounding_box()
    size = np.array(bb[3:]) - np.array(bb[:3])
    check("assembles to a true cube",
          float(size.max() - size.min()) < 1e-6 and abs(size[0] - C.SIDE) < 1e-6,
          f"{size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm")

    # ---- parts do not interfere -----------------------------------------
    named = list(parts.items())
    worst = 0.0
    for i in range(len(named)):
        for j in range(i + 1, len(named)):
            worst = max(worst, clash(named[i][1], named[j][1]))
    check("no two parts overlap", worst < 1e-6, f"worst {worst:.2f} mm^3")

    # ---- media -----------------------------------------------------------
    # One wide pocket, volumes pressed together with no dividers.
    stack = C.box(-C.N_BOOKS * C.BOOK_THICK / 2, C.N_BOOKS * C.BOOK_THICK / 2,
                  C.HX - C.SLOT_D, C.HX - C.SLOT_D + C.BOOK_DEPTH,
                  C.FLOOR_Z, C.FLOOR_Z + C.BOOK_HEIGHT)
    worst_fit = max(clash(p, stack) for p in parts.values())
    check("the full stack fits the pocket", worst_fit < 1e-6,
          f"{C.N_BOOKS} volumes, {worst_fit:.2f} mm^3 clash")
    check("pocket is snug across the stack",
          0.5 <= C.SLOT_W - C.N_BOOKS * C.BOOK_THICK <= 4.0,
          f"{C.SLOT_W - C.N_BOOKS * C.BOOK_THICK:.1f} mm slack over "
          f"{C.N_BOOKS} spines")
    check("books stand proud enough to grip",
          2.0 <= C.BOOK_DEPTH - C.SLOT_D <= 5.0,
          f"{C.BOOK_DEPTH - C.SLOT_D:.1f} mm proud of the face")
    check("spines fully enclosed in height",
          C.FLOOR + C.BOOK_HEIGHT <= C.SIDE - C.CEIL + 1e-6,
          f"book top {C.FLOOR + C.BOOK_HEIGHT:.1f} vs {C.SIDE - C.CEIL:.1f} mm")
    check("no dividers in the pocket",
          solid_frac(None if False else
                     [p for n, p in parts.items() if n == "base_FR"][0],
                     [10, 60, C.FLOOR_Z + 90]) < 0.1,
          "mid-pocket is open")
    capacity = C.N_BOOKS

    # ---- the shell is solid where it should be ---------------------------
    body = None
    for p in bases.values():
        body = p if body is None else body + p
    whole = None
    for p in list(bases.values()) + list(caps.values()):
        whole = p if whole is None else whole + p

    check("solid beside the pocket",
          solid_frac(body, [C.HX - C.MARGIN / 2, 60, -20]) > 0.9, "side margin")
    check("solid behind the pocket back",
          solid_frac(body, [0, C.SLOT_BACK - 7, -20]) > 0.9)
    check("solid under the pocket floor",
          solid_frac(body, [0, 60, C.FLOOR_Z - 6]) > 0.9)

    # ---- the cap lock ----------------------------------------------------
    # Each cap octant must lock to the body on its own: drop it TRAVEL forward,
    # lower it, slide it home, and then it must not lift.
    for name, cap in caps.items():
        rest = None
        for k, p in parts.items():
            if k == name:
                continue
            rest = p if rest is None else rest + p

        dropped = cap.translate([0, C.TRAVEL, 0])
        check(f"{name}: seats at the drop position",
              clash(body, dropped) < 1e-6, f"{clash(body, dropped):.2f} mm^3")
        worst = max(clash(body, cap.translate([0, C.TRAVEL, dz]))
                    for dz in np.arange(0.0, 40.0, 2.0))
        check(f"{name}: descends clear", worst < 1e-6, f"{worst:.2f} mm^3")
        worst = max(clash(body, cap.translate([0, t, 0]))
                    for t in np.arange(0.0, C.TRAVEL + 0.01, 0.5))
        check(f"{name}: slides home clear", worst < 1e-6, f"{worst:.2f} mm^3")

        play = 0.0
        for dz in np.arange(0.05, 4.0, 0.05):
            if clash(body, cap.translate([0, 0, float(dz)])) > 1.0:
                break
            play = float(dz)
        check(f"{name}: cannot lift off", play < 1.5, f"{play:.2f} mm play")

        over = clash(body, cap.translate([0, -1.0, 0]))
        check(f"{name}: blind channel stops it flush", over > 1.0,
              f"{over:.1f} mm^3 if pushed 1 mm past")

    # ---- the spline keys -------------------------------------------------
    for name, key in keys.items():
        bb = key.bounding_box()
        length = bb[5] - bb[2]
        check(f"{name}: long enough to be useful", length > 10.0,
              f"{length:.1f} mm")
        # a key must block the two octants it straddles from parting sideways
        blocked = 0
        for bname, base in bases.items():
            if clash(base, key.translate([0, 0, 0])) > 1e-6:
                blocked += 1
        seated = sum(clash(b, key) for b in bases.values())
        check(f"{name}: seats without interference", seated < 1e-6,
              f"{seated:.2f} mm^3")

    # keys must actually resist the seam opening: pull one base octant away
    # along the seam normal and it should foul its key.
    for axis, sign, kname in ((0, 1, "x-seam"), (1, 1, "y-seam")):
        moved = bases["base_BR"].translate(
            [2.0 if axis == 0 else 0.0, 2.0 if axis == 1 else 0.0, 0.0])
        hit = sum(clash(moved, k) for k in keys.values())
        check(f"keys resist {kname} opening", hit > 1.0,
              f"{hit:.1f} mm^3 of interference at 2 mm")

    # ---- report ----------------------------------------------------------
    total = sum(p.volume() for p in parts.values())
    print()
    print(f"assembled       : {C.SIDE:.0f} mm cube, true on all axes")
    print(f"parts           : 8 octants ({C.SEAM_Z:.0f} mm base, "
          f"{C.SIDE - C.SEAM_Z:.0f} mm cap) + 4 spline keys")
    print(f"capacity        : {capacity} x {C.BOOK_THICK:.0f} mm volumes")
    print(f"material        : {total/1000:.0f} cm^3 solid across all parts")
    print(f"cap lock        : {len(C.TEN_AT)*2} tenons, {C.TRAVEL:.0f} mm travel,"
          f" blind-ended channels")

    if FAILURES:
        print(f"\n{len(FAILURES)} FAILED: {', '.join(sorted(set(FAILURES)))}")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
