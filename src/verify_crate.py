#!/usr/bin/env python3
"""Checks on the two-part crate: geometry, media fit, the lock, printability.

    PYTHONPATH=src python3 src/verify_crate.py

Exits non-zero if anything fails.
"""

from __future__ import annotations

import sys

import numpy as np
from manifold3d import Manifold

import manga_crate as C

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not ok:
        FAILURES.append(name)


def clash(a: Manifold, b: Manifold) -> float:
    return (a ^ b).volume()


def book_stack(n: int) -> Manifold:
    """The volume a full row of manga occupies, standing on the floor."""
    w = n * C.BOOK_THICK
    return C.box(-w / 2, w / 2, -C.BOOK_DEPTH / 2, C.BOOK_DEPTH / 2,
                 C.zc(C.FLOOR), C.zc(C.FLOOR + C.BOOK_HEIGHT))


def overhang_area(part: Manifold, bridge_ok: float = 10.0) -> float:
    """Downward area past 45 deg with more unsupported run than can bridge."""
    mesh = C.to_trimesh(part)
    tris = mesh.vertices[mesh.faces]
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    norm = np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    areas = norm / 2.0
    nz = n[:, 2] / norm
    z0 = tris[:, :, 2].min()
    on_plate = tris[:, :, 2].max(axis=1) <= z0 + 1e-6
    steep = (nz < -np.cos(np.radians(45.0)) - 1e-6) & ~on_plate

    flat = tris[:, :, :2]
    e0, e1 = flat[:, 1] - flat[:, 0], flat[:, 2] - flat[:, 0]
    area2d = np.abs(e0[:, 0] * e1[:, 1] - e0[:, 1] * e1[:, 0]) / 2.0
    edges = np.stack([np.linalg.norm(flat[:, (i + 1) % 3] - flat[:, i], axis=1)
                      for i in range(3)], axis=1)
    depth = 2.0 * area2d / np.maximum(edges.max(axis=1), 1e-9)
    return float(areas[steep & (depth > bridge_ok)].sum())


def main() -> int:
    assembly = C.build_assembly()
    body, lid = C.split_parts(assembly)

    # ---- parts ----------------------------------------------------------
    for name, part, want_h in (("body", body, C.SPLIT), ("lid", lid, None)):
        mesh = C.to_trimesh(part)
        bb = part.bounding_box()
        size = np.array(bb[3:]) - np.array(bb[:3])
        check(f"{name}: watertight", bool(mesh.is_watertight))
        check(f"{name}: single body", len(part.decompose()) == 1)
        check(f"{name}: fits build volume", bool(np.all(size <= C.BUILD + 1e-6)),
              f"{size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm")
    check("body uses the full build height",
          abs((body.bounding_box()[5] - body.bounding_box()[2]) - C.SPLIT) < 1e-6)

    # ---- media ----------------------------------------------------------
    rim_open = 2 * (C.HX - C.RIM_W)
    capacity = int(rim_open // C.BOOK_THICK)
    check("holds at least 6 volumes", capacity >= 6, f"{capacity} fit the rim")
    stack = book_stack(capacity)
    check("stack clears the body", clash(body, stack) < 1e-6,
          f"{clash(body, stack):.1f} mm^3")
    check("stack clears the lid, locked", clash(lid, stack) < 1e-6,
          f"{clash(lid, stack):.1f} mm^3")
    check("spines fully enclosed",
          C.FLOOR + C.BOOK_HEIGHT <= C.TOTAL_H - C.LID_TOP + 1e-6,
          f"book top {C.FLOOR + C.BOOK_HEIGHT:.1f} vs ceiling "
          f"{C.TOTAL_H - C.LID_TOP:.1f} mm")

    # ---- openings --------------------------------------------------------
    def solid_frac(part, point, e=1.0):
        probe = Manifold.cube([e] * 3, True).translate([float(v) for v in point])
        return (part ^ probe).volume() / e ** 3

    wz = sum(C.WIN_Z) / 2
    check("front hatch is open",
          solid_frac(body, [0, C.HX - C.RELIEF_FIELD - 2, C.zc(wz)]) < 0.1)
    check("hatch head is solid above",
          solid_frac(body, [0, C.HX - C.RELIEF_FIELD - 2, C.zc(C.WIN_Z[1] + 14)]) > 0.9)
    check("hatch lip is solid below",
          solid_frac(body, [0, C.HX - C.RELIEF_FIELD - 2, C.zc(C.WIN_Z[0] - 14)]) > 0.9)

    # ---- the lock -------------------------------------------------------
    # Locked: the two parts must not interfere...
    check("locked: parts do not interfere", clash(body, lid) < 1e-6,
          f"{clash(body, lid):.1f} mm^3")

    # ...but lifting must be blocked by the dovetail. This is the check that
    # actually proves the lock locks rather than merely fits.
    play = 0.0
    for dz in np.arange(0.05, 4.0, 0.05):
        if clash(body, lid.translate([0, 0, float(dz)])) > 1.0:
            break
        play = float(dz)
    check("locked: lid cannot be lifted off", play < 1.5,
          f"{play:.2f} mm of vertical play before the dovetail bites")

    # Drop position: lid sits TRAVEL forward, seated, with nothing fouling.
    dropped = lid.translate([0, C.TRAVEL, 0])
    check("drop position: seats cleanly", clash(body, dropped) < 1e-6,
          f"{clash(body, dropped):.1f} mm^3")

    # ...and can be lowered straight down into it.
    worst = max(clash(body, lid.translate([0, C.TRAVEL, dz]))
                for dz in np.arange(0.0, 36.0, 1.5))
    check("drop position: vertical path is clear", worst < 1e-6,
          f"worst {worst:.1f} mm^3")

    # ...and slides from there to locked without binding.
    worst = max(clash(body, lid.translate([0, t, 0]))
                for t in np.arange(0.0, C.TRAVEL + 0.01, 0.5))
    check("slide path is clear", worst < 1e-6, f"worst {worst:.1f} mm^3")

    # The books must not foul the lid at the drop position either.
    check("stack clears the lid at drop position",
          clash(dropped, stack) < 1e-6, f"{clash(dropped, stack):.1f} mm^3")

    # ---- printability, in print orientation ------------------------------
    pr_body, pr_lid = C.print_ready(body, lid)
    for name, part in (("body", pr_body), ("lid", pr_lid)):
        a = overhang_area(part)
        check(f"{name}: no overhang needing support", a < 1.0, f"{a:.0f} mm^2")

    # ---- report ----------------------------------------------------------
    print()
    print(f"assembled       : 178 x 178 x {C.TOTAL_H:.0f} mm")
    print(f"body / lid      : {body.volume()/1000:.0f} / {lid.volume()/1000:.0f}"
          f" cm^3 solid")
    print(f"capacity        : {capacity} x {C.BOOK_THICK:.0f} mm volumes")
    print(f"lock            : {len(C.TEN_AT)*2} dovetail tenons, "
          f"{C.TRAVEL:.0f} mm travel")

    if FAILURES:
        print(f"\n{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
