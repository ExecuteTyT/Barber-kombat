"""Tests for the Review service."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.review import ReviewStatus
from app.services.reviews import _NEGATIVE_THRESHOLD, _OVERDUE_HOURS, ReviewService

# --- Helpers ---

ORG_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()
BARBER_ID = uuid.uuid4()
CLIENT_ID = uuid.uuid4()
REVIEW_ID = uuid.uuid4()


def make_review(
    review_id: uuid.UUID = REVIEW_ID,
    org_id: uuid.UUID = ORG_ID,
    branch_id: uuid.UUID = BRANCH_ID,
    barber_id: uuid.UUID = BARBER_ID,
    client_id: uuid.UUID | None = None,
    rating: int = 3,
    comment: str | None = "Bad haircut",
    source: str = "form",
    status: ReviewStatus = ReviewStatus.NEW,
    processed_by: uuid.UUID | None = None,
    processed_comment: str | None = None,
    processed_at: datetime | None = None,
    created_at: datetime | None = None,
    visit_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock Review object."""
    review = MagicMock()
    review.id = review_id
    review.organization_id = org_id
    review.branch_id = branch_id
    review.barber_id = barber_id
    review.client_id = client_id
    review.visit_id = visit_id
    review.rating = rating
    review.comment = comment
    review.source = source
    review.status = status
    review.processed_by = processed_by
    review.processed_comment = processed_comment
    review.processed_at = processed_at
    review.created_at = created_at or datetime.now(UTC)
    return review


def make_barber(barber_id: uuid.UUID = BARBER_ID, name: str = "Pavel") -> MagicMock:
    barber = MagicMock()
    barber.id = barber_id
    barber.name = name
    return barber


def make_client(
    client_id: uuid.UUID = CLIENT_ID, name: str = "Ivan", phone: str = "+79001234567"
) -> MagicMock:
    client = MagicMock()
    client.id = client_id
    client.name = name
    client.phone = phone
    return client


def make_branch(branch_id: uuid.UUID = BRANCH_ID, name: str = "Main Branch") -> MagicMock:
    branch = MagicMock()
    branch.id = branch_id
    branch.name = name
    branch.organization_id = ORG_ID
    return branch


# --- Tests: create_review ---


class TestCreateReview:
    @pytest.mark.asyncio
    async def test_positive_review_saved_as_processed(self):
        """Ratings 4-5 are saved with PROCESSED status, no notification."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        service = ReviewService(db=mock_db, redis=mock_redis)

        await service.create_review(
            organization_id=ORG_ID,
            branch_id=BRANCH_ID,
            barber_id=BARBER_ID,
            rating=5,
            comment="Great!",
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

        added_review = mock_db.add.call_args[0][0]
        assert added_review.status == ReviewStatus.PROCESSED
        assert added_review.rating == 5

        # No notification for positive review
        mock_redis.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_negative_review_saved_as_new(self):
        """Ratings 1-3 are saved with NEW status and trigger notification."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        service = ReviewService(db=mock_db, redis=mock_redis)

        # Mock the helper methods called by _publish_new_review
        barber = make_barber()
        branch = make_branch()
        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = barber
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        mock_db.execute = AsyncMock(side_effect=[barber_result, branch_result])

        await service.create_review(
            organization_id=ORG_ID,
            branch_id=BRANCH_ID,
            barber_id=BARBER_ID,
            rating=2,
            comment="Terrible",
        )

        added_review = mock_db.add.call_args[0][0]
        assert added_review.status == ReviewStatus.NEW
        assert added_review.rating == 2

        # Notification sent for negative review
        mock_redis.publish.assert_called_once()
        channel = mock_redis.publish.call_args[0][0]
        payload = json.loads(mock_redis.publish.call_args[0][1])
        assert channel == f"ws:org:{ORG_ID}"
        assert payload["type"] == "new_review"
        assert payload["review"]["rating"] == 2

    @pytest.mark.asyncio
    async def test_threshold_boundary_rating_3(self):
        """Rating exactly at threshold (3) is treated as negative."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        service = ReviewService(db=mock_db, redis=mock_redis)

        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = make_barber()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = make_branch()
        mock_db.execute = AsyncMock(side_effect=[barber_result, branch_result])

        await service.create_review(
            organization_id=ORG_ID,
            branch_id=BRANCH_ID,
            barber_id=BARBER_ID,
            rating=3,
        )

        added_review = mock_db.add.call_args[0][0]
        assert added_review.status == ReviewStatus.NEW
        mock_redis.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_threshold_boundary_rating_4(self):
        """Rating 4 is treated as positive (above threshold)."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        service = ReviewService(db=mock_db, redis=mock_redis)

        await service.create_review(
            organization_id=ORG_ID,
            branch_id=BRANCH_ID,
            barber_id=BARBER_ID,
            rating=4,
        )

        added_review = mock_db.add.call_args[0][0]
        assert added_review.status == ReviewStatus.PROCESSED
        mock_redis.publish.assert_not_called()


