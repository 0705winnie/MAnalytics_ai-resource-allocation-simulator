import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
import pytest
from alembic import command
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import Engine, delete, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import (
    ACCESS_COOKIE_NAME,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    AuthConfigurationError,
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
    get_auth_settings,
    require_instructor,
)
from app.core.config import AuthSettings
from app.core.security import hash_password
from app.db.session import get_db
from app.main import create_app
from app.models import CourseInstance, Enrollment, User
from app.models.enums import EnrollmentStatus, UserRole
from app.routers import auth as auth_router


TEST_JWT_SECRET = "test-only-jwt-signing-secret-32-characters"
TEST_PASSWORD = "test-only-instructor-password"
AUTH_USERNAMES = {
    "auth-instructor",
    "auth-student",
    "auth-inactive",
    "auth-missing-hash",
    "auth-damaged-hash",
}


def _settings(
    *,
    cookie_secure: bool = False,
    jwt_secret: str | None = TEST_JWT_SECRET,
) -> AuthSettings:
    return AuthSettings(
        _env_file=None,
        jwt_secret=SecretStr(jwt_secret) if jwt_secret is not None else None,
        auth_cookie_secure=cookie_secure,
        access_token_minutes=30,
        frontend_origin="http://frontend.test",
    )


def _clear_auth_users(
    session_factory: sessionmaker[Session],
    test_database_url: URL,
) -> None:
    assert test_database_url.database is not None
    assert test_database_url.database.endswith("_test")
    with session_factory() as session:
        session.execute(delete(Enrollment))
        session.execute(delete(CourseInstance))
        session.execute(
            delete(User).where(User.berkeley_username.in_(AUTH_USERNAMES))
        )
        session.commit()


@pytest.fixture(scope="module", autouse=True)
def account_schema(test_alembic_config):
    command.upgrade(test_alembic_config, "head")


@pytest.fixture
def auth_session_factory(
    test_engine: Engine,
    test_database_url: URL,
) -> Generator[sessionmaker[Session], None, None]:
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    _clear_auth_users(factory, test_database_url)
    yield factory
    _clear_auth_users(factory, test_database_url)


@pytest.fixture
def app_factory(
    auth_session_factory: sessionmaker[Session],
) -> Callable[[AuthSettings], object]:
    def build(settings: AuthSettings):
        api = create_app(settings)

        def override_get_db() -> Generator[Session, None, None]:
            with auth_session_factory() as session:
                yield session

        api.dependency_overrides[get_db] = override_get_db
        api.dependency_overrides[get_auth_settings] = lambda: settings

        @api.get("/api/auth/instructor-only")
        def instructor_only(
            user: Annotated[User, Depends(require_instructor)],
        ) -> dict[str, str]:
            return {"id": str(user.id)}

        return api

    return build


@pytest.fixture
def auth_settings() -> AuthSettings:
    return _settings()


@pytest.fixture
def client(app_factory, auth_settings) -> Generator[TestClient, None, None]:
    with TestClient(app_factory(auth_settings)) as test_client:
        yield test_client


def _create_user(
    session_factory: sessionmaker[Session],
    *,
    username: str = "auth-instructor",
    role: UserRole = UserRole.INSTRUCTOR,
    is_active: bool = True,
    password_hash: str | None = None,
) -> User:
    user = User(
        berkeley_username=username,
        password_hash=(
            hash_password(TEST_PASSWORD)
            if password_hash is None
            else password_hash
        ),
        role=role,
        is_active=is_active,
    )
    with session_factory() as session:
        session.add(user)
        session.commit()
    return user


def _login(
    client: TestClient,
    *,
    username: str = "auth-instructor",
    password: str = TEST_PASSWORD,
):
    return client.post(
        "/api/auth/instructor/login",
        json={"username": username, "password": password},
    )


@pytest.mark.parametrize(
    ("username", "password", "invalid_field"),
    [
        ("", TEST_PASSWORD, "username"),
        ("   ", TEST_PASSWORD, "username"),
        ("u" * 65, TEST_PASSWORD, "username"),
        ("auth-instructor", "", "password"),
        ("auth-instructor", "p" * 1025, "password"),
    ],
)
def test_login_rejects_out_of_range_input_before_authentication(
    username,
    password,
    invalid_field,
    client,
    monkeypatch,
):
    def unexpected_verification(*args, **kwargs):
        raise AssertionError("password verification must not run")

    monkeypatch.setattr(auth_router, "verify_password", unexpected_verification)

    response = _login(client, username=username, password=password)

    assert response.status_code == 422
    assert any(
        invalid_field in error["loc"]
        for error in response.json()["detail"]
    )


def test_instructor_login_sets_securely_scoped_httponly_cookie(
    client,
    auth_session_factory,
):
    _create_user(auth_session_factory)

    response = _login(client, username="  AUTH-INSTRUCTOR  ")

    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert response.json()["user"]["username"] == "auth-instructor"
    cookie_header = response.headers["set-cookie"].lower()
    assert f"{ACCESS_COOKIE_NAME}=" in cookie_header
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header
    assert "path=/" in cookie_header
    assert "max-age=1800" in cookie_header
    assert "secure" not in cookie_header


