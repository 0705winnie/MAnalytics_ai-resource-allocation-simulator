"""Add per-student daily paid LLM usage accounting.

Revision ID: 0005_llm_daily_usage
Revises: 0004_simulation_persistence
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_llm_daily_usage"
down_revision: str | None = "0004_simulation_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_daily_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("call_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(12, 6), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "call_count >= 0 AND input_tokens >= 0 AND output_tokens >= 0 AND estimated_cost >= 0",
            name="ck_llm_daily_usage_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_llm_daily_usage_user_id_users", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_llm_daily_usage"),
        sa.UniqueConstraint("user_id", "usage_date", name="uq_llm_daily_usage_user_date"),
    )
    op.create_index("ix_llm_daily_usage_usage_date", "llm_daily_usage", ["usage_date"])


def downgrade() -> None:
    op.drop_index("ix_llm_daily_usage_usage_date", table_name="llm_daily_usage")
    op.drop_table("llm_daily_usage")
