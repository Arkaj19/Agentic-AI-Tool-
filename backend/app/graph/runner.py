"""
Runs graph invocations in background threads. A run's thread id is its run
id, so a paused run resumes from the SQLite checkpoint, even after a restart.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from langgraph.types import Command

from app.graph import pipeline
from app.rulebook import service as mappings
from app.store import runs

_checkpointer = pipeline.make_checkpointer()
graph = pipeline.build(_checkpointer)
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="run")
_active: set[str] = set()
_alock = threading.Lock()


def _config(rid: str) -> dict:
    return {"configurable": {"thread_id": rid}, "recursion_limit": 60}


def _invoke(rid: str, payload) -> None:
    with _alock:
        _active.add(rid)
    try:
        runs.update(rid, lambda r: r.update(status="running", started=r.get("started") or runs.now()))
        runs.emit(rid, "run", "Run resumed" if isinstance(payload, Command) else "Run started",
                  data={"status": "running"})
        graph.invoke(payload, _config(rid))
        snap = graph.get_state(_config(rid))
        run = runs.get(rid)
        if snap.next:
            runs.update(rid, lambda r: r.update(status="waiting"))
            runs.emit(rid, "run", "Waiting for a decision", data={"status": "waiting"})
        elif run["gates"] and any(g["id"] == "G1" and g["status"] == "rejected" for g in run["gates"]):
            runs.update(rid, lambda r: r.update(status="rejected", finished=runs.now(), currentStep=None))
            runs.emit(rid, "run", "Run stopped: mapping rejected", data={"status": "rejected"})
        else:
            runs.update(rid, lambda r: r.update(status="completed", finished=runs.now(), currentStep=None))
            runs.emit(rid, "run", "Run completed", data={"status": "completed"})
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        runs.update(rid, lambda r: r.update(status="failed", error=msg[:500], finished=runs.now()))
        runs.emit(rid, "run", msg, level="error", data={"status": "failed"})
    finally:
        with _alock:
            _active.discard(rid)


def start(file: str, mapping_id: str, *, by: str = "user") -> dict:
    meta = mappings.get(mapping_id)
    run = runs.create(file=file, mapping_id=mapping_id, mapping_doc=meta["sourceDoc"]["name"], started_by=by)
    runs.emit(run["id"], "run", f"Run created for {file}", data={"status": "queued"})
    _pool.submit(_invoke, run["id"], {"run_id": run["id"]})
    return run


def resume(rid: str, gate: str, decision: dict) -> dict:
    run = runs.get(rid)
    pending = [g for g in run["gates"] if g["id"] == gate and g["status"] == "pending"]
    if not pending:
        raise ValueError(f"No pending {gate} decision on {rid}")
    with _alock:
        if rid in _active:
            raise ValueError(f"{rid} is still running")
    runs.emit(rid, "gate", f"{gate} decision received from {decision.get('by', 'user')}",
              step="approve", data={"gate": gate, "status": "decided"})
    _pool.submit(_invoke, rid, Command(resume=decision))
    return run


def recover_on_startup() -> None:
    """Runs that were mid-step when the server stopped cannot continue that
    step; mark them failed. Waiting runs stay resumable from the checkpoint."""
    for r in runs.list_all():
        if r["status"] in ("running", "queued"):
            def fn(x):
                x.update(status="failed", error="Server restarted while the run was in progress",
                         finished=runs.now())
                for s in x["steps"].values():
                    if s["status"] == "running":
                        s["status"] = "failed"
            runs.update(r["id"], fn)


def is_active(rid: str) -> bool:
    return rid in _active
