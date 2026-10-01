"""
Run records and their event log.

    data/runs/<run_id>/run.json      current state of the run (steps, gates, results)
    data/runs/<run_id>/events.jsonl  append-only progress log, streamed to the UI
    data/runs/<run_id>/*.parquet     intermediate data, *.xlsx outputs
"""
from __future__ import annotations

import json
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

STEPS = [
    {"id": "extract", "label": "Fetch data", "agent": "Extraction"},
    {"id": "mapping", "label": "Rulebook", "agent": "Rulebook"},
    {"id": "approve", "label": "Approve", "agent": "Approval", "gate": True},
    {"id": "transform", "label": "Transform", "agent": "Transformation"},
    {"id": "validate", "label": "Validate", "agent": "Validation"},
    {"id": "report", "label": "Report", "agent": "Reporting"},
]
STEPS_DBX = [
    {"id": "connect", "label": "Connect", "agent": "Databricks connection"},
    {"id": "silver", "label": "Silver layer", "agent": "Silver layer"},
    {"id": "rulebook", "label": "Rule book", "agent": "Rule book"},
    {"id": "approve", "label": "Approve", "agent": "Approval", "gate": True},
    {"id": "codegen", "label": "Generate code", "agent": "Code generation"},
    {"id": "transform", "label": "Transform", "agent": "Transformation"},
    {"id": "gold", "label": "Gold layer", "agent": "Gold layer"},
    {"id": "validate", "label": "Validate", "agent": "Validation"},
    {"id": "report", "label": "Report", "agent": "Reporting"},
]
ENGINES = {"embedded": STEPS, "databricks": STEPS_DBX}
_DIR = settings.DATA_DIR / "runs"
_locks: dict[str, threading.Lock] = {}
_glock = threading.Lock()
_events: dict[str, list[dict]] = {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _lock(rid: str) -> threading.Lock:
    with _glock:
        return _locks.setdefault(rid, threading.Lock())


def run_dir(rid: str) -> Path:
    return _DIR / rid


def _path(rid: str) -> Path:
    return run_dir(rid) / "run.json"


def create(*, file: str, mapping_id: str | None, mapping_doc: str, started_by: str = "user",
           engine: str = "embedded") -> dict:
    rid = f"RUN-MARC-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{secrets.token_hex(2)}"
    run_dir(rid).mkdir(parents=True, exist_ok=True)
    run = {"id": rid, "object": "MARC", "engine": engine, "file": file, "mappingId": mapping_id,
           "mappingDoc": mapping_doc,
           "status": "queued", "metrics": {"eccRows": None, "loadRows": None, "unmappedRows": None},
           "created": now(), "started": None, "finished": None, "startedBy": started_by,
           "currentStep": None,
           "steps": {s["id"]: {"status": "queued", "started": None, "finished": None, "summary": "",
                               "detail": {}} for s in ENGINES[engine]},
           "gates": [], "validation": None, "outputs": [], "error": None}
    save(run)
    return run


def save(run: dict) -> None:
    p = _path(run["id"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(run, indent=2, default=str), encoding="utf-8")
    # On Windows the replace fails while another request is reading run.json; retry briefly.
    for attempt in range(40):
        try:
            tmp.replace(p)
            return
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(0.05)


def get(rid: str) -> dict:
    p = _path(rid)
    if not p.exists():
        raise KeyError(f"run {rid} not found")
    for attempt in range(40):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (PermissionError, json.JSONDecodeError):
            if attempt == 39:
                raise
            time.sleep(0.05)


def update(rid: str, fn) -> dict:
    with _lock(rid):
        run = get(rid)
        fn(run)
        save(run)
        return run


def list_all() -> list[dict]:
    out = []
    for p in _DIR.glob("*/run.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return sorted(out, key=lambda r: r["created"], reverse=True)


# -- events ----------------------------------------------------------------------

def _load_events(rid: str) -> list[dict]:
    if rid not in _events:
        p = run_dir(rid) / "events.jsonl"
        _events[rid] = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] \
            if p.exists() else []
    return _events[rid]


def emit(rid: str, type_: str, message: str = "", *, step: str | None = None, level: str = "info",
         data: dict | None = None) -> dict:
    with _lock(rid + ":ev"):
        evs = _load_events(rid)
        ev = {"seq": len(evs) + 1, "ts": now(), "type": type_, "step": step, "level": level,
              "message": message, "data": data or {}}
        evs.append(ev)
        with open(run_dir(rid) / "events.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, default=str) + "\n")
        return ev


def events_since(rid: str, seq: int = 0) -> list[dict]:
    return [e for e in _load_events(rid) if e["seq"] > seq]
