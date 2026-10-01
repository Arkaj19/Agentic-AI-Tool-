"""
The Databricks pipeline for MARC (the sap-migration-agent flow as a LangGraph graph).

    connect -> silver -> rulebook -> approve -> codegen -> transform -> gold -> validate -> report

    connect    test the workspace and SQL warehouse
    silver     upload the ECC file picked in SharePoint to a Volume, rebuild the silver table (all strings)
    rulebook   fetch the rule book text from SharePoint (shown); load the local rule book (used)
    approve    the rule book was approved when the run was started from the Rulebook tab
    codegen    reuse the notebook when the rule book is unchanged, else the LLM writes, reviews and checks it
    transform  run the notebook as a job; on a runtime error the LLM fixes the code and it runs again
    gold       count the gold table and keep a preview for the UI
    validate   run every validation rule's check_sql (PASS when 0 rows fail) + row-level results
    report     row-validation Excel, generated code, rule book
"""
from __future__ import annotations

import json
import shutil
import time
from typing import TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph

from app import labels
from app.config import settings
from app.connectors import source
from app.databricks import client, codegen, report as dbx_report, rulebook
from app.databricks.row_validation import add_row_validation
from app.graph.pipeline import _add_output, _set_step, node
from app.store import runs

NOTEBOOK_NAME = "agentic_tool/marc_transformation"   # kept apart from the standalone agent's notebook
JOB_NAME = "agentic_tool_marc_migration"
POLL_SECONDS = 10


class State(TypedDict, total=False):
    run_id: str


def _dbx(rid: str, **fields) -> None:
    runs.update(rid, lambda r: r.setdefault("dbx", {}).update(fields))


def _log(rid: str, step: str, message: str, level: str = "info") -> None:
    runs.emit(rid, "log", message, step=step, level=level)


def _notebook_path() -> str:
    return f"{settings.DATABRICKS_NOTEBOOK_ROOT.rstrip('/')}/{NOTEBOOK_NAME}"


def _rules():
    t, v = rulebook.split(rulebook.load_rules())
    t_text = rulebook.transformation_text(t)
    return t, v, t_text, rulebook.rules_hash(t_text)


def _code_path(rid: str):
    return runs.run_dir(rid) / "notebook_code.py"


# -- nodes ---------------------------------------------------------------------------------------

@node("connect")
def connect(state: State, rid: str):
    info = client.test_connection()
    _dbx(rid, connection=info)
    return {}, f"Connected as {info['user']} · warehouse {info['warehouse']}"


@node("silver")
def silver(state: State, rid: str):
    run = runs.get(rid)
    df, f = source.load_table(run["file"])
    _log(rid, "silver", f"Read {len(df):,} rows from {f['name']} in SharePoint")
    sap = labels.to_sap(df) if "Material" in df.columns else df
    if "MATNR" not in sap or "WERKS" not in sap:
        raise ValueError("The ECC file has no material / plant columns")
    cols = client.table_columns(settings.DBX_SILVER_TABLE) or list(sap.columns)
    out = pd.DataFrame({c: (sap[c] if c in sap else "") for c in cols})
    # Excel dates arrive as '2024-05-15 00:00:00'; the rule book reads ECC dates as dd-MM-yyyy.
    for c in out.columns:
        v = out[c].astype(str)
        iso = v.str.match(r"^\d{4}-\d{2}-\d{2}( 00:00:00)?$")
        if iso.any():
            out.loc[iso, c] = pd.to_datetime(v[iso].str[:10], format="%Y-%m-%d").dt.strftime("%d-%m-%Y")
    missing = [c for c in cols if c not in sap]
    if missing:
        _log(rid, "silver", f"{len(missing)} silver columns not in the file, loaded blank: {', '.join(missing[:12])}", "warn")
    vol_file = f"{settings.DATABRICKS_VOLUME_PATH.rstrip('/')}/agentic_tool/{rid}.csv"
    client.upload_file(vol_file, out.to_csv(index=False).encode("utf-8"))
    _log(rid, "silver", f"Uploaded to {vol_file}")
    col_list = ", ".join(f"`{c}`" for c in cols)
    client.run_sql(f"CREATE OR REPLACE TABLE {settings.DBX_SILVER_TABLE} AS SELECT {col_list} FROM read_files("
                   f"'{vol_file}', format => 'csv', header => true, inferSchema => false)")
    n = client.scalar(f"SELECT count(*) FROM {settings.DBX_SILVER_TABLE}")
    by_plant = client.run_sql(f"SELECT WERKS, count(*) FROM {settings.DBX_SILVER_TABLE} GROUP BY WERKS ORDER BY 2 DESC")
    _dbx(rid, silverTable=settings.DBX_SILVER_TABLE, silverRows=n, volumeFile=vol_file,
         silverPlants={p: int(c) for p, c in by_plant})
    runs.update(rid, lambda r: r["metrics"].update(eccRows=len(df), silverRows=n))
    return {}, f"{n:,} rows loaded into {settings.DBX_SILVER_TABLE}"


