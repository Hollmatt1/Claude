"""Synthetic golf swing landmarks for testing the analyzer without a real video."""
import numpy as np


def _profile(t):
    """Arm angle (degrees, 0 = hands hanging down) over time.
    0.6 s address, 0.81 s backswing to 150°, 0.27 s downswing to 0, 0.6 s to -160°, 0.6 s hold."""
    a0, b, d, f = 0.6, 0.81, 0.27, 0.6
    if t < a0:
        return 0.0
    t -= a0
    if t < b:
        return 150 * (1 - np.cos(np.pi * t / b)) / 2
    t -= b
    if t < d:
        return 150 * (1 - (t / d) ** 2)
    t -= d
    if t < f:
        return -160 * np.sin(np.pi / 2 * t / f)
    return -160.0


def swing(view="face_on", fps=120, righty=True, head_sway=0.0, hip_sway=0.0, early_ext=0.0,
          stand_up_deg=0.0, hang_back=False, w=1080, h=1920):
    T = 0.6 + 0.81 + 0.27 + 0.6 + 0.6
    times = np.arange(0, T, 1 / fps)
    n = len(times)
    lm = np.zeros((n, 33, 4), dtype=np.float32)
    lm[..., 3] = 0.95
    cx, hip_y, torso = w / 2, h * 0.55, h * 0.18
    impact_t = 0.6 + 0.81 + 0.27
    lead = 1 if righty else -1  # target direction in image (face-on)
    for k, t in enumerate(times):
        ang = _profile(t)
        backswing_frac = max(0.0, ang) / 150 if t < impact_t else 0.0
        after = t >= impact_t
        if view == "face_on":
            hipx = cx - lead * hip_sway * torso * 0.75 * backswing_frac
            if after or t > 0.6 + 0.81:
                shift = 0.0 if hang_back else 0.25 * torso * 0.75
                prog = min(1, (t - (0.6 + 0.81)) / 0.27)
                hipx = cx + lead * shift * prog
                if after:
                    hipx = cx + lead * (shift + (0 if hang_back else 0.3 * torso * 0.75) * min(1, (t - impact_t) / 0.6))
            sw = torso * 0.75
            shx = hipx
            sh_y = hip_y - torso
            headx = cx - lead * head_sway * sw * backswing_frac
            lm[k, 0, :2] = (headx, sh_y - torso * 0.35)
            lm[k, 11, :2] = (shx + lead * sw / 2, sh_y)   # left shoulder is lead for a righty
            lm[k, 12, :2] = (shx - lead * sw / 2, sh_y)
            lm[k, 23, :2] = (hipx + lead * sw * 0.35, hip_y)
            lm[k, 24, :2] = (hipx - lead * sw * 0.35, hip_y)
            for j, side in ((25, 1), (26, -1)):
                lm[k, j, :2] = (cx + lead * side * sw * 0.45, hip_y + torso * 1.0)
            for j, side in ((27, 1), (28, -1)):
                lm[k, j, :2] = (cx + lead * side * sw * 0.5, hip_y + torso * 2.0)
            R = torso * 1.25
            th = np.radians(ang)
            hx = shx - lead * R * np.sin(th)
            hy = sh_y + R * np.cos(th)
            lm[k, 15, :2] = lm[k, 16, :2] = (hx, hy)
            lm[k, 13, :2] = ((lm[k, 11, 0] + hx) / 2, (sh_y + hy) / 2)
            lm[k, 14, :2] = ((lm[k, 12, 0] + hx) / 2, (sh_y + hy) / 2)
        else:  # down the line; ball is +x for a righty
            bd = 1 if righty else -1
            prog_imp = 0.0
            if t > 0.6 + 0.81:
                prog_imp = min(1, (t - (0.6 + 0.81)) / 0.27)
            bend = np.radians(38 - stand_up_deg * prog_imp)
            hipx = cx + bd * early_ext * torso * prog_imp
            shx = hipx + bd * torso * np.sin(bend)
            sh_y = hip_y - torso * np.cos(bend)
            lm[k, 0, :2] = (shx + bd * torso * 0.2, sh_y - torso * 0.2)
            lm[k, 11, :2] = lm[k, 12, :2] = (shx, sh_y)
            lm[k, 11, 0] += 5
            lm[k, 23, :2] = lm[k, 24, :2] = (hipx, hip_y)
            lm[k, 23, 0] += 4
            for j in (25, 26):
                lm[k, j, :2] = (cx + bd * torso * 0.25, hip_y + torso * 0.95)
            for j in (27, 28):
                lm[k, j, :2] = (cx + bd * torso * 0.05, hip_y + torso * 1.9)
            R = torso * 1.2
            th = np.radians(ang)
            # hands go up and slightly back on the way back; on the way down follow the same path
            hx = shx + bd * R * 0.35 * np.cos(th) - bd * R * 0.25 * np.sin(abs(th)) * (1 if t < impact_t else -1)
            hy = sh_y + R * np.cos(th)
            lm[k, 15, :2] = lm[k, 16, :2] = (hx, hy)
            lm[k, 13, :2] = lm[k, 14, :2] = ((shx + hx) / 2, (sh_y + hy) / 2)
    return lm, times
