"""Pydantic schemas for Reviews API endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    """Public form submission — no auth required."""

    branch_id: uuid.UUID
    barber_id: uuid.UUID
    visit_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    rating: int = Field(ge=1, le=5)
    comment: str | None = None
    source: str = Field(default="form", max_length=20)


class ReviewProcessRequest(BaseModel):
    """Request body to process/update a review."""

    status: str = Field(pattern="^(in_progress|processed)$")
    comment: str = Field(min_length=1, max_length=2000)


class ReviewResponse(BaseModel):
    """Single review in API response."""

    id: uuid.UUID
    branch_id: uuid.UUID
    barber_id: uuid.UUID
    barber_name: str
    visit_id: uuid.UUID | None
    client_id: uuid.UUID | None
    client_name: str | None
    client_phone: str | None
    rating: int
    comment: str | None
    source: str
    status: str
    processed_by: uuid.UUID | None
    processed_comment: str | None
    processed_at: datetime | None
    created_at: datetime


class ReviewListResponse(BaseModel):
    """Paginated list of reviews."""

    reviews: list[ReviewResponse]
    total: int
    page: int
    per_page: int


class AlarumResponse(BaseModel):
    """Unprocessed negative reviews (alarum feed)."""

    reviews: list[ReviewResponse]
    total: int


class ReviewCreatedResponse(BaseModel):
    """Response after creating a review."""

    id: uuid.UUID
    status: str
    message: str
