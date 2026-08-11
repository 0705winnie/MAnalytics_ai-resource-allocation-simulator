"""Make Student accounts course-specific while keeping Instructors global.

Revision ID: 0006_course_scoped_students
Revises: 0005_llm_daily_usage
"""

from collections.abc import Sequence
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "0006_course_scoped_students"
down_revision: str | None = "0005_llm_daily_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("users", sa.Column("course_id", sa.Uuid(), nullable=True))

    # Existing course values become the canonical display components. Generated
    # lowercase columns remain lookup/uniqueness keys.
    bind.execute(sa.text("UPDATE course_instances SET course_code = upper(btrim(course_code)), semester = upper(btrim(semester))"))
    op.add_column(
        "course_instances",
        sa.Column(
            "semester_normalized", sa.String(length=64),
            sa.Computed("lower(btrim(semester))", persisted=True), nullable=False,
        ),
    )
    op.drop_constraint(
        "uq_course_instances_course_code_normalized", "course_instances", type_="unique"
    )
    op.create_unique_constraint(
        "uq_course_instances_code_semester_normalized", "course_instances",
        ["course_code_normalized", "semester_normalized"],
    )
    op.create_check_constraint(
        "ck_course_instances_semester_length", "course_instances",
        "char_length(btrim(semester)) BETWEEN 1 AND 64",
    )

    # Student identities are about to be split into one User per course. Remove
    # the legacy global username uniqueness rule first so those copies can keep
    # their original Berkeley username. Instructors remain globally unique.
    op.drop_constraint("uq_users_berkeley_username", "users", type_="unique")
    op.create_index(
        "uq_users_instructor_username", "users", ["berkeley_username"],
        unique=True, postgresql_where=sa.text("role = 'instructor'"),
    )

    students = bind.execute(sa.text(
        "SELECT id, berkeley_username, password_hash, is_active, created_at, updated_at "
        "FROM users WHERE role = 'student' ORDER BY created_at, id"
    )).mappings().all()
    for student in students:
        enrollments = bind.execute(sa.text(
            "SELECT id, course_id FROM enrollments WHERE user_id = :user_id ORDER BY created_at, id"
        ), {"user_id": student["id"]}).mappings().all()
        if not enrollments:
            bind.execute(sa.text("DELETE FROM llm_daily_usage WHERE user_id = :user_id"), {"user_id": student["id"]})
            bind.execute(sa.text("DELETE FROM users WHERE id = :user_id"), {"user_id": student["id"]})
            continue
        bind.execute(sa.text("UPDATE users SET course_id = :course_id WHERE id = :user_id"), {
            "course_id": enrollments[0]["course_id"], "user_id": student["id"],
        })
        for enrollment in enrollments[1:]:
            clone_id = uuid.uuid4()
            bind.execute(sa.text(
                "INSERT INTO users (id, berkeley_username, password_hash, role, is_active, created_at, updated_at, course_id) "
                "VALUES (:id, :username, :password_hash, 'student', :is_active, :created_at, :updated_at, :course_id)"
            ), {
                "id": clone_id, "username": student["berkeley_username"],
                "password_hash": student["password_hash"], "is_active": student["is_active"],
                "created_at": student["created_at"], "updated_at": student["updated_at"],
                "course_id": enrollment["course_id"],
            })
            bind.execute(sa.text("UPDATE enrollments SET user_id = :user_id WHERE id = :enrollment_id"), {
                "user_id": clone_id, "enrollment_id": enrollment["id"],
            })

    # Legacy Student usage cannot be assigned unambiguously after a split.
    bind.execute(sa.text(
        "DELETE FROM llm_daily_usage WHERE user_id IN (SELECT id FROM users WHERE role = 'student')"
    ))

    op.create_foreign_key(
        "fk_users_course_id_course_instances", "users", "course_instances",
        ["course_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_unique_constraint("uq_users_id_course_id", "users", ["id", "course_id"])
    op.create_check_constraint(
        "ck_users_role_course_scope", "users",
        "(role = 'student' AND course_id IS NOT NULL) OR (role = 'instructor' AND course_id IS NULL)",
    )
    op.create_index(
        "uq_users_student_course_username", "users", ["course_id", "berkeley_username"],
        unique=True, postgresql_where=sa.text("role = 'student'"),
    )
    op.drop_constraint("uq_enrollments_course_user", "enrollments", type_="unique")
    op.drop_constraint("fk_enrollments_user_id_users", "enrollments", type_="foreignkey")
    op.create_unique_constraint("uq_enrollments_user_id", "enrollments", ["user_id"])
    op.create_foreign_key(
        "fk_enrollments_user_course_users", "enrollments", "users",
        ["user_id", "course_id"], ["id", "course_id"], ondelete="RESTRICT",
    )


def downgrade() -> None:
    bind = op.get_bind()
    duplicate_username = bind.scalar(sa.text(
        "SELECT berkeley_username FROM users GROUP BY berkeley_username HAVING count(*) > 1 LIMIT 1"
    ))
    duplicate_course_code = bind.scalar(sa.text(
        "SELECT course_code_normalized FROM course_instances GROUP BY course_code_normalized "
        "HAVING count(*) > 1 LIMIT 1"
    ))
    if duplicate_username is not None or duplicate_course_code is not None:
        raise RuntimeError(
            "Unsafe 0006 downgrade refused: course-scoped identities or repeated course codes exist"
        )

    op.drop_constraint("fk_enrollments_user_course_users", "enrollments", type_="foreignkey")
    op.drop_constraint("uq_enrollments_user_id", "enrollments", type_="unique")
    op.create_foreign_key(
        "fk_enrollments_user_id_users", "enrollments", "users",
        ["user_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_enrollments_course_user", "enrollments", ["course_id", "user_id"]
    )
    op.drop_index("uq_users_instructor_username", table_name="users")
    op.drop_index("uq_users_student_course_username", table_name="users")
    op.drop_constraint("ck_users_role_course_scope", "users", type_="check")
    op.drop_constraint("uq_users_id_course_id", "users", type_="unique")
    op.drop_constraint("fk_users_course_id_course_instances", "users", type_="foreignkey")
    op.create_unique_constraint(
        "uq_users_berkeley_username", "users", ["berkeley_username"]
    )
    op.drop_column("users", "course_id")

    op.drop_constraint(
        "uq_course_instances_code_semester_normalized", "course_instances", type_="unique"
    )
    op.drop_constraint(
        "ck_course_instances_semester_length", "course_instances", type_="check"
    )
    op.create_unique_constraint(
        "uq_course_instances_course_code_normalized", "course_instances",
        ["course_code_normalized"],
    )
    op.drop_column("course_instances", "semester_normalized")
