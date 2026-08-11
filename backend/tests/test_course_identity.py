"""Focused contracts for derived Course ID and student-facing schemas."""

from app.schemas.activation import ActivationVerificationResponse, ActivationVerifyRequest
from app.schemas.auth import StudentLoginRequest
from app.services.course_identity import course_identifier, normalize_course_component


def test_course_identifier_is_derived_from_canonical_components():
    assert normalize_course_component(" ieor150 ") == "IEOR150"
    assert course_identifier(" ieor150 ", " 2026fall ") == "IEOR150-2026FALL"


def test_login_and_activation_normalize_the_same_course_id():
    login = StudentLoginRequest(
        course_id=" ieor150-2026fall ",
        berkeley_username=" ABC123 ",
        password="test-only-password",
    )
    activation = ActivationVerifyRequest(
        course_id=" ieor150-2026fall ",
        berkeley_username=" ABC123 ",
        activation_code="ABCD-EFGH-JKLM",
    )
    assert login.course_id == activation.course_id == "IEOR150-2026FALL"
    assert login.berkeley_username == activation.berkeley_username == "abc123"


def test_activation_verification_has_no_existing_password_mode():
    response = ActivationVerificationResponse(verified=True, expires_in_seconds=600)
    assert response.model_dump() == {"verified": True, "expires_in_seconds": 600}
