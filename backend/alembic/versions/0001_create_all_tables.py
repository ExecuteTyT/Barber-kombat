"""create_all_tables

Revision ID: 0001
Revises:
Create Date: 2026-02-22 14:20:25.068573

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- organizations ---
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("settings", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # --- branches ---
    op.create_table(
        "branches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.String(500), nullable=False, server_default=""),
        sa.Column("yclients_company_id", sa.Integer(), nullable=True),
        sa.Column("telegram_group_id", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
    )
    op.create_index("ix_branches_organization_id", "branches", ["organization_id"])
    op.create_index("ix_branches_yclients_company_id", "branches", ["yclients_company_id"])

    # --- users ---
    userrole_enum = postgresql.ENUM(
        "owner", "manager", "chef", "barber", "admin", name="userrole", create_type=True
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("role", userrole_enum, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("grade", sa.String(50), nullable=True),
        sa.Column("haircut_price", sa.Integer(), nullable=True),
        sa.Column("yclients_staff_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_branch_id", "users", ["branch_id"])
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)
    op.create_index("ix_users_yclients_staff_id", "users", ["yclients_staff_id"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_unique_constraint(
        "uq_users_staff_org", "users", ["yclients_staff_id", "organization_id"]
    )

    # --- clients ---
    op.create_table(
        "clients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("yclients_client_id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False, server_default=""),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column("first_visit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_visit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_visits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
    )
    op.create_index("ix_clients_organization_id", "clients", ["organization_id"])
    op.create_index("ix_clients_yclients_client_id", "clients", ["yclients_client_id"])
    op.create_index("ix_clients_phone", "clients", ["phone"])
    op.create_unique_constraint(
        "uq_clients_yclient_org", "clients", ["yclients_client_id", "organization_id"]
    )

    # --- visits ---
    op.create_table(
        "visits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("barber_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("yclients_record_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("revenue", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("services_revenue", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("products_revenue", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("services", postgresql.JSONB(), nullable=True),
        sa.Column("products", postgresql.JSONB(), nullable=True),
        sa.Column("extras_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("products_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payment_type", sa.String(20), nullable=False, server_default="card"),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["barber_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
    )
    op.create_index("ix_visits_organization_id", "visits", ["organization_id"])
    op.create_index("ix_visits_branch_id", "visits", ["branch_id"])
    op.create_index("ix_visits_barber_id", "visits", ["barber_id"])
    op.create_index("ix_visits_date", "visits", ["date"])
    op.create_index("ix_visits_yclients_record_id", "visits", ["yclients_record_id"])
    op.create_index("ix_visits_branch_date", "visits", ["branch_id", "date"])
    op.create_unique_constraint(
        "uq_visits_record_org", "visits", ["yclients_record_id", "organization_id"]
    )

    # --- daily_ratings ---
    op.create_table(
        "daily_ratings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("barber_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("revenue", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cs_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("products_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extras_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reviews_avg", sa.Float(), nullable=True),
        sa.Column("revenue_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cs_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("products_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("extras_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reviews_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["barber_id"], ["users.id"]),
        sa.UniqueConstraint("barber_id", "date", name="uq_daily_ratings_barber_date"),
    )
    op.create_index("ix_daily_ratings_branch_date", "daily_ratings", ["branch_id", "date"])
    op.create_index("ix_daily_ratings_barber_date", "daily_ratings", ["barber_id", "date"])

    # --- pvr_records ---
    op.create_table(
        "pvr_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("barber_id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("cumulative_revenue", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_threshold", sa.Integer(), nullable=True),
        sa.Column("bonus_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("thresholds_reached", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["barber_id"], ["users.id"]),
        sa.UniqueConstraint("barber_id", "month", name="uq_pvr_records_barber_month"),
    )

    # --- reviews ---
    reviewstatus_enum = postgresql.ENUM(
        "new", "in_progress", "processed", name="reviewstatus", create_type=True
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("barber_id", sa.Uuid(), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=True),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="internal"),
        sa.Column("status", reviewstatus_enum, nullable=False, server_default="new"),
        sa.Column("processed_by", sa.Uuid(), nullable=True),
        sa.Column("processed_comment", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["barber_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["processed_by"], ["users.id"]),
    )
    op.create_index("ix_reviews_branch_created", "reviews", ["branch_id", "created_at"])
    op.create_index("ix_reviews_barber_created", "reviews", ["barber_id", "created_at"])
    op.create_index("ix_reviews_status", "reviews", ["status"])

    # --- plans ---
    op.create_table(
        "plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("target_amount", sa.Integer(), nullable=False),
        sa.Column("current_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("percentage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("forecast_amount", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.UniqueConstraint("branch_id", "month", name="uq_plans_branch_month"),
    )

    # --- reports ---
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=True),
        sa.Column(
            "delivered_telegram", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
    )
    op.create_index("ix_reports_org_type_date", "reports", ["organization_id", "type", "date"])
    op.create_index("ix_reports_branch_type_date", "reports", ["branch_id", "type", "date"])

    # --- rating_configs ---
    op.create_table(
        "rating_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("revenue_weight", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("cs_weight", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("products_weight", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("extras_weight", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("reviews_weight", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("prize_gold_pct", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("prize_silver_pct", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("prize_bronze_pct", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("extra_services", postgresql.JSONB(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint("organization_id"),
    )

    # --- pvr_configs ---
    op.create_table(
        "pvr_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("thresholds", postgresql.JSONB(), nullable=True),
        sa.Column(
            "count_products", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "count_certificates", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint("organization_id"),
    )

    # --- notification_configs ---
    op.create_table(
        "notification_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=True),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("schedule_time", sa.Time(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
    )


def downgrade() -> None:
    op.drop_table("notification_configs")
    op.drop_table("pvr_configs")
    op.drop_table("rating_configs")
    op.drop_table("reports")
    op.drop_table("plans")
    op.drop_table("reviews")
    op.drop_table("pvr_records")
    op.drop_table("daily_ratings")
    op.drop_table("visits")
    op.drop_table("clients")
    op.drop_table("users")
    op.drop_table("branches")
    op.drop_table("organizations")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS reviewstatus")
