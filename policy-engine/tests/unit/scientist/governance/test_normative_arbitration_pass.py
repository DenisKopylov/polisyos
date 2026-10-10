from __future__ import annotations

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.governance.passes.base import IssueSeverity, PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.normative_arbitration import (
    ArbitrationOption,
    NormativeArbitrationResult,
    NormativeModelCompleteness,
    OptionOutcomeMatrix,
    PolicyOutcome,
    TradeoffCertificate,
    persist_normative_arbitration_result,
)
from polisyos.ir.governance.problem_frame import NormativeArbitrationPolicy
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


def test_normative_arbitration_pass_consumes_persisted_result(
    pass_context_factory, strict_profile
) -> None:
    policy = NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS
    result = NormativeArbitrationResult(
        model_completeness=NormativeModelCompleteness.COMPLETE,
        option_matrix=[
            OptionOutcomeMatrix(option=ArbitrationOption.BASELINE),
            OptionOutcomeMatrix(option=ArbitrationOption.PROPOSAL),
        ],
        policy_outcomes=[
            PolicyOutcome(
                policy=policy,
                selected_option=ArbitrationOption.PROPOSAL,
                rationale="The proposal satisfies the evaluated policy.",
            )
        ],
        selected_policy=policy,
        selected_option=ArbitrationOption.PROPOSAL,
        tradeoff_certificate=TradeoffCertificate(
            selected_policy=policy,
            selected_option=ArbitrationOption.PROPOSAL,
        ),
    )
    ctx = pass_context_factory(profile=strict_profile)
    result_ref = persist_normative_arbitration_result(
        ensure_ir_artifact_store(ctx.state["_store"]), result
    )
    ctx.state["artifacts_index"] = {"normative_arbitration_result_ref": result_ref}

    issues = NormativeArbitrationPass().validate(ctx)

    assert issues == []
