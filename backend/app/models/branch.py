import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (
        Index("ix_branches_organization_id", "organization_id"),
        Index("ix_branches_yclients_company_id", "yclients_company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    yclients_company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # DataHeroes (Platrum) project id for this branch, e.g. "ZSXIHEMPX".
    # When set (and DataHeroes is enabled), QC call tasks are synced for it.
    datahero_project_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # DataHeroes activation (campaign) ids whose "Нужно связаться" tasks we pull,
    # e.g. [185298, 185299]. Required by their API — empty means no tasks.
    # Campaign-specific and may change; configured per branch.
    datahero_activations: Mapped[list[int] | None] = mapped_column(
        ARRAY(Integer), nullable=True
    )
    telegram_group_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="branches")  # noqa: F821
    users: Mapped[list["User"]] = relationship(back_populates="branch")  # noqa: F821
