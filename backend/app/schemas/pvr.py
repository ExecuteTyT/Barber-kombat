"""Pydantic schemas for PVR (Premium for High Results) API endpoints."""

import uuid

from pydantic import BaseModel


class ThresholdReached(BaseModel):
    """A single threshold that was reached by a barber."""

    amount: int
    reached_at: str


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


class BranchPVRResponse(BaseModel):
    """PVR data for all barbers in a branch."""

    branch_id: uuid.UUID
    month: str
    barbers: list[BarberPVRResponse]


class ThresholdEntry(BaseModel):
    """A single threshold configuration entry."""

    amount: int
    bonus: int


class ThresholdsResponse(BaseModel):
    """Threshold configuration for an organization."""

    thresholds: list[ThresholdEntry]
    count_products: bool
    count_certificates: bool
