"""Tests for owner people / access management."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.people import PeopleService

ORG = uuid.uuid4()


def _result(value):
    """A db.execute() result whose scalar_one_or_none() returns value."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


class TestAssign:
    @pytest.mark.asyncio
    async def test_bad_role_rejected(self):
        db = AsyncMock()
        out = await PeopleService(db=db).assign(ORG, telegram_id=1, role="superuser")
        assert out == {"ok": False, "error": "bad_role"}
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_deprecated_role_rejected(self):
        db = AsyncMock()
        out = await PeopleService(db=db).assign(ORG, telegram_id=1, role="chef")
        assert out == {"ok": False, "error": "bad_role"}

    @pytest.mark.asyncio
    async def test_telegram_in_use(self):
        other = MagicMock()
        other.id = uuid.uuid4()
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_result(other)])  # clash check finds another user
        out = await PeopleService(db=db).assign(ORG, telegram_id=42, role="admin", name="X")
        assert out == {"ok": False, "error": "telegram_in_use"}
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_new_manager(self):
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_result(None), MagicMock()])  # no clash, then update reg
        db.add = MagicMock()
        db.commit = AsyncMock()

        out = await PeopleService(db=db).assign(
            ORG, telegram_id=555, role="admin", name="Иван", branch_id=str(uuid.uuid4())
        )
        assert out["ok"] is True
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_new_requires_name(self):
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_result(None)])
        out = await PeopleService(db=db).assign(ORG, telegram_id=7, role="owner")
        assert out == {"ok": False, "error": "name_required"}

    @pytest.mark.asyncio
    async def test_link_existing_barber(self):
        barber = MagicMock()
        barber.id = uuid.uuid4()
        db = AsyncMock()
        # clash check (None) → fetch target user (barber) → update reg
        db.execute = AsyncMock(side_effect=[_result(None), _result(barber), MagicMock()])
        db.commit = AsyncMock()

        out = await PeopleService(db=db).assign(
            ORG, telegram_id=999, role="barber", user_id=str(barber.id)
        )
        assert out["ok"] is True
        assert barber.telegram_id == 999
        assert str(barber.role) == "barber"
        db.commit.assert_awaited_once()


class TestDeactivate:
    @pytest.mark.asyncio
    async def test_deactivate_sets_inactive(self):
        user = MagicMock()
        user.is_active = True
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_result(user))
        db.commit = AsyncMock()

        out = await PeopleService(db=db).deactivate(ORG, str(uuid.uuid4()))
        assert out == {"ok": True}
        assert user.is_active is False

    @pytest.mark.asyncio
    async def test_deactivate_not_found(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_result(None))
        out = await PeopleService(db=db).deactivate(ORG, str(uuid.uuid4()))
        assert out == {"ok": False, "error": "user_not_found"}
