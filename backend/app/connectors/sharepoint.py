"""
Thin Microsoft Graph client for one SharePoint site (reused from
Sharepoint-RO-Automation).

    - app-only auth (MSAL client credentials), token cached until it expires
    - resolves the site ID from the host name + site path
    - lists a document-library folder, downloads by item ID

429/503 responses are retried with the Retry-After delay Graph asks for.
"""
from __future__ import annotations

import time
from urllib.parse import quote

import msal
import requests

from app.config import settings

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_LIST_SELECT = "id,name,eTag,cTag,size,lastModifiedDateTime,file,folder,webUrl"
_RETRY_STATUSES = {429, 503}
_MAX_RETRIES = 4


class SharePointAuthError(RuntimeError):
    pass


def _enc(path: str) -> str:
    return quote(path.strip("/"), safe="/")


class SharePointClient:
    def __init__(self) -> None:
        self._token: str | None = None
        self._token_exp = 0.0
        self._site_id: str | None = None

    # -- auth -------------------------------------------------------------

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        app = msal.ConfidentialClientApplication(
            client_id=settings.CLIENT_ID,
            client_credential=settings.CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{settings.TENANT_ID}",
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in result:
            raise SharePointAuthError(
                f"Failed to acquire token: {result.get('error')} - {result.get('error_description')}")
        self._token = result["access_token"]
        self._token_exp = time.time() + int(result.get("expires_in", 3600))
        return self._token

    def _request(self, method: str, url: str, *, auth: bool = True, **kwargs) -> requests.Response:
        extra_headers = kwargs.pop("headers", None) or {}
        for attempt in range(_MAX_RETRIES + 1):
            headers = dict(extra_headers)
            if auth:
                headers["Authorization"] = f"Bearer {self._get_token()}"
            resp = requests.request(method, url, headers=headers,
                                    timeout=settings.HTTP_TIMEOUT, **kwargs)
            if resp.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES:
                time.sleep(min(float(resp.headers.get("Retry-After", 2 ** attempt)), 60))
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError("unreachable")

    # -- site -------------------------------------------------------------

    def site_id(self) -> str:
        if not self._site_id:
            url = f"{GRAPH_BASE}/sites/{settings.SHAREPOINT_HOSTNAME}:{settings.SITE_PATH}"
            self._site_id = self._request("GET", url).json()["id"]
        return self._site_id

    def site_info(self) -> dict:
        url = f"{GRAPH_BASE}/sites/{settings.SHAREPOINT_HOSTNAME}:{settings.SITE_PATH}"
        data = self._request("GET", url).json()
        self._site_id = data["id"]
        return {"id": data["id"], "name": data.get("displayName"), "webUrl": data.get("webUrl")}

    # -- read -------------------------------------------------------------

    def list_folder(self, folder_path: str) -> list[dict]:
        """Items directly inside folder_path ('' = library root)."""
        sid = self.site_id()
        if folder_path.strip("/"):
            url = f"{GRAPH_BASE}/sites/{sid}/drive/root:/{_enc(folder_path)}:/children"
        else:
            url = f"{GRAPH_BASE}/sites/{sid}/drive/root/children"
        url += f"?$select={_LIST_SELECT}&$top=200"
        items: list[dict] = []
        while url:
            data = self._request("GET", url).json()
            items.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
        return items

    def download(self, item_id: str) -> bytes:
        url = f"{GRAPH_BASE}/sites/{self.site_id()}/drive/items/{item_id}/content"
        return self._request("GET", url).content

    def item(self, path: str) -> dict:
        """Metadata of the file or folder at path ('' = library root)."""
        sid = self.site_id()
        url = (f"{GRAPH_BASE}/sites/{sid}/drive/root:/{_enc(path)}" if path.strip("/")
               else f"{GRAPH_BASE}/sites/{sid}/drive/root")
        return self._request("GET", f"{url}?$select={_LIST_SELECT}").json()

    def download_path(self, path: str) -> bytes:
        url = f"{GRAPH_BASE}/sites/{self.site_id()}/drive/root:/{_enc(path)}:/content"
        return self._request("GET", url).content
