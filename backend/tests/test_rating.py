"""Tests for the Rating Engine (Barber Kombat core)."""

import json
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.rating import (
    RatingEngine,
    _BarberRawData,
    _BarberScoredData,
    _DefaultConfig,
)

# --- Helpers ---


def make_visit(
    barber_id: uuid.UUID,
    revenue: int = 100_000,
    services_revenue: int = 80_000,
    extras_count: int = 0,
    products_count: int = 0,
    status: str = "completed",
):
    """Create a mock Visit object."""
    visit = MagicMock()
    visit.barber_id = barber_id
    visit.revenue = revenue
    visit.services_revenue = services_revenue
    visit.extras_count = extras_count
    visit.products_count = products_count
    visit.status = status
    return visit


def make_barber(
    name: str = "Barber",
    haircut_price: int | None = 160_000,
    branch_id: uuid.UUID | None = None,
    barber_id: uuid.UUID | None = None,
):
    """Create a mock User (barber) object."""
    barber = MagicMock()
    barber.id = barber_id or uuid.uuid4()
    barber.name = name
    barber.haircut_price = haircut_price
    barber.branch_id = branch_id or uuid.uuid4()
    barber.is_active = True
    barber.role = "barber"
    return barber


def make_branch(
    branch_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
):
    """Create a mock Branch object."""
    branch = MagicMock()
    branch.id = branch_id or uuid.uuid4()
    branch.organization_id = org_id or uuid.uuid4()
    branch.name = "Test Branch"
    return branch


def make_rating_config(
    org_id: uuid.UUID | None = None,
    revenue_weight: int = 20,
    cs_weight: int = 20,
    products_weight: int = 25,
    extras_weight: int = 25,
    reviews_weight: int = 10,
    prize_gold_pct: float = 0.5,
    prize_silver_pct: float = 0.3,
    prize_bronze_pct: float = 0.1,
):
    """Create a mock RatingConfig object."""
    config = MagicMock()
    config.organization_id = org_id or uuid.uuid4()
    config.revenue_weight = revenue_weight
    config.cs_weight = cs_weight
    config.products_weight = products_weight
    config.extras_weight = extras_weight
    config.reviews_weight = reviews_weight
    config.prize_gold_pct = prize_gold_pct
    config.prize_silver_pct = prize_silver_pct
    config.prize_bronze_pct = prize_bronze_pct
    return config


# --- Tests: _normalize ---


class TestNormalize:
    def test_basic(self):
        result = RatingEngine._normalize([13500, 12300, 6500])
        assert result[0] == 100.0
        assert abs(result[1] - 91.11) < 0.01
        assert abs(result[2] - 48.15) < 0.01

    def test_all_zeros(self):
        result = RatingEngine._normalize([0, 0, 0])
        assert result == [0.0, 0.0, 0.0]

    def test_single_value(self):
        result = RatingEngine._normalize([5000])
        assert result == [100.0]

    def test_single_zero(self):
        result = RatingEngine._normalize([0])
        assert result == [0.0]

    def test_with_one_zero(self):
        result = RatingEngine._normalize([10000, 0])
        assert result == [100.0, 0.0]

    def test_empty_list(self):
        result = RatingEngine._normalize([])
        assert result == []

    def test_all_equal(self):
        result = RatingEngine._normalize([500, 500, 500])
        assert result == [100.0, 100.0, 100.0]


# --- Tests: _compute_cs ---


