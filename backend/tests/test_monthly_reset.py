"""Tests for the MonthlyResetService.

Verifies monthly lifecycle:
- Champion determination per branch
- Prize fund freezing (kombat_monthly report saved)
- New PVR records with zeroes for the new month
- Plan copying to the new month
- Idempotency (running twice doesn't duplicate records)
- History preservation (old data untouched)
"""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.monthly_reset import MonthlyResetService, _next_month


# --- Helpers ---

ORG_ID = uuid.uuid4()
BRANCH_ID_1 = uuid.uuid4()
BRANCH_ID_2 = uuid.uuid4()
BARBER_ID_1 = uuid.uuid4()
BARBER_ID_2 = uuid.uuid4()
BARBER_ID_3 = uuid.uuid4()

JANUARY = date(2026, 1, 1)
FEBRUARY = date(2026, 2, 1)


def make_branch(branch_id: uuid.UUID = BRANCH_ID_1, org_id: uuid.UUID = ORG_ID):
    branch = MagicMock()
    branch.id = branch_id
    branch.organization_id = org_id
    branch.name = "Test Branch"
    branch.is_active = True
    return branch


def make_barber(
    barber_id: uuid.UUID = BARBER_ID_1,
    name: str = "Pavel",
    org_id: uuid.UUID = ORG_ID,
    branch_id: uuid.UUID = BRANCH_ID_1,
):
    barber = MagicMock()
    barber.id = barber_id
    barber.organization_id = org_id
    barber.branch_id = branch_id
    barber.name = name
    barber.role = "barber"
    barber.is_active = True
    return barber


def make_plan(
    branch_id: uuid.UUID = BRANCH_ID_1,
    month: date = JANUARY,
    target_amount: int = 240_000_000,
    current_amount: int = 200_000_000,
):
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.organization_id = ORG_ID
    plan.branch_id = branch_id
    plan.month = month
    plan.target_amount = target_amount
    plan.current_amount = current_amount
    plan.percentage = round(current_amount / target_amount * 100, 1) if target_amount else 0
    plan.forecast_amount = None
    return plan


def make_org(org_id: uuid.UUID = ORG_ID):
    org = MagicMock()
    org.id = org_id
    org.name = "Test Network"
    org.is_active = True
    return org


# --- Tests: _next_month ---


class TestNextMonth:
    """Tests for the _next_month helper."""

    def test_regular_month(self):
        assert _next_month(date(2026, 1, 1)) == date(2026, 2, 1)

    def test_december_to_january(self):
        assert _next_month(date(2025, 12, 1)) == date(2026, 1, 1)

    def test_november_to_december(self):
        assert _next_month(date(2026, 11, 1)) == date(2026, 12, 1)

    def test_mid_month_normalizes_to_first(self):
        """Even if day != 1, next month still returns 1st."""
        assert _next_month(date(2026, 3, 15)) == date(2026, 4, 1)


# --- Tests: _finalize_branch_ratings ---


