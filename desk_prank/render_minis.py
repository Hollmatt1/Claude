#!/usr/bin/env python3
"""Contact sheet of every mini, as it sits on the desk (not as it prints)."""
from __future__ import annotations
import argparse, math, os
import numpy as np
import make_minis as K


def draw(ax, part, colour):
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    mesh = part.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3]
    f = np.asarray(mesh.tri_verts)
    tris = v[f]
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    light = np.array([0.4, -0.6, 0.75]); light /= np.linalg.norm(light)
    k = 0.35 + 0.65 * np.clip(n @ light, 0, 1)
    cols = np.clip(np.array(colour)[None, :] * k[:, None] + 0.08 * k[:, None], 0, 1)
    ax.add_collection3d(Poly3DCollection(tris, facecolors=cols, edgecolors="none"))
    lo, hi = v.min(0), v.max(0)
    c, r = (lo + hi) / 2, (hi - lo).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=24, azim=-58)
    ax.set_axis_off()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.dirname(os.path.abspath(__file__)))
    args = ap.parse_args()
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = list(K.ITEMS)
    cols = 7
    rows = math.ceil(len(names) / cols)
    fig = plt.figure(figsize=(cols * 2.6, rows * 2.8), dpi=110)
    fig.patch.set_facecolor("#e9e6df")
    for i, name in enumerate(names):
        fn, _, colour = K.ITEMS[name]
        part = fn().scale([K.SCALE] * 3)
        x0, y0, z0, x1, y1, z1 = part.bounding_box()
        ax = fig.add_subplot(rows, cols, i + 1, projection="3d")
        ax.set_facecolor("#e9e6df")
        draw(ax, part, colour)
        ax.set_title(f"{name}\n{x1 - x0:.0f} x {y1 - y0:.0f} x {z1 - z0:.0f} mm", fontsize=8)
    fig.tight_layout()
    path = os.path.join(args.out, "preview.png")
    fig.savefig(path, facecolor=fig.get_facecolor())
    print(path)


if __name__ == "__main__":
    main()
