"""Read a video and run MediaPipe Pose on it."""
from __future__ import annotations

import os
from typing import Callable, Iterator

import cv2
import numpy as np

MODEL_PATH = os.environ.get("POSE_MODEL", "/app/models/pose_landmarker_heavy.task")
SCAN_MODEL_PATH = os.environ.get("SCAN_POSE_MODEL", "/app/models/pose_landmarker_full.task")
TARGET_FPS = 120       # process at most this many frames per second of real time
MAX_SECONDS = 20       # ignore anything after this
DETECT_LONG_SIDE = 960  # resize frames to this before running pose


def video_info(path: str, target_fps: float | None = None) -> dict:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError("Could not open video")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if not (1 < fps < 1000):
        fps = 30.0
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    stride = max(1, round(fps / (target_fps or TARGET_FPS)))
    return {"fps": float(fps), "frame_count": count, "stride": stride}


def iter_frames(path: str, stride: int, fps: float) -> Iterator[tuple[int, np.ndarray]]:
    """Yield (source_frame_index, BGR frame) for every `stride`-th frame. OpenCV applies
    the phone's rotation metadata automatically."""
    cap = cv2.VideoCapture(path)
    idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok or idx / fps > MAX_SECONDS:
                break
            if idx % stride == 0:
                yield idx, frame
            idx += 1
    finally:
        cap.release()


def _mediapipe_detector(model_path: str | None = None):
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    options = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=model_path or MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    landmarker = vision.PoseLandmarker.create_from_options(options)

    def detect(rgb: np.ndarray, ts_ms: int):
        res = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts_ms)
        if not res.pose_landmarks:
            return None
        return np.array([[p.x, p.y, p.z, p.visibility] for p in res.pose_landmarks[0]], dtype=np.float32)

    detect.close = landmarker.close
    return detect


def extract(path: str, progress: Callable[[float], None] | None = None,
            detector_factory: Callable = _mediapipe_detector, target_fps: float | None = None) -> dict:
    """Return landmarks (N,33,4) in source-pixel coordinates, times (N,), and video info."""
    info = video_info(path, target_fps)
    fps, stride = info["fps"], info["stride"]
    total = info["frame_count"] or 1
    detect = detector_factory()
    rows, times, frames = [], [], []
    w = h = 0
    try:
        for idx, frame in iter_frames(path, stride, fps):
            h, w = frame.shape[:2]
            s = DETECT_LONG_SIDE / max(h, w)
            small = cv2.resize(frame, (int(w * s), int(h * s))) if s < 1 else frame
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            out = detect(rgb, int(round(idx * 1000.0 / fps)))
            if out is None:
                rows.append(np.full((33, 4), np.nan, dtype=np.float32))
            else:
                out = out.copy()
                out[:, 0] *= w
                out[:, 1] *= h
                out[:, 2] *= w
                rows.append(out)
            times.append(idx / fps)
            frames.append(idx)
            if progress and len(frames) % 10 == 0:
                progress(min(0.99, idx / total))
    finally:
        if hasattr(detect, "close"):
            detect.close()
    if not rows:
        raise ValueError("No frames could be read from the video")
    return {
        "landmarks": np.stack(rows),
        "times": np.array(times, dtype=np.float64),
        "frames": frames,
        "width": w,
        "height": h,
        **info,
    }
