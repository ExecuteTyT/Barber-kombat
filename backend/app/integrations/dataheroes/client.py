"""Async client for the DataHeroes (Platrum) BFF.

DataHeroes has no public API, but its SPA talks to a JSON BFF at bff.dataheroes.pro
authenticated with a JWT (email/password login). This client mirrors that:
login -> Bearer token -> POST taskList endpoints. Fragile by nature (internal
API) — gated behind settings.dataheroes_enabled and re-logs-in on 401.
"""

import asyncio
import base64
import binascii
import json

import httpx
import structlog

from app.config import settings
from app.integrations.dataheroes.schemas import DHTask

logger = structlog.stdlib.get_logger()

DH_BASE_URL = "https://bff.dataheroes.pro/api"
RETRY_DELAYS = [5, 15, 45]  # seconds
DEFAULT_STATUS = "Нужно связаться"
# actionType sent to taskList/action to mark a task as handled ("Связались").
ACTION_CONTACT = "CONTACT"


def _jwt_sub(token: str) -> str | None:
    """Decode the ``sub`` claim from a JWT without verifying the signature.

    DataHeroes needs the acting ``userId`` in the mark-contacted payload, and it
    equals the token's ``sub`` (e.g. "auth0|UycEDxcVivWfeodGSbvfB").
    """
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)  # pad to a multiple of 4
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("sub")
    except (IndexError, ValueError, binascii.Error, json.JSONDecodeError):
        return None


class DataHeroesClient:
    """Async client for the DataHeroes BFF (login + quality-control task list)."""

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        company: str | None = None,
        base_url: str = DH_BASE_URL,
        max_concurrent: int = 5,
    ):
        self.email = email or settings.dataheroes_email
        self.password = password or settings.dataheroes_password
        self.company = company or settings.dataheroes_company
        self.base_url = base_url
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._client: httpx.AsyncClient | None = None
        self._token: str | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def login(self) -> str:
        """Authenticate and cache the JWT bearer token."""
        client = await self._get_client()
        resp = await client.post(
            "/auth/login", json={"email": self.email, "password": self.password}
        )
        resp.raise_for_status()
        token = ((resp.json() or {}).get("data") or {}).get("token")
        if not token:
            raise RuntimeError("DataHeroes login returned no token")
        self._token = token
        return token

    async def _ensure_token(self) -> str:
        if not self._token:
            await self.login()
        assert self._token is not None
        return self._token

    async def _post(self, path: str, json_body: dict) -> dict:
        """POST with retry + automatic re-login on 401 (expired token)."""
        async with self._semaphore:
            for attempt in range(len(RETRY_DELAYS) + 1):
                token = await self._ensure_token()
                client = await self._get_client()
                try:
                    resp = await client.post(
                        path,
                        json=json_body,
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if resp.status_code == 401:
                        self._token = None  # force re-login on next attempt
                        raise httpx.HTTPStatusError(
                            "401 Unauthorized", request=resp.request, response=resp
                        )
                    resp.raise_for_status()
                    return resp.json()
                except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                    if attempt >= len(RETRY_DELAYS):
                        raise
                    await logger.awarning(
                        "DataHeroes request failed, retrying", path=path, error=str(exc)
                    )
                    await asyncio.sleep(RETRY_DELAYS[attempt])
        raise RuntimeError(f"DataHeroes request failed after retries: {path}")

    async def get_qc_tasks(
        self,
        project_id: str,
        status: str = DEFAULT_STATUS,
        activations: list[int] | None = None,
        page_size: int = 200,
    ) -> list[DHTask]:
        """Fetch call tasks for a project filtered by status (default: needs-contact)."""
        body = {
            "projectId": project_id,
            "filters": {
                "visitCount": {"min": 0, "max": 100000},
                "phone": "",
                "activations": activations or [],
                "clients": {"state": "ALL", "mode": "EXCLUDE", "data": []},
            },
            "page": 1,
            "pageSize": page_size,
            "status": status,
            "sort": {"type": None, "order": None},
            "hrProject": False,
        }
        data = await self._post(f"/{self.company}/taskList/getData", body)
        rows = (data or {}).get("data") or []
        return [DHTask.model_validate(r) for r in rows]

    async def mark_contacted(
        self,
        communication_id: str,
        project_id: str,
        client_id: str | None = None,
        status_text: str = DEFAULT_STATUS,
        comment: str = "",
        tags: list[str] | None = None,
    ) -> dict:
        """Mark a task as handled ("Связались") in DataHeroes.

        Mirrors the SPA's POST to ``taskList/action`` with ``actionType=CONTACT``.
        ``userId`` is taken from the logged-in token's ``sub`` claim. ``socketId``
        (used by the SPA only to skip echoing the change back over its websocket)
        is intentionally omitted server-side.
        """
        token = await self._ensure_token()
        user_id = _jwt_sub(token)
        email = (self.email or "").lower()
        body = {
            "actionType": ACTION_CONTACT,
            "projectId": project_id,
            "communicationId": communication_id,
            "statusText": status_text,
            "data": {
                "commType": "no",
                "projectId": project_id,
                "communicationId": communication_id,
                "clientId": client_id,
                "userId": user_id,
                "userName": email,
                "email": email,
                "comment": comment,
                "communicationTags": tags or [],
            },
        }
        return await self._post(f"/{self.company}/taskList/action", body)
