"""
App configuration, loaded from backend/.env. Credentials never live in code.
Variable names match the existing Sharepoint-RO-Automation project so the same
.env values work in both.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")


def _str(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _path(name: str, default: Path) -> Path:
    raw = _str(name)
    if not raw:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


class Settings:
    # -- SharePoint / Microsoft Graph (app registration) ---------------------
    TENANT_ID = _str("SP_TENANT_ID")
    CLIENT_ID = _str("SP_CLIENT_ID")
    CLIENT_SECRET = _str("SP_CLIENT_SECRET")
    SHAREPOINT_HOSTNAME = _str("SP_HOSTNAME")
    SITE_PATH = _str("SP_SITE_PATH")
    # Folder the Rulebook's "Fetch" browser opens first.
    MAPPINGS_FOLDER = _str("SP_MAPPINGS_FOLDER", "Mappings")
    # Databricks S/4 output used for validation (one file per plant).
    DATABRICKS_FOLDER = _str("SP_DATABRICKS_FOLDER", "Databricks Files")
    DATABRICKS_FILE = _str("SP_DATABRICKS_FILE", "S_MARC#FreeText - {plant}.csv")
    HTTP_TIMEOUT = _int("HTTP_TIMEOUT", 120)

    # sharepoint | local ("local" reads a folder laid out like the library)
    SOURCE_MODE = _str("SOURCE_MODE", "sharepoint").lower() or "sharepoint"
    LOCAL_SOURCE_ROOT = _path("LOCAL_SOURCE_ROOT", PROJECT_DIR / "local_sharepoint")

    # -- Azure OpenAI ------------------------------------------------------------
    LLM_PROVIDER = _str("LLM_PROVIDER", "azure").lower()  # azure | none
    AZURE_OPENAI_API_KEY = _str("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT = _str("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_VERSION = _str("AZURE_OPENAI_API_VERSION")
    AZURE_OPENAI_CHAT_DEPLOYMENT = _str("AZURE_OPENAI_CHAT_DEPLOYMENT")
    LLM_REASONING_EFFORT = _str("LLM_REASONING_EFFORT", "low")
    LLM_MAX_OUTPUT_TOKENS = _int("LLM_MAX_OUTPUT_TOKENS", 16000)

    # -- Local storage ---------------------------------------------------------
    DATA_DIR = _path("DATA_DIR", BACKEND_DIR / "data")
    TEMPLATE_PATH = _path("MAPPING_TEMPLATE", PROJECT_DIR / "templates" / "MARC_MBEW_Mappings.xlsx")

    # -- Validation (demo: one plant against the Databricks output) -----------
    VALIDATION_PLANT = _str("VALIDATION_PLANT", "1021")
    # Share of Databricks rows that must also be in our output.
    MATCH_PASS_MARK = float(_str("MATCH_PASS_MARK", "0.95"))
    # Share of matched rows whose key field values must agree.
    FIELD_PASS_MARK = float(_str("FIELD_PASS_MARK", "0.99"))

    # -- Databricks pipeline -------------------------------------------------------
    DATABRICKS_HOST = _str("DATABRICKS_HOST")
    DATABRICKS_TOKEN = _str("DATABRICKS_TOKEN")
    DATABRICKS_WAREHOUSE_ID = _str("DATABRICKS_WAREHOUSE_ID")
    DATABRICKS_NOTEBOOK_ROOT = _str("DATABRICKS_NOTEBOOK_ROOT")
    # Unity Catalog Volume the ECC file is uploaded to before the silver table is built.
    DATABRICKS_VOLUME_PATH = _str("DATABRICKS_VOLUME_PATH", "/Volumes/dbr_agent/silver/sap")
    DBX_SILVER_TABLE = _str("DBX_SILVER_TABLE", "dbr_agent.silver.marc_dap")
    DBX_GOLD_TABLE = _str("DBX_GOLD_TABLE", "dbr_agent.gold.marc_dap")
    # Rule book used for code generation (local copy) and the text shown from SharePoint.
    DBX_RULEBOOK_LOCAL = _path("DBX_RULEBOOK_LOCAL", PROJECT_DIR / "rules" / "databricks" / "MARC_Rule_Book_dbr_agent.csv")
    DBX_ROW_RULES = _path("DBX_ROW_RULES", PROJECT_DIR / "rules" / "databricks" / "row_rules_MARC.json")
    SP_DBX_RULEBOOK_PATH = _str("SP_DBX_RULEBOOK_PATH", "Mappings/Databricks/MARC_Rule_Book_dbr_agent.txt")
    DBX_MAX_FIX_ATTEMPTS = int(_str("DBX_MAX_FIX_ATTEMPTS", "3"))   # static-check fix loop
    DBX_MAX_RUN_ATTEMPTS = int(_str("DBX_MAX_RUN_ATTEMPTS", "2"))   # runtime-error fix loop
    DBX_PREVIEW_ROWS = int(_str("DBX_PREVIEW_ROWS", "500"))         # gold rows kept for the UI

    FRONTEND_ORIGIN = _str("FRONTEND_ORIGIN", "http://localhost:5180")

    @property
    def sharepoint_configured(self) -> bool:
        return all([self.TENANT_ID, self.CLIENT_ID, self.CLIENT_SECRET,
                    self.SHAREPOINT_HOSTNAME, self.SITE_PATH])

    @property
    def databricks_configured(self) -> bool:
        return all([self.DATABRICKS_HOST, self.DATABRICKS_TOKEN, self.DATABRICKS_WAREHOUSE_ID,
                    self.DATABRICKS_NOTEBOOK_ROOT])

    @property
    def llm_configured(self) -> bool:
        return self.LLM_PROVIDER == "azure" and all([
            self.AZURE_OPENAI_API_KEY, self.AZURE_OPENAI_ENDPOINT,
            self.AZURE_OPENAI_API_VERSION, self.AZURE_OPENAI_CHAT_DEPLOYMENT])


settings = Settings()

for sub in ("cache", "runs", "docs", "mappings"):
    (settings.DATA_DIR / sub).mkdir(parents=True, exist_ok=True)
