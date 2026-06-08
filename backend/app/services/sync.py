"""Service for synchronizing data from YClients API to local database."""

import contextlib
import uuid
from datetime import UTC, date, datetime, timedelta, timezone

import structlog
from sqlalchemy import case, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.yclients.client import YClientsClient
from app.integrations.yclients.schemas import YClientRecord, YClientStaff
from app.models.branch import Branch
from app.models.client import Client
from app.models.rating_config import RatingConfig
from app.models.review import Review, ReviewStatus
from app.models.user import User, UserRole
from app.models.visit import Visit

logger = structlog.stdlib.get_logger()

# --- Mapping helpers ---

PAYMENT_TYPE_MAP: dict[int, str] = {
    0: "card",
    1: "card",
    2: "cash",
    3: "card",  # online payment
    4: "certificate",
    6: "qr",
}

# YClients visit_attendance field (per official API):
#   -1 — client did not come
#    0 — waiting / not yet confirmed (appointment in the future)
#    1 — client came (service delivered)
#    2 — client confirmed the booking (but has not come yet)
#
# Anything other than "completed" must NOT count toward revenue, ratings, or
# PVR. The default is intentionally "scheduled" so that unknown attendance
# values never silently inflate today's revenue.
ATTENDANCE_STATUS_MAP: dict[int, str] = {
    -1: "no_show",
    0: "scheduled",
    1: "completed",
    2: "scheduled",
}


def rubles_to_kopecks(amount: float) -> int:
    """Convert a ruble amount (float) to kopecks (int)."""
    return round(amount * 100)


def map_payment_type(paid_full: int) -> str:
    return PAYMENT_TYPE_MAP.get(paid_full, "card")


def map_visit_status(visit_attendance: int) -> str:
    return ATTENDANCE_STATUS_MAP.get(visit_attendance, "scheduled")


def _normalize_extras_keywords(extra_services_list: list[str]) -> list[str]:
    return [k.lower().strip() for k in extra_services_list if k and k.strip()]


def count_extras(services: list[dict], extra_services_list: list[str]) -> int:
    """Count how many extras are present across a visit's services list.

    YClients stores services as combo strings (e.g. "Мужская стрижка +
    Оформление бороды + Камуфляж бороды"), so exact-string equality would
    miss every combo. We instead do case-insensitive substring matching and
    count each keyword hit inside the title — so a combo that contains both
    "оформление бороды" and "камуфляж бороды" contributes +2.
    """
    keywords = _normalize_extras_keywords(extra_services_list)
    if not keywords:
        return 0
    count = 0
    for svc in services:
        title = (svc.get("title") or "").lower()
        for kw in keywords:
            if kw in title:
                count += 1
    return count


def count_products(goods_transactions: list[dict]) -> int:
    """Sum product quantities from goods transactions.

    Only counts positive amounts (sales). Negative amounts are returns
    and should not reduce the sold-product count.
    """
    return sum(max(g.get("amount", 1), 0) for g in goods_transactions)


def map_record_to_visit_dict(
    record: YClientRecord,
    organization_id: uuid.UUID,
    branch_id: uuid.UUID,
    barber_id: uuid.UUID,
    client_id: uuid.UUID | None,
    extra_services_list: list[str],
) -> dict:
    """Map a YClients record to a dict of Visit column values."""
    services_list = [
        {"id": s.id, "title": s.title, "cost": s.cost, "is_extra": False} for s in record.services
    ]
    products_list = [
        {"id": g.id, "title": g.title, "cost": g.cost, "amount": g.amount}
        for g in record.goods_transactions
    ]

    services_revenue = rubles_to_kopecks(sum(s.cost for s in record.services))
    products_revenue = rubles_to_kopecks(sum(g.cost * g.amount for g in record.goods_transactions))

    # YClients returns cost=0 for records that haven't been fully settled yet,
    # but individual service/product costs are already populated.
    # Fall back to sum of services + products when record.cost is zero.
    record_cost = rubles_to_kopecks(record.cost)
    if record_cost == 0:
        record_cost = services_revenue + products_revenue

    # Mark extras in services list (substring matching, multi-hit per combo).
    extras = 0
    keywords = _normalize_extras_keywords(extra_services_list)
    for svc in services_list:
        title = (svc.get("title") or "").lower()
        hits = sum(1 for kw in keywords if kw in title)
        if hits > 0:
            svc["is_extra"] = True
            extras += hits

    return {
        "organization_id": organization_id,
        "branch_id": branch_id,
        "barber_id": barber_id,
        "client_id": client_id,
        "yclients_record_id": record.id,
        "date": date.fromisoformat(record.date[:10]) if record.date else date.today(),
        "revenue": record_cost,
        "services_revenue": services_revenue,
        "products_revenue": products_revenue,
        "services": services_list,
        "products": products_list,
        "extras_count": extras,
        "products_count": count_products(products_list),
        "payment_type": map_payment_type(record.paid_full),
        "status": map_visit_status(record.visit_attendance),
        "confirmed": bool(record.confirmed),
    }


