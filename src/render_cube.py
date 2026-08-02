#!/usr/bin/env python3
"""Preview renders of the 12-part cube."""
from __future__ import annotations
import argparse, os, itertools
import numpy as np
import manga_cube as C
import raster as R

STEEL = (0.44, 0.48, 0.54)
AMBER = (0.86, 0.52, 0.16)
KEYC = (0.72, 0.32, 0.22)


def books(n=6):
    w = n * C.BOOK_THICK
    out = []
    for i in range(n):
        x0 = -w / 2 + i * C.BOOK_THICK
        sh = 0.80 + 0.20 * ((i % 3) / 2.0)
        out.append((C.box(x0 + 0.8, x0 + C.BOOK_THICK - 0.8,
                          -C.BOOK_DEPTH / 2, C.BOOK_DEPTH / 2,
                          C.FLOOR_Z, C.FLOOR_Z + C.BOOK_HEIGHT),
                    tuple(c * sh for c in AMBER)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs")
    ap.add_argument("--px", type=int, default=900)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    parts = C.split_parts()
    tint = {"base_FR": 0.00, "base_FL": 0.06, "base_BR": 0.06, "base_BL": 0.00,
            "cap_FR": 0.10, "cap_FL": 0.04, "cap_BR": 0.04, "cap_BL": 0.10}

    def shade(name):
        if name.startswith("key"):
            return KEYC
        t = tint.get(name, 0.0)
        return tuple(min(1.0, c + t) for c in STEEL)

    whole = [(p, shade(n)) for n, p in parts.items()]
    solidc = [(p, STEEL) for n, p in parts.items() if not n.startswith("key")]

    half = C.box(-C.BIG, C.BIG, -C.BIG, 0, -C.BIG, C.BIG)
    exploded = []
    for n, p in parts.items():
        dx = 26 if "R" in n[-2:] else -26
        dy = 26 if "F" in n else -26
        dz = 40 if n.startswith("cap") else 0
        if n.startswith("key"):
            dx, dy, dz = 0, 0, -46
        exploded.append((p.translate([dx, dy, dz]), shade(n)))

    views = [
        ("assembled", solidc, 22, 58),
        ("front", solidc, 8, 90),
        ("parts, by colour", whole, 22, 58),
        ("loaded, 6 volumes", [(p, STEEL) for n, p in parts.items()
                               if n.startswith("base")] + books(), 24, 58),
        ("exploded", exploded, 20, 58),
        ("section", [(p - half, shade(n)) for n, p in parts.items()]
         + [(b - half, c) for b, c in books()], 6, 84),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(15, 10.6), dpi=120)
    for ax, (title, ps, elev, azim) in zip(axes.ravel(), views):
        ax.imshow(R.rasterise(ps, elev, azim, C.to_trimesh, C.SIDE * 0.78,
                              px=args.px))
        ax.set_title(title, fontsize=12); ax.axis("off")
    fig.tight_layout()
    path = os.path.join(args.out, "cube_preview.png")
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    print("wrote", path)


if __name__ == "__main__":
    main()
