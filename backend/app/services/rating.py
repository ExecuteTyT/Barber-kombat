"""Rating Engine for Barber Kombat daily competitions."""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import redis.asyncio as aioredis
import structlog
from sqlalchemy import Date, cast, select
from sqlalchemy import func as sa_func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.daily_rating import DailyRating
from app.models.rating_config import RatingConfig
from app.models.review import Review
from app.models.user import User, UserRole
from app.models.visit import Visit

logger = structlog.stdlib.get_logger()

# Redis cache TTL: 24 hours
_CACHE_TTL = 86400


# --- Internal dataclasses ---


@dataclass
class _BarberRawData:
    """Raw collected data for a single barber on a given date."""

    barber_id: uuid.UUID
    barber_name: str
    haircut_price: int | None
    revenue: int = 0
    visits_count: int = 0
    cs_value: float = 0.0
    products_count: int = 0
    extras_count: int = 0
    reviews_avg: float | None = None


@dataclass
class _BarberScoredData:
    """Barber data after normalization and scoring."""

    barber_id: uuid.UUID
    barber_name: str
    revenue: int
    cs_value: float
    products_count: int
    extras_count: int
    reviews_avg: float | None
    revenue_score: float = 0.0
    cs_score: float = 0.0
    products_score: float = 0.0
    extras_score: float = 0.0
    reviews_score: float = 0.0
    total_score: float = 0.0
    rank: int = 0


# --- Default config (when no RatingConfig exists in DB) ---

_DEFAULT_WEIGHTS: dict[str, int] = {
    "revenue_weight": 20,
    "cs_weight": 20,
    "products_weight": 25,
    "extras_weight": 25,
    "reviews_weight": 10,
}

_DEFAULT_PRIZE_PCTS: dict[str, float] = {
    "prize_gold_pct": 0.5,
    "prize_silver_pct": 0.3,
    "prize_bronze_pct": 0.1,
}


