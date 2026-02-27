"""PVR (Premium for High Results) service.

Calculates cumulative monthly clean revenue for barbers,
checks threshold crossings, and sends bell notifications.
"""

import json
import uuid
from datetime import UTC, date, datetime

import redis.asyncio as aioredis
import structlog
from sqlalchemy import select
from sqlalchemy import func as sa_func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.pvr_config import PVRConfig
from app.models.pvr_record import PVRRecord
from app.models.user import User, UserRole
from app.models.visit import Visit

logger = structlog.stdlib.get_logger()

# Default thresholds sorted descending by amount (in kopecks).
# 300k rubles = 30_000_000 kopecks, bonus 10k = 1_000_000, etc.
_DEFAULT_THRESHOLDS: list[dict[str, int]] = [
    {"amount": 80_000_000, "bonus": 5_000_000},
    {"amount": 60_000_000, "bonus": 4_000_000},
    {"amount": 50_000_000, "bonus": 3_000_000},
    {"amount": 40_000_000, "bonus": 2_000_000},
    {"amount": 35_000_000, "bonus": 1_500_000},
    {"amount": 30_000_000, "bonus": 1_000_000},
]


class PVRService:
    """Calculates PVR (cumulative monthly bonuses) for barbers."""

    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self.db = db
        self.redis = redis

    # --- Public methods ---

    async def recalculate_barber(
        self,
        barber_id: uuid.UUID,
        organization_id: uuid.UUID,
        target_month: date,
    ) -> PVRRecord | None:
        """Recalculate PVR for a single barber for the given month.

        Pipeline:
        1. Load config (thresholds, count_products, count_certificates)
        2. Sum clean revenue from completed visits
        3. Find highest crossed threshold
        4. Detect new threshold crossing vs previous record
        5. UPSERT pvr_records
        6. Publish bell notification if new threshold crossed
        """
        month_start = target_month.replace(day=1)

        # 1. Load config
        config = await self._load_config(organization_id)

        # 2. Calculate clean revenue
        cumulative_revenue = await self._calc_clean_revenue(
            barber_id, month_start, config
        )

        # 3. Determine threshold
        thresholds = self._get_thresholds(config)
        current_threshold, bonus_amount = self._find_threshold(
            cumulative_revenue, thresholds
        )

        # 4. Load previous record and detect new crossing
        prev_record = await self._get_record(barber_id, month_start)
        old_threshold = prev_record.current_threshold if prev_record else None

        thresholds_reached: list[dict] = list(
            prev_record.thresholds_reached or []
        ) if prev_record else []

        new_threshold_crossed = False
        if current_threshold is not None and current_threshold > (old_threshold or 0):
            new_threshold_crossed = True
            reached_amounts = {t["amount"] for t in thresholds_reached}
            today_str = str(date.today())
            for t in sorted(thresholds, key=lambda x: x["amount"]):
                if (
                    t["amount"] > (old_threshold or 0)
                    and t["amount"] <= current_threshold
                    and t["amount"] not in reached_amounts
                ):
                    thresholds_reached.append({
                        "amount": t["amount"],
                        "reached_at": today_str,
                    })

        # 5. UPSERT
        values: dict = {
            "id": uuid.uuid4(),
            "organization_id": organization_id,
            "barber_id": barber_id,
            "month": month_start,
            "cumulative_revenue": cumulative_revenue,
            "current_threshold": current_threshold,
            "bonus_amount": bonus_amount,
            "thresholds_reached": thresholds_reached or None,
        }

        upsert_cols = (
            "cumulative_revenue",
            "current_threshold",
            "bonus_amount",
            "thresholds_reached",
        )
        stmt = pg_insert(PVRRecord).values(**values)
        update_cols = {k: getattr(stmt.excluded, k) for k in upsert_cols}
        stmt = stmt.on_conflict_do_update(
            constraint="uq_pvr_records_barber_month",
            set_=update_cols,
        )
        await self.db.execute(stmt)
        await self.db.commit()

        # 6. Bell notification
        if new_threshold_crossed and current_threshold is not None:
            barber = await self._get_barber(barber_id)
            barber_name = barber.name if barber else "Unknown"
            await self._publish_bell(
                organization_id,
                barber_id,
                barber_name,
                cumulative_revenue,
                current_threshold,
                bonus_amount,
            )

        await logger.ainfo(
            "PVR recalculated",
            barber_id=str(barber_id),
            month=str(month_start),
            revenue=cumulative_revenue,
            threshold=current_threshold,
            bonus=bonus_amount,
            bell=new_threshold_crossed,
        )

        return await self._get_record(barber_id, month_start)

    async def recalculate_branch(
        self,
        branch_id: uuid.UUID,
        target_month: date,
    ) -> list[PVRRecord]:
        """Recalculate PVR for all active barbers in a branch."""
        result = await self.db.execute(select(Branch).where(Branch.id == branch_id))
        branch = result.scalar_one_or_none()
        if not branch:
            return []

        result = await self.db.execute(
            select(User).where(
                User.branch_id == branch_id,
                User.role == UserRole.BARBER,
                User.is_active.is_(True),
            )
        )
        barbers = result.scalars().all()

        records: list[PVRRecord] = []
        for barber in barbers:
            record = await self.recalculate_barber(
                barber.id, branch.organization_id, target_month
            )
            if record:
                records.append(record)
        return records

    async def get_barber_pvr(
        self,
        barber_id: uuid.UUID,
        organization_id: uuid.UUID,
        target_month: date | None = None,
    ) -> dict:
        """Get PVR data for a single barber."""
        month_start = (target_month or date.today()).replace(day=1)
        record = await self._get_record(barber_id, month_start)
        config = await self._load_config(organization_id)
        thresholds = self._get_thresholds(config)
        barber = await self._get_barber(barber_id)

        return self._format_barber_pvr(record, barber, thresholds)

    async def get_branch_pvr(
        self,
        branch_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> list[dict]:
        """Get PVR data for all active barbers in a branch (current month)."""
        month_start = date.today().replace(day=1)

        result = await self.db.execute(
            select(User).where(
                User.branch_id == branch_id,
                User.role == UserRole.BARBER,
                User.is_active.is_(True),
            )
        )
        barbers = result.scalars().all()

        config = await self._load_config(organization_id)
        thresholds = self._get_thresholds(config)

        pvr_list: list[dict] = []
        for barber in barbers:
            record = await self._get_record(barber.id, month_start)
            pvr_list.append(self._format_barber_pvr(record, barber, thresholds))
        return pvr_list

    async def get_thresholds(
        self,
        organization_id: uuid.UUID,
    ) -> list[dict[str, int]]:
        """Get the threshold configuration for an organization."""
        config = await self._load_config(organization_id)
        thresholds = self._get_thresholds(config)
        return sorted(thresholds, key=lambda t: t["amount"])

    # --- Private helpers ---

    async def _load_config(self, organization_id: uuid.UUID) -> PVRConfig | None:
        """Load PVRConfig for the organization."""
        result = await self.db.execute(
            select(PVRConfig).where(PVRConfig.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    def _get_thresholds(self, config: PVRConfig | None) -> list[dict[str, int]]:
        """Get thresholds sorted descending by amount."""
        if config and config.thresholds:
            return sorted(config.thresholds, key=lambda t: t["amount"], reverse=True)
        return list(_DEFAULT_THRESHOLDS)

    @staticmethod
    def _find_threshold(
        revenue: int,
        thresholds: list[dict[str, int]],
    ) -> tuple[int | None, int]:
        """Find highest crossed threshold. Returns (threshold_amount, bonus)."""
        for t in sorted(thresholds, key=lambda x: x["amount"], reverse=True):
            if revenue >= t["amount"]:
                return t["amount"], t["bonus"]
        return None, 0

    async def _calc_clean_revenue(
        self,
        barber_id: uuid.UUID,
        month_start: date,
        config: PVRConfig | None,
    ) -> int:
        """Sum clean revenue for a barber in the given month.

        Clean revenue = services_revenue only by default.
        Includes products_revenue if config.count_products is True.
        Excludes certificate payments by default.
        Includes certificates if config.count_certificates is True.
        """
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)

        # Payment type filter
        allowed_payments = ["card", "cash", "qr"]
        if config and config.count_certificates:
            allowed_payments.append("certificate")

        # Revenue expression
        if config and config.count_products:
            revenue_expr = Visit.services_revenue + Visit.products_revenue
        else:
            revenue_expr = Visit.services_revenue

        stmt = select(
            sa_func.coalesce(sa_func.sum(revenue_expr), 0)
        ).where(
            Visit.barber_id == barber_id,
            Visit.date >= month_start,
            Visit.date < month_end,
            Visit.status == "completed",
            Visit.payment_type.in_(allowed_payments),
        )

        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _get_record(
        self, barber_id: uuid.UUID, month: date
    ) -> PVRRecord | None:
        """Load existing PVR record."""
        result = await self.db.execute(
            select(PVRRecord).where(
                PVRRecord.barber_id == barber_id,
                PVRRecord.month == month,
            )
        )
        return result.scalar_one_or_none()

    async def _get_barber(self, barber_id: uuid.UUID) -> User | None:
        """Load barber user by id."""
        result = await self.db.execute(select(User).where(User.id == barber_id))
        return result.scalar_one_or_none()

    @staticmethod
    def _format_barber_pvr(
        record: PVRRecord | None,
        barber: User | None,
        thresholds: list[dict[str, int]],
    ) -> dict:
        """Format PVR data for API response."""
        cumulative = record.cumulative_revenue if record else 0
        current_t = record.current_threshold if record else None
        bonus = record.bonus_amount if record else 0
        reached = record.thresholds_reached if record and record.thresholds_reached else []

        barber_id = barber.id if barber else (record.barber_id if record else uuid.UUID(int=0))
        name = barber.name if barber else "Unknown"

        # Next threshold = smallest threshold above cumulative_revenue
        next_threshold: int | None = None
        for t in sorted(thresholds, key=lambda x: x["amount"]):
            if t["amount"] > cumulative:
                next_threshold = t["amount"]
                break

        remaining = (next_threshold - cumulative) if next_threshold else None

        return {
            "barber_id": barber_id,
            "name": name,
            "cumulative_revenue": cumulative,
            "current_threshold": current_t,
            "bonus_amount": bonus,
            "next_threshold": next_threshold,
            "remaining_to_next": remaining,
            "thresholds_reached": reached,
        }

    async def _publish_bell(
        self,
        organization_id: uuid.UUID,
        barber_id: uuid.UUID,
        barber_name: str,
        revenue: int,
        threshold: int,
        bonus: int,
    ) -> None:
        """Publish bell notification via Redis Pub/Sub."""
        payload = {
            "type": "pvr_threshold",
            "barber_id": str(barber_id),
            "barber_name": barber_name,
            "revenue": revenue,
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
