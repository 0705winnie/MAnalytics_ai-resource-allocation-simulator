"""Parse roster CSV files and prepare one-time student activation exports."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CourseInstance, Enrollment, User
from app.models.enums import EnrollmentStatus, UserRole
from app.services.activation_codes import issue_activation_code


MAX_ROSTER_BYTES = 1024 * 1024
MAX_ROSTER_ROWS = 1000
ROSTER_HEADER = "berkeley_username"
_USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_FORMULA_PREFIXES = ("=", "+", "-", "@")


class RosterImportStatus(StrEnum):
    CREATED = "created"
    ALREADY_ENROLLED = "already_enrolled"
    DUPLICATE_INPUT = "duplicate_input"
    INVALID = "invalid"
    ROLE_CONFLICT = "role_conflict"
    USER_INACTIVE = "user_inactive"


class RosterCsvError(ValueError):
    """A safe CSV validation error that contains no uploaded content."""


@dataclass(frozen=True)
class RosterInputRow:
    username: str
    is_valid: bool


@dataclass(frozen=True)
class RosterImportRow:
    berkeley_username: str
    course_code: str
    activation_code: str
    status: RosterImportStatus
    message: str


def parse_roster_csv(content: bytes) -> list[RosterInputRow]:
    """Validate and normalize a one-column UTF-8 roster."""

    if not content:
        raise RosterCsvError("The roster CSV is empty")
    if len(content) > MAX_ROSTER_BYTES:
        raise RosterCsvError("The roster CSV exceeds the 1 MB limit")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RosterCsvError("The roster CSV must be valid UTF-8") from exc

    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader, None)
        if header is None:
            raise RosterCsvError("The roster CSV is missing its header")
        if header != [ROSTER_HEADER]:
            raise RosterCsvError(
                "The roster CSV must contain exactly the berkeley_username header"
            )

        rows: list[RosterInputRow] = []
        for values in reader:
            if not values or all(not value.strip() for value in values):
                continue
            if len(values) != 1:
                raise RosterCsvError(
                    "Each roster CSV row must contain exactly one column"
                )
            if len(rows) >= MAX_ROSTER_ROWS:
                raise RosterCsvError("The roster CSV exceeds the 1000-row limit")

            username = values[0].strip().lower()
            rows.append(
                RosterInputRow(
                    username=username,
                    is_valid=bool(_USERNAME_PATTERN.fullmatch(username)),
                )
            )
    except csv.Error as exc:
        raise RosterCsvError("The roster CSV is malformed") from exc

    if not rows:
        raise RosterCsvError("The roster CSV contains no data rows")
    return rows


def import_roster(
    db: Session,
    course: CourseInstance,
    input_rows: list[RosterInputRow],
) -> list[RosterImportRow]:
    """Prepare users, enrollments, and one-time codes without committing."""

    valid_usernames = {row.username for row in input_rows if row.is_valid}
    users_by_username = {
        user.berkeley_username: user
        for user in db.scalars(
            select(User).where(User.berkeley_username.in_(valid_usernames))
        )
    }
    existing_user_ids = [user.id for user in users_by_username.values()]
    enrolled_user_ids = (
        set(
            db.scalars(
                select(Enrollment.user_id).where(
                    Enrollment.course_id == course.id,
                    Enrollment.user_id.in_(existing_user_ids),
                )
            )
        )
        if existing_user_ids
        else set()
    )

    results: list[RosterImportRow] = []
    seen_valid_usernames: set[str] = set()
    for input_row in input_rows:
        username = input_row.username
        if not input_row.is_valid:
            results.append(
                _result(
                    username,
                    course.course_code,
                    RosterImportStatus.INVALID,
                    "Invalid Berkeley username",
                )
            )
            continue
        if username in seen_valid_usernames:
            results.append(
                _result(
                    username,
                    course.course_code,
                    RosterImportStatus.DUPLICATE_INPUT,
                    "Duplicate username in uploaded roster",
                )
            )
            continue
        seen_valid_usernames.add(username)

        user = users_by_username.get(username)
        if user is not None and not user.is_active:
            results.append(
                _result(
                    username,
                    course.course_code,
                    RosterImportStatus.USER_INACTIVE,
                    "The existing user is inactive",
                )
            )
            continue
        if user is not None and user.role == UserRole.INSTRUCTOR:
            results.append(
                _result(
                    username,
                    course.course_code,
                    RosterImportStatus.ROLE_CONFLICT,
                    "The username belongs to an instructor",
                )
            )
            continue
        if user is not None and user.id in enrolled_user_ids:
            results.append(
                _result(
                    username,
                    course.course_code,
                    RosterImportStatus.ALREADY_ENROLLED,
                    "The student is already enrolled",
                )
            )
            continue

        if user is None:
            user = User(
                berkeley_username=username,
                password_hash=None,
                role=UserRole.STUDENT,
                is_active=True,
            )
            db.add(user)
            users_by_username[username] = user

        enrollment = Enrollment(
            course=course,
            user=user,
            nickname=None,
            status=EnrollmentStatus.PENDING,
        )
        activation_code = issue_activation_code(enrollment)
        db.add(enrollment)
        results.append(
            _result(
                username,
                course.course_code,
                RosterImportStatus.CREATED,
                "Student enrollment created",
                activation_code=activation_code,
            )
        )

    return results


def render_roster_csv(rows: list[RosterImportRow]) -> str:
    """Render a spreadsheet-safe CSV containing codes only for created rows."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(
        [
            "berkeley_username",
            "course_code",
            "activation_code",
            "status",
            "message",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                spreadsheet_safe_csv_cell(row.berkeley_username),
                spreadsheet_safe_csv_cell(row.course_code),
                spreadsheet_safe_csv_cell(row.activation_code),
                spreadsheet_safe_csv_cell(row.status.value),
                spreadsheet_safe_csv_cell(row.message),
            ]
        )
    return output.getvalue()


def roster_summary(rows: list[RosterImportRow]) -> dict[str, int]:
    counts = {status.value: 0 for status in RosterImportStatus}
    for row in rows:
        counts[row.status.value] += 1
    return counts


def _result(
    username: str,
    course_code: str,
    status: RosterImportStatus,
    message: str,
    *,
    activation_code: str = "",
) -> RosterImportRow:
    return RosterImportRow(
        berkeley_username=username,
        course_code=course_code,
        activation_code=activation_code if status == RosterImportStatus.CREATED else "",
        status=status,
        message=message,
    )


def spreadsheet_safe_csv_cell(value: str) -> str:
    """Prevent exported values from being interpreted as spreadsheet formulas."""

    return f"'{value}" if value.startswith(_FORMULA_PREFIXES) else value
