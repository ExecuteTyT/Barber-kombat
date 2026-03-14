"""Async HTTP client for YClients API with rate limiting and retry."""

import asyncio
from datetime import date

import httpx
import structlog

from app.config import settings
from app.integrations.yclients.schemas import (
    YClientClient,
    YClientRecord,
    YClientServiceItem,
    YClientStaff,
)

logger = structlog.stdlib.get_logger()

YCLIENTS_BASE_URL = "https://api.yclients.com/api/v1"
RETRY_DELAYS = [10, 30, 90]  # seconds


class YClientsClient:
    """Async client for YClients REST API.

    Features:
    - Rate limiting via asyncio.Semaphore (10 concurrent requests)
    - Retry with exponential backoff (3 attempts: 10s, 30s, 90s)
    - Pydantic parsing of all responses

    Authentication per YClients docs:
    - Partner token (Bearer) is always required
    - User token is required for methods accessing user-specific data
    - Header format: Authorization: Bearer <partner>, User <user>
    """

    def __init__(
        self,
        partner_token: str | None = None,
        user_token: str | None = None,
        base_url: str = YCLIENTS_BASE_URL,
        max_concurrent: int = 10,
    ):
        self.partner_token = partner_token or settings.yclients_partner_token
        self.user_token = user_token or settings.yclients_user_token
        self.base_url = base_url
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._client: httpx.AsyncClient | None = None

    def _get_headers(self) -> dict[str, str]:
        auth = f"Bearer {self.partner_token}"
        if self.user_token:
            auth += f", User {self.user_token}"
        return {
            "Authorization": auth,
            "Accept": "application/vnd.yclients.v2+json",
            "Content-Type": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> dict | list:
        """Execute an HTTP request with rate limiting and retry."""
        last_error: Exception | None = None

        for attempt, delay in enumerate(RETRY_DELAYS):
            async with self._semaphore:
                try:
                    client = await self._get_client()
                    response = await client.request(method, path, **kwargs)
                    response.raise_for_status()

                    data = response.json()

                    # YClients v2 wraps responses in {"success": true, "data": ..., "meta": ...}
                    if isinstance(data, dict) and "data" in data:
                        return data["data"]
                    return data

                except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as e:
                    last_error = e
                    await logger.awarning(
                        "YClients API request failed",
                        path=path,
                        attempt=attempt + 1,
                        error=str(e),
                        retry_in=delay,
                    )
                    if attempt < len(RETRY_DELAYS) - 1:
                        await asyncio.sleep(delay)

        await logger.aerror(
            "YClients API request failed after all retries",
            path=path,
            error=str(last_error),
        )
        raise last_error  # type: ignore[misc]

    # --- Public API methods ---

    async def get_records(
        self,
        company_id: int,
        date_from: date,
        date_to: date,
        page: int = 1,
        count: int = 300,
    ) -> list[YClientRecord]:
        """Get visit records for a company within a date range.

        Automatically paginates to fetch all records when page=1.
        """
        all_records: list[YClientRecord] = []
        current_page = page

        while True:
            params = {
                "start_date": date_from.isoformat(),
                "end_date": date_to.isoformat(),
                "page": current_page,
                "count": count,
            }
            data = await self._request("GET", f"/records/{company_id}", params=params)

            if not isinstance(data, list) or len(data) == 0:
                break

            all_records.extend(YClientRecord.model_validate(item) for item in data)

            if len(data) < count:
                break  # last page
            current_page += 1

        return all_records

    async def get_record(self, company_id: int, record_id: int) -> YClientRecord:
        """Get a single visit record by ID."""
        data = await self._request("GET", f"/record/{company_id}/{record_id}")
        return YClientRecord.model_validate(data)

    async def get_staff(self, company_id: int) -> list[YClientStaff]:
        """Get all staff members for a company."""
        data = await self._request("GET", f"/staff/{company_id}")
        if not isinstance(data, list):
            return []
        return [YClientStaff.model_validate(item) for item in data]

    async def get_services(self, company_id: int) -> list[YClientServiceItem]:
        """Get all services for a company."""
        data = await self._request("GET", f"/services/{company_id}")
        if not isinstance(data, list):
            return []
        return [YClientServiceItem.model_validate(item) for item in data]

    async def get_clients(
        self,
        company_id: int,
        page: int = 1,
        count: int = 200,
    ) -> list[YClientClient]:
        """Get clients list for a company."""
        params = {"page": page, "count": count}
        data = await self._request("GET", f"/clients/{company_id}", params=params)
        if not isinstance(data, list):
            return []
        return [YClientClient.model_validate(item) for item in data]

    async def get_client(self, company_id: int, client_id: int) -> YClientClient:
        """Get a single client by ID."""
        data = await self._request("GET", f"/client/{company_id}/{client_id}")
        return YClientClient.model_validate(data)
