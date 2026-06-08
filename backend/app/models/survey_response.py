import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SurveyResponse(Base):
    """A guest-survey submission (Yandex Forms `makon.men/guest-survey`).

    Stores the full payload (`raw`) plus extracted/scored fields so the admin
    and barber modules can use the feedback. branch/client/barber are resolved
    best-effort (branch by text, client by phone, barber by the client's most
    recent visit at that branch).
    """

    __tablename__ = "survey_responses"
    __table_args__ = (
        Index("ix_survey_responses_branch_created", "branch_id", "created_at"),
        Index("ix_survey_responses_negative", "is_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id"), nullable=True
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id"), nullable=True
    )
    barber_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    phone: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    recommend: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    master_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    is_negative: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    raw: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
