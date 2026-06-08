import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ReviewStatus(enum.StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    PROCESSED = "processed"


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        Index("ix_reviews_branch_created", "branch_id", "created_at"),
        Index("ix_reviews_barber_created", "barber_id", "created_at"),
        Index("ix_reviews_status", "status"),
        # Idempotent sync of YClients reviews: one row per (org, comment).
        # NULLs (form/internal reviews) are distinct, so they are unaffected.
        UniqueConstraint(
            "organization_id", "yclients_comment_id", name="uq_reviews_yclients_comment_org"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    barber_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    visit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("visits.id"), nullable=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="internal")
    # YClients comment id when source="yclients" (for idempotent sync); NULL otherwise.
    yclients_comment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(
            ReviewStatus,
            values_callable=lambda e: [i.value for i in e],
            name="reviewstatus",
            create_constraint=False,
        ),
        nullable=False,
        default=ReviewStatus.NEW,
    )
    processed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    processed_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    visit: Mapped["Visit | None"] = relationship(back_populates="review")  # noqa: F821
