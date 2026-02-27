"""PVR (Premium for High Results) API endpoints."""

import uuid
from datetime import date
from typing import Annotated

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.branch import Branch
from app.models.user import User, UserRole
from app.redis import get_redis
from app.schemas.pvr import (
    BarberPVRResponse,
    BranchPVRResponse,
    ThresholdEntry,
    ThresholdsResponse,
)
from app.services.pvr import PVRService

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/pvr", tags=["pvr"])


async def _validate_branch(
    branch_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> Branch:
    """Load and validate that a branch belongs to the user's organization."""
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


@router.get("/{branch_id}/current", response_model=BranchPVRResponse)
async def get_branch_pvr(
    branch_id: uuid.UUID,
    current_user: Annotated[
        User, Depends(require_role(UserRole.CHEF, UserRole.OWNER, UserRole.ADMIN))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Get PVR for all barbers in a branch. Chef, owner, admin only."""
    await _validate_branch(branch_id, current_user.organization_id, db)

    pvr_service = PVRService(db=db, redis=redis)
    barbers_data = await pvr_service.get_branch_pvr(
        branch_id, current_user.organization_id
    )

    today = date.today()
    month_label = f"{today.year}-{today.month:02d}"

    return BranchPVRResponse(
        branch_id=branch_id,
        month=month_label,
        barbers=[BarberPVRResponse(**b) for b in barbers_data],
    )


@router.get("/barber/{barber_id}", response_model=BarberPVRResponse)
async def get_barber_pvr(
    barber_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Get PVR for a single barber. Barbers can only see themselves."""
    # Barber can only see own PVR
    if current_user.role == UserRole.BARBER and current_user.id != barber_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Barbers can only view their own PVR",
        )

    # Validate barber belongs to user's org
    result = await db.execute(
        select(User).where(
            User.id == barber_id,
            User.organization_id == current_user.organization_id,
        )
    )
    barber = result.scalar_one_or_none()
    if barber is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barber not found",
        )

    pvr_service = PVRService(db=db, redis=redis)
    data = await pvr_service.get_barber_pvr(
        barber_id, current_user.organization_id
    )

    return BarberPVRResponse(**data)


@router.get("/thresholds", response_model=ThresholdsResponse)
async def get_thresholds(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Get PVR threshold configuration for the current organization."""
    pvr_service = PVRService(db=db, redis=redis)

    thresholds = await pvr_service.get_thresholds(current_user.organization_id)
    config = await pvr_service._load_config(current_user.organization_id)

    return ThresholdsResponse(
        thresholds=[ThresholdEntry(**t) for t in thresholds],
        count_products=config.count_products if config else False,
        count_certificates=config.count_certificates if config else False,
    )
