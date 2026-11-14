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
import zipfile
from pathlib import Path

import numpy as np

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from . import analyze as A
from . import pose, render
from . import session as S

DATA = Path(os.environ.get("DATA_DIR", "./data")) / "swings"
DATA.mkdir(parents=True, exist_ok=True)
STATIC = Path(__file__).parent / "static"
APP_USER = os.environ.get("APP_USER", "golf")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "600"))
SESSION_MIN_S = float(os.environ.get("SESSION_MIN_SECONDS", "25"))   # longer uploads are range sessions
SESSION_SWING_FPS = float(os.environ.get("SESSION_SWING_FPS", "60"))  # analysis frame rate per session swing
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
    out = {k: m.get(k) for k in ("id", "created", "status", "label", "note", "is_reference", "error", "kind",
                                 "index", "peak", "stage", "progress", "practice")} | {
        "view": r.get("view") or m.get("view_hint"), "counts": r.get("counts"), "tracking": r.get("tracking"),
        "thumb": f"/media/{m['id']}/address.jpg" if m.get("status") == "done" else None,
    }
    if m.get("kind") == "session":
        kids = [k for k in (_try_meta(c) for c in m.get("children", [])) if k]
        done = [k for k in kids if k["status"] == "done"]
        out |= {"swings_found": len(m.get("windows") or []), "swings_done": len(done),
                "thumb": f"/media/{done[0]['id']}/address.jpg" if done else None,
                "view": (done[0]["result"]["view"] if done else m.get("view_hint"))}
    return out


def _try_meta(sid: str) -> dict | None:
    try:
        return load_meta(sid)
    except HTTPException:
        return None


PRACTICE_GAP_S = 10.0  # a swing followed by another this soon is probably a practice swing


def mark_practice(kids: list[dict]) -> None:
    """Set k["practice"]: the user's choice if they made one, else True when another swing follows within
    PRACTICE_GAP_S (people rehearse, then hit)."""
    kids = sorted(kids, key=lambda k: k.get("peak") or 0)
    for i, k in enumerate(kids):
        if k.get("practice_set") is not None:
            k["practice"] = bool(k["practice_set"])
            continue
        nxt = kids[i + 1].get("peak") if i + 1 < len(kids) else None
        k["practice"] = nxt is not None and (nxt - (k.get("peak") or 0)) < PRACTICE_GAP_S


def session_report(m: dict) -> dict:
    """Every swing in a session plus how often each check came out good / check / bad."""
    kids = [k for k in (_try_meta(c) for c in m.get("children", [])) if k]
    mark_practice(kids)
    agg: dict[str, dict] = {}
    for k in kids:
        if k["status"] != "done" or k["practice"] or (k["result"].get("tracking") or {}).get("grade") == "poor":
            continue
        for c in k["result"]["checks"]:
            a = agg.setdefault(c["id"], {"id": c["id"], "title": c["title"], "good": 0, "warn": 0, "bad": 0,
                                         "values": [], "tip": None})
            a[c["status"]] += 1
            if c.get("value") is not None:
                a["values"].append(c["value"])
            if c["status"] != "good" and c.get("tip") and not a["tip"]:
                a["tip"] = c["tip"]
    rows = sorted(agg.values(), key=lambda a: (-(a["bad"] * 2 + a["warn"]), a["title"]))
    for a in rows:
        v = a.pop("values")
        a["median"] = round(float(np.median(v)), 2) if v else None
        a["n"] = a["good"] + a["warn"] + a["bad"]
    poor = sum(1 for k in kids if k["status"] == "done" and not k["practice"]
               and (k["result"].get("tracking") or {}).get("grade") == "poor")
    practice = sum(1 for k in kids if k["status"] == "done" and k["practice"])
    return {"swings": [_summary(k) for k in sorted(kids, key=lambda k: k.get("index", 0))], "checks": rows,
            "poor_tracking": poor, "practice": practice, "can_reanalyze": not m.get("input_deleted") and (_dir(m["id"]) / m["input"]).exists()}


# ------------------------------------------------------------- worker

jobs: "queue.Queue[str]" = queue.Queue()


def process(sid: str):
    meta = load_meta(sid)
    if meta.get("kind") == "session":
        return process_session(meta)
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
        fps = SESSION_SWING_FPS if meta.get("session_id") else None
        data = pose.extract(str(d / meta["input"]), progress=progress, target_fps=fps)
        result = A.analyze(data["landmarks"], data["times"], view=meta.get("view_hint", "auto"))
        meta["progress"] = 0.85
        save_meta(meta)
        media = render.render(str(d / meta["input"]), data, result, str(d))
        result.pop("_smoothed", None)
        result.pop("_ref", None)
        result["video"] = {"fps": data["fps"], "stride": data["stride"], "width": data["width"],
                           "height": data["height"], **media}
        meta.update(status="done", progress=1.0, result=result)
        if os.environ.get("KEEP_ORIGINALS", "1") != "1":
            (d / meta["input"]).unlink(missing_ok=True)
            meta["input_deleted"] = True
    except A.AnalysisError as e:
        meta.update(status="error", error=str(e))
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        meta.update(status="error", error=f"Processing failed: {e}")
    save_meta(meta)


