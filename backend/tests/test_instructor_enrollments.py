import csv
import io
import re
import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import ACCESS_COOKIE_NAME, create_access_token
from app.core.config import AuthSettings, get_auth_settings
from app.db.session import get_db
from app.main import create_app
from app.models import CourseInstance, Enrollment, User
from app.models.enums import EnrollmentStatus, UserRole
from app.routers import instructor_enrollments
from app.services.activation_codes import (
    ACTIVATION_CODE_TTL,
    issue_activation_code,
    verify_activation_code,
)


TEST_JWT_SECRET = "test-only-enrollment-api-signing-secret-32-characters"
INSTRUCTOR = "enrollment-instructor"
OTHER_INSTRUCTOR = "other-enrollment-instructor"


def _auth_settings() -> AuthSettings:
    return AuthSettings(
        _env_file=None,
        jwt_secret=SecretStr(TEST_JWT_SECRET),
        auth_cookie_secure=False,
        access_token_minutes=30,
        frontend_origin="http://frontend.test",
    )


def _clear_account_tables(
    factory: sessionmaker[Session],
    test_database_url: URL,
) -> None:
    assert test_database_url.database is not None
    assert test_database_url.database.endswith("_test")
    with factory() as session:
        session.execute(delete(Enrollment))
        session.execute(delete(CourseInstance))
        session.execute(delete(User))
        session.commit()


@pytest.fixture(scope="module", autouse=True)
def account_schema(test_alembic_config):
    command.upgrade(test_alembic_config, "head")


@pytest.fixture
def enrollment_session_factory(
    test_engine: Engine,
    test_database_url: URL,
) -> Generator[sessionmaker[Session], None, None]:
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    _clear_account_tables(factory, test_database_url)
    yield factory
    _clear_account_tables(factory, test_database_url)


@pytest.fixture
def auth_settings() -> AuthSettings:
    return _auth_settings()


@pytest.fixture
def app_factory(
    enrollment_session_factory: sessionmaker[Session],
) -> Callable[[AuthSettings], object]:
    def build(settings: AuthSettings):
        api = create_app(settings)

        def override_get_db() -> Generator[Session, None, None]:
            with enrollment_session_factory() as session:
                yield session

        api.dependency_overrides[get_db] = override_get_db
        api.dependency_overrides[get_auth_settings] = lambda: settings
        return api

    return build


@pytest.fixture
def client(app_factory, auth_settings) -> Generator[TestClient, None, None]:
    with TestClient(app_factory(auth_settings)) as test_client:
        yield test_client


def _create_user(
    factory: sessionmaker[Session],
    username: str,
    *,
    role: UserRole = UserRole.STUDENT,
    is_active: bool = True,
) -> User:
    user = User(
        berkeley_username=username,
        role=role,
        is_active=is_active,
    )
    with factory() as session:
        session.add(user)
        session.commit()
    return user


def _create_course(
    factory: sessionmaker[Session],
    owner: User,
    *,
    code: str = "IEOR150-Enrollments",
    is_active: bool = True,
) -> CourseInstance:
    course = CourseInstance(
        course_code=code,
        course_name="Resource Allocation",
        semester="Fall 2026",
        created_by=owner.id,
        is_active=is_active,
    )
    with factory() as session:
        session.add(course)
        session.commit()
    return course


def _create_enrollment(
    factory: sessionmaker[Session],
    course: CourseInstance,
    user: User,
    *,
    status: EnrollmentStatus = EnrollmentStatus.PENDING,
    nickname: str | None = None,
    issue_code: bool = False,
    activated_at: datetime | None = None,
    enrollment_id: uuid.UUID | None = None,
) -> tuple[Enrollment, str | None]:
    enrollment = Enrollment(
        id=enrollment_id or uuid.uuid4(),
        course_id=course.id,
        user_id=user.id,
        nickname=nickname,
        status=EnrollmentStatus.PENDING if issue_code else status,
        activation_used_at=activated_at,
    )
    code = issue_activation_code(enrollment) if issue_code else None
    enrollment.status = status
    with factory() as session:
        session.add(enrollment)
        session.commit()
    return enrollment, code


def _authenticate(
    client: TestClient,
    user: User,
    settings: AuthSettings,
) -> None:
    client.cookies.set(
        ACCESS_COOKIE_NAME,
        create_access_token(user.id, user.role, settings),
    )


