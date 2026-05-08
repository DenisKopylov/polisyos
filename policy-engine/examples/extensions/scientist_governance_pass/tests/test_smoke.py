from __future__ import annotations

from polisyos_scientist_governance_pass_example import audit_marker_pass_factory

from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ValidationProfile


def test_audit_marker_pass_factory_returns_validator_pass() -> None:
    validator = audit_marker_pass_factory()

    if not isinstance(validator, ValidatorPass):
        raise AssertionError(type(validator))
    if validator.pass_id != "example_audit_marker":  # noqa: S105 - pass identifier, not a secret.
        raise AssertionError(validator.pass_id)


def test_audit_marker_pass_accepts_approved_context() -> None:
    validator = audit_marker_pass_factory()
    ctx = PassContext(
        ir=None,
        state={"example_governance_approved": True},
        registry_bundle=None,
        profile=ValidationProfile.fast(),
        run_id="example-run",
    )

    issues = validator.validate(ctx)

    if issues != []:
        raise AssertionError(issues)
