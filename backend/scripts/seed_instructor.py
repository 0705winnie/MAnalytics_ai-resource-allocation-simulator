"""Idempotently seed the local development instructor account."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Protocol

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import (
    DevelopmentInstructorSettings,
    get_development_instructor_settings,
)
from app.core.security import hash_password
from app.models import User
from app.models.enums import UserRole


class InstructorSeedError(RuntimeError):
    """A safe, user-facing seed failure that never contains credentials."""


@dataclass(frozen=True)
class InstructorSeedResult:
    user: User
    created: bool


class SessionFactory(Protocol):
    def __call__(self) -> Session: ...


def require_seed_credentials(
    settings: DevelopmentInstructorSettings,
) -> tuple[str, str]:
    """Return normalized credentials or fail without exposing their values."""

    username = settings.dev_instructor_username
    password_setting: SecretStr | None = settings.dev_instructor_password
    password = password_setting.get_secret_value() if password_setting else ""

    if not username:
        raise InstructorSeedError("DEV_INSTRUCTOR_USERNAME must be set")
    if not password:
        raise InstructorSeedError("DEV_INSTRUCTOR_PASSWORD must be set")
    if len(username) > 64:
        raise InstructorSeedError(
            "DEV_INSTRUCTOR_USERNAME must contain at most 64 characters"
        )
    if len(password) < 12:
        raise InstructorSeedError(
            "DEV_INSTRUCTOR_PASSWORD must contain at least 12 characters"
        )
    return username, password


def seed_instructor(
    session: Session,
    username: str,
    password: str,
) -> InstructorSeedResult:
    """Create one instructor without committing or changing an existing user."""

    normalized_username = username.strip().lower()
    if not normalized_username or len(normalized_username) > 64:
        raise InstructorSeedError(
            "DEV_INSTRUCTOR_USERNAME must contain between 1 and 64 characters"
        )
    if len(password) < 12:
        raise InstructorSeedError(
            "DEV_INSTRUCTOR_PASSWORD must contain at least 12 characters"
        )

    existing_user = session.scalar(
        select(User).where(User.berkeley_username == normalized_username)
    )
    if existing_user is not None:
        if existing_user.role != UserRole.INSTRUCTOR:
            raise InstructorSeedError(
                "The configured username already belongs to a non-instructor user"
            )
        if not existing_user.is_active:
            raise InstructorSeedError(
                "The configured instructor is disabled and cannot be seeded"
            )
        return InstructorSeedResult(user=existing_user, created=False)

    instructor = User(
        berkeley_username=normalized_username,
        password_hash=hash_password(password),
        role=UserRole.INSTRUCTOR,
        is_active=True,
    )
    session.add(instructor)
    session.flush()
    return InstructorSeedResult(user=instructor, created=True)


def main(
    settings: DevelopmentInstructorSettings | None = None,
    session_factory: SessionFactory | None = None,
) -> int:
    """Run the local seed command and emit only non-sensitive status."""

    try:
        seed_settings = settings or get_development_instructor_settings()
        username, password = require_seed_credentials(seed_settings)
        if session_factory is None:
            from app.db.session import SessionLocal

            session_factory = SessionLocal
        with session_factory() as session:
            result = seed_instructor(session, username, password)
            session.commit()
    except InstructorSeedError as exc:
        print(f"Instructor seed failed: {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("Instructor seed failed: database operation was unsuccessful", file=sys.stderr)
        return 1

    outcome = "created" if result.created else "already exists; password unchanged"
    print(f"Development instructor {outcome}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
