"""Add partial unique indexes on reports table for ON CONFLICT upsert.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-28
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old non-unique indexes (replaced by the unique ones below)
    op.drop_index("ix_reports_org_type_date", table_name="reports")
    op.drop_index("ix_reports_branch_type_date", table_name="reports")

    # Partial unique index for reports WITHOUT a branch_id (network-level)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_reports_org_type_date_no_branch
        ON reports (organization_id, type, date)
        WHERE branch_id IS NULL
        """
    )

    # Partial unique index for reports WITH a branch_id (branch-level)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_reports_org_branch_type_date
        ON reports (organization_id, branch_id, type, date)
        WHERE branch_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_reports_org_branch_type_date")
    op.execute("DROP INDEX IF EXISTS uq_reports_org_type_date_no_branch")

    # Recreate original non-unique indexes
    op.create_index("ix_reports_org_type_date", "reports", ["organization_id", "type", "date"])
    op.create_index("ix_reports_branch_type_date", "reports", ["branch_id", "type", "date"])
