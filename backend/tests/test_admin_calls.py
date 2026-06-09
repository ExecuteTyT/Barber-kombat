"""Tests for admin call-list and call marking (Stage A)."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.admin import AdminService

ORG_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()
ADMIN_ID = uuid.uuid4()


def _visit(record_id: int, confirmed: bool, client_id=None):
    v = MagicMock()
    v.id = uuid.uuid4()
    v.yclients_record_id = record_id
    v.confirmed = confirmed
    v.client_id = client_id
    v.date = date(2026, 6, 10)
    v.created_at = date(2026, 6, 9)
    return v


class TestGetCallList:
    @pytest.mark.asyncio
    async def test_confirmation_rate_and_call_progress(self):
        v1 = _visit(101, confirmed=True)
        v2 = _visit(102, confirmed=False, client_id=uuid.uuid4())
        v3 = _visit(103, confirmed=False, client_id=uuid.uuid4())

        rows_result = MagicMock()
        rows_result.all.return_value = [(v1, "Барбер1"), (v2, "Барбер2"), (v3, "Барбер3")]

        called_result = MagicMock()
        called_result.all.return_value = [MagicMock(yclients_record_id=103, result="confirmed")]

        c2_row = MagicMock()
        c2_row.name = "Клиент А"
        c2_row.phone = "+79990000002"
        client2 = MagicMock()
        client2.first.return_value = c2_row
        c3_row = MagicMock()
        c3_row.name = "Клиент Б"
        c3_row.phone = "+79990000003"
        client3 = MagicMock()
        client3.first.return_value = c3_row

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[rows_result, called_result, client2, client3])

        svc = AdminService(db=db)
        data = await svc.get_call_list(BRANCH_ID, date(2026, 6, 9))

        assert data["total_upcoming"] == 3
        assert data["confirmed_upcoming"] == 1
        assert data["confirmation_rate"] == 33  # 1/3
        assert data["to_call_count"] == 2  # v2, v3 unconfirmed
        assert data["called_count"] == 1  # v3 was called
        assert data["call_progress"] == 50  # 1/2
        # v3 marked called, v2 not
        by_rec = {t["yclients_record_id"]: t for t in data["to_call"]}
        assert by_rec[103]["called"] is True
        assert by_rec[102]["called"] is False
        assert by_rec[102]["client_name"] == "Клиент А"

    @pytest.mark.asyncio
    async def test_empty_upcoming_is_100_percent(self):
        rows_result = MagicMock()
        rows_result.all.return_value = []
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[rows_result])
        svc = AdminService(db=db)
        data = await svc.get_call_list(BRANCH_ID, date(2026, 6, 9))
        assert data["confirmation_rate"] == 100
        assert data["call_progress"] == 100
        assert data["to_call"] == []


class TestGetHistory:
    @pytest.mark.asyncio
    async def test_confirmed_rate_uses_flag_and_completed_only(self):
        main = MagicMock()
        main.all.return_value = [
            MagicMock(date=date(2026, 6, 8), records_count=10, products_sold=2, revenue=100000),
        ]
        conf = MagicMock()
        conf.all.return_value = [MagicMock(date=date(2026, 6, 8), confirmed_count=6)]
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[main, conf])

        svc = AdminService(db=db)
        data = await svc.get_history(BRANCH_ID, 2026, 6)

        assert len(data["days"]) == 1
        day = data["days"][0]
        assert day["records_count"] == 10
        assert day["revenue"] == 100000
        assert day["confirmed_rate"] == 60  # 6 / 10


class TestMarkCall:
    @pytest.mark.asyncio
    async def test_upserts_call_log(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        svc = AdminService(db=db)

        await svc.mark_call(
            organization_id=ORG_ID,
            branch_id=BRANCH_ID,
            admin_id=ADMIN_ID,
            yclients_record_id=102,
            result="no_answer",
            call_date=date(2026, 6, 9),
        )

        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()
