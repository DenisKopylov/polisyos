"""Focused behavioral tests for runtime step-up verification."""

from __future__ import annotations

import pytest

from tests.unit.runtime.http.test_runtime_step_up_authz import (
    _jwt_step_up_verifier,
    _signed_step_up_token,
    _step_up_context,
)


def test_valid_signed_step_up_assertion_verifies_exact_context() -> None:
    from polisyos.runtime.http.step_up import StepUpAssertionVerification

    now = 1_800_000_000
    context = _step_up_context()
    token = _signed_step_up_token(
        context,
        issued_at=now - 5,
        expires_at=now + 60,
        assertion_id="valid-signed-step-up-jti",
    )

    verification = _jwt_step_up_verifier(now=now).verify(token, context)

    assert type(verification) is StepUpAssertionVerification
    assert verification.context == context
    assert verification.assertion_id == "valid-signed-step-up-jti"
    assert verification.issuer == "https://step-up.example"
    assert verification.audience == "polisyos-runtime-step-up"
    assert verification.assurance == "fresh_mfa"


@pytest.mark.parametrize(
    ("case", "claim_overrides", "signing_key", "error_code"),
    [
        (
            "invalid_signature",
            {},
            "different-ds20-step-up-signing-key-at-least-32-bytes",
            "step_up_signature_invalid",
        ),
        (
            "wrong_issuer",
            {"iss": "https://attacker.invalid"},
            "ds20-test-step-up-key-with-at-least-32-bytes",
            "step_up_signature_invalid",
        ),
        (
            "wrong_audience",
            {"aud": "different-runtime"},
            "ds20-test-step-up-key-with-at-least-32-bytes",
            "step_up_signature_invalid",
        ),
        (
            "multi_audience_expected_first",
            {"aud": ["polisyos-runtime-step-up", "other-service"]},
            "ds20-test-step-up-key-with-at-least-32-bytes",
            "step_up_signature_invalid",
        ),
        (
            "multi_audience_expected_second",
            {"aud": ["other-service", "polisyos-runtime-step-up"]},
            "ds20-test-step-up-key-with-at-least-32-bytes",
            "step_up_signature_invalid",
        ),
        (
            "mfa_not_verified",
            {"mfa_verified": False},
            "ds20-test-step-up-key-with-at-least-32-bytes",
            "step_up_assurance_required",
        ),
        (
            "assurance_missing",
            {"assurance": ""},
            "ds20-test-step-up-key-with-at-least-32-bytes",
            "step_up_assurance_required",
        ),
        (
            "expired",
            {"iat": 1_799_999_900, "exp": 1_799_999_989},
            "ds20-test-step-up-key-with-at-least-32-bytes",
            "step_up_expired",
        ),
    ],
)
def test_signed_step_up_assertion_fails_closed_for_invalid_authenticity_or_assurance(
    case: str,
    claim_overrides: dict[str, object],
    signing_key: str,
    error_code: str,
) -> None:
    del case
    from polisyos.runtime.http.step_up import StepUpAssertionVerificationError

    now = 1_800_000_000
    context = _step_up_context()
    token = _signed_step_up_token(
        context,
        issued_at=now - 5,
        expires_at=now + 60,
        claim_overrides=claim_overrides,
        signing_key=signing_key,
    )

    with pytest.raises(StepUpAssertionVerificationError) as exc:
        _jwt_step_up_verifier(now=now).verify(token, context)

    assert exc.value.code == error_code


@pytest.mark.parametrize(
    ("claim_name", "wrong_value"),
    [
        ("sub", "different-subject"),
        ("tenant_id", "different-tenant"),
        ("method", "DELETE"),
        ("route", "/api/v1/different-route"),
        ("permission", "runs.launch"),
        ("resource_id", "urn:polisyos:different-resource"),
        ("resource_digest", "sha256:" + "9" * 64),
        ("resource_kind", "runtime.different-kind"),
        ("binding_authority", "request_composite"),
        ("body_sha256", "sha256:" + "8" * 64),
        ("step_up_class", "publication"),
    ],
)
def test_signed_step_up_assertion_denies_every_mismatched_request_binding(
    claim_name: str,
    wrong_value: str,
) -> None:
    from polisyos.runtime.http.step_up import StepUpAssertionVerificationError

    now = 1_800_000_000
    context = _step_up_context()
    token = _signed_step_up_token(
        context,
        issued_at=now - 5,
        expires_at=now + 60,
        claim_overrides={claim_name: wrong_value},
    )

    with pytest.raises(StepUpAssertionVerificationError) as exc:
        _jwt_step_up_verifier(now=now).verify(token, context)

    assert exc.value.code == "step_up_binding_mismatch"
