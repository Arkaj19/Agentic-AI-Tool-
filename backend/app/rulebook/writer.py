"""
Structured plant rules -> mapping workbook in the format of
templates/MARC_MBEW_Mappings.xlsx.

For the demo the S_MARC field rows (structure, source table, target field,
rule type and the other fields' logic) come from the template unchanged; only
the WERKS block's "Rule logic" cells are written from the parsed rules.
Generated cells are shaded so reviewers can see what the agent wrote.
"""
from __future__ import annotations

import json
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.config import settings
from app.rulebook.parser import PlantRules

SHEET = "MARC"
COLUMNS = ["Filters", "Group", "Field description", "Mandatory", "Type", "Length", "Decimals",
           "Structure", "Source table", "Target field", "Rule type", "Rule logic"]
TARGET_COL, RULE_TYPE_COL, LOGIC_COL = 10, 11, 12
GENERATED_FILL = PatternFill("solid", fgColor="FFF4D6")


def logic_lines(rules: PlantRules) -> list[str]:
    lines = [f"For {p}: split → {', '.join(t)} (one S/4 row per target plant)"
             for p, t in rules.splits.items()]
    lines += [f"{p} → {t}" for p, t in rules.one_to_one.items()]
    lines.append("Other plants → keep MARC.WERKS, flag as unmapped for review"
                 if rules.unmapped_policy == "keep_and_flag" else "Other plants → excluded from load")
    return lines


def _werks_block(ws) -> tuple[int, int]:
    """First and last row of the WERKS field (up to the next target field)."""
    start = None
    for r in range(1, ws.max_row + 1):
        val = ws.cell(r, TARGET_COL).value
        if start is None and str(val or "").strip().upper() == "WERKS":
            start = r
        elif start is not None and val:
            return start, r - 1
    if start is None:
        raise ValueError("Template has no WERKS row in the MARC sheet")
    return start, ws.max_row


def target_fields(template: Path | None = None) -> list[dict]:
    """S_MARC field rows from the template: [{field, description, source, rule_type, logic}]."""
    wb = openpyxl.load_workbook(template or settings.TEMPLATE_PATH, read_only=True)
    ws = wb[SHEET]
    rows, cur = [], None
    for row in ws.iter_rows(min_row=2, values_only=True):
        row = list(row) + [None] * (12 - len(row))
        if row[TARGET_COL - 1]:
            cur = {"field": str(row[9]).strip(), "description": row[2], "mandatory": bool(row[3]),
                   "source": row[8], "rule_type": str(row[10] or "").strip(),
                   "logic": [str(row[11])] if row[11] else []}
            rows.append(cur)
        elif cur and row[11]:
            cur["logic"].append(str(row[11]))
    wb.close()
    return rows


def write(rules: PlantRules, out_path: Path, meta: dict) -> dict:
    wb = openpyxl.load_workbook(settings.TEMPLATE_PATH)
    for name in list(wb.sheetnames):
        if name != SHEET:
            del wb[name]  # MARC only for now
    ws = wb[SHEET]
    start, end = _werks_block(ws)

    lines = logic_lines(rules)
    slots = end - start + 1
    if len(lines) > slots:  # keep the layout: overflow goes into the last cell
        lines = lines[:slots - 1] + ["\n".join(lines[slots - 1:])]
    for i, r in enumerate(range(start, end + 1)):
        cell = ws.cell(r, LOGIC_COL)
        cell.value = lines[i] if i < len(lines) else None
        cell.fill = GENERATED_FILL
    ws.cell(start, RULE_TYPE_COL).fill = GENERATED_FILL

    # Structured copy of the rules, for people and for the transform engine.
    pr = wb.create_sheet("Plant Rules")
    pr.append(["ECC plant", "Rule", "S/4 plant(s)", "Rows per ECC row"])
    for p, t in rules.splits.items():
        pr.append([p, "Split", ", ".join(t), len(t)])
    for p, t in rules.one_to_one.items():
        pr.append([p, "One-to-one", t, 1])
    pr.append(["(any other)", "Unmapped", "keep ECC value, flag" if rules.unmapped_policy == "keep_and_flag"
               else "exclude", 0])
    for c in pr[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="0F2A4A")
    for i, w in enumerate([12, 14, 22, 18], start=1):
        pr.column_dimensions[get_column_letter(i)].width = w

    src = wb.create_sheet("Rule Source")
    src.column_dimensions["A"].width = 22
    src.column_dimensions["B"].width = 90
    for k, v in [("Mapping ID", meta["id"]), ("Mapping document", meta["sourceDoc"]["path"]),
                 ("Generated", meta["created"]), ("Parser", meta["parser"]),
                 ("Model", (meta.get("llm") or {}).get("model", "-")),
                 ("Cross-check", "agrees" if meta["crosscheck"]["agree"] else "; ".join(meta["crosscheck"]["diffs"])),
                 ("Generated cells", f"{SHEET}!L{start}:L{end} (shaded)"),
                 ("Structured rules", json.dumps(rules.model_dump()))]:
        src.append([k, v])
    for row in src.iter_rows():
        row[0].font = Font(bold=True)
        row[1].alignment = Alignment(wrap_text=True, vertical="top")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return {"werksRows": [start, end], "lines": logic_lines(rules)}


def preview(path: Path) -> dict:
    wb = openpyxl.load_workbook(path, read_only=False)
    ws = wb[SHEET]
    start, end = _werks_block(ws)
    rows = []
    for r in range(1, ws.max_row + 1):
        vals = [ws.cell(r, c).value for c in range(1, 13)]
        if not any(v not in (None, "") for v in vals):
            continue
        rows.append({"row": r, "cells": ["" if v is None else str(v) for v in vals],
                     "generated": start <= r <= end, "isField": bool(vals[TARGET_COL - 1])})
    plant = [[("" if c.value is None else str(c.value)) for c in row] for row in wb["Plant Rules"].iter_rows()]
    wb.close()
    return {"columns": COLUMNS, "rows": rows, "plantRules": plant, "werksRows": [start, end]}
