"""Pydantic schemas for Plans (revenue target) API endpoints."""

import uuid
from datetime import date

from pydantic import BaseModel, Field


class PlanCreate(BaseModel):
    """Request body to create or update a plan for a branch."""

    month: date = Field(description="First day of the target month (e.g. 2024-10-01)")
    target_amount: int = Field(gt=0, description="Target revenue in kopecks")


class PlanResponse(BaseModel):
    """Single plan data for API response."""

    id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str
    month: str
    target_amount: int
    current_amount: int
    percentage: float
    forecast_amount: int | None
    required_daily: int | None
    days_passed: int
    days_in_month: int
    days_left: int
    is_behind: bool


class PlanNetworkEntry(BaseModel):
    """Plan data for a single branch in the network overview."""

    branch_id: uuid.UUID
    branch_name: str
    target_amount: int
    current_amount: int
    percentage: float
    forecast_amount: int | None


class PlanNetworkResponse(BaseModel):
    """All plans across the network for a given month."""

    month: str
    plans: list[PlanNetworkEntry]
    total_target: int
    total_current: int
    total_percentage: float
