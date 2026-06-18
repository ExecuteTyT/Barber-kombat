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


class DHCallTask(Base):
    """A quality-control call task pulled from DataHeroes ("Нужно связаться").

    One row per (branch, DataHeroes communicationId). The local row is the
    source of truth for whether our admin has handled it; ``mark_qc_call`` flips
    ``status`` to "contacted" locally first, then pushes the change to DataHeroes.
    DataHeroes' client id is a YClients string id, not our Client UUID, so it is
    stored as plain text rather than a foreign key.
    """

    __tablename__ = "dh_call_tasks"
    __table_args__ = (
        UniqueConstraint(
            "branch_id", "dataheroes_task_id", name="uq_dh_call_branch_task"
        ),
        Index("ix_dh_call_tasks_branch_status", "branch_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    # DataHeroes identifiers (communicationId / projectId / clientId) — strings.
    dataheroes_task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dh_project_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dh_client_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Activation name, e.g. "Контроль качества. Был впервые."
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    visit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # pending | contacted
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Free-text call outcome (optional), set when an admin marks it.
    result: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contacted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Whether the "contacted" mark has been pushed back to DataHeroes.
    pushed: Mapped[bool] = mapped_column(default=False, nullable=False)
    task_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
