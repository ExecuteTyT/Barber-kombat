"""Tests for the rating-based PVR service."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.pvr import _DEFAULT_THRESHOLDS, PVRService
from app.services.rating import _BarberMonthlyScore


ORG_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()
BARBER_ID_1 = uuid.uuid4()


def make_pvr_config(
    thresholds: list[dict] | None = None,
    count_products: bool = False,
    count_certificates: bool = False,
    min_visits_per_month: int = 0,
):
    config = MagicMock()
    config.organization_id = ORG_ID
    config.thresholds = thresholds
    config.count_products = count_products
    config.count_certificates = count_certificates
    config.min_visits_per_month = min_visits_per_month
    return config


def make_barber(name: str = "Pavel", barber_id: uuid.UUID | None = None):
    b = MagicMock()
    b.id = barber_id or uuid.uuid4()
    b.name = name
    b.organization_id = ORG_ID
    b.branch_id = BRANCH_ID
    b.is_active = True
    return b


def make_monthly(
    barber_id: uuid.UUID,
    total_score: float = 0.0,
    working_days: int = 0,
    revenue: int = 0,
    components: tuple[float, float, float, float, float] = (0, 0, 0, 0, 0),
) -> _BarberMonthlyScore:
    rev, cs, prod, ext, rev_score = components
    return _BarberMonthlyScore(
        barber_id=barber_id,
        barber_name="X",
        total_score=total_score,
        revenue_score=rev,
        cs_score=cs,
        products_score=prod,
        extras_score=ext,
        reviews_score=rev_score,
        revenue=revenue,
        working_days=working_days,
    )


# --- _find_threshold (score-based) ---


class TestFindThreshold:
    def test_zero_score_no_threshold(self):
        threshold, bonus = PVRService._find_threshold(0, _DEFAULT_THRESHOLDS)
        assert threshold is None
        assert bonus == 0

    def test_below_first_threshold(self):
        threshold, bonus = PVRService._find_threshold(55, _DEFAULT_THRESHOLDS)
        assert threshold is None
        assert bonus == 0

    def test_exact_first_threshold(self):
        threshold, bonus = PVRService._find_threshold(60, _DEFAULT_THRESHOLDS)
        assert threshold == 60
        assert bonus == 100_000_000

    def test_between_thresholds(self):
        threshold, bonus = PVRService._find_threshold(70, _DEFAULT_THRESHOLDS)
        assert threshold == 60

    def test_highest_threshold(self):
        threshold, bonus = PVRService._find_threshold(92, _DEFAULT_THRESHOLDS)
        assert threshold == 90
        assert bonus == 500_000_000

    def test_empty_list(self):
        threshold, bonus = PVRService._find_threshold(80, [])
        assert threshold is None
        assert bonus == 0

    def test_custom_thresholds(self):
        custom = [{"score": 50, "bonus": 100_000}, {"score": 70, "bonus": 500_000}]
        threshold, bonus = PVRService._find_threshold(65, custom)
        assert threshold == 50
        assert bonus == 100_000


# --- _get_thresholds normalization ---


class TestGetThresholds:
    def _svc(self):
        return PVRService(db=AsyncMock(), redis=AsyncMock())

    def test_none_config_returns_defaults(self):
        out = self._svc()._get_thresholds(None)
        assert out == sorted(_DEFAULT_THRESHOLDS, key=lambda t: t["score"], reverse=True)

    def test_legacy_amount_rows_filtered_out(self):
        config = make_pvr_config(thresholds=[{"amount": 30_000_000, "bonus": 100}])
        out = self._svc()._get_thresholds(config)
        assert out == sorted(_DEFAULT_THRESHOLDS, key=lambda t: t["score"], reverse=True)

    def test_valid_score_rows_kept(self):
        config = make_pvr_config(
            thresholds=[{"score": 50, "bonus": 1}, {"score": 80, "bonus": 2}]
        )
        out = self._svc()._get_thresholds(config)
        assert out == [{"score": 80, "bonus": 2}, {"score": 50, "bonus": 1}]


# --- min_visits_per_month guard ---


class TestMinVisitsGuard:
    @pytest.mark.asyncio
    async def test_score_zeroed_when_below_minimum(self):
        """Barber with great metrics but too few working days → score=0, no bonus."""
        svc = PVRService(db=AsyncMock(), redis=AsyncMock())
        barber = make_barber()
        monthly = make_monthly(
            barber.id, total_score=85.0, working_days=3, revenue=500_000
        )
        thresholds = [{"score": 60, "bonus": 100}, {"score": 80, "bonus": 500}]

        out = svc._format_live(
            barber=barber,
            monthly=monthly,
            thresholds=thresholds,
            min_visits=20,
            cumulative_revenue=500_000,
        )
        assert out["monthly_rating_score"] == 0
        assert out["current_threshold"] is None
        assert out["bonus_amount"] == 0

    @pytest.mark.asyncio
    async def test_score_kept_when_at_or_above_minimum(self):
        svc = PVRService(db=AsyncMock(), redis=AsyncMock())
        barber = make_barber()
        monthly = make_monthly(
            barber.id, total_score=85.0, working_days=20, revenue=500_000
        )
        thresholds = [{"score": 60, "bonus": 100}, {"score": 80, "bonus": 500}]

        out = svc._format_live(
            barber=barber,
            monthly=monthly,
            thresholds=thresholds,
            min_visits=20,
            cumulative_revenue=500_000,
        )
        assert out["monthly_rating_score"] == 85
        assert out["current_threshold"] == 80
        assert out["bonus_amount"] == 500


# --- Formatters ---


class TestFormatters:
    def test_next_threshold_returns_smallest_above(self):
        t = [{"score": 60, "bonus": 1}, {"score": 80, "bonus": 2}, {"score": 90, "bonus": 3}]
        assert PVRService._next_threshold_score(70, t) == 80
        assert PVRService._next_threshold_score(80, t) == 90
        assert PVRService._next_threshold_score(95, t) is None

    def test_format_live_surfaces_breakdown(self):
        svc = PVRService(db=AsyncMock(), redis=AsyncMock())
        barber = make_barber()
        monthly = make_monthly(
            barber.id,
            total_score=72.0,
            working_days=22,
            revenue=350_000_00,
            components=(50.0, 80.0, 90.0, 60.0, 80.0),
        )
        thresholds = [{"score": 60, "bonus": 100}, {"score": 80, "bonus": 500}]
        out = svc._format_live(
            barber=barber,
            monthly=monthly,
            thresholds=thresholds,
            min_visits=0,
            cumulative_revenue=350_000_00,
        )
        assert out["monthly_rating_score"] == 72
        assert out["metric_breakdown"] == {
            "revenue_score": 50,
            "cs_score": 80,
            "products_score": 90,
            "extras_score": 60,
            "reviews_score": 80,
        }
        assert out["next_threshold"] == 80
        assert out["remaining_to_next"] == 8
        assert out["cumulative_revenue"] == 350_000_00

    def test_empty_breakdown_when_no_monthly(self):
        svc = PVRService(db=AsyncMock(), redis=AsyncMock())
        barber = make_barber()
        out = svc._format_live(
            barber=barber,
            monthly=None,
            thresholds=[],
            min_visits=0,
            cumulative_revenue=0,
        )
        assert out["monthly_rating_score"] == 0
        assert out["metric_breakdown"] == {
            "revenue_score": 0,
            "cs_score": 0,
            "products_score": 0,
            "extras_score": 0,
            "reviews_score": 0,
        }
