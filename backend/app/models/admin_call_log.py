import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AdminCallLog(Base):
    """An admin's logged call about an upcoming appointment (confirmation calls).

    One row per (branch, yclients_record, call_date) — re-marking updates the
    result. Used to track daily call completion as an admin KPI input.
    """

    __tablename__ = "admin_call_logs"
    __table_args__ = (
        UniqueConstraint(
            "branch_id", "yclients_record_id", "call_date", name="uq_admin_call_branch_record_date"
        ),
        Index("ix_admin_call_logs_branch_date", "branch_id", "call_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    yclients_record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    call_date: Mapped[date] = mapped_column(Date, nullable=False)
    # confirmed | no_answer | callback | declined
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