def test_proxy_stripped_local_auth_path_remains_available(
    client,
    auth_session_factory,
):
    _create_user(auth_session_factory)

    response = client.post(
        "/auth/instructor/login",
        json={
            "username": "auth-instructor",
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200
    assert ACCESS_COOKIE_NAME in response.cookies


def test_secure_cookie_setting_adds_secure_attribute(
    app_factory,
    auth_session_factory,
):
    settings = _settings(cookie_secure=True)
    _create_user(auth_session_factory)

    with TestClient(app_factory(settings)) as secure_client:
        response = _login(secure_client)

    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()


def test_access_token_claims_are_complete_and_exclude_identity_secrets(
    client,
    auth_session_factory,
):
    user = _create_user(auth_session_factory)
    response = _login(client)
    token = response.cookies[ACCESS_COOKIE_NAME]

    payload = jwt.decode(
        token,
        TEST_JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
    )

    assert payload["sub"] == str(user.id)
    assert payload["role"] == UserRole.INSTRUCTOR.value
    assert payload["type"] == "access"
    assert payload["iss"] == JWT_ISSUER
    assert payload["aud"] == JWT_AUDIENCE
    assert int(payload["exp"]) - int(payload["iat"]) == 30 * 60
    uuid.UUID(payload["jti"])
    assert {
        "username",
        "password",
        "password_hash",
        "jwt_secret",
    }.isdisjoint(payload)
    assert TEST_JWT_SECRET not in token


@pytest.mark.parametrize(
    ("invalid_field", "invalid_value", "algorithm"),
    [
        ("iss", "wrong-issuer", JWT_ALGORITHM),
        ("aud", "wrong-audience", JWT_ALGORITHM),
        ("type", "refresh", JWT_ALGORITHM),
        ("sub", "not-a-uuid", JWT_ALGORITHM),
        ("role", "administrator", JWT_ALGORITHM),
        ("jti", "not-a-uuid", JWT_ALGORITHM),
        ("algorithm", None, "HS384"),
    ],
)
def test_decode_rejects_untrusted_algorithm_and_invalid_required_claims(
    invalid_field,
    invalid_value,
    algorithm,
    auth_settings,
):
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "role": UserRole.INSTRUCTOR.value,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=30),
        "jti": str(uuid.uuid4()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    if invalid_field != "algorithm":
        payload[invalid_field] = invalid_value
    signing_key = (
        TEST_JWT_SECRET
        if algorithm == JWT_ALGORITHM
        else TEST_JWT_SECRET * 2
    )
    token = jwt.encode(payload, signing_key, algorithm=algorithm)

    with pytest.raises(
        InvalidAccessTokenError,
        match="Invalid or expired access token",
    ):
        decode_access_token(token, auth_settings)


@pytest.mark.parametrize(
    "case",
    [
        "wrong-password",
        "missing-user",
        "student",
        "inactive",
        "missing-hash",
        "damaged-hash",
    ],
)
def test_all_invalid_login_states_return_identical_unauthorized_response(
    case,
    client,
    auth_session_factory,
):
    username = "auth-instructor"
    password = TEST_PASSWORD
    if case == "wrong-password":
        _create_user(auth_session_factory)
        password = "incorrect-test-password"
    elif case == "missing-user":
        username = "does-not-exist"
    elif case == "student":
        username = "auth-student"
        _create_user(
            auth_session_factory,
            username=username,
            role=UserRole.STUDENT,
        )
    elif case == "inactive":
        username = "auth-inactive"
        _create_user(
            auth_session_factory,
            username=username,
            is_active=False,
        )
    elif case == "missing-hash":
        username = "auth-missing-hash"
        user = User(
            berkeley_username=username,
            password_hash=None,
            role=UserRole.INSTRUCTOR,
            is_active=True,
        )
        with auth_session_factory() as session:
            session.add(user)
            session.commit()
    else:
        username = "auth-damaged-hash"
        _create_user(
            auth_session_factory,
            username=username,
            password_hash="$argon2id$damaged",
        )

    response = _login(client, username=username, password=password)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}
    assert ACCESS_COOKIE_NAME not in response.cookies
    assert "set-cookie" not in response.headers


def test_me_returns_minimal_identity_for_valid_cookie(
    client,
    auth_session_factory,
):
    user = _create_user(auth_session_factory)
    assert _login(client).status_code == 200

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "user": {
            "id": str(user.id),
            "username": "auth-instructor",
            "role": "instructor",
        },
    }


