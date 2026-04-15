import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PVRRecord(Base):
    __tablename__ = "pvr_records"
    __table_args__ = (UniqueConstraint("barber_id", "month", name="uq_pvr_records_barber_month"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    barber_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    month: Mapped[date] = mapped_column(Date, nullable=False)
    cumulative_revenue: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # current_threshold now holds a score (0-100), not a kopeck amount.
    current_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bonus_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    thresholds_reached: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    monthly_rating_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metric_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    working_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
