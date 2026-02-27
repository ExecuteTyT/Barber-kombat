"""Tests for Reviews API endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.main import app
from app.models.review import ReviewStatus
from app.models.user import UserRole
from app.redis import get_redis

# --- Test constants ---

ORG_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()
BARBER_ID = uuid.uuid4()
REVIEW_ID = uuid.uuid4()
CLIENT_ID = uuid.uuid4()


# --- Helpers ---


def make_user(
    role: str = "chef",
    org_id: uuid.UUID = ORG_ID,
    branch_id: uuid.UUID = BRANCH_ID,
    user_id: uuid.UUID | None = None,
) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.organization_id = org_id
    user.branch_id = branch_id
    user.role = UserRole(role)
    user.name = "Test User"
    user.is_active = True
    return user


def make_branch(
    branch_id: uuid.UUID = BRANCH_ID,
    org_id: uuid.UUID = ORG_ID,
) -> MagicMock:
    branch = MagicMock()
    branch.id = branch_id
    branch.organization_id = org_id
    branch.name = "Test Branch"
    branch.is_active = True
    return branch


def make_barber(
    barber_id: uuid.UUID = BARBER_ID,
    name: str = "Pavel",
    org_id: uuid.UUID = ORG_ID,
    branch_id: uuid.UUID = BRANCH_ID,
) -> MagicMock:
    barber = MagicMock()
    barber.id = barber_id
    barber.name = name
    barber.organization_id = org_id
    barber.branch_id = branch_id
    barber.is_active = True
    barber.role = UserRole.BARBER
    return barber


def make_review_dict(
    review_id: uuid.UUID = REVIEW_ID,
    branch_id: uuid.UUID = BRANCH_ID,
    barber_id: uuid.UUID = BARBER_ID,
    rating: int = 2,
    status: str = "new",
) -> dict:
    """Create a formatted review dict as returned by ReviewService._format_review."""
    return {
        "id": review_id,
        "branch_id": branch_id,
        "barber_id": barber_id,
        "barber_name": "Pavel",
        "visit_id": None,
        "client_id": None,
        "client_name": None,
        "client_phone": None,
        "rating": rating,
        "comment": "Bad haircut",
        "source": "form",
        "status": status,
        "processed_by": None,
        "processed_comment": None,
        "processed_at": None,
        "created_at": datetime.now(UTC),
    }


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.clear()


# --- Tests: POST /reviews/submit (public, no auth) ---


class TestSubmitReview:
    @pytest.mark.asyncio
    async def test_submit_positive_review(self):
        """Public endpoint creates a review without auth."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Validate branch exists
        branch = make_branch()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        # Validate barber exists in branch
        barber = make_barber()
        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = barber

        mock_db.execute = AsyncMock(side_effect=[branch_result, barber_result])
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/reviews/submit",
                json={
                    "branch_id": str(BRANCH_ID),
                    "barber_id": str(BARBER_ID),
                    "rating": 5,
                    "comment": "Great!",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Спасибо за отзыв!"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_submit_review_branch_not_found(self):
        """Returns 404 when branch doesn't exist."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=branch_result)

        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/reviews/submit",
                json={
                    "branch_id": str(uuid.uuid4()),
                    "barber_id": str(BARBER_ID),
                    "rating": 4,
                },
            )

        assert response.status_code == 404
        assert "Branch not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_submit_review_barber_not_found(self):
        """Returns 404 when barber not in this branch."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        branch = make_branch()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(side_effect=[branch_result, barber_result])

        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/reviews/submit",
                json={
                    "branch_id": str(BRANCH_ID),
                    "barber_id": str(uuid.uuid4()),
                    "rating": 3,
                },
            )

        assert response.status_code == 404
        assert "Barber not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_submit_review_invalid_rating(self):
        """Returns 422 for out-of-range rating."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/reviews/submit",
                json={
                    "branch_id": str(BRANCH_ID),
                    "barber_id": str(BARBER_ID),
                    "rating": 0,
                },
            )

        assert response.status_code == 422


# --- Tests: GET /reviews/{branch_id} ---


class TestGetBranchReviews:
    @pytest.mark.asyncio
    async def test_chef_can_view_reviews(self):
        """Chef can view reviews for their branch."""
        user = make_user(role="chef")
        branch = make_branch()

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # _validate_branch
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        # get_branch_reviews: count + select + _format for each review
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1

        review_mock = MagicMock()
        review_mock.id = REVIEW_ID
        review_mock.branch_id = BRANCH_ID
        review_mock.barber_id = BARBER_ID
        review_mock.client_id = None
        review_mock.visit_id = None
        review_mock.rating = 2
        review_mock.comment = "Bad"
        review_mock.source = "form"
        review_mock.status = ReviewStatus.NEW
        review_mock.processed_by = None
        review_mock.processed_comment = None
        review_mock.processed_at = None
        review_mock.created_at = datetime.now(UTC)

        reviews_result = MagicMock()
        reviews_result.scalars.return_value.all.return_value = [review_mock]

        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = make_barber()

        mock_db.execute = AsyncMock(
            side_effect=[branch_result, count_result, reviews_result, barber_result]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/reviews/{BRANCH_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["reviews"]) == 1
        assert data["reviews"][0]["rating"] == 2

    @pytest.mark.asyncio
    async def test_barber_cannot_view_reviews(self):
        """Barbers don't have access to the reviews list."""
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/reviews/{BRANCH_ID}")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_branch_not_found_404(self):
        """Returns 404 when branch doesn't belong to user's org."""
        user = make_user(role="chef")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=branch_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/reviews/{uuid.uuid4()}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthenticated_401(self):
        """Returns 401/403 without authentication."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/reviews/{BRANCH_ID}")

        assert response.status_code in (401, 403)


# --- Tests: PUT /reviews/{review_id}/process ---


class TestProcessReview:
    @pytest.mark.asyncio
    async def test_chef_can_process_review(self):
        """Chef can process a review."""
        user = make_user(role="chef")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # process_review -> _get_review
        review_mock = MagicMock()
        review_mock.id = REVIEW_ID
        review_mock.organization_id = ORG_ID
        review_mock.branch_id = BRANCH_ID
        review_mock.barber_id = BARBER_ID
        review_mock.client_id = None
        review_mock.visit_id = None
        review_mock.rating = 2
        review_mock.comment = "Bad"
        review_mock.source = "form"
        review_mock.status = ReviewStatus.IN_PROGRESS
        review_mock.processed_by = user.id
        review_mock.processed_comment = "Called the client"
        review_mock.processed_at = None
        review_mock.created_at = datetime.now(UTC)

        review_result = MagicMock()
        review_result.scalar_one_or_none.return_value = review_mock

        # _format_review -> _get_user
        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = make_barber()

        mock_db.execute = AsyncMock(side_effect=[review_result, barber_result])
        mock_db.commit = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/reviews/{REVIEW_ID}/process",
                json={
                    "status": "in_progress",
                    "comment": "Called the client",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["barber_name"] == "Pavel"

    @pytest.mark.asyncio
    async def test_review_not_found_404(self):
        """Returns 404 when review doesn't exist."""
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        review_result = MagicMock()
        review_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=review_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/reviews/{uuid.uuid4()}/process",
                json={
                    "status": "processed",
                    "comment": "Done",
                },
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_barber_cannot_process(self):
        """Barbers cannot process reviews."""
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/reviews/{REVIEW_ID}/process",
                json={
                    "status": "in_progress",
                    "comment": "test",
                },
            )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_status_422(self):
        """Returns 422 for invalid status value."""
        user = make_user(role="chef")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/reviews/{REVIEW_ID}/process",
                json={
                    "status": "invalid_status",
                    "comment": "test",
                },
            )

        assert response.status_code == 422


