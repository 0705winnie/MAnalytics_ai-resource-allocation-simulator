"""Focused coverage for explicit enrollment and course deletion scope."""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from alembic import command
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    CourseInstance,
    Enrollment,
    LLMDailyUsage,
    MonthlyResult,
    SimulationSession,
    Submission,
    User,
)
from app.models.enums import EnrollmentStatus, UserRole
from app.routers import instructor_courses
from app.services.course_deletions import remove_owned_course, remove_owned_enrollment


@pytest.fixture(scope="module", autouse=True)
def schema(test_alembic_config):
    command.upgrade(test_alembic_config, "head")


def _clear(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        db.execute(delete(MonthlyResult))
        db.execute(delete(SimulationSession))
        db.execute(delete(Submission))
        db.execute(delete(Enrollment))
        db.execute(delete(CourseInstance))
        db.execute(delete(LLMDailyUsage))
        db.execute(delete(User))
        db.commit()


def _add_official_month(db: Session, enrollment: Enrollment) -> SimulationSession:
    simulation_session = SimulationSession(enrollment_id=enrollment.id, completed_months=1)
    db.add(simulation_session)
    db.flush()
    db.add(
        MonthlyResult(
            session_id=simulation_session.id,
            month=1,
            idempotency_key=uuid.uuid4(),
            policy_code="def admission_policy(request, state, history, params): return True",
            policy_params={},
            policy_hash="a" * 64,
            total_requests=1,
            admitted_requests=1,
            completed_requests=1,
            rejected_requests=0,
            total_revenue=Decimal("10"),
            unfinished_requests=0,
            unfinished_value=Decimal("0"),
            avg_utilization={},
            peak_utilization={},
            remaining_capacity={},
            by_type=[],
            warnings=[],
            benchmark_comparison=[],
        )
    )
    db.add(
        Submission(
            enrollment_id=enrollment.id,
            total_revenue=10,
            total_unfinished_requests=0,
            total_unfinished_value=0,
            warnings_count=0,
            months_completed=12,
        )
    )
    return simulation_session


def _seed(factory: sessionmaker[Session]):
    with factory() as db:
        owner = User(berkeley_username="delete-owner", role=UserRole.INSTRUCTOR)
        other_owner = User(berkeley_username="delete-other-owner", role=UserRole.INSTRUCTOR)
        student = User(berkeley_username="delete-student")
        db.add_all([owner, other_owner, student])
        db.flush()
        target = CourseInstance(
            course_code="DELETE-TARGET",
            course_name="Delete Target",
            semester="Test",
            created_by=owner.id,
        )
        retained = CourseInstance(
            course_code="DELETE-RETAIN",
            course_name="Retained Course",
            semester="Test",
            created_by=owner.id,
        )
        db.add_all([target, retained])
        db.flush()
        target_enrollment = Enrollment(
            course_id=target.id,
            user_id=student.id,
            nickname="Delete Target Student",
            status=EnrollmentStatus.ACTIVE,
        )
        retained_enrollment = Enrollment(
            course_id=retained.id,
            user_id=student.id,
            nickname="Retained Student",
            status=EnrollmentStatus.ACTIVE,
        )
        db.add_all([target_enrollment, retained_enrollment])
        db.flush()
        target_session = _add_official_month(db, target_enrollment)
        retained_session = _add_official_month(db, retained_enrollment)
        db.commit()
        return {
            "owner": owner,
            "other_owner": other_owner,
            "student": student,
            "target": target,
            "retained": retained,
            "target_enrollment": target_enrollment,
            "retained_enrollment": retained_enrollment,
            "target_session": target_session,
            "retained_session": retained_session,
        }


def test_remove_enrollment_is_owned_scoped_and_retains_user_and_other_course(test_engine):
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    _clear(factory)
    try:
        seeded = _seed(factory)
        with factory() as db:
            assert remove_owned_enrollment(
                db,
                course_id=seeded["target"].id,
                enrollment_id=seeded["target_enrollment"].id,
                instructor_id=seeded["other_owner"].id,
            ) is False
            db.rollback()
            assert db.get(Enrollment, seeded["target_enrollment"].id) is not None

            assert remove_owned_enrollment(
                db,
                course_id=seeded["target"].id,
                enrollment_id=seeded["target_enrollment"].id,
                instructor_id=seeded["owner"].id,
            ) is True
            db.commit()
            assert db.get(Enrollment, seeded["target_enrollment"].id) is None
            assert db.get(SimulationSession, seeded["target_session"].id) is None
            assert db.get(User, seeded["student"].id) is not None
            assert db.get(Enrollment, seeded["retained_enrollment"].id) is not None
            assert db.get(SimulationSession, seeded["retained_session"].id) is not None
            assert db.scalar(select(func.count()).select_from(MonthlyResult)) == 1
    finally:
        _clear(factory)


def test_delete_course_is_owned_scoped_and_retains_users_and_other_course(test_engine):
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    _clear(factory)
    try:
        seeded = _seed(factory)
        with factory() as db:
            assert remove_owned_course(
                db,
                course_id=seeded["target"].id,
                instructor_id=seeded["other_owner"].id,
            ) is False
            db.rollback()
            assert db.get(CourseInstance, seeded["target"].id) is not None

            assert remove_owned_course(
                db,
                course_id=seeded["target"].id,
                instructor_id=seeded["owner"].id,
            ) is True
            db.commit()
            assert db.get(CourseInstance, seeded["target"].id) is None
            assert db.get(User, seeded["student"].id) is not None
            assert db.get(CourseInstance, seeded["retained"].id) is not None
            assert db.get(Enrollment, seeded["retained_enrollment"].id) is not None
            assert db.get(SimulationSession, seeded["retained_session"].id) is not None
            assert db.scalar(select(func.count()).select_from(MonthlyResult)) == 1
    finally:
        _clear(factory)


def test_delete_course_route_rolls_back_on_commit_failure(monkeypatch):
    instructor = User(id=uuid.uuid4(), berkeley_username="rollback-owner", role=UserRole.INSTRUCTOR)
    db = MagicMock(spec=Session)
    db.commit.side_effect = SQLAlchemyError("commit failed")
    monkeypatch.setattr(instructor_courses, "remove_owned_course", lambda *args, **kwargs: True)

    with pytest.raises(HTTPException) as exc_info:
        instructor_courses.delete_course(uuid.uuid4(), db, instructor)

    assert exc_info.value.status_code == 500
    db.rollback.assert_called_once_with()