class TestComputeCS:
    def test_basic(self):
        """Barber with haircut_price=160000, two visits."""
        barber_id = uuid.uuid4()
        visits = [
            make_visit(barber_id, services_revenue=250_000),
            make_visit(barber_id, services_revenue=160_000),
        ]
        cs = RatingEngine._compute_cs(visits, 160_000)
        # (250000/160000 + 160000/160000) / 2 = (1.5625 + 1.0) / 2 = 1.28125
        assert abs(cs - 1.28125) < 0.0001

    def test_no_haircut_price_none(self):
        visits = [make_visit(uuid.uuid4())]
        assert RatingEngine._compute_cs(visits, None) == 0.0

    def test_zero_haircut_price(self):
        visits = [make_visit(uuid.uuid4())]
        assert RatingEngine._compute_cs(visits, 0) == 0.0

    def test_no_visits(self):
        assert RatingEngine._compute_cs([], 160_000) == 0.0

    def test_single_visit(self):
        barber_id = uuid.uuid4()
        visits = [make_visit(barber_id, services_revenue=320_000)]
        cs = RatingEngine._compute_cs(visits, 160_000)
        # 320000 / 160000 = 2.0
        assert cs == 2.0


# --- Tests: _compute_weighted_score ---


class TestComputeWeightedScore:
    def test_default_weights(self):
        config = _DefaultConfig()
        score = RatingEngine._compute_weighted_score(
            revenue_score=100,
            cs_score=80,
            products_score=60,
            extras_score=40,
            reviews_score=0,
            config=config,
        )
        # (100*20 + 80*20 + 60*25 + 40*25 + 0*10) / 100
        # = (2000 + 1600 + 1500 + 1000 + 0) / 100 = 61.0
        assert score == 61.0

    def test_all_zeros(self):
        config = _DefaultConfig()
        score = RatingEngine._compute_weighted_score(0, 0, 0, 0, 0, config)
        assert score == 0.0

    def test_all_max(self):
        config = _DefaultConfig()
        score = RatingEngine._compute_weighted_score(100, 100, 100, 100, 100, config)
        assert score == 100.0

    def test_custom_weights_revenue_only(self):
        config = make_rating_config(
            revenue_weight=100,
            cs_weight=0,
            products_weight=0,
            extras_weight=0,
            reviews_weight=0,
        )
        score = RatingEngine._compute_weighted_score(75, 100, 100, 100, 100, config)
        assert score == 75.0


# --- Tests: _assign_ranks ---


class TestAssignRanks:
    def test_basic_ranking(self):
        entries = [
            _BarberScoredData(
                barber_id=uuid.uuid4(),
                barber_name="A",
                revenue=10000,
                cs_value=1.0,
                products_count=0,
                extras_count=0,
                reviews_avg=None,
                total_score=95,
            ),
            _BarberScoredData(
                barber_id=uuid.uuid4(),
                barber_name="B",
                revenue=8000,
                cs_value=1.0,
                products_count=0,
                extras_count=0,
                reviews_avg=None,
                total_score=87,
            ),
            _BarberScoredData(
                barber_id=uuid.uuid4(),
                barber_name="C",
                revenue=12000,
                cs_value=1.0,
                products_count=0,
                extras_count=0,
                reviews_avg=None,
                total_score=100,
            ),
        ]
        result = RatingEngine._assign_ranks(entries)
        assert result[0].rank == 1
        assert result[0].barber_name == "C"
        assert result[1].rank == 2
        assert result[1].barber_name == "A"
        assert result[2].rank == 3
        assert result[2].barber_name == "B"

    def test_tie_broken_by_revenue(self):
        entries = [
            _BarberScoredData(
                barber_id=uuid.uuid4(),
                barber_name="Low Revenue",
                revenue=5000,
                cs_value=1.0,
                products_count=0,
                extras_count=0,
                reviews_avg=None,
                total_score=80,
            ),
            _BarberScoredData(
                barber_id=uuid.uuid4(),
                barber_name="High Revenue",
                revenue=15000,
                cs_value=1.0,
                products_count=0,
                extras_count=0,
                reviews_avg=None,
                total_score=80,
            ),
        ]
        result = RatingEngine._assign_ranks(entries)
        assert result[0].barber_name == "High Revenue"
        assert result[0].rank == 1
        assert result[1].barber_name == "Low Revenue"
        assert result[1].rank == 2

    def test_single_entry(self):
        entries = [
            _BarberScoredData(
                barber_id=uuid.uuid4(),
                barber_name="Solo",
                revenue=10000,
                cs_value=1.0,
                products_count=0,
                extras_count=0,
                reviews_avg=None,
                total_score=50,
            ),
        ]
        result = RatingEngine._assign_ranks(entries)
        assert result[0].rank == 1


