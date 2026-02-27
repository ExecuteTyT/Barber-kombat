"""Plans (revenue targets) API endpoints."""

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
from app.schemas.plans import (
    PlanCreate,
    PlanNetworkEntry,
    PlanNetworkResponse,
    PlanResponse,
)
from app.services.plans import PlanService

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/plans", tags=["plans"])


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


@router.get("/{branch_id}", response_model=PlanResponse)
async def get_branch_plan(
    branch_id: uuid.UUID,
    current_user: Annotated[
        User, Depends(require_role(UserRole.CHEF, UserRole.OWNER, UserRole.ADMIN))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    month: Annotated[date | None, Query(description="First day of month, e.g. 2024-10-01")] = None,
):
    """Get plan for a branch. Chef, owner, admin only."""
    await _validate_branch(branch_id, current_user.organization_id, db)

    plan_service = PlanService(db=db, redis=redis)
    data = await plan_service.get_plan_with_details(branch_id, current_user.organization_id, month)

    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found for this branch/month",
        )

    return PlanResponse(**data)


@router.put("/{branch_id}", response_model=PlanResponse)
async def upsert_branch_plan(
    branch_id: uuid.UUID,
    body: PlanCreate,
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Create or update a plan for a branch. Owner/admin only."""
    await _validate_branch(branch_id, current_user.organization_id, db)

    plan_service = PlanService(db=db, redis=redis)
    await plan_service.upsert_plan(
        organization_id=current_user.organization_id,
        branch_id=branch_id,
        month=body.month,
        target_amount=body.target_amount,
    )

    data = await plan_service.get_plan_with_details(
        branch_id, current_user.organization_id, body.month
    )

    return PlanResponse(**data)


@router.get("/network/all", response_model=PlanNetworkResponse)
async def get_network_plans(
    current_user: Annotated[User, Depends(require_role(UserRole.OWNER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    month: Annotated[date | None, Query(description="First day of month, e.g. 2024-10-01")] = None,
):
    """Get plans for all branches in the network. Owner/admin only."""
    plan_service = PlanService(db=db, redis=redis)
    data = await plan_service.get_network_plans(current_user.organization_id, month)

    return PlanNetworkResponse(
        month=data["month"],
        plans=[PlanNetworkEntry(**p) for p in data["plans"]],
        total_target=data["total_target"],
        total_current=data["total_current"],
        total_percentage=data["total_percentage"],
    )
