"""Shared official-result ranking queries for student and instructor views."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import Enrollment, MonthlyResult, SimulationSession, User
from app.models.enums import EnrollmentStatus
from app.schemas.leaderboards import RankedEnrollmentRecord


def completed_months_for_enrollment(
    db: Session,
    enrollment_id: uuid.UUID,
) -> int:
    value = db.scalar(
        select(SimulationSession.completed_months).where(
            SimulationSession.enrollment_id == enrollment_id
        )
    )
    return int(value or 0)


def ranked_course_stage(
    db: Session,
    *,
    course_id: uuid.UUID,
    stage: int,
) -> list[RankedEnrollmentRecord]:
    """Rank one official course stage using SQL RANK tie semantics."""

    aggregate = (
        select(
            Enrollment.id.label("enrollment_id"),
            Enrollment.nickname.label("nickname"),
            SimulationSession.completed_months.label("completed_months"),
            func.coalesce(func.sum(MonthlyResult.total_revenue), 0).label(
                "cumulative_revenue"
            ),
            SimulationSession.last_completed_at.label("last_activity"),
        )
        .join(User, User.id == Enrollment.user_id)
        .join(
            SimulationSession,
            SimulationSession.enrollment_id == Enrollment.id,
        )
        .outerjoin(
            MonthlyResult,
            and_(
                MonthlyResult.session_id == SimulationSession.id,
                MonthlyResult.month <= stage,
            ),
        )
        .where(
            Enrollment.course_id == course_id,
            Enrollment.status == EnrollmentStatus.ACTIVE,
            User.is_active.is_(True),
            Enrollment.nickname.is_not(None),
            SimulationSession.completed_months >= stage,
        )
        .group_by(
            Enrollment.id,
            Enrollment.nickname,
            SimulationSession.completed_months,
            SimulationSession.last_completed_at,
        )
        .subquery()
    )
    rank_column = func.rank().over(
        order_by=aggregate.c.cumulative_revenue.desc()
    ).label("rank")
    rows = db.execute(
        select(
            aggregate.c.enrollment_id,
            rank_column,
            aggregate.c.nickname,
            aggregate.c.completed_months,
            aggregate.c.cumulative_revenue,
            aggregate.c.last_activity,
        ).order_by(
            rank_column.asc(),
            func.lower(aggregate.c.nickname).asc(),
            aggregate.c.enrollment_id.asc(),
        )
    ).all()
    return [
        RankedEnrollmentRecord(
            enrollment_id=row.enrollment_id,
            rank=int(row.rank),
            nickname=row.nickname,
            completed_months=int(row.completed_months),
            cumulative_revenue=float(row.cumulative_revenue),
            last_activity=row.last_activity,
        )
        for row in rows
    ]
