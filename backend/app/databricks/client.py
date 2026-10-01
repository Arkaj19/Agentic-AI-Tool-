"""
Databricks workspace access (ported from sap-migration-agent tools/databricks_tools.py):
connection test, SQL through the warehouse, notebooks, jobs and Volume uploads.
"""
from __future__ import annotations

import base64
import io
import posixpath
import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import NotebookTask, Task
from databricks.sdk.service.sql import Disposition, Format, StatementState
from databricks.sdk.service.workspace import ExportFormat, ImportFormat, Language

from app.config import settings

_w: WorkspaceClient | None = None
_status: dict = {"at": 0.0, "value": None}


class NotConfigured(RuntimeError):
    pass


def ws() -> WorkspaceClient:
    global _w
    if not settings.databricks_configured:
        raise NotConfigured("Databricks is not configured (DATABRICKS_* in backend/.env)")
    if _w is None:
        _w = WorkspaceClient(host=settings.DATABRICKS_HOST, token=settings.DATABRICKS_TOKEN)
    return _w


def host() -> str:
    return settings.DATABRICKS_HOST.rstrip("/")


# -- connection ------------------------------------------------------------------------

def test_connection() -> dict:
    me = ws().current_user.me()
    wh = ws().warehouses.get(settings.DATABRICKS_WAREHOUSE_ID)
    return {"connected": True, "user": me.user_name, "warehouse": wh.name,
            "warehouseState": wh.state.value if wh.state else None, "host": host()}


def status(force: bool = False) -> dict:
    now = time.time()
    if not force and _status["value"] and now - _status["at"] < 60:
        return _status["value"]
    if not settings.databricks_configured:
        value = {"connected": False, "detail": "Not configured"}
    else:
        try:
            value = test_connection()
            value["detail"] = f"{value['user']} · {value['warehouse']}"
        except Exception as exc:
            value = {"connected": False, "detail": f"{type(exc).__name__}: {str(exc)[:160]}"}
    _status.update(at=now, value=value)
    return value


# -- SQL -------------------------------------------------------------------------------

def _execute(statement: str):
    w = ws()
    resp = w.statement_execution.execute_statement(
        warehouse_id=settings.DATABRICKS_WAREHOUSE_ID, statement=statement.strip().rstrip(";"),
        wait_timeout="50s", disposition=Disposition.INLINE, format=Format.JSON_ARRAY)
    while resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(3)
        resp = w.statement_execution.get_statement(resp.statement_id)
    if resp.status.state != StatementState.SUCCEEDED:
        msg = resp.status.error.message if resp.status.error else resp.status.state.value
        raise RuntimeError(msg)
    return resp


def run_sql(statement: str) -> list[list]:
    resp = _execute(statement)
    return list(resp.result.data_array or []) if resp.result else []


def query(statement: str) -> tuple[list[str], list[list]]:
    """(column names, all rows), following result chunks."""
    resp = _execute(statement)
    cols = [c.name for c in resp.manifest.schema.columns] if resp.manifest and resp.manifest.schema else []
    rows = list(resp.result.data_array or []) if resp.result else []
    chunk = resp.result
    while chunk and chunk.next_chunk_index is not None:
        chunk = ws().statement_execution.get_statement_result_chunk_n(resp.statement_id, chunk.next_chunk_index)
        rows += chunk.data_array or []
    return cols, rows


def scalar(statement: str) -> int:
    rows = run_sql(statement)
    return int(float(rows[0][0])) if rows and rows[0][0] is not None else 0


def table_columns(table: str) -> list[str]:
    try:
        cols, rows = query(f"DESCRIBE TABLE {table}")
    except RuntimeError:
        return []
    out = []
    for r in rows:
        name = (r[0] or "").strip()
        if not name or name.startswith("#"):
            break
        out.append(name)
    return out


# -- files -------------------------------------------------------------------------------

def upload_file(path: str, content: bytes) -> None:
    ws().files.upload(path, io.BytesIO(content), overwrite=True)


# -- notebooks ---------------------------------------------------------------------------

def create_notebook(path: str, source: str) -> None:
    w = ws()
    w.workspace.mkdirs(posixpath.dirname(path))
    w.workspace.import_(path=path, content=base64.b64encode(source.encode("utf-8")).decode("utf-8"),
                        format=ImportFormat.SOURCE, language=Language.PYTHON, overwrite=True)


def read_notebook(path: str) -> str | None:
    try:
        resp = ws().workspace.export(path, format=ExportFormat.SOURCE)
        return base64.b64decode(resp.content).decode("utf-8")
    except Exception:
        return None


def notebook_url(path: str) -> str:
    try:
        oid = ws().workspace.get_status(path).object_id
        return f"{host()}/#notebook/{oid}"
    except Exception:
        return host()


# -- jobs -------------------------------------------------------------------------------------

def start_job(notebook_path: str, job_name: str) -> dict:
    """Creates the job the first time, then reuses it; returns {job_id, run_id}."""
    w = ws()
    task = Task(task_key=job_name, notebook_task=NotebookTask(notebook_path=notebook_path))
    job_id = next((j.job_id for j in w.jobs.list(name=job_name)), None)
    created = job_id is None
    if created:
        job_id = w.jobs.create(name=job_name, tasks=[task]).job_id
    run = w.jobs.run_now(job_id=job_id)
    return {"job_id": job_id, "run_id": run.run_id, "created": created}


def run_state(run_id: int) -> dict:
    r = ws().jobs.get_run(run_id)
    return {"life_cycle": r.state.life_cycle_state.value if r.state and r.state.life_cycle_state else None,
            "result": r.state.result_state.value if r.state and r.state.result_state else None,
            "message": r.state.state_message if r.state else None, "url": r.run_page_url}


def run_output(run_id: int) -> dict:
    w = ws()
    run = w.jobs.get_run(run_id)
    if not run.tasks:
        return {"error": "No tasks found in job run.", "error_trace": None}
    out = w.jobs.get_run_output(run.tasks[0].run_id)
    return {"error": out.error or None, "error_trace": out.error_trace or None,
            "notebook_output": out.notebook_output.result if out.notebook_output else None}