# --- Tests: _score_barbers ---


class TestScoreBarbers:
    def test_three_barbers(self):
        """Test full scoring pipeline with three barbers."""
        config = _DefaultConfig()
        engine = RatingEngine.__new__(RatingEngine)

        raw_data = [
            _BarberRawData(
                barber_id=uuid.uuid4(),
                barber_name="Pavel",
                haircut_price=160_000,
                revenue=1_350_000,
                visits_count=5,
                cs_value=1.45,
                products_count=2,
                extras_count=3,
                reviews_avg=4.5,
            ),
            _BarberRawData(
                barber_id=uuid.uuid4(),
                barber_name="Leo",
                haircut_price=160_000,
                revenue=1_230_000,
                visits_count=4,
                cs_value=1.52,
                products_count=1,
                extras_count=2,
                reviews_avg=4.8,
            ),
            _BarberRawData(
                barber_id=uuid.uuid4(),
                barber_name="Mark",
                haircut_price=160_000,
                revenue=650_000,
                visits_count=3,
                cs_value=1.61,
                products_count=3,
                extras_count=1,
                reviews_avg=None,
            ),
        ]

        scored = engine._score_barbers(raw_data, config)

        assert len(scored) == 3

        # Pavel has highest revenue -> revenue_score = 100
        pavel = scored[0]
        assert pavel.revenue_score == 100.0

        # Mark has highest CS -> cs_score = 100
        mark = scored[2]
        assert mark.cs_score == 100.0

        # Mark has most products -> products_score = 100
        assert mark.products_score == 100.0

        # Pavel has most extras -> extras_score = 100
        assert pavel.extras_score == 100.0

        # Leo has highest review -> reviews_score = 100
        leo = scored[1]
        assert leo.reviews_score == 100.0

        # Mark has no reviews -> reviews_score = 0
        assert mark.reviews_score == 0.0

    def test_all_zero_revenue(self):
        config = _DefaultConfig()
        engine = RatingEngine.__new__(RatingEngine)

        raw_data = [
            _BarberRawData(
                barber_id=uuid.uuid4(),
                barber_name="A",
                haircut_price=160_000,
                revenue=0,
                visits_count=0,
                cs_value=0.0,
                products_count=0,
                extras_count=0,
                reviews_avg=None,
            ),
            _BarberRawData(
                barber_id=uuid.uuid4(),
                barber_name="B",
                haircut_price=160_000,
                revenue=0,
                visits_count=0,
                cs_value=0.0,
                products_count=0,
                extras_count=0,
                reviews_avg=None,
            ),
        ]

        scored = engine._score_barbers(raw_data, config)

        for s in scored:
            assert s.revenue_score == 0.0
            assert s.total_score == 0.0


# --- Tests: recalculate (integration with mocks) ---


