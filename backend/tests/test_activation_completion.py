import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime

import jwt
import pytest
from alembic import command
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, delete, select
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.activation_auth import ACTIVATION_COOKIE_NAME
from app.core.auth import (
    ACCESS_COOKIE_NAME,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
    require_instructor,
)
from app.core.config import AuthSettings, get_auth_settings
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.main import create_app
from app.models import CourseInstance, Enrollment, User
from app.models.enums import EnrollmentStatus, UserRole
from app.services.activation_codes import (
    issue_activation_code,
    regenerate_activation_code,
)
from app.services import activation_completion


TEST_JWT_SECRET = "test-only-completion-jwt-secret-32-characters"
TEST_PASSWORD = "test-only-student-password"


def _settings(*, secure: bool = False) -> AuthSettings:
    return AuthSettings(
        _env_file=None,
        jwt_secret=SecretStr(TEST_JWT_SECRET),
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
def completion_session_factory(
    test_engine: Engine,
    test_database_url: URL,
) -> Generator[sessionmaker[Session], None, None]:
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    _clear_account_tables(factory, test_database_url)
    yield factory
    _clear_account_tables(factory, test_database_url)


@pytest.fixture
def auth_settings() -> AuthSettings:
    return _settings()


@pytest.fixture
def app_factory(
    completion_session_factory: sessionmaker[Session],
) -> Callable[[AuthSettings], object]:
    def build(settings: AuthSettings):
        api = create_app(settings)

        def override_get_db() -> Generator[Session, None, None]:
            with completion_session_factory() as session:
                yield session

        api.dependency_overrides[get_db] = override_get_db
        api.dependency_overrides[get_auth_settings] = lambda: settings

        @api.get("/api/auth/instructor-only")
        def instructor_only(
            _user: User = Depends(require_instructor),
        ) -> dict[str, bool]:
            return {"allowed": True}

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
    password_hash: str | None = None,
) -> User:
    user = User(
        berkeley_username=username,
        role=role,
        is_active=True,
        password_hash=password_hash,
    )
    with factory() as session:
        session.add(user)
        session.commit()
    return user


def _create_course(
    factory: sessionmaker[Session],
    owner: User,
    code: str,
) -> CourseInstance:
    course = CourseInstance(
        course_code=code,
        course_name="Resource Allocation",
        semester="Fall 2026",
        created_by=owner.id,
        is_active=True,
    )
    with factory() as session:
        session.add(course)
        session.commit()
    return course


def _create_pending_enrollment(
    factory: sessionmaker[Session],
    course: CourseInstance,
    user: User,
) -> tuple[Enrollment, str]:
    enrollment = Enrollment(
        course_id=course.id,
        user_id=user.id,
        status=EnrollmentStatus.PENDING,
    )
    code = issue_activation_code(enrollment)
    with factory() as session:
        session.add(enrollment)
        session.commit()
    return enrollment, code


def _activation_fixture(
    factory: sessionmaker[Session],
    *,
    username: str = "new-student",
    existing_password: str | None = None,
    course_code: str = "IEOR150-Complete",
) -> tuple[User, CourseInstance, Enrollment, str]:
    owner = _create_user(
        factory,
        f"owner-{uuid.uuid4().hex}",
        role=UserRole.INSTRUCTOR,
    )
    user = _create_user(
        factory,
        username,
        password_hash=(
            hash_password(existing_password)
            if existing_password is not None
            else None
        ),
    )
    course = _create_course(factory, owner, course_code)
    enrollment, code = _create_pending_enrollment(factory, course, user)
    return user, course, enrollment, code


def _verify(
    client: TestClient,
    user: User,
    course: CourseInstance,
    code: str,
):
    return client.post(
        "/api/auth/activate/verify",
        json={
            "course_code": course.course_code,
            "berkeley_username": user.berkeley_username,
            "activation_code": code,
        },
    )


