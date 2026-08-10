"""Create submissions.

Revision ID: 0002_submissions
Revises: 0001_account_foundation
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_submissions"
down_revision: str | None = "0001_account_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("total_revenue", sa.Float(), nullable=False),
        sa.Column("total_unfinished_requests", sa.Integer(), nullable=False),
        sa.Column("total_unfinished_value", sa.Float(), nullable=False),
        sa.Column("warnings_count", sa.Integer(), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["enrollments.id"],
            name="fk_submissions_enrollment_id_enrollments",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_submissions"),
    )
    op.create_index(
        "ix_submissions_enrollment_id",
        "submissions",
        ["enrollment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_submissions_enrollment_id", table_name="submissions")
    op.drop_table("submissions")
