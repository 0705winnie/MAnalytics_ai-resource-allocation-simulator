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
from app.models import CourseInstance, Enrollment, SimulationSession, User
from app.models.enums import EnrollmentStatus, UserRole
from app.routers import instructor_roster
from app.services.activation_codes import ACTIVATION_CODE_TTL, verify_activation_code


TEST_JWT_SECRET = "test-only-roster-api-signing-secret-32-characters"
INSTRUCTOR = "roster-instructor"
OTHER_INSTRUCTOR = "other-roster-instructor"
STUDENT = "roster-student"


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
        session.execute(delete(SimulationSession))
        session.execute(delete(Enrollment))
        session.execute(delete(CourseInstance))
        session.execute(delete(User))
        session.commit()


@pytest.fixture(scope="module", autouse=True)
def account_schema(test_alembic_config):
    command.upgrade(test_alembic_config, "head")


@pytest.fixture
def roster_session_factory(
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
    roster_session_factory: sessionmaker[Session],
) -> Callable[[AuthSettings], object]:
    def build(settings: AuthSettings):
        api = create_app(settings)

        def override_get_db() -> Generator[Session, None, None]:
            with roster_session_factory() as session:
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
    role: UserRole = UserRole.INSTRUCTOR,
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
    code: str = "IEOR150-Roster",
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


def _authenticate(
    client: TestClient,
    user: User,
    settings: AuthSettings,
) -> None:
    client.cookies.set(
        ACCESS_COOKIE_NAME,
        create_access_token(user.id, user.role, settings),
    )


def _upload(
    client: TestClient,
    course: CourseInstance,
    content: bytes,
    *,
    path_prefix: str = "/api",
):
    return client.post(
        f"{path_prefix}/instructor/courses/{course.id}/roster/import",
        files={"file": ("roster.csv", content, "text/csv")},
    )


def _response_rows(response) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(response.text)))


def test_import_creates_student_pending_enrollment_and_verifiable_one_time_code(
    client,
    roster_session_factory,
    auth_settings,
):
    instructor = _create_user(roster_session_factory, INSTRUCTOR)
    course = _create_course(roster_session_factory, instructor)
    _authenticate(client, instructor, auth_settings)
    before = datetime.now(UTC)

    response = _upload(
        client,
        course,
        b"berkeley_username\n  New.Student-1  \n",
    )

    assert response.status_code == 200
    rows = _response_rows(response)
    assert len(rows) == 1
    row = rows[0]
    assert row["berkeley_username"] == "new.student-1"
    assert row["course_id"] == course.course_identifier
    assert row["status"] == "created"
    code = row["activation_code"]
    assert re.fullmatch(r"[A-Z2-9]{4}(?:-[A-Z2-9]{4}){2}", code)

    with roster_session_factory() as session:
        user = session.scalar(
            select(User).where(User.berkeley_username == "new.student-1")
        )
        assert user is not None
        assert user.role == UserRole.STUDENT
        assert user.is_active is True
        assert user.password_hash is None
        enrollment = session.scalar(
            select(Enrollment).where(
                Enrollment.course_id == course.id,
                Enrollment.user_id == user.id,
            )
        )
        assert enrollment is not None
        assert enrollment.status == EnrollmentStatus.PENDING
        assert enrollment.nickname is None
        assert enrollment.activation_code_hash is not None
        assert enrollment.activation_code_hash != code
        assert code.replace("-", "") not in enrollment.activation_code_hash
        assert verify_activation_code(enrollment, code)
        assert enrollment.activation_expires_at is not None
        assert enrollment.simulation_session is not None
        assert enrollment.simulation_session.completed_months == 0
        assert enrollment.simulation_session.last_completed_at is None
        expires_at = enrollment.activation_expires_at.astimezone(UTC)
        assert before + ACTIVATION_CODE_TTL <= expires_at
        assert expires_at <= datetime.now(UTC) + ACTIVATION_CODE_TTL


def test_existing_active_student_can_join_multiple_courses(
    client,
    roster_session_factory,
    auth_settings,
):
    instructor = _create_user(roster_session_factory, INSTRUCTOR)
    student = _create_user(
        roster_session_factory,
        STUDENT,
        role=UserRole.STUDENT,
    )
    first_course = _create_course(
        roster_session_factory,
        instructor,
        code="IEOR150-A",
    )
    second_course = _create_course(
        roster_session_factory,
        instructor,
        code="IEOR150-B",
    )
    _authenticate(client, instructor, auth_settings)

    first = _upload(
        client,
        first_course,
        f"berkeley_username\n{student.berkeley_username}\n".encode(),
    )
    second = _upload(
        client,
        second_course,
        f"berkeley_username\n{student.berkeley_username}\n".encode(),
    )

    assert first.status_code == second.status_code == 200
    assert _response_rows(first)[0]["status"] == "created"
    assert _response_rows(second)[0]["status"] == "created"
    with roster_session_factory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.berkeley_username == STUDENT)
        ) == 1
        assert session.scalar(
            select(func.count())
            .select_from(Enrollment)
            .where(Enrollment.user_id == student.id)
        ) == 2
        assert session.scalar(
            select(func.count())
            .select_from(SimulationSession)
            .join(Enrollment)
            .where(Enrollment.user_id == student.id)
        ) == 2


