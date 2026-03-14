"""add review_request_sent to visits

Revision ID: 0003
Revises: ccd081b239e1
Create Date: 2026-03-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = 'ccd081b239e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add review_request_sent boolean column to visits."""
    op.add_column(
        'visits',
        sa.Column('review_request_sent', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    """Remove review_request_sent column from visits."""
    op.drop_column('visits', 'review_request_sent')
