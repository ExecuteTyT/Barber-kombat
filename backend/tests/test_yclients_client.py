"""Tests for YClients API client with mocked HTTP responses."""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations.yclients.client import YClientsClient
from app.integrations.yclients.schemas import (
    YClientClient,
    YClientRecord,
    YClientServiceItem,
    YClientStaff,
)

# --- Fixtures ---


@pytest.fixture
def client():
    return YClientsClient(
        api_key="test_key",
        bearer_token="test_token",
        base_url="https://api.test.com/api/v1",
        max_concurrent=10,
    )


@pytest.fixture
def sample_records_response():
    return {
        "success": True,
        "data": [
            {
                "id": 1001,
                "company_id": 555,
                "staff_id": 10,
                "client": {"id": 200, "name": "Иван Петров", "phone": "+79001234567"},
                "date": "2024-10-13",
                "datetime": "2024-10-13 10:00:00",
                "services": [
                    {"id": 1, "title": "Стрижка", "cost": 1500.0, "first_cost": 1500.0, "amount": 1},
                    {"id": 2, "title": "Воск", "cost": 300.0, "first_cost": 300.0, "amount": 1},
                ],
                "goods_transactions": [
                    {"id": 50, "title": "Шампунь", "cost": 800.0, "amount": 1, "good_id": 100},
                ],
                "cost": 2600.0,
                "paid_full": 1,
                "visit_attendance": 1,
                "attendance": 1,
            },
            {
                "id": 1002,
                "company_id": 555,
                "staff_id": 11,
                "client": {"id": 201, "name": "Сергей Иванов", "phone": "+79009876543"},
                "date": "2024-10-13",
                "datetime": "2024-10-13 11:00:00",
                "services": [
                    {"id": 3, "title": "Бритьё", "cost": 1000.0, "first_cost": 1000.0, "amount": 1},
                ],
                "goods_transactions": [],
                "cost": 1000.0,
                "paid_full": 2,
                "visit_attendance": 1,
                "attendance": 1,
            },
        ],
    }


@pytest.fixture
def sample_staff_response():
    return {
        "success": True,
        "data": [
            {"id": 10, "name": "Павел", "specialization": "Барбер", "fired": 0},
            {"id": 11, "name": "Лев", "specialization": "Барбер", "fired": 0},
            {"id": 12, "name": "Марк", "specialization": "Барбер", "fired": 1},
        ],
    }


@pytest.fixture
def sample_services_response():
    return {
        "success": True,
        "data": [
            {"id": 1, "title": "Стрижка", "category_id": 1, "price_min": 1500, "price_max": 1500},
            {"id": 2, "title": "Воск", "category_id": 2, "price_min": 300, "price_max": 300},
        ],
    }


@pytest.fixture
def sample_clients_response():
    return {
        "success": True,
        "data": [
            {
                "id": 200,
                "name": "Иван Петров",
                "phone": "+79001234567",
                "birth_date": "1990-05-15",
                "visits_count": 12,
            },
        ],
    }


# --- Helper ---


def mock_response(json_data, status_code=200):
    """Create a mock httpx.Response."""
    response = httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "https://test.com"),
    )
    return response


# --- Tests: Parsing responses ---


class TestGetRecords:
    @pytest.mark.asyncio
    async def test_parse_records(self, client, sample_records_response):
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_response(sample_records_response))
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            records = await client.get_records(555, date(2024, 10, 13), date(2024, 10, 13))

        assert len(records) == 2
        assert all(isinstance(r, YClientRecord) for r in records)

        # First record
        r = records[0]
        assert r.id == 1001
        assert r.staff_id == 10
        assert r.client is not None
        assert r.client.name == "Иван Петров"
        assert len(r.services) == 2
        assert r.services[0].title == "Стрижка"
        assert r.services[1].title == "Воск"
        assert len(r.goods_transactions) == 1
        assert r.goods_transactions[0].title == "Шампунь"
        assert r.cost == 2600.0
        assert r.visit_attendance == 1

    @pytest.mark.asyncio
    async def test_empty_records(self, client):
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(
                return_value=mock_response({"success": True, "data": []})
            )
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            records = await client.get_records(555, date(2024, 10, 1), date(2024, 10, 1))

        assert records == []