def test_already_enrolled_does_not_change_or_return_existing_code(
    client,
    roster_session_factory,
    auth_settings,
):
    instructor = _create_user(roster_session_factory, INSTRUCTOR)
    course = _create_course(roster_session_factory, instructor)
    _authenticate(client, instructor, auth_settings)
    content = b"berkeley_username\nexisting-student\n"
    first = _upload(client, course, content)
    first_code = _response_rows(first)[0]["activation_code"]
    with roster_session_factory() as session:
        enrollment = session.scalar(
            select(Enrollment).join(User).where(
                Enrollment.course_id == course.id,
                User.berkeley_username == "existing-student",
            )
        )
        assert enrollment is not None
        original_hash = enrollment.activation_code_hash
        original_expiration = enrollment.activation_expires_at

    second = _upload(client, course, content)

    row = _response_rows(second)[0]
    assert row["status"] == "already_enrolled"
    assert row["activation_code"] == ""
    with roster_session_factory() as session:
        enrollment = session.scalar(
            select(Enrollment).join(User).where(
                Enrollment.course_id == course.id,
                User.berkeley_username == "existing-student",
            )
        )
        assert enrollment is not None
        assert enrollment.activation_code_hash == original_hash
        assert enrollment.activation_expires_at == original_expiration
        assert verify_activation_code(enrollment, first_code)


def test_mixed_roster_reports_duplicates_conflicts_invalid_and_ignores_empty_rows(
    client,
    roster_session_factory,
    auth_settings,
):
    instructor = _create_user(roster_session_factory, INSTRUCTOR)
    _create_user(roster_session_factory, "existing-instructor")
    _create_user(
        roster_session_factory,
        "inactive-student",
        role=UserRole.STUDENT,
        is_active=False,
    )
    course = _create_course(roster_session_factory, instructor)
    _authenticate(client, instructor, auth_settings)
    content = (
        "\ufeffberkeley_username\r\n"
        "NewStudent\r\n"
        "\r\n"
        "newstudent\r\n"
        "existing-instructor\r\n"
        "inactive-student\r\n"
        "bad username\r\n"
        "\"=FORMULA\"\r\n"
    ).encode("utf-8")

    response = _upload(client, course, content)

    assert response.status_code == 200
    rows = _response_rows(response)
    assert [row["status"] for row in rows] == [
        "created",
        "duplicate_input",
        "role_conflict",
        "user_inactive",
        "invalid",
        "invalid",
    ]
    assert rows[0]["berkeley_username"] == "newstudent"
    assert rows[1]["activation_code"] == ""
    assert all(
        bool(row["activation_code"]) == (row["status"] == "created")
        for row in rows
    )
    assert rows[-1]["berkeley_username"].startswith("'=")
    assert response.headers["x-roster-created"] == "1"
    assert response.headers["x-roster-invalid"] == "2"
    assert response.headers["x-roster-conflicts"] == "2"
    with roster_session_factory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.berkeley_username == "bad username")
        ) == 0
        assert session.scalar(
            select(func.count())
            .select_from(Enrollment)
            .where(Enrollment.course_id == course.id)
        ) == 1


@pytest.mark.parametrize(
    ("content", "expected_detail"),
    [
        (b"", "empty"),
        (b"berkeley_username\n", "no data rows"),
        (b"berkeley_username\n\n \n\t\n", "no data rows"),
        (b"not_the_header\nstudent\n", "exactly"),
        (b"berkeley_username,extra\nstudent,value\n", "exactly"),
        (
            b"berkeley_username,berkeley_username\nstudent,student\n",
            "exactly",
        ),
        (b"berkeley_username\nstudent,extra\n", "one column"),
        (b'berkeley_username\n"unterminated\n', "malformed"),
        (b"\xff\xfe\xfa", "UTF-8"),
    ],
)
def test_invalid_csv_structures_are_rejected_safely(
    content,
    expected_detail,
    client,
    roster_session_factory,
    auth_settings,
):
    instructor = _create_user(roster_session_factory, INSTRUCTOR)
    course = _create_course(roster_session_factory, instructor)
    _authenticate(client, instructor, auth_settings)

    response = _upload(client, course, content)

    assert response.status_code == 422
    assert expected_detail in response.json()["detail"]
    with roster_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Enrollment)) == 0
        assert session.scalar(select(func.count()).select_from(SimulationSession)) == 0


