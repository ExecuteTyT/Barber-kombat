"""Tests for the admin KPI service (Stage C)."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.admin_kpi import AdminKpiService

ORG_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()


class TestComposite:
    def test_falls_back_to_confirmation_when_no_surveys(self):
        assert AdminKpiService._composite(None, 80) == 80

    def test_weighted_blend(self):
        # 0.6*80 + 0.4*90 = 84
        assert AdminKpiService._composite(80, 90) == 84


class TestBranchKpi:
    @pytest.mark.asyncio
    async def test_aggregates_and_composite(self):
        survey_result = MagicMock()
        survey_result.first.return_value = (4, 80.0, 90.0, 4.5, 3, 1)
        conf_result = MagicMock()
        conf_result.first.return_value = (10, 8)

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[survey_result, conf_result])

        svc = AdminKpiService(db=db)
        kpi = await svc.get_branch_kpi(BRANCH_ID, date(2026, 6, 1))

        assert kpi["survey_count"] == 4
        assert kpi["admin_avg"] == 80
        assert kpi["master_avg"] == 90
        assert kpi["stars_avg"] == 4.5
        assert kpi["nps"] == 75  # 3/4
        assert kpi["negatives"] == 1
        assert kpi["confirmation_rate"] == 80  # 8/10
        assert kpi["composite_score"] == 80  # 0.6*80 + 0.4*80
        assert kpi["month"] == "2026-06"

    @pytest.mark.asyncio
    async def test_no_surveys_uses_confirmation(self):
        survey_result = MagicMock()
        survey_result.first.return_value = (0, None, None, None, 0, 0)
        conf_result = MagicMock()
        conf_result.first.return_value = (5, 5)

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[survey_result, conf_result])

        svc = AdminKpiService(db=db)
        kpi = await svc.get_branch_kpi(BRANCH_ID, date(2026, 6, 15))

        assert kpi["survey_count"] == 0
        assert kpi["admin_avg"] is None
        assert kpi["nps"] is None
        assert kpi["confirmation_rate"] == 100
        assert kpi["composite_score"] == 100  # falls back to confirmation


class TestNetworkKpi:
    @pytest.mark.asyncio
    async def test_ranks_branches_by_composite(self):
        b1 = MagicMock()
        b1.id = uuid.uuid4()
        b1.name = "Менделеева"
        b2 = MagicMock()
        b2.id = uuid.uuid4()
        b2.name = "Корабельная"
        branches_result = MagicMock()
        branches_result.scalars.return_value.all.return_value = [b1, b2]

        db = AsyncMock()
        db.execute = AsyncMock(return_value=branches_result)

        svc = AdminKpiService(db=db)
        # Stub per-branch KPI: b1 weaker (60), b2 stronger (90)
        svc.get_branch_kpi = AsyncMock(
            side_effect=[
                {"branch_id": str(b1.id), "composite_score": 60},
                {"branch_id": str(b2.id), "composite_score": 90},
            ]
        )

        data = await svc.get_network_kpi(ORG_ID, date(2026, 6, 1))

        by_id = {b["branch_id"]: b for b in data["branches"]}
        assert by_id[str(b2.id)]["rank"] == 1  # higher composite ranks first
        assert by_id[str(b1.id)]["rank"] == 2
        assert by_id[str(b2.id)]["branch_name"] == "Корабельная"
        assert data["month"] == "2026-06"