def _complete(
    client: TestClient,
    *,
    password: str = TEST_PASSWORD,
    confirmation: str | None = None,
    nickname: str = "Bold Falcon 86",
    path: str = "/api/auth/activate/complete",
):
    return client.post(
        path,
        json={
            "password": password,
            "password_confirmation": (
                password if confirmation is None else confirmation
            ),
            "nickname": nickname,
        },
    )


def test_new_student_activation_is_atomic_and_establishes_scoped_session(
    client,
    completion_session_factory,
):
    user, course, enrollment, code = _activation_fixture(
        completion_session_factory
    )
    verify_response = _verify(client, user, course, code)
    activation_token = verify_response.cookies[ACTIVATION_COOKIE_NAME]
    assert verify_response.json()["password_mode"] == "create"

    response = _complete(
        client,
        nickname="  Bold   Falcon 86  ",
    )

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "user": {
            "id": str(user.id),
            "username": user.berkeley_username,
            "role": "student",
        },
        "course": {
            "id": str(course.id),
            "course_code": course.course_code,
        },
        "nickname": "Bold Falcon 86",
    }
    assert ACCESS_COOKIE_NAME in response.cookies
    assert ACTIVATION_COOKIE_NAME not in client.cookies
    cookie_headers = [
        value.lower() for value in response.headers.get_list("set-cookie")
    ]
    assert any(
        header.startswith(f"{ACCESS_COOKIE_NAME}=")
        and "max-age=1800" in header
        and "httponly" in header
        and "samesite=lax" in header
        and "path=/" in header
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
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    response_text = response.text.lower()
    assert "token" not in response_text
    assert "password" not in response_text
    assert "hash" not in response_text
    assert activation_token not in response.text
    assert code not in response.text

    access_token = response.cookies[ACCESS_COOKIE_NAME]
    claims = decode_access_token(access_token, _settings())
    assert claims.role == UserRole.STUDENT
    assert claims.course_id == course.id
    assert claims.enrollment_id == enrollment.id
    with completion_session_factory() as session:
        stored_user = session.get(User, user.id)
        stored_enrollment = session.get(Enrollment, enrollment.id)
        assert stored_user is not None
        assert stored_enrollment is not None
        assert stored_user.password_hash is not None
        assert stored_user.password_hash != TEST_PASSWORD
        assert stored_user.password_hash.startswith("$argon2id$")
        assert verify_password(TEST_PASSWORD, stored_user.password_hash)
        assert stored_enrollment.nickname == "Bold Falcon 86"
        assert stored_enrollment.status == EnrollmentStatus.ACTIVE
        assert stored_enrollment.activation_used_at is not None
        assert stored_enrollment.activation_code_hash is None

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == response.json()


def test_secure_completion_cookie_attributes(
    app_factory,
    completion_session_factory,
):
    user, course, _, code = _activation_fixture(completion_session_factory)
    with TestClient(app_factory(_settings(secure=True))) as secure_client:
        verified = _verify(secure_client, user, course, code)
        assert verified.status_code == 200
        activation_token = verified.cookies[ACTIVATION_COOKIE_NAME]
        secure_client.cookies.clear()
        secure_client.cookies.set(
            ACTIVATION_COOKIE_NAME,
            activation_token,
            domain="testserver.local",
            path="/",
        )
        response = _complete(secure_client)

    assert response.status_code == 200
    assert all(
        "secure" in header.lower()
        for header in response.headers.get_list("set-cookie")
    )


def test_existing_password_is_confirmed_unchanged_for_second_course(
    client,
    completion_session_factory,
):
    owner = _create_user(
        completion_session_factory,
        "multi-owner",
        role=UserRole.INSTRUCTOR,
    )
    original_hash = hash_password(TEST_PASSWORD)
    user = _create_user(
        completion_session_factory,
        "multi-course-user",
        password_hash=original_hash,
    )
    first_course = _create_course(
        completion_session_factory,
        owner,
        "IEOR150-FirstActive",
    )
    first_enrollment = Enrollment(
        course_id=first_course.id,
        user_id=user.id,
        nickname="Shared Nickname",
        status=EnrollmentStatus.ACTIVE,
        activation_used_at=datetime.now(UTC),
    )
    with completion_session_factory() as session:
        session.add(first_enrollment)
        session.commit()
    second_course = _create_course(
        completion_session_factory,
        owner,
        "IEOR150-SecondPending",
    )
    second_enrollment, code = _create_pending_enrollment(
        completion_session_factory,
        second_course,
        user,
    )

    verified = _verify(client, user, second_course, code)
    assert verified.json()["password_mode"] == "confirm"
    response = _complete(client, nickname="Shared Nickname")

    assert response.status_code == 200
    with completion_session_factory() as session:
        stored_user = session.get(User, user.id)
        assert stored_user is not None
        assert stored_user.password_hash == original_hash
        enrollments = session.scalars(
            select(Enrollment).where(Enrollment.user_id == user.id)
        ).all()
        assert len(enrollments) == 2
        assert all(
            enrollment.status == EnrollmentStatus.ACTIVE
            for enrollment in enrollments
        )
        assert {enrollment.nickname for enrollment in enrollments} == {
            "Shared Nickname"
        }
        assert session.get(Enrollment, second_enrollment.id).activation_code_hash is None


def test_wrong_existing_password_is_retryable_and_changes_nothing(
    client,
    completion_session_factory,
):
    user, course, enrollment, code = _activation_fixture(
        completion_session_factory,
        existing_password=TEST_PASSWORD,
    )
    original_hash = user.password_hash
    original_activation_hash = enrollment.activation_code_hash
    assert _verify(client, user, course, code).status_code == 200
    activation_cookie = client.cookies[ACTIVATION_COOKIE_NAME]

    rejected = _complete(client, password="wrong-test-password")

    assert rejected.status_code == 400
    assert rejected.json() == {
        "detail": "Activation credentials could not be confirmed"
    }
    assert client.cookies[ACTIVATION_COOKIE_NAME] == activation_cookie
    assert ACCESS_COOKIE_NAME not in client.cookies
    with completion_session_factory() as session:
        stored_user = session.get(User, user.id)
        stored = session.get(Enrollment, enrollment.id)
        assert stored_user.password_hash == original_hash
        assert stored.status == EnrollmentStatus.PENDING
        assert stored.nickname is None
        assert stored.activation_code_hash == original_activation_hash
        assert stored.activation_used_at is None

    assert _complete(client).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {
            "password": "Secr3t!",
            "password_confirmation": "Secr3t!",
            "nickname": "Valid Nick",
        },
        {
            "password": "x" * 129,
            "password_confirmation": "x" * 129,
            "nickname": "Valid Nick",
        },
        {
            "password": TEST_PASSWORD,
            "password_confirmation": "different-password",
            "nickname": "Valid Nick",
        },
        {
            "password": TEST_PASSWORD,
            "password_confirmation": TEST_PASSWORD,
            "nickname": "Valid Nick",
            "user_id": "forbidden",
        },
    ],
)
def test_password_and_extra_field_validation_is_422_and_non_consuming(
    payload,
    client,
    completion_session_factory,
):
    user, course, enrollment, code = _activation_fixture(
        completion_session_factory
    )
    assert _verify(client, user, course, code).status_code == 200
    activation_cookie = client.cookies[ACTIVATION_COOKIE_NAME]

    response = client.post("/api/auth/activate/complete", json=payload)

    assert response.status_code == 422
    for field in ("password", "password_confirmation", "nickname"):
        value = payload.get(field)
        if isinstance(value, str):
            assert value not in response.text
    assert client.cookies[ACTIVATION_COOKIE_NAME] == activation_cookie
    with completion_session_factory() as session:
        stored = session.get(Enrollment, enrollment.id)
        assert session.get(User, user.id).password_hash is None
        assert stored.status == EnrollmentStatus.PENDING
        assert stored.activation_code_hash is not None