def _enrollment_path(
    course: CourseInstance,
    enrollment: Enrollment,
    suffix: str,
    *,
    api: bool = True,
) -> str:
    prefix = "/api" if api else ""
    return (
        f"{prefix}/instructor/courses/{course.id}/enrollments/"
        f"{enrollment.id}/{suffix}"
    )


def _csv_row(response) -> dict[str, str]:
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 1
    return rows[0]


def test_student_list_is_course_scoped_safe_sorted_paginated_and_allows_inactive_course(
    client,
    enrollment_session_factory,
    auth_settings,
):
    instructor = _create_user(
        enrollment_session_factory,
        INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    course = _create_course(
        enrollment_session_factory,
        instructor,
        is_active=False,
    )
    other_course = _create_course(
        enrollment_session_factory,
        instructor,
        code="IEOR150-Other",
    )
    activated_at = datetime.now(UTC) - timedelta(days=1)
    charlie = _create_user(enrollment_session_factory, "charlie")
    alpha = _create_user(enrollment_session_factory, "alpha")
    bravo = _create_user(enrollment_session_factory, "bravo")
    outsider = _create_user(enrollment_session_factory, "outsider")
    _create_enrollment(
        enrollment_session_factory,
        course,
        charlie,
        status=EnrollmentStatus.PENDING,
        issue_code=True,
        enrollment_id=uuid.UUID(int=3),
    )
    _create_enrollment(
        enrollment_session_factory,
        course,
        alpha,
        status=EnrollmentStatus.ACTIVE,
        activated_at=activated_at,
        enrollment_id=uuid.UUID(int=1),
    )
    _create_enrollment(
        enrollment_session_factory,
        course,
        bravo,
        status=EnrollmentStatus.DISABLED,
        activated_at=activated_at,
        enrollment_id=uuid.UUID(int=2),
    )
    _create_enrollment(
        enrollment_session_factory,
        other_course,
        outsider,
        enrollment_id=uuid.UUID(int=4),
    )
    _authenticate(client, instructor, auth_settings)

    full = client.get(f"/api/instructor/courses/{course.id}/students")
    page = client.get(
        f"/api/instructor/courses/{course.id}/students",
        params={"offset": 1, "limit": 2},
    )

    assert full.status_code == page.status_code == 200
    assert [item["berkeley_username"] for item in full.json()["items"]] == [
        "alpha",
        "bravo",
        "charlie",
    ]
    by_username = {
        item["berkeley_username"]: item for item in full.json()["items"]
    }
    assert by_username["alpha"]["status"] == "active"
    assert by_username["alpha"]["activated"] is True
    assert by_username["bravo"]["status"] == "disabled"
    assert by_username["bravo"]["activated"] is True
    assert by_username["charlie"]["status"] == "pending"
    assert by_username["charlie"]["activated"] is False
    assert page.json()["total"] == 3
    assert page.json()["offset"] == 1
    assert page.json()["limit"] == 2
    assert [item["berkeley_username"] for item in page.json()["items"]] == [
        "bravo",
        "charlie",
    ]
    safe_keys = {
        "enrollment_id",
        "berkeley_username",
        "nickname",
        "status",
        "user_is_active",
        "activated",
        "activation_expires_at",
        "activation_used_at",
        "created_at",
    }
    assert all(set(item) == safe_keys for item in full.json()["items"])
    response_text = full.text.lower()
    assert "password_hash" not in response_text
    assert "activation_code_hash" not in response_text
    assert "jwt" not in response_text
    assert str(alpha.id) not in full.text
    assert str(instructor.id) not in full.text


def test_student_list_hides_unowned_and_missing_courses(
    client,
    enrollment_session_factory,
    auth_settings,
):
    instructor = _create_user(
        enrollment_session_factory,
        INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    other = _create_user(
        enrollment_session_factory,
        OTHER_INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    other_course = _create_course(enrollment_session_factory, other)
    _authenticate(client, instructor, auth_settings)

    unowned = client.get(
        f"/api/instructor/courses/{other_course.id}/students"
    )
    missing = client.get(
        f"/api/instructor/courses/{uuid.uuid4()}/students"
    )

    assert unowned.status_code == missing.status_code == 404
    assert unowned.json() == missing.json() == {
        "detail": "Course or enrollment not found"
    }


def test_pending_student_activation_regeneration_invalidates_old_code(
    client,
    enrollment_session_factory,
    auth_settings,
):
    instructor = _create_user(
        enrollment_session_factory,
        INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    student = _create_user(enrollment_session_factory, "pending-student")
    course = _create_course(
        enrollment_session_factory,
        instructor,
        code="-FormulaCourse",
    )
    enrollment, old_code = _create_enrollment(
        enrollment_session_factory,
        course,
        student,
        issue_code=True,
    )
    assert old_code is not None
    _authenticate(client, instructor, auth_settings)
    before = datetime.now(UTC)

    response = client.post(
        _enrollment_path(course, enrollment, "activation/regenerate")
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="regenerated-activation-code.csv"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    row = _csv_row(response)
    new_code = row["activation_code"]
    assert row["berkeley_username"] == student.berkeley_username
    assert row["course_code"] == "'-FormulaCourse"
    assert row["status"] == "regenerated"
    assert re.fullmatch(r"[A-Z2-9]{4}(?:-[A-Z2-9]{4}){2}", new_code)
    assert new_code != old_code
    with enrollment_session_factory() as session:
        stored = session.get(Enrollment, enrollment.id)
        assert stored is not None
        assert not verify_activation_code(stored, old_code)
        assert verify_activation_code(stored, new_code)
        assert stored.activation_code_hash is not None
        assert stored.activation_code_hash != new_code
        assert new_code.replace("-", "") not in stored.activation_code_hash
        assert stored.activation_expires_at is not None
        expiration = stored.activation_expires_at.astimezone(UTC)
        assert before + ACTIVATION_CODE_TTL <= expiration
        assert expiration <= datetime.now(UTC) + ACTIVATION_CODE_TTL


@pytest.mark.parametrize(
    ("enrollment_status", "activated", "user_active", "role", "message"),
    [
        (
            EnrollmentStatus.ACTIVE,
            True,
            True,
            UserRole.STUDENT,
            "password-reset",
        ),
        (
            EnrollmentStatus.DISABLED,
            False,
            True,
            UserRole.STUDENT,
            "Restore",
        ),
        (
            EnrollmentStatus.PENDING,
            False,
            False,
            UserRole.STUDENT,
            "inactive users",
        ),
        (
            EnrollmentStatus.PENDING,
            False,
            True,
            UserRole.INSTRUCTOR,
            "student enrollments",
        ),
    ],
)
def test_regeneration_rejects_ineligible_enrollments(
    enrollment_status,
    activated,
    user_active,
    role,
    message,
    client,
    enrollment_session_factory,
    auth_settings,
):
    instructor = _create_user(
        enrollment_session_factory,
        INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    enrolled_user = _create_user(
        enrollment_session_factory,
        "ineligible-user",
        role=role,
        is_active=user_active,
    )
    course = _create_course(enrollment_session_factory, instructor)
    enrollment, _ = _create_enrollment(
        enrollment_session_factory,
        course,
        enrolled_user,
        status=enrollment_status,
        activated_at=datetime.now(UTC) if activated else None,
    )
    _authenticate(client, instructor, auth_settings)

    response = client.post(
        _enrollment_path(course, enrollment, "activation/regenerate")
    )

    assert response.status_code == 409
    assert message in response.json()["detail"]
    assert "activation_code" not in response.text


def test_regeneration_rejects_inactive_course_and_cross_course_or_owner_ids(
    client,
    enrollment_session_factory,
    auth_settings,
):
    instructor = _create_user(
        enrollment_session_factory,
        INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    other = _create_user(
        enrollment_session_factory,
        OTHER_INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    student = _create_user(enrollment_session_factory, "scoped-student")
    course = _create_course(enrollment_session_factory, instructor)
    same_owner_other_course = _create_course(
        enrollment_session_factory,
        instructor,
        code="IEOR150-SameOwnerOther",
    )
    inactive_course = _create_course(
        enrollment_session_factory,
        instructor,
        code="IEOR150-Inactive",
        is_active=False,
    )
    other_course = _create_course(
        enrollment_session_factory,
        other,
        code="IEOR150-Unowned",
    )
    enrollment, _ = _create_enrollment(
        enrollment_session_factory,
        course,
        student,
        issue_code=True,
    )
    inactive_enrollment, _ = _create_enrollment(
        enrollment_session_factory,
        inactive_course,
        student,
        issue_code=True,
    )
    _authenticate(client, instructor, auth_settings)

    inactive = client.post(
        _enrollment_path(
            inactive_course,
            inactive_enrollment,
            "activation/regenerate",
        )
    )
    wrong_course = client.post(
        _enrollment_path(
            same_owner_other_course,
            enrollment,
            "activation/regenerate",
        )
    )
    unowned = client.post(
        _enrollment_path(other_course, enrollment, "activation/regenerate")
    )

    assert inactive.status_code == 409
    assert wrong_course.status_code == unowned.status_code == 404


@pytest.mark.parametrize("failure_kind", ["render", "commit"])
def test_regeneration_failure_rolls_back_without_leaking_new_code(
    failure_kind,
    monkeypatch,
    client,
    enrollment_session_factory,
    auth_settings,
):
    instructor = _create_user(
        enrollment_session_factory,
        INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    student = _create_user(enrollment_session_factory, "rollback-student")
    course = _create_course(enrollment_session_factory, instructor)
    enrollment, old_code = _create_enrollment(
        enrollment_session_factory,
        course,
        student,
        issue_code=True,
    )
    assert old_code is not None
    _authenticate(client, instructor, auth_settings)
    generated_codes: list[str] = []
    original_renderer = (
        instructor_enrollments.render_regenerated_activation_csv
    )

    def capture_then_render(stored_enrollment, code):
        generated_codes.append(code)
        if failure_kind == "render":
            raise RuntimeError("private render failure")
        return original_renderer(stored_enrollment, code)

    monkeypatch.setattr(
        instructor_enrollments,
        "render_regenerated_activation_csv",
        capture_then_render,
    )
    if failure_kind == "commit":
        original_commit = Session.commit

        def fail_commit(_session):
            raise IntegrityError("safe test statement", {}, Exception("constraint"))

        monkeypatch.setattr(Session, "commit", fail_commit)

    response = client.post(
        _enrollment_path(course, enrollment, "activation/regenerate")
    )
    if failure_kind == "commit":
        monkeypatch.setattr(Session, "commit", original_commit)

    assert generated_codes
    assert response.status_code == (409 if failure_kind == "commit" else 500)
    assert all(code not in response.text for code in generated_codes)
    assert "hash" not in response.text.lower()
    assert "private render failure" not in response.text
    with enrollment_session_factory() as session:
        stored = session.get(Enrollment, enrollment.id)
        assert stored is not None
        assert verify_activation_code(stored, old_code)
        assert all(
            not verify_activation_code(stored, code)
            for code in generated_codes
        )


def test_disable_is_idempotent_course_scoped_and_does_not_disable_user(
    client,
    enrollment_session_factory,
    auth_settings,
):
    instructor = _create_user(
        enrollment_session_factory,
        INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    student = _create_user(enrollment_session_factory, "multi-course-student")
    first_course = _create_course(
        enrollment_session_factory,
        instructor,
        code="IEOR150-First",
    )
    second_course = _create_course(
        enrollment_session_factory,
        instructor,
        code="IEOR150-Second",
    )
    first, _ = _create_enrollment(
        enrollment_session_factory,
        first_course,
        student,
    )
    second, _ = _create_enrollment(
        enrollment_session_factory,
        second_course,
        student,
        status=EnrollmentStatus.ACTIVE,
        activated_at=datetime.now(UTC),
    )
    _authenticate(client, instructor, auth_settings)
    path = _enrollment_path(first_course, first, "status")

    first_response = client.patch(path, json={"enabled": False})
    second_response = client.patch(path, json={"enabled": False})

    assert first_response.status_code == second_response.status_code == 200
    assert first_response.json()["status"] == "disabled"
    assert second_response.json()["status"] == "disabled"
    with enrollment_session_factory() as session:
        assert session.get(User, student.id).is_active is True
        assert session.get(Enrollment, first.id).status == EnrollmentStatus.DISABLED
        assert session.get(Enrollment, second.id).status == EnrollmentStatus.ACTIVE


def test_restore_uses_activation_history_and_never_generates_a_code(
    client,
    enrollment_session_factory,
    auth_settings,
):
    instructor = _create_user(
        enrollment_session_factory,
        INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    activated_student = _create_user(enrollment_session_factory, "activated")
    pending_student = _create_user(enrollment_session_factory, "not-activated")
    course = _create_course(enrollment_session_factory, instructor)
    activated, _ = _create_enrollment(
        enrollment_session_factory,
        course,
        activated_student,
        status=EnrollmentStatus.DISABLED,
        activated_at=datetime.now(UTC),
    )
    pending, _ = _create_enrollment(
        enrollment_session_factory,
        course,
        pending_student,
        status=EnrollmentStatus.DISABLED,
    )
    _authenticate(client, instructor, auth_settings)

    active_response = client.patch(
        _enrollment_path(course, activated, "status"),
        json={"enabled": True},
    )
    pending_response = client.patch(
        _enrollment_path(course, pending, "status"),
        json={"enabled": True},
    )

    assert active_response.status_code == pending_response.status_code == 200
    assert active_response.json()["status"] == "active"
    assert pending_response.json()["status"] == "pending"
    with enrollment_session_factory() as session:
        restored = session.get(Enrollment, pending.id)
        assert restored is not None
        assert restored.activation_code_hash is None
        assert restored.activation_expires_at is None


def test_inactive_user_cannot_be_restored_and_status_payload_is_strict(
    client,
    enrollment_session_factory,
    auth_settings,
):
    instructor = _create_user(
        enrollment_session_factory,
        INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    student = _create_user(
        enrollment_session_factory,
        "inactive-student",
        is_active=False,
    )
    course = _create_course(enrollment_session_factory, instructor)
    enrollment, _ = _create_enrollment(
        enrollment_session_factory,
        course,
        student,
        status=EnrollmentStatus.DISABLED,
    )
    _authenticate(client, instructor, auth_settings)
    path = _enrollment_path(course, enrollment, "status")

    inactive = client.patch(path, json={"enabled": True})
    extra = client.patch(path, json={"enabled": False, "user_id": "ignored"})
    invalid = client.patch(path, json={"enabled": "true"})

    assert inactive.status_code == 409
    assert extra.status_code == invalid.status_code == 422
    with enrollment_session_factory() as session:
        assert session.get(Enrollment, enrollment.id).status == (
            EnrollmentStatus.DISABLED
        )
        assert session.get(User, student.id).is_active is False


def test_nickname_reset_is_idempotent_course_scoped_and_returns_empty_204(
    client,
    enrollment_session_factory,
    auth_settings,
):
    instructor = _create_user(
        enrollment_session_factory,
        INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    student = _create_user(enrollment_session_factory, "nickname-student")
    first_course = _create_course(
        enrollment_session_factory,
        instructor,
        code="IEOR150-Nickname-A",
    )
    second_course = _create_course(
        enrollment_session_factory,
        instructor,
        code="IEOR150-Nickname-B",
    )
    first, _ = _create_enrollment(
        enrollment_session_factory,
        first_course,
        student,
        nickname="First Name",
    )
    second, _ = _create_enrollment(
        enrollment_session_factory,
        second_course,
        student,
        nickname="Second Name",
    )
    _authenticate(client, instructor, auth_settings)
    path = _enrollment_path(first_course, first, "nickname")

    first_response = client.delete(path)
    second_response = client.delete(path)

    assert first_response.status_code == second_response.status_code == 204
    assert first_response.content == second_response.content == b""
    with enrollment_session_factory() as session:
        assert session.get(Enrollment, first.id).nickname is None
        assert session.get(Enrollment, second.id).nickname == "Second Name"


@pytest.mark.parametrize("operation", ["status", "nickname"])
def test_enrollment_write_commit_failure_rolls_back(
    operation,
    monkeypatch,
    client,
    enrollment_session_factory,
    auth_settings,
):
    instructor = _create_user(
        enrollment_session_factory,
        INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    student = _create_user(enrollment_session_factory, "commit-failure-student")
    course = _create_course(enrollment_session_factory, instructor)
    enrollment, _ = _create_enrollment(
        enrollment_session_factory,
        course,
        student,
        nickname="Original Name",
    )
    _authenticate(client, instructor, auth_settings)
    original_commit = Session.commit

    def fail_commit(_session):
        raise IntegrityError("safe test statement", {}, Exception("constraint"))

    monkeypatch.setattr(Session, "commit", fail_commit)
    if operation == "status":
        response = client.patch(
            _enrollment_path(course, enrollment, "status"),
            json={"enabled": False},
        )
    else:
        response = client.delete(
            _enrollment_path(course, enrollment, "nickname")
        )
    monkeypatch.setattr(Session, "commit", original_commit)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "The enrollment could not be updated"
    }
    with enrollment_session_factory() as session:
        stored = session.get(Enrollment, enrollment.id)
        assert stored is not None
        assert stored.status == EnrollmentStatus.PENDING
        assert stored.nickname == "Original Name"


@pytest.mark.parametrize("operation", ["status", "nickname"])
def test_inactive_course_rejects_enrollment_modifications(
    operation,
    client,
    enrollment_session_factory,
    auth_settings,
):
    instructor = _create_user(
        enrollment_session_factory,
        INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    student = _create_user(enrollment_session_factory, "inactive-course-student")
    course = _create_course(
        enrollment_session_factory,
        instructor,
        is_active=False,
    )
    enrollment, _ = _create_enrollment(
        enrollment_session_factory,
        course,
        student,
        nickname="Safe Name",
    )
    _authenticate(client, instructor, auth_settings)

    if operation == "status":
        response = client.patch(
            _enrollment_path(course, enrollment, "status"),
            json={"enabled": False},
        )
    else:
        response = client.delete(
            _enrollment_path(course, enrollment, "nickname")
        )

    assert response.status_code == 409


def test_authentication_role_and_uuid_validation(
    client,
    enrollment_session_factory,
    auth_settings,
):
    instructor = _create_user(
        enrollment_session_factory,
        INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    course = _create_course(enrollment_session_factory, instructor)
    unauthenticated = client.get(
        f"/api/instructor/courses/{course.id}/students"
    )
    student = _create_user(enrollment_session_factory, "auth-student")
    student_enrollment, _ = _create_enrollment(
        enrollment_session_factory,
        course,
        student,
        status=EnrollmentStatus.ACTIVE,
        nickname="Auth Student",
        activated_at=datetime.now(UTC),
    )
    client.cookies.set(
        ACCESS_COOKIE_NAME,
        create_access_token(
            student.id,
            student.role,
            auth_settings,
            course_id=course.id,
            enrollment_id=student_enrollment.id,
        ),
    )
    forbidden = client.get(
        f"/api/instructor/courses/{course.id}/students"
    )
    client.cookies.clear()
    inactive = _create_user(
        enrollment_session_factory,
        "inactive-auth-instructor",
        role=UserRole.INSTRUCTOR,
        is_active=False,
    )
    _authenticate(client, inactive, auth_settings)
    inactive_response = client.get(
        f"/api/instructor/courses/{course.id}/students"
    )
    client.cookies.clear()
    _authenticate(client, instructor, auth_settings)
    invalid_uuid = client.get(
        "/api/instructor/courses/not-a-uuid/students"
    )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert inactive_response.status_code == 401
    assert invalid_uuid.status_code == 422


def test_proxy_paths_share_handlers_and_are_hidden_from_openapi(
    client,
    enrollment_session_factory,
    auth_settings,
):
    instructor = _create_user(
        enrollment_session_factory,
        INSTRUCTOR,
        role=UserRole.INSTRUCTOR,
    )
    student = _create_user(enrollment_session_factory, "proxy-student")
    course = _create_course(enrollment_session_factory, instructor)
    enrollment, _ = _create_enrollment(
        enrollment_session_factory,
        course,
        student,
        nickname="Proxy Name",
        issue_code=True,
    )
    _authenticate(client, instructor, auth_settings)

    listing = client.get(f"/instructor/courses/{course.id}/students")
    status_response = client.patch(
        _enrollment_path(course, enrollment, "status", api=False),
        json={"enabled": True},
    )
    regeneration = client.post(
        _enrollment_path(
            course,
            enrollment,
            "activation/regenerate",
            api=False,
        )
    )
    nickname = client.delete(
        _enrollment_path(course, enrollment, "nickname", api=False)
    )
    paths = client.get("/openapi.json").json()["paths"]

    assert listing.status_code == 200
    assert status_response.status_code == 200
    assert regeneration.status_code == 200
    assert nickname.status_code == 204
    assert "/api/instructor/courses/{course_id}/students" in paths
    assert (
        "/api/instructor/courses/{course_id}/enrollments/"
        "{enrollment_id}/status"
    ) in paths
    assert "/instructor/courses/{course_id}/students" not in paths
    assert (
        "/instructor/courses/{course_id}/enrollments/"
        "{enrollment_id}/status"
    ) not in paths
