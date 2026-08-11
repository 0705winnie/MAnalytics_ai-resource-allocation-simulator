"""Focused integration coverage for official progress and shared rankings."""

import uuid
from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    CourseInstance,
    Enrollment,
    MonthlyResult,
    SimulationSession,
    Submission,
    User,
)
from app.models.enums import EnrollmentStatus, UserRole
from app.routers.instructor_progress import list_course_progress
from app.services.leaderboards import ranked_course_stage


@pytest.fixture(scope="module", autouse=True)
def account_schema(test_alembic_config):
    command.upgrade(test_alembic_config, "head")


def _clear(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        db.execute(delete(MonthlyResult))
        db.execute(delete(SimulationSession))
        db.execute(delete(Submission))
        db.execute(delete(Enrollment))
        db.execute(delete(CourseInstance))
        db.execute(delete(User))
        db.commit()


def _monthly_result(session_id: uuid.UUID, month: int, revenue: int) -> MonthlyResult:
    return MonthlyResult(
        session_id=session_id,
        month=month,
        idempotency_key=uuid.uuid4(),
        policy_code="def admission_policy(request, state, history, params): return True",
        policy_params={},
        policy_hash="a" * 64,
        total_requests=1,
        admitted_requests=1,
        completed_requests=1,
        rejected_requests=0,
        total_revenue=Decimal(revenue),
        unfinished_requests=0,
        unfinished_value=Decimal(0),
        avg_utilization={},
        peak_utilization={},
        remaining_capacity={},
        by_type=[],
        warnings=["warning"] if month == 1 else [],
        benchmark_comparison=[],
    )


def test_progress_and_rankings_share_official_monthly_results(test_engine):
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    _clear(factory)
    try:
        with factory() as db:
            instructor = User(
                berkeley_username="phase45-instructor",
                role=UserRole.INSTRUCTOR,
            )
            students = [
                User(berkeley_username=f"phase45-student-{index}")
                for index in range(4)
            ]
            db.add_all([instructor, *students])
            db.flush()
            course = CourseInstance(
                course_code="PHASE45",
                course_name="Phase 4 and 5",
                semester="Test",
                created_by=instructor.id,
            )
            db.add(course)
            db.flush()
            enrollments = [
                Enrollment(
                    course_id=course.id,
                    user_id=student.id,
                    nickname=f"Player {index}",
                    status=EnrollmentStatus.DISABLED if index == 2 else EnrollmentStatus.ACTIVE,
                )
                for index, student in enumerate(students)
            ]
            db.add_all(enrollments)
            db.flush()
            sessions = [
                SimulationSession(enrollment_id=enrollments[index].id, completed_months=2)
                for index in range(3)
            ]
            db.add_all(sessions)
            db.flush()
            for session, revenues in zip(
                sessions,
                ((100, 200), (150, 150), (500, 500)),
                strict=True,
            ):
                db.add_all(
                    _monthly_result(session.id, month, revenue)
                    for month, revenue in enumerate(revenues, start=1)
                )
            db.commit()

            ranked = ranked_course_stage(db, course_id=course.id, stage=2)
            assert [(row.rank, row.nickname, row.cumulative_revenue) for row in ranked] == [
                (1, "Player 0", 300.0),
                (1, "Player 1", 300.0),
            ]

            progress = list_course_progress(course.id, db, instructor, 0, 50)
            assert progress.total == 4
            by_nickname = {row.nickname: row for row in progress.items}
            assert by_nickname["Player 0"].completed_months == 2
            assert by_nickname["Player 0"].cumulative_revenue == 300.0
            assert by_nickname["Player 0"].warnings_count == 1
            assert by_nickname["Player 0"].simulation_status == "in_progress"
            assert by_nickname["Player 2"].enrollment_status == EnrollmentStatus.DISABLED
            assert by_nickname["Player 3"].completed_months == 0
            assert by_nickname["Player 3"].simulation_status == "not_started"
    finally:
        _clear(factory)