@pytest.mark.parametrize("token_state", ["missing", "invalid", "expired"])
def test_me_rejects_missing_invalid_and_expired_tokens(
    token_state,
    client,
    auth_session_factory,
    auth_settings,
):
    user = _create_user(auth_session_factory)
    if token_state == "invalid":
        client.cookies.set(ACCESS_COOKIE_NAME, "not-a-valid-token")
    elif token_state == "expired":
        token = create_access_token(
            user.id,
            user.role,
            auth_settings,
            now=datetime.now(UTC) - timedelta(minutes=31),
        )
        client.cookies.set(ACCESS_COOKIE_NAME, token)

    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_disabling_user_immediately_invalidates_existing_cookie(
    client,
    auth_session_factory,
):
    user = _create_user(auth_session_factory)
    assert _login(client).status_code == 200

    with auth_session_factory() as session:
        stored_user = session.get(User, user.id)
        assert stored_user is not None
        stored_user.is_active = False
        session.commit()

    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_token_role_must_match_database_role(
    client,
    auth_session_factory,
    auth_settings,
):
    user = _create_user(auth_session_factory)
    mismatched_token = create_access_token(
        user.id,
        UserRole.STUDENT,
        auth_settings,
        course_id=uuid.uuid4(),
        enrollment_id=uuid.uuid4(),
    )
    client.cookies.set(ACCESS_COOKIE_NAME, mismatched_token)

    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_require_instructor_rejects_authenticated_student(
    client,
    auth_session_factory,
    auth_settings,
):
    student = _create_user(
        auth_session_factory,
        username="auth-student",
        role=UserRole.STUDENT,
    )
    instructor = _create_user(auth_session_factory)
    course = CourseInstance(
        course_code="IEOR150-AuthStudent",
        course_name="Authentication Test",
        semester="Fall 2026",
        created_by=instructor.id,
    )
    enrollment = Enrollment(
        course=course,
        user_id=student.id,
        nickname="Auth Student",
        status=EnrollmentStatus.ACTIVE,
        activation_used_at=datetime.now(UTC),
    )
    with auth_session_factory() as session:
        session.add(enrollment)
        session.commit()
    student_token = create_access_token(
        student.id,
        student.role,
        auth_settings,
        course_id=course.id,
        enrollment_id=enrollment.id,
    )
    client.cookies.set(ACCESS_COOKIE_NAME, student_token)

    response = client.get("/api/auth/instructor-only")

    assert response.status_code == 403
    assert response.json() == {"detail": "Instructor access required"}


def test_logout_clears_cookie_with_matching_scope(client, auth_session_factory):
    _create_user(auth_session_factory)
    assert _login(client).status_code == 200

    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False}
    cookie_header = response.headers["set-cookie"].lower()
    assert f"{ACCESS_COOKIE_NAME}=" in cookie_header
    assert "max-age=0" in cookie_header
    assert "path=/" in cookie_header
    assert "samesite=lax" in cookie_header
    assert "httponly" in cookie_header


def test_logout_without_authentication_is_safe(client):
    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False}
    assert "max-age=0" in response.headers["set-cookie"].lower()


@pytest.mark.parametrize("secret", [None, "too-short"])
def test_missing_or_short_jwt_secret_fails_safely(secret):
    settings = _settings(jwt_secret=secret)

    with pytest.raises(
        AuthConfigurationError,
        match="not configured securely",
    ) as error:
        create_access_token(
            uuid.uuid4(),
            UserRole.INSTRUCTOR,
            settings,
        )

    if secret is not None:
        assert secret not in str(error.value)


@pytest.mark.parametrize("secret", [None, "too-short"])
def test_login_with_insecure_jwt_configuration_fails_without_cookie(
    secret,
    app_factory,
    auth_session_factory,
):
    settings = _settings(jwt_secret=secret)
    _create_user(auth_session_factory)

    with TestClient(app_factory(settings)) as insecure_client:
        response = _login(insecure_client)

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is unavailable"}
    assert "set-cookie" not in response.headers
    if secret is not None:
        assert secret not in response.text


@pytest.mark.parametrize("minutes", [4, 1441])
def test_access_token_lifetime_is_bounded(minutes):
    with pytest.raises(ValidationError):
        AuthSettings(
            _env_file=None,
            access_token_minutes=minutes,
        )


def test_frontend_origin_rejects_wildcard():
    with pytest.raises(ValidationError, match="explicit HTTP or HTTPS origin"):
        AuthSettings(_env_file=None, frontend_origin="*")


def test_cors_allows_only_configured_origin_with_credentials(client):
    allowed = client.options(
        "/api/auth/me",
        headers={
            "Origin": "http://frontend.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/api/auth/me",
        headers={
            "Origin": "http://untrusted.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers["access-control-allow-origin"] == "http://frontend.test"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert allowed.headers["access-control-allow-origin"] != "*"
    assert "access-control-allow-origin" not in denied.headers


def test_api_output_does_not_expose_credentials_or_token(
    client,
    auth_session_factory,
    capsys,
):
    _create_user(auth_session_factory)

    response = _login(client)
    token = response.cookies[ACCESS_COOKIE_NAME]
    captured = capsys.readouterr()
    observable_output = response.text + captured.out + captured.err

    assert TEST_PASSWORD not in observable_output
    assert TEST_JWT_SECRET not in observable_output
    assert token not in response.text
    assert "password_hash" not in observable_output
