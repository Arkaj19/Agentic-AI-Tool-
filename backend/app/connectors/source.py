"""
Where the tool reads files from: the SharePoint document library (Microsoft
Graph) or, with SOURCE_MODE=local, a folder laid out the same way.

Every file is addressed by its path inside the library, e.g.
"MARC_DAP 8.10.26.XLSX" or "Mappings/Mappings for MARC.pdf".
Parsed tables are cached as Parquet keyed by the file's version.
"""
from __future__ import annotations

import hashlib
import io
import re
import threading
import time
import zipfile
from pathlib import Path, PurePosixPath

import pandas as pd

from app.config import settings
from app.connectors.sharepoint import SharePointClient

TABLE_EXT = (".xlsx", ".xls", ".xlsm", ".csv")
DOC_EXT = (".pdf", ".docx", ".txt", ".md")

_client = SharePointClient()
_mem: dict[str, pd.DataFrame] = {}
_locks: dict[str, threading.Lock] = {}
_status_cache: dict = {"at": 0.0, "value": None}


def mode() -> str:
    return "local" if settings.SOURCE_MODE == "local" else "sharepoint"


def _clean(path: str) -> str:
    p = str(PurePosixPath("/" + (path or "").replace("\\", "/"))).lstrip("/")
    if ".." in p.split("/"):
        raise ValueError("Invalid path")
    return p


def _local(path: str) -> Path:
    return settings.LOCAL_SOURCE_ROOT / _clean(path)


def detect_table(name: str) -> str | None:
    m = re.match(r"^(MARA|MARC|MBEW|MARD|MARM)[_\s-]", name, re.IGNORECASE)
    return m.group(1).upper() if m else None


# -- status ------------------------------------------------------------------

def status(force: bool = False) -> dict:
    now = time.time()
    if not force and _status_cache["value"] and now - _status_cache["at"] < 60:
        return _status_cache["value"]
    if mode() == "local":
        value = {"mode": "local", "connected": settings.LOCAL_SOURCE_ROOT.exists(), "detail": "Local folder"}
    elif not settings.sharepoint_configured:
        value = {"mode": "sharepoint", "connected": False, "detail": "Not configured"}
    else:
        try:
            info = _client.site_info()
            value = {"mode": "sharepoint", "connected": True, "detail": info.get("name") or settings.SITE_PATH}
        except Exception as exc:
            value = {"mode": "sharepoint", "connected": False, "detail": f"{type(exc).__name__}: {str(exc)[:160]}"}
    _status_cache.update(at=now, value=value)
    return value


# -- browsing ---------------------------------------------------------------------

def _entry(name: str, path: str, is_folder: bool, size: int, modified, version: str) -> dict:
    ext = PurePosixPath(name).suffix.lower()
    return {"name": name, "path": path, "type": "folder" if is_folder else "file", "size": size,
            "modified": modified, "ext": ext, "version": version}


def browse(path: str = "") -> list[dict]:
    path = _clean(path)
    out = []
    if mode() == "local":
        folder = _local(path)
        if not folder.is_dir():
            raise FileNotFoundError(f"Folder '{path}' not found")
        for p in sorted(folder.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            st = p.stat()
            out.append(_entry(p.name, f"{path}/{p.name}".strip("/"), p.is_dir(), st.st_size,
                              pd.Timestamp(st.st_mtime, unit="s", tz="UTC").isoformat(), f"{int(st.st_mtime)}-{st.st_size}"))
        return out
    for it in _client.list_folder(path):
        out.append(_entry(it["name"], f"{path}/{it['name']}".strip("/"), "folder" in it, it.get("size", 0),
                          it.get("lastModifiedDateTime"), it.get("cTag") or it.get("eTag") or ""))
    return sorted(out, key=lambda e: (e["type"] == "file", e["name"].lower()))


def info(path: str) -> dict:
    path = _clean(path)
    name = PurePosixPath(path).name
    if mode() == "local":
        p = _local(path)
        if not p.is_file():
            raise FileNotFoundError(f"File '{path}' not found")
        st = p.stat()
        return _entry(name, path, False, st.st_size, pd.Timestamp(st.st_mtime, unit="s", tz="UTC").isoformat(),
                      f"{int(st.st_mtime)}-{st.st_size}")
    it = _client.item(path)
    if "folder" in it:
        raise FileNotFoundError(f"'{path}' is a folder")
    return _entry(it["name"], path, False, it.get("size", 0), it.get("lastModifiedDateTime"),
                  it.get("cTag") or it.get("eTag") or "")


def read_bytes(path: str) -> bytes:
    path = _clean(path)
    if mode() == "local":
        return _local(path).read_bytes()
    return _client.download_path(path)


# -- tables (ECC extracts, Databricks output) -----------------------------------------

def _cache_path(f: dict) -> Path:
    key = hashlib.sha1(f"{f['path']}|{f['version']}".encode()).hexdigest()[:16]
    return settings.DATA_DIR / "cache" / f"{PurePosixPath(f['name']).stem}-{key}.parquet"


def _parse_table(content: bytes, name: str) -> pd.DataFrame:
    buf = io.BytesIO(content)
    if name.lower().endswith(".csv"):
        return pd.read_csv(buf, dtype=str, keep_default_na=False, low_memory=False)
    try:
        return pd.read_excel(buf, dtype=str, keep_default_na=False, engine="calamine")
    except Exception:
        buf.seek(0)
        return pd.read_excel(buf, dtype=str, keep_default_na=False, engine="openpyxl")


def load_table(path: str) -> tuple[pd.DataFrame, dict]:
    """(dataframe with the file's own headers, all values as text; file info)."""
    f = info(path)
    if f["ext"] not in TABLE_EXT:
        raise ValueError(f"{f['name']} is not an Excel or CSV file")
    cache = _cache_path(f)
    with _locks.setdefault(str(cache), threading.Lock()):
        if str(cache) in _mem:
            return _mem[str(cache)], f
        if cache.exists():
            df = pd.read_parquet(cache)
        else:
            df = _parse_table(read_bytes(path), f["name"])
            df = df.astype(str).replace({"nan": "", "NaT": "", "None": ""})
            df.columns = [str(c).strip() for c in df.columns]
            df.to_parquet(cache, index=False)
        if len(_mem) >= 3:
            _mem.pop(next(iter(_mem)))
        _mem[str(cache)] = df
        return df, f


# -- documents (mapping rules) ----------------------------------------------------------

def _docx_text(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    return re.sub(r"<[^>]+>", "", xml)


def read_document(path: str) -> dict:
    f = info(path)
    if f["ext"] not in DOC_EXT:
        raise ValueError(f"{f['name']}: pick a PDF, Word or text file")
    content = read_bytes(path)
    if f["ext"] == ".pdf":
        from pypdf import PdfReader
        text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(content)).pages)
    elif f["ext"] == ".docx":
        text = _docx_text(content)
    else:
        text = content.decode("utf-8-sig", "ignore")
    text = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip()
    if not text:
        raise ValueError(f"No text found in {f['name']} (scanned PDFs are not supported)")
    return {**f, "text": text}
