"""Review Service — creation, routing, processing, and alarum feed.

Handles customer feedback: saves reviews, routes negatives to alarum,
publishes WebSocket notifications, and checks for overdue reviews.
"""

import json
import uuid
from datetime import UTC, date, datetime, timedelta

import redis.asyncio as aioredis
import structlog
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.client import Client
from app.models.review import Review, ReviewStatus
from app.models.user import User

logger = structlog.stdlib.get_logger()

# Reviews with rating <= this threshold are considered negative.
_NEGATIVE_THRESHOLD = 3

# Unprocessed reviews older than this trigger a reminder.
_OVERDUE_HOURS = 2


class ReviewService:
    """Manages review lifecycle: creation, routing, processing."""

    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self.db = db
        self.redis = redis

    # --- Create ---

    async def create_review(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID,
        barber_id: uuid.UUID,
        rating: int,
        comment: str | None = None,
        visit_id: uuid.UUID | None = None,
        client_id: uuid.UUID | None = None,
        source: str = "form",
    ) -> Review:
        """Create a new review and route it based on rating.

        Positive (4-5): saved silently, used in barber rating.
        Negative (1-3): saved as 'new', triggers alarum notification.
        """
        review = Review(
            id=uuid.uuid4(),
            organization_id=organization_id,
            branch_id=branch_id,
            barber_id=barber_id,
            visit_id=visit_id,
            client_id=client_id,
            rating=rating,
            comment=comment,
            source=source,
            status=ReviewStatus.NEW if rating <= _NEGATIVE_THRESHOLD else ReviewStatus.PROCESSED,
        )
        self.db.add(review)
        await self.db.commit()
        await self.db.refresh(review)

        # Route negative reviews
        if rating <= _NEGATIVE_THRESHOLD:
            await self._publish_new_review(review)

        await logger.ainfo(
            "Review created",
            review_id=str(review.id),
            branch_id=str(branch_id),
            barber_id=str(barber_id),
            rating=rating,
            is_negative=rating <= _NEGATIVE_THRESHOLD,
        )

        return review

    # --- Process ---

    async def process_review(
        self,
        review_id: uuid.UUID,
        organization_id: uuid.UUID,
        processed_by: uuid.UUID,
        status: str,
        comment: str,
    ) -> Review | None:
        """Update a review's processing status.

        Transitions: new -> in_progress -> processed
        """
        review = await self._get_review(review_id, organization_id)
        if review is None:
            return None

        review.status = ReviewStatus(status)
        review.processed_by = processed_by
        review.processed_comment = comment
        if status == ReviewStatus.PROCESSED:
            review.processed_at = datetime.now(UTC)

        await self.db.commit()

        await logger.ainfo(
            "Review processed",
            review_id=str(review_id),
            new_status=status,
            processed_by=str(processed_by),
        )

        return review

    # --- Query ---

    async def get_branch_reviews(
        self,
        branch_id: uuid.UUID,
        organization_id: uuid.UUID,
        status: str | None = None,
        rating_max: int | None = None,
        date_from: date | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[dict], int]:
        """Get paginated reviews for a branch with optional filters.

        Returns (reviews_list, total_count).
        """
        conditions = [
            Review.branch_id == branch_id,
            Review.organization_id == organization_id,
        ]
        if status:
            conditions.append(Review.status == ReviewStatus(status))
        if rating_max is not None:
            conditions.append(Review.rating <= rating_max)
        if date_from:
            conditions.append(Review.created_at >= datetime.combine(date_from, datetime.min.time()))

        # Count
        count_stmt = select(sa_func.count(Review.id)).where(*conditions)
        total = (await self.db.execute(count_stmt)).scalar_one()

        # Fetch paginated
        offset = (page - 1) * per_page
        stmt = (
            select(Review)
            .where(*conditions)
            .order_by(Review.created_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        result = await self.db.execute(stmt)
        reviews = result.scalars().all()

        formatted = []
        for review in reviews:
            formatted.append(await self._format_review(review))

        return formatted, total

    async def get_alarum(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
    ) -> tuple[list[dict], int]:
        """Get unprocessed negative reviews (alarum feed).

        Owner sees all branches; chef sees only their branch.
        """
        conditions = [
            Review.organization_id == organization_id,
            Review.rating <= _NEGATIVE_THRESHOLD,
            Review.status.in_([ReviewStatus.NEW, ReviewStatus.IN_PROGRESS]),
        ]
        if branch_id is not None:
            conditions.append(Review.branch_id == branch_id)

        count_stmt = select(sa_func.count(Review.id)).where(*conditions)
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = (
            select(Review)
            .where(*conditions)
            .order_by(Review.created_at.desc())
        )
        result = await self.db.execute(stmt)
        reviews = result.scalars().all()

        formatted = []
        for review in reviews:
            formatted.append(await self._format_review(review))

        return formatted, total

    # --- Overdue check ---

    async def get_overdue_reviews(
        self,
        organization_id: uuid.UUID | None = None,
    ) -> list[Review]:
        """Find unprocessed negative reviews older than 2 hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=_OVERDUE_HOURS)

        conditions = [
            Review.status == ReviewStatus.NEW,
            Review.rating <= _NEGATIVE_THRESHOLD,
            Review.created_at < cutoff,
        ]
        if organization_id is not None:
            conditions.append(Review.organization_id == organization_id)

        result = await self.db.execute(
            select(Review).where(*conditions).order_by(Review.created_at.asc())
        )
        return list(result.scalars().all())

    async def send_overdue_reminders(self) -> int:
        """Find and send reminders for all overdue reviews.

        Returns the number of reminders sent.
        """
        overdue = await self.get_overdue_reviews()

        sent = 0
        for review in overdue:
            try:
                await self._publish_overdue_reminder(review)
                sent += 1
            except Exception:
                await logger.aexception(
                    "Failed to send overdue reminder",
                    review_id=str(review.id),
                )

        if sent > 0:
            await logger.awarning(
                "Overdue review reminders sent",
                total=sent,
            )

        return sent

    # --- Private helpers ---

    async def _get_review(
        self,
        review_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Review | None:
        """Load a review by ID within an organization."""
        result = await self.db.execute(
            select(Review).where(
                Review.id == review_id,
                Review.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def _format_review(self, review: Review) -> dict:
        """Format a review for the API response, resolving barber/client names."""
        barber_name = "Unknown"
        barber = await self._get_user(review.barber_id)
        if barber:
            barber_name = barber.name

        client_name = None
        client_phone = None
        if review.client_id:
            client = await self._get_client(review.client_id)
            if client:
                client_name = client.name
                client_phone = client.phone

        return {
            "id": review.id,
            "branch_id": review.branch_id,
            "barber_id": review.barber_id,
            "barber_name": barber_name,
            "visit_id": review.visit_id,
            "client_id": review.client_id,
            "client_name": client_name,
            "client_phone": client_phone,
            "rating": review.rating,
            "comment": review.comment,
            "source": review.source,
            "status": review.status.value if isinstance(review.status, ReviewStatus) else review.status,
            "processed_by": review.processed_by,
            "processed_comment": review.processed_comment,
            "processed_at": review.processed_at,
            "created_at": review.created_at,
        }

    async def _get_user(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def _get_client(self, client_id: uuid.UUID) -> Client | None:
        result = await self.db.execute(select(Client).where(Client.id == client_id))
        return result.scalar_one_or_none()

    async def _publish_new_review(self, review: Review) -> None:
        """Publish new_review event via Redis Pub/Sub for alarum."""
        barber = await self._get_user(review.barber_id)
        barber_name = barber.name if barber else "Unknown"

        branch = await self._get_branch(review.branch_id)
        branch_name = branch.name if branch else "Unknown"

        client_name = None
        client_phone = None
        if review.client_id:
            client = await self._get_client(review.client_id)
            if client:
                client_name = client.name
                client_phone = client.phone

        payload = {
            "type": "new_review",
            "branch_id": str(review.branch_id),
            "review": {
                "id": str(review.id),
                "branch_name": branch_name,
                "barber_name": barber_name,
                "client_name": client_name,
                "client_phone": client_phone,
                "rating": review.rating,
                "comment": review.comment,
                "created_at": review.created_at.isoformat() if review.created_at else None,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self.redis.publish(
            f"ws:org:{review.organization_id}",
            json.dumps(payload),
        )
        await logger.ainfo(
            "New review notification sent",
            review_id=str(review.id),
            rating=review.rating,
            branch_name=branch_name,
            barber_name=barber_name,
        )

    async def _publish_overdue_reminder(self, review: Review) -> None:
        """Publish reminder for an overdue unprocessed review."""
        barber = await self._get_user(review.barber_id)
        barber_name = barber.name if barber else "Unknown"

        branch = await self._get_branch(review.branch_id)
        branch_name = branch.name if branch else "Unknown"

        hours_ago = (datetime.now(UTC) - review.created_at).total_seconds() / 3600

        payload = {
            "type": "review_overdue",
            "branch_id": str(review.branch_id),
            "review_id": str(review.id),
            "branch_name": branch_name,
            "barber_name": barber_name,
            "rating": review.rating,
            "hours_overdue": round(hours_ago, 1),
            "message": (
                f"Необработанный отзыв ({review.rating}/5) "
                f"в филиале {branch_name} уже {hours_ago:.0f}ч!"
            ),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self.redis.publish(
            f"ws:org:{review.organization_id}",
            json.dumps(payload),
        )

    async def _get_branch(self, branch_id: uuid.UUID) -> Branch | None:
        result = await self.db.execute(select(Branch).where(Branch.id == branch_id))
        return result.scalar_one_or_none()
