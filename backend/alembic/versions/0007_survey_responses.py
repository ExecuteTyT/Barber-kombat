"""guest survey responses (Yandex Forms)

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-03

Stores guest-survey submissions received via the Yandex Forms webhook, with
extracted/scored fields (admin/master score, stars, recommend, negative flag)
and the full raw payload.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "survey_responses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=True
        ),
        sa.Column(
            "client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=True
        ),
        sa.Column(
            "barber_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("phone", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("recommend", sa.Boolean(), nullable=True),
        sa.Column("stars", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("admin_score", sa.Integer(), nullable=True),
        sa.Column("master_score", sa.Integer(), nullable=True),
        sa.Column(
            "is_negative", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("raw", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_survey_responses_branch_created",
        "survey_responses",
        ["branch_id", "created_at"],
    )
    op.create_index(
        "ix_survey_responses_negative", "survey_responses", ["is_negative"]
    )


def downgrade() -> None:
    op.drop_index("ix_survey_responses_negative", table_name="survey_responses")
    op.drop_index("ix_survey_responses_branch_created", table_name="survey_responses")
    op.drop_table("survey_responses")
