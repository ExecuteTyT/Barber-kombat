"""PVR (Premium for High Results) service — rating-based thresholds.

Monthly bonuses are awarded based on a barber's **monthly rating score** (0-100)
rather than absolute revenue. The score balances five normalized metrics
(revenue, CS, products, extras, reviews) so that a barber with lower traffic
but strong product sales, upsells, or reviews can still earn a premium.

Pipeline (per branch per month):
  RatingEngine.calculate_monthly()  ->  monthly score per barber
      ->  find highest score threshold crossed
      ->  UPSERT pvr_records
      ->  publish bell notification on new crossing
"""

import json
import uuid
from datetime import UTC, date, datetime

import redis.asyncio as aioredis
import structlog
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.pvr_config import PVRConfig
from app.models.pvr_record import PVRRecord
from app.models.user import User, UserRole
from app.models.visit import Visit
from app.services.rating import RatingEngine, _BarberMonthlyScore

logger = structlog.stdlib.get_logger()

# Default score thresholds (0-100 scale). Bonus amounts are in kopecks.
_DEFAULT_THRESHOLDS: list[dict[str, int]] = [
    {"score": 90, "bonus": 500_000_000},
    {"score": 75, "bonus": 200_000_000},
    {"score": 60, "bonus": 100_000_000},
]