@pytest.mark.parametrize(
    "nickname",
    [
        "ab",
        "x" * 31,
        "-Starts Bad",
        "Ends Bad_",
        "Bad<script>",
        "Bad/Slash",
        "Line\nBreak",
        "Tab\tName",
        "Control\u0000Name",
    ],
)
def test_invalid_nickname_format_is_rejected_without_consuming_activation(
    nickname,
    client,
    completion_session_factory,
):
    user, course, enrollment, code = _activation_fixture(
        completion_session_factory
    )
    assert _verify(client, user, course, code).status_code == 200

    response = _complete(client, nickname=nickname)

    assert response.status_code == 422
    assert ACTIVATION_COOKIE_NAME in client.cookies
    with completion_session_factory() as session:
        stored = session.get(Enrollment, enrollment.id)
        assert session.get(User, user.id).password_hash is None
        assert stored.status == EnrollmentStatus.PENDING
        assert stored.nickname is None


def test_oversized_raw_nickname_is_rejected_before_auth_or_password_work(
    monkeypatch,
    client,
    completion_session_factory,
):
    user, course, enrollment, code = _activation_fixture(
        completion_session_factory
    )
    assert _verify(client, user, course, code).status_code == 200

    def unexpected_call(*_args, **_kwargs):
        raise AssertionError("Security-sensitive processing must not run")

    monkeypatch.setattr(
        activation_completion,
        "lock_activation_context",
        unexpected_call,
    )
    monkeypatch.setattr(
        activation_completion,
        "hash_password",
        unexpected_call,
    )
    monkeypatch.setattr(
        activation_completion,
        "verify_password",
        unexpected_call,
    )
    oversized_nickname = "N" * 129

    response = _complete(client, nickname=oversized_nickname)

    assert response.status_code == 422
    assert oversized_nickname not in response.text
    with completion_session_factory() as session:
        stored = session.get(Enrollment, enrollment.id)
        assert session.get(User, user.id).password_hash is None
        assert stored.status == EnrollmentStatus.PENDING
        assert stored.nickname is None
        assert stored.activation_used_at is None
        assert stored.activation_code_hash is not None