class TestGetStaff:
    @pytest.mark.asyncio
    async def test_parse_staff(self, client, sample_staff_response):
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_response(sample_staff_response))
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            staff = await client.get_staff(555)

        assert len(staff) == 3
        assert all(isinstance(s, YClientStaff) for s in staff)
        assert staff[0].name == "Павел"
        assert staff[2].fired == 1


class TestGetServices:
    @pytest.mark.asyncio
    async def test_parse_services(self, client, sample_services_response):
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_response(sample_services_response))
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            services = await client.get_services(555)

        assert len(services) == 2
        assert all(isinstance(s, YClientServiceItem) for s in services)
        assert services[0].title == "Стрижка"
        assert services[1].price_min == 300


class TestGetClients:
    @pytest.mark.asyncio
    async def test_parse_clients(self, client, sample_clients_response):
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_response(sample_clients_response))
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            clients = await client.get_clients(555)

        assert len(clients) == 1
        assert isinstance(clients[0], YClientClient)
        assert clients[0].name == "Иван Петров"
        assert clients[0].visits_count == 12

    @pytest.mark.asyncio
    async def test_get_single_client(self, client):
        single = {"success": True, "data": {"id": 200, "name": "Иван", "phone": "+7900", "birth_date": "", "visits_count": 5}}
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_response(single))
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            result = await client.get_client(555, 200)

        assert isinstance(result, YClientClient)
        assert result.id == 200


class TestGetRecord:
    @pytest.mark.asyncio
    async def test_get_single_record(self, client):
        single = {
            "success": True,
            "data": {
                "id": 1001,
                "company_id": 555,
                "staff_id": 10,
                "client": {"id": 200, "name": "Иван", "phone": "+7900"},
                "date": "2024-10-13",
                "datetime": "2024-10-13 10:00:00",
                "services": [],
                "goods_transactions": [],
                "cost": 1500.0,
                "paid_full": 1,
                "visit_attendance": 1,
                "attendance": 1,
            },
        }
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_response(single))
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            record = await client.get_record(555, 1001)

        assert isinstance(record, YClientRecord)
        assert record.id == 1001


# --- Tests: Retry ---


class TestRetry:
    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, client):
        """Should retry on HTTP 500 and succeed on third attempt."""
        error_response = mock_response({"error": "server error"}, 500)
        error_response.raise_for_status = lambda: (_ for _ in ()).throw(
            httpx.HTTPStatusError("500", request=error_response.request, response=error_response)
        )

        success_response = mock_response({"success": True, "data": []})

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(
                side_effect=[error_response, error_response, success_response]
            )
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            with patch("app.integrations.yclients.client.asyncio.sleep", new_callable=AsyncMock):
                records = await client.get_records(555, date(2024, 10, 1), date(2024, 10, 1))

        assert records == []
        assert mock_http.request.call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_all_retries_fail(self, client):
        """Should raise after all 3 retry attempts fail."""
        error_response = mock_response({"error": "server error"}, 500)
        error_response.raise_for_status = lambda: (_ for _ in ()).throw(
            httpx.HTTPStatusError("500", request=error_response.request, response=error_response)
        )

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=error_response)
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            with (
                patch("app.integrations.yclients.client.asyncio.sleep", new_callable=AsyncMock),
                pytest.raises(httpx.HTTPStatusError),
            ):
                await client._request("GET", "/records/555")


# --- Tests: Rate Limiting ---


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """Verify that the semaphore limits concurrent requests."""
        max_concurrent_seen = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def slow_request(*args, **kwargs):
            nonlocal max_concurrent_seen, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent_seen:
                    max_concurrent_seen = current_concurrent
            await asyncio.sleep(0.02)
            async with lock:
                current_concurrent -= 1
            return mock_response({"success": True, "data": []})

        yclient = YClientsClient(
            api_key="k", bearer_token="t", base_url="https://test.com", max_concurrent=3
        )

        with patch.object(yclient, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.request = slow_request
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            tasks = [
                yclient.get_records(555, date(2024, 1, 1), date(2024, 1, 1)) for _ in range(10)
            ]
            await asyncio.gather(*tasks)

        # Semaphore should limit to at most 3 concurrent
        assert max_concurrent_seen <= 3


# --- Tests: Headers ---


class TestHeaders:
    def test_auth_headers(self, client):
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer test_token"
        assert "yclients" in headers["Accept"]
