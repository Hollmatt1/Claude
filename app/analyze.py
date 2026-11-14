"""Swing form analysis from 2D pose landmarks.

Input: landmarks array (N, 33, 4) in pixel coordinates (x, y, z, visibility),
NaN where no pose was found, plus per-frame timestamps in seconds.

Output: a JSON-serialisable dict with the detected view, swing phases,
measurements, and form checks.
"""
from __future__ import annotations

import math
import numpy as np

# MediaPipe Pose landmark indices
NOSE = 0
L_SH, R_SH = 11, 12
L_EL, R_EL = 13, 14
L_WR, R_WR = 15, 16
L_HIP, R_HIP = 23, 24
L_KN, R_KN = 25, 26
L_AN, R_AN = 27, 28

# Rough real-world sizes used only to show approximate inches next to ratios.
SHOULDER_WIDTH_IN = 15.0
TORSO_IN = 20.0

PHASES = ["address", "top", "impact", "finish"]


class AnalysisError(Exception):
    pass


# ---------------------------------------------------------------- helpers

def _interp_nans(a: np.ndarray) -> np.ndarray:
    """Linear-interpolate NaNs along axis 0 for every column."""
    out = a.copy()
    flat = out.reshape(out.shape[0], -1)
    idx = np.arange(flat.shape[0])
    for c in range(flat.shape[1]):
        col = flat[:, c]
        ok = ~np.isnan(col)
        if ok.sum() == 0:
            continue
        if ok.sum() < len(col):
            col[~ok] = np.interp(idx[~ok], idx[ok], col[ok])
    return flat.reshape(out.shape)


def _smooth(a: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return a
    pad = window // 2
    flat = a.reshape(a.shape[0], -1)
    padded = np.pad(flat, ((pad, pad), (0, 0)), mode="edge")
    kernel = np.ones(window) / window
    out = np.empty_like(flat)
    for c in range(flat.shape[1]):
        out[:, c] = np.convolve(padded[:, c], kernel, mode="valid")
    return out.reshape(a.shape)


def _mid(lm, i, j):
    return (lm[..., i, :2] + lm[..., j, :2]) / 2.0


def _angle(a, b, c) -> float:
    """Interior angle at b, in degrees, for 2D points."""
    v1, v2 = np.asarray(a) - np.asarray(b), np.asarray(c) - np.asarray(b)
    n = np.linalg.norm(v1) * np.linalg.norm(v2)
    if n == 0:
        return float("nan")
    return float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / n, -1, 1))))


