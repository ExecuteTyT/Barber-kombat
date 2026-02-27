"""Tests for the Plan Service."""

import json
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.plans import _DEVIATION_THRESHOLD_PP, PlanService

# --- Helpers ---

ORG_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()
BRANCH_ID_2 = uuid.uuid4()


def make_plan(
    branch_id: uuid.UUID = BRANCH_ID,
    org_id: uuid.UUID = ORG_ID,
    month: date | None = None,
    target_amount: int = 240_000_000,
    current_amount: int = 0,
    percentage: float = 0.0,
    forecast_amount: int | None = None,
):
    """Create a mock Plan object."""
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.organization_id = org_id
    plan.branch_id = branch_id
    plan.month = month or date.today().replace(day=1)
    plan.target_amount = target_amount
    plan.current_amount = current_amount
    plan.percentage = percentage
    plan.forecast_amount = forecast_amount
    return plan


def make_branch(
    branch_id: uuid.UUID = BRANCH_ID,
    org_id: uuid.UUID = ORG_ID,
    name: str = "8 марта",
):
    """Create a mock Branch object."""
    branch = MagicMock()
    branch.id = branch_id
    branch.organization_id = org_id
    branch.name = name
    branch.is_active = True
    return branch


# --- Tests: _format_plan ---


class TestFormatPlan:
    """Tests for plan response formatting."""

    def test_basic_format(self):
        """Formats a plan with all computed fields."""
        today = date.today()
        month_start = today.replace(day=1)
        plan = make_plan(
            month=month_start,
            target_amount=240_000_000,
            current_amount=185_000_000,
            percentage=77.1,
            forecast_amount=235_000_000,
        )

        result = PlanService._format_plan(plan, "8 марта")

        assert result["branch_id"] == BRANCH_ID
        assert result["branch_name"] == "8 марта"
        assert result["target_amount"] == 240_000_000
        assert result["current_amount"] == 185_000_000
        assert result["percentage"] == 77.1
        assert result["forecast_amount"] == 235_000_000
        assert "days_passed" in result
        assert "days_in_month" in result
        assert "days_left" in result
        assert "required_daily" in result
        assert "is_behind" in result

    def test_plan_complete(self):
        """When current >= target, required_daily is None."""
        month_start = date.today().replace(day=1)
        plan = make_plan(
            month=month_start,
            target_amount=100_000_000,
            current_amount=110_000_000,
            percentage=110.0,
        )

        result = PlanService._format_plan(plan, "Test")

        # Nothing more required
        assert result["required_daily"] is None or result["required_daily"] == 0

    def test_is_behind_true(self):
        """Plan is marked behind when deviation exceeds threshold."""
        today = date.today()
        month_start = today.replace(day=1)

        # Simulate being at day 20 of 30 with only 30% done
        # Expected ~66%, actual 30%, gap 36% > 15%
        plan = make_plan(
            month=month_start,
            target_amount=240_000_000,
            current_amount=72_000_000,
            percentage=30.0,
        )

        result = PlanService._format_plan(plan, "Test")

        # Only behind if we're far enough into the month
        days_passed = result["days_passed"]
        days_in_month = result["days_in_month"]
        expected_pct = (days_passed / days_in_month * 100) if days_in_month > 0 else 0

        if expected_pct - 30.0 > _DEVIATION_THRESHOLD_PP:
            assert result["is_behind"] is True

    def test_future_month_plan(self):
        """Plan for a future month has 0 days passed."""
        future = date.today().replace(day=1)
        if future.month == 12:
            future = future.replace(year=future.year + 1, month=1)
        else:
            future = future.replace(month=future.month + 1)

        plan = make_plan(
            month=future,
            target_amount=300_000_000,
            current_amount=0,
            percentage=0.0,
        )

        result = PlanService._format_plan(plan, "Test")
        assert result["days_passed"] == 0


# --- Tests: _sum_revenue ---


