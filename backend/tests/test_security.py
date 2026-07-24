from app.core.security import (
    hash_one_time_secret,
    hash_password,
    verify_one_time_secret,
    verify_password,
)


def test_password_hash_is_not_plaintext_and_verifies():
    password = "phase-one-c-password"

    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2id$")
    assert verify_password(password, password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_same_password_produces_distinct_valid_hashes():
    password = "same-password"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash
    assert verify_password(password, first_hash) is True
    assert verify_password(password, second_hash) is True


def test_one_time_secret_is_hashed_and_verifiable():
    secret = "single-use-activation-value"

    secret_hash = hash_one_time_secret(secret)

    assert secret_hash != secret
    assert verify_one_time_secret(secret, secret_hash) is True
    assert verify_one_time_secret("wrong-secret", secret_hash) is False
