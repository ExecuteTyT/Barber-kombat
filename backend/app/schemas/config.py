"""Pydantic schemas for configuration API endpoints."""

import uuid
from datetime import datetime, time

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.user import UserRole


# --- Rating Config ---


class RatingWeightsRequest(BaseModel):
    """Request body for updating rating weights and prize distribution."""

    revenue_weight: int = Field(ge=0)
    cs_weight: int = Field(ge=0)
    products_weight: int = Field(ge=0)
    extras_weight: int = Field(ge=0)
    reviews_weight: int = Field(ge=0)
    prize_gold_pct: float = Field(ge=0)
    prize_silver_pct: float = Field(ge=0)
    prize_bronze_pct: float = Field(ge=0)
    extra_services: list[str] | None = None

    @model_validator(mode="after")
    def validate_weights_sum(self) -> "RatingWeightsRequest":
        total = (
            self.revenue_weight
            + self.cs_weight
            + self.products_weight
            + self.extras_weight
            + self.reviews_weight
        )
        if total != 100:
            raise ValueError(f"Weights must sum to 100, got {total}")
        return self

    @model_validator(mode="after")
    def validate_prize_pcts(self) -> "RatingWeightsRequest":
        total = self.prize_gold_pct + self.prize_silver_pct + self.prize_bronze_pct
        if total > 1.0:
            raise ValueError(
                f"Prize percentages must sum to <= 1.0, got {total}"
            )
        return self


class RatingWeightsResponse(BaseModel):
    """Response body for rating weights."""

    revenue_weight: int
    cs_weight: int
    products_weight: int
    extras_weight: int
    reviews_weight: int
    prize_gold_pct: float
    prize_silver_pct: float
    prize_bronze_pct: float
    extra_services: list[str] | None = None

    model_config = {"from_attributes": True}


# --- PVR Config ---


class ThresholdEntry(BaseModel):
    """A single PVR threshold entry."""

    amount: int = Field(gt=0)
    bonus: int = Field(gt=0)


class PVRThresholdsRequest(BaseModel):
    """Request body for updating PVR thresholds."""

    thresholds: list[ThresholdEntry]
    count_products: bool
    count_certificates: bool

    @field_validator("thresholds")
    @classmethod
    def validate_thresholds(cls, v: list[ThresholdEntry]) -> list[ThresholdEntry]:
        if len(v) < 1:
            raise ValueError("At least one threshold required")
        amounts = [t.amount for t in v]
        if amounts != sorted(amounts):
            raise ValueError("Thresholds must be sorted ascending by amount")
        if len(set(amounts)) != len(amounts):
            raise ValueError("Threshold amounts must be unique")
        return v


class PVRThresholdsResponse(BaseModel):
    """Response body for PVR thresholds."""

    thresholds: list[ThresholdEntry]
    count_products: bool
    count_certificates: bool


# --- Branch ---


class BranchCreateRequest(BaseModel):
    """Request body for creating a branch."""

    name: str = Field(min_length=1, max_length=255)
    address: str = Field(default="", max_length=500)
    yclients_company_id: int | None = None
    telegram_group_id: int | None = None


class BranchUpdateRequest(BaseModel):
    """Request body for updating a branch. All fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    yclients_company_id: int | None = None
    telegram_group_id: int | None = None
    is_active: bool | None = None


class BranchResponse(BaseModel):
    """Single branch in API response."""

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    address: str
    yclients_company_id: int | None
    telegram_group_id: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BranchListResponse(BaseModel):
    """List of branches."""

    branches: list[BranchResponse]


# --- User ---


class UserCreateRequest(BaseModel):
    """Request body for creating a user."""

    telegram_id: int
    name: str = Field(min_length=1, max_length=255)
    role: UserRole
    branch_id: uuid.UUID | None = None
    grade: str | None = Field(default=None, max_length=50)
    haircut_price: int | None = None
    yclients_staff_id: int | None = None


class UserUpdateRequest(BaseModel):
    """Request body for updating a user. All fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None
    branch_id: uuid.UUID | None = None
    grade: str | None = Field(default=None, max_length=50)
    haircut_price: int | None = None
    yclients_staff_id: int | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    """Single user in API response."""

    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    telegram_id: int
    role: UserRole
    name: str
    grade: str | None
    haircut_price: int | None
    yclients_staff_id: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """List of users."""

    users: list[UserResponse]


# --- Notification Config ---


class NotificationConfigCreateRequest(BaseModel):
    """Request body for creating a notification config."""

    branch_id: uuid.UUID | None = None
    notification_type: str = Field(min_length=1, max_length=50)
    telegram_chat_id: int
    is_enabled: bool = True
    schedule_time: time | None = None


class NotificationConfigUpdateRequest(BaseModel):
    """Request body for updating a notification config."""

    telegram_chat_id: int | None = None
    is_enabled: bool | None = None
    schedule_time: time | None = None


class NotificationConfigResponse(BaseModel):
    """Single notification config in API response."""

    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    notification_type: str
    telegram_chat_id: int
    is_enabled: bool
    schedule_time: time | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationConfigListResponse(BaseModel):
    """List of notification configs."""

    notifications: list[NotificationConfigResponse]
