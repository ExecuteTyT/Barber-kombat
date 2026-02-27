import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Visit(Base):
    __tablename__ = "visits"
    __table_args__ = (
        UniqueConstraint(
            "yclients_record_id", "organization_id", name="uq_visits_record_org"
        ),
        Index("ix_visits_organization_id", "organization_id"),
        Index("ix_visits_branch_id", "branch_id"),
        Index("ix_visits_barber_id", "barber_id"),
        Index("ix_visits_date", "date"),
        Index("ix_visits_yclients_record_id", "yclients_record_id"),
        Index("ix_visits_branch_date", "branch_id", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    barber_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id"), nullable=True
    )
    yclients_record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    revenue: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    services_revenue: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_revenue: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    services: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    products: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    extras_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    products_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payment_type: Mapped[str] = mapped_column(String(20), nullable=False, default="card")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    review: Mapped["Review | None"] = relationship(back_populates="visit")  # noqa: F821
