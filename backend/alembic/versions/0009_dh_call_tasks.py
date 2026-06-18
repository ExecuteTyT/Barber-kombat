"""dataheroes call tasks

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-18

Adds branches.datahero_project_id and the dh_call_tasks table storing
quality-control call tasks pulled from DataHeroes ("Нужно связаться").
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "branches",
        sa.Column("datahero_project_id", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "branches",
        sa.Column("datahero_activations", sa.ARRAY(sa.Integer()), nullable=True),
    )
    op.create_table(
        "dh_call_tasks",
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
        sa.Column("dataheroes_task_id", sa.String(length=64), nullable=False),
        sa.Column("dh_project_id", sa.String(length=32), nullable=True),
        sa.Column("dh_client_id", sa.String(length=64), nullable=True),
        sa.Column("client_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("visit_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("result", sa.String(length=40), nullable=True),
        sa.Column(
            "contacted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "pushed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("task_date", sa.Date(), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "branch_id", "dataheroes_task_id", name="uq_dh_call_branch_task"
        ),
    )
    op.create_index(
        "ix_dh_call_tasks_branch_status", "dh_call_tasks", ["branch_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_dh_call_tasks_branch_status", table_name="dh_call_tasks")
    op.drop_table("dh_call_tasks")
    op.drop_column("branches", "datahero_activations")
    op.drop_column("branches", "datahero_project_id")