def _grade(value, good, warn, higher_is_worse=True):
    """good/warn are thresholds. Returns 'good' | 'warn' | 'bad'."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "unknown"
    if higher_is_worse:
        return "good" if value <= good else "warn" if value <= warn else "bad"
    return "good" if value >= good else "warn" if value >= warn else "bad"


def _grade_range(value, good_lo, good_hi, warn_lo, warn_hi):
    if value is None or math.isnan(value):
        return "unknown"
    if good_lo <= value <= good_hi:
        return "good"
    if warn_lo <= value <= warn_hi:
        return "warn"
    return "bad"


def _check(cid, title, status, value, value_text, target_text, detail, tip, conf):
    return {
        "id": cid,
        "title": title,
        "status": status,
        "value": None if value is None or (isinstance(value, float) and math.isnan(value)) else round(float(value), 3),
        "value_text": value_text,
        "target_text": target_text,
        "detail": detail,
        "tip": tip if status in ("warn", "bad") else "",
        "confidence": conf,
    }


# ---------------------------------------------------------------- phases

def detect_phases(lm: np.ndarray, t: np.ndarray, scale: float) -> dict:
    """Find address, top, impact, finish frame indices from hand motion."""
    n = len(t)
    hands = _mid(lm, L_WR, R_WR)
    sh = _mid(lm, L_SH, R_SH)
    # Hand height above the shoulders, in torso lengths (positive = above).
    h = (sh[:, 1] - hands[:, 1]) / scale
    dt = np.gradient(t)
    dt[dt <= 0] = np.median(dt[dt > 0]) if np.any(dt > 0) else 1 / 30
    vel = np.gradient(hands, axis=0) / dt[:, None]
    speed = np.linalg.norm(vel, axis=1) / scale  # torso lengths per second

    low = h < -0.35
    if not low.any():
        raise AnalysisError("Couldn't find the hands below the waist. Make sure the whole body is in frame.")
    fast = int(np.argmax(np.where(low, speed, -1)))
    vmax = float(speed[fast])
    fps_eff = 1.0 / float(np.median(dt))

    # Impact: lowest hand position close to the fastest low-hands frame.
    win = max(2, int(round(0.08 * fps_eff)))
    lo, hi = max(0, fast - win), min(n, fast + win + 1)
    impact = lo + int(np.argmin(h[lo:hi]))

    # Top: highest hands in the 2.5 s before impact.
    start = max(0, int(np.searchsorted(t, t[impact] - 2.5)))
    if impact - start < 3:
        raise AnalysisError("The video starts too close to impact. Start recording before you take the club back.")
    top = start + int(np.argmax(h[start:impact]))
    if h[top] - h[impact] < 0.4:
        raise AnalysisError("Couldn't find a full swing (no backswing detected). Trim the clip to a single swing.")

    # Address / takeaway: last still frame before the hands reach halfway up.
    # (The hands are also nearly still at the top, so search from mid-backswing.)
    half = (h[impact] + h[top]) / 2
    mid = top
    while mid > 0 and h[mid] > half:
        mid -= 1
    still = 0.04 * vmax
    address = 0
    for f in range(mid, -1, -1):
        if speed[f] < still:
            address = f
            break

    # Finish: first still moment at least 0.2 s after impact, else last frame.
    finish = n - 1
    f0 = int(np.searchsorted(t, t[impact] + 0.2))
    for f in range(f0, n):
        if speed[f] < 0.12 * vmax:
            finish = f
            break

    return {
        "address": int(address),
        "top": int(top),
        "impact": int(impact),
        "finish": int(finish),
        "_speed": speed,
        "_h": h,
    }


# ---------------------------------------------------------------- main

def analyze(landmarks: np.ndarray, times: np.ndarray, view: str = "auto") -> dict:
    n = len(times)
    if n < 15:
        raise AnalysisError("Video is too short.")
    found = ~np.isnan(landmarks[:, 0, 0])
    if found.mean() < 0.6:
        raise AnalysisError(
            f"A golfer was only detected in {found.mean():.0%} of frames. "
            "Keep your whole body in frame and avoid other people in the shot.")

    fps_eff = 1.0 / float(np.median(np.diff(times)))
    window = max(3, int(round(0.04 * fps_eff)) | 1)
    lm = _smooth(_interp_nans(landmarks), window)
    vis = lm[..., 3]

    torso = np.linalg.norm(_mid(lm, L_SH, R_SH) - _mid(lm, L_HIP, R_HIP), axis=1)
    scale = float(np.median(torso))
    if scale <= 1:
        raise AnalysisError("Body is too small in the frame. Move the camera closer.")

    ph = detect_phases(lm, times, scale)
    a, top, imp, fin = ph["address"], ph["top"], ph["impact"], ph["finish"]

    # Reference values at address: median of the still period just before takeaway.
    a0 = max(0, int(np.searchsorted(times, times[a] - 0.3)))
    A = np.median(lm[a0:a + 1], axis=0)

    torso_a = float(np.linalg.norm(_mid(A, L_SH, R_SH) - _mid(A, L_HIP, R_HIP)))
    sw_a = float(abs(A[L_SH, 0] - A[R_SH, 0]))
    sw_ratio = sw_a / torso_a if torso_a else 0.0

    if view not in ("face_on", "dtl"):
        view = "face_on" if sw_ratio > 0.45 else "dtl"

    def conf(frames, idxs):
        v = float(np.mean([vis[f, i] for f in frames for i in idxs]))
        return "high" if v >= 0.7 else "medium" if v >= 0.5 else "low"

    checks = []
    metrics = {}

    # ---- Tempo (both views)
    back = float(times[top] - times[a])
    down = float(times[imp] - times[top])
    ratio = back / down if down > 0 else float("nan")
    metrics.update(backswing_s=round(back, 3), downswing_s=round(down, 3), tempo_ratio=round(ratio, 2))
    slowmo_note = ""
    if down > 0.6:
        slowmo_note = (" The downswing measured over 0.6 s, so this clip is probably slowed-down playback; "
                       "the seconds are off but the ratio is still valid.")
    checks.append(_check(
        "tempo", "Tempo (backswing : downswing)",
        _grade_range(ratio, 2.4, 3.6, 2.0, 4.2), ratio,
        f"{ratio:.1f} : 1  ({back:.2f}s back, {down:.2f}s down)",
        "about 3 : 1",
        "Most tour players take about three times as long going back as coming down." + slowmo_note,
        ("Your backswing is rushed relative to the downswing. Count '1-2' going back and '3' coming down."
         if ratio < 2.4 else
         "Your backswing is slow relative to the downswing, or you pause at the top. Keep the club moving through the transition."),
        "high"))

    if view == "face_on":
        # Which image direction is the target? Hands move to the trail side going back.
        hands = _mid(lm, L_WR, R_WR)
        trail_dir = 1.0 if hands[top, 0] > hands[a, 0] else -1.0
        lead_dir = -trail_dir
        lead_is_left = (A[L_SH, 0] - A[R_SH, 0]) * lead_dir > 0
        lsh, lel, lwr = (L_SH, L_EL, L_WR) if lead_is_left else (R_SH, R_EL, R_WR)
        lan = L_AN if lead_is_left else R_AN
        sw = sw_a
        handed = "right" if lead_dir > 0 else "left"
        metrics.update(handedness_guess=handed, shoulder_width_px=round(sw, 1))

        def lat(frame_vals, ref_vals):  # lateral shift toward target, in shoulder widths
            return float((frame_vals - ref_vals) * lead_dir / sw)

        # Head sway in backswing
        head_back = -lat(lm[top, NOSE, 0], A[NOSE, 0])  # positive = moved to trail side
        checks.append(_check(
            "head_sway", "Head movement in backswing", _grade(abs(head_back), 0.25, 0.45), head_back,
            f"{head_back * SHOULDER_WIDTH_IN:+.1f} in toward trail side",
            "less than ~4 in",
            "How far your head shifts sideways from address to the top.",
            "Your head is drifting off the ball. Turn your shoulders around your spine instead of sliding; "
            "practice with your head lightly touching a wall or alignment stick.",
            conf([a, top], [NOSE])))

        # Head ahead of ball at impact
        head_imp = lat(lm[imp, NOSE, 0], A[NOSE, 0])
        checks.append(_check(
            "head_impact", "Head position at impact", _grade(head_imp, 0.1, 0.25), head_imp,
            f"{head_imp * SHOULDER_WIDTH_IN:+.1f} in toward target",
            "at or behind its address position",
            "Your head should not move toward the target before impact.",
            "Your head is moving toward the target before impact, which tends to cause thin shots and slices. "
            "Keep your head behind the ball until the club passes it.",
            conf([a, imp], [NOSE])))

        # Hip sway at top
        hip_mid = _mid(lm, L_HIP, R_HIP)
        hip_a = _mid(A, L_HIP, R_HIP)
        hip_sway = -lat(hip_mid[top, 0], hip_a[0])
        checks.append(_check(
            "hip_sway", "Hip sway in backswing", _grade(hip_sway, 0.2, 0.35), hip_sway,
            f"{hip_sway * SHOULDER_WIDTH_IN:+.1f} in toward trail side",
            "less than ~3 in",
            "How far your pelvis slides away from the target going back.",
            "Your hips are sliding away from the target instead of turning. Feel pressure on the inside of your "
            "trail foot at the top and keep your trail knee flexed.",
            conf([a, top], [L_HIP, R_HIP])))

        # Hip shift toward target at impact
        hip_imp = lat(hip_mid[imp, 0], hip_a[0])
        checks.append(_check(
            "weight_shift", "Weight shift at impact", _grade(hip_imp, 0.15, 0.0, higher_is_worse=False), hip_imp,
            f"{hip_imp * SHOULDER_WIDTH_IN:+.1f} in toward target",
            "~2 in or more toward target",
            "Your pelvis should be ahead of where it started when you strike the ball.",
            "You're hanging back on your trail side at impact. Start the downswing by shifting your lead hip "
            "toward the target before turning.",
            conf([a, imp], [L_HIP, R_HIP])))

        # Lead arm at top
        arm = _angle(lm[top, lsh, :2], lm[top, lel, :2], lm[top, lwr, :2])
        checks.append(_check(
            "lead_arm", "Lead arm at the top", _grade(arm, 155, 135, higher_is_worse=False), arm,
            f"{arm:.0f}° at the elbow",
            "155° or straighter",
            "Lead elbow angle at the top of the backswing. This is measured in 2D, so it can read lower than it is.",
            "Your lead arm is bending a lot at the top, which shortens the swing arc. Make a shorter backswing that "
            "keeps the arm extended.",
            conf([top], [lsh, lel, lwr])))

        # Finish balance
        fin_end = min(n, int(np.searchsorted(times, times[fin] + 0.3)) + 1)
        hip_fin = np.median(hip_mid[fin:fin_end, 0])
        an_fin = np.median(lm[fin:fin_end, lan, 0])
        bal = float((hip_fin - an_fin) * lead_dir / sw)
        checks.append(_check(
            "finish", "Finish balance", _grade(bal, -0.25, -0.5, higher_is_worse=False), bal,
            f"hips {abs(bal) * SHOULDER_WIDTH_IN:.1f} in {'past' if bal >= 0 else 'behind'} lead foot",
            "hips over the lead foot",
            "At the finish your weight should be on your lead side, hips stacked over the lead foot.",
            "You're finishing on your back foot. Hold your finish for 3 seconds on every practice swing with "
            "your trail toe touching the ground lightly.",
            conf([fin], [L_HIP, R_HIP, lan])))

    else:  # down the line
        sh_mid = _mid(lm, L_SH, R_SH)
        hip_mid = _mid(lm, L_HIP, R_HIP)
        sh_a, hip_a = _mid(A, L_SH, R_SH), _mid(A, L_HIP, R_HIP)
        ball_dir = 1.0 if sh_a[0] > hip_a[0] else -1.0
        metrics.update(handedness_guess="right" if ball_dir > 0 else "left")

        def bend(sh, hp):  # forward bend from vertical, degrees
            dx, dy = (sh[0] - hp[0]) * ball_dir, hp[1] - sh[1]
            return float(np.degrees(np.arctan2(dx, dy)))

        bend_a = bend(sh_a, hip_a)
        checks.append(_check(
            "posture", "Spine tilt at address", _grade_range(bend_a, 28, 45, 20, 55), bend_a,
            f"{bend_a:.0f}° forward", "about 30–45°",
            "How far you bend forward from the hips at setup.",
            ("You're standing too upright at address. Push your hips back and let your chest tilt over the ball."
             if bend_a < 28 else
             "You're bent over a lot at address. Stand a little taller and let your arms hang from the shoulders."),
            conf([a], [L_SH, R_SH, L_HIP, R_HIP])))

        knee = np.nanmean([_angle(A[L_HIP, :2], A[L_KN, :2], A[L_AN, :2]),
                           _angle(A[R_HIP, :2], A[R_KN, :2], A[R_AN, :2])])
        checks.append(_check(
            "knees", "Knee flex at address", _grade_range(knee, 145, 165, 135, 172), knee,
            f"{180 - knee:.0f}° of flex", "about 15–35°",
            "How much your knees are bent at setup.",
            ("Your legs are nearly straight at address. Add a small amount of knee flex so you can turn your hips."
             if knee > 165 else
             "You're squatting at address. Straighten your legs slightly and get the bend from your hips instead."),
            conf([a], [L_KN, R_KN, L_AN, R_AN])))

        bend_i = bend(sh_mid[imp], hip_mid[imp])
        loss = bend_a - bend_i
        checks.append(_check(
            "spine_angle", "Spine angle kept through impact", _grade(loss, 6, 12), loss,
            f"{loss:+.0f}° lost (address {bend_a:.0f}°, impact {bend_i:.0f}°)", "within ~6°",
            "Whether you stay bent over through impact or stand up out of the shot.",
            "You're standing up through impact (losing your spine angle). Keep your chest pointed down at the ball "
            "until after impact.",
            conf([a, imp], [L_SH, R_SH, L_HIP, R_HIP])))

        ee = float((hip_mid[imp, 0] - hip_a[0]) * ball_dir / torso_a)
        checks.append(_check(
            "early_ext", "Hips toward the ball (early extension)", _grade(ee, 0.08, 0.16), ee,
            f"{ee * TORSO_IN:+.1f} in toward ball", "less than ~1.5 in",
            "Whether your hips move toward the ball during the downswing.",
            "Your hips are moving toward the ball in the downswing (early extension). Set up with your backside "
            "touching a wall or chair and keep it touching through impact in practice swings.",
            conf([a, imp], [L_HIP, R_HIP])))

        head_y = float((lm[imp, NOSE, 1] - A[NOSE, 1]) / torso_a)
        checks.append(_check(
            "head_height", "Head height at impact", _grade(abs(head_y), 0.06, 0.12), head_y,
            f"{abs(head_y) * TORSO_IN:.1f} in {'lower' if head_y > 0 else 'higher'}", "within ~1 in",
            "How much your head moves up or down from address to impact.",
            ("Your head is dropping in the downswing, which can cause fat shots."
             if head_y > 0 else
             "Your head is rising before impact, which can cause thin and topped shots.")
            + " Keep your eyes level and your knee flex constant.",
            conf([a, imp], [NOSE])))

        # Downswing path vs backswing path at mid-height (over-the-top tendency)
        hands = _mid(lm, L_WR, R_WR)
        hy = hands[:, 1]
        level = (A[L_WR, 1] + A[R_WR, 1]) / 2 + 0.5 * (sh_a[1] - (A[L_WR, 1] + A[R_WR, 1]) / 2)
        up = next((f for f in range(a + 1, top + 1) if hy[f] <= level), None)
        dn = next((f for f in range(top + 1, imp + 1) if hy[f] >= level), None)

        def x_at_level(f):  # interpolate hand x between frames f-1 and f where y crosses `level`
            y0, y1 = hy[f - 1], hy[f]
            k = 0.0 if y1 == y0 else (level - y0) / (y1 - y0)
            return hands[f - 1, 0] + k * (hands[f, 0] - hands[f - 1, 0])

        if up is not None and dn is not None:
            ott = float((x_at_level(dn) - x_at_level(up)) * ball_dir / torso_a)
            checks.append(_check(
                "path", "Downswing hand path", _grade(ott, 0.05, 0.15), ott,
                f"hands {abs(ott) * TORSO_IN:.1f} in {'outside' if ott > 0 else 'inside'} the backswing path",
                "on or inside the backswing path",
                "Compares where your hands are at chest height going back vs coming down. Coming down outside "
                "(closer to the ball) is the 'over the top' move.",
                "Your hands are coming down outside the backswing path (over the top), which causes slices and "
                "pulls. Start the downswing with your lower body and let your hands drop before turning your shoulders.",
                conf([up, dn], [L_WR, R_WR])))

    order = {"bad": 0, "warn": 1, "good": 2, "unknown": 3}
    priority = sorted([c for c in checks if c["status"] in ("bad", "warn")], key=lambda c: order[c["status"]])
    counts = {s: sum(c["status"] == s for c in checks) for s in ("good", "warn", "bad")}

    return {
        "view": view,
        "shoulder_ratio": round(sw_ratio, 3),
        "fps_effective": round(fps_eff, 1),
        "phases": {p: {"frame": int(ph[p]), "time": round(float(times[ph[p]]), 3)} for p in PHASES},
        "metrics": metrics,
        "checks": checks,
        "counts": counts,
        "top_priority": priority[0]["id"] if priority else None,
        "_smoothed": lm,  # used for rendering, stripped before saving
        "_ref": {"address_landmarks": A},
    }


def compare(mine: dict, ref: dict) -> list[dict]:
    """Side-by-side check values against a reference swing analysed the same way."""
    if mine.get("view") != ref.get("view"):
        return []
    ref_by_id = {c["id"]: c for c in ref["checks"]}
    rows = []
    for c in mine["checks"]:
        r = ref_by_id.get(c["id"])
        if not r:
            continue
        rows.append({"id": c["id"], "title": c["title"], "mine": c["value_text"], "ref": r["value_text"],
                     "mine_status": c["status"], "ref_status": r["status"]})
    return rows
