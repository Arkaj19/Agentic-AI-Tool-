"""
Validation against the Databricks S/4 output, for one plant (demo: 1021).

Our S_MARC rows for the plant are compared with
"Databricks Files/S_MARC#FreeText - <plant>.csv" from SharePoint:

    1. Databricks file found
    2. Same S/4 plants            - the Databricks rows use the plants our rules produce
    3. Databricks rows found      - share of Databricks rows (material + S/4 plant) we also produce
    4. Key field values match     - on the rows found, the key fields hold the same values

Material numbers are compared without leading zeros (Databricks pads them to 18).
"""
from __future__ import annotations

import pandas as pd

from app.config import settings
from app.rulebook.parser import PlantRules

KEY_FIELDS = {"DISMM": "MRP type", "DISPO": "MRP controller", "MMSTA": "Plant status",
              "KOKRS": "Controlling area", "XCHPF": "Batch management"}


def _norm(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lstrip("0")


def _check(cid: str, name: str, ok: bool, detail: str, value=None) -> dict:
    return {"id": cid, "name": name, "status": "pass" if ok else "fail", "detail": detail, "value": value}


def run(s4: pd.DataFrame, rules: PlantRules, db: pd.DataFrame | None, db_path: str) -> dict:
    plant = settings.VALIDATION_PLANT
    ours = s4[(s4["__src_plant"] == plant) & (s4["__status"] == "mapped")]
    targets = rules.targets_for(plant) or []
    checks, fields, missing = [], [], pd.DataFrame()
    metrics = {"plant": plant, "ourRows": int(len(ours)), "dbRows": 0, "foundRows": 0, "foundPct": 0.0}

    found_file = db is not None and len(db) > 0
    checks.append(_check("file", "Databricks file found", found_file,
                         f"{len(db):,} rows in {db_path}" if found_file else f"{db_path} not found"))
    if not found_file:
        return {"plant": plant, "dbFile": db_path, "checks": checks, "fields": [], "metrics": metrics,
                "passed": False, "missing": []}

    werks_col = "werks" if "werks" in db.columns else "WERKS"
    db = db.assign(_k=_norm(db["PRODUCT"]) + "|" + db[werks_col].str.strip())
    ours = ours.assign(_k=_norm(ours["PRODUCT"]) + "|" + ours["WERKS"])
    metrics["dbRows"] = int(len(db))

    db_plants = sorted(db[werks_col].str.strip().unique())
    same = set(db_plants) == set(targets)
    checks.append(_check("plants", "Same S/4 plants", same,
                         f"Both use {', '.join(targets)}" if same else
                         f"Databricks uses {', '.join(db_plants)}; our rules give {', '.join(targets) or 'none'}"))

    hit = db["_k"].isin(set(ours["_k"]))
    pct = float(hit.mean()) if len(db) else 0.0
    metrics.update(foundRows=int(hit.sum()), foundPct=round(pct * 100, 1))
    checks.append(_check("rows", "Databricks rows found in our output", pct >= settings.MATCH_PASS_MARK,
                         f"{pct:.0%} found ({int(hit.sum()):,} of {len(db):,}) · pass mark {settings.MATCH_PASS_MARK:.0%}",
                         round(pct * 100, 1)))
    missing = db.loc[~hit, ["PRODUCT", werks_col]].rename(columns={werks_col: "WERKS"})

    merged = db[hit].merge(ours.drop_duplicates("_k"), on="_k", suffixes=("_db", "_ours"))
    for f, label in KEY_FIELDS.items():
        a, b = f"{f}_db", f"{f}_ours"
        if a in merged and b in merged and len(merged):
            share = float((merged[a].astype(str).str.strip() == merged[b].astype(str).str.strip()).mean())
            fields.append({"field": f, "label": label, "matchPct": round(share * 100, 1)})
    low = [x for x in fields if x["matchPct"] < settings.FIELD_PASS_MARK * 100]
    checks.append(_check("fields", "Key field values match", bool(fields) and not low,
                         (", ".join(f"{x['label']} {x['matchPct']:.0f}%" for x in low) + " below the pass mark") if low
                         else f"{', '.join(x['label'] for x in fields)} agree on the rows found", fields))

    return {"plant": plant, "dbFile": db_path, "checks": checks, "fields": fields, "metrics": metrics,
            "passed": all(c["status"] == "pass" for c in checks),
            "missing": missing.head(500).values.tolist(), "missingCount": int(len(missing))}
