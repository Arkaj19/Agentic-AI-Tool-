"""
ECC extracts use SAP screen labels as headers ("Plant", "Procurement type").
This maps them to SAP technical field names (WERKS, BESKZ) using
sap_labels.yaml (reused from Sharepoint-RO-Automation).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

_LABELS_FILE = Path(__file__).with_name("sap_labels.yaml")


@lru_cache
def field_to_label(table: str = "MARC") -> dict[str, str]:
    data = yaml.safe_load(_LABELS_FILE.read_text(encoding="utf-8")) or {}
    return {str(k).upper(): str(v) for k, v in (data.get(table) or {}).items()}


@lru_cache
def label_to_field(table: str = "MARC") -> dict[str, str]:
    return {v: k for k, v in field_to_label(table).items()}


def header_map(columns: list[str], table: str = "MARC") -> dict[str, str | None]:
    """{extract header: SAP field or None}."""
    rev = label_to_field(table)
    return {c: rev.get(c) for c in columns}


def to_sap(df: pd.DataFrame, table: str = "MARC") -> pd.DataFrame:
    """Keeps only the columns that have a known SAP field, renamed to it."""
    mapping = {c: f for c, f in header_map(list(df.columns), table).items() if f}
    return df[list(mapping)].rename(columns=mapping)
