#!/usr/bin/env python3
"""A small orthographic z-buffer rasteriser for previewing solids.

Model-agnostic on purpose. matplotlib's 3D axes sort whole collections
back-to-front, which puts contents in front of the wall that should hide them
and drops faces at openings, so previews here are rasterised directly.
"""

from __future__ import annotations

import numpy as np

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


def rasterise(parts, elev, azim, to_tri, half, px=900, pad=1.06):
    """parts: list of (Manifold, rgb). Returns an HxWx3 float image.

    `to_tri` converts a solid to a trimesh; `half` is the orthographic
    half-extent of the view.
    """
    tris, cols = [], []
    for solid, colour in parts:
        mesh = to_tri(solid)
        t = mesh.vertices[mesh.faces]
        tris.append(t)
        cols.append(np.repeat(np.array(colour)[None, :], len(t), axis=0))
    tris = np.concatenate(tris)
    cols = np.concatenate(cols)

    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    lam = 0.26 + 0.74 * np.clip(n @ LIGHT, 0.0, 1.0)

    R = camera(elev, azim)
    cam = tris @ R.T                      # (T,3,3) -> x,y screen, z depth

    # Depth cue. Without it a recess reads as flat: the inside of a back wall
    # shares its normal with the front face, so pure Lambertian shading gives
    # the two identical colour and openings vanish.
    dm = cam[:, :, 2].mean(axis=1)
    lo, hi = dm.min(), dm.max()
    fog = 1.0 - 0.42 * (hi - dm) / max(hi - lo, 1e-9)
    shade = np.clip(cols * (lam * fog)[:, None], 0, 1)

    half = half * pad
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