def process_session(meta: dict):
    """Find every swing in a long video, cut each into its own swing entry, analyze them in order."""
    d = _dir(meta["id"])
    src = str(d / meta["input"])
    meta.update(status="processing")
    try:
        info = meta.get("info") or S.probe(src)
        meta["info"] = info
        if meta.get("windows") is None:
            meta.update(stage="Finding swings", progress=0.0)
            save_meta(meta)
            last = [0.0]

            def scan_progress(frac):
                if time.time() - last[0] > 2:
                    last[0] = time.time()
                    meta["progress"] = round(frac * 0.3, 3)
                    save_meta(meta)

            lm, t = S.scan(src, info, progress=scan_progress)
            meta["windows"] = S.find_swings(lm, t, info["duration"])
            meta["children"] = []
            save_meta(meta)
        wins = meta["windows"]
        if not wins:
            raise A.AnalysisError("No full swings found. The whole body needs to stay in frame, "
                                  "and chips and putts aren't counted.")
        for i, w in enumerate(wins):
            meta.update(stage=f"Analyzing swing {i + 1} of {len(wins)}", progress=round(0.3 + 0.7 * i / len(wins), 3))
            save_meta(meta)
            cid = f"{meta['id']}s{i + 1:03d}"
            if cid in meta["children"] and _try_meta(cid) and load_meta(cid)["status"] in ("done", "error"):
                continue
            cd = DATA / cid
            if cd.exists():
                shutil.rmtree(cd)
            cd.mkdir(parents=True)
            S.cut(src, w["start"], w["end"], str(cd / "input.mp4"), info)
            base = meta.get("label") or "Swing"
            child = {"id": cid, "created": meta["created"] + i * 0.001, "status": "queued", "progress": 0.0,
                     "input": "input.mp4", "filename": meta.get("filename"), "view_hint": meta.get("view_hint", "auto"),
                     "label": f"{base} #{i + 1}", "note": "", "is_reference": bool(meta.get("is_reference")),
                     "session_id": meta["id"], "index": i + 1, "peak": w["peak"]}
            save_meta(child)
            if cid not in meta["children"]:
                meta["children"].append(cid)
                save_meta(meta)
            process(cid)
        kids = [_try_meta(c) for c in meta["children"]]
        ok = sum(1 for k in kids if k and k["status"] == "done")
        meta.update(status="done", progress=1.0, stage=f"{ok} of {len(wins)} swings analyzed")
        if os.environ.get("KEEP_ORIGINALS", "1") != "1":
            (d / meta["input"]).unlink(missing_ok=True)
            meta["input_deleted"] = True
    except A.AnalysisError as e:
        meta.update(status="error", error=str(e))
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        meta.update(status="error", error=f"Processing failed: {e}")
    save_meta(meta)


def worker():
    try:
        os.nice(10)  # this thread only: Minecraft on the same box keeps priority
    except OSError:
        pass
    while True:
        sid = jobs.get()
        try:
            process(sid)
        except Exception:  # noqa: BLE001
            traceback.print_exc()


@app.on_event("startup")
def start_worker():
    for m in sorted(all_metas(), key=lambda m: m["created"]):
        if m["status"] in ("queued", "processing") and not m.get("session_id"):
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
                raise HTTPException(413, f"Upload is over {MAX_UPLOAD_MB} MB.")
            f.write(chunk)
    common = {"view_hint": view, "note": note.strip()[:500], "is_reference": bool(is_reference)}
    if zipfile.is_zipfile(dest):
        try:
            ids = _unzip_videos(dest, label.strip()[:80], common)
        finally:
            shutil.rmtree(d, ignore_errors=True)
        if not ids:
            raise HTTPException(400, "The zip file has no videos in it.")
        return {"id": ids[0], "ids": ids}
    _register(sid, dest, file.filename, label.strip()[:80], common)
    return {"id": sid, "ids": [sid]}


VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".3gp", ".webm"}