def test_unicode_nickname_and_space_normalization_are_supported(
    client,
    completion_session_factory,
):
    user, course, enrollment, code = _activation_fixture(
        completion_session_factory
    )
    assert _verify(client, user, course, code).status_code == 200

    response = _complete(client, nickname="  Élan   熊_9  ")

    assert response.status_code == 200
    assert response.json()["nickname"] == "Élan 熊_9"
    with completion_session_factory() as session:
        assert session.get(Enrollment, enrollment.id).nickname == "Élan 熊_9"


@pytest.mark.parametrize(
    "nickname",
    ["newstudent", "NEW STUDENT", "new-student", "new_student"],
)
def test_nickname_cannot_disguise_berkeley_username(
    nickname,
    client,
    completion_session_factory,
):
    user, course, enrollment, code = _activation_fixture(
        completion_session_factory,
        username="new.student",
    )
    assert _verify(client, user, course, code).status_code == 200

    response = _complete(client, nickname=nickname)

    assert response.status_code == 422
    assert response.json() == {"detail": "Nickname is invalid"}
    assert ACTIVATION_COOKIE_NAME in client.cookies
    with completion_session_factory() as session:
        assert session.get(User, user.id).password_hash is None
        assert session.get(Enrollment, enrollment.id).status == (
            EnrollmentStatus.PENDING
        )


