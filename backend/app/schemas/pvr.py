"""Pydantic schemas for PVR (Premium for High Results) API endpoints."""

import uuid
from datetime import date

from pydantic import BaseModel, Field


class ThresholdReached(BaseModel):
    """A score threshold that was crossed during the month."""

    score: int
    reached_at: str


class MetricBreakdown(BaseModel):
    """Per-metric component scores (0-100) contributing to the monthly rating."""

    revenue_score: int = 0
    cs_score: int = 0
    products_score: int = 0
    extras_score: int = 0
    reviews_score: int = 0


class BarberPVRResponse(BaseModel):
    """PVR data for a single barber."""

    barber_id: uuid.UUID
    name: str
    cumulative_revenue: int
    current_threshold: int | None
    bonus_amount: int
    next_threshold: int | None
    remaining_to_next: int | None
    thresholds_reached: list[ThresholdReached]
    monthly_rating_score: int
    metric_breakdown: MetricBreakdown
    working_days: int
    min_visits_required: int


class BranchPVRResponse(BaseModel):
    """PVR data for all barbers in a branch."""

    branch_id: uuid.UUID
    month: str
    barbers: list[BarberPVRResponse]


class ThresholdEntry(BaseModel):
    """A single threshold configuration entry."""

    score: int = Field(ge=0, le=100)
    bonus: int = Field(gt=0)


class ThresholdsResponse(BaseModel):
    """Threshold configuration for an organization."""

    thresholds: list[ThresholdEntry]
    count_products: bool
    count_certificates: bool
    min_visits_per_month: int


class PVRPreviewRequest(BaseModel):
    """Simulate PVR with hypothetical config without saving."""

    branch_id: uuid.UUID
    thresholds: list[ThresholdEntry]
    min_visits_per_month: int = Field(ge=0)
    month: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}$",
        description="YYYY-MM. Defaults to the current month.",
    )


class PVRPreviewEntry(BaseModel):
    barber_id: uuid.UUID
    name: str
    monthly_rating_score: int
    working_days: int
    current_threshold: int | None
    bonus_amount: int
    revenue: int


class PVRPreviewResponse(BaseModel):
    month: str
    total_bonus_fund: int
    barbers: list[PVRPreviewEntry]