def test_file_and_row_limits_are_enforced(
    client,
    roster_session_factory,
    auth_settings,
):
    instructor = _create_user(roster_session_factory, INSTRUCTOR)
    course = _create_course(roster_session_factory, instructor)
    _authenticate(client, instructor, auth_settings)

    oversized = _upload(client, course, b"x" * (1024 * 1024 + 1))
    too_many_rows = _upload(
        client,
        course,
        (
            "berkeley_username\n"
            + "".join(f"student{i}\n" for i in range(1001))
        ).encode(),
    )

    assert oversized.status_code == 413
    assert too_many_rows.status_code == 422
    assert "1000-row limit" in too_many_rows.json()["detail"]


def test_course_ownership_activity_and_uuid_are_enforced(
    client,
    roster_session_factory,
    auth_settings,
):
    instructor = _create_user(roster_session_factory, INSTRUCTOR)
    other = _create_user(roster_session_factory, OTHER_INSTRUCTOR)
    other_course = _create_course(roster_session_factory, other)
    inactive_course = _create_course(
        roster_session_factory,
        instructor,
        code="IEOR150-Inactive",
        is_active=False,
    )
    _authenticate(client, instructor, auth_settings)

    not_owned = _upload(client, other_course, b"berkeley_username\nstudent1\n")
    missing = client.post(
        f"/api/instructor/courses/{uuid.uuid4()}/roster/import",
        files={"file": ("roster.csv", b"berkeley_username\nstudent1\n")},
    )
    inactive = _upload(
        client,
        inactive_course,
        b"berkeley_username\nstudent1\n",
    )
    invalid_uuid = client.post(
        "/api/instructor/courses/not-a-uuid/roster/import",
        files={"file": ("roster.csv", b"berkeley_username\nstudent1\n")},
    )

    assert not_owned.status_code == missing.status_code == 404
    assert not_owned.json() == missing.json() == {"detail": "Course not found"}
    assert inactive.status_code == 409
    assert invalid_uuid.status_code == 422


def test_authentication_and_instructor_role_are_enforced(
    client,
    roster_session_factory,
    auth_settings,
):
    instructor = _create_user(roster_session_factory, INSTRUCTOR)
    course = _create_course(roster_session_factory, instructor)
    content = b"berkeley_username\nstudent1\n"

    unauthenticated = _upload(client, course, content)
    student = _create_user(
        roster_session_factory,
        STUDENT,
        role=UserRole.STUDENT,
    )
    enrollment = Enrollment(
        course_id=course.id,
        user_id=student.id,
        nickname="Roster Student",
        status=EnrollmentStatus.ACTIVE,
        activation_used_at=datetime.now(UTC),
    )
    with roster_session_factory() as session:
        session.add(enrollment)
        session.commit()
    client.cookies.set(
        ACCESS_COOKIE_NAME,
        create_access_token(
            student.id,
            student.role,
            auth_settings,
            course_id=course.id,
            enrollment_id=enrollment.id,
        ),
    )
    forbidden = _upload(client, course, content)
    client.cookies.clear()
    inactive = _create_user(
        roster_session_factory,
        "inactive-instructor",
        is_active=False,
    )
    _authenticate(client, inactive, auth_settings)
    inactive_response = _upload(client, course, content)

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert inactive_response.status_code == 401


def test_integrity_error_rolls_back_and_returns_no_generated_code(
    monkeypatch,
    client,
    roster_session_factory,
    auth_settings,
):
    instructor = _create_user(roster_session_factory, INSTRUCTOR)
    course = _create_course(roster_session_factory, instructor)
    _authenticate(client, instructor, auth_settings)
    original_import = instructor_roster.import_roster

    def fail_after_import(db, owned_course, rows):
        original_import(db, owned_course, rows)
        raise IntegrityError("safe test statement", {}, Exception("constraint"))

    monkeypatch.setattr(instructor_roster, "import_roster", fail_after_import)
    response = _upload(
        client,
        course,
        b"berkeley_username\nrollback-student\n",
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "The roster could not be imported"}
    assert not re.search(r"[A-Z2-9]{4}(?:-[A-Z2-9]{4}){2}", response.text)
    with roster_session_factory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.berkeley_username == "rollback-student")
        ) == 0
        assert session.scalar(select(func.count()).select_from(Enrollment)) == 0
        assert session.scalar(select(func.count()).select_from(SimulationSession)) == 0


