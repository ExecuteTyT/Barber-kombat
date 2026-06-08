"""admin call logs

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-08

Tracks admin confirmation calls about upcoming appointments (one row per
branch + record + day) so call completion can feed the admin KPI.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_call_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False
        ),
        sa.Column(
            "admin_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=True
        ),
        sa.Column("yclients_record_id", sa.Integer(), nullable=False),
        sa.Column("call_date", sa.Date(), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=False, server_default="confirmed"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "branch_id",
            "yclients_record_id",
            "call_date",
            name="uq_admin_call_branch_record_date",
        ),
    )
    op.create_index(
        "ix_admin_call_logs_branch_date", "admin_call_logs", ["branch_id", "call_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_admin_call_logs_branch_date", table_name="admin_call_logs")
    op.drop_table("admin_call_logs")
