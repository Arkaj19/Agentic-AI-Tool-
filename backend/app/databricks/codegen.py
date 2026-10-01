"""
LLM code generation for the Databricks notebook (ported from sap-migration-agent agent.py):
generate -> self-review -> static checks with a fix loop; runtime errors are fixed with fix_code().
"""
from __future__ import annotations

import ast
import re

from app.config import settings
from app.llm import azure

HASH_MARKER = "# RULEBOOK_HASH:"
SYSTEM_PROMPT = ("You are a Databricks PySpark developer. Always return complete executable Python code. "
                 "Never stop in the middle of a statement. Never return explanations or markdown.")


def ask(prompt: str) -> str:
    out = azure.chat([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}])
    if not out["text"].strip():
        raise RuntimeError("Azure OpenAI returned an empty reply")
    return out["text"]


def clean_code(code: str) -> str:
    return (code or "").replace("```python", "").replace("```", "").strip()


def static_issues(code: str) -> str | None:
    if not code:
        return "LLM returned empty code."
    try:
        ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError at line {e.lineno}: {e.msg}"
    if "saveAsTable" not in code:
        return "Code never writes the target table with saveAsTable()."
    if "SparkSession.builder" in code:
        return "Do not create a SparkSession; use the existing `spark` object."
    return None


def fix_code(rules: str, code: str, error: str) -> str:
    return clean_code(ask(f"""
The following Databricks PySpark notebook code has a problem.

TRANSFORMATION RULES:
{rules}

CODE:
{code}

ERROR:
{error}

Fix the error. Keep implementing the rules exactly.
Return ONLY the complete corrected Python code.
"""))


def generate_code(rules: str, log=lambda msg: None) -> str | None:
    code = clean_code(ask(f"""
You are generating a Databricks notebook (Python / PySpark) for an
SAP ECC to S/4HANA data migration.

TRANSFORMATION RULES (source of truth):
{rules}

Hard requirements:
- A SparkSession named `spark` already exists. Do NOT create one.
- Start with: from pyspark.sql import functions as F
- Read the source table named in the rules with spark.table(...).
- Implement every transformation rule exactly. Do not invent rules.
- The final DataFrame must contain only the columns the rules produce.
- Write the target table named in the rules with:
  df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(...)
- Do NOT write any validation logic. Validation happens outside this notebook.
- No display(), no dbutils, no markdown, no explanations.
- Keep it short (20-40 lines).

Return ONLY the Python code.
"""))
    log("Code drafted; the AI is reviewing it against the rule book")
    reviewed = clean_code(ask(f"""
Review this Databricks PySpark code before deployment.

TRANSFORMATION RULES:
{rules}

CODE:
{code}

Check for: syntax errors, incomplete statements, missing imports,
undefined variables, table or column names that differ from the rules,
rules that are not implemented, SparkSession creation, validation logic.

Return the complete corrected code (or the same code if it is correct).
Return ONLY Python code.
"""))
    if reviewed:
        code = reviewed
    for attempt in range(1, settings.DBX_MAX_FIX_ATTEMPTS + 1):
        issue = static_issues(code)
        if not issue:
            return code
        log(f"Static check failed (attempt {attempt}): {issue}; asking the AI to fix it")
        code = fix_code(rules, code, issue)
    return code if not static_issues(code) else None


def with_marker(code: str, rb_hash: str) -> str:
    return f"{HASH_MARKER} {rb_hash}\n{code}"


def get_hash(source: str | None) -> str | None:
    m = re.search(rf"{re.escape(HASH_MARKER)}\s*(\w+)", source or "")
    return m.group(1) if m else None


def strip_marker(source: str) -> str:
    """The generated code only: without the hash marker, header and the appended row-validation cell."""
    body = source.split("# COMMAND ----------")[0]
    lines = [l for l in body.splitlines()
             if not l.startswith(HASH_MARKER) and l.strip() != "# Databricks notebook source"]
    return "\n".join(lines).strip()


def target_table(code: str) -> str | None:
    m = re.search(r'saveAsTable\(\s*["\']([^"\']+)["\']', code or "")
    return m.group(1) if m else None