# --- Tests: process_review ---


class TestProcessReview:
    @pytest.mark.asyncio
    async def test_process_review_in_progress(self):
        """Review can be set to in_progress status."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        review = make_review(status=ReviewStatus.NEW)
        result = MagicMock()
        result.scalar_one_or_none.return_value = review
        mock_db.execute = AsyncMock(return_value=result)

        user_id = uuid.uuid4()
        service = ReviewService(db=mock_db, redis=mock_redis)
        processed = await service.process_review(
            review_id=REVIEW_ID,
            organization_id=ORG_ID,
            processed_by=user_id,
            status="in_progress",
            comment="Working on it",
        )

        assert processed is not None
        assert processed.processed_by == user_id
        assert processed.processed_comment == "Working on it"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_review_processed_sets_timestamp(self):
        """Setting status to 'processed' also sets processed_at."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        review = make_review(status=ReviewStatus.IN_PROGRESS)
        result = MagicMock()
        result.scalar_one_or_none.return_value = review
        mock_db.execute = AsyncMock(return_value=result)

        user_id = uuid.uuid4()
        service = ReviewService(db=mock_db, redis=mock_redis)
        processed = await service.process_review(
            review_id=REVIEW_ID,
            organization_id=ORG_ID,
            processed_by=user_id,
            status="processed",
            comment="Resolved with client",
        )

        assert processed is not None
        assert processed.processed_at is not None

    @pytest.mark.asyncio
    async def test_process_review_not_found(self):
        """Returns None when review doesn't exist."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        service = ReviewService(db=mock_db, redis=mock_redis)
        processed = await service.process_review(
            review_id=uuid.uuid4(),
            organization_id=ORG_ID,
            processed_by=uuid.uuid4(),
            status="in_progress",
            comment="test",
        )

        assert processed is None
        mock_db.commit.assert_not_awaited()


# --- Tests: get_branch_reviews ---


class TestGetBranchReviews:
    @pytest.mark.asyncio
    async def test_returns_paginated_reviews(self):
        """Returns formatted reviews with total count."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        review1 = make_review(rating=2)
        review2 = make_review(review_id=uuid.uuid4(), rating=5, status=ReviewStatus.PROCESSED)

        # Count query
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2

        # Select query
        reviews_result = MagicMock()
        reviews_result.scalars.return_value.all.return_value = [review1, review2]

        # _format_review calls for each review: _get_user, _get_client (if client_id)
        barber_result1 = MagicMock()
        barber_result1.scalar_one_or_none.return_value = make_barber()
        barber_result2 = MagicMock()
        barber_result2.scalar_one_or_none.return_value = make_barber()

        mock_db.execute = AsyncMock(
            side_effect=[count_result, reviews_result, barber_result1, barber_result2]
        )

        service = ReviewService(db=mock_db, redis=mock_redis)
        reviews, total = await service.get_branch_reviews(
            branch_id=BRANCH_ID,
            organization_id=ORG_ID,
        )

        assert total == 2
        assert len(reviews) == 2
        assert reviews[0]["rating"] == 2
        assert reviews[0]["barber_name"] == "Pavel"

    @pytest.mark.asyncio
    async def test_empty_results(self):
        """Returns empty list when no reviews match."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        reviews_result = MagicMock()
        reviews_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[count_result, reviews_result])

        service = ReviewService(db=mock_db, redis=mock_redis)
        reviews, total = await service.get_branch_reviews(
            branch_id=BRANCH_ID,
            organization_id=ORG_ID,
        )

        assert total == 0
        assert reviews == []


# --- Tests: get_alarum ---


class TestGetAlarum:
    @pytest.mark.asyncio
    async def test_returns_unprocessed_negative_reviews(self):
        """Alarum returns negative reviews with NEW or IN_PROGRESS status."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        review = make_review(rating=1, status=ReviewStatus.NEW)

        count_result = MagicMock()
        count_result.scalar_one.return_value = 1

        reviews_result = MagicMock()
        reviews_result.scalars.return_value.all.return_value = [review]

        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = make_barber()

        mock_db.execute = AsyncMock(side_effect=[count_result, reviews_result, barber_result])

        service = ReviewService(db=mock_db, redis=mock_redis)
        reviews, total = await service.get_alarum(organization_id=ORG_ID)

        assert total == 1
        assert len(reviews) == 1
        assert reviews[0]["rating"] == 1

    @pytest.mark.asyncio
    async def test_alarum_with_branch_filter(self):
        """Alarum can be filtered to a specific branch (for chef role)."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        reviews_result = MagicMock()
        reviews_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[count_result, reviews_result])

        service = ReviewService(db=mock_db, redis=mock_redis)
        reviews, total = await service.get_alarum(
            organization_id=ORG_ID,
            branch_id=BRANCH_ID,
        )

        assert total == 0
        assert reviews == []
        # Verify execute was called (conditions included branch_id)
        assert mock_db.execute.call_count == 2


# --- Tests: get_overdue_reviews ---


class TestGetOverdueReviews:
    @pytest.mark.asyncio
    async def test_finds_overdue_reviews(self):
        """Finds reviews older than _OVERDUE_HOURS that are still NEW."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        old_review = make_review(
            created_at=datetime.now(UTC) - timedelta(hours=3),
            status=ReviewStatus.NEW,
            rating=2,
        )

        result = MagicMock()
        result.scalars.return_value.all.return_value = [old_review]
        mock_db.execute = AsyncMock(return_value=result)

        service = ReviewService(db=mock_db, redis=mock_redis)
        overdue = await service.get_overdue_reviews()

        assert len(overdue) == 1
        assert overdue[0].rating == 2

    @pytest.mark.asyncio
    async def test_no_overdue_reviews(self):
        """Returns empty list when no reviews are overdue."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=result)

        service = ReviewService(db=mock_db, redis=mock_redis)
        overdue = await service.get_overdue_reviews()

        assert overdue == []


# --- Tests: send_overdue_reminders ---


class TestSendOverdueReminders:
    @pytest.mark.asyncio
    async def test_sends_reminders_for_overdue(self):
        """Publishes reminder for each overdue review."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        old_review = make_review(
            created_at=datetime.now(UTC) - timedelta(hours=4),
            status=ReviewStatus.NEW,
            rating=1,
        )

        # get_overdue_reviews query
        overdue_result = MagicMock()
        overdue_result.scalars.return_value.all.return_value = [old_review]

        # _publish_overdue_reminder -> _get_user, _get_branch
        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = make_barber()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = make_branch()

        mock_db.execute = AsyncMock(side_effect=[overdue_result, barber_result, branch_result])

        service = ReviewService(db=mock_db, redis=mock_redis)
        sent = await service.send_overdue_reminders()

        assert sent == 1
        mock_redis.publish.assert_called_once()
        payload = json.loads(mock_redis.publish.call_args[0][1])
        assert payload["type"] == "review_overdue"
        assert payload["rating"] == 1

    @pytest.mark.asyncio
    async def test_no_reminders_when_none_overdue(self):
        """Returns 0 when no overdue reviews exist."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        overdue_result = MagicMock()
        overdue_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=overdue_result)

        service = ReviewService(db=mock_db, redis=mock_redis)
        sent = await service.send_overdue_reminders()

        assert sent == 0
        mock_redis.publish.assert_not_called()


# --- Tests: _format_review ---


class TestFormatReview:
    @pytest.mark.asyncio
    async def test_format_with_barber_and_client(self):
        """Formats a review resolving barber and client names."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        review = make_review(client_id=CLIENT_ID)

        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = make_barber()
        client_result = MagicMock()
        client_result.scalar_one_or_none.return_value = make_client()

        mock_db.execute = AsyncMock(side_effect=[barber_result, client_result])

        service = ReviewService(db=mock_db, redis=mock_redis)
        formatted = await service._format_review(review)

        assert formatted["barber_name"] == "Pavel"
        assert formatted["client_name"] == "Ivan"
        assert formatted["client_phone"] == "+79001234567"
        assert formatted["rating"] == 3
        assert formatted["status"] == "new"

    @pytest.mark.asyncio
    async def test_format_without_client(self):
        """Formats a review without client info."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        review = make_review(client_id=None)

        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = make_barber()

        mock_db.execute = AsyncMock(return_value=barber_result)

        service = ReviewService(db=mock_db, redis=mock_redis)
        formatted = await service._format_review(review)

        assert formatted["barber_name"] == "Pavel"
        assert formatted["client_name"] is None
        assert formatted["client_phone"] is None

    @pytest.mark.asyncio
    async def test_format_unknown_barber(self):
        """Formats a review with missing barber as 'Unknown'."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        review = make_review(client_id=None)

        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(return_value=barber_result)

        service = ReviewService(db=mock_db, redis=mock_redis)
        formatted = await service._format_review(review)

        assert formatted["barber_name"] == "Unknown"


