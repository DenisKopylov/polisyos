from __future__ import annotations

from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.scientist.governance.passes.base import IssueSeverity
from polisyos.scientist.governance.passes.normative_arbitration_pass import (
    NormativeArbitrationPass,
)


def test_normative_arbitration_invalid_payload_emits_warning() -> None:
    ctx = PassContext(
        ir=None,
        state={
            "normative_arbitration_result": {"invalid": True},
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_normative_invalid",
    )

    issues = NormativeArbitrationPass().validate(ctx)

    assert len(issues) == 2
    assert issues[0].code == "NORMATIVE_RESULT_INVALID"
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[1].code == "NORMATIVE_RESULT_MISSING"
