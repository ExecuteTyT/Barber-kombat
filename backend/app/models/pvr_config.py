import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PVRConfig(Base):
    __tablename__ = "pvr_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), unique=True, nullable=False
    )
    thresholds: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    count_products: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    count_certificates: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_visits_per_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    thresholds_legacy_backup: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(  # noqa: F821
        back_populates="pvr_config"
    )
