"""Password and one-time-secret hashing helpers."""

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


_PASSWORD_HASH = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Return a salted Argon2id hash suitable for persistent storage."""

    return _PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether a password matches its stored hash."""

    try:
        return _PASSWORD_HASH.verify(password, password_hash)
    except UnknownHashError:
        return False


def hash_one_time_secret(secret: str) -> str:
    """Hash an activation or reset secret before persistent storage."""

    return _PASSWORD_HASH.hash(secret)


def verify_one_time_secret(secret: str, secret_hash: str) -> bool:
    """Return whether an activation or reset secret matches its stored hash."""

    return _PASSWORD_HASH.verify(secret, secret_hash)
