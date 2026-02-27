"""Barber Kombat API endpoints."""

import calendar
import uuid
from datetime import date
from typing import Annotated

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Integer, case, select
from sqlalchemy import func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.branch import Branch
from app.models.daily_rating import DailyRating
from app.models.plan import Plan
from app.models.rating_config import RatingConfig
from app.models.user import User, UserRole
from app.redis import get_redis
from app.schemas.kombat import (
    BarberStatsResponse,
    DailyScoreEntry,
    HistoryDay,
    HistoryResponse,
    HistoryWinner,
    PlanResponse,
    PrizeFundResponse,
    RatingEntry,
    StandingEntry,
    StandingsResponse,
    TodayRatingResponse,
    WeightsResponse,
)
from app.services.rating import RatingEngine

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/kombat", tags=["kombat"])

# Default weights when no RatingConfig exists
_DEFAULT_WEIGHTS = {
    "revenue": 20,
    "cs": 20,
    "products": 25,
    "extras": 25,
    "reviews": 10,
}


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


def _parse_month(month_str: str | None) -> tuple[date, date]:
    """Parse a YYYY-MM string into (month_start, month_end) dates.

    Defaults to current month if None.
    """
    today = date.today()
    if month_str:
        try:
            parts = month_str.split("-")
            year, month = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid month format. Use YYYY-MM",
            ) from None
    else:
        year, month = today.year, today.month

    month_start = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    month_end = date(year, month, last_day)
    return month_start, month_end


async def _load_weights(
    org_id: uuid.UUID, db: AsyncSession
) -> WeightsResponse:
    """Load rating weights from RatingConfig or use defaults."""
    result = await db.execute(
        select(RatingConfig).where(RatingConfig.organization_id == org_id)
    )
    config = result.scalar_one_or_none()
    if config:
        return WeightsResponse(
            revenue=config.revenue_weight,
            cs=config.cs_weight,
            products=config.products_weight,
            extras=config.extras_weight,
            reviews=config.reviews_weight,
        )
    return WeightsResponse(**_DEFAULT_WEIGHTS)


