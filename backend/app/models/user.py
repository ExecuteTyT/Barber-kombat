import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UserRole(enum.StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    CHEF = "chef"
    BARBER = "barber"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint(
            "yclients_staff_id", "organization_id", name="uq_users_staff_org"
        ),
        Index("ix_users_organization_id", "organization_id"),
        Index("ix_users_branch_id", "branch_id"),
        Index("ix_users_telegram_id", "telegram_id", unique=True),
        Index("ix_users_yclients_staff_id", "yclients_staff_id"),
        Index("ix_users_role", "role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id"), nullable=True
    )
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda e: [i.value for i in e], name="userrole", create_constraint=False),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    grade: Mapped[str | None] = mapped_column(String(50), nullable=True)
    haircut_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yclients_staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="users")  # noqa: F821
    branch: Mapped["Branch | None"] = relationship(back_populates="users")  # noqa: F821
