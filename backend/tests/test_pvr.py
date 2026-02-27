"""Tests for the PVR (Premium for High Results) service."""

import json
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.pvr import _DEFAULT_THRESHOLDS, PVRService

# --- Helpers ---


ORG_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()
BARBER_ID_1 = uuid.uuid4()
BARBER_ID_2 = uuid.uuid4()


def make_visit(
    barber_id: uuid.UUID,
    services_revenue: int = 100_000,
    products_revenue: int = 0,
    payment_type: str = "card",
    status: str = "completed",
    visit_date: date | None = None,
):
    """Create a mock Visit object."""
    visit = MagicMock()
    visit.barber_id = barber_id
    visit.services_revenue = services_revenue
    visit.products_revenue = products_revenue
    visit.payment_type = payment_type
    visit.status = status
    visit.date = visit_date or date.today()
    return visit


def make_pvr_config(
    org_id: uuid.UUID = ORG_ID,
    thresholds: list[dict] | None = None,
    count_products: bool = False,
    count_certificates: bool = False,
):
    """Create a mock PVRConfig object."""
    config = MagicMock()
    config.organization_id = org_id
    config.thresholds = thresholds
    config.count_products = count_products
    config.count_certificates = count_certificates
    return config


def make_pvr_record(
    barber_id: uuid.UUID = BARBER_ID_1,
    month: date | None = None,
    cumulative_revenue: int = 0,
    current_threshold: int | None = None,
    bonus_amount: int = 0,
    thresholds_reached: list | None = None,
):
    """Create a mock PVRRecord object."""
    record = MagicMock()
    record.barber_id = barber_id
    record.month = month or date.today().replace(day=1)
    record.cumulative_revenue = cumulative_revenue
    record.current_threshold = current_threshold
    record.bonus_amount = bonus_amount
    record.thresholds_reached = thresholds_reached
    return record


def make_barber(
    barber_id: uuid.UUID | None = None,
    name: str = "Pavel",
    org_id: uuid.UUID = ORG_ID,
    branch_id: uuid.UUID = BRANCH_ID,
):
    """Create a mock User (barber) object."""
    barber = MagicMock()
    barber.id = barber_id or uuid.uuid4()
    barber.name = name
    barber.organization_id = org_id
    barber.branch_id = branch_id
    barber.is_active = True
    barber.role = "barber"
    return barber


def make_branch(
    branch_id: uuid.UUID = BRANCH_ID,
    org_id: uuid.UUID = ORG_ID,
):
    """Create a mock Branch object."""
    branch = MagicMock()
    branch.id = branch_id
    branch.organization_id = org_id
    branch.name = "Test Branch"
    branch.is_active = True
    return branch


# --- Tests: _find_threshold ---


class TestFindThreshold:
    """Tests for threshold determination logic."""

    def test_no_threshold_when_below_minimum(self):
        """Revenue below all thresholds returns None, 0."""
        threshold, bonus = PVRService._find_threshold(25_000_000, _DEFAULT_THRESHOLDS)
        assert threshold is None
        assert bonus == 0

    def test_exact_minimum_threshold(self):
        """Revenue exactly at 300k threshold."""
        threshold, bonus = PVRService._find_threshold(30_000_000, _DEFAULT_THRESHOLDS)
        assert threshold == 30_000_000
        assert bonus == 1_000_000

    def test_between_thresholds(self):
        """Revenue between 300k and 350k returns the 300k threshold."""
        threshold, bonus = PVRService._find_threshold(32_000_000, _DEFAULT_THRESHOLDS)
        assert threshold == 30_000_000
        assert bonus == 1_000_000

    def test_exact_second_threshold(self):
        """Revenue exactly at 350k threshold."""
        threshold, bonus = PVRService._find_threshold(35_000_000, _DEFAULT_THRESHOLDS)
        assert threshold == 35_000_000
        assert bonus == 1_500_000

    def test_highest_threshold(self):
        """Revenue at 800k returns max threshold."""
        threshold, bonus = PVRService._find_threshold(80_000_000, _DEFAULT_THRESHOLDS)
        assert threshold == 80_000_000
        assert bonus == 5_000_000

    def test_above_highest_threshold(self):
        """Revenue exceeding 800k still returns max threshold."""
        threshold, bonus = PVRService._find_threshold(120_000_000, _DEFAULT_THRESHOLDS)
        assert threshold == 80_000_000
        assert bonus == 5_000_000

    def test_zero_revenue(self):
        """Zero revenue returns no threshold."""
        threshold, bonus = PVRService._find_threshold(0, _DEFAULT_THRESHOLDS)
        assert threshold is None
        assert bonus == 0

    def test_custom_thresholds(self):
        """Custom thresholds work correctly."""
        custom = [
            {"amount": 10_000_000, "bonus": 500_000},
            {"amount": 20_000_000, "bonus": 1_000_000},
        ]
        threshold, bonus = PVRService._find_threshold(15_000_000, custom)
        assert threshold == 10_000_000
        assert bonus == 500_000

    def test_empty_thresholds(self):
        """Empty thresholds list returns no threshold."""
        threshold, bonus = PVRService._find_threshold(50_000_000, [])
        assert threshold is None
        assert bonus == 0