class RatingEngine:
    """Calculates daily Barber Kombat ratings for a branch."""

    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self.db = db
        self.redis = redis

    # --- Public methods ---

    async def recalculate(
        self,
        branch_id: uuid.UUID,
        target_date: date,
    ) -> list[_BarberScoredData]:
        """Recalculate the full rating for a branch on a given date.

        Pipeline: collect raw data -> compute CS -> normalize ->
        weighted sum -> rank -> persist -> cache -> notify.

        Returns the list of scored barber entries (sorted by rank).
        """
        # 1. Load branch
        result = await self.db.execute(select(Branch).where(Branch.id == branch_id))
        branch = result.scalar_one_or_none()
        if branch is None:
            await logger.awarning("Branch not found", branch_id=str(branch_id))
            return []

        organization_id = branch.organization_id

        # 2. Load config
        config = await self._load_rating_config(organization_id)

        # 3. Get active barbers
        barbers = await self._get_active_barbers(branch_id)
        if not barbers:
            await logger.ainfo("No active barbers for branch", branch_id=str(branch_id))
            return []

        # 4. Collect raw data
        raw_data = await self._collect_raw_data(branch_id, target_date, barbers)

        # 5-8. Normalize and score
        scored = self._score_barbers(raw_data, config)

        # 9. Rank
        scored = self._assign_ranks(scored)

        # 10. Persist
        await self._persist_ratings(organization_id, branch_id, target_date, scored)

        # 11. Prize fund
        prize_fund = await self.get_prize_fund(branch_id, organization_id)

        # 12. Cache
        await self._cache_rating(branch_id, target_date, scored, prize_fund)

        # 13. Publish to WebSocket via Redis Pub/Sub
        ws_payload = {
            "type": "rating_update",
            "branch_id": str(branch_id),
            "date": str(target_date),
            "timestamp": datetime.now(UTC).isoformat(),
            "ratings": [
                {
                    "barber_id": str(e.barber_id),
                    "name": e.barber_name,
                    "rank": e.rank,
                    "total_score": round(e.total_score, 2),
                    "revenue": e.revenue,
                }
                for e in scored
            ],
            "prize_fund": prize_fund,
        }
        await self.redis.publish(
            f"ws:org:{organization_id}",
            json.dumps(ws_payload),
        )

        await logger.ainfo(
            "Rating recalculated",
            branch_id=str(branch_id),
            date=str(target_date),
            barbers=len(scored),
        )

        return scored

    async def get_prize_fund(
        self,
        branch_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> dict[str, int]:
        """Calculate the current prize fund based on monthly cumulative revenue.

        Returns {"gold": int, "silver": int, "bronze": int} in kopecks.
        """
        config = await self._load_rating_config(organization_id)

        today = date.today()
        month_start = today.replace(day=1)

        stmt = select(sa_func.coalesce(sa_func.sum(Visit.revenue), 0)).where(
            Visit.branch_id == branch_id,
            Visit.date >= month_start,
            Visit.status == "completed",
        )
        result = await self.db.execute(stmt)
        monthly_revenue: int = result.scalar_one()

        gold_pct = getattr(config, "prize_gold_pct", _DEFAULT_PRIZE_PCTS["prize_gold_pct"])
        silver_pct = getattr(config, "prize_silver_pct", _DEFAULT_PRIZE_PCTS["prize_silver_pct"])
        bronze_pct = getattr(config, "prize_bronze_pct", _DEFAULT_PRIZE_PCTS["prize_bronze_pct"])

        return {
            "gold": round(monthly_revenue * gold_pct / 100),
            "silver": round(monthly_revenue * silver_pct / 100),
            "bronze": round(monthly_revenue * bronze_pct / 100),
        }

    async def get_cached_rating(
        self,
        branch_id: uuid.UUID,
        target_date: date,
    ) -> dict | None:
        """Retrieve cached rating from Redis. Returns None on cache miss."""
        key = f"rating:{branch_id}:{target_date}"
        data = await self.redis.get(key)
        if data is None:
            return None
        return json.loads(data)

    # --- Private methods ---

    async def _load_rating_config(
        self, organization_id: uuid.UUID
    ) -> RatingConfig | Any:
        """Load RatingConfig for the organization.

        Falls back to a simple object with default weights if none exists.
        """
        result = await self.db.execute(
            select(RatingConfig).where(
                RatingConfig.organization_id == organization_id
            )
        )
        config = result.scalar_one_or_none()
        if config is not None:
            return config

        # Return a simple namespace with defaults
        return _DefaultConfig()

    async def _get_active_barbers(self, branch_id: uuid.UUID) -> list[User]:
        """Get all active barbers assigned to this branch."""
        result = await self.db.execute(
            select(User).where(
                User.branch_id == branch_id,
                User.role == UserRole.BARBER,
                User.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    async def _collect_raw_data(
        self,
        branch_id: uuid.UUID,
        target_date: date,
        barbers: list[User],
    ) -> list[_BarberRawData]:
        """Collect raw metrics for each barber on the given date."""
        # Single query for all completed visits
        visits_result = await self.db.execute(
            select(Visit).where(
                Visit.branch_id == branch_id,
                Visit.date == target_date,
                Visit.status == "completed",
            )
        )
        all_visits = visits_result.scalars().all()

        # Group visits by barber_id
        visits_by_barber: dict[uuid.UUID, list[Visit]] = {}
        for visit in all_visits:
            visits_by_barber.setdefault(visit.barber_id, []).append(visit)

        # Single query for reviews
        reviews_result = await self.db.execute(
            select(
                Review.barber_id,
                sa_func.avg(Review.rating).label("avg_rating"),
            )
            .where(
                Review.branch_id == branch_id,
                cast(Review.created_at, Date) == target_date,
            )
            .group_by(Review.barber_id)
        )
        # Build a dict of barber_id -> avg_rating
        reviews_by_barber: dict[uuid.UUID, float] = {}
        for row in reviews_result:
            reviews_by_barber[row.barber_id] = float(row.avg_rating)

        # Build raw data for each barber
        raw_data: list[_BarberRawData] = []
        for barber in barbers:
            barber_visits = visits_by_barber.get(barber.id, [])

            revenue = sum(v.revenue for v in barber_visits)
            products_count = sum(v.products_count for v in barber_visits)
            extras_count = sum(v.extras_count for v in barber_visits)
            cs_value = self._compute_cs(barber_visits, barber.haircut_price)
            reviews_avg = reviews_by_barber.get(barber.id)

            raw_data.append(
                _BarberRawData(
                    barber_id=barber.id,
                    barber_name=barber.name,
                    haircut_price=barber.haircut_price,
                    revenue=revenue,
                    visits_count=len(barber_visits),
                    cs_value=cs_value,
                    products_count=products_count,
                    extras_count=extras_count,
                    reviews_avg=reviews_avg,
                )
            )

        return raw_data

    @staticmethod
    def _compute_cs(
        visits: list[Visit],
        haircut_price: int | None,
    ) -> float:
        """Compute average CS (Check/Service ratio) for a barber's daily visits.

        CS_visit = visit.services_revenue / haircut_price
        CS_day = sum(CS_visit) / len(visits)
        """
        if not visits or not haircut_price:
            return 0.0
        cs_sum = sum(v.services_revenue / haircut_price for v in visits)
        return cs_sum / len(visits)

    @staticmethod
    def _normalize(values: list[float]) -> list[float]:
        """Normalize values so the leader = 100, others proportional.

        If max is 0, all return 0.0.
        """
        if not values:
            return []
        max_val = max(values)
        if max_val == 0:
            return [0.0] * len(values)
        return [(v / max_val) * 100 for v in values]

    @staticmethod
    def _compute_weighted_score(
        revenue_score: float,
        cs_score: float,
        products_score: float,
        extras_score: float,
        reviews_score: float,
        config: Any,
    ) -> float:
        """Apply the weighted sum formula using config weights."""
        rw = getattr(config, "revenue_weight", _DEFAULT_WEIGHTS["revenue_weight"])
        cw = getattr(config, "cs_weight", _DEFAULT_WEIGHTS["cs_weight"])
        pw = getattr(config, "products_weight", _DEFAULT_WEIGHTS["products_weight"])
        ew = getattr(config, "extras_weight", _DEFAULT_WEIGHTS["extras_weight"])
        vw = getattr(config, "reviews_weight", _DEFAULT_WEIGHTS["reviews_weight"])

        return (
            revenue_score * rw / 100
            + cs_score * cw / 100
            + products_score * pw / 100
            + extras_score * ew / 100
            + reviews_score * vw / 100
        )

    def _score_barbers(
        self,
        raw_data: list[_BarberRawData],
        config: Any,
    ) -> list[_BarberScoredData]:
        """Normalize all metrics and compute weighted scores."""
        # Extract raw values
        revenues = [float(b.revenue) for b in raw_data]
        cs_values = [b.cs_value for b in raw_data]
        products = [float(b.products_count) for b in raw_data]
        extras = [float(b.extras_count) for b in raw_data]
        reviews = [b.reviews_avg if b.reviews_avg is not None else 0.0 for b in raw_data]

        # Normalize
        rev_scores = self._normalize(revenues)
        cs_scores = self._normalize(cs_values)
        prod_scores = self._normalize(products)
        ext_scores = self._normalize(extras)
        rev_review_scores = self._normalize(reviews)

        # Build scored entries
        scored: list[_BarberScoredData] = []
        for i, raw in enumerate(raw_data):
            total = self._compute_weighted_score(
                rev_scores[i],
                cs_scores[i],
                prod_scores[i],
                ext_scores[i],
                rev_review_scores[i],
                config,
            )
            scored.append(
                _BarberScoredData(
                    barber_id=raw.barber_id,
                    barber_name=raw.barber_name,
                    revenue=raw.revenue,
                    cs_value=raw.cs_value,
                    products_count=raw.products_count,
                    extras_count=raw.extras_count,
                    reviews_avg=raw.reviews_avg,
                    revenue_score=rev_scores[i],
                    cs_score=cs_scores[i],
                    products_score=prod_scores[i],
                    extras_score=ext_scores[i],
                    reviews_score=rev_review_scores[i],
                    total_score=total,
                )
            )

        return scored

    @staticmethod
    def _assign_ranks(entries: list[_BarberScoredData]) -> list[_BarberScoredData]:
        """Sort by total_score DESC, then revenue DESC for ties. Assign 1-based ranks."""
        entries.sort(key=lambda e: (e.total_score, e.revenue), reverse=True)
        for i, entry in enumerate(entries):
            entry.rank = i + 1
        return entries

    async def _persist_ratings(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID,
        target_date: date,
        scored_entries: list[_BarberScoredData],
    ) -> None:
        """UPSERT all rating entries into daily_ratings table."""
        immutable_keys = {"id", "organization_id", "barber_id", "date"}

        for entry in scored_entries:
            values = {
                "id": uuid.uuid4(),
                "organization_id": organization_id,
                "branch_id": branch_id,
                "barber_id": entry.barber_id,
                "date": target_date,
                "revenue": entry.revenue,
                "cs_value": entry.cs_value,
                "products_count": entry.products_count,
                "extras_count": entry.extras_count,
                "reviews_avg": entry.reviews_avg,
                "revenue_score": entry.revenue_score,
                "cs_score": entry.cs_score,
                "products_score": entry.products_score,
                "extras_score": entry.extras_score,
                "reviews_score": entry.reviews_score,
                "total_score": entry.total_score,
                "rank": entry.rank,
            }

            stmt = pg_insert(DailyRating).values(**values)
            update_cols = {
                k: getattr(stmt.excluded, k)
                for k in values
                if k not in immutable_keys
            }
            stmt = stmt.on_conflict_do_update(
                constraint="uq_daily_ratings_barber_date",
                set_=update_cols,
            )
            await self.db.execute(stmt)

        await self.db.commit()

    async def _cache_rating(
        self,
        branch_id: uuid.UUID,
        target_date: date,
        scored: list[_BarberScoredData],
        prize_fund: dict[str, int],
    ) -> None:
        """Store the rating result as JSON in Redis."""
        key = f"rating:{branch_id}:{target_date}"

        payload = {
            "type": "rating_update",
            "branch_id": str(branch_id),
            "date": str(target_date),
            "timestamp": datetime.now(UTC).isoformat(),
            "ratings": [
                {
                    "barber_id": str(e.barber_id),
                    "name": e.barber_name,
                    "rank": e.rank,
                    "total_score": round(e.total_score, 2),
                    "revenue": e.revenue,
                    "cs_value": round(e.cs_value, 4),
                    "products_count": e.products_count,
                    "extras_count": e.extras_count,
                    "reviews_avg": round(e.reviews_avg, 2) if e.reviews_avg is not None else None,
                    "revenue_score": round(e.revenue_score, 2),
                    "cs_score": round(e.cs_score, 2),
                    "products_score": round(e.products_score, 2),
                    "extras_score": round(e.extras_score, 2),
                    "reviews_score": round(e.reviews_score, 2),
                }
                for e in scored
            ],
            "prize_fund": prize_fund,
        }

        await self.redis.set(key, json.dumps(payload), ex=_CACHE_TTL)


class _DefaultConfig:
    """Fallback config when no RatingConfig exists in the database."""

    revenue_weight: int = 20
    cs_weight: int = 20
    products_weight: int = 25
    extras_weight: int = 25
    reviews_weight: int = 10
    prize_gold_pct: float = 0.5
    prize_silver_pct: float = 0.3
    prize_bronze_pct: float = 0.1