@node("rulebook")
def load_rulebook(state: State, rid: str):
    shared = rulebook.fetch_shared()
    if shared["found"]:
        _log(rid, "rulebook", f"Fetched the rule book from SharePoint: {shared['path']}")
    else:
        _log(rid, "rulebook", f"Rule book not found in SharePoint at {shared['path']}", "warn")
    t, v, t_text, h = _rules()
    _dbx(rid, ruleHash=h, ruleCounts={"transformation": len(t), "validation": len(v)},
         sharedRulebook={k: shared.get(k) for k in ("found", "path", "name")})
    return {}, f"{len(t)} transformation rules, {len(v)} validation rules"


@node("approve")
def approve(state: State, rid: str):
    run = runs.get(rid)
    if not run["gates"]:
        runs.update(rid, lambda r: r["gates"].append({
            "id": "G1", "round": 1, "status": "approved", "title": "Approve Databricks rule book",
            "requested": r["created"], "decidedAt": r.get("approvedAt"), "decidedBy": r.get("approvedBy"),
            "comment": "", "proposal": {}}))
    return {}, f"Approved by {run.get('approvedBy') or 'user'}"


@node("codegen")
def generate(state: State, rid: str):
    _, _, t_text, h = _rules()
    path = _notebook_path()
    existing = client.read_notebook(path)
    if existing and codegen.get_hash(existing) == h:
        code = codegen.strip_marker(existing)
        _dbx(rid, notebookPath=path, codeReused=True)
        summary = "Rule book unchanged — reused the existing notebook"
    else:
        _log(rid, "codegen", "The AI is writing the PySpark notebook from the transformation rules")
        code = codegen.generate_code(t_text, log=lambda m: _log(rid, "codegen", m))
        if not code:
            raise RuntimeError("Code generation failed the static checks")
        _dbx(rid, notebookPath=path, codeReused=False)
        summary = f"Notebook written by the AI ({len(code.splitlines())} lines)"
    _code_path(rid).write_text(code, encoding="utf-8")
    return {}, summary


def _deploy(rid: str, code: str, h: str) -> str:
    target = codegen.target_table(code) or settings.DBX_GOLD_TABLE
    src = codegen.with_marker(code, h)
    rr = rulebook.row_rules()
    if rr:
        src = add_row_validation(src, rr, target, f"{target}_row_validation")
    client.create_notebook(_notebook_path(), src)
    return target


@node("transform")
def transform(state: State, rid: str):
    _, _, t_text, h = _rules()
    code = _code_path(rid).read_text(encoding="utf-8")
    attempts: list[dict] = []
    for n in range(1, settings.DBX_MAX_RUN_ATTEMPTS + 1):
        target = _deploy(rid, code, h)
        job = client.start_job(_notebook_path(), JOB_NAME)
        att = {"attempt": n, "runId": job["run_id"], "status": "running", "started": runs.now()}
        attempts.append(att)
        _dbx(rid, jobId=job["job_id"], attempts=attempts, goldTable=target)
        _log(rid, "transform", f"Attempt {n}: job run {job['run_id']} started")
        t0 = time.time()
        while True:
            st = client.run_state(job["run_id"])
            att["url"] = st["url"]
            if st["life_cycle"] in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
                break
            mins, secs = divmod(int(time.time() - t0), 60)
            _set_step(rid, "transform", summary=f"Attempt {n}: {(st['life_cycle'] or 'pending').lower()} · {mins}m {secs:02d}s")
            _dbx(rid, attempts=attempts)
            runs.emit(rid, "progress", "", step="transform")
            time.sleep(POLL_SECONDS)
        if st["result"] == "SUCCESS":
            att.update(status="succeeded", finished=runs.now())
            _dbx(rid, attempts=attempts)
            break
        out = client.run_output(job["run_id"])
        error = f"{out.get('error')}\n{(out.get('error_trace') or '')[:3000]}"
        att.update(status="failed", finished=runs.now(), error=(out.get("error") or st["message"] or "failed")[:300])
        _dbx(rid, attempts=attempts)
        _log(rid, "transform", f"Attempt {n} failed: {att['error']}", "warn")
        if n == settings.DBX_MAX_RUN_ATTEMPTS:
            raise RuntimeError(f"Transformation failed after {n} attempts: {att['error']}")
        _log(rid, "transform", "The AI is fixing the code from the error message")
        code = codegen.fix_code(t_text, code, error)
        issue = codegen.static_issues(code)
        if issue:
            raise RuntimeError(f"The AI fix failed the static check: {issue}")
        att["fixed"] = True
        _dbx(rid, attempts=attempts, codeReused=False)
        _code_path(rid).write_text(code, encoding="utf-8")
    ok = attempts[-1]
    return {}, (f"Succeeded on attempt {ok['attempt']} after an AI fix" if len(attempts) > 1
                else "Notebook ran successfully")


