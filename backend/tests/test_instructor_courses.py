import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from alembic import command
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, delete, select
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import ACCESS_COOKIE_NAME, create_access_token, require_instructor
from app.core.config import AuthSettings, get_auth_settings
from app.db.session import get_db
from app.main import create_app
from app.models import CourseInstance, Enrollment, User
from app.models.enums import UserRole


TEST_JWT_SECRET = "test-only-course-api-signing-secret-32-characters"
INSTRUCTOR_A = "course-instructor-a"
INSTRUCTOR_B = "course-instructor-b"
STUDENT = "course-student"
TEST_USERNAMES = {INSTRUCTOR_A, INSTRUCTOR_B, STUDENT}


def _auth_settings() -> AuthSettings:
    return AuthSettings(
        _env_file=None,
        jwt_secret=SecretStr(TEST_JWT_SECRET),
        auth_cookie_secure=False,
        access_token_minutes=30,
        frontend_origin="http://frontend.test",
    )


def _clear_account_tables(
    session_factory: sessionmaker[Session],
    test_database_url: URL,
) -> None:
    assert test_database_url.database is not None
    assert test_database_url.database.endswith("_test")
    with session_factory() as session:
        session.execute(delete(Enrollment))
        session.execute(delete(CourseInstance))
        session.execute(delete(User))
        session.commit()


@pytest.fixture(scope="module", autouse=True)
def account_schema(test_alembic_config):
    command.upgrade(test_alembic_config, "head")


@pytest.fixture
def course_session_factory(
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
    course_session_factory: sessionmaker[Session],
) -> Callable[[AuthSettings], object]:
    def build(settings: AuthSettings):
        api = create_app(settings)

        def override_get_db() -> Generator[Session, None, None]:
            with course_session_factory() as session:
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
    session_factory: sessionmaker[Session],
    *,
    username: str,
    role: UserRole = UserRole.INSTRUCTOR,
    is_active: bool = True,
) -> User:
    user = User(
        berkeley_username=username,
        role=role,
        is_active=is_active,
    )
    with session_factory() as session:
        session.add(user)
        session.commit()
    return user


def _authenticate(
    client: TestClient,
    user: User,
    settings: AuthSettings,
    *,
    now: datetime | None = None,
) -> str:
    token = create_access_token(user.id, user.role, settings, now=now)
    client.cookies.set(ACCESS_COOKIE_NAME, token)
    return token


def _create_course(
    session_factory: sessionmaker[Session],
    *,
    owner: User,
    course_id: uuid.UUID,
    code: str,
    created_at: datetime,
    is_active: bool = True,
) -> CourseInstance:
    course = CourseInstance(
        id=course_id,
        course_code=code,
        course_name=f"Course {code}",
        semester="Fall 2026",
        created_by=owner.id,
        is_active=is_active,
        created_at=created_at,
        updated_at=created_at,
    )
    with session_factory() as session:
        session.add(course)
        session.commit()
    return course


def test_instructor_creates_trimmed_active_owned_course(
    client,
    course_session_factory,
    auth_settings,
):
    instructor = _create_user(
        course_session_factory,
        username=INSTRUCTOR_A,
    )
    _authenticate(client, instructor, auth_settings)

    response = client.post(
        "/api/instructor/courses",
        json={
            "course_code": "  IEOR150-Fall2026  ",
            "course_name": "  IEOR 150  ",
            "semester": "  Fall 2026  ",
        },
    )

    assert response.status_code == 201
    assert response.json()["course_code"] == "IEOR150-Fall2026"
    assert response.json()["course_name"] == "IEOR 150"
    assert response.json()["semester"] == "Fall 2026"
    assert response.json()["is_active"] is True

    with course_session_factory() as session:
        stored_course = session.scalar(
            select(CourseInstance).where(
                CourseInstance.id == uuid.UUID(response.json()["id"])
            )
        )
        assert stored_course is not None
        assert stored_course.created_by == instructor.id
        assert stored_course.is_active is True


@pytest.mark.parametrize(
    "duplicate_code",
    ["ieor150-fall2026", "  IEOR150-Fall2026  "],
)
def test_duplicate_course_code_returns_safe_conflict(
    duplicate_code,
    client,
    course_session_factory,
    auth_settings,
):
    instructor = _create_user(
        course_session_factory,
        username=INSTRUCTOR_A,
    )
    _authenticate(client, instructor, auth_settings)
    original_payload = {
        "course_code": "IEOR150-Fall2026",
        "course_name": "IEOR 150",
        "semester": "Fall 2026",
    }
    assert client.post(
        "/api/instructor/courses",
        json=original_payload,
    ).status_code == 201

    response = client.post(
        "/api/instructor/courses",
        json={**original_payload, "course_code": duplicate_code},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "A course with this course code already exists"
    }


