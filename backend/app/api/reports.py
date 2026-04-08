"""Report API endpoints.

Provides access to generated reports: daily revenue, day-to-day
comparison, client statistics, and Barber Kombat standings (bingo).
"""

import uuid
from datetime import date
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.reports import (
    BranchAnalytics,
    ClientsReport,
    DailyRevenueReport,
    DayToDayReport,
    KombatDailyReport,
    KombatMonthlyReport,
)
from app.services.reports import ReportService

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/reports", tags=["reports"])


# --- Revenue ---


@router.get("/revenue", response_model=DailyRevenueReport)
async def get_revenue_report(
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    target_date: Annotated[
        date | None, Query(description="Report date (defaults to today)")
    ] = None,
):
    """Get daily revenue report. Owner, admin only.

    Returns per-branch revenue for the requested day, month-to-date
    totals, plan progress, and network-wide aggregates.  If no stored
    report is found for the date the service generates one on-the-fly.
    """
    report_date = target_date or date.today()
    report_service = ReportService(db=db)

    report = await report_service.get_report(
        current_user.organization_id, "daily_revenue", report_date
    )
    if report and report.data:
        return DailyRevenueReport(**report.data)

    # Generate on-the-fly if not pre-generated
    data = await report_service.generate_daily_revenue(current_user.organization_id, report_date)
    return DailyRevenueReport(**data)


# --- Day-to-day ---


@router.get("/day-to-day", response_model=DayToDayReport)
async def get_day_to_day_report(
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    target_date: Annotated[
        date | None, Query(description="Report date (defaults to today)")
    ] = None,
    branch_id: Annotated[
        uuid.UUID | None, Query(description="Branch filter (null = entire network)")
    ] = None,
):
    """Get day-to-day month comparison report. Owner, admin only."""
    report_date = target_date or date.today()
    report_service = ReportService(db=db)

    # The scheduled day_to_day task only runs once a day (11:00 MSK), but
    # visits are synced every 10 minutes. For the current month we always
    # regenerate so the chart reflects the latest visits. Historical months
    # are served from cache.
    today = date.today()
    is_current_month = (
        report_date.year == today.year and report_date.month == today.month
    )
    if not is_current_month:
        report = await report_service.get_report(
            current_user.organization_id, "day_to_day", report_date, branch_id
        )
        if report and report.data:
            return DayToDayReport(**report.data)

    data = await report_service.generate_day_to_day(
        current_user.organization_id, report_date, branch_id
    )
    return DayToDayReport(**data)


# --- Clients ---


@router.get("/clients", response_model=ClientsReport)
async def get_clients_report(
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    target_date: Annotated[
        date | None, Query(description="Report date (defaults to today)")
    ] = None,
):
    """Get client statistics report (new vs returning). Owner, admin only."""
    report_date = target_date or date.today()
    report_service = ReportService(db=db)

    report = await report_service.get_report(current_user.organization_id, "clients", report_date)
    if report and report.data:
        try:
            return ClientsReport(**report.data)
        except Exception:
            pass  # Cached data has stale schema — regenerate below

    data = await report_service.generate_clients_report(current_user.organization_id, report_date)
    return ClientsReport(**data)


# --- Bingo (Kombat standings) ---


@router.get("/bingo", response_model=KombatDailyReport)
async def get_bingo_report(
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    target_date: Annotated[
        date | None, Query(description="Report date (defaults to today)")
    ] = None,
):
    """Get Barber Kombat daily standings (bingo view). Owner/admin only."""
    report_date = target_date or date.today()
    report_service = ReportService(db=db)

    report = await report_service.get_report(
        current_user.organization_id, "kombat_daily", report_date
    )
    if report and report.data:
        return KombatDailyReport(**report.data)

    data = await report_service.generate_kombat_daily(current_user.organization_id, report_date)
    return KombatDailyReport(**data)


# --- Kombat monthly ---


@router.get("/bingo/monthly", response_model=KombatMonthlyReport)
async def get_bingo_monthly_report(
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    month: Annotated[
        date | None, Query(description="Month (first day, defaults to current month)")
    ] = None,
):
    """Get Barber Kombat monthly summary. Owner/admin only."""
    month_start = (month or date.today()).replace(day=1)
    report_service = ReportService(db=db)

    report = await report_service.get_report(
        current_user.organization_id, "kombat_monthly", month_start
    )
    if report and report.data:
        return KombatMonthlyReport(**report.data)

    data = await report_service.generate_kombat_monthly(current_user.organization_id, month_start)
    return KombatMonthlyReport(**data)


# --- Branch analytics ---


@router.get("/branch-analytics/{branch_id}", response_model=BranchAnalytics)
async def get_branch_analytics(
    branch_id: uuid.UUID,
    current_user: Annotated[
        User,
        Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    target_date: Annotated[
        date | None, Query(description="Report date (defaults to today)")
    ] = None,
):
    """Get comprehensive branch analytics. Owner/admin only."""
    report_date = target_date or date.today()
    report_service = ReportService(db=db)
    data = await report_service.generate_branch_analytics(
        current_user.organization_id, branch_id, report_date
    )
    return BranchAnalytics(**data)