class TestFinalizeBranchRatings:
    """Tests for champion determination."""

    @pytest.mark.asyncio
    async def test_champion_is_barber_with_most_wins(self):
        """Barber with most rank=1 days is the champion."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        # Wins query result: barber1 has 10 wins, barber2 has 5
        wins_row_1 = MagicMock()
        wins_row_1.barber_id = BARBER_ID_1
        wins_row_1.wins = 10
        wins_row_1.total_score = 950.5

        wins_row_2 = MagicMock()
        wins_row_2.barber_id = BARBER_ID_2
        wins_row_2.wins = 5
        wins_row_2.total_score = 450.0

        wins_result = MagicMock()
        wins_result.all.return_value = [wins_row_1, wins_row_2]

        # Name lookups
        name_result_1 = MagicMock()
        name_result_1.scalar_one_or_none.return_value = "Pavel"

        name_result_2 = MagicMock()
        name_result_2.scalar_one_or_none.return_value = "Pavel"

        name_result_3 = MagicMock()
        name_result_3.scalar_one_or_none.return_value = "Leo"

        mock_db.execute = AsyncMock(
            side_effect=[wins_result, name_result_1, name_result_2, name_result_3]
        )

        result = await service._finalize_branch_ratings(
            ORG_ID, BRANCH_ID_1, JANUARY
        )

        assert result is not None
        assert result["barber_id"] == str(BARBER_ID_1)
        assert result["name"] == "Pavel"
        assert result["wins"] == 10
        assert len(result["standings"]) == 2
        assert result["standings"][0]["wins"] == 10
        assert result["standings"][1]["wins"] == 5

    @pytest.mark.asyncio
    async def test_no_ratings_returns_none(self):
        """When no daily_ratings exist for the month, returns None."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        wins_result = MagicMock()
        wins_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=wins_result)

        result = await service._finalize_branch_ratings(
            ORG_ID, BRANCH_ID_1, JANUARY
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_tiebreaker_uses_total_score(self):
        """When two barbers have equal wins, champion is the one with higher total_score."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        # Both have 7 wins, but barber2 has higher total_score
        # (query is already ordered by wins DESC, total_score DESC)
        wins_row_1 = MagicMock()
        wins_row_1.barber_id = BARBER_ID_2
        wins_row_1.wins = 7
        wins_row_1.total_score = 700.0

        wins_row_2 = MagicMock()
        wins_row_2.barber_id = BARBER_ID_1
        wins_row_2.wins = 7
        wins_row_2.total_score = 650.0

        wins_result = MagicMock()
        wins_result.all.return_value = [wins_row_1, wins_row_2]

        name_1 = MagicMock()
        name_1.scalar_one_or_none.return_value = "Leo"
        name_2 = MagicMock()
        name_2.scalar_one_or_none.return_value = "Leo"
        name_3 = MagicMock()
        name_3.scalar_one_or_none.return_value = "Pavel"

        mock_db.execute = AsyncMock(
            side_effect=[wins_result, name_1, name_2, name_3]
        )

        result = await service._finalize_branch_ratings(
            ORG_ID, BRANCH_ID_1, JANUARY
        )

        assert result is not None
        assert result["barber_id"] == str(BARBER_ID_2)
        assert result["name"] == "Leo"


# --- Tests: _create_new_pvr_records ---


class TestCreateNewPvrRecords:
    """Tests for PVR record initialization."""

    @pytest.mark.asyncio
    async def test_creates_zeroed_records_for_all_barbers(self):
        """Creates a PVR record with 0 revenue for each active barber."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        barber1 = make_barber(barber_id=BARBER_ID_1, name="Pavel")
        barber2 = make_barber(barber_id=BARBER_ID_2, name="Leo")

        # Query barbers
        barbers_result = MagicMock()
        barbers_result.scalars.return_value.all.return_value = [barber1, barber2]

        # Existing check — none exist
        existing_result_1 = MagicMock()
        existing_result_1.scalar_one_or_none.return_value = None
        existing_result_2 = MagicMock()
        existing_result_2.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(
            side_effect=[barbers_result, existing_result_1, existing_result_2]
        )

        added_items: list = []
        mock_db.add = MagicMock(side_effect=lambda item: added_items.append(item))

        count = await service._create_new_pvr_records(ORG_ID, FEBRUARY)

        assert count == 2
        assert len(added_items) == 2

        for item in added_items:
            assert item.organization_id == ORG_ID
            assert item.month == FEBRUARY
            assert item.cumulative_revenue == 0
            assert item.current_threshold is None
            assert item.bonus_amount == 0
            assert item.thresholds_reached == []

    @pytest.mark.asyncio
    async def test_idempotent_skips_existing_records(self):
        """Doesn't duplicate PVR records if they already exist."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        barber1 = make_barber(barber_id=BARBER_ID_1)

        barbers_result = MagicMock()
        barbers_result.scalars.return_value.all.return_value = [barber1]

        # Record already exists
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = uuid.uuid4()

        mock_db.execute = AsyncMock(side_effect=[barbers_result, existing_result])
        mock_db.add = MagicMock()

        count = await service._create_new_pvr_records(ORG_ID, FEBRUARY)

        assert count == 0
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_active_barbers_returns_zero(self):
        """Returns 0 if no active barbers exist."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        barbers_result = MagicMock()
        barbers_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=barbers_result)
        mock_db.add = MagicMock()

        count = await service._create_new_pvr_records(ORG_ID, FEBRUARY)
        assert count == 0


# --- Tests: _copy_plans ---