# Reviews with rating <= this are negative (kept in sync with ReviewService).
_NEGATIVE_RATING = 3

# Only alert for negative reviews newer than this. Guards against the first
# backfill flooding the Telegram chat with historical negatives.
_FRESH_ALERT_HOURS = 48

# YClients comment dates are salon-local (Moscow time, UTC+3).
_MSK = timezone(timedelta(hours=3))


def parse_comment_date(value: str) -> datetime | None:
    """Parse a YClients comment date ('YYYY-MM-DD HH:MM:SS', salon-local MSK).

    Returns a timezone-aware datetime (MSK), or None if it can't be parsed —
    in which case the caller lets the DB default (now()) apply.
    """
    if not value:
        return None
    try:
        naive = datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return naive.replace(tzinfo=_MSK)


class SyncService:
    """Synchronizes data from YClients API into the local database."""

    def __init__(self, db: AsyncSession, yclients: YClientsClient):
        self.db = db
        self.yclients = yclients

    async def _get_extra_services(self, organization_id: uuid.UUID) -> list[str]:
        """Load the extras service names from RatingConfig."""
        result = await self.db.execute(
            select(RatingConfig.extra_services).where(
                RatingConfig.organization_id == organization_id
            )
        )
        row = result.scalar_one_or_none()
        if row and isinstance(row, list):
            return row
        return []

    async def _resolve_branch(self, yclients_company_id: int) -> Branch | None:
        """Find a Branch by its yclients_company_id."""
        result = await self.db.execute(
            select(Branch).where(Branch.yclients_company_id == yclients_company_id)
        )
        return result.scalar_one_or_none()

    async def _resolve_barber(
        self, yclients_staff_id: int, organization_id: uuid.UUID
    ) -> User | None:
        """Find a barber User by yclients_staff_id within an organization."""
        result = await self.db.execute(
            select(User).where(
                User.yclients_staff_id == yclients_staff_id,
                User.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def _upsert_client(
        self,
        organization_id: uuid.UUID,
        yclients_client_id: int,
        name: str,
        phone: str,
    ) -> uuid.UUID:
        """UPSERT a client record, return its UUID."""
        stmt = pg_insert(Client).values(
            id=uuid.uuid4(),
            organization_id=organization_id,
            yclients_client_id=yclients_client_id,
            name=name,
            phone=phone,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["yclients_client_id", "organization_id"],
            set_={
                "name": stmt.excluded.name,
                "phone": stmt.excluded.phone,
            },
        )
        await self.db.execute(stmt)

        result = await self.db.execute(
            select(Client.id).where(
                Client.yclients_client_id == yclients_client_id,
                Client.organization_id == organization_id,
            )
        )
        return result.scalar_one()

    async def _upsert_visit(self, visit_data: dict) -> None:
        """UPSERT a visit record by yclients_record_id + organization_id.

        Preserves admin-set status="confirmed": when an admin manually verifies
        a check (admin.py), we must not let the next polling cycle downgrade
        that visit back to "scheduled" if YClients still reports attendance=0.
        """
        stmt = pg_insert(Visit).values(id=uuid.uuid4(), **visit_data)
        update_cols = {
            k: getattr(stmt.excluded, k)
            for k in visit_data
            if k not in ("organization_id", "yclients_record_id", "status")
        }
        update_cols["status"] = case(
            (Visit.status == "confirmed", Visit.status),
            else_=stmt.excluded.status,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["yclients_record_id", "organization_id"],
            set_=update_cols,
        )
        await self.db.execute(stmt)

    async def sync_records(
        self,
        branch_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> int:
        """Sync visit records for a branch within a date range.

        Returns the number of records synced.
        """
        # Load branch
        result = await self.db.execute(select(Branch).where(Branch.id == branch_id))
        branch = result.scalar_one_or_none()
        if branch is None or branch.yclients_company_id is None:
            await logger.awarning(
                "Branch not found or missing yclients_company_id", branch_id=str(branch_id)
            )
            return 0

        organization_id = branch.organization_id
        extra_services = await self._get_extra_services(organization_id)

        # Fetch records from YClients
        records = await self.yclients.get_records(branch.yclients_company_id, date_from, date_to)

        synced = 0
        skipped = 0
        for record in records:
            # SAVEPOINT per record: if the upsert of one record raises
            # (FK violation, integrity error, Pydantic coercion failure, ...)
            # the outer transaction stays valid and we keep processing the
            # rest of the batch. Without this a single bad record poisons
            # the whole sync with PendingRollbackError.
            try:
                async with self.db.begin_nested():
                    # Resolve barber
                    barber = await self._resolve_barber(
                        record.staff_id, organization_id
                    )
                    if barber is None:
                        await logger.awarning(
                            "Barber not found, skipping record",
                            staff_id=record.staff_id,
                            record_id=record.id,
                        )
                        skipped += 1
                        continue

                    # Resolve client
                    client_id = None
                    if record.client:
                        client_id = await self._upsert_client(
                            organization_id=organization_id,
                            yclients_client_id=record.client.id,
                            name=record.client.name,
                            phone=record.client.phone,
                        )

                    visit_data = map_record_to_visit_dict(
                        record=record,
                        organization_id=organization_id,
                        branch_id=branch_id,
                        barber_id=barber.id,
                        client_id=client_id,
                        extra_services_list=extra_services,
                    )

                    await self._upsert_visit(visit_data)
                    synced += 1

            except Exception:
                await logger.aexception(
                    "Error syncing record",
                    record_id=record.id,
                )

        await self.db.commit()
        await logger.ainfo(
            "Records synced",
            branch_id=str(branch_id),
            date_from=str(date_from),
            date_to=str(date_to),
            total=len(records),
            synced=synced,
            skipped=skipped,
        )
        return synced

    async def sync_reviews(self, branch_id: uuid.UUID) -> int:
        """Sync YClients reviews (отзывы) for a branch into the reviews table.

        Maps salon_id -> this branch, master_id -> barber, and record_id -> the
        visit (taking its client). Idempotent via reviews.yclients_comment_id —
        already-synced comments are skipped. Negative reviews (rating <= 3) are
        stored as NEW so the admin alarum surfaces them; positives as PROCESSED.
        Reviews whose master can't be resolved are skipped (barber is required).

        For freshly-appeared negative reviews (created within the last
        ``_FRESH_ALERT_HOURS``) a Telegram alert is queued after commit; older
        backfilled negatives are stored silently. Returns the number inserted.
        """
        result = await self.db.execute(select(Branch).where(Branch.id == branch_id))
        branch = result.scalar_one_or_none()
        if branch is None or branch.yclients_company_id is None:
            await logger.awarning(
                "Branch not found or missing yclients_company_id", branch_id=str(branch_id)
            )
            return 0

        organization_id = branch.organization_id
        comments = await self.yclients.get_comments(branch.yclients_company_id)

        inserted = 0
        skipped = 0
        pending_alerts: list[dict] = []
        alert_cutoff = datetime.now(UTC) - timedelta(hours=_FRESH_ALERT_HOURS)
        for comment in comments:
            # Only star reviews (1-5); ignore non-rating comments.
            if comment.rating < 1 or comment.rating > 5:
                continue

            try:
                async with self.db.begin_nested():
                    # Idempotency: skip comments we've already synced.
                    existing = await self.db.execute(
                        select(Review.id).where(
                            Review.organization_id == organization_id,
                            Review.yclients_comment_id == comment.id,
                        )
                    )
                    if existing.scalar_one_or_none() is not None:
                        continue

                    barber = await self._resolve_barber(comment.master_id, organization_id)
                    if barber is None:
                        skipped += 1
                        continue

                    # Resolve visit (and its client) from the linked record.
                    visit_id: uuid.UUID | None = None
                    client_id: uuid.UUID | None = None
                    if comment.record_id:
                        vres = await self.db.execute(
                            select(Visit.id, Visit.client_id).where(
                                Visit.yclients_record_id == comment.record_id,
                                Visit.organization_id == organization_id,
                            )
                        )
                        row = vres.first()
                        if row is not None:
                            visit_id, client_id = row

                    is_negative = comment.rating <= _NEGATIVE_RATING
                    review = Review(
                        id=uuid.uuid4(),
                        organization_id=organization_id,
                        branch_id=branch_id,
                        barber_id=barber.id,
                        visit_id=visit_id,
                        client_id=client_id,
                        rating=comment.rating,
                        comment=comment.text or None,
                        source="yclients",
                        status=ReviewStatus.NEW if is_negative else ReviewStatus.PROCESSED,
                        yclients_comment_id=comment.id,
                    )
                    # Use the YClients timestamp when present; otherwise leave it
                    # unset so the column's server_default (now()) applies.
                    created_at = parse_comment_date(comment.date)
                    if created_at is not None:
                        review.created_at = created_at
                    self.db.add(review)
                    inserted += 1

                    # Queue an alert only for genuinely fresh negatives.
                    if is_negative and created_at is not None and created_at >= alert_cutoff:
                        client_name = None
                        if client_id:
                            cres = await self.db.execute(
                                select(Client.name).where(Client.id == client_id)
                            )
                            client_name = cres.scalar_one_or_none()
                        pending_alerts.append(
                            {
                                "organization_id": str(organization_id),
                                "branch_name": branch.name,
                                "barber_name": barber.name,
                                "client_name": client_name,
                                "rating": comment.rating,
                                "comment": comment.text or None,
                                "created_at": created_at.isoformat(),
                                "review_id": str(review.id),
                                "branch_id": str(branch_id),
                            }
                        )
            except Exception:
                await logger.aexception("Error syncing review", comment_id=comment.id)

        await self.db.commit()

        # Dispatch Telegram alerts for committed fresh negatives (fire-and-forget).
        if pending_alerts:
            from app.tasks.notification_tasks import send_negative_review_alert

            for payload in pending_alerts:
                try:
                    send_negative_review_alert.delay(**payload)
                except Exception:
                    await logger.aexception(
                        "Failed to queue negative review alert",
                        review_id=payload["review_id"],
                    )

        await logger.ainfo(
            "Reviews synced",
            branch_id=str(branch_id),
            total=len(comments),
            inserted=inserted,
            skipped=skipped,
            alerts_queued=len(pending_alerts),
        )
        return inserted

    async def sync_staff(self, branch_id: uuid.UUID) -> int:
        """Sync staff members for a branch from YClients.

        Returns the number of staff synced.
        """
        result = await self.db.execute(select(Branch).where(Branch.id == branch_id))
        branch = result.scalar_one_or_none()
        if branch is None or branch.yclients_company_id is None:
            return 0

        organization_id = branch.organization_id
        staff_list = await self.yclients.get_staff(branch.yclients_company_id)

        synced = 0
        for staff in staff_list:
            try:
                await self._upsert_staff(staff, organization_id, branch_id)
                synced += 1
            except Exception:
                await logger.aexception("Error syncing staff", staff_id=staff.id)

        await self.db.commit()
        await logger.ainfo("Staff synced", branch_id=str(branch_id), synced=synced)
        return synced

    async def _upsert_staff(
        self,
        staff: YClientStaff,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID,
    ) -> None:
        """UPSERT a staff member as a User."""
        is_active = not bool(staff.fired)

        stmt = pg_insert(User).values(
            id=uuid.uuid4(),
            organization_id=organization_id,
            branch_id=branch_id,
            telegram_id=None,  # set when user authenticates via Telegram
            role=UserRole.BARBER,
            name=staff.name,
            yclients_staff_id=staff.id,
            is_active=is_active,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["yclients_staff_id", "organization_id"],
            set_={
                "name": stmt.excluded.name,
                "is_active": stmt.excluded.is_active,
                "branch_id": stmt.excluded.branch_id,
            },
        )
        await self.db.execute(stmt)

    async def sync_clients(
        self,
        organization_id: uuid.UUID,
        yclients_company_id: int,
        client_ids: list[int],
    ) -> int:
        """Sync specific clients by their YClients IDs.

        Returns the number of clients synced.
        """
        synced = 0
        for cid in client_ids:
            try:
                client_data = await self.yclients.get_client(yclients_company_id, cid)
                birthday = None
                if client_data.birth_date:
                    with contextlib.suppress(ValueError):
                        birthday = date.fromisoformat(client_data.birth_date)

                stmt = pg_insert(Client).values(
                    id=uuid.uuid4(),
                    organization_id=organization_id,
                    yclients_client_id=client_data.id,
                    name=client_data.name,
                    phone=client_data.phone,
                    birthday=birthday,
                    total_visits=client_data.visits_count,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["yclients_client_id", "organization_id"],
                    set_={
                        "name": stmt.excluded.name,
                        "phone": stmt.excluded.phone,
                        "birthday": stmt.excluded.birthday,
                        "total_visits": stmt.excluded.total_visits,
                    },
                )
                await self.db.execute(stmt)
                synced += 1
            except Exception:
                await logger.aexception("Error syncing client", client_id=cid)

        await self.db.commit()
        return synced

    async def process_single_record(
        self,
        company_id: int,
        record_id: int,
    ) -> bool:
        """Process a single record from a webhook event.

        Fetches the full record from YClients API, resolves all references,
        and upserts the visit.

        Returns True if the record was processed, False if skipped.
        """
        record = await self.yclients.get_record(company_id, record_id)

        branch = await self._resolve_branch(company_id)
        if branch is None:
            await logger.awarning(
                "Branch not found for record",
                yclients_company_id=company_id,
                record_id=record_id,
            )
            return False

        organization_id = branch.organization_id

        barber = await self._resolve_barber(record.staff_id, organization_id)
        if barber is None:
            await logger.awarning(
                "Barber not found for record",
                staff_id=record.staff_id,
                record_id=record_id,
            )
            return False

        client_id = None
        if record.client:
            client_id = await self._upsert_client(
                organization_id=organization_id,
                yclients_client_id=record.client.id,
                name=record.client.name,
                phone=record.client.phone,
            )

        extra_services = await self._get_extra_services(organization_id)

        visit_data = map_record_to_visit_dict(
            record=record,
            organization_id=organization_id,
            branch_id=branch.id,
            barber_id=barber.id,
            client_id=client_id,
            extra_services_list=extra_services,
        )
        await self._upsert_visit(visit_data)
        await self.db.commit()

        await logger.ainfo(
            "Single record processed",
            record_id=record_id,
            branch_id=str(branch.id),
            barber_id=str(barber.id),
            status=visit_data["status"],
            revenue=visit_data["revenue"],
        )
        return True

    async def initial_sync(self, org_id: uuid.UUID) -> None:
        """Perform initial data load for an organization.

        1. Sync staff for all branches
        2. Sync all visits for current month
        """
        result = await self.db.execute(
            select(Branch).where(Branch.organization_id == org_id, Branch.is_active.is_(True))
        )
        branches = result.scalars().all()

        today = date.today()
        month_start = today.replace(day=1)

        for branch in branches:
            await logger.ainfo(
                "Initial sync for branch", branch_id=str(branch.id), name=branch.name
            )
            await self.sync_staff(branch.id)
            await self.sync_records(branch.id, month_start, today)

        await logger.ainfo("Initial sync completed", org_id=str(org_id), branches=len(branches))
