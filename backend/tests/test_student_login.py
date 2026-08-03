"""Phase 3C integration tests for course-scoped Student regular login."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime

import jwt
import pytest
from alembic import command
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, delete
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.activation_auth import ACTIVATION_COOKIE_NAME
from app.core.auth import (
    ACCESS_COOKIE_NAME,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
)
from app.core.config import AuthSettings, get_auth_settings
from app.core.security import DUMMY_PASSWORD_HASH, hash_password
from app.db.session import get_db
from app.main import create_app
from app.models import CourseInstance, Enrollment, User
from app.models.enums import EnrollmentStatus, UserRole
from app.services import student_authentication


TEST_JWT_SECRET = "test-only-student-login-jwt-secret-32-characters"
TEST_PASSWORD = "test-only-regular-student-password"
INVALID_LOGIN_RESPONSE = {
    "detail": "Invalid course, username, or password"
}
_DEFAULT_PASSWORD_HASH = object()


def _settings(
    *,
    secure: bool = False,
    jwt_secret: str | None = TEST_JWT_SECRET,
) -> AuthSettings:
    return AuthSettings(
        _env_file=None,
        jwt_secret=SecretStr(jwt_secret) if jwt_secret is not None else None,
        auth_cookie_secure=secure,
        access_token_minutes=30,
        activation_token_minutes=10,
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
def student_login_session_factory(
    test_engine: Engine,
    test_database_url: URL,
) -> Generator[sessionmaker[Session], None, None]:
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    _clear_account_tables(factory, test_database_url)
    yield factory
    _clear_account_tables(factory, test_database_url)


@pytest.fixture
def app_factory(
    student_login_session_factory: sessionmaker[Session],
) -> Callable[[AuthSettings], object]:
    def build(settings: AuthSettings):
        api = create_app(settings)

        def override_get_db() -> Generator[Session, None, None]:
            with student_login_session_factory() as session:
                yield session

        api.dependency_overrides[get_db] = override_get_db
        api.dependency_overrides[get_auth_settings] = lambda: settings
        return api

    return build


@pytest.fixture
def client(app_factory) -> Generator[TestClient, None, None]:
    with TestClient(app_factory(_settings())) as test_client:
        yield test_client


def _create_user(
    factory: sessionmaker[Session],
    username: str,
    *,
    role: UserRole = UserRole.STUDENT,
    is_active: bool = True,
    password_hash: str | None | object = _DEFAULT_PASSWORD_HASH,
) -> User:
    user = User(
        berkeley_username=username,
        role=role,
        is_active=is_active,
        password_hash=(
            hash_password(TEST_PASSWORD)
            if password_hash is _DEFAULT_PASSWORD_HASH
            else password_hash
        ),
    )
    with factory() as session:
        session.add(user)
        session.commit()
    return user


def _create_course(
    factory: sessionmaker[Session],
    owner: User,
    code: str,
    *,
    is_active: bool = True,
) -> CourseInstance:
    course = CourseInstance(
        course_code=code,
        course_name="Student Login Test",
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
    user: User,
    course: CourseInstance,
    *,
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE,
    nickname: str | None = "Bold Falcon 86",
    activation_used_at: datetime | None = None,
    activation_code_hash: str | None = None,
) -> Enrollment:
    enrollment = Enrollment(
        user_id=user.id,
        course_id=course.id,
        status=status,
        nickname=nickname,
        activation_used_at=(
            datetime.now(UTC)
            if activation_used_at is None
            and status == EnrollmentStatus.ACTIVE
            else activation_used_at
        ),
        activation_code_hash=activation_code_hash,
    )
    with factory() as session:
        session.add(enrollment)
        session.commit()
    return enrollment


def _active_student_fixture(
    factory: sessionmaker[Session],
    *,
    username: str = "regular-student",
    course_code: str = "IEOR150-Fall2026",
    nickname: str = "Bold Falcon 86",
) -> tuple[User, CourseInstance, Enrollment]:
    owner = _create_user(
        factory,
        f"owner-{uuid.uuid4().hex}",
        role=UserRole.INSTRUCTOR,
    )
    student = _create_user(factory, username)
    course = _create_course(factory, owner, course_code)
    enrollment = _create_enrollment(
        factory,
        student,
        course,
        nickname=nickname,
    )
    return student, course, enrollment


def _login(
    client: TestClient,
    *,
    course_code: str = "IEOR150-Fall2026",
    username: str = "regular-student",
    password: str = TEST_PASSWORD,
    path: str = "/api/auth/student/login",
):
    return client.post(
        path,
        json={
            "course_code": course_code,
            "berkeley_username": username,
            "password": password,
        },
    )


def test_activated_student_login_sets_scoped_cookie_and_safe_response(
    client,
    student_login_session_factory,
):
    student, course, enrollment = _active_student_fixture(
        student_login_session_factory
    )
    client.cookies.set(
        ACCESS_COOKIE_NAME,
        "old-access-cookie",
        domain="testserver.local",
        path="/",
    )
    client.cookies.set(
        ACTIVATION_COOKIE_NAME,
        "old-activation-cookie",
        domain="testserver.local",
        path="/",
    )

    response = _login(
        client,
        course_code="  ieor150-FALL2026  ",
        username="  REGULAR-STUDENT  ",
    )

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "user": {
            "id": str(student.id),
            "username": student.berkeley_username,
            "role": "student",
        },
        "course": {
            "id": str(course.id),
            "course_code": course.course_code,
        },
        "nickname": enrollment.nickname,
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    cookie_headers = [
        value.lower() for value in response.headers.get_list("set-cookie")
    ]
    assert any(
        header.startswith(f"{ACCESS_COOKIE_NAME}=")
        and "httponly" in header
        and "samesite=lax" in header
        and "path=/" in header
        and "max-age=1800" in header
        and "secure" not in header
        for header in cookie_headers
    )
    assert any(
        header.startswith(f"{ACTIVATION_COOKIE_NAME}=")
        and "max-age=0" in header
        and "httponly" in header
        and "samesite=lax" in header
        and "path=/" in header
        for header in cookie_headers
    )
    assert client.cookies[ACCESS_COOKIE_NAME] != "old-access-cookie"
    assert ACTIVATION_COOKIE_NAME not in client.cookies

    token = response.cookies[ACCESS_COOKIE_NAME]
    payload = jwt.decode(
        token,
        TEST_JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
    )
    assert payload["sub"] == str(student.id)
    assert payload["role"] == "student"
    assert payload["course_id"] == str(course.id)
    assert payload["enrollment_id"] == str(enrollment.id)
    assert int(payload["exp"]) - int(payload["iat"]) == 30 * 60
    response_text = response.text.lower()
    assert "token" not in response_text
    assert "password" not in response_text
    assert TEST_PASSWORD not in response.text


def test_student_login_secure_cookie_setting(
    app_factory,
    student_login_session_factory,
):
    _active_student_fixture(student_login_session_factory)

    with TestClient(app_factory(_settings(secure=True))) as secure_client:
        response = _login(secure_client)

    assert response.status_code == 200
    access_cookie = next(
        header
        for header in response.headers.get_list("set-cookie")
        if header.startswith(f"{ACCESS_COOKIE_NAME}=")
    )
    assert "secure" in access_cookie.lower()


def test_student_login_me_and_logout_share_existing_session_behavior(
    client,
    student_login_session_factory,
):
    student, course, enrollment = _active_student_fixture(
        student_login_session_factory
    )
    assert _login(client).status_code == 200

    me = client.get("/api/auth/me")
    logout = client.post("/api/auth/logout")

    assert me.status_code == 200
    assert me.json() == {
        "authenticated": True,
        "user": {
            "id": str(student.id),
            "username": student.berkeley_username,
            "role": "student",
        },
        "course": {
            "id": str(course.id),
            "course_code": course.course_code,
        },
        "nickname": enrollment.nickname,
    }
    assert logout.status_code == 200
    assert logout.json() == {"authenticated": False}
    assert ACCESS_COOKIE_NAME not in client.cookies
    assert "max-age=0" in logout.headers["set-cookie"].lower()


def test_multicourse_login_selects_the_requested_enrollment_and_nickname(
    client,
    student_login_session_factory,
):
    owner = _create_user(
        student_login_session_factory,
        "multicourse-owner",
        role=UserRole.INSTRUCTOR,
    )
    student = _create_user(
        student_login_session_factory,
        "multicourse-student",
    )
    first_course = _create_course(
        student_login_session_factory,
        owner,
        "IEOR150-First",
    )
    second_course = _create_course(
        student_login_session_factory,
        owner,
        "IEOR150-Second",
    )
    _create_enrollment(
        student_login_session_factory,
        student,
        first_course,
        nickname="First Falcon",
    )
    second_enrollment = _create_enrollment(
        student_login_session_factory,
        student,
        second_course,
        nickname="Second Falcon",
    )

    second = _login(
        client,
        course_code="ieor150-second",
        username=student.berkeley_username,
    )
    second_me = client.get("/api/auth/me")
    first = _login(
        client,
        course_code="IEOR150-FIRST",
        username=student.berkeley_username,
    )

    assert second.status_code == 200
    assert second.json()["course"]["id"] == str(second_course.id)
    assert second.json()["nickname"] == second_enrollment.nickname
    assert second_me.json()["course"]["id"] == str(second_course.id)
    assert second_me.json()["nickname"] == "Second Falcon"
    assert first.status_code == 200
    assert first.json()["course"]["id"] == str(first_course.id)
    assert first.json()["nickname"] == "First Falcon"


@pytest.mark.parametrize(
    "failure_case",
    [
        "wrong_password",
        "unknown_course",
        "unknown_username",
        "not_enrolled",
        "inactive_user",
        "inactive_course",
        "pending_enrollment",
        "disabled_enrollment",
        "missing_nickname",
        "missing_activation_used_at",
        "remaining_activation_hash",
        "missing_password_hash",
        "instructor",
    ],
)
def test_all_student_authentication_failures_are_uniform_and_verify_once(
    failure_case,
    monkeypatch,
    client,
    student_login_session_factory,
):
    student, course, enrollment = _active_student_fixture(
        student_login_session_factory
    )
    course_code = course.course_code
    username = student.berkeley_username
    password = TEST_PASSWORD

    with student_login_session_factory() as session:
        stored_user = session.get(User, student.id)
        stored_course = session.get(CourseInstance, course.id)
        stored_enrollment = session.get(Enrollment, enrollment.id)
        if failure_case == "wrong_password":
            password = "incorrect-test-password"
        elif failure_case == "unknown_course":
            course_code = "UNKNOWN-COURSE"
        elif failure_case == "unknown_username":
            username = "unknown-student"
        elif failure_case == "not_enrolled":
            other_course = CourseInstance(
                course_code="IEOR150-NotEnrolled",
                course_name="Not Enrolled",
                semester="Fall 2026",
                created_by=stored_course.created_by,
            )
            session.add(other_course)
            session.flush()
            course_code = other_course.course_code
        elif failure_case == "inactive_user":
            stored_user.is_active = False
        elif failure_case == "inactive_course":
            stored_course.is_active = False
        elif failure_case == "pending_enrollment":
            stored_enrollment.status = EnrollmentStatus.PENDING
        elif failure_case == "disabled_enrollment":
            stored_enrollment.status = EnrollmentStatus.DISABLED
        elif failure_case == "missing_nickname":
            stored_enrollment.nickname = None
        elif failure_case == "missing_activation_used_at":
            stored_enrollment.activation_used_at = None
        elif failure_case == "remaining_activation_hash":
            stored_enrollment.activation_code_hash = (
                "test-only-incomplete-activation-state"
            )
        elif failure_case == "missing_password_hash":
            stored_user.password_hash = None
        else:
            stored_user.role = UserRole.INSTRUCTOR
        session.commit()

    original_verify = student_authentication.verify_password
    verification_hashes: list[str] = []

    def track_verification(submitted_password: str, stored_hash: str) -> bool:
        verification_hashes.append(stored_hash)
        return original_verify(submitted_password, stored_hash)

    monkeypatch.setattr(
        student_authentication,
        "verify_password",
        track_verification,
    )

    response = _login(
        client,
        course_code=course_code,
        username=username,
        password=password,
    )

    assert response.status_code == 401
    assert response.json() == INVALID_LOGIN_RESPONSE
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert ACCESS_COOKIE_NAME not in response.cookies
    assert len(verification_hashes) == 1
    if failure_case != "wrong_password":
        assert verification_hashes[0] == DUMMY_PASSWORD_HASH


@pytest.mark.parametrize(
    ("payload", "secret_value"),
    [
        (
            {
                "course_code": "C" * 65,
                "berkeley_username": "regular-student",
                "password": TEST_PASSWORD,
            },
            "C" * 65,
        ),
        (
            {
                "course_code": "IEOR150-Fall2026",
                "berkeley_username": "u" * 65,
                "password": TEST_PASSWORD,
            },
            "u" * 65,
        ),
        (
            {
                "course_code": "IEOR150-Fall2026",
                "berkeley_username": "regular-student",
                "password": "p" * 129,
            },
            "p" * 129,
        ),
        (
            {
                "course_code": "   ",
                "berkeley_username": "regular-student",
                "password": TEST_PASSWORD,
            },
            TEST_PASSWORD,
        ),
        (
            {
                "course_code": "IEOR150-Fall2026",
                "berkeley_username": "   ",
                "password": TEST_PASSWORD,
            },
            TEST_PASSWORD,
        ),
        (
            {
                "course_code": "IEOR150-Fall2026",
                "berkeley_username": "regular-student",
                "password": "",
            },
            TEST_PASSWORD,
        ),
        (
            {
                "course_code": "IEOR150-Fall2026",
                "berkeley_username": "regular-student",
                "password": TEST_PASSWORD,
                "user_id": "forbidden",
            },
            TEST_PASSWORD,
        ),
    ],
)
def test_invalid_input_is_rejected_before_database_or_argon2(
    payload,
    secret_value,
    monkeypatch,
    client,
):
    def unexpected_call(*_args, **_kwargs):
        raise AssertionError("Database and Argon2 work must not run")

    monkeypatch.setattr(Session, "scalar", unexpected_call)
    monkeypatch.setattr(
        student_authentication,
        "verify_password",
        unexpected_call,
    )

    response = client.post("/api/auth/student/login", json=payload)

    assert response.status_code == 422
    assert secret_value not in response.text
    assert "password" not in response.text.lower() or TEST_PASSWORD not in response.text


@pytest.mark.parametrize(
    "token_change",
    [
        "missing_course_id",
        "missing_enrollment_id",
        "wrong_course_id",
        "wrong_enrollment_id",
    ],
)
def test_student_session_rejects_missing_or_tampered_scope_claims(
    token_change,
    client,
    student_login_session_factory,
):
    _active_student_fixture(student_login_session_factory)
    login = _login(client)
    payload = jwt.decode(
        login.cookies[ACCESS_COOKIE_NAME],
        TEST_JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
    )
    if token_change == "missing_course_id":
        payload.pop("course_id")
    elif token_change == "missing_enrollment_id":
        payload.pop("enrollment_id")
    elif token_change == "wrong_course_id":
        payload["course_id"] = str(uuid.uuid4())
    else:
        payload["enrollment_id"] = str(uuid.uuid4())
    tampered_token = jwt.encode(
        payload,
        TEST_JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set(ACCESS_COOKIE_NAME, tampered_token)

    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


@pytest.mark.parametrize(
    "state_change",
    ["inactive_user", "inactive_course", "disabled_enrollment"],
)
def test_database_state_change_invalidates_logged_in_student(
    state_change,
    client,
    student_login_session_factory,
):
    student, course, enrollment = _active_student_fixture(
        student_login_session_factory
    )
    assert _login(client).status_code == 200

    with student_login_session_factory() as session:
        if state_change == "inactive_user":
            session.get(User, student.id).is_active = False
        elif state_change == "inactive_course":
            session.get(CourseInstance, course.id).is_active = False
        else:
            session.get(Enrollment, enrollment.id).status = (
                EnrollmentStatus.DISABLED
            )
        session.commit()

    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_database_error_returns_safe_unavailable_response(
    monkeypatch,
    client,
):
    rollback_calls = 0
    original_rollback = Session.rollback

    def fail_query(*_args, **_kwargs):
        raise SQLAlchemyError("SELECT private_column FROM private_table")

    def track_rollback(session):
        nonlocal rollback_calls
        rollback_calls += 1
        return original_rollback(session)

    monkeypatch.setattr(Session, "scalar", fail_query)
    monkeypatch.setattr(Session, "rollback", track_rollback)

    response = _login(client)

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert rollback_calls == 1
    assert "private_column" not in response.text
    assert "private_table" not in response.text
    assert TEST_PASSWORD not in response.text
    assert ACCESS_COOKIE_NAME not in response.cookies
    assert "set-cookie" not in response.headers


def test_auth_configuration_error_returns_safe_non_cacheable_response(
    app_factory,
    student_login_session_factory,
):
    _active_student_fixture(student_login_session_factory)

    with TestClient(app_factory(_settings(jwt_secret=None))) as insecure_client:
        response = _login(insecure_client)

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert TEST_PASSWORD not in response.text
    assert ACCESS_COOKIE_NAME not in response.cookies
    assert "set-cookie" not in response.headers


def test_proxy_compatibility_path_uses_the_same_student_login_handler(
    client,
    student_login_session_factory,
):
    _active_student_fixture(student_login_session_factory)

    response = _login(client, path="/auth/student/login")

    assert response.status_code == 200
    assert ACCESS_COOKIE_NAME in response.cookies
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/auth/student/login" in paths
    assert "/auth/student/login" not in paths


def test_existing_instructor_login_remains_compatible(
    client,
    student_login_session_factory,
):
    instructor = _create_user(
        student_login_session_factory,
        "existing-instructor",
        role=UserRole.INSTRUCTOR,
    )

    response = client.post(
        "/api/auth/instructor/login",
        json={
            "username": instructor.berkeley_username,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "instructor"
    assert "course" not in response.json()
    assert "nickname" not in response.json()
