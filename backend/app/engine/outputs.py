"""
Output files for a run: the S_MARC load file and the validation report.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.engine.transform import LINEAGE

NAVY = "#0F2A4A"


def write_load_file(s4: pd.DataFrame, plan: list[dict], path: Path) -> int:
    load = s4[s4["__status"] == "mapped"].drop(columns=LINEAGE)
    with pd.ExcelWriter(path, engine="xlsxwriter") as xw:
        load.to_excel(xw, sheet_name="S_MARC", index=False, startrow=1)
        wb, ws = xw.book, xw.sheets["S_MARC"]
        head = wb.add_format({"bold": True, "font_color": "white", "bg_color": NAVY, "border": 1})
        desc = wb.add_format({"italic": True, "font_color": "#475569", "bg_color": "#E2E8F0", "border": 1})
        by_field = {p["field"]: p for p in plan}
        for i, col in enumerate(load.columns):
            ws.write(0, i, str(by_field.get(col, {}).get("description") or col), desc)
            ws.write(1, i, col, head)
            ws.set_column(i, i, max(10, min(28, len(col) + 4)))
        ws.freeze_panes(2, 2)
    return len(load)


def write_report(run: dict, path: Path) -> None:
    v, m = run["validation"], run["validation"]["metrics"]
    summary = [
        ("Run", run["id"]), ("ECC file", run["file"]), ("Mapping document", run.get("mappingDoc")),
        ("Mapping", run["mappingId"]), ("Finished", run.get("finished")),
        ("ECC rows", run["metrics"]["eccRows"]), ("Rows in S_MARC load file", run["metrics"]["loadRows"]),
        ("Validated plant", v["plant"]), ("Compared with", v["dbFile"]),
        ("Databricks rows", m["dbRows"]), ("Found in our output", f"{m['foundRows']:,} ({m['foundPct']}%)"),
        ("Result", "PASSED" if v["passed"] else "FAILED"),
    ]
    with pd.ExcelWriter(path, engine="xlsxwriter") as xw:
        wb = xw.book
        head = wb.add_format({"bold": True, "font_color": "white", "bg_color": NAVY, "border": 1})
        title = wb.add_format({"bold": True, "font_size": 16, "font_color": NAVY})
        bold = wb.add_format({"bold": True})
        ok = wb.add_format({"bg_color": "#DCFCE7", "font_color": "#166534", "bold": True})
        bad = wb.add_format({"bg_color": "#FEE2E2", "font_color": "#991B1B", "bold": True})

        ws = wb.add_worksheet("Summary")
        ws.write(0, 0, f"MARC Validation Report · plant {v['plant']}", title)
        for i, (k, val) in enumerate(summary, start=2):
            ws.write(i, 0, k, bold)
            ws.write(i, 1, val, (ok if v["passed"] else bad) if k == "Result" else None)
        ws.set_column(0, 0, 28)
        ws.set_column(1, 1, 60)

        def table(name, df, widths=None, status_col=None):
            df.to_excel(xw, sheet_name=name, index=False)
            s = xw.sheets[name]
            for i, c in enumerate(df.columns):
                s.write(0, i, c, head)
                s.set_column(i, i, (widths or {}).get(c, 18))
            if status_col:
                ci = list(df.columns).index(status_col)
                for r, val in enumerate(df[status_col], start=1):
                    s.write(r, ci, val, ok if val == "pass" else bad)
            s.freeze_panes(1, 0)

        table("Checks", pd.DataFrame([{"Check": c["name"], "Result": c["status"], "Detail": c["detail"]}
                                      for c in v["checks"]]), {"Check": 36, "Detail": 90}, "Result")
        table("Field comparison", pd.DataFrame([{"Field": f["field"], "Meaning": f["label"], "Match %": f["matchPct"]}
                                                for f in v["fields"]] or [{"Field": "-"}]))
        table("Not found", pd.DataFrame(v["missing"], columns=["PRODUCT", "WERKS"]) if v["missing"]
              else pd.DataFrame([{"PRODUCT": "none"}]), {"PRODUCT": 24})
