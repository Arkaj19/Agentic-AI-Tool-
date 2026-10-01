"""
FastAPI app: REST API for the React frontend plus an SSE progress stream.
Run from the project root:
    backend\\.venv\\Scripts\\python -m uvicorn --app-dir backend app.main:app --port 8010
"""
from __future__ import annotations

import asyncio
import json

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from app import labels
from app.config import settings
from app.connectors import source
from app.databricks import client as dbx, rulebook as dbx_rulebook
from app.graph import runner
from app.llm import azure
from app.rulebook import service as mappings
from app.store import runs

app = FastAPI(title="GyanSys Agentic Migration Tool", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=[settings.FRONTEND_ORIGIN, "http://127.0.0.1:5180"],
                   allow_methods=["*"], allow_headers=["*"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
KEY_LABELS = ["Material", "Plant", "Procurement type", "Special procurement", "MRP Type", "MRP Controller",
              "Plant-sp.matl status", "Availability check", "Profit Center", "Purchasing Group"]


@app.on_event("startup")
def _startup() -> None:
    runner.recover_on_startup()


def _fail(exc: Exception, code: int = 400):
    if isinstance(exc, FileNotFoundError) or "404" in str(exc):
        code = 404
    raise HTTPException(status_code=code, detail=str(exc) if code != 502 else f"{type(exc).__name__}: {exc}")


# -- status ----------------------------------------------------------------------------

@app.get("/api/status")
def status(force: bool = False):
    return {"sharepoint": source.status(force),
            "llm": {"configured": azure.available(),
                    "deployment": settings.AZURE_OPENAI_CHAT_DEPLOYMENT if azure.available() else None},
            "databricks": dbx.status(force) if settings.databricks_configured else {"connected": False, "detail": "Not configured"},
            "mappingsFolder": settings.MAPPINGS_FOLDER, "validationPlant": settings.VALIDATION_PLANT}


@app.get("/api/meta")
def meta():
    return {"steps": runs.STEPS, "engines": runs.ENGINES}


# -- SharePoint browsing and previews --------------------------------------------------------

@app.get("/api/files")
def files(path: str = ""):
    try:
        return {"path": path.strip("/"), "items": source.browse(path)}
    except Exception as exc:
        _fail(exc, 502)


@app.get("/api/files/table")
def table_preview(path: str, offset: int = 0, limit: int = Query(50, le=500), columns: str = "key", q: str = ""):
    try:
        df, f = source.load_table(path)
    except ValueError as exc:
        _fail(exc)
    except Exception as exc:
        _fail(exc, 502)
    hm = labels.header_map(list(df.columns), source.detect_table(f["name"]) or "MARC")
    if q:
        col = "Material" if "Material" in df else ("PRODUCT" if "PRODUCT" in df else None)
        if col:
            df = df[df[col].str.contains(q, case=False, regex=False)]
    cols = [c for c in KEY_LABELS if c in df.columns] if columns == "key" else list(df.columns)
    if len(cols) < 3:
        cols = list(df.columns)
    page = df.iloc[offset:offset + limit][cols]
    return {"file": f, "total": int(len(df)), "offset": offset, "allColumns": len(hm),
            "columns": [{"label": c, "field": hm.get(c)} for c in cols], "rows": page.values.tolist()}


@app.get("/api/files/document")
def document_preview(path: str):
    try:
        return source.read_document(path)
    except ValueError as exc:
        _fail(exc)
    except Exception as exc:
        _fail(exc, 502)


# -- rulebook ----------------------------------------------------------------------------------

@app.post("/api/mappings/generate")
def mappings_generate(body: dict = Body(...)):
    if not body.get("path"):
        raise HTTPException(400, "Select a mapping document first")
    try:
        return mappings.generate(body["path"])
    except ValueError as exc:
        _fail(exc)
    except Exception as exc:
        _fail(exc, 502)


@app.get("/api/mappings/{mid}")
def mapping_get(mid: str):
    try:
        return mappings.preview(mid)
    except KeyError as exc:
        _fail(exc, 404)


@app.get("/api/mappings/{mid}/download")
def mapping_download(mid: str):
    p = mappings.xlsx_path(mid)
    if not p.exists():
        raise HTTPException(404, "Rulebook file not found")
    return FileResponse(p, media_type=XLSX, filename=p.name)


@app.post("/api/mappings/{mid}/approve-and-run")
def mapping_approve_and_run(mid: str, body: dict = Body(...)):
    if not body.get("file"):
        raise HTTPException(400, "Select the MARC file in Data Extraction first")
    try:
        mappings.approve(mid, body.get("by", "user"), body.get("comment", ""))
        return {"runId": runner.start(body["file"], mid, by=body.get("by", "user"))["id"]}
    except KeyError as exc:
        _fail(exc, 404)


# -- Databricks pipeline ---------------------------------------------------------------------------

@app.get("/api/databricks/rulebook")
def databricks_rulebook():
    try:
        return dbx_rulebook.overview()
    except FileNotFoundError as exc:
        _fail(exc)


@app.post("/api/databricks/start")
def databricks_start(body: dict = Body(...)):
    if not body.get("file"):
        raise HTTPException(400, "Select the ECC file in Data Extraction first")
    if not settings.databricks_configured:
        raise HTTPException(400, "Databricks is not configured (DATABRICKS_* in backend/.env)")
    return {"runId": runner.start_databricks(body["file"], by=body.get("by", "user"))["id"]}


@app.get("/api/runs/{rid}/gold")
def run_gold(rid: str, offset: int = 0, limit: int = Query(50, le=500)):
    p = runs.run_dir(rid) / "gold_preview.json"
    if not p.exists():
        raise HTTPException(404, "No gold data for this run yet")
    data = json.loads(p.read_text(encoding="utf-8"))
    total = (runs.get(rid).get("dbx") or {}).get("goldRows", len(data["rows"]))
    return {"columns": data["columns"], "rows": data["rows"][offset:offset + limit], "total": int(total),
            "previewRows": len(data["rows"])}


# -- runs ----------------------------------------------------------------------------------------

@app.get("/api/runs")
def runs_list():
    keep = ("id", "engine", "file", "mappingId", "mappingDoc", "status", "created", "started", "finished", "startedBy",
            "currentStep", "error", "metrics", "gates")
    out = []
    for r in runs.list_all():
        v = r.get("validation") or {}
        out.append({k: r.get(k) for k in keep} | {"passed": v.get("passed"), "outputs": len(r["outputs"]),
                                                   "checks": [c["status"] for c in v.get("checks", [])]})
    return {"runs": out}


@app.get("/api/runs/{rid}")
def run_get(rid: str):
    try:
        return {**runs.get(rid), "active": runner.is_active(rid)}
    except KeyError as exc:
        _fail(exc, 404)


@app.get("/api/runs/{rid}/events")
async def run_events(rid: str, request: Request, since: int = 0):
    try:
        runs.get(rid)
    except KeyError as exc:
        _fail(exc, 404)

    async def stream():
        seq, idle = since, 0
        yield "retry: 2000\n\n"
        while not await request.is_disconnected():
            evs = runs.events_since(rid, seq)
            for e in evs:
                seq = e["seq"]
                yield f"id: {seq}\ndata: {json.dumps(e, default=str)}\n\n"
            idle = 0 if evs else idle + 1
            if idle and idle % 40 == 0:
                yield ": keep-alive\n\n"
            if idle > 3 and runs.get(rid)["status"] in ("completed", "failed", "rejected") and not runner.is_active(rid):
                yield "event: end\ndata: {}\n\n"
                break
            await asyncio.sleep(0.35)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/runs/{rid}/gates/{gate}/decision")
def run_decide(rid: str, gate: str, body: dict = Body(...)):
    if body.get("action") not in ("approve", "reject"):
        raise HTTPException(400, "action must be approve or reject")
    try:
        runner.resume(rid, gate.upper(), body)
        return {"ok": True}
    except KeyError as exc:
        _fail(exc, 404)
    except ValueError as exc:
        _fail(exc, 409)


@app.get("/api/runs/{rid}/outputs/{name}")
def run_output(rid: str, name: str):
    p = runs.run_dir(rid) / name
    types = {".xlsx": XLSX, ".py": "text/x-python", ".csv": "text/csv"}
    if not p.exists() or p.parent != runs.run_dir(rid) or p.suffix not in types:
        raise HTTPException(404, "File not found")
    return FileResponse(p, media_type=types[p.suffix], filename=name)


# -- approvals -------------------------------------------------------------------------------------

@app.get("/api/approvals")
def approvals():
    items = [{**g, "runId": r["id"], "file": r["file"], "mappingDoc": r.get("mappingDoc"), "runStatus": r["status"]}
             for r in runs.list_all() for g in r["gates"]]
    pending = [i for i in items if i["status"] == "pending"]
    rest = sorted([i for i in items if i["status"] != "pending"], key=lambda g: g.get("decidedAt") or "", reverse=True)
    return {"items": pending + rest, "pending": len(pending)}
