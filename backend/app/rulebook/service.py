"""
Mapping lifecycle: generate (draft) from a mapping document picked in
SharePoint, preview, approve. Each mapping lives in data/mappings/<id>/ with
the workbook, the document text it was generated from, and meta.json.
"""
from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.connectors import source
from app.rulebook import parser, writer

_DIR = settings.DATA_DIR / "mappings"
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _meta_path(mid: str) -> Path:
    return _DIR / mid / "meta.json"


def _save(meta: dict) -> None:
    _meta_path(meta["id"]).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def get(mid: str) -> dict:
    p = _meta_path(mid)
    if not p.exists():
        raise KeyError(f"mapping {mid} not found")
    return json.loads(p.read_text(encoding="utf-8"))


def xlsx_path(mid: str) -> Path:
    return _DIR / mid / f"MARC_Mapping_{mid}.xlsx"


def list_all() -> list[dict]:
    items = [json.loads(p.read_text(encoding="utf-8")) for p in _DIR.glob("*/meta.json")]
    return sorted(items, key=lambda m: m["created"], reverse=True)


def rules_of(mid: str) -> parser.PlantRules:
    return parser.PlantRules.model_validate(get(mid)["rules"])


def generate(doc_path: str, *, use_llm: bool = True) -> dict:
    doc = source.read_document(doc_path)
    result = parser.parse(doc["text"], use_llm=use_llm)
    mid = f"M-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{secrets.token_hex(2)}"
    (_DIR / mid).mkdir(parents=True, exist_ok=True)
    (_DIR / mid / "source.txt").write_text(doc["text"], encoding="utf-8")
    meta = {"id": mid, "object": "MARC", "created": _now(),
            "sourceDoc": {"path": doc["path"], "name": doc["name"], "modified": doc["modified"]},
            "parser": result["parser"], "llm": result["llm"], "crosscheck": result["crosscheck"],
            "rules": result["rules"].model_dump(), "status": "draft",
            "approvedBy": None, "approvedAt": None, "runs": []}
    info = writer.write(result["rules"], xlsx_path(mid), meta)
    meta["logicLines"] = info["lines"]
    meta["werksRows"] = info["werksRows"]
    with _lock:
        _save(meta)
    return meta


def preview(mid: str) -> dict:
    return {**writer.preview(xlsx_path(mid)), "meta": get(mid)}


def approve(mid: str, by: str = "user", comment: str = "") -> dict:
    with _lock:
        meta = get(mid)
        if meta["status"] != "approved":
            meta.update(status="approved", approvedBy=by, approvedAt=_now(), approvalComment=comment)
            _save(meta)
        return meta


def reject(mid: str, by: str = "user", comment: str = "") -> dict:
    with _lock:
        meta = get(mid)
        meta.update(status="rejected", approvedBy=by, approvedAt=_now(), approvalComment=comment)
        _save(meta)
        return meta


def link_run(mid: str, run_id: str) -> None:
    with _lock:
        meta = get(mid)
        if run_id not in meta["runs"]:
            meta["runs"].append(run_id)
            _save(meta)
