"""
The Databricks rule book.

    shown : the text version in SharePoint (SP_DBX_RULEBOOK_PATH), fetched for the user to see
    used  : the local CSV (DBX_RULEBOOK_LOCAL, same columns as the Databricks rule_book table:
            object_name, rule_type, rule_id, rule_text, check_sql) for code generation and validation
"""
from __future__ import annotations

import hashlib
import json

import pandas as pd

from app.config import settings
from app.connectors import source


def load_rules(object_name: str = "MARC") -> list[dict]:
    path = settings.DBX_RULEBOOK_LOCAL
    if not path.exists():
        raise FileNotFoundError(f"Databricks rule book not found at {path}")
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = df[df["object_name"].str.strip().str.upper() == object_name.upper()]
    rules = [{"rule_type": r.rule_type.strip().upper(), "rule_id": r.rule_id.strip(), "rule_text": r.rule_text.strip(),
              "check_sql": (r.check_sql or "").strip() or None} for r in df.itertuples()]
    return sorted(rules, key=lambda r: (r["rule_type"], r["rule_id"]))


def split(rules: list[dict]) -> tuple[list[dict], list[dict]]:
    return ([r for r in rules if r["rule_type"] == "TRANSFORMATION"],
            [r for r in rules if r["rule_type"] == "VALIDATION"])


def transformation_text(t_rules: list[dict]) -> str:
    return "\n".join(f"{r['rule_id']}. {r['rule_text']}" for r in t_rules)


def rules_hash(t_text: str) -> str:
    return hashlib.sha256(t_text.encode("utf-8")).hexdigest()[:16]


def row_rules() -> list[dict]:
    p = settings.DBX_ROW_RULES
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def fetch_shared() -> dict:
    """The rule book document in SharePoint, for display."""
    try:
        doc = source.read_document(settings.SP_DBX_RULEBOOK_PATH)
        return {"found": True, "path": doc["path"], "name": doc["name"], "modified": doc["modified"], "text": doc["text"]}
    except Exception as exc:
        return {"found": False, "path": settings.SP_DBX_RULEBOOK_PATH, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


def overview() -> dict:
    rules = load_rules()
    t, v = split(rules)
    return {"shared": fetch_shared(), "transformation": t, "validation": v,
            "silverTable": settings.DBX_SILVER_TABLE, "goldTable": settings.DBX_GOLD_TABLE}
