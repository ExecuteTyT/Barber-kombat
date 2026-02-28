"""Admin API endpoints.

Provides branch-level admin tools: metrics dashboard, task management
(unconfirmed records, unfilled birthdays, unprocessed checks), and
historical daily breakdowns.
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.admin import (
    AdminHistoryResponse,
    AdminMetricsResponse,
    AdminTasksResponse,
    ConfirmRequest,
)
from app.services.admin import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics/{branch_id}", response_model=AdminMetricsResponse)
async def get_admin_metrics(
    branch_id: uuid.UUID,
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    target_date: Annotated[
        date | None, Query(description="Report date (defaults to today)")
    ] = None,
):
    """Get daily admin metrics for a branch."""
    report_date = target_date or date.today()
    service = AdminService(db=db)
    return await service.get_metrics(branch_id, report_date)


@router.get("/tasks/{branch_id}", response_model=AdminTasksResponse)
async def get_admin_tasks(
    branch_id: uuid.UUID,
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get actionable tasks for a branch admin."""
    service = AdminService(db=db)
    return await service.get_tasks(branch_id, date.today())


@router.post("/tasks/{branch_id}/confirm")
async def confirm_records(
    branch_id: uuid.UUID,
    body: ConfirmRequest,
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Confirm pending visit records."""
    service = AdminService(db=db)
    count = await service.confirm_records(branch_id, body.record_ids)
    return {"confirmed": count}


@router.get("/history/{branch_id}", response_model=AdminHistoryResponse)
async def get_admin_history(
    branch_id: uuid.UUID,
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    month: Annotated[
        str | None,
        Query(description="Month in YYYY-MM format (defaults to current month)"),
    ] = None,
):
    """Get daily history for a branch in a given month."""
    if month:
        parts = month.split("-")
        year, mon = int(parts[0]), int(parts[1])
    else:
        today = date.today()
        year, mon = today.year, today.month

    service = AdminService(db=db)
    return await service.get_history(branch_id, year, mon)