def test_same_course_nickname_conflict_rolls_back_and_allows_retry(
    client,
    completion_session_factory,
):
    owner = _create_user(
        completion_session_factory,
        "nickname-owner",
        role=UserRole.INSTRUCTOR,
    )
    existing_user = _create_user(
        completion_session_factory,
        "existing-nickname-user",
    )
    target_user = _create_user(
        completion_session_factory,
        "target-nickname-user",
    )
    course = _create_course(
        completion_session_factory,
        owner,
        "IEOR150-NicknameConflict",
    )
    existing = Enrollment(
        course_id=course.id,
        user_id=existing_user.id,
        nickname="Bold Falcon",
        status=EnrollmentStatus.ACTIVE,
        activation_used_at=datetime.now(UTC),
    )
    with completion_session_factory() as session:
        session.add(existing)
        session.commit()
    target, code = _create_pending_enrollment(
        completion_session_factory,
        course,
        target_user,
    )
    original_activation_hash = target.activation_code_hash
    assert _verify(client, target_user, course, code).status_code == 200
    activation_cookie = client.cookies[ACTIVATION_COOKIE_NAME]

    conflict = _complete(client, nickname="bold falcon")

    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "Nickname is unavailable"}
    assert client.cookies[ACTIVATION_COOKIE_NAME] == activation_cookie
    assert ACCESS_COOKIE_NAME not in client.cookies
    with completion_session_factory() as session:
        stored = session.get(Enrollment, target.id)
        assert session.get(User, target_user.id).password_hash is None
        assert stored.nickname is None
        assert stored.status == EnrollmentStatus.PENDING
        assert stored.activation_used_at is None
        assert stored.activation_code_hash == original_activation_hash

    retry = _complete(client, nickname="Different Falcon")
    assert retry.status_code == 200