# --- Tests: _publish_new_review ---


class TestPublishNewReview:
    @pytest.mark.asyncio
    async def test_publishes_correct_payload(self):
        """New review notification contains all required fields."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        review = make_review(rating=1, comment="Awful!")

        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = make_barber()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = make_branch()

        mock_db.execute = AsyncMock(side_effect=[barber_result, branch_result])

        service = ReviewService(db=mock_db, redis=mock_redis)
        await service._publish_new_review(review)

        mock_redis.publish.assert_called_once()
        channel, payload_str = mock_redis.publish.call_args[0]
        assert channel == f"ws:org:{ORG_ID}"

        payload = json.loads(payload_str)
        assert payload["type"] == "new_review"
        assert payload["branch_id"] == str(BRANCH_ID)
        assert payload["review"]["barber_name"] == "Pavel"
        assert payload["review"]["branch_name"] == "Main Branch"
        assert payload["review"]["rating"] == 1
        assert payload["review"]["comment"] == "Awful!"
        assert "timestamp" in payload

    @pytest.mark.asyncio
    async def test_publishes_with_client_info(self):
        """Notification includes client info when available."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        review = make_review(rating=2, client_id=CLIENT_ID)

        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = make_barber()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = make_branch()
        client_result = MagicMock()
        client_result.scalar_one_or_none.return_value = make_client()

        mock_db.execute = AsyncMock(side_effect=[barber_result, branch_result, client_result])

        service = ReviewService(db=mock_db, redis=mock_redis)
        await service._publish_new_review(review)

        payload = json.loads(mock_redis.publish.call_args[0][1])
        assert payload["review"]["client_name"] == "Ivan"
        assert payload["review"]["client_phone"] == "+79001234567"


# --- Tests: constants ---


class TestConstants:
    def test_negative_threshold(self):
        assert _NEGATIVE_THRESHOLD == 3

    def test_overdue_hours(self):
        assert _OVERDUE_HOURS == 2
