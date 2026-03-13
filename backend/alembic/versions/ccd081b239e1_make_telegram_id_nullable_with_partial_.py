"""make telegram_id nullable with partial unique index

Revision ID: ccd081b239e1
Revises: 0002
Create Date: 2026-03-14 00:55:42.646870

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ccd081b239e1'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make telegram_id nullable and use partial unique index."""
    # Drop the old unique index
    op.drop_index('ix_users_telegram_id', table_name='users')

    # Make column nullable
    op.alter_column('users', 'telegram_id',
               existing_type=sa.BIGINT(),
               nullable=True)

    # Set existing placeholder 0 values to NULL
    op.execute("UPDATE users SET telegram_id = NULL WHERE telegram_id = 0")

    # Recreate as partial unique index (only non-null values)
    op.create_index(
        'ix_users_telegram_id', 'users', ['telegram_id'],
        unique=True,
        postgresql_where=sa.text('telegram_id IS NOT NULL'),
    )


def downgrade() -> None:
    """Revert telegram_id to non-nullable with full unique index."""
    op.drop_index('ix_users_telegram_id', table_name='users')

    op.execute("UPDATE users SET telegram_id = 0 WHERE telegram_id IS NULL")

    op.alter_column('users', 'telegram_id',
               existing_type=sa.BIGINT(),
               nullable=False)

    op.create_index('ix_users_telegram_id', 'users', ['telegram_id'], unique=True)
