"""Long range-session videos: find each full swing, then cut it into its own clip.

The scan runs pose at a low frame rate and resolution over the whole video. A swing shows up as a
burst of hand speed (measured relative to the hips, so walking doesn't count) while the hands get
above the shoulders. Chips and putts don't qualify, and neither do waggles.
"""
from __future__ import annotations

import json
import subprocess
from typing import Callable

import cv2
import numpy as np

import functools

from .pose import SCAN_MODEL_PATH, _mediapipe_detector

SCAN_FPS = 10            # pose samples per second of real time during the scan
SCAN_LONG_SIDE = 480     # frame size for the scan
BEFORE_S = 2.6           # clip starts this long before the fastest hand movement (about impact)
AFTER_S = 2.0            # and ends this long after it
MERGE_S = 2.5            # speed peaks closer than this are one swing
SPEED_MIN = 4.0          # hand speed relative to hips, torso lengths per second
CLIP_MAX_FPS = 120       # cut clips keep at most this frame rate
CLIP_LONG_SIDE = 1080


def probe(path: str) -> dict:
    """Duration, frame rate and display size (after the phone's rotation flag)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,avg_frame_rate,r_frame_rate,duration:stream_side_data=rotation:"
                          "format=duration", "-of", "json", path], capture_output=True, text=True)
    info = json.loads(out.stdout or "{}")
    st = (info.get("streams") or [{}])[0]
    dur = float(st.get("duration") or info.get("format", {}).get("duration") or 0)

    def rate(r):
        try:
            a, b = r.split("/")
            return float(a) / float(b) if float(b) else 0.0
        except (ValueError, AttributeError):
            return 0.0

    fps = rate(st.get("avg_frame_rate")) or rate(st.get("r_frame_rate")) or 30.0
    w, h = int(st.get("width") or 0), int(st.get("height") or 0)
    rot = 0
    for sd in st.get("side_data_list") or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    if abs(rot) % 180 == 90:
        w, h = h, w
    if not (w and h):  # ffprobe failed; fall back to OpenCV, which also applies rotation
        cap = cv2.VideoCapture(path)
        ok, fr = cap.read()
        if ok:
            h, w = fr.shape[:2]
        n, f = cap.get(cv2.CAP_PROP_FRAME_COUNT), cap.get(cv2.CAP_PROP_FPS) or 30.0
        dur = dur or (n / f if f else 0)
        cap.release()
    return {"duration": dur, "fps": fps, "width": w, "height": h}


def scan(path: str, info: dict, progress: Callable[[float], None] | None = None,
         detector_factory: Callable = functools.partial(_mediapipe_detector, SCAN_MODEL_PATH)) -> tuple[np.ndarray, np.ndarray]:
    """Pose at SCAN_FPS over the whole video. Returns landmarks (N,33,4) in scan pixels and times (N,)."""
    w, h = info["width"], info["height"]
    s = min(1.0, SCAN_LONG_SIDE / max(w, h))
    sw, sh = max(2, int(w * s) // 2 * 2), max(2, int(h * s) // 2 * 2)
    # Decode only reference frames (I and P); phones put 3 B-frames between them, so this halves the
    # decode time. Never sample faster than what's left, or duplicated frames would fake hand speed.
    rate = min(SCAN_FPS, max(2.0, info["fps"] / 4))
    cmd = ["ffmpeg", "-v", "error", "-threads", "2", "-skip_frame:v:0", "noref", "-i", path, "-map", "0:v:0", "-an",
           "-vf", f"fps={rate},scale={sw}:{sh}:flags=fast_bilinear", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    detect = detector_factory()
    n_bytes = sw * sh * 3
    rows, times = [], []
    total = max(1, int(info["duration"] * rate))
    try:
        while True:
            buf = proc.stdout.read(n_bytes)
            if len(buf) < n_bytes:
                break
            k = len(times)
            rgb = np.frombuffer(buf, np.uint8).reshape(sh, sw, 3)
            out = detect(np.ascontiguousarray(rgb), int(k * 1000 / rate))
            if out is None:
                rows.append(np.full((33, 4), np.nan, np.float32))
            else:
                out = out.copy()
                out[:, 0] *= sw
                out[:, 1] *= sh
                rows.append(out)
            times.append(k / rate)
            if progress and k % 20 == 0:
                progress(min(0.99, k / total))
    finally:
        proc.stdout.close()
        proc.wait()
        if hasattr(detect, "close"):
            detect.close()
    if not rows:
        raise ValueError("No frames could be read from the video")
    return np.stack(rows), np.array(times)


def find_swings(lm: np.ndarray, t: np.ndarray, duration: float | None = None) -> list[dict]:
    """Return [{"start", "end", "peak"}] in seconds, one per full swing."""
    if len(t) < 5:
        return []
    sh = (lm[:, 11, :2] + lm[:, 12, :2]) / 2
    hip = (lm[:, 23, :2] + lm[:, 24, :2]) / 2
    hands = (lm[:, 15, :2] + lm[:, 16, :2]) / 2
    torso = np.linalg.norm(sh - hip, axis=1)
    scale = np.nanmedian(torso)
    if not np.isfinite(scale) or scale <= 0:
        return []
    rel = (hands - hip) / scale
    dt = np.diff(t)
    speed = np.zeros(len(t))
    speed[1:] = np.linalg.norm(np.diff(rel, axis=0), axis=1) / np.maximum(dt, 1e-6)
    speed = np.nan_to_num(speed, nan=0.0)
    # hands above the shoulders (image y grows downward), in torso lengths
    above = np.nan_to_num((sh[:, 1] - hands[:, 1]) / scale, nan=-9.0)

    end_t = duration or float(t[-1])
    cands = []
    for i in np.flatnonzero(speed >= SPEED_MIN):
        near = (t >= t[i] - 1.6) & (t <= t[i] + 1.6)
        if above[near].max() > 0.15:
            cands.append(i)
    # one peak per burst: keep the fastest sample, drop anything within MERGE_S of a faster one
    peaks: list[int] = []
    for i in sorted(cands, key=lambda i: -speed[i]):
        if all(abs(t[i] - t[j]) >= MERGE_S for j in peaks):
            peaks.append(i)
    out = []
    for i in sorted(peaks):
        pk = float(t[i])
        out.append({"start": round(max(0.0, pk - BEFORE_S), 2), "end": round(min(end_t, pk + AFTER_S), 2),
                    "peak": round(pk, 2)})
    return out


def cut(path: str, start: float, end: float, dest: str, info: dict) -> None:
    """Re-encode one swing as its own clip: exact cut, rotation baked in, at most CLIP_MAX_FPS."""
    w, h = info["width"], info["height"]
    s = min(1.0, CLIP_LONG_SIDE / max(w, h))
    vf = f"scale={int(w * s) // 2 * 2}:{int(h * s) // 2 * 2}"
    if info["fps"] > CLIP_MAX_FPS + 1:
        vf = f"fps={CLIP_MAX_FPS}," + vf
    cmd = ["ffmpeg", "-y", "-v", "error", "-threads", "2", "-ss", f"{start:.3f}", "-i", path, "-t", f"{end - start:.3f}",
           "-map", "0:v:0", "-an", "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p", dest]
    subprocess.run(cmd, check=True)
