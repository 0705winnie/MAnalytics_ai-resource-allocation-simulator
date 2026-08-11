"""Add legacy submission month count.

Revision ID: 0003_months_completed
Revises: 0002_submissions
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_months_completed"
down_revision: str | None = "0002_submissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Reproduce the legacy production schema without a server default."""

    op.add_column(
        "submissions",
        sa.Column("months_completed", sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE submissions "
            "SET months_completed = 12 "
            "WHERE months_completed IS NULL"
        )
    )
    op.alter_column(
        "submissions",
        "months_completed",
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("submissions", "months_completed")
