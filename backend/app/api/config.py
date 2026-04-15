"""Configuration API endpoints.

Provides CRUD for rating weights, PVR thresholds, branches,
users, and notification configs. Most endpoints require OWNER or ADMIN role.
"""

import uuid
from typing import Annotated

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.redis import get_redis
from app.schemas.config import (
    BranchCreateRequest,
    BranchListResponse,
    BranchResponse,
    BranchUpdateRequest,
    NotificationConfigCreateRequest,
    NotificationConfigListResponse,
    NotificationConfigResponse,
    NotificationConfigUpdateRequest,
    PVRThresholdsRequest,
    PVRThresholdsResponse,
    RatingWeightsRequest,
    RatingWeightsResponse,
    ThresholdEntry,
    UserCreateRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.services.config import ConfigService

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/config", tags=["config"])

# Default values matching services/rating.py and services/pvr.py
_DEFAULT_RATING_WEIGHTS = {
    "revenue_weight": 20,
    "cs_weight": 20,
    "products_weight": 25,
    "extras_weight": 25,
    "reviews_weight": 10,
    "prize_gold_pct": 0.5,
    "prize_silver_pct": 0.3,
    "prize_bronze_pct": 0.1,
    "extra_services": None,
}

_DEFAULT_PVR_THRESHOLDS = {
    "thresholds": [
        {"score": 60, "bonus": 100_000_000},
        {"score": 75, "bonus": 200_000_000},
        {"score": 90, "bonus": 500_000_000},
    ],
    "count_products": False,
    "count_certificates": False,
    "min_visits_per_month": 0,
}


# --- Rating Weights ---


@router.get("/rating-weights", response_model=RatingWeightsResponse)
async def get_rating_weights(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Get current rating weights. Any authenticated user can read."""
    service = ConfigService(db=db, redis=redis)
    config = await service.get_rating_config(current_user.organization_id)

    if config is None:
        return RatingWeightsResponse(**_DEFAULT_RATING_WEIGHTS)

    return RatingWeightsResponse.model_validate(config)


@router.put("/rating-weights", response_model=RatingWeightsResponse)
async def update_rating_weights(
    body: RatingWeightsRequest,
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Update rating weights. Owner/admin only."""
    service = ConfigService(db=db, redis=redis)
    config = await service.upsert_rating_config(
        organization_id=current_user.organization_id,
        data=body.model_dump(),
    )
    return RatingWeightsResponse.model_validate(config)


# --- PVR Thresholds ---


@router.get("/pvr-thresholds", response_model=PVRThresholdsResponse)
async def get_pvr_thresholds(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Get current PVR thresholds. Any authenticated user can read."""
    service = ConfigService(db=db, redis=redis)
    config = await service.get_pvr_config(current_user.organization_id)

    if config is None:
        return PVRThresholdsResponse(**_DEFAULT_PVR_THRESHOLDS)

    raw = config.thresholds or _DEFAULT_PVR_THRESHOLDS["thresholds"]
    # Filter any stale legacy {amount,bonus} rows that may slip through.
    thresholds = [t for t in raw if "score" in t] or _DEFAULT_PVR_THRESHOLDS["thresholds"]
    return PVRThresholdsResponse(
        thresholds=[ThresholdEntry(**t) for t in sorted(thresholds, key=lambda x: x["score"])],
        count_products=config.count_products,
        count_certificates=config.count_certificates,
        min_visits_per_month=config.min_visits_per_month,
    )


@router.put("/pvr-thresholds", response_model=PVRThresholdsResponse)
async def update_pvr_thresholds(
    body: PVRThresholdsRequest,
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Update PVR thresholds. Owner/admin only."""
    service = ConfigService(db=db, redis=redis)
    config = await service.upsert_pvr_config(
        organization_id=current_user.organization_id,
        data={
            "thresholds": [t.model_dump() for t in body.thresholds],
            "count_products": body.count_products,
            "count_certificates": body.count_certificates,
            "min_visits_per_month": body.min_visits_per_month,
        },
    )

    thresholds = config.thresholds or []
    return PVRThresholdsResponse(
        thresholds=[ThresholdEntry(**t) for t in sorted(thresholds, key=lambda x: x["score"])],
        count_products=config.count_products,
        count_certificates=config.count_certificates,
        min_visits_per_month=config.min_visits_per_month,
    )


# --- Branches ---


@router.get("/branches", response_model=BranchListResponse)
async def list_branches(
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """List all branches. Owner/admin only."""
    service = ConfigService(db=db, redis=redis)
    branches = await service.list_branches(current_user.organization_id)
    return BranchListResponse(branches=[BranchResponse.model_validate(b) for b in branches])


@router.post(
    "/branches",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_branch(
    body: BranchCreateRequest,
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Create a new branch. Owner/admin only."""
    service = ConfigService(db=db, redis=redis)
    branch = await service.create_branch(
        organization_id=current_user.organization_id,
        data=body.model_dump(),
    )
    return BranchResponse.model_validate(branch)


@router.get("/branches/{branch_id}", response_model=BranchResponse)
async def get_branch(
    branch_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Get a single branch. Owner/admin only."""
    service = ConfigService(db=db, redis=redis)
    branch = await service.get_branch(current_user.organization_id, branch_id)
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found",
        )
    return BranchResponse.model_validate(branch)


@router.put("/branches/{branch_id}", response_model=BranchResponse)
async def update_branch(
    branch_id: uuid.UUID,
    body: BranchUpdateRequest,
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Update a branch. Owner/admin only."""
    service = ConfigService(db=db, redis=redis)
    branch = await service.update_branch(
        organization_id=current_user.organization_id,
        branch_id=branch_id,
        data=body.model_dump(exclude_unset=True),
    )
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found",
        )
    return BranchResponse.model_validate(branch)


# --- Users ---


@router.get("/users", response_model=UserListResponse)
async def list_users(
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    branch_id: Annotated[uuid.UUID | None, Query()] = None,
):
    """List users, optionally filtered by branch. Owner/admin only."""
    service = ConfigService(db=db, redis=redis)
    users = await service.list_users(current_user.organization_id, branch_id=branch_id)
    return UserListResponse(users=[UserResponse.model_validate(u) for u in users])


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    body: UserCreateRequest,
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Create a new user. Owner/admin only."""
    service = ConfigService(db=db, redis=redis)
    user = await service.create_user(
        organization_id=current_user.organization_id,
        data=body.model_dump(),
    )
    return UserResponse.model_validate(user)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Get a single user. Owner/admin only."""
    service = ConfigService(db=db, redis=redis)
    user = await service.get_user(current_user.organization_id, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Update a user. Owner/admin only."""
    service = ConfigService(db=db, redis=redis)
    user = await service.update_user(
        organization_id=current_user.organization_id,
        user_id=user_id,
        data=body.model_dump(exclude_unset=True),
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


# --- Notifications ---


@router.get("/notifications", response_model=NotificationConfigListResponse)
async def list_notifications(
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    branch_id: Annotated[uuid.UUID | None, Query()] = None,
):
    """List notification configs. Owner/admin only."""
    service = ConfigService(db=db, redis=redis)
    notifs = await service.list_notifications(current_user.organization_id, branch_id=branch_id)
    return NotificationConfigListResponse(
        notifications=[NotificationConfigResponse.model_validate(n) for n in notifs]
    )


@router.post(
    "/notifications",
    response_model=NotificationConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification(
    body: NotificationConfigCreateRequest,
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Create a notification config. Owner/admin only."""
    service = ConfigService(db=db, redis=redis)
    notif = await service.create_notification(
        organization_id=current_user.organization_id,
        data=body.model_dump(),
    )
    return NotificationConfigResponse.model_validate(notif)


@router.put(
    "/notifications/{notification_id}",
    response_model=NotificationConfigResponse,
)
async def update_notification(
    notification_id: uuid.UUID,
    body: NotificationConfigUpdateRequest,
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Update a notification config. Owner/admin only."""
    service = ConfigService(db=db, redis=redis)
    notif = await service.update_notification(
        organization_id=current_user.organization_id,
        notification_id=notification_id,
        data=body.model_dump(exclude_unset=True),
    )
    if notif is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification config not found",
        )
    return NotificationConfigResponse.model_validate(notif)


@router.delete(
    "/notifications/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_notification(
    notification_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Delete a notification config. Owner/admin only."""
    service = ConfigService(db=db, redis=redis)
    deleted = await service.delete_notification(current_user.organization_id, notification_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification config not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