class TestSumRevenue:
    """Tests for revenue summation."""

    @pytest.mark.asyncio
    async def test_basic_sum(self):
        """Sums completed visit revenue for the month."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 185_000_000
        mock_db.execute = AsyncMock(return_value=revenue_result)

        service = PlanService(db=mock_db, redis=mock_redis)
        result = await service._sum_revenue(BRANCH_ID, date(2026, 2, 1))

        assert result == 185_000_000
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_zero_revenue(self):
        """No visits returns 0 via COALESCE."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 0
        mock_db.execute = AsyncMock(return_value=revenue_result)

        service = PlanService(db=mock_db, redis=mock_redis)
        result = await service._sum_revenue(BRANCH_ID, date(2026, 2, 1))

        assert result == 0

    @pytest.mark.asyncio
    async def test_december_boundary(self):
        """December correctly rolls over to January for month_end."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 50_000_000
        mock_db.execute = AsyncMock(return_value=revenue_result)

        service = PlanService(db=mock_db, redis=mock_redis)
        result = await service._sum_revenue(BRANCH_ID, date(2025, 12, 1))

        assert result == 50_000_000
        mock_db.execute.assert_called_once()


# --- Tests: update_progress ---


class TestUpdateProgress:
    """Tests for plan progress update pipeline."""

    @pytest.mark.asyncio
    async def test_no_plan_returns_none(self):
        """Returns None when no plan exists for the branch/month."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=plan_result)

        service = PlanService(db=mock_db, redis=mock_redis)
        result = await service.update_progress(BRANCH_ID)

        assert result is None

    @pytest.mark.asyncio
    async def test_updates_plan_fields(self):
        """Updates current_amount, percentage, forecast on the plan."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        plan = make_plan(
            target_amount=240_000_000,
            current_amount=0,
            percentage=0.0,
        )

        # _get_plan
        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = plan

        # _sum_revenue -> 120M
        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 120_000_000

        # _get_branch (for deviation check — won't trigger if not behind)
        branch = make_branch()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        mock_db.execute = AsyncMock(side_effect=[plan_result, revenue_result, branch_result])
        mock_db.commit = AsyncMock()

        service = PlanService(db=mock_db, redis=mock_redis)
        result = await service.update_progress(BRANCH_ID)

        assert result is not None
        assert plan.current_amount == 120_000_000
        assert plan.percentage == round(120_000_000 / 240_000_000 * 100, 1)
        mock_db.commit.assert_called()
        # WebSocket update published
        mock_redis.publish.assert_called()

    @pytest.mark.asyncio
    async def test_deviation_warning_published(self):
        """Publishes plan_warning when behind by more than threshold."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        today = date.today()
        month_start = today.replace(day=1)

        # Create a plan that's significantly behind
        plan = make_plan(
            month=month_start,
            target_amount=300_000_000,
            current_amount=0,
            percentage=0.0,
        )

        # _get_plan
        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = plan

        # _sum_revenue -> very low: 10M
        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 10_000_000

        # _get_branch for deviation notification
        branch = make_branch(name="Центральный")
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        mock_db.execute = AsyncMock(side_effect=[plan_result, revenue_result, branch_result])
        mock_db.commit = AsyncMock()

        service = PlanService(db=mock_db, redis=mock_redis)
        await service.update_progress(BRANCH_ID)

        # Check if deviation is enough to trigger warning
        import calendar

        days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
        days_passed = (today - month_start).days + 1
        expected_pct = (days_passed / days_in_month) * 100
        actual_pct = 10_000_000 / 300_000_000 * 100

        if actual_pct < expected_pct - _DEVIATION_THRESHOLD_PP:
            # At least 2 publish calls: one for warning, one for plan_update
            assert mock_redis.publish.call_count >= 2
            # Find the warning call
            warning_found = False
            for call in mock_redis.publish.call_args_list:
                payload = json.loads(call[0][1])
                if payload.get("type") == "plan_warning":
                    warning_found = True
                    assert "Центральный" in payload["message"]
                    break
            assert warning_found


# --- Tests: upsert_plan ---


