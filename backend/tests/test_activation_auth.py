import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from alembic import command
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import Engine, delete, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.core.activation_auth import (
    ACTIVATION_CONTEXT_REQUIRED_MESSAGE,
    ACTIVATION_COOKIE_NAME,
    ACTIVATION_TOKEN_AUDIENCE,
    ACTIVATION_TOKEN_TYPE,
    ActivationContext,
    InvalidActivationTokenError,
    create_activation_token,
    decode_activation_token,
    get_activation_context,
)
from app.core.auth import (
    ACCESS_COOKIE_NAME,
    JWT_ALGORITHM,
    JWT_ISSUER,
    AuthConfigurationError,
)
from app.core.config import AuthSettings, get_auth_settings
from app.db.session import get_db
from app.main import create_app
from app.models import CourseInstance, Enrollment, User
from app.models.enums import EnrollmentStatus, UserRole
from app.services import activation_verification
from app.services.activation_codes import (
    issue_activation_code,
    regenerate_activation_code,
)


TEST_JWT_SECRET = "test-only-activation-jwt-secret-32-characters"
COURSE_CODE = "IEOR150-Fall2026"
STUDENT_USERNAME = "activation-login-student"
GENERIC_FAILURE = {"detail": "Invalid or expired activation credentials"}


def _settings(
    *,
    secure: bool = False,
    activation_minutes: int = 10,
    jwt_secret: str | None = TEST_JWT_SECRET,
) -> AuthSettings:
    return AuthSettings(
        _env_file=None,
        jwt_secret=SecretStr(jwt_secret) if jwt_secret is not None else None,
        auth_cookie_secure=secure,
        access_token_minutes=30,
        activation_token_minutes=activation_minutes,
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
def activation_session_factory(
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
    activation_session_factory: sessionmaker[Session],
) -> Callable[[AuthSettings], object]:
    def build(settings: AuthSettings):
        api = create_app(settings)

        def override_get_db() -> Generator[Session, None, None]:
            with activation_session_factory() as session:
                yield session

        api.dependency_overrides[get_db] = override_get_db
        api.dependency_overrides[get_auth_settings] = lambda: settings

        @api.get("/test/activation-context")
        def activation_context_probe(
            _context: ActivationContext = Depends(get_activation_context),
        ) -> dict[str, bool]:
            return {"valid": True}

        return api

    return build


@pytest.fixture
def client(app_factory, auth_settings) -> Generator[TestClient, None, None]:
    with TestClient(app_factory(auth_settings)) as test_client:
        yield test_client


def _create_user(
    factory: sessionmaker[Session],
    *,
    username: str = STUDENT_USERNAME,
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
    *,
    owner: User,
    code: str = COURSE_CODE,
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


def _create_activation_fixture(
    factory: sessionmaker[Session],
    *,
    course_active: bool = True,
    user_active: bool = True,
    user_role: UserRole = UserRole.STUDENT,
    status: EnrollmentStatus = EnrollmentStatus.PENDING,
    used: bool = False,
    expires_at: datetime | None = None,
    hash_value: str | None = "valid",
) -> tuple[CourseInstance, User, Enrollment, str]:
    owner = _create_user(
        factory,
        username=f"owner-{uuid.uuid4().hex}",
        role=UserRole.INSTRUCTOR,
    )
    user = _create_user(
        factory,
        role=user_role,
        is_active=user_active,
    )
    course = _create_course(
        factory,
        owner=owner,
        is_active=course_active,
    )
    enrollment = Enrollment(
        course_id=course.id,
        user_id=user.id,
        status=EnrollmentStatus.PENDING,
    )
    activation_code = issue_activation_code(enrollment)
    enrollment.status = status
    if used:
        enrollment.activation_used_at = datetime.now(UTC)
    if expires_at is not None:
        enrollment.activation_expires_at = expires_at
    if hash_value == "missing":
        enrollment.activation_code_hash = None
    elif hash_value == "damaged":
        enrollment.activation_code_hash = "not-a-valid-password-hash"
    with factory() as session:
        session.add(enrollment)
        session.commit()
    return course, user, enrollment, activation_code


def _verify_payload(
    course_code: str,
    username: str,
    activation_code: str,
) -> dict[str, str]:
    return {
        "course_code": course_code,
        "berkeley_username": username,
        "activation_code": activation_code,
    }


def _verify(
    client: TestClient,
    course: CourseInstance,
    user: User,
    activation_code: str,
    *,
    path: str = "/api/auth/activate/verify",
):
    return client.post(
        path,
        json=_verify_payload(
            course.course_code,
            user.berkeley_username,
            activation_code,
        ),
    )


def test_valid_credentials_normalize_inputs_set_cookie_and_do_not_consume_code(
    monkeypatch,
    client,
    activation_session_factory,
):
    course, user, enrollment, activation_code = _create_activation_fixture(
        activation_session_factory
    )
    original_hash = enrollment.activation_code_hash
    original_expiration = enrollment.activation_expires_at
    verify_calls = 0
    original_verify = activation_verification.verify_one_time_secret

    def count_verification(secret, secret_hash):
        nonlocal verify_calls
        verify_calls += 1
        return original_verify(secret, secret_hash)

    monkeypatch.setattr(
        activation_verification,
        "verify_one_time_secret",
        count_verification,
    )
    response = client.post(
        "/api/auth/activate/verify",
        json=_verify_payload(
            f"  {course.course_code.swapcase()}  ",
            f"  {user.berkeley_username.upper()}  ",
            f"  {activation_code.lower().replace('-', '')}  ",
        ),
    )

    assert response.status_code == 200
    assert response.json() == {
        "verified": True,
        "expires_in_seconds": 600,
        "password_mode": "create",
    }
    assert verify_calls == 1
    assert ACTIVATION_COOKIE_NAME in response.cookies
    assert ACCESS_COOKIE_NAME not in response.cookies
    cookie_header = response.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header
    assert "path=/" in cookie_header
    assert "max-age=600" in cookie_header
    assert "secure" not in cookie_header
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    response_text = response.text.lower()
    assert "token" not in response_text
    assert "activation_code" not in response_text
    assert user.berkeley_username not in response.text
    assert original_hash is not None
    assert original_hash not in response.text
    with activation_session_factory() as session:
        stored = session.get(Enrollment, enrollment.id)
        assert stored is not None
        assert stored.status == EnrollmentStatus.PENDING
        assert stored.activation_used_at is None
        assert stored.activation_code_hash == original_hash
        assert stored.activation_expires_at == original_expiration


def test_secure_setting_adds_secure_activation_cookie(
    app_factory,
    activation_session_factory,
):
    course, user, _, activation_code = _create_activation_fixture(
        activation_session_factory
    )
    with TestClient(app_factory(_settings(secure=True))) as secure_client:
        response = _verify(secure_client, course, user, activation_code)

    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()


def test_invalid_credentials_clear_existing_activation_cookie_without_leaking_it(
    client,
    activation_session_factory,
):
    course, user, enrollment, activation_code = _create_activation_fixture(
        activation_session_factory
    )
    successful = _verify(client, course, user, activation_code)
    old_token = successful.cookies[ACTIVATION_COOKIE_NAME]
    old_payload = jwt.decode(
        old_token,
        TEST_JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=ACTIVATION_TOKEN_AUDIENCE,
    )
    fingerprint = old_payload["activation_version"]
    stored_hash = enrollment.activation_code_hash
    assert stored_hash is not None

    response = client.post(
        "/api/auth/activate/verify",
        json=_verify_payload(
            course.course_code,
            user.berkeley_username,
            "IIII-IIII-IIII",
        ),
    )

    assert response.status_code == 401
    assert response.json() == GENERIC_FAILURE
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    cookie_header = response.headers["set-cookie"].lower()
    assert cookie_header.startswith(f"{ACTIVATION_COOKIE_NAME}=")
    assert "max-age=0" in cookie_header
    assert "path=/" in cookie_header
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header
    assert ACTIVATION_COOKIE_NAME not in client.cookies
    assert old_token not in response.text
    assert activation_code not in response.text
    assert stored_hash not in response.text
    assert fingerprint not in response.text


def test_unconfigured_jwt_failure_clears_existing_activation_cookie(
    client,
    activation_session_factory,
):
    course, user, enrollment, activation_code = _create_activation_fixture(
        activation_session_factory
    )
    successful = _verify(client, course, user, activation_code)
    old_token = successful.cookies[ACTIVATION_COOKIE_NAME]
    old_payload = jwt.decode(
        old_token,
        TEST_JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=ACTIVATION_TOKEN_AUDIENCE,
    )
    fingerprint = old_payload["activation_version"]
    stored_hash = enrollment.activation_code_hash
    assert stored_hash is not None
    client.app.dependency_overrides[get_auth_settings] = lambda: _settings(
        jwt_secret="too-short"
    )

    response = _verify(client, course, user, activation_code)

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Activation verification is unavailable"
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    cookie_header = response.headers["set-cookie"].lower()
    assert "max-age=0" in cookie_header
    assert "path=/" in cookie_header
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header
    assert ACTIVATION_COOKIE_NAME not in client.cookies
    assert old_token not in response.text
    assert activation_code not in response.text
    assert stored_hash not in response.text
    assert fingerprint not in response.text


def test_invalid_credentials_without_existing_cookie_keep_same_safe_failure(
    client,
    activation_session_factory,
):
    course, user, _, _ = _create_activation_fixture(
        activation_session_factory
    )

    response = _verify(
        client,
        course,
        user,
        "IIII-IIII-IIII",
    )

    assert response.status_code == 401
    assert response.json() == GENERIC_FAILURE
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert ACTIVATION_COOKIE_NAME not in client.cookies


def test_failure_cookie_clear_respects_secure_setting(
    app_factory,
    activation_session_factory,
):
    course, user, _, activation_code = _create_activation_fixture(
        activation_session_factory
    )
    with TestClient(app_factory(_settings(secure=True))) as secure_client:
        assert _verify(
            secure_client,
            course,
            user,
            activation_code,
        ).status_code == 200
        response = _verify(
            secure_client,
            course,
            user,
            "IIII-IIII-IIII",
        )

    assert response.status_code == 401
    assert "secure" in response.headers["set-cookie"].lower()


def test_successful_reverification_overwrites_existing_activation_cookie(
    client,
    activation_session_factory,
):
    course, user, _, activation_code = _create_activation_fixture(
        activation_session_factory
    )
    first = _verify(client, course, user, activation_code)
    first_token = first.cookies[ACTIVATION_COOKIE_NAME]

    second = _verify(client, course, user, activation_code)

    assert second.status_code == 200
    assert second.cookies[ACTIVATION_COOKIE_NAME] != first_token
    assert client.cookies[ACTIVATION_COOKIE_NAME] == (
        second.cookies[ACTIVATION_COOKIE_NAME]
    )


@pytest.mark.parametrize(
    "failure_case",
    [
        "course_missing",
        "course_inactive",
        "username_missing",
        "not_enrolled",
        "instructor_user",
        "inactive_user",
        "active_enrollment",
        "disabled_enrollment",
        "used_code",
        "expired_code",
        "wrong_code",
        "missing_hash",
        "damaged_hash",
    ],
)
def test_all_invalid_credentials_have_one_uniform_failure_and_one_verification(
    failure_case,
    monkeypatch,
    client,
    activation_session_factory,
):
    options: dict[str, object] = {}
    if failure_case == "course_inactive":
        options["course_active"] = False
    elif failure_case == "instructor_user":
        options["user_role"] = UserRole.INSTRUCTOR
    elif failure_case == "inactive_user":
        options["user_active"] = False
    elif failure_case == "active_enrollment":
        options["status"] = EnrollmentStatus.ACTIVE
    elif failure_case == "disabled_enrollment":
        options["status"] = EnrollmentStatus.DISABLED
    elif failure_case == "used_code":
        options["used"] = True
    elif failure_case == "expired_code":
        options["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
    elif failure_case == "missing_hash":
        options["hash_value"] = "missing"
    elif failure_case == "damaged_hash":
        options["hash_value"] = "damaged"

    course, user, _, activation_code = _create_activation_fixture(
        activation_session_factory,
        **options,
    )
    request_course = course.course_code
    request_username = user.berkeley_username
    request_code = activation_code
    if failure_case == "course_missing":
        request_course = "MISSING-COURSE"
    elif failure_case == "username_missing":
        request_username = "missing-student"
    elif failure_case == "not_enrolled":
        other_user = _create_user(
            activation_session_factory,
            username="not-enrolled-student",
        )
        request_username = other_user.berkeley_username
    elif failure_case == "wrong_code":
        request_code = "IIII-IIII-IIII"

    verify_calls = 0
    original_verify = activation_verification.verify_one_time_secret

    def count_verification(secret, secret_hash):
        nonlocal verify_calls
        verify_calls += 1
        return original_verify(secret, secret_hash)

    monkeypatch.setattr(
        activation_verification,
        "verify_one_time_secret",
        count_verification,
    )
    response = client.post(
        "/api/auth/activate/verify",
        json=_verify_payload(
            request_course,
            request_username,
            request_code,
        ),
    )

    assert response.status_code == 401
    assert response.json() == GENERIC_FAILURE
    assert ACTIVATION_COOKIE_NAME not in response.cookies
    assert verify_calls == 1
    assert request_code not in response.text
    assert "hash" not in response.text.lower()


@pytest.mark.parametrize(
    "payload",
    [
        {
            "course_code": "C" * 65,
            "berkeley_username": STUDENT_USERNAME,
            "activation_code": "A",
        },
        {
            "course_code": COURSE_CODE,
            "berkeley_username": "u" * 65,
            "activation_code": "A",
        },
        {
            "course_code": COURSE_CODE,
            "berkeley_username": STUDENT_USERNAME,
            "activation_code": "A" * 33,
        },
        {
            "course_code": COURSE_CODE,
            "berkeley_username": STUDENT_USERNAME,
            "activation_code": "A",
            "user_id": "not-accepted",
        },
    ],
)
def test_invalid_input_is_rejected_before_secret_verification(
    payload,
    monkeypatch,
    client,
):
    def unexpected_verification(_secret, _secret_hash):
        raise AssertionError("verification must not run")

    monkeypatch.setattr(
        activation_verification,
        "verify_one_time_secret",
        unexpected_verification,
    )

    response = client.post("/api/auth/activate/verify", json=payload)

    assert response.status_code == 422


def test_activation_token_claims_are_complete_and_exclude_identity_text(
    client,
    activation_session_factory,
):
    course, user, enrollment, activation_code = _create_activation_fixture(
        activation_session_factory
    )
    response = _verify(client, course, user, activation_code)
    token = response.cookies[ACTIVATION_COOKIE_NAME]
    payload = jwt.decode(
        token,
        TEST_JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=ACTIVATION_TOKEN_AUDIENCE,
    )

    assert payload["sub"] == str(user.id)
    assert payload["enrollment_id"] == str(enrollment.id)
    assert payload["course_id"] == str(course.id)
    assert payload["role"] == "student"
    assert payload["type"] == ACTIVATION_TOKEN_TYPE
    assert {"iat", "exp", "jti", "iss", "aud", "activation_version"} <= set(
        payload
    )
    forbidden_claims = {
        "berkeley_username",
        "course_code",
        "activation_code",
        "activation_code_hash",
        "password",
        "password_hash",
        "jwt_secret",
    }
    assert forbidden_claims.isdisjoint(payload)
    assert user.berkeley_username not in token
    assert course.course_code not in token
    assert activation_code not in token
    assert TEST_JWT_SECRET not in token


@pytest.mark.parametrize(
    "mutation",
    ["algorithm", "expired", "audience", "type", "uuid", "issuer"],
)
def test_activation_token_decoder_rejects_invalid_claims(
    mutation,
    activation_session_factory,
    auth_settings,
):
    course, user, enrollment, _ = _create_activation_fixture(
        activation_session_factory
    )
    assert enrollment.activation_code_hash is not None
    token = create_activation_token(
        user_id=user.id,
        enrollment_id=enrollment.id,
        course_id=course.id,
        activation_code_hash=enrollment.activation_code_hash,
        settings=auth_settings,
        now=(
            datetime.now(UTC) - timedelta(minutes=11)
            if mutation == "expired"
            else None
        ),
    )
    if mutation != "expired":
        payload = jwt.decode(
            token,
            TEST_JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={
                "verify_signature": True,
                "verify_exp": False,
                "verify_aud": False,
            },
        )
        if mutation == "audience":
            payload["aud"] = "wrong-audience"
        elif mutation == "type":
            payload["type"] = "access"
        elif mutation == "uuid":
            payload["enrollment_id"] = "not-a-uuid"
        elif mutation == "issuer":
            payload["iss"] = "wrong-issuer"
        algorithm = "HS384" if mutation == "algorithm" else JWT_ALGORITHM
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm=algorithm)

    with pytest.raises(InvalidActivationTokenError):
        decode_activation_token(token, auth_settings)


def test_valid_activation_cookie_resolves_database_context(
    client,
    activation_session_factory,
):
    course, user, _, activation_code = _create_activation_fixture(
        activation_session_factory
    )
    assert _verify(client, course, user, activation_code).status_code == 200

    response = client.get("/test/activation-context")

    assert response.status_code == 200
    assert response.json() == {"valid": True}


@pytest.mark.parametrize(
    "state_change",
    [
        "regenerate",
        "clear_hash",
        "active",
        "disabled",
        "course_inactive",
        "user_inactive",
    ],
)
def test_activation_context_rejects_changed_database_state(
    state_change,
    client,
    activation_session_factory,
):
    course, user, enrollment, activation_code = _create_activation_fixture(
        activation_session_factory
    )
    assert _verify(client, course, user, activation_code).status_code == 200

    with activation_session_factory() as session:
        stored = session.get(Enrollment, enrollment.id)
        assert stored is not None
        if state_change == "regenerate":
            regenerate_activation_code(stored)
        elif state_change == "clear_hash":
            stored.activation_code_hash = None
        elif state_change == "active":
            stored.status = EnrollmentStatus.ACTIVE
            stored.activation_used_at = datetime.now(UTC)
        elif state_change == "disabled":
            stored.status = EnrollmentStatus.DISABLED
        elif state_change == "course_inactive":
            session.get(CourseInstance, course.id).is_active = False
        elif state_change == "user_inactive":
            session.get(User, user.id).is_active = False
        session.commit()

    response = client.get("/test/activation-context")

    assert response.status_code == 401
    assert response.json() == {
        "detail": ACTIVATION_CONTEXT_REQUIRED_MESSAGE
    }


def test_activation_context_rejects_mismatched_relationship_claims(
    client,
    activation_session_factory,
    auth_settings,
):
    course, user, enrollment, _ = _create_activation_fixture(
        activation_session_factory
    )
    other_owner = _create_user(
        activation_session_factory,
        username="other-owner",
        role=UserRole.INSTRUCTOR,
    )
    other_course = _create_course(
        activation_session_factory,
        owner=other_owner,
        code="IEOR150-OtherActivation",
    )
    assert enrollment.activation_code_hash is not None
    token = create_activation_token(
        user_id=user.id,
        enrollment_id=enrollment.id,
        course_id=other_course.id,
        activation_code_hash=enrollment.activation_code_hash,
        settings=auth_settings,
    )
    client.cookies.set(ACTIVATION_COOKIE_NAME, token)

    response = client.get("/test/activation-context")

    assert response.status_code == 401
    assert response.json() == {
        "detail": ACTIVATION_CONTEXT_REQUIRED_MESSAGE
    }


def test_missing_and_malformed_activation_cookies_share_one_failure(client):
    missing = client.get("/test/activation-context")
    client.cookies.set(ACTIVATION_COOKIE_NAME, "not-a-token")
    malformed = client.get("/test/activation-context")

    assert missing.status_code == malformed.status_code == 401
    assert missing.json() == malformed.json() == {
        "detail": ACTIVATION_CONTEXT_REQUIRED_MESSAGE
    }


def test_logout_clears_access_and_activation_cookies(
    client,
    activation_session_factory,
):
    course, user, _, activation_code = _create_activation_fixture(
        activation_session_factory
    )
    assert _verify(client, course, user, activation_code).status_code == 200
    client.cookies.set(ACCESS_COOKIE_NAME, "test-only-access-cookie")

    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    cookie_headers = [
        value.lower() for value in response.headers.get_list("set-cookie")
    ]
    assert any(
        header.startswith(f"{ACCESS_COOKIE_NAME}=")
        and "max-age=0" in header
        and "path=/" in header
        and "samesite=lax" in header
        for header in cookie_headers
    )
    assert any(
        header.startswith(f"{ACTIVATION_COOKIE_NAME}=")
        and "max-age=0" in header
        and "path=/" in header
        and "samesite=lax" in header
        for header in cookie_headers
    )


def test_public_and_proxy_activation_paths_share_handler_and_schema_visibility(
    client,
    activation_session_factory,
):
    first_course, first_user, _, first_code = _create_activation_fixture(
        activation_session_factory
    )
    public = _verify(client, first_course, first_user, first_code)
    client.cookies.clear()
    second_owner = _create_user(
        activation_session_factory,
        username="proxy-owner",
        role=UserRole.INSTRUCTOR,
    )
    second_user = _create_user(
        activation_session_factory,
        username="proxy-student",
    )
    second_course = _create_course(
        activation_session_factory,
        owner=second_owner,
        code="IEOR150-ProxyActivation",
    )
    second_enrollment = Enrollment(
        course_id=second_course.id,
        user_id=second_user.id,
    )
    second_code = issue_activation_code(second_enrollment)
    with activation_session_factory() as session:
        session.add(second_enrollment)
        session.commit()
    proxy = _verify(
        client,
        second_course,
        second_user,
        second_code,
        path="/auth/activate/verify",
    )
    paths = client.get("/openapi.json").json()["paths"]

    assert public.status_code == proxy.status_code == 200
    assert "/api/auth/activate/verify" in paths
    assert "/auth/activate/verify" not in paths


@pytest.mark.parametrize(
    "minutes",
    [4, 31],
)
def test_activation_token_lifetime_is_bounded(minutes):
    with pytest.raises(ValidationError):
        _settings(activation_minutes=minutes)


@pytest.mark.parametrize("secret", [None, "too-short"])
def test_activation_token_requires_secure_jwt_secret(secret):
    settings = _settings(jwt_secret=secret)

    with pytest.raises(AuthConfigurationError):
        create_activation_token(
            user_id=uuid.uuid4(),
            enrollment_id=uuid.uuid4(),
            course_id=uuid.uuid4(),
            activation_code_hash="test-only-hash-placeholder",
            settings=settings,
        )