def test_render_failure_rolls_back_without_returning_generated_secret(
    monkeypatch,
    client,
    roster_session_factory,
    auth_settings,
):
    instructor = _create_user(roster_session_factory, INSTRUCTOR)
    course = _create_course(roster_session_factory, instructor)
    _authenticate(client, instructor, auth_settings)
    generated_values: list[str] = []

    def fail_render(rows):
        generated_values.extend(row.activation_code for row in rows)
        raise RuntimeError("private rendering failure")

    monkeypatch.setattr(instructor_roster, "render_roster_csv", fail_render)
    response = _upload(
        client,
        course,
        b"berkeley_username\nrender-rollback-student\n",
    )

    assert generated_values
    assert response.status_code == 500
    assert response.json() == {
        "detail": "The roster import could not be completed"
    }
    assert all(value not in response.text for value in generated_values)
    assert "hash" not in response.text.lower()
    assert "private rendering failure" not in response.text
    with roster_session_factory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.berkeley_username == "render-rollback-student")
        ) == 0
        assert session.scalar(select(func.count()).select_from(Enrollment)) == 0
        assert session.scalar(select(func.count()).select_from(SimulationSession)) == 0


def test_success_response_is_rendered_before_commit_and_returned_after_commit(
    monkeypatch,
    client,
    roster_session_factory,
    auth_settings,
):
    instructor = _create_user(roster_session_factory, INSTRUCTOR)
    course = _create_course(roster_session_factory, instructor)
    _authenticate(client, instructor, auth_settings)
    original_render = instructor_roster.render_roster_csv
    rendered = False
    commit_saw_rendered: list[bool] = []
    original_commit = Session.commit

    def track_render(rows):
        nonlocal rendered
        rendered = True
        return original_render(rows)

    def track_commit(session):
        commit_saw_rendered.append(rendered)
        return original_commit(session)

    monkeypatch.setattr(instructor_roster, "render_roster_csv", track_render)
    monkeypatch.setattr(Session, "commit", track_commit)
    response = _upload(
        client,
        course,
        b"berkeley_username\ncommit-order-student\n",
    )

    assert rendered is True
    assert commit_saw_rendered == [True]
    assert response.status_code == 200
    assert _response_rows(response)[0]["status"] == "created"
    with roster_session_factory() as session:
        enrollment = session.scalar(
            select(Enrollment).join(User).where(
                User.berkeley_username == "commit-order-student"
            )
        )
        assert enrollment is not None
        assert enrollment.simulation_session is not None
        assert enrollment.simulation_session.completed_months == 0


def test_response_is_non_cacheable_attachment_and_spreadsheet_safe(
    client,
    roster_session_factory,
    auth_settings,
):
    instructor = _create_user(roster_session_factory, INSTRUCTOR)
    course = _create_course(
        roster_session_factory,
        instructor,
        code="-SpreadsheetFormula",
    )
    _authenticate(client, instructor, auth_settings)

    response = _upload(
        client,
        course,
        b"berkeley_username\nsafe-student\n",
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="roster-activation-codes.csv"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    row = _response_rows(response)[0]
    assert row["course_id"] == f"'{course.course_identifier}"
    lowered = response.text.lower()
    assert "password_hash" not in lowered
    assert "activation_code_hash" not in lowered
    assert "jwt" not in lowered
    assert "secret" not in lowered
    assert str(instructor.id) not in response.text


def test_public_and_proxy_paths_share_handler_and_only_public_path_is_documented(
    client,
    roster_session_factory,
    auth_settings,
):
    instructor = _create_user(roster_session_factory, INSTRUCTOR)
    first_course = _create_course(
        roster_session_factory,
        instructor,
        code="IEOR150-Public",
    )
    second_course = _create_course(
        roster_session_factory,
        instructor,
        code="IEOR150-Proxy",
    )
    _authenticate(client, instructor, auth_settings)

    public_response = _upload(
        client,
        first_course,
        b"berkeley_username\npublic-student\n",
    )
    proxy_response = _upload(
        client,
        second_course,
        b"berkeley_username\nproxy-student\n",
        path_prefix="",
    )
    paths = client.get("/openapi.json").json()["paths"]

    assert public_response.status_code == proxy_response.status_code == 200
    assert _response_rows(public_response)[0]["status"] == "created"
    assert _response_rows(proxy_response)[0]["status"] == "created"
    public_path = "/api/instructor/courses/{course_id}/roster/import"
    proxy_path = "/instructor/courses/{course_id}/roster/import"
    assert public_path in paths
    assert proxy_path not in paths