def _register(sid: str, dest: Path, filename: str | None, label: str, common: dict, created: float | None = None):
    """Write the metadata for an uploaded video (a session if it's long) and queue it."""
    meta = {"id": sid, "created": created or time.time(), "status": "queued", "progress": 0.0, "input": dest.name,
            "filename": filename, "label": label} | common
    try:
        info = S.probe(str(dest))
    except Exception:  # noqa: BLE001
        info = None
    if info and info["duration"] > SESSION_MIN_S:
        meta.update(kind="session", info=info)
    save_meta(meta)
    jobs.put(sid)


def _unzip_videos(zpath: Path, label: str, common: dict) -> list[str]:
    """Each video inside the zip becomes its own upload. Folder paths inside the zip are ignored (only the
    file name is used), other files are skipped, and the unpacked total is capped at the upload limit."""
    ids, total, limit = [], 0, MAX_UPLOAD_MB * 1024 * 1024
    with zipfile.ZipFile(zpath) as z:
        members = sorted((i for i in z.infolist() if not i.is_dir()), key=lambda i: i.filename)
        vids = [i for i in members if Path(i.filename).suffix.lower() in VIDEO_EXTS
                and not Path(i.filename).name.startswith(".") and "__MACOSX" not in i.filename]
        now = time.time()
        for n, info in enumerate(vids):
            total += info.file_size
            if total > limit:
                break
            sid = uuid.uuid4().hex[:12]
            d = DATA / sid
            d.mkdir(parents=True)
            name = Path(info.filename).name
            dest = d / f"input{Path(name).suffix.lower()}"
            with z.open(info) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out, 1024 * 1024)
            lab = f"{label} · video {n + 1}" if label and len(vids) > 1 else (label or Path(name).stem)
            _register(sid, dest, name, lab, common, created=now + n * 0.001)
            ids.append(sid)
    return ids


@app.get("/api/swings")
def list_swings():
    return [_summary(m) for m in all_metas() if not m.get("session_id")]


@app.get("/api/swings/{sid}")
def get_swing(sid: str, ref: str | None = None):
    m = load_meta(sid)
    m.pop("input", None)
    if m.get("kind") == "session":
        return m | session_report(m)
    if m.get("session_id"):
        parent = _try_meta(m["session_id"])
        m["session_label"] = (parent or {}).get("label") or "Session"
        m["session_size"] = len((parent or {}).get("children") or [])
        sibs = [k for k in (_try_meta(c) for c in (parent or {}).get("children", [])) if k]
        mark_practice(sibs)
        m["practice"] = next((k["practice"] for k in sibs if k["id"] == sid), False)
    m["available_refs"] = []
    if m.get("status") == "done" and not m.get("is_reference"):  # a pro's own page has nothing to compare
        refs = [r for r in all_metas() if r.get("is_reference") and r["status"] == "done" and r.get("result")
                and r["id"] != sid and r["result"]["view"] == m["result"]["view"]]
        m["available_refs"] = [{"id": r["id"], "label": r.get("label") or "Reference"} for r in refs]
        if not ref and refs:
            # Prefer a reference for the same club: "8 iron" -> a reference labelled "Iron".
            words = set((m.get("label") or "").lower().replace("·", " ").split())
            club = next((w for w in ("driver", "wood", "hybrid", "iron", "wedge") if w in words), None)
            refs.sort(key=lambda r: club is None or club not in (r.get("label") or "").lower())
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
    if "practice" in body and m.get("session_id"):
        m["practice_set"] = None if body["practice"] is None else bool(body["practice"])
    save_meta(m)
    return _summary(m)


@app.post("/api/swings/{sid}/reanalyze")
def reanalyze(sid: str):
    """Run the analysis again on the kept original (after an update to the tracking or checks)."""
    m = load_meta(sid)
    if m.get("session_id") or m.get("input_deleted") or not (_dir(sid) / m["input"]).exists():
        raise HTTPException(409, "The original video wasn't kept, so this can't be re-analyzed. Upload it again.")
    if m["status"] in ("queued", "processing"):
        return _summary(m)
    if m.get("kind") == "session":
        for c in m.get("children") or []:
            if (DATA / c).is_dir() and c.isalnum():
                shutil.rmtree(DATA / c)
        m.update(windows=None, children=[])
    m.update(status="queued", progress=0.0, error=None, stage=None)
    m.pop("result", None)
    save_meta(m)
    jobs.put(sid)
    return _summary(m)


@app.delete("/api/swings/{sid}")
def delete_swing(sid: str):
    m = load_meta(sid)
    for c in m.get("children") or []:
        if (DATA / c).is_dir() and c.isalnum():
            shutil.rmtree(DATA / c)
    if m.get("session_id"):
        parent = _try_meta(m["session_id"])
        if parent and sid in parent.get("children", []):
            parent["children"].remove(sid)
            save_meta(parent)
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
