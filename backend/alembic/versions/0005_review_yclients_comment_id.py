"""add yclients_comment_id to reviews

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-31

Adds reviews.yclients_comment_id so reviews synced from the YClients
/comments API can be upserted idempotently (one row per org + comment).
A unique constraint on (organization_id, yclients_comment_id) enforces this;
existing form/internal reviews keep yclients_comment_id = NULL (NULLs are
distinct in Postgres, so they are unaffected).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reviews",
        sa.Column("yclients_comment_id", sa.Integer(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_reviews_yclients_comment_org",
        "reviews",
        ["organization_id", "yclients_comment_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_reviews_yclients_comment_org", "reviews", type_="unique")
    op.drop_column("reviews", "yclients_comment_id")