def test_instructor_and_student_access_claim_shapes_are_strict(
    completion_session_factory,
    auth_settings,
):
    instructor = _create_user(
        completion_session_factory,
        "claims-instructor",
        role=UserRole.INSTRUCTOR,
    )
    instructor_token = create_access_token(
        instructor.id,
        UserRole.INSTRUCTOR,
        auth_settings,
    )
    payload = jwt.decode(
        instructor_token,
        TEST_JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
    )
    assert "course_id" not in payload
    assert "enrollment_id" not in payload
    with pytest.raises(ValueError):
        create_access_token(
            instructor.id,
            UserRole.INSTRUCTOR,
            auth_settings,
            course_id=uuid.uuid4(),
            enrollment_id=uuid.uuid4(),
        )
    with pytest.raises(ValueError):
        create_access_token(
            uuid.uuid4(),
            UserRole.STUDENT,
            auth_settings,
        )

    malformed_student = {
        **payload,
        "sub": str(uuid.uuid4()),
        "role": "student",
        "course_id": str(uuid.uuid4()),
    }
    token = jwt.encode(
        malformed_student,
        TEST_JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(token, auth_settings)


@pytest.mark.parametrize(
    "state_change",
    ["enrollment_disabled", "course_inactive", "user_inactive"],
)
def test_student_session_is_immediately_invalidated_by_database_state(
    state_change,
    client,
    completion_session_factory,
):
    user, course, enrollment, code = _activation_fixture(
        completion_session_factory
    )
    assert _verify(client, user, course, code).status_code == 200
    assert _complete(client).status_code == 200

    with completion_session_factory() as session:
        if state_change == "enrollment_disabled":
            session.get(Enrollment, enrollment.id).status = (
                EnrollmentStatus.DISABLED
            )
        elif state_change == "course_inactive":
            session.get(CourseInstance, course.id).is_active = False
        else:
            session.get(User, user.id).is_active = False
        session.commit()

    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


@pytest.mark.parametrize(
    "incomplete_state",
    ["missing_used_timestamp", "remaining_activation_hash"],
)
def test_student_session_rejects_incomplete_activation_state(
    incomplete_state,
    client,
    completion_session_factory,
):
    user, course, enrollment, code = _activation_fixture(
        completion_session_factory
    )
    assert _verify(client, user, course, code).status_code == 200
    assert _complete(client).status_code == 200

    with completion_session_factory() as session:
        stored = session.get(Enrollment, enrollment.id)
        if incomplete_state == "missing_used_timestamp":
            stored.activation_used_at = None
        else:
            stored.activation_code_hash = "test-only-incomplete-state"
        session.commit()

    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_valid_student_session_is_forbidden_by_require_instructor(
    client,
    completion_session_factory,
):
    user, course, _, code = _activation_fixture(completion_session_factory)
    assert _verify(client, user, course, code).status_code == 200
    assert _complete(client).status_code == 200

    response = client.get("/api/auth/instructor-only")

    assert response.status_code == 403
    assert response.json() == {"detail": "Instructor access required"}


def test_activation_token_is_single_use_and_regeneration_invalidates_it(
    client,
    completion_session_factory,
):
    user, course, enrollment, code = _activation_fixture(
        completion_session_factory
    )
    verified = _verify(client, user, course, code)
    old_activation_token = verified.cookies[ACTIVATION_COOKIE_NAME]

    assert _complete(client).status_code == 200
    client.cookies.set(
        ACTIVATION_COOKIE_NAME,
        old_activation_token,
        domain="testserver.local",
        path="/",
    )
    repeated = _complete(client, nickname="Another Nickname")
    assert repeated.status_code == 401
    assert ACTIVATION_COOKIE_NAME not in client.cookies

    client.cookies.clear()
    second_user, second_course, second_enrollment, second_code = (
        _activation_fixture(
            completion_session_factory,
            username="regenerated-student",
            course_code="IEOR150-Regenerated",
        )
    )
    verified = _verify(client, second_user, second_course, second_code)
    assert verified.status_code == 200
    with completion_session_factory() as session:
        stored = session.get(Enrollment, second_enrollment.id)
        regenerate_activation_code(stored)
        session.commit()
    invalidated = _complete(client)
    assert invalidated.status_code == 401


@pytest.mark.parametrize("failure_kind", ["integrity", "database"])
def test_commit_failure_rolls_back_and_keeps_activation_cookie_retryable(
    failure_kind,
    monkeypatch,
    client,
    completion_session_factory,
):
    user, course, enrollment, code = _activation_fixture(
        completion_session_factory
    )
    assert _verify(client, user, course, code).status_code == 200
    activation_cookie = client.cookies[ACTIVATION_COOKIE_NAME]
    original_activation_hash = enrollment.activation_code_hash
    original_commit = Session.commit

    def fail_commit(_session):
        if failure_kind == "integrity":
            raise IntegrityError("safe statement", {}, Exception("constraint"))
        raise SQLAlchemyError("safe database failure")

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = _complete(client)
    monkeypatch.setattr(Session, "commit", original_commit)

    assert response.status_code == (409 if failure_kind == "integrity" else 500)
    assert ACCESS_COOKIE_NAME not in response.cookies
    assert ACCESS_COOKIE_NAME not in client.cookies
    assert client.cookies[ACTIVATION_COOKIE_NAME] == activation_cookie
    with completion_session_factory() as session:
        stored = session.get(Enrollment, enrollment.id)
        assert session.get(User, user.id).password_hash is None
        assert stored.nickname is None
        assert stored.status == EnrollmentStatus.PENDING
        assert stored.activation_used_at is None
        assert stored.activation_code_hash == original_activation_hash


def test_completion_uses_row_lock_and_proxy_path_shares_handler(
    monkeypatch,
    client,
    completion_session_factory,
):
    user, course, _, code = _activation_fixture(completion_session_factory)
    assert _verify(client, user, course, code).status_code == 200
    original_scalar = Session.scalar
    for_update_targets: set[str] = set()

    def track_scalar(session, statement, *args, **kwargs):
        for_update = getattr(statement, "_for_update_arg", None)
        if for_update is not None and for_update.of is not None:
            for target in for_update.of:
                for_update_targets.add(target.name)
        return original_scalar(session, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "scalar", track_scalar)
    response = _complete(
        client,
        path="/auth/activate/complete",
    )

    assert response.status_code == 200
    assert for_update_targets == {"enrollments", "users", "course_instances"}
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/auth/activate/complete" in paths
    assert "/auth/activate/complete" not in paths


def test_missing_or_invalid_activation_cookie_is_uniform_and_cleared(client):
    missing = _complete(client)
    client.cookies.set(
        ACTIVATION_COOKIE_NAME,
        "not-a-token",
        domain="testserver.local",
        path="/",
    )
    invalid = _complete(client)

    assert missing.status_code == invalid.status_code == 401
    assert missing.json() == invalid.json() == {
        "detail": "Invalid or expired activation session"
    }
    assert "max-age=0" in invalid.headers["set-cookie"].lower()
    assert ACTIVATION_COOKIE_NAME not in client.cookies