class PVRService:
    """Calculates rating-based monthly PVR bonuses for barbers."""

    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self.db = db
        self.redis = redis

    # --- Public methods ---

    async def recalculate_branch(
        self,
        branch_id: uuid.UUID,
        target_month: date,
    ) -> list[PVRRecord]:
        """Recalculate PVR for all active barbers in a branch for the month.

        Computes monthly ratings via RatingEngine, applies score thresholds,
        upserts pvr_records, and emits a bell notification for every barber
        who crossed a new threshold since the last calculation.
        """
        result = await self.db.execute(select(Branch).where(Branch.id == branch_id))
        branch = result.scalar_one_or_none()
        if branch is None:
            return []

        organization_id = branch.organization_id
        month_start = target_month.replace(day=1)

        config = await self._load_config(organization_id)
        thresholds = self._get_thresholds(config)
        min_visits = config.min_visits_per_month if config else 0

        engine = RatingEngine(db=self.db, redis=self.redis)
        monthly_scores = await engine.calculate_monthly(
            branch_id, organization_id, month_start
        )
        scores_by_barber = {m.barber_id: m for m in monthly_scores}

        result = await self.db.execute(
            select(User).where(
                User.branch_id == branch_id,
                User.role == UserRole.BARBER,
                User.is_active.is_(True),
            )
        )
        barbers = list(result.scalars().all())

        records: list[PVRRecord] = []
        for barber in barbers:
            monthly = scores_by_barber.get(barber.id)
            record = await self._upsert_record(
                organization_id=organization_id,
                barber=barber,
                month_start=month_start,
                monthly=monthly,
                thresholds=thresholds,
                min_visits=min_visits,
                config=config,
            )
            if record:
                records.append(record)
        return records

    async def recalculate_barber(
        self,
        barber_id: uuid.UUID,
        organization_id: uuid.UUID,
        target_month: date,
    ) -> PVRRecord | None:
        """Recalculate PVR for a single barber by running the branch pipeline."""
        barber = await self._get_barber(barber_id)
        if barber is None or barber.branch_id is None:
            return None
        await self.recalculate_branch(barber.branch_id, target_month)
        return await self._get_record(barber_id, target_month.replace(day=1))

    async def get_barber_pvr(
        self,
        barber_id: uuid.UUID,
        organization_id: uuid.UUID,
        target_month: date | None = None,
    ) -> dict:
        """Return PVR data for a single barber. Falls back to a live calc."""
        month_start = (target_month or date.today()).replace(day=1)
        record = await self._get_record(barber_id, month_start)
        config = await self._load_config(organization_id)
        thresholds = self._get_thresholds(config)
        barber = await self._get_barber(barber_id)

        if record is None and barber is not None and barber.branch_id is not None:
            engine = RatingEngine(db=self.db, redis=self.redis)
            monthly_scores = await engine.calculate_monthly(
                barber.branch_id, organization_id, month_start
            )
            monthly = next((m for m in monthly_scores if m.barber_id == barber_id), None)
            cumulative = await self._calc_display_revenue(barber_id, month_start, config)
            return self._format_live(
                barber=barber,
                monthly=monthly,
                thresholds=thresholds,
                min_visits=config.min_visits_per_month if config else 0,
                cumulative_revenue=cumulative,
            )

        return self._format_record(record, barber, thresholds, config)

    async def get_branch_pvr(
        self,
        branch_id: uuid.UUID,
        organization_id: uuid.UUID,
        target_date: date | None = None,
    ) -> list[dict]:
        """Return PVR data for all active barbers in a branch."""
        month_start = (target_date or date.today()).replace(day=1)

        result = await self.db.execute(
            select(User).where(
                User.branch_id == branch_id,
                User.role == UserRole.BARBER,
                User.is_active.is_(True),
            )
        )
        barbers = list(result.scalars().all())

        config = await self._load_config(organization_id)
        thresholds = self._get_thresholds(config)
        min_visits = config.min_visits_per_month if config else 0

        engine = RatingEngine(db=self.db, redis=self.redis)
        monthly_scores = await engine.calculate_monthly(
            branch_id, organization_id, month_start
        )
        scores_by_barber = {m.barber_id: m for m in monthly_scores}

        out: list[dict] = []
        for barber in barbers:
            record = await self._get_record(barber.id, month_start)
            if record is None:
                cumulative = await self._calc_display_revenue(barber.id, month_start, config)
                out.append(
                    self._format_live(
                        barber=barber,
                        monthly=scores_by_barber.get(barber.id),
                        thresholds=thresholds,
                        min_visits=min_visits,
                        cumulative_revenue=cumulative,
                    )
                )
            else:
                out.append(self._format_record(record, barber, thresholds, config))
        return out

    async def get_thresholds(
        self,
        organization_id: uuid.UUID,
    ) -> list[dict[str, int]]:
        """Return the threshold configuration for an organization (sorted asc)."""
        config = await self._load_config(organization_id)
        return sorted(self._get_thresholds(config), key=lambda t: t["score"])

    async def preview(
        self,
        branch_id: uuid.UUID,
        organization_id: uuid.UUID,
        target_month: date,
        thresholds: list[dict[str, int]],
        min_visits: int,
    ) -> list[dict]:
        """Simulate PVR for all branch barbers with hypothetical config.

        Does not write to the database — used by the owner's settings UI
        to preview the impact of a weight/threshold change before saving.
        Weights come from the currently saved RatingConfig (owner is expected
        to save the weights first if they changed them alongside thresholds).
        """
        month_start = target_month.replace(day=1)
        engine = RatingEngine(db=self.db, redis=self.redis)
        monthly_scores = await engine.calculate_monthly(
            branch_id, organization_id, month_start
        )

        out: list[dict] = []
        sorted_thresholds = sorted(thresholds, key=lambda t: t["score"], reverse=True)
        for m in monthly_scores:
            score_int = round(m.total_score)
            if m.working_days < min_visits:
                score_int = 0
            current, bonus = self._find_threshold(score_int, sorted_thresholds)
            out.append(
                {
                    "barber_id": str(m.barber_id),
                    "name": m.barber_name,
                    "monthly_rating_score": score_int,
                    "working_days": m.working_days,
                    "current_threshold": current,
                    "bonus_amount": bonus,
                    "revenue": m.revenue,
                }
            )
        out.sort(key=lambda x: x["monthly_rating_score"], reverse=True)
        return out

    # --- Internal pipeline ---

    async def _upsert_record(
        self,
        organization_id: uuid.UUID,
        barber: User,
        month_start: date,
        monthly: _BarberMonthlyScore | None,
        thresholds: list[dict[str, int]],
        min_visits: int,
        config: PVRConfig | None,
    ) -> PVRRecord | None:
        """Persist a barber's monthly PVR record and emit bell on new crossing."""
        score_int = round(monthly.total_score) if monthly else 0
        working_days = monthly.working_days if monthly else 0
        if working_days < min_visits:
            score_int = 0

        current_threshold, bonus_amount = self._find_threshold(score_int, thresholds)

        cumulative_revenue = await self._calc_display_revenue(
            barber.id, month_start, config
        )

        breakdown = self._breakdown(monthly) if monthly else None

        prev = await self._get_record(barber.id, month_start)
        old_threshold = prev.current_threshold if prev else None
        thresholds_reached: list[dict] = (
            list(prev.thresholds_reached or []) if prev else []
        )

        crossed_new = False
        if current_threshold is not None and current_threshold > (old_threshold or 0):
            crossed_new = True
            reached_scores = {t["score"] for t in thresholds_reached}
            today_str = str(date.today())
            for t in sorted(thresholds, key=lambda x: x["score"]):
                if (
                    t["score"] > (old_threshold or 0)
                    and t["score"] <= current_threshold
                    and t["score"] not in reached_scores
                ):
                    thresholds_reached.append(
                        {"score": t["score"], "reached_at": today_str}
                    )

        values: dict = {
            "id": uuid.uuid4(),
            "organization_id": organization_id,
            "barber_id": barber.id,
            "month": month_start,
            "cumulative_revenue": cumulative_revenue,
            "current_threshold": current_threshold,
            "bonus_amount": bonus_amount,
            "thresholds_reached": thresholds_reached or None,
            "monthly_rating_score": score_int,
            "metric_breakdown": breakdown,
            "working_days": working_days,
        }

        upsert_cols = (
            "cumulative_revenue",
            "current_threshold",
            "bonus_amount",
            "thresholds_reached",
            "monthly_rating_score",
            "metric_breakdown",
            "working_days",
        )
        stmt = pg_insert(PVRRecord).values(**values)
        update_cols = {k: getattr(stmt.excluded, k) for k in upsert_cols}
        stmt = stmt.on_conflict_do_update(
            constraint="uq_pvr_records_barber_month",
            set_=update_cols,
        )
        await self.db.execute(stmt)
        await self.db.commit()

        if crossed_new and current_threshold is not None:
            await self._publish_bell(
                organization_id=organization_id,
                barber_id=barber.id,
                barber_name=barber.name,
                score=score_int,
                threshold=current_threshold,
                bonus=bonus_amount,
            )

        await logger.ainfo(
            "PVR recalculated",
            barber_id=str(barber.id),
            month=str(month_start),
            score=score_int,
            working_days=working_days,
            threshold=current_threshold,
            bonus=bonus_amount,
            bell=crossed_new,
        )

        return await self._get_record(barber.id, month_start)

    # --- Helpers ---

    async def _load_config(self, organization_id: uuid.UUID) -> PVRConfig | None:
        result = await self.db.execute(
            select(PVRConfig).where(PVRConfig.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    def _get_thresholds(self, config: PVRConfig | None) -> list[dict[str, int]]:
        """Return thresholds sorted descending by score."""
        raw = config.thresholds if (config and config.thresholds) else list(_DEFAULT_THRESHOLDS)
        # Support legacy rows that slipped through with {amount, bonus}.
        normalized = []
        for t in raw:
            if "score" in t:
                normalized.append({"score": int(t["score"]), "bonus": int(t["bonus"])})
        if not normalized:
            normalized = list(_DEFAULT_THRESHOLDS)
        return sorted(normalized, key=lambda t: t["score"], reverse=True)

    @staticmethod
    def _find_threshold(
        score: int,
        thresholds: list[dict[str, int]],
    ) -> tuple[int | None, int]:
        """Return the highest crossed score threshold (threshold_score, bonus)."""
        for t in sorted(thresholds, key=lambda x: x["score"], reverse=True):
            if score >= t["score"]:
                return t["score"], t["bonus"]
        return None, 0

    @staticmethod
    def _breakdown(monthly: _BarberMonthlyScore) -> dict[str, int]:
        return {
            "revenue_score": round(monthly.revenue_score),
            "cs_score": round(monthly.cs_score),
            "products_score": round(monthly.products_score),
            "extras_score": round(monthly.extras_score),
            "reviews_score": round(monthly.reviews_score),
        }

    async def _calc_display_revenue(
        self,
        barber_id: uuid.UUID,
        month_start: date,
        config: PVRConfig | None,
    ) -> int:
        """Sum the barber's revenue for display purposes (not used for thresholds)."""
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)

        allowed_payments = ["card", "cash", "qr"]
        if config and config.count_certificates:
            allowed_payments.append("certificate")

        if config and config.count_products:
            revenue_expr = Visit.services_revenue + Visit.products_revenue
        else:
            revenue_expr = Visit.services_revenue

        stmt = select(sa_func.coalesce(sa_func.sum(revenue_expr), 0)).where(
            Visit.barber_id == barber_id,
            Visit.date >= month_start,
            Visit.date < month_end,
            Visit.status == "completed",
            Visit.payment_type.in_(allowed_payments),
        )
        result = await self.db.execute(stmt)
        return int(result.scalar_one() or 0)

    async def _get_record(self, barber_id: uuid.UUID, month: date) -> PVRRecord | None:
        result = await self.db.execute(
            select(PVRRecord).where(
                PVRRecord.barber_id == barber_id,
                PVRRecord.month == month,
            )
        )
        return result.scalar_one_or_none()

    async def _get_barber(self, barber_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == barber_id))
        return result.scalar_one_or_none()

    # --- Formatters ---

    @staticmethod
    def _next_threshold_score(
        score: int, thresholds: list[dict[str, int]]
    ) -> int | None:
        for t in sorted(thresholds, key=lambda x: x["score"]):
            if t["score"] > score:
                return t["score"]
        return None

    def _format_record(
        self,
        record: PVRRecord | None,
        barber: User | None,
        thresholds: list[dict[str, int]],
        config: PVRConfig | None,
    ) -> dict:
        score = record.monthly_rating_score if record else 0
        cumulative = record.cumulative_revenue if record else 0
        current_t = record.current_threshold if record else None
        bonus = record.bonus_amount if record else 0
        reached = record.thresholds_reached if record and record.thresholds_reached else []
        breakdown = (
            record.metric_breakdown
            if record and record.metric_breakdown
            else self._empty_breakdown()
        )
        working_days = record.working_days if record else 0

        next_score = self._next_threshold_score(score, thresholds)
        gap = (next_score - score) if next_score is not None else None

        barber_id = barber.id if barber else (record.barber_id if record else uuid.UUID(int=0))
        name = barber.name if barber else "Unknown"

        return {
            "barber_id": barber_id,
            "name": name,
            "cumulative_revenue": cumulative,
            "current_threshold": current_t,
            "bonus_amount": bonus,
            "next_threshold": next_score,
            "remaining_to_next": gap,
            "thresholds_reached": reached,
            "monthly_rating_score": score,
            "metric_breakdown": breakdown,
            "working_days": working_days,
            "min_visits_required": config.min_visits_per_month if config else 0,
        }

    def _format_live(
        self,
        barber: User,
        monthly: _BarberMonthlyScore | None,
        thresholds: list[dict[str, int]],
        min_visits: int,
        cumulative_revenue: int,
    ) -> dict:
        score = round(monthly.total_score) if monthly else 0
        working_days = monthly.working_days if monthly else 0
        if working_days < min_visits:
            score = 0
        current_t, bonus = self._find_threshold(score, thresholds)
        next_score = self._next_threshold_score(score, thresholds)
        gap = (next_score - score) if next_score is not None else None
        breakdown = self._breakdown(monthly) if monthly else self._empty_breakdown()

        return {
            "barber_id": barber.id,
            "name": barber.name,
            "cumulative_revenue": cumulative_revenue,
            "current_threshold": current_t,
            "bonus_amount": bonus,
            "next_threshold": next_score,
            "remaining_to_next": gap,
            "thresholds_reached": [],
            "monthly_rating_score": score,
            "metric_breakdown": breakdown,
            "working_days": working_days,
            "min_visits_required": min_visits,
        }

    @staticmethod
    def _empty_breakdown() -> dict[str, int]:
        return {
            "revenue_score": 0,
            "cs_score": 0,
            "products_score": 0,
            "extras_score": 0,
            "reviews_score": 0,
        }

    async def _publish_bell(
        self,
        organization_id: uuid.UUID,
        barber_id: uuid.UUID,
        barber_name: str,
        score: int,
        threshold: int,
        bonus: int,
    ) -> None:
        payload = {
            "type": "pvr_threshold",
            "barber_id": str(barber_id),
            "barber_name": barber_name,
            "score": score,
            "threshold": threshold,
            "bonus": bonus,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self.redis.publish(
            f"ws:org:{organization_id}",
            json.dumps(payload),
        )
        await logger.ainfo(
            "PVR bell notification sent",
            barber_id=str(barber_id),
            barber_name=barber_name,
            threshold=threshold,
            bonus=bonus,
        )
