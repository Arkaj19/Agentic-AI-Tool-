"""
The LangGraph migration pipeline for MARC.

    extract -> mapping -> approve -> transform -> validate -> report

"approve" pauses with interrupt() when the mapping has not been approved yet;
a run started from the Rulebook's Approve button passes it straight away.
Large data never goes through the graph state: nodes read and write files in
the run folder.
"""
from __future__ import annotations

import json
import sqlite3
from functools import wraps
from typing import TypedDict

import pandas as pd
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.config import settings
from app.connectors import source
from app.engine import outputs, transform, validate
from app.rulebook import service as mappings
from app.store import runs


class State(TypedDict, total=False):
    run_id: str
    rejected: bool


def _set_step(rid: str, step: str, **fields) -> None:
    def fn(run):
        run["steps"][step].update(fields)
        if fields.get("status") in ("running", "waiting"):
            run["currentStep"] = step
    runs.update(rid, fn)


def node(step: str):
    def deco(fn):
        @wraps(fn)
        def wrapped(state: State):
            rid = state["run_id"]
            if runs.get(rid)["steps"][step]["status"] != "waiting":
                _set_step(rid, step, status="running", started=runs.now(), finished=None)
                runs.emit(rid, "step", f"{step} started", step=step, data={"status": "running"})
            try:
                update, summary = fn(state, rid)
            except GraphInterrupt:
                raise
            except Exception as exc:
                msg = f"{type(exc).__name__}: {exc}"
                _set_step(rid, step, status="failed", finished=runs.now(), summary=msg[:300])
                runs.emit(rid, "step", msg, step=step, level="error", data={"status": "failed"})
                raise
            _set_step(rid, step, status="done", finished=runs.now(), summary=summary)
            runs.emit(rid, "step", summary, step=step, data={"status": "done"})
            return update or {}
        return wrapped
    return deco


def _ecc(rid: str) -> pd.DataFrame:
    return source.load_table(runs.get(rid)["file"])[0]


@node("extract")
def extract(state: State, rid: str):
    df, f = source.load_table(runs.get(rid)["file"])
    runs.update(rid, lambda r: r["metrics"].update(eccRows=len(df)))
    return {}, f"Read {len(df):,} rows from {f['name']}"


@node("mapping")
def mapping(state: State, rid: str):
    meta = mappings.get(runs.get(rid)["mappingId"])
    mappings.link_run(meta["id"], rid)
    r = meta["rules"]
    return {}, f"{len(r['splits'])} split plants, {len(r['one_to_one'])} one-to-one plants"


@node("approve")
def approve(state: State, rid: str):
    run = runs.get(rid)
    meta = mappings.get(run["mappingId"])
    if meta["status"] == "approved":
        if not run["gates"]:
            runs.update(rid, lambda r: r["gates"].append({
                "id": "G1", "round": 1, "status": "approved", "title": "Approve rulebook",
                "requested": meta["created"], "decidedAt": meta["approvedAt"], "decidedBy": meta["approvedBy"],
                "comment": meta.get("approvalComment", ""), "proposal": {"mappingId": meta["id"]}}))
        return {}, f"Approved by {meta['approvedBy']}"

    if not run["gates"]:
        def fn(r):
            r["gates"].append({"id": "G1", "round": 1, "status": "pending", "title": "Approve rulebook",
                               "description": f"Rulebook from {meta['sourceDoc']['name']}",
                               "requested": runs.now(), "proposal": {"mappingId": meta["id"],
                                                                     "lines": meta.get("logicLines", [])}})
            r["status"] = "waiting"
        runs.update(rid, fn)
        _set_step(rid, "approve", status="waiting")
        runs.emit(rid, "gate", "Rulebook needs approval", step="approve", data={"gate": "G1"})

    decision = interrupt({"gate": "G1"})
    ok = decision.get("action") == "approve"
    (mappings.approve if ok else mappings.reject)(meta["id"], decision.get("by", "user"), decision.get("comment", ""))
    runs.update(rid, lambda r: r["gates"][0].update(
        status="approved" if ok else "rejected", decidedAt=runs.now(), decidedBy=decision.get("by", "user"),
        comment=decision.get("comment", "")))
    return ({}, f"Approved by {decision.get('by', 'user')}") if ok else ({"rejected": True}, "Rejected")


