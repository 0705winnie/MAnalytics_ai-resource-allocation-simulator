"""Create official simulation sessions and monthly results.

Revision ID: 0004_simulation_persistence
Revises: 0003_months_completed
"""

from collections.abc import Sequence
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_simulation_persistence"
down_revision: str | None = "0003_months_completed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulation_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("enrollment_id", sa.Uuid(), nullable=False),
        sa.Column(
            "completed_months",
            sa.SmallInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "completed_months BETWEEN 0 AND 12",
            name="ck_simulation_sessions_completed_months_range",
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["enrollments.id"],
            name="fk_simulation_sessions_enrollment_id_enrollments",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_simulation_sessions"),
        sa.UniqueConstraint(
            "enrollment_id",
            name="uq_simulation_sessions_enrollment_id",
        ),
    )
    op.create_index(
        "ix_simulation_sessions_completed_months",
        "simulation_sessions",
        ["completed_months"],
    )

    op.create_table(
        "monthly_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.SmallInteger(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("policy_code", sa.Text(), nullable=False),
        sa.Column("policy_params", postgresql.JSONB(), nullable=False),
        sa.Column("policy_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("total_requests", sa.Integer(), nullable=False),
        sa.Column("admitted_requests", sa.Integer(), nullable=False),
        sa.Column("completed_requests", sa.Integer(), nullable=False),
        sa.Column("rejected_requests", sa.Integer(), nullable=False),
        sa.Column("total_revenue", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("unfinished_requests", sa.Integer(), nullable=False),
        sa.Column("unfinished_value", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("avg_utilization", postgresql.JSONB(), nullable=False),
        sa.Column("peak_utilization", postgresql.JSONB(), nullable=False),
        sa.Column("remaining_capacity", postgresql.JSONB(), nullable=False),
        sa.Column("by_type", postgresql.JSONB(), nullable=False),
        sa.Column("warnings", postgresql.JSONB(), nullable=False),
        sa.Column("benchmark_comparison", postgresql.JSONB(), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "month BETWEEN 1 AND 12",
            name="ck_monthly_results_month_range",
        ),
        sa.CheckConstraint(
            "total_requests >= 0 "
            "AND admitted_requests >= 0 "
            "AND completed_requests >= 0 "
            "AND rejected_requests >= 0 "
            "AND unfinished_requests >= 0",
            name="ck_monthly_results_nonnegative_counts",
        ),
        sa.CheckConstraint(
            "total_revenue >= 0 AND unfinished_value >= 0",
            name="ck_monthly_results_nonnegative_values",
        ),
        sa.CheckConstraint(
            "admitted_requests <= total_requests",
            name="ck_monthly_results_admitted_within_total",
        ),
        sa.CheckConstraint(
            "completed_requests <= admitted_requests",
            name="ck_monthly_results_completed_within_admitted",
        ),
        sa.CheckConstraint(
            "rejected_requests = total_requests - admitted_requests",
            name="ck_monthly_results_rejected_consistent",
        ),
        sa.CheckConstraint(
            "unfinished_requests = admitted_requests - completed_requests",
            name="ck_monthly_results_unfinished_consistent",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(policy_params) = 'object'",
            name="ck_monthly_results_policy_params_object",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["simulation_sessions.id"],
            name="fk_monthly_results_session_id_simulation_sessions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_monthly_results"),
        sa.UniqueConstraint(
            "session_id",
            "month",
            name="uq_monthly_results_session_month",
        ),
        sa.UniqueConstraint(
            "session_id",
            "idempotency_key",
            name="uq_monthly_results_session_idempotency_key",
        ),
    )

    connection = op.get_bind()
    enrollment_ids = connection.execute(
        sa.text("SELECT id FROM enrollments ORDER BY id")
    ).scalars()
    session_rows = [
        {
            "id": uuid.uuid4(),
            "enrollment_id": enrollment_id,
            "completed_months": 0,
        }
        for enrollment_id in enrollment_ids
    ]
    if session_rows:
        simulation_sessions = sa.table(
            "simulation_sessions",
            sa.column("id", sa.Uuid()),
            sa.column("enrollment_id", sa.Uuid()),
            sa.column("completed_months", sa.SmallInteger()),
        )
        op.bulk_insert(simulation_sessions, session_rows)


def downgrade() -> None:
    op.drop_table("monthly_results")
    op.drop_index(
        "ix_simulation_sessions_completed_months",
        table_name="simulation_sessions",
    )
    op.drop_table("simulation_sessions")