def test_integrity_error_rolls_back_and_returns_safe_conflict(
    client,
    auth_settings,
):
    instructor = User(
        id=uuid.uuid4(),
        berkeley_username=INSTRUCTOR_A,
        role=UserRole.INSTRUCTOR,
        is_active=True,
    )
    db = MagicMock(spec=Session)
    db.scalar.return_value = None
    db.commit.side_effect = IntegrityError(
        "statement",
        {},
        RuntimeError("database details must remain private"),
    )
    client.app.dependency_overrides[require_instructor] = lambda: instructor
    client.app.dependency_overrides[get_db] = lambda: db

    response = client.post(
        "/api/instructor/courses",
        json={
            "course_code": "IEOR150-Fall2026",
            "course_name": "IEOR 150",
            "semester": "Fall 2026",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "A course with this course code already exists"
    }
    db.rollback.assert_called_once_with()
    assert "database details" not in response.text


@pytest.mark.parametrize(
    "payload",
    [
        {
            "course_code": "",
            "course_name": "IEOR 150",
            "semester": "Fall 2026",
        },
        {
            "course_code": "C" * 65,
            "course_name": "IEOR 150",
            "semester": "Fall 2026",
        },
        {
            "course_code": "IEOR150",
            "course_name": "   ",
            "semester": "Fall 2026",
        },
        {
            "course_code": "IEOR150",
            "course_name": "N" * 256,
            "semester": "Fall 2026",
        },
        {
            "course_code": "IEOR150",
            "course_name": "IEOR 150",
            "semester": "",
        },
        {
            "course_code": "IEOR150",
            "course_name": "IEOR 150",
            "semester": "S" * 65,
        },
        {
            "course_code": "IEOR150",
            "course_name": "IEOR 150",
            "semester": "Fall 2026",
            "created_by": str(uuid.uuid4()),
        },
    ],
)
def test_create_rejects_invalid_fields_and_extra_data(
    payload,
    client,
    course_session_factory,
    auth_settings,
):
    instructor = _create_user(
        course_session_factory,
        username=INSTRUCTOR_A,
    )
    _authenticate(client, instructor, auth_settings)

    response = client.post("/api/instructor/courses", json=payload)

    assert response.status_code == 422


def test_student_cannot_create_course(
    client,
    course_session_factory,
    auth_settings,
):
    student = _create_user(
        course_session_factory,
        username=STUDENT,
        role=UserRole.STUDENT,
    )
    _authenticate(client, student, auth_settings)

    response = client.post(
        "/api/instructor/courses",
        json={
            "course_code": "IEOR150",
            "course_name": "IEOR 150",
            "semester": "Fall 2026",
        },
    )

    assert response.status_code == 403


def test_unauthenticated_create_returns_401(client):
    response = client.post(
        "/api/instructor/courses",
        json={
            "course_code": "IEOR150",
            "course_name": "IEOR 150",
            "semester": "Fall 2026",
        },
    )

    assert response.status_code == 401


@pytest.mark.parametrize("credential_state", ["invalid", "expired", "inactive"])
def test_invalid_expired_or_inactive_instructor_cookie_returns_401(
    credential_state,
    client,
    course_session_factory,
    auth_settings,
):
    instructor = _create_user(
        course_session_factory,
        username=INSTRUCTOR_A,
        is_active=credential_state != "inactive",
    )
    if credential_state == "invalid":
        client.cookies.set(ACCESS_COOKIE_NAME, "not-a-valid-token")
    elif credential_state == "expired":
        _authenticate(
            client,
            instructor,
            auth_settings,
            now=datetime.now(UTC) - timedelta(minutes=31),
        )
    else:
        _authenticate(client, instructor, auth_settings)

    response = client.get("/api/instructor/courses")

    assert response.status_code == 401


def test_list_is_owner_scoped_paginated_and_stably_sorted(
    client,
    course_session_factory,
    auth_settings,
):
    instructor_a = _create_user(
        course_session_factory,
        username=INSTRUCTOR_A,
    )
    instructor_b = _create_user(
        course_session_factory,
        username=INSTRUCTOR_B,
    )
    older = datetime(2026, 1, 1, tzinfo=UTC)
    newer = datetime(2026, 2, 1, tzinfo=UTC)
    a1 = _create_course(
        course_session_factory,
        owner=instructor_a,
        course_id=uuid.UUID(int=1),
        code="A-1",
        created_at=older,
    )
    a2 = _create_course(
        course_session_factory,
        owner=instructor_a,
        course_id=uuid.UUID(int=2),
        code="A-2",
        created_at=newer,
    )
    a3 = _create_course(
        course_session_factory,
        owner=instructor_a,
        course_id=uuid.UUID(int=3),
        code="A-3",
        created_at=newer,
    )
    _create_course(
        course_session_factory,
        owner=instructor_b,
        course_id=uuid.UUID(int=4),
        code="B-1",
        created_at=newer + timedelta(days=1),
    )
    _authenticate(client, instructor_a, auth_settings)

    first_page = client.get(
        "/api/instructor/courses",
        params={"offset": 0, "limit": 2},
    )
    second_page = client.get(
        "/api/instructor/courses",
        params={"offset": 2, "limit": 2},
    )

    assert first_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert first_page.json()["offset"] == 0
    assert first_page.json()["limit"] == 2
    assert [item["id"] for item in first_page.json()["items"]] == [
        str(a3.id),
        str(a2.id),
    ]
    assert second_page.json()["total"] == 3
    assert [item["id"] for item in second_page.json()["items"]] == [str(a1.id)]


@pytest.mark.parametrize(
    "params",
    [
        {"offset": -1},
        {"limit": 0},
        {"limit": 101},
    ],
)
def test_list_rejects_unsafe_pagination(
    params,
    client,
    course_session_factory,
    auth_settings,
):
    instructor = _create_user(
        course_session_factory,
        username=INSTRUCTOR_A,
    )
    _authenticate(client, instructor, auth_settings)

    assert client.get(
        "/api/instructor/courses",
        params=params,
    ).status_code == 422


def test_course_detail_is_owner_scoped_and_inactive_course_remains_visible(
    client,
    course_session_factory,
    auth_settings,
):
    instructor_a = _create_user(
        course_session_factory,
        username=INSTRUCTOR_A,
    )
    instructor_b = _create_user(
        course_session_factory,
        username=INSTRUCTOR_B,
    )
    owned_course = _create_course(
        course_session_factory,
        owner=instructor_a,
        course_id=uuid.uuid4(),
        code="A-INACTIVE",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        is_active=False,
    )
    other_course = _create_course(
        course_session_factory,
        owner=instructor_b,
        course_id=uuid.uuid4(),
        code="B-PRIVATE",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    _authenticate(client, instructor_a, auth_settings)

    owned_response = client.get(
        f"/api/instructor/courses/{owned_course.id}"
    )
    other_response = client.get(
        f"/api/instructor/courses/{other_course.id}"
    )
    missing_response = client.get(
        f"/api/instructor/courses/{uuid.uuid4()}"
    )

    assert owned_response.status_code == 200
    assert owned_response.json()["is_active"] is False
    assert other_response.status_code == 404
    assert missing_response.status_code == 404
    assert other_response.json() == missing_response.json() == {
        "detail": "Course not found"
    }


def test_invalid_course_uuid_returns_422(
    client,
    course_session_factory,
    auth_settings,
):
    instructor = _create_user(
        course_session_factory,
        username=INSTRUCTOR_A,
    )
    _authenticate(client, instructor, auth_settings)

    response = client.get("/api/instructor/courses/not-a-uuid")

    assert response.status_code == 422


def test_public_and_proxy_stripped_paths_use_same_handlers(
    client,
    course_session_factory,
    auth_settings,
):
    instructor = _create_user(
        course_session_factory,
        username=INSTRUCTOR_A,
    )
    _authenticate(client, instructor, auth_settings)

    created = client.post(
        "/instructor/courses",
        json={
            "course_code": "IEOR150-Proxy",
            "course_name": "IEOR 150",
            "semester": "Fall 2026",
        },
    )
    public_list = client.get("/api/instructor/courses")
    internal_detail = client.get(
        f"/instructor/courses/{created.json()['id']}"
    )
    openapi_paths = client.get("/openapi.json").json()["paths"]

    assert created.status_code == 201
    assert public_list.status_code == 200
    assert internal_detail.status_code == 200
    assert "/api/instructor/courses" in openapi_paths
    assert "/instructor/courses" not in openapi_paths


def test_course_responses_exclude_private_and_secret_fields(
    client,
    course_session_factory,
    auth_settings,
):
    instructor = _create_user(
        course_session_factory,
        username=INSTRUCTOR_A,
    )
    token = _authenticate(client, instructor, auth_settings)

    response = client.post(
        "/api/instructor/courses",
        json={
            "course_code": "IEOR150-Safe",
            "course_name": "IEOR 150",
            "semester": "Fall 2026",
        },
    )

    assert response.status_code == 201
    assert set(response.json()) == {
        "id",
        "course_code",
        "course_name",
        "semester",
        "is_active",
        "created_at",
        "updated_at",
    }
    response_text = response.text.lower()
    assert "password" not in response_text
    assert "password_hash" not in response_text
    assert "jwt" not in response_text
    assert "secret" not in response_text
    assert token not in response.text