class TestCopyPlans:
    """Tests for plan carryover to the new month."""

    @pytest.mark.asyncio
    async def test_copies_target_amount_with_zero_progress(self):
        """Plans are copied with the same target but zero progress."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        old_plan = make_plan(branch_id=BRANCH_ID_1, month=JANUARY, target_amount=240_000_000)

        plans_result = MagicMock()
        plans_result.scalars.return_value.all.return_value = [old_plan]

        # No existing plan for new month
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(side_effect=[plans_result, existing_result])

        added_items: list = []
        mock_db.add = MagicMock(side_effect=lambda item: added_items.append(item))

        count = await service._copy_plans(ORG_ID, JANUARY, FEBRUARY)

        assert count == 1
        assert len(added_items) == 1

        new_plan = added_items[0]
        assert new_plan.organization_id == ORG_ID
        assert new_plan.branch_id == BRANCH_ID_1
        assert new_plan.month == FEBRUARY
        assert new_plan.target_amount == 240_000_000
        assert new_plan.current_amount == 0
        assert new_plan.percentage == 0.0
        assert new_plan.forecast_amount is None

    @pytest.mark.asyncio
    async def test_idempotent_skips_existing_plans(self):
        """Doesn't duplicate plans if new month already has one."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        old_plan = make_plan(branch_id=BRANCH_ID_1, month=JANUARY)

        plans_result = MagicMock()
        plans_result.scalars.return_value.all.return_value = [old_plan]

        # Plan already exists for new month
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = uuid.uuid4()

        mock_db.execute = AsyncMock(side_effect=[plans_result, existing_result])
        mock_db.add = MagicMock()

        count = await service._copy_plans(ORG_ID, JANUARY, FEBRUARY)
        assert count == 0
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_plans_returns_zero(self):
        """Returns 0 if there are no plans to copy."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        plans_result = MagicMock()
        plans_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=plans_result)

        count = await service._copy_plans(ORG_ID, JANUARY, FEBRUARY)
        assert count == 0

    @pytest.mark.asyncio
    async def test_multiple_branches_copied(self):
        """Copies plans for all branches in the organization."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        plan1 = make_plan(branch_id=BRANCH_ID_1, month=JANUARY, target_amount=200_000_000)
        plan2 = make_plan(branch_id=BRANCH_ID_2, month=JANUARY, target_amount=300_000_000)

        plans_result = MagicMock()
        plans_result.scalars.return_value.all.return_value = [plan1, plan2]

        existing_1 = MagicMock()
        existing_1.scalar_one_or_none.return_value = None
        existing_2 = MagicMock()
        existing_2.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(side_effect=[plans_result, existing_1, existing_2])

        added_items: list = []
        mock_db.add = MagicMock(side_effect=lambda item: added_items.append(item))

        count = await service._copy_plans(ORG_ID, JANUARY, FEBRUARY)

        assert count == 2
        targets = sorted([p.target_amount for p in added_items])
        assert targets == [200_000_000, 300_000_000]


# --- Tests: reset_organization (integration) ---


class TestResetOrganization:
    """Integration tests for the full reset pipeline."""

    @pytest.mark.asyncio
    async def test_full_reset_pipeline(self):
        """Verifies the full pipeline calls all steps and commits."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        with (
            patch.object(
                service, "_get_active_branches", new_callable=AsyncMock
            ) as mock_branches,
            patch.object(
                service, "_finalize_branch_ratings", new_callable=AsyncMock
            ) as mock_finalize,
            patch.object(
                service, "_save_monthly_report", new_callable=AsyncMock
            ) as mock_report,
            patch.object(
                service, "_create_new_pvr_records", new_callable=AsyncMock
            ) as mock_pvr,
            patch.object(
                service, "_copy_plans", new_callable=AsyncMock
            ) as mock_plans,
        ):
            branch1 = make_branch(BRANCH_ID_1)
            branch2 = make_branch(BRANCH_ID_2)
            mock_branches.return_value = [branch1, branch2]

            champion1 = {"barber_id": str(BARBER_ID_1), "name": "Pavel", "wins": 10}
            mock_finalize.side_effect = [champion1, None]

            mock_pvr.return_value = 3
            mock_plans.return_value = 2

            result = await service.reset_organization(ORG_ID, JANUARY)

        # Verify all methods called
        mock_branches.assert_called_once_with(ORG_ID)
        assert mock_finalize.call_count == 2
        assert mock_report.call_count == 2
        mock_pvr.assert_called_once_with(ORG_ID, FEBRUARY)
        mock_plans.assert_called_once_with(ORG_ID, JANUARY, FEBRUARY)
        mock_db.commit.assert_called_once()

        # Verify summary
        assert result["branches"] == 2
        assert result["champions"] == 1
        assert result["pvr_records_created"] == 3
        assert result["plans_copied"] == 2
        assert result["finalized_month"] == str(JANUARY)
        assert result["new_month"] == str(FEBRUARY)

    @pytest.mark.asyncio
    async def test_december_to_january_year_rollover(self):
        """December reset rolls over to January of next year."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        december = date(2025, 12, 1)
        january_next = date(2026, 1, 1)

        with (
            patch.object(
                service, "_get_active_branches", new_callable=AsyncMock
            ) as mock_branches,
            patch.object(
                service, "_finalize_branch_ratings", new_callable=AsyncMock
            ),
            patch.object(
                service, "_save_monthly_report", new_callable=AsyncMock
            ),
            patch.object(
                service, "_create_new_pvr_records", new_callable=AsyncMock
            ) as mock_pvr,
            patch.object(
                service, "_copy_plans", new_callable=AsyncMock
            ) as mock_plans,
        ):
            mock_branches.return_value = []
            mock_pvr.return_value = 0
            mock_plans.return_value = 0

            result = await service.reset_organization(ORG_ID, december)

        # PVR and plans should be created for January 2026
        mock_pvr.assert_called_once_with(ORG_ID, january_next)
        mock_plans.assert_called_once_with(ORG_ID, december, january_next)
        assert result["new_month"] == str(january_next)