@router.get("/today/{branch_id}", response_model=TodayRatingResponse)
async def get_today_rating(
    branch_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Get today's rating for a branch. All roles."""
    branch = await _validate_branch(branch_id, current_user.organization_id, db)
    today = date.today()

    # Try cached rating first
    engine = RatingEngine(db=db, redis=redis)
    cached = await engine.get_cached_rating(branch_id, today)

    if cached:
        ratings = [
            RatingEntry(
                barber_id=uuid.UUID(r["barber_id"]),
                name=r["name"],
                rank=r["rank"],
                total_score=r["total_score"],
                revenue=r["revenue"],
                revenue_score=r["revenue_score"],
                cs_value=r["cs_value"],
                cs_score=r["cs_score"],
                products_count=r["products_count"],
                products_score=r["products_score"],
                extras_count=r["extras_count"],
                extras_score=r["extras_score"],
                reviews_avg=r["reviews_avg"],
                reviews_score=r["reviews_score"],
            )
            for r in cached["ratings"]
        ]
        prize_fund = PrizeFundResponse(**cached["prize_fund"])
    else:
        # Fall back to DB query
        result = await db.execute(
            select(DailyRating, User.name)
            .join(User, DailyRating.barber_id == User.id)
            .where(
                DailyRating.branch_id == branch_id,
                DailyRating.date == today,
            )
            .order_by(DailyRating.rank)
        )
        rows = result.all()

        ratings = [
            RatingEntry(
                barber_id=dr.barber_id,
                name=name,
                rank=dr.rank,
                total_score=round(dr.total_score, 2),
                revenue=dr.revenue,
                revenue_score=round(dr.revenue_score, 2),
                cs_value=round(dr.cs_value, 4),
                cs_score=round(dr.cs_score, 2),
                products_count=dr.products_count,
                products_score=round(dr.products_score, 2),
                extras_count=dr.extras_count,
                extras_score=round(dr.extras_score, 2),
                reviews_avg=round(dr.reviews_avg, 2) if dr.reviews_avg is not None else None,
                reviews_score=round(dr.reviews_score, 2),
            )
            for dr, name in rows
        ]

        # Calculate prize fund from engine
        pf = await engine.get_prize_fund(branch_id, current_user.organization_id)
        prize_fund = PrizeFundResponse(**pf)

    # Load plan
    month_start = today.replace(day=1)
    plan_result = await db.execute(
        select(Plan).where(
            Plan.branch_id == branch_id,
            Plan.month == month_start,
        )
    )
    plan_row = plan_result.scalar_one_or_none()
    plan = None
    if plan_row:
        _, last_day = calendar.monthrange(today.year, today.month)
        remaining_days = last_day - today.day
        if remaining_days > 0 and plan_row.target_amount > plan_row.current_amount:
            required_daily = (plan_row.target_amount - plan_row.current_amount) // remaining_days
        else:
            required_daily = 0

        plan = PlanResponse(
            target=plan_row.target_amount,
            current=plan_row.current_amount,
            percentage=plan_row.percentage,
            forecast=plan_row.forecast_amount,
            required_daily=required_daily,
        )

    # Load weights
    weights = await _load_weights(current_user.organization_id, db)

    return TodayRatingResponse(
        branch_id=branch.id,
        branch_name=branch.name,
        date=today,
        is_active=branch.is_active,
        ratings=ratings,
        prize_fund=prize_fund,
        plan=plan,
        weights=weights,
    )


@router.get("/standings/{branch_id}", response_model=StandingsResponse)
async def get_standings(
    branch_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    month: str | None = Query(None, description="Month in YYYY-MM format"),
):
    """Get monthly standings for a branch. All roles."""
    await _validate_branch(branch_id, current_user.organization_id, db)
    month_start, month_end = _parse_month(month)

    month_label = f"{month_start.year}-{month_start.month:02d}"

    # Aggregate standings: wins (rank=1 count) and avg_score
    wins_case = sa_func.sum(
        case((DailyRating.rank == 1, 1), else_=0)
    ).cast(Integer)

    stmt = (
        select(
            DailyRating.barber_id,
            User.name,
            wins_case.label("wins"),
            sa_func.avg(DailyRating.total_score).label("avg_score"),
        )
        .join(User, DailyRating.barber_id == User.id)
        .where(
            DailyRating.branch_id == branch_id,
            DailyRating.date >= month_start,
            DailyRating.date <= month_end,
        )
        .group_by(DailyRating.barber_id, User.name)
        .order_by(wins_case.desc(), sa_func.avg(DailyRating.total_score).desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    standings = [
        StandingEntry(
            barber_id=row.barber_id,
            name=row.name,
            wins=row.wins,
            avg_score=round(float(row.avg_score), 1),
        )
        for row in rows
    ]

    return StandingsResponse(
        branch_id=branch_id,
        month=month_label,
        standings=standings,
    )


@router.get("/history/{branch_id}", response_model=HistoryResponse)
async def get_history(
    branch_id: uuid.UUID,
    current_user: Annotated[
        User, Depends(require_role(UserRole.CHEF, UserRole.OWNER))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: Annotated[date, Query(description="Start date (YYYY-MM-DD)")],
    date_to: Annotated[date, Query(description="End date (YYYY-MM-DD)")],
):
    """Get rating history for a branch. Chef and owner only."""
    await _validate_branch(branch_id, current_user.organization_id, db)

    result = await db.execute(
        select(DailyRating, User.name)
        .join(User, DailyRating.barber_id == User.id)
        .where(
            DailyRating.branch_id == branch_id,
            DailyRating.date >= date_from,
            DailyRating.date <= date_to,
        )
        .order_by(DailyRating.date.desc(), DailyRating.rank)
    )
    rows = result.all()

    # Group by date
    days_map: dict[date, list[tuple]] = {}
    for dr, name in rows:
        days_map.setdefault(dr.date, []).append((dr, name))

    days = []
    for day_date in sorted(days_map.keys(), reverse=True):
        day_rows = days_map[day_date]
        ratings = [
            RatingEntry(
                barber_id=dr.barber_id,
                name=name,
                rank=dr.rank,
                total_score=round(dr.total_score, 2),
                revenue=dr.revenue,
                revenue_score=round(dr.revenue_score, 2),
                cs_value=round(dr.cs_value, 4),
                cs_score=round(dr.cs_score, 2),
                products_count=dr.products_count,
                products_score=round(dr.products_score, 2),
                extras_count=dr.extras_count,
                extras_score=round(dr.extras_score, 2),
                reviews_avg=round(dr.reviews_avg, 2) if dr.reviews_avg is not None else None,
                reviews_score=round(dr.reviews_score, 2),
            )
            for dr, name in day_rows
        ]

        # Winner is rank=1
        winner = None
        for dr, name in day_rows:
            if dr.rank == 1:
                winner = HistoryWinner(barber_id=dr.barber_id, name=name)
                break

        days.append(HistoryDay(date=day_date, winner=winner, ratings=ratings))

    return HistoryResponse(days=days)


@router.get("/barber/{barber_id}/stats", response_model=BarberStatsResponse)
async def get_barber_stats(
    barber_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    month: str | None = Query(None, description="Month in YYYY-MM format"),
):
    """Get detailed statistics for a barber. All roles."""
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

    month_start, month_end = _parse_month(month)
    month_label = f"{month_start.year}-{month_start.month:02d}"

    # Query DailyRating for barber in month
    dr_result = await db.execute(
        select(DailyRating)
        .where(
            DailyRating.barber_id == barber_id,
            DailyRating.date >= month_start,
            DailyRating.date <= month_end,
        )
        .order_by(DailyRating.date)
    )
    daily_ratings = list(dr_result.scalars().all())

    # Calculate aggregates
    wins = sum(1 for dr in daily_ratings if dr.rank == 1)
    total_days = len(daily_ratings)

    if total_days > 0:
        avg_score = sum(dr.total_score for dr in daily_ratings) / total_days
        total_revenue = sum(dr.revenue for dr in daily_ratings)
        avg_revenue_per_day = total_revenue // total_days
        avg_cs = sum(dr.cs_value for dr in daily_ratings) / total_days
        total_products = sum(dr.products_count for dr in daily_ratings)
        total_extras = sum(dr.extras_count for dr in daily_ratings)

        reviews_with_data = [dr.reviews_avg for dr in daily_ratings if dr.reviews_avg is not None]
        avg_review = (
            sum(reviews_with_data) / len(reviews_with_data)
            if reviews_with_data
            else None
        )
    else:
        avg_score = 0.0
        total_revenue = 0
        avg_revenue_per_day = 0
        avg_cs = 0.0
        total_products = 0
        total_extras = 0
        avg_review = None

    daily_scores = [
        DailyScoreEntry(
            date=dr.date,
            score=round(dr.total_score, 2),
            rank=dr.rank,
        )
        for dr in daily_ratings
    ]

    return BarberStatsResponse(
        barber_id=barber.id,
        name=barber.name,
        month=month_label,
        wins=wins,
        avg_score=round(avg_score, 1),
        total_revenue=total_revenue,
        avg_revenue_per_day=avg_revenue_per_day,
        avg_cs=round(avg_cs, 2),
        total_products=total_products,
        total_extras=total_extras,
        avg_review=round(avg_review, 1) if avg_review is not None else None,
        daily_scores=daily_scores,
    )
