"""Reviews API endpoints.

Includes a public endpoint for review submission (no auth)
and protected endpoints for listing, processing, and alarum.
"""

import uuid
from datetime import date
from typing import Annotated

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.branch import Branch
from app.models.user import User, UserRole
from app.redis import get_redis
from app.schemas.reviews import (
    AlarumResponse,
    ReviewCreate,
    ReviewCreatedResponse,
    ReviewListResponse,
    ReviewProcessRequest,
    ReviewResponse,
)
from app.services.reviews import ReviewService

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/reviews", tags=["reviews"])


async def _validate_branch(
    branch_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> Branch:
    """Load and validate that a branch belongs to the organization."""
    result = await db.execute(
        select(Branch).where(
            Branch.id == branch_id,
            Branch.organization_id == org_id,
        )
    )
    branch = result.scalar_one_or_none()
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found",
        )
    return branch


# --- Public endpoints (no auth) ---


@router.get("/info")
async def get_review_info(
    branch: Annotated[uuid.UUID, Query()],
    barber: Annotated[uuid.UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return barber and branch display info for the public review form."""
    result = await db.execute(
        select(User).where(
            User.id == barber,
            User.branch_id == branch,
            User.role == UserRole.BARBER,
        )
    )
    barber_obj = result.scalar_one_or_none()
    if barber_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barber not found",
        )

    result = await db.execute(select(Branch).where(Branch.id == branch))
    branch_obj = result.scalar_one_or_none()
    if branch_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found",
        )

    return {
        "barber_name": barber_obj.name,
        "branch_name": branch_obj.name,
        "branch_address": branch_obj.address or "",
    }


@router.post("/submit", response_model=ReviewCreatedResponse, status_code=status.HTTP_201_CREATED)
async def submit_review(
    body: ReviewCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Submit a review from the public form. No authentication required.

    The branch must exist, and the barber must belong to that branch.
    """
    # Validate branch exists
    result = await db.execute(select(Branch).where(Branch.id == body.branch_id))
    branch = result.scalar_one_or_none()
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found",
        )

    # Validate barber exists and belongs to this branch
    result = await db.execute(
        select(User).where(
            User.id == body.barber_id,
            User.branch_id == body.branch_id,
            User.role == UserRole.BARBER,
        )
    )
    barber = result.scalar_one_or_none()
    if barber is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barber not found in this branch",
        )

    review_service = ReviewService(db=db, redis=redis)
    review = await review_service.create_review(
        organization_id=branch.organization_id,
        branch_id=body.branch_id,
        barber_id=body.barber_id,
        rating=body.rating,
        comment=body.comment,
        visit_id=body.visit_id,
        client_id=body.client_id,
        source=body.source,
    )

    return ReviewCreatedResponse(
        id=review.id,
        status=review.status.value,
        message="Спасибо за отзыв!",
    )


# --- Protected endpoints ---


@router.get("/{branch_id}", response_model=ReviewListResponse)
async def get_branch_reviews(
    branch_id: uuid.UUID,
    current_user: Annotated[
        User, Depends(require_role(UserRole.CHEF, UserRole.OWNER, UserRole.ADMIN))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    rating_max: Annotated[int | None, Query(ge=1, le=5)] = None,
    date_from: Annotated[date | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Get reviews for a branch with optional filters. Chef/owner/admin only."""
    await _validate_branch(branch_id, current_user.organization_id, db)

    review_service = ReviewService(db=db, redis=redis)
    reviews, total = await review_service.get_branch_reviews(
        branch_id=branch_id,
        organization_id=current_user.organization_id,
        status=status_filter,
        rating_max=rating_max,
        date_from=date_from,
        page=page,
        per_page=per_page,
    )

    return ReviewListResponse(
        reviews=[ReviewResponse(**r) for r in reviews],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.put("/{review_id}/process", response_model=ReviewResponse)
async def process_review(
    review_id: uuid.UUID,
    body: ReviewProcessRequest,
    current_user: Annotated[
        User, Depends(require_role(UserRole.CHEF, UserRole.OWNER, UserRole.ADMIN))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Process a review (change status, add comment). Chef/owner/admin only."""
    review_service = ReviewService(db=db, redis=redis)
    review = await review_service.process_review(
        review_id=review_id,
        organization_id=current_user.organization_id,
        processed_by=current_user.id,
        status=body.status,
        comment=body.comment,
    )

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )

    formatted = await review_service._format_review(review)
    return ReviewResponse(**formatted)


@router.get("/alarum/feed", response_model=AlarumResponse)
async def get_alarum(
    current_user: Annotated[
        User, Depends(require_role(UserRole.CHEF, UserRole.OWNER, UserRole.ADMIN))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Get alarum feed: unprocessed negative reviews.

    Owner/admin sees all branches. Chef sees only their branch.
    """
    # Chef only sees their branch
    branch_id = None
    if current_user.role == UserRole.CHEF:
        branch_id = current_user.branch_id

    review_service = ReviewService(db=db, redis=redis)
    reviews, total = await review_service.get_alarum(
        organization_id=current_user.organization_id,
        branch_id=branch_id,
    )

    return AlarumResponse(
        reviews=[ReviewResponse(**r) for r in reviews],
        total=total,
    )