# --- Tests: _save_monthly_report ---


class TestSaveMonthlyReport:
    """Tests for monthly report persistence."""

    @pytest.mark.asyncio
    async def test_saves_report_with_champion_data(self):
        """Saves a kombat_monthly report with branch revenue and champion."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        # Revenue query
        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 250_000_000
        mock_db.execute = AsyncMock(return_value=revenue_result)

        added_items: list = []
        mock_db.add = MagicMock(side_effect=lambda item: added_items.append(item))

        champion = {"barber_id": str(BARBER_ID_1), "name": "Pavel", "wins": 12}

        await service._save_monthly_report(ORG_ID, BRANCH_ID_1, JANUARY, champion)

        assert len(added_items) == 1
        report = added_items[0]
        assert report.type == "kombat_monthly"
        assert report.organization_id == ORG_ID
        assert report.branch_id == BRANCH_ID_1
        assert report.date == JANUARY
        assert report.data["total_revenue"] == 250_000_000
        assert report.data["champion"]["name"] == "Pavel"
        assert report.data["champion"]["wins"] == 12

    @pytest.mark.asyncio
    async def test_saves_report_without_champion(self):
        """Saves report even when no champion (no ratings for month)."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 0
        mock_db.execute = AsyncMock(return_value=revenue_result)

        added_items: list = []
        mock_db.add = MagicMock(side_effect=lambda item: added_items.append(item))

        await service._save_monthly_report(ORG_ID, BRANCH_ID_1, JANUARY, None)

        assert len(added_items) == 1
        report = added_items[0]
        assert report.data["champion"] is None
        assert report.data["total_revenue"] == 0


# --- Tests: reset_all_organizations ---