@node("gold")
def gold(state: State, rid: str):
    table = runs.get(rid)["dbx"].get("goldTable") or settings.DBX_GOLD_TABLE
    n = client.scalar(f"SELECT count(*) FROM {table}")
    by_plant = client.run_sql(f"SELECT WERKS, count(*) FROM {table} GROUP BY WERKS ORDER BY 1")
    cols, rows = client.query(f"SELECT * FROM {table} LIMIT {settings.DBX_PREVIEW_ROWS}")
    (runs.run_dir(rid) / "gold_preview.json").write_text(json.dumps({"columns": cols, "rows": rows}), encoding="utf-8")
    plants = {p: int(c) for p, c in by_plant}
    _dbx(rid, goldRows=n, goldPlants=plants)
    runs.update(rid, lambda r: r["metrics"].update(loadRows=n))
    return {}, f"{n:,} rows in {table}" + (f" ({', '.join(f'{p}: {c:,}' for p, c in plants.items())})" if plants else "")


@node("validate")
def validate(state: State, rid: str):
    _, v_rules, _, _ = _rules()
    checks = []
    for r in v_rules:
        if not r["check_sql"]:
            status, detail, failed = "fail", "No check_sql in the rule book", None
        else:
            try:
                failed = client.scalar(r["check_sql"])
                status, detail = ("pass" if failed == 0 else "fail"), f"{failed:,} failing"
            except Exception as exc:
                status, detail, failed = "fail", f"Check could not run: {str(exc)[:160]}", None
        checks.append({"id": r["rule_id"], "name": r["rule_text"], "status": status, "detail": detail, "count": failed})
        _log(rid, "validate", f"{r['rule_id']}: {status.upper()} ({detail})")
    table = runs.get(rid)["dbx"].get("goldTable") or settings.DBX_GOLD_TABLE
    row_counts = {}
    try:
        row_counts = {s: int(c) for s, c in client.run_sql(
            f"SELECT _row_status, count(*) FROM {table}_row_validation GROUP BY _row_status")}
    except Exception as exc:
        _log(rid, "validate", f"Row-level results not available: {str(exc)[:120]}", "warn")
    passed = sum(c["status"] == "pass" for c in checks)
    res = {"title": "Validation · rule book checks", "subtitle": f"SQL checks on {table}",
           "checks": checks, "passed": passed == len(checks) and bool(checks),
           "metrics": {"rulesPassed": passed, "rulesTotal": len(checks), "rowPass": row_counts.get("PASS", 0),
                       "rowFail": row_counts.get("FAIL", 0)}}
    runs.update(rid, lambda r: r.update(validation=res))
    return {}, f"{passed} of {len(checks)} rules passed"


@node("report")
def report(state: State, rid: str):
    run = runs.get(rid)
    table = run["dbx"].get("goldTable") or settings.DBX_GOLD_TABLE
    rule_results = [{"rule_id": c["id"], "description": c["name"], "status": c["status"].upper(),
                     "details": c["detail"]} for c in run["validation"]["checks"]]
    name = f"MARC_row_validation_{rid}.xlsx"
    try:
        dbx_report.export_row_validation_excel(f"{table}_row_validation", str(runs.run_dir(rid) / name),
                                               rule_results=rule_results, title="MARC", max_rows=50000)
        _add_output(rid, name, "report", "Row-by-row validation report")
    except Exception as exc:
        _log(rid, "report", f"Excel export failed: {str(exc)[:160]}", "warn")
    code_name = f"marc_transformation_{rid}.py"
    shutil.copyfile(_code_path(rid), runs.run_dir(rid) / code_name)
    _add_output(rid, code_name, "code", "Generated notebook code")
    rb_name = "MARC_Rule_Book_dbr_agent.csv"
    shutil.copyfile(settings.DBX_RULEBOOK_LOCAL, runs.run_dir(rid) / rb_name)
    _add_output(rid, rb_name, "mapping", "Databricks rule book")
    runs.update(rid, lambda r: r.update(finished=runs.now()))
    return {}, "Validation report and notebook code ready"


def build(checkpointer):
    g = StateGraph(State)
    order = [("connect", connect), ("silver", silver), ("rulebook", load_rulebook), ("approve", approve),
             ("codegen", generate), ("transform", transform), ("gold", gold), ("validate", validate),
             ("report", report)]
    for name, fn in order:
        g.add_node(name, fn)
    g.add_edge(START, order[0][0])
    for (a, _), (b, _) in zip(order, order[1:]):
        g.add_edge(a, b)
    g.add_edge(order[-1][0], END)
    return g.compile(checkpointer=checkpointer)