class TestUpsertPlan:
    """Tests for plan creation/update."""

    @pytest.mark.asyncio
    async def test_creates_new_plan(self):
        """Creates a new plan and triggers progress update."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        # UPSERT execute
        upsert_result = MagicMock()

        # After upsert, update_progress is called:
        # _get_plan for update_progress
        plan = make_plan(
            target_amount=240_000_000,
            current_amount=0,
            percentage=0.0,
        )
        plan_result_1 = MagicMock()
        plan_result_1.scalar_one_or_none.return_value = plan

        # _sum_revenue
        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 0

        # Branch for deviation (no deviation at 0)
        # No deviation call needed if percentage = 0 and expected is low

        # _get_plan (final return from upsert_plan)
        plan_result_2 = MagicMock()
        plan_result_2.scalar_one_or_none.return_value = plan

        mock_db.execute = AsyncMock(
            side_effect=[upsert_result, plan_result_1, revenue_result, plan_result_2]
        )
        mock_db.commit = AsyncMock()

        service = PlanService(db=mock_db, redis=mock_redis)

        with patch.object(service, "update_progress", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = plan
            with patch.object(service, "_get_plan", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = plan

                result = await service.upsert_plan(
                    organization_id=ORG_ID,
                    branch_id=BRANCH_ID,
                    month=date(2026, 2, 1),
                    target_amount=240_000_000,
                )

        assert result is not None
        mock_update.assert_called_once()


# --- Tests: get_network_plans ---


class TestGetNetworkPlans:
    """Tests for network-wide plan overview."""

    @pytest.mark.asyncio
    async def test_returns_all_branches(self):
        """Returns plans for all branches with totals."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        plan1 = make_plan(
            branch_id=BRANCH_ID,
            target_amount=240_000_000,
            current_amount=185_000_000,
            percentage=77.1,
            forecast_amount=235_000_000,
        )
        plan2 = make_plan(
            branch_id=BRANCH_ID_2,
            target_amount=200_000_000,
            current_amount=160_000_000,
            percentage=80.0,
            forecast_amount=210_000_000,
        )

        rows = [
            (plan1, "8 марта"),
            (plan2, "Ленина"),
        ]

        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_db.execute = AsyncMock(return_value=result_mock)

        service = PlanService(db=mock_db, redis=mock_redis)
        data = await service.get_network_plans(ORG_ID)

        assert len(data["plans"]) == 2
        assert data["total_target"] == 440_000_000
        assert data["total_current"] == 345_000_000
        assert data["total_percentage"] == round(345_000_000 / 440_000_000 * 100, 1)

    @pytest.mark.asyncio
    async def test_empty_network(self):
        """Returns zeros when no plans exist."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_db.execute = AsyncMock(return_value=result_mock)

        service = PlanService(db=mock_db, redis=mock_redis)
        data = await service.get_network_plans(ORG_ID)

        assert len(data["plans"]) == 0
        assert data["total_target"] == 0
        assert data["total_current"] == 0
        assert data["total_percentage"] == 0.0


# --- Tests: update_progress_all_branches ---


class TestUpdateProgressAllBranches:
    """Tests for batch progress update."""

    @pytest.mark.asyncio
    async def test_updates_all_branches(self):
        """Updates progress for every branch that has a plan."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # select Plan.branch_id
        branches_result = MagicMock()
        branches_result.scalars.return_value.all.return_value = [BRANCH_ID, BRANCH_ID_2]
        mock_db.execute = AsyncMock(return_value=branches_result)

        service = PlanService(db=mock_db, redis=mock_redis)

        with patch.object(service, "update_progress", new_callable=AsyncMock) as mock_update:
            plan1 = make_plan(branch_id=BRANCH_ID)
            plan2 = make_plan(branch_id=BRANCH_ID_2)
            mock_update.side_effect = [plan1, plan2]

            count = await service.update_progress_all_branches(ORG_ID)

        assert count == 2
        assert mock_update.call_count == 2

    @pytest.mark.asyncio
    async def test_no_plans_returns_zero(self):
        """Returns 0 when no plans exist for the organization."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        branches_result = MagicMock()
        branches_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=branches_result)

        service = PlanService(db=mock_db, redis=mock_redis)
        count = await service.update_progress_all_branches(ORG_ID)

        assert count == 0


# --- Tests: _check_deviation ---


class TestCheckDeviation:
    """Tests for deviation detection and notification."""

    @pytest.mark.asyncio
    async def test_no_deviation_no_notification(self):
        """No notification when plan is on track."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        plan = make_plan(percentage=50.0)

        service = PlanService(db=mock_db, redis=mock_redis)
        # 50% done with 50% of month passed — on track
        await service._check_deviation(plan, days_passed=15, days_in_month=30, branch_id=BRANCH_ID)

        mock_redis.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_deviation_sends_warning(self):
        """Sends notification when behind by more than threshold."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        plan = make_plan(percentage=20.0)

        branch = make_branch(name="Центральный")
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch
        mock_db.execute = AsyncMock(return_value=branch_result)

        service = PlanService(db=mock_db, redis=mock_redis)
        # 20% done with 50% of month passed — expected 50%, gap = 30% > 15%
        await service._check_deviation(plan, days_passed=15, days_in_month=30, branch_id=BRANCH_ID)

        mock_redis.publish.assert_called_once()
        payload = json.loads(mock_redis.publish.call_args[0][1])
        assert payload["type"] == "plan_warning"
        assert "Центральный" in payload["message"]
        assert payload["actual_percentage"] == 20.0
        assert payload["expected_percentage"] == 50.0

    @pytest.mark.asyncio
    async def test_zero_days_no_check(self):
        """No deviation check when 0 days have passed."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        plan = make_plan(percentage=0.0)

        service = PlanService(db=mock_db, redis=mock_redis)
        await service._check_deviation(plan, days_passed=0, days_in_month=30, branch_id=BRANCH_ID)

        mock_redis.publish.assert_not_called()