class TestResetAllOrganizations:
    """Tests for multi-org reset."""

    @pytest.mark.asyncio
    async def test_processes_all_active_orgs(self):
        """Runs reset for every active organization."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        org1 = make_org(uuid.uuid4())
        org2 = make_org(uuid.uuid4())

        orgs_result = MagicMock()
        orgs_result.scalars.return_value.all.return_value = [org1, org2]
        mock_db.execute = AsyncMock(return_value=orgs_result)

        with patch.object(
            service, "reset_organization", new_callable=AsyncMock
        ) as mock_reset:
            mock_reset.return_value = {"branches": 1}

            result = await service.reset_all_organizations(JANUARY)

        assert result["orgs_processed"] == 2
        assert result["errors"] == 0
        assert mock_reset.call_count == 2

    @pytest.mark.asyncio
    async def test_continues_on_org_error(self):
        """If one org fails, the others still get processed."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        org1 = make_org(uuid.uuid4())
        org2 = make_org(uuid.uuid4())

        orgs_result = MagicMock()
        orgs_result.scalars.return_value.all.return_value = [org1, org2]
        mock_db.execute = AsyncMock(return_value=orgs_result)

        with patch.object(
            service, "reset_organization", new_callable=AsyncMock
        ) as mock_reset:
            # First org fails, second succeeds
            mock_reset.side_effect = [Exception("DB error"), {"branches": 2}]

            result = await service.reset_all_organizations(JANUARY)

        assert result["orgs_processed"] == 1
        assert result["errors"] == 1

    @pytest.mark.asyncio
    async def test_empty_when_no_active_orgs(self):
        """Returns zero counts when no active organizations exist."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        orgs_result = MagicMock()
        orgs_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=orgs_result)

        result = await service.reset_all_organizations(JANUARY)
        assert result["orgs_processed"] == 0
        assert result["errors"] == 0


# --- Tests: Celery task wrapper ---


class TestMonthlyResetTask:
    """Tests for the Celery task wrapper."""

    def test_task_is_registered(self):
        """Verify the task is registered in Celery."""
        from app.tasks.monthly_reset_tasks import monthly_reset
        assert monthly_reset.name == "monthly_reset"

    @pytest.mark.asyncio
    async def test_run_monthly_reset_defaults_to_previous_month(self):
        """_run_monthly_reset without args finalizes the previous month."""
        from app.tasks.monthly_reset_tasks import _run_monthly_reset

        with patch(
            "app.database.async_session"
        ) as mock_session_maker:
            mock_db = AsyncMock()
            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_session_maker.return_value = mock_session_ctx

            with patch(
                "app.services.monthly_reset.MonthlyResetService.reset_all_organizations",
                new_callable=AsyncMock,
            ) as mock_reset:
                mock_reset.return_value = {"orgs_processed": 1, "errors": 0}
                result = await _run_monthly_reset()

            # Should have been called with previous month
            call_args = mock_reset.call_args[0]
            target_month = call_args[0]
            today = date.today()
            if today.month == 1:
                expected = date(today.year - 1, 12, 1)
            else:
                expected = date(today.year, today.month - 1, 1)
            assert target_month == expected

    @pytest.mark.asyncio
    async def test_run_monthly_reset_with_explicit_month(self):
        """_run_monthly_reset with explicit month uses that month."""
        from app.tasks.monthly_reset_tasks import _run_monthly_reset

        with patch(
            "app.database.async_session"
        ) as mock_session_maker:
            mock_db = AsyncMock()
            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_session_maker.return_value = mock_session_ctx

            with patch(
                "app.services.monthly_reset.MonthlyResetService.reset_all_organizations",
                new_callable=AsyncMock,
            ) as mock_reset:
                mock_reset.return_value = {"orgs_processed": 1, "errors": 0}
                result = await _run_monthly_reset(date(2026, 1, 15))

            call_args = mock_reset.call_args[0]
            assert call_args[0] == date(2026, 1, 1)  # Normalized to 1st


# --- Tests: History preservation ---


class TestHistoryPreservation:
    """Verify that old data is not deleted during reset."""

    @pytest.mark.asyncio
    async def test_old_pvr_records_untouched(self):
        """Creating new PVR records does not delete or modify old ones."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        barber = make_barber(barber_id=BARBER_ID_1)

        barbers_result = MagicMock()
        barbers_result.scalars.return_value.all.return_value = [barber]

        # No existing record for new month
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(
            side_effect=[barbers_result, existing_result]
        )

        added_items: list = []
        mock_db.add = MagicMock(side_effect=lambda item: added_items.append(item))

        await service._create_new_pvr_records(ORG_ID, FEBRUARY)

        # Verify: only db.add() was called, never delete/update
        assert mock_db.add.call_count == 1
        # No DELETE statements executed (execute was called for SELECT only)
        # db.execute calls: 1 for barbers query + 1 for existing check = 2
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_old_plans_untouched(self):
        """Copying plans does not modify old month plans."""
        mock_db = AsyncMock()
        service = MonthlyResetService(db=mock_db)

        old_plan = make_plan(month=JANUARY, target_amount=240_000_000)

        plans_result = MagicMock()
        plans_result.scalars.return_value.all.return_value = [old_plan]

        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(side_effect=[plans_result, existing_result])

        added_items: list = []
        mock_db.add = MagicMock(side_effect=lambda item: added_items.append(item))

        await service._copy_plans(ORG_ID, JANUARY, FEBRUARY)

        # Old plan is not mutated
        assert old_plan.current_amount == 200_000_000  # Unchanged
        assert old_plan.month == JANUARY  # Unchanged
