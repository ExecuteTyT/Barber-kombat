"""pvr rating-based thresholds

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-15

Switches PVR from absolute revenue thresholds to monthly rating score thresholds.

pvr_records:
  + monthly_rating_score INTEGER NOT NULL DEFAULT 0
  + metric_breakdown JSONB NULL
  + working_days INTEGER NOT NULL DEFAULT 0
  (semantics of current_threshold shifts from kopecks to 0-100 score;
   column type stays Integer. Old monthly records get reset to zero so
   they recompute on next sync.)

pvr_configs:
  + min_visits_per_month INTEGER NOT NULL DEFAULT 0
  + thresholds_legacy_backup JSONB NULL  (backup of old revenue thresholds)
  * thresholds reset to rating-based defaults for any org that had the old
    format. Owner must re-review them in SettingsScreen.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DEFAULT_SCORE_THRESHOLDS = [
    {"score": 60, "bonus": 100_000_000},
    {"score": 75, "bonus": 200_000_000},
    {"score": 90, "bonus": 500_000_000},
]


def upgrade() -> None:
    op.add_column(
        "pvr_records",
        sa.Column("monthly_rating_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pvr_records",
        sa.Column("metric_breakdown", JSONB(), nullable=True),
    )
    op.add_column(
        "pvr_records",
        sa.Column("working_days", sa.Integer(), nullable=False, server_default="0"),
    )

    op.add_column(
        "pvr_configs",
        sa.Column("min_visits_per_month", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pvr_configs",
        sa.Column("thresholds_legacy_backup", JSONB(), nullable=True),
    )

    # Back up the old revenue thresholds, then reset to score-based defaults.
    # Old records store {"amount", "bonus"}; new records store {"score", "bonus"}.
    op.execute(
        """
        UPDATE pvr_configs
           SET thresholds_legacy_backup = thresholds,
               thresholds = :new_thresholds
         WHERE thresholds IS NOT NULL
        """.replace(":new_thresholds", "'" + _json(_DEFAULT_SCORE_THRESHOLDS) + "'::jsonb")
    )

    # Reset stored thresholds on past records: the meaning changed and the
    # old kopeck values would be nonsense as scores. The next sync pass
    # rewrites them with real rating scores.
    op.execute(
        "UPDATE pvr_records SET current_threshold = NULL, bonus_amount = 0, "
        "thresholds_reached = NULL"
    )


def downgrade() -> None:
    # Restore legacy thresholds (best-effort; new-format rows lose data).
    op.execute(
        """
        UPDATE pvr_configs
           SET thresholds = thresholds_legacy_backup
         WHERE thresholds_legacy_backup IS NOT NULL
        """
    )

    op.drop_column("pvr_configs", "thresholds_legacy_backup")
    op.drop_column("pvr_configs", "min_visits_per_month")

    op.drop_column("pvr_records", "working_days")
    op.drop_column("pvr_records", "metric_breakdown")
    op.drop_column("pvr_records", "monthly_rating_score")


def _json(value) -> str:
    import json as _j

    return _j.dumps(value).replace("'", "''")