class TestRecalculate:
    """Integration tests for the full recalculate pipeline."""

    @pytest.fixture
    def branch_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def org_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def target_date(self):
        return date(2024, 10, 13)

    def _setup_engine(self, branch, barbers, visits, reviews_rows, config):
        """Create a RatingEngine with mocked DB and Redis."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Track call count to db.execute to return different results
        call_results = []

        # 1. Branch query
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch
        call_results.append(branch_result)

        # 2. RatingConfig query
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = config
        call_results.append(config_result)

        # 3. Active barbers query
        barbers_result = MagicMock()
        barbers_result.scalars.return_value.all.return_value = barbers
        call_results.append(barbers_result)

        # 4. Visits query
        visits_result = MagicMock()
        visits_result.scalars.return_value.all.return_value = visits
        call_results.append(visits_result)

        # 5. Reviews query
        reviews_result = MagicMock()
        reviews_result.__iter__ = lambda self: iter(reviews_rows)
        call_results.append(reviews_result)

        # 6+ UPSERT calls (one per barber)
        for _ in barbers:
            call_results.append(MagicMock())

        # get_prize_fund calls _load_rating_config again
        config_result2 = MagicMock()
        config_result2.scalar_one_or_none.return_value = config
        call_results.append(config_result2)

        # Prize fund query (SUM of revenue)
        prize_result = MagicMock()
        prize_result.scalar_one.return_value = 0
        call_results.append(prize_result)

        mock_db.execute = AsyncMock(side_effect=call_results)
        mock_db.commit = AsyncMock()

        engine = RatingEngine(db=mock_db, redis=mock_redis)
        return engine, mock_db, mock_redis

    @pytest.mark.asyncio
    async def test_three_barbers_full_pipeline(self, branch_id, org_id, target_date):
        branch = make_branch(branch_id, org_id)

        b1 = make_barber("Pavel", 160_000, branch_id)
        b2 = make_barber("Leo", 160_000, branch_id)
        b3 = make_barber("Mark", 160_000, branch_id)

        visits = [
            # Pavel: 2 visits, total revenue 1,350,000
            make_visit(
                b1.id, revenue=900_000, services_revenue=800_000, extras_count=2, products_count=1
            ),
            make_visit(
                b1.id, revenue=450_000, services_revenue=400_000, extras_count=1, products_count=0
            ),
            # Leo: 1 visit, total revenue 500_000
            make_visit(
                b2.id, revenue=500_000, services_revenue=450_000, extras_count=0, products_count=2
            ),
            # Mark: no visits
        ]

        engine, mock_db, mock_redis = self._setup_engine(
            branch=branch,
            barbers=[b1, b2, b3],
            visits=visits,
            reviews_rows=[],
            config=None,  # use defaults
        )

        result = await engine.recalculate(branch_id, target_date)

        assert len(result) == 3
        # Pavel has highest revenue -> rank 1
        assert result[0].barber_name == "Pavel"
        assert result[0].rank == 1
        assert result[0].revenue == 1_350_000

        # Leo rank 2
        assert result[1].barber_name == "Leo"
        assert result[1].rank == 2

        # Mark rank 3 (no visits)
        assert result[2].barber_name == "Mark"
        assert result[2].rank == 3
        assert result[2].revenue == 0

        # Verify DB commit was called
        mock_db.commit.assert_called()

        # Verify Redis cache was set
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_barbers_returns_empty(self, branch_id, org_id, target_date):
        branch = make_branch(branch_id, org_id)

        engine, _mock_db, mock_redis = self._setup_engine(
            branch=branch,
            barbers=[],
            visits=[],
            reviews_rows=[],
            config=None,
        )

        # Override: barbers query returns empty list
        # The setup already handles this — barbers=[] means 3rd call returns []

        result = await engine.recalculate(branch_id, target_date)

        assert result == []
        mock_redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_barber_gets_first(self, branch_id, org_id, target_date):
        branch = make_branch(branch_id, org_id)
        b1 = make_barber("Solo Barber", 160_000, branch_id)

        visits = [
            make_visit(
                b1.id, revenue=500_000, services_revenue=400_000, extras_count=1, products_count=1
            ),
        ]

        engine, _, _ = self._setup_engine(
            branch=branch,
            barbers=[b1],
            visits=visits,
            reviews_rows=[],
            config=None,
        )

        result = await engine.recalculate(branch_id, target_date)

        assert len(result) == 1
        assert result[0].rank == 1
        assert result[0].revenue_score == 100.0
        assert result[0].cs_score == 100.0
        assert result[0].products_score == 100.0
        assert result[0].extras_score == 100.0

    @pytest.mark.asyncio
    async def test_barber_no_visits_participates(self, branch_id, org_id, target_date):
        branch = make_branch(branch_id, org_id)
        b1 = make_barber("Active", 160_000, branch_id)
        b2 = make_barber("Idle", 160_000, branch_id)

        visits = [
            make_visit(b1.id, revenue=500_000, services_revenue=400_000),
        ]

        engine, _, _ = self._setup_engine(
            branch=branch,
            barbers=[b1, b2],
            visits=visits,
            reviews_rows=[],
            config=None,
        )

        result = await engine.recalculate(branch_id, target_date)

        assert len(result) == 2
        idle = next(r for r in result if r.barber_name == "Idle")
        assert idle.revenue == 0
        assert idle.total_score == 0.0
        assert idle.rank == 2

    @pytest.mark.asyncio
    async def test_cancelled_visits_excluded(self, branch_id, org_id, target_date):
        """Cancelled visits should not appear in the visits list.

        The query filters by status='completed', so cancelled visits
        are excluded at the DB level. In tests, we just don't include them.
        """
        branch = make_branch(branch_id, org_id)
        b1 = make_barber("Barber", 160_000, branch_id)

        # Only completed visits in the mock (cancelled ones are filtered by query)
        visits = [
            make_visit(b1.id, revenue=300_000, services_revenue=250_000),
        ]

        engine, _, _ = self._setup_engine(
            branch=branch,
            barbers=[b1],
            visits=visits,
            reviews_rows=[],
            config=None,
        )

        result = await engine.recalculate(branch_id, target_date)

        assert len(result) == 1
        assert result[0].revenue == 300_000

    @pytest.mark.asyncio
    async def test_with_reviews(self, branch_id, org_id, target_date):
        branch = make_branch(branch_id, org_id)
        b1 = make_barber("With Review", 160_000, branch_id)
        b2 = make_barber("Without Review", 160_000, branch_id)

        visits = [
            make_visit(b1.id, revenue=500_000, services_revenue=400_000),
            make_visit(b2.id, revenue=500_000, services_revenue=400_000),
        ]

        # Review result rows
        review_row = MagicMock()
        review_row.barber_id = b1.id
        review_row.avg_rating = 4.5

        engine, _, _ = self._setup_engine(
            branch=branch,
            barbers=[b1, b2],
            visits=visits,
            reviews_rows=[review_row],
            config=None,
        )

        result = await engine.recalculate(branch_id, target_date)

        assert len(result) == 2
        with_review = next(r for r in result if r.barber_name == "With Review")
        without_review = next(r for r in result if r.barber_name == "Without Review")

        assert with_review.reviews_avg == 4.5
        assert with_review.reviews_score == 100.0
        assert without_review.reviews_avg is None
        assert without_review.reviews_score == 0.0

    @pytest.mark.asyncio
    async def test_custom_weights_applied(self, branch_id, org_id, target_date):
        branch = make_branch(branch_id, org_id)
        b1 = make_barber("Revenue King", 160_000, branch_id)
        b2 = make_barber("CS King", 160_000, branch_id)

        visits = [
            # b1: high revenue, low CS
            make_visit(b1.id, revenue=1_000_000, services_revenue=160_000),
            # b2: low revenue, high CS
            make_visit(b2.id, revenue=200_000, services_revenue=480_000),
        ]

        # Custom weights: revenue 80%, CS 20%, rest 0%
        config = make_rating_config(
            org_id,
            revenue_weight=80,
            cs_weight=20,
            products_weight=0,
            extras_weight=0,
            reviews_weight=0,
        )

        engine, _, _ = self._setup_engine(
            branch=branch,
            barbers=[b1, b2],
            visits=visits,
            reviews_rows=[],
            config=config,
        )

        result = await engine.recalculate(branch_id, target_date)

        # With 80% revenue weight, Revenue King should win
        assert result[0].barber_name == "Revenue King"
        assert result[0].rank == 1

    @pytest.mark.asyncio
    async def test_caches_in_redis(self, branch_id, org_id, target_date):
        branch = make_branch(branch_id, org_id)
        b1 = make_barber("Barber", 160_000, branch_id)

        visits = [make_visit(b1.id, revenue=500_000, services_revenue=400_000)]

        engine, _, mock_redis = self._setup_engine(
            branch=branch,
            barbers=[b1],
            visits=visits,
            reviews_rows=[],
            config=None,
        )

        await engine.recalculate(branch_id, target_date)

        # Verify redis.set was called with correct key
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        assert key == f"rating:{branch_id}:{target_date}"

        # Verify the JSON payload
        payload = json.loads(call_args[0][1])
        assert payload["type"] == "rating_update"
        assert payload["branch_id"] == str(branch_id)
        assert len(payload["ratings"]) == 1
        assert "prize_fund" in payload

        # Verify TTL
        assert call_args[1]["ex"] == 86400

    @pytest.mark.asyncio
    async def test_no_rating_config_uses_defaults(self, branch_id, org_id, target_date):
        branch = make_branch(branch_id, org_id)
        b1 = make_barber("Barber", 160_000, branch_id)

        visits = [
            make_visit(
                b1.id,
                revenue=500_000,
                services_revenue=400_000,
                extras_count=1,
                products_count=2,
            ),
        ]

        engine, _, _ = self._setup_engine(
            branch=branch,
            barbers=[b1],
            visits=visits,
            reviews_rows=[],
            config=None,  # No config in DB -> defaults used
        )

        result = await engine.recalculate(branch_id, target_date)

        assert len(result) == 1
        # Single barber gets 100% on all non-zero metrics.
        # reviews_avg is None -> reviews_score=0, _normalize([0])=[0.0]
        # revenue=100, cs=100, products=100, extras=100, reviews=0
        # Default weights: 20+20+25+25+10=100
        # Score: 100*20/100 + 100*20/100 + 100*25/100 + 100*25/100 + 0*10/100 = 90
        assert result[0].total_score == 90.0
        assert result[0].revenue_score == 100.0
        assert result[0].cs_score == 100.0
        assert result[0].products_score == 100.0
        assert result[0].extras_score == 100.0
        assert result[0].reviews_score == 0.0

    @pytest.mark.asyncio
    async def test_branch_not_found_returns_empty(self, branch_id, target_date):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Branch query returns None
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=branch_result)

        engine = RatingEngine(db=mock_db, redis=mock_redis)
        result = await engine.recalculate(branch_id, target_date)

        assert result == []

    @pytest.mark.asyncio
    async def test_barber_no_haircut_price_cs_zero(self, branch_id, org_id, target_date):
        branch = make_branch(branch_id, org_id)
        b1 = make_barber("No Price", haircut_price=None, branch_id=branch_id)
        b2 = make_barber("Has Price", haircut_price=160_000, branch_id=branch_id)

        visits = [
            make_visit(b1.id, revenue=500_000, services_revenue=400_000),
            make_visit(b2.id, revenue=500_000, services_revenue=400_000),
        ]

        engine, _, _ = self._setup_engine(
            branch=branch,
            barbers=[b1, b2],
            visits=visits,
            reviews_rows=[],
            config=None,
        )

        result = await engine.recalculate(branch_id, target_date)

        no_price = next(r for r in result if r.barber_name == "No Price")
        has_price = next(r for r in result if r.barber_name == "Has Price")

        assert no_price.cs_value == 0.0
        assert no_price.cs_score == 0.0
        assert has_price.cs_value > 0
        assert has_price.cs_score == 100.0


# --- Tests: get_prize_fund ---


class TestGetPrizeFund:
    @pytest.mark.asyncio
    async def test_basic(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        org_id = uuid.uuid4()
        branch_id = uuid.uuid4()

        # Config query
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = make_rating_config(org_id)

        # Revenue query: 9,800,000 kopecks (98,000 rubles)
        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 9_800_000

        mock_db.execute = AsyncMock(side_effect=[config_result, revenue_result])

        engine = RatingEngine(db=mock_db, redis=mock_redis)
        fund = await engine.get_prize_fund(branch_id, org_id)

        # 9,800,000 * 0.5 / 100 = 49,000
        assert fund["gold"] == 49_000
        # 9,800,000 * 0.3 / 100 = 29,400
        assert fund["silver"] == 29_400
        # 9,800,000 * 0.1 / 100 = 9,800
        assert fund["bronze"] == 9_800

    @pytest.mark.asyncio
    async def test_no_revenue(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        org_id = uuid.uuid4()
        branch_id = uuid.uuid4()

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None  # defaults

        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 0

        mock_db.execute = AsyncMock(side_effect=[config_result, revenue_result])

        engine = RatingEngine(db=mock_db, redis=mock_redis)
        fund = await engine.get_prize_fund(branch_id, org_id)

        assert fund["gold"] == 0
        assert fund["silver"] == 0
        assert fund["bronze"] == 0

    @pytest.mark.asyncio
    async def test_custom_percentages(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        org_id = uuid.uuid4()
        branch_id = uuid.uuid4()

        config = make_rating_config(
            org_id,
            prize_gold_pct=1.0,
            prize_silver_pct=0.5,
            prize_bronze_pct=0.2,
        )
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = config

        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 10_000_000

        mock_db.execute = AsyncMock(side_effect=[config_result, revenue_result])

        engine = RatingEngine(db=mock_db, redis=mock_redis)
        fund = await engine.get_prize_fund(branch_id, org_id)

        # 10,000,000 * 1.0 / 100 = 100,000
        assert fund["gold"] == 100_000
        # 10,000,000 * 0.5 / 100 = 50,000
        assert fund["silver"] == 50_000
        # 10,000,000 * 0.2 / 100 = 20,000
        assert fund["bronze"] == 20_000


# --- Tests: get_cached_rating ---


class TestGetCachedRating:
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        branch_id = uuid.uuid4()
        target_date = date(2024, 10, 13)

        cached_data = {
            "type": "rating_update",
            "branch_id": str(branch_id),
            "ratings": [{"name": "Pavel", "rank": 1}],
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        engine = RatingEngine(db=mock_db, redis=mock_redis)
        result = await engine.get_cached_rating(branch_id, target_date)

        assert result is not None
        assert result["type"] == "rating_update"
        assert len(result["ratings"]) == 1

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        engine = RatingEngine(db=mock_db, redis=mock_redis)
        result = await engine.get_cached_rating(uuid.uuid4(), date(2024, 10, 13))

        assert result is None


# --- Tests: _DefaultConfig ---


class TestDefaultConfig:
    def test_weights_sum_to_100(self):
        config = _DefaultConfig()
        total = (
            config.revenue_weight
            + config.cs_weight
            + config.products_weight
            + config.extras_weight
            + config.reviews_weight
        )
        assert total == 100

    def test_prize_percentages(self):
        config = _DefaultConfig()
        assert config.prize_gold_pct == 0.5
        assert config.prize_silver_pct == 0.3
        assert config.prize_bronze_pct == 0.1


# --- Tests: doc example scenario ---


class TestDocExample:
    """Tests based on the example from barber-kombat.md documentation."""

    def test_cs_example_from_docs(self):
        """Doc example: haircut_price=1600 rubles (160000 kopecks).
        Visit 1: haircut(1600) + beard(900) = 2500 -> CS = 2500/1600 = 1.5625
        Visit 2: haircut only = 1600 -> CS = 1600/1600 = 1.0
        Average CS = (1.5625 + 1.0) / 2 = 1.28125
        """
        barber_id = uuid.uuid4()
        visits = [
            make_visit(barber_id, services_revenue=250_000),  # 2500 rub
            make_visit(barber_id, services_revenue=160_000),  # 1600 rub
        ]
        cs = RatingEngine._compute_cs(visits, 160_000)
        assert abs(cs - 1.28125) < 0.0001

    def test_normalization_example_from_docs(self):
        """Doc example: Pavel 13,500 -> 100%, Leo 12,300 -> 91.1%, Mark 6,500 -> 48.1%"""
        # Using kopecks: 1,350,000 / 1,230,000 / 650,000
        result = RatingEngine._normalize([1_350_000, 1_230_000, 650_000])
        assert result[0] == 100.0
        assert abs(result[1] - 91.11) < 0.01
        assert abs(result[2] - 48.15) < 0.01