# --- Tests: _calc_clean_revenue ---


class TestCalcCleanRevenue:
    """Tests for clean revenue calculation."""

    @pytest.mark.asyncio
    async def test_basic_services_only(self):
        """Default config: only services_revenue, card/cash/qr payments."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Return sum of services_revenue
        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 45_000_000
        mock_db.execute = AsyncMock(return_value=revenue_result)

        service = PVRService(db=mock_db, redis=mock_redis)
        config = None  # Default config

        result = await service._calc_clean_revenue(BARBER_ID_1, date(2026, 2, 1), config)
        assert result == 45_000_000

        # Verify the SQL was executed
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_with_products_enabled(self):
        """When count_products is True, includes products_revenue."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 55_000_000
        mock_db.execute = AsyncMock(return_value=revenue_result)

        service = PVRService(db=mock_db, redis=mock_redis)
        config = make_pvr_config(count_products=True)

        result = await service._calc_clean_revenue(BARBER_ID_1, date(2026, 2, 1), config)
        assert result == 55_000_000

    @pytest.mark.asyncio
    async def test_with_certificates_enabled(self):
        """When count_certificates is True, includes certificate payments."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 48_000_000
        mock_db.execute = AsyncMock(return_value=revenue_result)

        service = PVRService(db=mock_db, redis=mock_redis)
        config = make_pvr_config(count_certificates=True)

        result = await service._calc_clean_revenue(BARBER_ID_1, date(2026, 2, 1), config)
        assert result == 48_000_000

    @pytest.mark.asyncio
    async def test_zero_revenue(self):
        """No completed visits returns 0 (via COALESCE)."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 0
        mock_db.execute = AsyncMock(return_value=revenue_result)

        service = PVRService(db=mock_db, redis=mock_redis)
        result = await service._calc_clean_revenue(BARBER_ID_1, date(2026, 2, 1), None)
        assert result == 0

    @pytest.mark.asyncio
    async def test_december_month_boundary(self):
        """December correctly rolls over to January for month_end."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 30_000_000
        mock_db.execute = AsyncMock(return_value=revenue_result)

        service = PVRService(db=mock_db, redis=mock_redis)
        result = await service._calc_clean_revenue(BARBER_ID_1, date(2025, 12, 1), None)
        assert result == 30_000_000
        mock_db.execute.assert_called_once()


# --- Tests: recalculate_barber ---


class TestRecalculateBarber:
    """Tests for full PVR recalculation pipeline."""

    @pytest.mark.asyncio
    async def test_new_record_no_threshold(self):
        """Barber with low revenue — no threshold crossed, no bell."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        service = PVRService(db=mock_db, redis=mock_redis)

        # _load_config -> None (use defaults)
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None

        # _calc_clean_revenue -> 20M (below 30M threshold)
        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 20_000_000

        # _get_record (prev) -> None (no previous record)
        prev_result = MagicMock()
        prev_result.scalar_one_or_none.return_value = None

        # UPSERT execute + commit
        upsert_result = MagicMock()

        # _get_record (after upsert) -> new record
        new_record = make_pvr_record(
            barber_id=BARBER_ID_1,
            cumulative_revenue=20_000_000,
            current_threshold=None,
            bonus_amount=0,
        )
        final_result = MagicMock()
        final_result.scalar_one_or_none.return_value = new_record

        mock_db.execute = AsyncMock(
            side_effect=[config_result, revenue_result, prev_result, upsert_result, final_result]
        )
        mock_db.commit = AsyncMock()

        result = await service.recalculate_barber(BARBER_ID_1, ORG_ID, date.today())

        assert result is not None
        assert result.cumulative_revenue == 20_000_000
        assert result.current_threshold is None
        assert result.bonus_amount == 0
        # No bell notification
        mock_redis.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_threshold_crossed_sends_bell(self):
        """Barber crosses a new threshold — bell notification published."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        service = PVRService(db=mock_db, redis=mock_redis)

        # _load_config -> None (use defaults)
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None

        # _calc_clean_revenue -> 35M (crosses 300k and 350k thresholds)
        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 35_000_000

        # _get_record -> previous record with 300k threshold
        prev_record = make_pvr_record(
            barber_id=BARBER_ID_1,
            cumulative_revenue=30_500_000,
            current_threshold=30_000_000,
            bonus_amount=1_000_000,
            thresholds_reached=[{"amount": 30_000_000, "reached_at": "2026-02-10"}],
        )
        prev_result = MagicMock()
        prev_result.scalar_one_or_none.return_value = prev_record

        # UPSERT
        upsert_result = MagicMock()

        # _get_barber for bell notification
        barber = make_barber(barber_id=BARBER_ID_1, name="Pavel")
        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = barber

        # _get_record (final)
        new_record = make_pvr_record(
            barber_id=BARBER_ID_1,
            cumulative_revenue=35_000_000,
            current_threshold=35_000_000,
            bonus_amount=1_500_000,
        )
        final_result = MagicMock()
        final_result.scalar_one_or_none.return_value = new_record

        mock_db.execute = AsyncMock(
            side_effect=[
                config_result,
                revenue_result,
                prev_result,
                upsert_result,
                barber_result,
                final_result,
            ]
        )
        mock_db.commit = AsyncMock()

        result = await service.recalculate_barber(BARBER_ID_1, ORG_ID, date.today())

        assert result.current_threshold == 35_000_000
        assert result.bonus_amount == 1_500_000

        # Bell notification was published
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        channel = call_args[0][0]
        payload = json.loads(call_args[0][1])
        assert channel == f"ws:org:{ORG_ID}"
        assert payload["type"] == "pvr_threshold"
        assert payload["barber_name"] == "Pavel"
        assert payload["threshold"] == 35_000_000
        assert payload["bonus"] == 1_500_000

    @pytest.mark.asyncio
    async def test_same_threshold_no_bell(self):
        """Revenue increases but stays at same threshold — no bell."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        service = PVRService(db=mock_db, redis=mock_redis)

        # _load_config
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None

        # Revenue went from 31M to 33M — still at 300k threshold
        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 33_000_000

        # Previous record at 300k threshold
        prev_record = make_pvr_record(
            barber_id=BARBER_ID_1,
            cumulative_revenue=31_000_000,
            current_threshold=30_000_000,
            bonus_amount=1_000_000,
            thresholds_reached=[{"amount": 30_000_000, "reached_at": "2026-02-08"}],
        )
        prev_result = MagicMock()
        prev_result.scalar_one_or_none.return_value = prev_record

        upsert_result = MagicMock()

        final_record = make_pvr_record(
            barber_id=BARBER_ID_1,
            cumulative_revenue=33_000_000,
            current_threshold=30_000_000,
            bonus_amount=1_000_000,
        )
        final_result = MagicMock()
        final_result.scalar_one_or_none.return_value = final_record

        mock_db.execute = AsyncMock(
            side_effect=[config_result, revenue_result, prev_result, upsert_result, final_result]
        )
        mock_db.commit = AsyncMock()

        result = await service.recalculate_barber(BARBER_ID_1, ORG_ID, date.today())

        assert result.current_threshold == 30_000_000
        assert result.bonus_amount == 1_000_000
        # No bell — same threshold
        mock_redis.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_thresholds_crossed_at_once(self):
        """Revenue jumps from 0 to 500k — crosses multiple thresholds, bell for highest."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        service = PVRService(db=mock_db, redis=mock_redis)

        # _load_config
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None

        # Revenue = 50M (crosses 300k, 350k, 400k, 500k thresholds)
        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 50_000_000

        # No previous record
        prev_result = MagicMock()
        prev_result.scalar_one_or_none.return_value = None

        upsert_result = MagicMock()

        barber = make_barber(barber_id=BARBER_ID_1, name="Pavel")
        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = barber

        final_record = make_pvr_record(
            barber_id=BARBER_ID_1,
            cumulative_revenue=50_000_000,
            current_threshold=50_000_000,
            bonus_amount=3_000_000,
        )
        final_result = MagicMock()
        final_result.scalar_one_or_none.return_value = final_record

        mock_db.execute = AsyncMock(
            side_effect=[
                config_result,
                revenue_result,
                prev_result,
                upsert_result,
                barber_result,
                final_result,
            ]
        )
        mock_db.commit = AsyncMock()

        result = await service.recalculate_barber(BARBER_ID_1, ORG_ID, date.today())

        assert result.current_threshold == 50_000_000
        assert result.bonus_amount == 3_000_000
        # Bell sent for the new highest threshold
        mock_redis.publish.assert_called_once()
        payload = json.loads(mock_redis.publish.call_args[0][1])
        assert payload["threshold"] == 50_000_000
        assert payload["bonus"] == 3_000_000


# --- Tests: recalculate_branch ---


class TestRecalculateBranch:
    """Tests for branch-level PVR recalculation."""

    @pytest.mark.asyncio
    async def test_recalculates_all_active_barbers(self):
        """Recalculates PVR for each active barber in the branch."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        service = PVRService(db=mock_db, redis=mock_redis)

        branch = make_branch()
        barber1 = make_barber(barber_id=BARBER_ID_1, name="Pavel")
        barber2 = make_barber(barber_id=BARBER_ID_2, name="Leo")

        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        barbers_result = MagicMock()
        barbers_result.scalars.return_value.all.return_value = [barber1, barber2]

        mock_db.execute = AsyncMock(side_effect=[branch_result, barbers_result])

        with patch.object(service, "recalculate_barber", new_callable=AsyncMock) as mock_recalc:
            record1 = make_pvr_record(barber_id=BARBER_ID_1)
            record2 = make_pvr_record(barber_id=BARBER_ID_2)
            mock_recalc.side_effect = [record1, record2]

            records = await service.recalculate_branch(BRANCH_ID, date.today())

        assert len(records) == 2
        assert mock_recalc.call_count == 2
        mock_recalc.assert_any_call(BARBER_ID_1, ORG_ID, date.today())
        mock_recalc.assert_any_call(BARBER_ID_2, ORG_ID, date.today())

    @pytest.mark.asyncio
    async def test_branch_not_found_returns_empty(self):
        """Returns empty list when branch doesn't exist."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        service = PVRService(db=mock_db, redis=mock_redis)

        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=branch_result)

        records = await service.recalculate_branch(uuid.uuid4(), date.today())
        assert records == []


# --- Tests: _format_barber_pvr ---


class TestFormatBarberPvr:
    """Tests for API response formatting."""

    def test_with_record_and_next_threshold(self):
        """Formats a barber with an active record below max threshold."""
        record = make_pvr_record(
            barber_id=BARBER_ID_1,
            cumulative_revenue=35_000_000,
            current_threshold=35_000_000,
            bonus_amount=1_500_000,
            thresholds_reached=[
                {"amount": 30_000_000, "reached_at": "2026-02-05"},
                {"amount": 35_000_000, "reached_at": "2026-02-10"},
            ],
        )
        barber = make_barber(barber_id=BARBER_ID_1, name="Pavel")

        result = PVRService._format_barber_pvr(record, barber, _DEFAULT_THRESHOLDS)

        assert result["barber_id"] == BARBER_ID_1
        assert result["name"] == "Pavel"
        assert result["cumulative_revenue"] == 35_000_000
        assert result["current_threshold"] == 35_000_000
        assert result["bonus_amount"] == 1_500_000
        assert result["next_threshold"] == 40_000_000
        assert result["remaining_to_next"] == 5_000_000
        assert len(result["thresholds_reached"]) == 2

    def test_at_max_threshold(self):
        """When at the highest threshold, next_threshold is None."""
        record = make_pvr_record(
            barber_id=BARBER_ID_1,
            cumulative_revenue=85_000_000,
            current_threshold=80_000_000,
            bonus_amount=5_000_000,
        )
        barber = make_barber(barber_id=BARBER_ID_1)

        result = PVRService._format_barber_pvr(record, barber, _DEFAULT_THRESHOLDS)

        assert result["next_threshold"] is None
        assert result["remaining_to_next"] is None

    def test_no_record_returns_zeros(self):
        """No record yet — all values are zero/None."""
        barber = make_barber(barber_id=BARBER_ID_1, name="Pavel")
        result = PVRService._format_barber_pvr(None, barber, _DEFAULT_THRESHOLDS)

        assert result["cumulative_revenue"] == 0
        assert result["current_threshold"] is None
        assert result["bonus_amount"] == 0
        assert result["next_threshold"] == 30_000_000
        assert result["remaining_to_next"] == 30_000_000
        assert result["thresholds_reached"] == []

    def test_below_first_threshold(self):
        """Barber with some revenue but below first threshold."""
        record = make_pvr_record(
            barber_id=BARBER_ID_1,
            cumulative_revenue=15_000_000,
            current_threshold=None,
            bonus_amount=0,
        )
        barber = make_barber(barber_id=BARBER_ID_1)

        result = PVRService._format_barber_pvr(record, barber, _DEFAULT_THRESHOLDS)

        assert result["current_threshold"] is None
        assert result["bonus_amount"] == 0
        assert result["next_threshold"] == 30_000_000
        assert result["remaining_to_next"] == 15_000_000


# --- Tests: get_thresholds ---


class TestGetThresholds:
    """Tests for threshold config retrieval."""

    @pytest.mark.asyncio
    async def test_returns_default_when_no_config(self):
        """Returns default thresholds sorted ascending when no DB config."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=config_result)

        service = PVRService(db=mock_db, redis=mock_redis)
        thresholds = await service.get_thresholds(ORG_ID)

        # Should be sorted ascending
        assert len(thresholds) == 6
        assert thresholds[0]["amount"] == 30_000_000
        assert thresholds[-1]["amount"] == 80_000_000

    @pytest.mark.asyncio
    async def test_returns_custom_config(self):
        """Returns custom thresholds from DB config sorted ascending."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        custom_thresholds = [
            {"amount": 20_000_000, "bonus": 500_000},
            {"amount": 50_000_000, "bonus": 2_000_000},
        ]
        config = make_pvr_config(thresholds=custom_thresholds)

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = config
        mock_db.execute = AsyncMock(return_value=config_result)

        service = PVRService(db=mock_db, redis=mock_redis)
        thresholds = await service.get_thresholds(ORG_ID)

        assert len(thresholds) == 2
        assert thresholds[0]["amount"] == 20_000_000
        assert thresholds[1]["amount"] == 50_000_000


# --- Tests: get_barber_pvr ---


class TestGetBarberPvr:
    """Tests for single barber PVR data retrieval."""

    @pytest.mark.asyncio
    async def test_barber_with_record(self):
        """Returns formatted PVR data when a record exists."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        record = make_pvr_record(
            barber_id=BARBER_ID_1,
            cumulative_revenue=40_000_000,
            current_threshold=40_000_000,
            bonus_amount=2_000_000,
            thresholds_reached=[
                {"amount": 30_000_000, "reached_at": "2026-02-05"},
                {"amount": 35_000_000, "reached_at": "2026-02-09"},
                {"amount": 40_000_000, "reached_at": "2026-02-14"},
            ],
        )
        barber = make_barber(barber_id=BARBER_ID_1, name="Pavel")

        # _get_record, _load_config, _get_barber
        record_result = MagicMock()
        record_result.scalar_one_or_none.return_value = record

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None

        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = barber

        mock_db.execute = AsyncMock(side_effect=[record_result, config_result, barber_result])

        service = PVRService(db=mock_db, redis=mock_redis)
        data = await service.get_barber_pvr(BARBER_ID_1, ORG_ID)

        assert data["barber_id"] == BARBER_ID_1
        assert data["name"] == "Pavel"
        assert data["cumulative_revenue"] == 40_000_000
        assert data["current_threshold"] == 40_000_000
        assert data["bonus_amount"] == 2_000_000
        assert data["next_threshold"] == 50_000_000
        assert data["remaining_to_next"] == 10_000_000
        assert len(data["thresholds_reached"]) == 3

    @pytest.mark.asyncio
    async def test_barber_no_record(self):
        """Returns zero values when no PVR record exists yet."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        barber = make_barber(barber_id=BARBER_ID_1, name="Leo")

        record_result = MagicMock()
        record_result.scalar_one_or_none.return_value = None

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None

        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = barber

        mock_db.execute = AsyncMock(side_effect=[record_result, config_result, barber_result])

        service = PVRService(db=mock_db, redis=mock_redis)
        data = await service.get_barber_pvr(BARBER_ID_1, ORG_ID)

        assert data["cumulative_revenue"] == 0
        assert data["current_threshold"] is None
        assert data["bonus_amount"] == 0


# --- Tests: Default thresholds ---


class TestDefaultThresholds:
    """Tests for default threshold configuration."""

    def test_six_tiers(self):
        assert len(_DEFAULT_THRESHOLDS) == 6

    def test_sorted_descending(self):
        amounts = [t["amount"] for t in _DEFAULT_THRESHOLDS]
        assert amounts == sorted(amounts, reverse=True)

    def test_bonus_increases_with_amount(self):
        """Higher thresholds have higher bonuses."""
        sorted_asc = sorted(_DEFAULT_THRESHOLDS, key=lambda t: t["amount"])
        bonuses = [t["bonus"] for t in sorted_asc]
        assert bonuses == sorted(bonuses)

    def test_threshold_amounts_match_docs(self):
        """Verify thresholds match the documented values (in kopecks)."""
        expected = {
            30_000_000: 1_000_000,  # 300k -> 10k
            35_000_000: 1_500_000,  # 350k -> 15k
            40_000_000: 2_000_000,  # 400k -> 20k
            50_000_000: 3_000_000,  # 500k -> 30k
            60_000_000: 4_000_000,  # 600k -> 40k
            80_000_000: 5_000_000,  # 800k -> 50k
        }
        actual = {t["amount"]: t["bonus"] for t in _DEFAULT_THRESHOLDS}
        assert actual == expected


# --- Tests: bell notification content ---


class TestBellNotification:
    """Tests for bell notification publishing."""

    @pytest.mark.asyncio
    async def test_notification_payload_structure(self):
        """Bell notification contains all required fields."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        service = PVRService(db=mock_db, redis=mock_redis)

        await service._publish_bell(
            organization_id=ORG_ID,
            barber_id=BARBER_ID_1,
            barber_name="Pavel",
            revenue=50_000_000,
            threshold=50_000_000,
            bonus=3_000_000,
        )

        mock_redis.publish.assert_called_once()
        channel, payload_str = mock_redis.publish.call_args[0]

        assert channel == f"ws:org:{ORG_ID}"

        payload = json.loads(payload_str)
        assert payload["type"] == "pvr_threshold"
        assert payload["barber_id"] == str(BARBER_ID_1)
        assert payload["barber_name"] == "Pavel"
        assert payload["revenue"] == 50_000_000
        assert payload["threshold"] == 50_000_000
        assert payload["bonus"] == 3_000_000
        assert "timestamp" in payload
