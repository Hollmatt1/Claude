"""Draw the skeleton, hand path and reference lines onto the video."""
from __future__ import annotations

import subprocess

import cv2
import numpy as np

from .analyze import NOSE, L_SH, R_SH, L_HIP, R_HIP, L_WR, R_WR, PHASES
from .pose import iter_frames

BONES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24),
         (23, 25), (25, 27), (24, 26), (26, 28), (27, 31), (28, 32)]
OUT_LONG_SIDE = 720
WHITE, YELLOW, CYAN, GREEN = (255, 255, 255), (0, 220, 255), (255, 210, 0), (90, 220, 90)


def _draw(img, lm, s, ref, view, trail, label):
    def p(pt):
        return int(pt[0] * s), int(pt[1] * s)

    h, w = img.shape[:2]
    th = max(2, int(round(w / 300)))
    # reference lines from address
    if view == "face_on":
        for x in (ref["head_x"], ref["hip_x"]):
            cv2.line(img, (int(x * s), 0), (int(x * s), h), CYAN, 1, cv2.LINE_AA)
    else:
        cv2.line(img, p(ref["hip"]), p(ref["sh_ext"]), CYAN, th, cv2.LINE_AA)
    cv2.line(img, (0, int(ref["head_y"] * s)), (w, int(ref["head_y"] * s)), CYAN, 1, cv2.LINE_AA)
    # hand trail
    if len(trail) > 1:
        pts = np.array([p(q) for q in trail], dtype=np.int32)
        cv2.polylines(img, [pts], False, YELLOW, th, cv2.LINE_AA)
    for a, b in BONES:
        if not (np.isfinite(lm[a, :2]).all() and np.isfinite(lm[b, :2]).all()) or not lm[a, 0] or not lm[b, 0]:
            continue
        cv2.line(img, p(lm[a]), p(lm[b]), WHITE, th, cv2.LINE_AA)
    for i in (NOSE, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28):
        cv2.circle(img, p(lm[i]), th + 2, GREEN, -1, cv2.LINE_AA)
    if label:
        fs = w / 600
        cv2.putText(img, label.upper(), (12, int(40 * fs) + 4), cv2.FONT_HERSHEY_SIMPLEX, fs * 1.1,
                    (0, 0, 0), th + 3, cv2.LINE_AA)
        cv2.putText(img, label.upper(), (12, int(40 * fs) + 4), cv2.FONT_HERSHEY_SIMPLEX, fs * 1.1,
                    YELLOW, th, cv2.LINE_AA)


def render(video_path: str, data: dict, result: dict, out_dir: str) -> dict:
    lm_all = result["_smoothed"]
    A = result["_ref"]["address_landmarks"]
    view = result["view"]
    sh_a = (A[L_SH, :2] + A[R_SH, :2]) / 2
    hip_a = (A[L_HIP, :2] + A[R_HIP, :2]) / 2
    ref = {
        "head_x": A[NOSE, 0], "head_y": A[NOSE, 1], "hip_x": hip_a[0],
        "hip": hip_a, "sh_ext": hip_a + (sh_a - hip_a) * 1.4,
    }
    phase_frames = {result["phases"][p]["frame"]: p for p in PHASES}

    w, h = data["width"], data["height"]
    s = min(1.0, OUT_LONG_SIDE / max(w, h))
    ow, oh = int(w * s) // 2 * 2, int(h * s) // 2 * 2
    fps_eff = result["fps_effective"]
    out_fps = 30 if fps_eff > 60 else max(10, round(fps_eff))
    hold = max(1, int(round(out_fps * 0.6)))  # freeze on each key position for ~0.6 s

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{ow}x{oh}", "-r", str(out_fps), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", f"{out_dir}/annotated.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    hands = (lm_all[:, L_WR, :2] + lm_all[:, R_WR, :2]) / 2
    a_frame = result["phases"]["address"]["frame"]
    stills = {}
    try:
        for i, (_, frame) in enumerate(iter_frames(video_path, data["stride"], data["fps"])):
            if i >= len(lm_all):
                break
            img = cv2.resize(frame, (ow, oh)) if s < 1 or frame.shape[1] != ow else frame.copy()
            label = phase_frames.get(i, "")
            trail = hands[a_frame:i + 1] if i >= a_frame else hands[:0]
            _draw(img, lm_all[i], s, ref, view, trail, label)
            proc.stdin.write(img.tobytes())
            if label:
                for _ in range(hold):
                    proc.stdin.write(img.tobytes())
                cv2.imwrite(f"{out_dir}/{label}.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                stills[label] = f"{label}.jpg"
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed to write the annotated video")
    return {"video": "annotated.mp4", "stills": stills, "playback_fps": out_fps}