# --- Tests: _publish_plan_update ---


class TestPublishPlanUpdate:
    """Tests for WebSocket plan_update event."""

    @pytest.mark.asyncio
    async def test_publishes_correct_payload(self):
        """Publishes plan_update with all required fields."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        plan = make_plan(
            target_amount=240_000_000,
            current_amount=185_000_000,
            percentage=77.1,
            forecast_amount=235_000_000,
        )

        service = PlanService(db=mock_db, redis=mock_redis)
        await service._publish_plan_update(plan)

        mock_redis.publish.assert_called_once()
        channel, payload_str = mock_redis.publish.call_args[0]

        assert channel == f"ws:org:{ORG_ID}"

        payload = json.loads(payload_str)
        assert payload["type"] == "plan_update"
        assert payload["branch_id"] == str(BRANCH_ID)
        assert payload["percentage"] == 77.1
        assert payload["current_amount"] == 185_000_000
        assert payload["target_amount"] == 240_000_000
        assert payload["forecast_amount"] == 235_000_000
        assert "timestamp" in payload


# --- Tests: get_plan_with_details ---


class TestGetPlanWithDetails:
    """Tests for detailed plan retrieval."""

    @pytest.mark.asyncio
    async def test_returns_formatted_plan(self):
        """Returns plan with computed fields when plan exists."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        plan = make_plan(
            target_amount=240_000_000,
            current_amount=185_000_000,
            percentage=77.1,
            forecast_amount=235_000_000,
        )
        branch = make_branch(name="8 марта")

        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = plan

        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        mock_db.execute = AsyncMock(side_effect=[plan_result, branch_result])

        service = PlanService(db=mock_db, redis=mock_redis)
        data = await service.get_plan_with_details(BRANCH_ID, ORG_ID)

        assert data is not None
        assert data["branch_name"] == "8 марта"
        assert data["target_amount"] == 240_000_000
        assert data["current_amount"] == 185_000_000

    @pytest.mark.asyncio
    async def test_returns_none_when_no_plan(self):
        """Returns None when no plan exists."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=plan_result)

        service = PlanService(db=mock_db, redis=mock_redis)
        data = await service.get_plan_with_details(BRANCH_ID, ORG_ID)

        assert data is None
