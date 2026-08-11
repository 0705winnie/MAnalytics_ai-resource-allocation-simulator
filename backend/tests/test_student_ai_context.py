"""Privacy and semantic contract tests for authoritative student AI context."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

from app.core.auth import AuthContext
from app.models import CourseInstance, Enrollment, User
from app.models.enums import EnrollmentStatus, UserRole
from app.services import student_ai_context
from app.services.prompt_templates import build_system_prompt
from app.services.student_ai_context import StudentAIContextAssembler


def _type_result(name: str, revenue: float) -> SimpleNamespace:
    value = {
        "type": name,
        "total_requests": 10,
        "admitted_requests": 7,
        "completed_requests": 6,
        "total_revenue": revenue,
    }
    return SimpleNamespace(**value, model_dump=lambda: dict(value))


def _month(month: int) -> SimpleNamespace:
    return SimpleNamespace(
        month=month,
        policy_code=f"def admission_policy(*args):\n    return {month}",
        params={"threshold": float(month)},
        policy_hash=f"own-policy-hash-{month}",
        total_requests=10 + month,
        admitted_requests=7,
        completed_requests=6,
        rejected_requests=3 + month,
        total_revenue=1000.0 * month,
        unfinished_requests=1,
        unfinished_value=50.0,
        warnings=[f"own-warning-{month}"],
        by_type=[_type_result("VIP", 1000.0 * month)],
        avg_utilization={"1": 0.5},
        peak_utilization={"1": 0.8},
    )


def _official_state() -> SimpleNamespace:
    months = [_month(month) for month in range(1, 5)]
    cumulative_type = _type_result("VIP", 10000.0)
    return SimpleNamespace(
        completed_months=4,
        next_month=5,
        status="in_progress",
        monthly_results=months,
        cumulative=SimpleNamespace(
            total_requests=50,
            admitted_requests=28,
            completed_requests=24,
            rejected_requests=22,
            total_revenue=10000.0,
            total_unfinished_requests=4,
            total_unfinished_value=200.0,
            warnings_count=4,
            by_type=[cumulative_type],
        ),
    )


def _auth_context() -> AuthContext:
    owner_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        berkeley_username="student-a",
        role=UserRole.STUDENT,
    )
    course = CourseInstance(
        id=uuid.uuid4(),
        course_code="AI-CONTEXT",
        course_name="AI Context Course",
        semester="Fall 2026",
        created_by=owner_id,
    )
    enrollment = Enrollment(
        id=uuid.uuid4(),
        user_id=user.id,
        course_id=course.id,
        nickname="Student A Nickname",
        status=EnrollmentStatus.ACTIVE,
    )
    return AuthContext(user=user, course=course, enrollment=enrollment)


def test_context_contains_own_progress_history_and_distinct_draft(monkeypatch):
    auth = _auth_context()
    requested_enrollments = []

    def fake_official_session(_db, enrollment_id):
        requested_enrollments.append(enrollment_id)
        return _official_state()

    monkeypatch.setattr(
        student_ai_context,
        "get_official_session_response",
        fake_official_session,
    )
    context = StudentAIContextAssembler(SimpleNamespace()).build(
        auth,
        message="Why did Month 4 perform poorly?",
        draft_policy_code="CURRENT-DRAFT-POLICY-A",
        draft_params={"draft_threshold": 9.0},
    )

    assert requested_enrollments == [auth.enrollment.id]
    assert context["official_progress"] == {
        "completed_months": 4,
        "next_month": 5,
        "status": "in_progress",
    }
    assert context["official_cumulative_metrics"]["total_revenue"] == 10000.0
    assert [item["month"] for item in context["official_monthly_history"]] == [1, 2, 3, 4]
    assert context["latest_executed_policy"]["month"] == 4
    assert context["latest_executed_policy"]["policy_code"].endswith("return 4")
    assert context["requested_historical_policies"] == [
        {
            "month": 4,
            "policy_code": "def admission_policy(*args):\n    return 4",
            "params": {"threshold": 4.0},
            "policy_hash": "own-policy-hash-4",
        }
    ]
    assert context["current_editor_draft"] == {
        "authoritative": False,
        "has_been_executed": False,
        "policy_code": "CURRENT-DRAFT-POLICY-A",
        "params": {"draft_threshold": 9.0},
    }

    prompt = build_system_prompt(context)
    assert "LATEST EXECUTED POLICY" in prompt
    assert "CURRENT EDITOR DRAFT" in prompt
    assert "CURRENT-DRAFT-POLICY-A" in prompt
    assert "own-warning-4" in prompt


def test_context_cannot_include_another_students_private_data(monkeypatch):
    auth = _auth_context()
    student_b_private_values = {
        "Student B Secret Nickname",
        "STUDENT-B-PRIVATE-POLICY",
        "987654.32",
    }

    monkeypatch.setattr(
        student_ai_context,
        "get_official_session_response",
        lambda _db, enrollment_id: (
            _official_state()
            if enrollment_id == auth.enrollment.id
            else (_ for _ in ()).throw(AssertionError("peer enrollment queried"))
        ),
    )
    context = StudentAIContextAssembler(SimpleNamespace()).build(
        auth,
        message="How am I doing?",
        draft_policy_code="CURRENT-DRAFT-POLICY-A",
        draft_params={},
    )
    serialized = json.dumps(context, sort_keys=True)

    assert all(private not in serialized for private in student_b_private_values)
    assert "Student A Nickname" not in serialized
