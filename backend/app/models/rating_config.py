import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RatingConfig(Base):
    __tablename__ = "rating_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), unique=True, nullable=False
    )

    # Weights (should sum to 100)
    revenue_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    cs_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    products_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    extras_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    reviews_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    # Prize distribution
    prize_gold_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    prize_silver_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    prize_bronze_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)

    # Extra services list
    extra_services: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(  # noqa: F821
        back_populates="rating_config"
    )
