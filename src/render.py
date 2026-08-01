#!/usr/bin/env python3
"""Shaded preview images of the cube, including cutaways and a loaded view.

Uses a small orthographic z-buffer rasteriser rather than matplotlib's 3D
axes: matplotlib sorts whole collections back-to-front, which puts the manga
in front of the wall that should hide them and drops faces at the openings.

    python3 src/render.py --out docs/
"""

from __future__ import annotations

import argparse
import os

import numpy as np

import manga_loot_cube as M

BG = np.array([1.0, 1.0, 1.0])
LIGHT = np.array([0.40, 0.62, 0.68])
LIGHT /= np.linalg.norm(LIGHT)


def camera(elev_deg: float, azim_deg: float) -> np.ndarray:
    """World -> camera rotation. Camera looks along -Z, +Y is up on screen."""
    e, a = np.radians(elev_deg), np.radians(azim_deg)
    fwd = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    up = np.array([0.0, 0.0, 1.0])
    right = np.cross(up, fwd)
    right /= np.linalg.norm(right)
    true_up = np.cross(fwd, right)
    return np.stack([right, true_up, fwd])


def rasterise(parts, elev, azim, px=900, pad=1.06):
    """parts: list of (Manifold, rgb). Returns an HxWx3 float image."""
    tris, cols = [], []
    for solid, colour in parts:
        mesh = M.to_trimesh(solid)
        t = mesh.vertices[mesh.faces]
        tris.append(t)
        cols.append(np.repeat(np.array(colour)[None, :], len(t), axis=0))
    tris = np.concatenate(tris)
    cols = np.concatenate(cols)

    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    lam = 0.26 + 0.74 * np.clip(n @ LIGHT, 0.0, 1.0)
    shade = np.clip(cols * lam[:, None], 0, 1)

    R = camera(elev, azim)
    cam = tris @ R.T                      # (T,3,3) -> x,y screen, z depth

    half = M.H * np.sqrt(3.0) * pad
    scale = px / (2 * half)
    sx = (cam[:, :, 0] + half) * scale
    sy = (half - cam[:, :, 1]) * scale    # flip: image rows go down
    # fwd points from the origin toward the camera, so larger cam-z is nearer.
    # Negate it: the z-test below keeps the smallest value.
    depth = -cam[:, :, 2]

    img = np.repeat(np.repeat(BG[None, None, :], px, 0), px, 1)
    zbuf = np.full((px, px), np.inf)

    for i in range(len(tris)):
        x, y, z = sx[i], sy[i], depth[i]
        x0, x1 = int(np.floor(x.min())), int(np.ceil(x.max())) + 1
        y0, y1 = int(np.floor(y.min())), int(np.ceil(y.max())) + 1
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, px), min(y1, px)
        if x1 <= x0 or y1 <= y0:
            continue

        area = ((x[1] - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (y[1] - y[0]))
        if abs(area) < 1e-9:
            continue

        gx, gy = np.meshgrid(np.arange(x0, x1) + 0.5,
                            np.arange(y0, y1) + 0.5)
        w0 = ((x[1] - x[0]) * (gy - y[0]) - (gx - x[0]) * (y[1] - y[0])) / area
        w1 = ((gx - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (gy - y[0])) / area
        inside = (w0 >= -1e-9) & (w1 >= -1e-9) & (w0 + w1 <= 1 + 1e-9)
        if not inside.any():
            continue

        zz = z[0] + w1 * (z[1] - z[0]) + w0 * (z[2] - z[0])
        tile = zbuf[y0:y1, x0:x1]
        win = inside & (zz < tile)
        if not win.any():
            continue
        tile[win] = zz[win]
        img[y0:y1, x0:x1][win] = shade[i]

    return img


def books(n=7, colour=(0.85, 0.51, 0.14)):
    floor_z = -M.H + M.FLOOR
    span = n * M.BOOK_THICK
    out = []
    for i in range(n):
        x0 = -span / 2 + i * M.BOOK_THICK
        shade = 0.82 + 0.18 * ((i % 3) / 2.0)
        out.append((M.box(x0 + 0.7, x0 + M.BOOK_THICK - 0.7,
                          -M.BOOK_DEPTH / 2, M.BOOK_DEPTH / 2,
                          floor_z, floor_z + M.BOOK_HEIGHT),
                    tuple(c * shade for c in colour)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs")
    ap.add_argument("--px", type=int, default=900)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    shell = M.build()
    body = (0.36, 0.42, 0.86)

    # front face is +Y, so the camera wants azimuth 90
    views = [
        ("three-quarter", [(shell, body)], 24, 62),
        ("front", [(shell, body)], 8, 90),
        ("top, showing the slot", [(shell, body)], 62, 74),
        ("loaded with 7 volumes", [(shell, body)] + books(), 24, 62),
        ("cutaway", [(shell - M.box(0, M.BIG, 0, M.BIG, -M.BIG, M.BIG), body)],
         24, 62),
        ("section through the channel",
         [(shell - M.box(-M.BIG, M.BIG, -M.BIG, 0, -M.BIG, M.BIG), body)]
         + [(b - M.box(-M.BIG, M.BIG, -M.BIG, 0, -M.BIG, M.BIG), c)
            for b, c in books()],
         6, 84),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(15, 10.4), dpi=120)
    for ax, (title, parts, elev, azim) in zip(axes.ravel(), views):
        ax.imshow(rasterise(parts, elev, azim, px=args.px))
        ax.set_title(title, fontsize=12)
        ax.axis("off")
    fig.tight_layout()
    path = os.path.join(args.out, "preview.png")
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


if __name__ == "__main__":
    main()