# --- Tests: GET /reviews/alarum/feed ---


class TestGetAlarum:
    @pytest.mark.asyncio
    async def test_owner_sees_all_branches(self):
        """Owner sees alarum for all branches."""
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        review_mock = MagicMock()
        review_mock.id = REVIEW_ID
        review_mock.branch_id = BRANCH_ID
        review_mock.barber_id = BARBER_ID
        review_mock.client_id = None
        review_mock.visit_id = None
        review_mock.rating = 1
        review_mock.comment = "Terrible"
        review_mock.source = "form"
        review_mock.status = ReviewStatus.NEW
        review_mock.processed_by = None
        review_mock.processed_comment = None
        review_mock.processed_at = None
        review_mock.created_at = datetime.now(UTC)

        count_result = MagicMock()
        count_result.scalar_one.return_value = 1

        reviews_result = MagicMock()
        reviews_result.scalars.return_value.all.return_value = [review_mock]

        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = make_barber()

        mock_db.execute = AsyncMock(side_effect=[count_result, reviews_result, barber_result])

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/reviews/alarum/feed")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["reviews"]) == 1
        assert data["reviews"][0]["rating"] == 1

    @pytest.mark.asyncio
    async def test_barber_cannot_view_alarum(self):
        """Barbers cannot access the alarum feed."""
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/reviews/alarum/feed")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_alarum(self):
        """Returns empty alarum when no unprocessed reviews."""
        user = make_user(role="chef")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        reviews_result = MagicMock()
        reviews_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[count_result, reviews_result])

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/reviews/alarum/feed")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["reviews"] == []

    @pytest.mark.asyncio
    async def test_unauthenticated_401(self):
        """Returns 401/403 without authentication."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/reviews/alarum/feed")

        assert response.status_code in (401, 403)