@node("transform")
def do_transform(state: State, rid: str):
    run = runs.get(rid)
    s4, plan = transform.run(_ecc(rid), mappings.rules_of(run["mappingId"]))
    s4.to_parquet(runs.run_dir(rid) / "s4.parquet", index=False)
    (runs.run_dir(rid) / "field_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    loaded = int((s4["__status"] == "mapped").sum())
    runs.update(rid, lambda r: r["metrics"].update(loadRows=loaded,
                                                   unmappedRows=int((s4["__status"] == "unmapped").sum())))
    return {}, f"Created {loaded:,} S/4 rows"


@node("validate")
def do_validate(state: State, rid: str):
    run = runs.get(rid)
    plant = settings.VALIDATION_PLANT
    db_path = f"{settings.DATABRICKS_FOLDER}/{settings.DATABRICKS_FILE.format(plant=plant)}".strip("/")
    try:
        db, _ = source.load_table(db_path)
    except FileNotFoundError:
        db = None
    except Exception as exc:
        if "404" in str(exc) or "Not Found" in str(exc):
            db = None
        else:
            raise
    s4 = pd.read_parquet(runs.run_dir(rid) / "s4.parquet")
    res = validate.run(s4, mappings.rules_of(run["mappingId"]), db, db_path)
    runs.update(rid, lambda r: r.update(validation=res))
    n = sum(c["status"] == "pass" for c in res["checks"])
    return {}, f"Plant {plant}: {n} of {len(res['checks'])} checks passed"


@node("report")
def report(state: State, rid: str):
    s4 = pd.read_parquet(runs.run_dir(rid) / "s4.parquet")
    plan = json.loads((runs.run_dir(rid) / "field_plan.json").read_text(encoding="utf-8"))
    load_name = f"S_MARC_{rid}.xlsx"
    n = outputs.write_load_file(s4, plan, runs.run_dir(rid) / load_name)
    _add_output(rid, load_name, "s4", "S/4 load file (S_MARC)")
    runs.update(rid, lambda r: r.update(finished=runs.now()))
    rep_name = f"Validation_Report_{rid}.xlsx"
    outputs.write_report(runs.get(rid), runs.run_dir(rid) / rep_name)
    _add_output(rid, rep_name, "report", "Validation report")
    mp = mappings.xlsx_path(runs.get(rid)["mappingId"])
    (runs.run_dir(rid) / mp.name).write_bytes(mp.read_bytes())
    _add_output(rid, mp.name, "mapping", "Rulebook")
    return {}, f"S/4 file ({n:,} rows) and validation report ready"


def _add_output(rid: str, name: str, kind: str, label: str) -> None:
    size = (runs.run_dir(rid) / name).stat().st_size

    def fn(r):
        r["outputs"] = [o for o in r["outputs"] if o["name"] != name]
        r["outputs"].append({"name": name, "kind": kind, "label": label, "size": size, "created": runs.now()})
    runs.update(rid, fn)


def build(checkpointer):
    g = StateGraph(State)
    for name, fn in [("extract", extract), ("mapping", mapping), ("approve", approve),
                     ("transform", do_transform), ("validate", do_validate), ("report", report)]:
        g.add_node(name, fn)
    g.add_edge(START, "extract")
    g.add_edge("extract", "mapping")
    g.add_edge("mapping", "approve")
    g.add_conditional_edges("approve", lambda s: END if s.get("rejected") else "transform", ["transform", END])
    g.add_edge("transform", "validate")
    g.add_edge("validate", "report")
    g.add_edge("report", END)
    return g.compile(checkpointer=checkpointer)


def make_checkpointer():
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        return SqliteSaver(sqlite3.connect(settings.DATA_DIR / "checkpoints.sqlite", check_same_thread=False))
    except ImportError:
        from langgraph.checkpoint.memory import InMemorySaver
        return InMemorySaver()
