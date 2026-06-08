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

from app.auth.dependencies import require_branch_access
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.admin import (
    AdminHistoryResponse,
    AdminMetricsResponse,
    AdminTasksResponse,
    CallListResponse,
    ConfirmRequest,
    MarkCallRequest,
)
from app.services.admin import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics/{branch_id}", response_model=AdminMetricsResponse)
async def get_admin_metrics(
    branch_id: uuid.UUID,
    current_user: Annotated[
        User,
        Depends(require_branch_access(UserRole.ADMIN, UserRole.OWNER)),
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
        Depends(require_branch_access(UserRole.ADMIN, UserRole.OWNER)),
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
        Depends(require_branch_access(UserRole.ADMIN, UserRole.OWNER)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Confirm pending visit records."""
    service = AdminService(db=db)
    count = await service.confirm_records(branch_id, body.record_ids)
    return {"confirmed": count}


@router.get("/calls/{branch_id}", response_model=CallListResponse)
async def get_admin_calls(
    branch_id: uuid.UUID,
    current_user: Annotated[
        User,
        Depends(require_branch_access(UserRole.ADMIN, UserRole.OWNER)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    target_date: Annotated[
        date | None, Query(description="Working date (defaults to today)")
    ] = None,
):
    """Upcoming appointments to confirm + confirmation/call stats for a branch."""
    service = AdminService(db=db)
    return await service.get_call_list(branch_id, target_date or date.today())


@router.post("/calls/{branch_id}/mark")
async def mark_admin_call(
    branch_id: uuid.UUID,
    body: MarkCallRequest,
    current_user: Annotated[
        User,
        Depends(require_branch_access(UserRole.ADMIN, UserRole.OWNER)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Log that the admin called about an upcoming appointment."""
    service = AdminService(db=db)
    await service.mark_call(
        organization_id=current_user.organization_id,
        branch_id=branch_id,
        admin_id=current_user.id,
        yclients_record_id=body.yclients_record_id,
        result=body.result,
        call_date=date.today(),
    )
    return {"ok": True}


@router.get("/history/{branch_id}", response_model=AdminHistoryResponse)
async def get_admin_history(
    branch_id: uuid.UUID,
    current_user: Annotated[
        User,
        Depends(require_branch_access(UserRole.ADMIN, UserRole.OWNER)),
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
