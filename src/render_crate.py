#!/usr/bin/env python3
"""Preview renders of the two-part crate."""
from __future__ import annotations
import argparse, os
import numpy as np
import manga_crate as C
import raster as R


def books(n=7, colour=(0.85, 0.51, 0.14)):
    w = n * C.BOOK_THICK
    out = []
    for i in range(n):
        x0 = -w / 2 + i * C.BOOK_THICK
        sh = 0.80 + 0.20 * ((i % 3) / 2.0)
        out.append((C.box(x0 + 0.7, x0 + C.BOOK_THICK - 0.7,
                          -C.BOOK_DEPTH / 2, C.BOOK_DEPTH / 2,
                          C.zc(C.FLOOR), C.zc(C.FLOOR + C.BOOK_HEIGHT)),
                    tuple(c * sh for c in colour)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs")
    ap.add_argument("--px", type=int, default=900)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    body, lid = C.split_parts(C.build_assembly())
    steel = (0.42, 0.46, 0.52)
    amber = (0.86, 0.52, 0.16)

    half = C.box(-C.BIG, C.BIG, -C.BIG, 0, -C.BIG, C.BIG)
    views = [
        ("assembled, three-quarter", [(body, steel), (lid, steel)], 22, 58),
        ("front", [(body, steel), (lid, steel)], 8, 90),
        ("lid lifted", [(body, steel),
                        (lid.translate([0, C.TRAVEL, 55]), steel)], 20, 58),
        ("loaded, lid off", [(body, steel)] + books(), 22, 58),
        ("section through the crate",
         [(body - half, steel), (lid - half, steel)]
         + [(b - half, c) for b, c in books()], 6, 84),
        ("dovetail shoulder, lid removed",
         [(body ^ C.box(-C.BIG, C.BIG, -C.BIG, C.BIG,
                        C.zc(C.SPLIT - 42), C.zc(C.SPLIT)), steel)], 46, 62),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(15, 10.6), dpi=120)
    for ax, (title, parts, elev, azim) in zip(axes.ravel(), views):
        ax.imshow(R.rasterise(parts, elev, azim, C.to_trimesh,
                              C.TOTAL_H * 0.62, px=args.px))
        ax.set_title(title, fontsize=12); ax.axis("off")
    fig.tight_layout()
    path = os.path.join(args.out, "crate_preview.png")
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    print("wrote", path)


if __name__ == "__main__":
    main()
