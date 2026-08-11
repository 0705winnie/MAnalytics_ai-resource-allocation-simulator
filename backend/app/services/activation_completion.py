"""Atomic preparation of a completed Student course activation."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.activation_auth import (
    ActivationContext,
    lock_activation_context,
)
from app.core.auth import create_access_token
from app.core.config import AuthSettings
from app.core.security import hash_password
from app.models.enums import UserRole
from app.services.activation_codes import mark_activation_used


class ActivationCompletionError(RuntimeError):
    """A safe, retryable completion error."""


class InvalidNicknameError(ActivationCompletionError):
    pass


@dataclass(frozen=True)
class PreparedActivationCompletion:
    context: ActivationContext
    access_token: str


def _nickname_identity(value: str) -> str:
    return "".join(
        character
        for character in value.casefold()
        if character not in {" ", "-", "_", "."}
    )


def prepare_activation_completion(
    db: Session,
    *,
    activation_token: str,
    password: str,
    nickname: str,
    settings: AuthSettings,
) -> PreparedActivationCompletion:
    """Lock, revalidate, and prepare all activation writes without committing."""

    context = lock_activation_context(db, activation_token, settings)
    user = context.user
    enrollment = context.enrollment

    if _nickname_identity(nickname) == _nickname_identity(
        user.berkeley_username
    ):
        raise InvalidNicknameError("Nickname is invalid")

    user.password_hash = hash_password(password)

    enrollment.nickname = nickname
    mark_activation_used(enrollment)
    access_token = create_access_token(
        user.id,
        UserRole.STUDENT,
        settings,
        course_id=context.course.id,
        enrollment_id=enrollment.id,
    )
    return PreparedActivationCompletion(
        context=context,
        access_token=access_token,
    )
