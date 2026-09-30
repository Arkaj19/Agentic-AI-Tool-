"""
ECC MARC -> S_MARC.

WERKS follows the plant rules (split / one-to-one / unmapped), plus any
decisions taken at gate G2:
    overrides  {ecc_plant: [targets]}  ([] = exclude the plant from the load)
    priority   {s4_plant: ecc_plant}   which source wins when two ECC plants
                                       land on the same material + S/4 plant
Every other S_MARC field is handled as the template says: Passthrough copies
the ECC field, Hardcoded writes the constant, other Derived fields are passed
through for the demo (their logic is out of scope) and listed in the report.
"""
from __future__ import annotations

import re

import pandas as pd

from app import labels
from app.rulebook.parser import PlantRules
from app.rulebook.writer import target_fields

LINEAGE = ["__src_row", "__src_plant", "__status"]
# S_MARC field -> ECC field when the names differ
SOURCE_ALIAS = {"PRODUCT": "MATNR", "WERKS": "WERKS"}


def _hardcoded_value(logic: list[str]) -> str:
    text = " ".join(logic)
    m = re.search(r'"([^"]*)"', text)
    if m:
        return m.group(1)
    return ""  # "BLANK"


def field_plan(ecc_fields: set[str]) -> list[dict]:
    plan = []
    for f in target_fields():
        field, rt = f["field"], f["rule_type"].lower()
        src = SOURCE_ALIAS.get(field, field)
        if field == "WERKS":
            how, note = "plant-rules", "From the approved plant rules"
        elif rt.startswith("hardcoded"):
            how, note = "hardcoded", f"Constant '{_hardcoded_value(f['logic'])}'"
        elif src in ecc_fields:
            how = "passthrough" if rt.startswith("passthrough") else "derived-passthrough"
            note = f"MARC.{src}" if how == "passthrough" else f"MARC.{src} passed through (derivation not in demo scope)"
        else:
            how, note = "missing", f"MARC.{src} not in the extract; left blank"
        plan.append({"field": field, "ruleType": f["rule_type"], "handling": how, "source": src,
                     "note": note, "value": _hardcoded_value(f["logic"]) if how == "hardcoded" else None,
                     "description": f["description"], "mandatory": f["mandatory"]})
    return plan


def run(ecc: pd.DataFrame, rules: PlantRules, overrides: dict | None = None,
        priority: dict | None = None) -> tuple[pd.DataFrame, list[dict]]:
    """Returns (S_MARC rows incl. lineage columns, field plan)."""
    overrides = overrides or {}
    priority = priority or {}
    sap = labels.to_sap(ecc).reset_index(drop=True)
    if "MATNR" not in sap or "WERKS" not in sap:
        raise ValueError("Extract has no Material / Plant columns")
    sap["__src_row"] = range(len(sap))
    sap["__src_plant"] = sap["WERKS"]

    def targets(plant: str):
        if plant in overrides:
            return overrides[plant] or ["__EXCLUDED__"]
        return rules.targets_for(plant) or ["__UNMAPPED__"]

    plants = sap["WERKS"].unique()
    tmap = {p: targets(p) for p in plants}
    out = sap.assign(__target=sap["WERKS"].map(tmap)).explode("__target", ignore_index=True)
    out["__status"] = "mapped"
    out.loc[out["__target"] == "__UNMAPPED__", "__status"] = "unmapped"
    out.loc[out["__target"] == "__EXCLUDED__", "__status"] = "excluded"
    keep_ecc = out["__status"] != "mapped"
    out["WERKS"] = out["__target"].where(~keep_ecc, out["__src_plant"])
    out = out.drop(columns="__target")

    # G2 priority decisions: drop the losing source plant's rows for that S/4 plant.
    if priority:
        mapped = out["__status"] == "mapped"
        dup = out[mapped].duplicated(["MATNR", "WERKS"], keep=False)
        dup_idx = out[mapped][dup].index
        for s4_plant, winner in priority.items():
            lose = out.loc[dup_idx]
            lose = lose[(lose["WERKS"] == s4_plant) & (lose["__src_plant"] != winner)].index
            out.loc[lose, "__status"] = "superseded"

    plan = field_plan(set(sap.columns))
    cols = {}
    for p in plan:
        if p["handling"] == "plant-rules":
            cols[p["field"]] = out["WERKS"]
        elif p["handling"] == "hardcoded":
            cols[p["field"]] = p["value"]
        elif p["handling"] in ("passthrough", "derived-passthrough"):
            cols[p["field"]] = out[p["source"]]
        else:
            cols[p["field"]] = ""
    s4 = pd.DataFrame(cols, index=out.index)
    for c in LINEAGE:
        s4[c] = out[c]
    return s4, plan
