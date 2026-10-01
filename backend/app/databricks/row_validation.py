"""
Row-by-row validation (runs INSIDE the Databricks notebook).

row_validation_cell(...) returns a notebook cell (as text) that the agent appends to
the generated notebook. The cell checks EVERY gold row against each row-level rule
and writes a table with the original columns plus:

    _row_status        PASS / FAIL
    _failed_rules      e.g. "V05;V09"
    _failure_reasons   e.g. "V05: WERKS must be a valid S/4 plant | V09: WAERS ..."
    _row_no            original row order (1..N)
    _failed_columns    e.g. "WERKS,WAERS"   (used to colour the exact cells in Excel)

Rule format (one dict per rule):
    {"rule_id": "V03", "description": "PRODUCT must not be blank",
     "fail_condition": "PRODUCT IS NULL OR trim(PRODUCT) = ''",   # Spark SQL, TRUE = row fails
     "columns": ["PRODUCT"]}
    {"rule_id": "V04", "description": "PRODUCT + WERKS must be unique",
     "type": "unique", "columns": ["PRODUCT", "WERKS"]}

Table-level rules (row counts, columns exist) have no fail_condition -> they stay in
the overall summary and are skipped here.
"""

import json

_CELL = r'''
# COMMAND ----------

# ===== Row-by-row validation (fixed code, added by the agent) =====
import json as _json
from pyspark.sql import functions as _F
from pyspark.sql.window import Window as _W

_ROW_RULES = _json.loads(__RULES__)
_TARGET_TABLE = "__TARGET__"
_ROW_TABLE = "__ROW_TABLE__"

_df = spark.table(_TARGET_TABLE).withColumn("_mid", _F.monotonically_increasing_id())
_flags, _skipped = [], []
for _r in _ROW_RULES:
    _flag = "_fail_" + _r["rule_id"]
    try:
        if _r.get("type") == "unique":
            _cond = _F.count(_F.lit(1)).over(_W.partitionBy(*_r["columns"])) > 1
        elif _r.get("fail_condition"):
            _cond = _F.coalesce(_F.expr(_r["fail_condition"]), _F.lit(False))
        else:
            continue                      # table-level rule
        _df.select(_cond.alias("_probe")).limit(1).collect()   # catches bad SQL early
        _df = _df.withColumn(_flag, _cond)
        _flags.append((_flag, _r))
    except Exception as _e:
        _skipped.append(f'{_r["rule_id"]}: {type(_e).__name__}: {str(_e)[:200]}')

_ids = _F.concat_ws(";", *[_F.when(_F.col(f), _F.lit(r["rule_id"])) for f, r in _flags]) \
    if _flags else _F.lit("")
_why = _F.concat_ws(" | ", *[_F.when(_F.col(f), _F.lit(f'{r["rule_id"]}: {r.get("description", "")}'))
                             for f, r in _flags]) if _flags else _F.lit("")
_cols = _F.concat_ws(",", *[_F.when(_F.col(f), _F.lit(",".join(r.get("columns") or [])))
                            for f, r in _flags]) if _flags else _F.lit("")

_data_cols = [c for c in _df.columns if not c.startswith("_fail_") and c != "_mid"]
_row_df = (_df.withColumn("_failed_rules", _ids)
              .withColumn("_failure_reasons", _why)
              .withColumn("_failed_columns", _cols)
              .withColumn("_row_status", _F.when(_F.col("_failed_rules") == "", "PASS").otherwise("FAIL"))
              .withColumn("_row_no", _F.row_number().over(_W.orderBy("_mid")))
              .select("_row_no", "_row_status", "_failed_rules", "_failure_reasons", *_data_cols,
                      "_failed_columns")
              .orderBy("_row_no"))

_row_df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(_ROW_TABLE)
_counts = {r["_row_status"]: r["count"] for r in spark.table(_ROW_TABLE).groupBy("_row_status").count().collect()}
print(f"Row validation -> {_ROW_TABLE}: {_counts.get('PASS', 0)} PASS, {_counts.get('FAIL', 0)} FAIL")
if _skipped:
    print("Row rules skipped (invalid condition):", _skipped)
'''
def load_row_rules(path):
    """Load row-level validation rules from a JSON file."""

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)

def row_validation_cell(rules: list[dict], target_table: str, row_table: str) -> str:
    """Notebook cell text to append to the generated notebook source."""
    return (_CELL.replace("__RULES__", repr(json.dumps(rules)))
                 .replace("__TARGET__", target_table)
                 .replace("__ROW_TABLE__", row_table))


def add_row_validation(notebook_source: str, rules: list[dict], target_table: str,
                       row_table: str) -> str:
    """
    Insert the row-validation cell into a notebook. If the notebook ends with
    dbutils.notebook.exit(...), the cell is placed BEFORE that cell (code after
    exit() never runs).
    """
    cell = row_validation_cell(rules, target_table, row_table)
    marker = "# COMMAND ----------"
    exit_pos = notebook_source.rfind("dbutils.notebook.exit(")
    if exit_pos == -1:
        return notebook_source.rstrip() + "\n" + cell
    cell_start = notebook_source.rfind(marker, 0, exit_pos)
    if cell_start != -1:
        return notebook_source[:cell_start] + cell.lstrip("\n") + "\n" + notebook_source[cell_start:]
    line_start = notebook_source.rfind("\n", 0, exit_pos) + 1
    if notebook_source[line_start:exit_pos].strip() == "":       # exit() at top level
        return notebook_source[:line_start] + cell + "\n" + notebook_source[line_start:]
    return notebook_source.rstrip() + "\n" + cell
