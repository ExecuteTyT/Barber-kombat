"""add confirmed flag to visits

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-03

Captures the YClients booking-confirmation flag on each visit so the admin
module can measure confirmation of upcoming appointments. Existing rows
default to False.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "visits",
        sa.Column(
            "confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("visits", "confirmed")
