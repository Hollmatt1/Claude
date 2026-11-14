"""SwingCheck web app: upload a swing video, get form feedback."""
from __future__ import annotations

import json
import os
import queue
import secrets
import shutil
import threading
import time
import traceback
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from . import analyze as A
from . import pose, render

DATA = Path(os.environ.get("DATA_DIR", "./data")) / "swings"
DATA.mkdir(parents=True, exist_ok=True)
STATIC = Path(__file__).parent / "static"
APP_USER = os.environ.get("APP_USER", "golf")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "600"))
MEDIA_NAMES = {"annotated.mp4"} | {f"{p}.jpg" for p in A.PHASES}

security = HTTPBasic(auto_error=False)


def auth(creds: HTTPBasicCredentials | None = Depends(security)):
    if not APP_PASSWORD:
        return
    ok = creds is not None and secrets.compare_digest(creds.username, APP_USER) and \
        secrets.compare_digest(creds.password, APP_PASSWORD)
    if not ok:
        raise HTTPException(401, "Login required", headers={"WWW-Authenticate": "Basic"})


app = FastAPI(title="SwingCheck", dependencies=[Depends(auth)])


# ------------------------------------------------------------- storage

def _dir(sid: str) -> Path:
    if not sid.isalnum():
        raise HTTPException(404)
    return DATA / sid


def load_meta(sid: str) -> dict:
    p = _dir(sid) / "meta.json"
    if not p.exists():
        raise HTTPException(404, "Swing not found")
    return json.loads(p.read_text())


def save_meta(meta: dict):
    d = _dir(meta["id"])
    tmp = d / "meta.json.tmp"
    tmp.write_text(json.dumps(meta, indent=1))
    tmp.replace(d / "meta.json")


def all_metas() -> list[dict]:
    out = []
    for d in DATA.iterdir():
        p = d / "meta.json"
        if p.exists():
            try:
                out.append(json.loads(p.read_text()))
            except json.JSONDecodeError:
                pass
    return sorted(out, key=lambda m: m["created"], reverse=True)


def _summary(m: dict) -> dict:
    r = m.get("result") or {}
    return {k: m.get(k) for k in ("id", "created", "status", "label", "note", "is_reference", "error")} | {
        "view": r.get("view") or m.get("view_hint"), "counts": r.get("counts"),
        "thumb": f"/media/{m['id']}/address.jpg" if m.get("status") == "done" else None,
    }


# ------------------------------------------------------------- worker

jobs: "queue.Queue[str]" = queue.Queue()


def process(sid: str):
    meta = load_meta(sid)
    d = _dir(sid)
    meta.update(status="processing", progress=0.0)
    save_meta(meta)
    last = [0.0]

    def progress(frac):
        if time.time() - last[0] > 1:
            last[0] = time.time()
            meta["progress"] = round(frac * 0.8, 3)
            save_meta(meta)

    try:
        data = pose.extract(str(d / meta["input"]), progress=progress)
        result = A.analyze(data["landmarks"], data["times"], view=meta.get("view_hint", "auto"))
        meta["progress"] = 0.85
        save_meta(meta)
        media = render.render(str(d / meta["input"]), data, result, str(d))
        result.pop("_smoothed", None)
        result.pop("_ref", None)
        result["video"] = {"fps": data["fps"], "stride": data["stride"], "width": data["width"],
                           "height": data["height"], **media}
        meta.update(status="done", progress=1.0, result=result)
        if os.environ.get("KEEP_ORIGINALS", "0") != "1":
            (d / meta["input"]).unlink(missing_ok=True)
            meta["input_deleted"] = True
    except A.AnalysisError as e:
        meta.update(status="error", error=str(e))
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        meta.update(status="error", error=f"Processing failed: {e}")
    save_meta(meta)


def worker():
    while True:
        sid = jobs.get()
        try:
            process(sid)
        except Exception:  # noqa: BLE001
            traceback.print_exc()


@app.on_event("startup")
def start_worker():
    for m in sorted(all_metas(), key=lambda m: m["created"]):
        if m["status"] in ("queued", "processing"):
            jobs.put(m["id"])
    threading.Thread(target=worker, daemon=True).start()


# ------------------------------------------------------------- API

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.post("/api/swings")
def upload(file: UploadFile = File(...), view: str = Form("auto"), label: str = Form(""),
           note: str = Form(""), is_reference: bool = Form(False)):
    if view not in ("auto", "face_on", "dtl"):
        view = "auto"
    sid = uuid.uuid4().hex[:12]
    d = DATA / sid
    d.mkdir(parents=True)
    ext = Path(file.filename or "video.mov").suffix.lower()[:6] or ".mov"
    dest = d / f"input{ext}"
    size, limit = 0, MAX_UPLOAD_MB * 1024 * 1024
    with dest.open("wb") as f:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                f.close()
                shutil.rmtree(d)
                raise HTTPException(413, f"Video is over {MAX_UPLOAD_MB} MB. Trim it to just the swing.")
            f.write(chunk)
    meta = {"id": sid, "created": time.time(), "status": "queued", "progress": 0.0, "input": dest.name,
            "filename": file.filename, "view_hint": view, "label": label.strip()[:80],
            "note": note.strip()[:500], "is_reference": bool(is_reference)}
    save_meta(meta)
    jobs.put(sid)
    return {"id": sid}


@app.get("/api/swings")
def list_swings():
    return [_summary(m) for m in all_metas()]


@app.get("/api/swings/{sid}")
def get_swing(sid: str, ref: str | None = None):
    m = load_meta(sid)
    m.pop("input", None)
    if m.get("status") == "done":
        refs = [r for r in all_metas() if r.get("is_reference") and r["status"] == "done"
                and r["id"] != sid and r["result"]["view"] == m["result"]["view"]]
        m["available_refs"] = [{"id": r["id"], "label": r.get("label") or "Reference"} for r in refs]
        chosen = next((r for r in refs if r["id"] == ref), None) if ref else (refs[0] if refs else None)
        if chosen:
            m["comparison"] = {"ref_id": chosen["id"], "ref_label": chosen.get("label") or "Reference",
                               "ref_stills": chosen["result"]["video"]["stills"],
                               "rows": A.compare(m["result"], chosen["result"])}
    return m


@app.patch("/api/swings/{sid}")
def update_swing(sid: str, body: dict):
    m = load_meta(sid)
    for k in ("label", "note"):
        if k in body:
            m[k] = str(body[k])[:500]
    if "is_reference" in body:
        m["is_reference"] = bool(body["is_reference"])
    save_meta(m)
    return _summary(m)


@app.delete("/api/swings/{sid}")
def delete_swing(sid: str):
    load_meta(sid)
    shutil.rmtree(_dir(sid))
    return {"ok": True}


@app.get("/media/{sid}/{name}")
def media(sid: str, name: str):
    if name not in MEDIA_NAMES:
        raise HTTPException(404)
    p = _dir(sid) / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, headers={"Cache-Control": "private, max-age=86400"})
