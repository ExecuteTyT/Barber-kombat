"""Pydantic schemas for Barber Kombat API endpoints."""

import uuid
from datetime import date

from pydantic import BaseModel

# --- /kombat/today/{branch_id} ---


class RatingEntry(BaseModel):
    """Single barber's rating entry."""

    barber_id: uuid.UUID
    name: str
    rank: int
    total_score: float
    revenue: int
    revenue_score: float
    cs_value: float
    cs_score: float
    products_count: int
    products_score: float
    extras_count: int
    extras_score: float
    reviews_avg: float | None
    reviews_score: float

    model_config = {"from_attributes": True}


class PrizeFundResponse(BaseModel):
    """Prize fund breakdown."""

    gold: int
    silver: int
    bronze: int


class PlanResponse(BaseModel):
    """Monthly revenue plan progress."""

    target: int
    current: int
    percentage: float
    forecast: int | None
    required_daily: int


class WeightsResponse(BaseModel):
    """Rating weights configuration."""

    revenue: int
    cs: int
    products: int
    extras: int
    reviews: int


class TodayRatingResponse(BaseModel):
    """Full response for today's rating."""

    branch_id: uuid.UUID
    branch_name: str
    date: date
    is_active: bool
    ratings: list[RatingEntry]
    prize_fund: PrizeFundResponse
    plan: PlanResponse | None
    weights: WeightsResponse


# --- /kombat/standings/{branch_id} ---


class StandingEntry(BaseModel):
    """Single barber's monthly standing."""

    barber_id: uuid.UUID
    name: str
    wins: int
    avg_score: float


class StandingsResponse(BaseModel):
    """Monthly standings response."""

    branch_id: uuid.UUID
    month: str
    standings: list[StandingEntry]


# --- /kombat/history/{branch_id} ---


class HistoryWinner(BaseModel):
    """Winner of a single day."""

    barber_id: uuid.UUID
    name: str


class HistoryDay(BaseModel):
    """Single day's rating history."""

    date: date
    winner: HistoryWinner | None
    ratings: list[RatingEntry]


class HistoryResponse(BaseModel):
    """Rating history response."""

    days: list[HistoryDay]


# --- /kombat/barber/{barber_id}/stats ---


class DailyScoreEntry(BaseModel):
    """Single day's score for a barber."""

    date: date
    score: float
    rank: int
    revenue: int = 0


class BarberStatsResponse(BaseModel):
    """Detailed barber statistics for a month."""

    barber_id: uuid.UUID
    name: str
    month: str
    wins: int
    avg_score: float
    total_revenue: int
    avg_revenue_per_day: int
    avg_cs: float
    total_products: int
    total_extras: int
    avg_review: float | None
    daily_scores: list[DailyScoreEntry]
