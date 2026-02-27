import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DailyRating(Base):
    __tablename__ = "daily_ratings"
    __table_args__ = (
        UniqueConstraint("barber_id", "date", name="uq_daily_ratings_barber_date"),
        Index("ix_daily_ratings_branch_date", "branch_id", "date"),
        Index("ix_daily_ratings_barber_date", "barber_id", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    barber_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # Raw values
    revenue: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cs_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    products_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extras_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviews_avg: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Normalized scores (0-100)
    revenue_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cs_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    products_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    extras_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reviews_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Final
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
