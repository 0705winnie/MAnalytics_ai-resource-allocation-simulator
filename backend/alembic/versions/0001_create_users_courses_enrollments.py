"""Create users, course instances, and enrollments.

Revision ID: 0001_account_foundation
Revises:
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_account_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


user_role = sa.Enum(
    "student",
    "instructor",
    name="user_role",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)

enrollment_status = sa.Enum(
    "pending",
    "active",
    "disabled",
    name="enrollment_status",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("berkeley_username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column(
            "role",
            user_role,
            server_default="student",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
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
        sa.CheckConstraint(
            "char_length(berkeley_username) BETWEEN 1 AND 64",
            name="ck_users_berkeley_username_length",
        ),
        sa.CheckConstraint(
            "berkeley_username = lower(btrim(berkeley_username))",
            name="ck_users_berkeley_username_normalized",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint(
            "berkeley_username",
            name="uq_users_berkeley_username",
        ),
    )

    op.create_table(
        "course_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_code", sa.String(length=64), nullable=False),
        sa.Column(
            "course_code_normalized",
            sa.String(length=64),
            sa.Computed("lower(btrim(course_code))", persisted=True),
            nullable=False,
        ),
        sa.Column("course_name", sa.String(length=255), nullable=False),
        sa.Column("semester", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
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
        sa.CheckConstraint(
            "char_length(btrim(course_code)) BETWEEN 1 AND 64",
            name="ck_course_instances_course_code_length",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_course_instances_created_by_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_course_instances"),
        sa.UniqueConstraint(
            "course_code_normalized",
            name="uq_course_instances_course_code_normalized",
        ),
    )

    op.create_table(
        "enrollments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("nickname", sa.String(length=30), nullable=True),
        sa.Column(
            "nickname_normalized",
            sa.String(length=30),
            sa.Computed("lower(btrim(nickname))", persisted=True),
            nullable=True,
        ),
        sa.Column("activation_code_hash", sa.String(length=255), nullable=True),
        sa.Column(
            "activation_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "activation_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            enrollment_status,
            server_default="pending",
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
        sa.CheckConstraint(
            "nickname IS NULL OR "
            "(nickname = btrim(nickname) "
            "AND char_length(nickname) BETWEEN 3 AND 30)",
            name="ck_enrollments_nickname_normalized_length",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["course_instances.id"],
            name="fk_enrollments_course_id_course_instances",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_enrollments_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_enrollments"),
        sa.UniqueConstraint(
            "course_id",
            "nickname_normalized",
            name="uq_enrollments_course_nickname_normalized",
        ),
        sa.UniqueConstraint(
            "course_id",
            "user_id",
            name="uq_enrollments_course_user",
        ),
    )


def downgrade() -> None:
    op.drop_table("enrollments")
    op.drop_table("course_instances")
    op.drop_table("users")
