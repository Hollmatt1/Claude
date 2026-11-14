"""End-to-end: synthetic video -> upload -> mocked pose -> analysis -> render -> API."""
import os, sys, time, tempfile, functools, subprocess
sys.path.insert(0, ".")
tmp = tempfile.mkdtemp(); os.environ["DATA_DIR"] = tmp; os.environ["APP_PASSWORD"] = "pw"
import cv2, numpy as np
from tests.synth import swing
from app import pose, main
from fastapi.testclient import TestClient

def make_video(path, view, fps):
    w, h = 540, 960
    lm, t = swing(view=view, fps=fps, w=w, h=h)
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for k in range(len(t)):
        img = np.full((h, w, 3), 60, np.uint8)
        for a, b in [(11,13),(13,15),(12,14),(14,16),(11,23),(12,24),(23,25),(25,27),(24,26),(26,28)]:
            cv2.line(img, tuple(map(int, lm[k,a,:2])), tuple(map(int, lm[k,b,:2])), (200,200,200), 4)
        vw.write(img)
    vw.release()
    return lm, t, w, h

def fake_factory(lm, t, w, h):
    def factory():
        def detect(rgb, ts_ms):
            k = int(np.argmin(np.abs(t * 1000 - ts_ms)))
            out = lm[k].copy(); out[:, 0] /= w; out[:, 1] /= h; out[:, 2] = 0
            return out
        return detect
    return factory

c = TestClient(main.app)
assert c.get("/").status_code == 401
auth = ("golf", "pw")
with c:
    ids = {}
    for name, view, fps, ref in [("mine_fo", "face_on", 60, False), ("pro_fo", "face_on", 60, True), ("mine_dtl", "dtl", 120, False)]:
        vp = f"{tmp}/{name}.mp4"
        lm, t, w, h = make_video(vp, view, fps)
        pose.extract = functools.partial(pose.__dict__["extract"].func if isinstance(pose.extract, functools.partial) else pose.extract, detector_factory=fake_factory(lm, t, w, h))
        with open(vp, "rb") as f:
            r = c.post("/api/swings", auth=auth, files={"file": ("IMG_1.MOV", f, "video/quicktime")},
                       data={"view": "auto", "label": "Max Homa" if ref else name, "is_reference": str(ref).lower()})
        sid = r.json()["id"]; ids[name] = sid
        for _ in range(120):
            m = c.get(f"/api/swings/{sid}", auth=auth).json()
            if m["status"] in ("done", "error"): break
            time.sleep(0.25)
        assert m["status"] == "done", m
        print(name, m["result"]["view"], m["result"]["counts"], m["result"]["video"]["stills"])
    m = c.get(f"/api/swings/{ids['mine_fo']}", auth=auth).json()
    print("comparison:", m["comparison"]["ref_label"], len(m["comparison"]["rows"]), "rows")
    m2 = c.get(f"/api/swings/{ids['mine_dtl']}", auth=auth).json()
    assert "comparison" not in m2  # no DTL reference yet
    r = c.get(f"/media/{ids['mine_fo']}/annotated.mp4", auth=auth, headers={"Range": "bytes=0-99"})
    print("range:", r.status_code, r.headers.get("content-range"))
    assert r.status_code == 206
    assert c.get(f"/media/{ids['mine_fo']}/meta.json", auth=auth).status_code == 404
    print("list:", len(c.get("/api/swings", auth=auth).json()))
    print("ffprobe:", subprocess.run(["ffprobe","-v","error","-show_entries","stream=codec_name,width,height,r_frame_rate,nb_frames","-of","csv=p=0",f"{tmp}/swings/{ids['mine_dtl']}/annotated.mp4"],capture_output=True,text=True).stdout.strip())
    print("TMP", tmp, ids)
print("E2E OK")
