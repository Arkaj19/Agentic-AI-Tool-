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

    FRONTEND_ORIGIN = _str("FRONTEND_ORIGIN", "http://localhost:5180")

    @property
    def sharepoint_configured(self) -> bool:
        return all([self.TENANT_ID, self.CLIENT_ID, self.CLIENT_SECRET,
                    self.SHAREPOINT_HOSTNAME, self.SITE_PATH])

    @property
    def llm_configured(self) -> bool:
        return self.LLM_PROVIDER == "azure" and all([
            self.AZURE_OPENAI_API_KEY, self.AZURE_OPENAI_ENDPOINT,
            self.AZURE_OPENAI_API_VERSION, self.AZURE_OPENAI_CHAT_DEPLOYMENT])


settings = Settings()

for sub in ("cache", "runs", "docs", "mappings"):
    (settings.DATA_DIR / sub).mkdir(parents=True, exist_ok=True)
