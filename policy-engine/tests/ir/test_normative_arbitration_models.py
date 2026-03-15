from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.normative_arbitration import (
    ArbitrationOption,
    NormativeArbitrationResult,
    NormativeModelCompleteness,
    NormativeProvenance,
    OptionOutcomeMatrix,
    PolicyOutcome,
    ResidualDissent,
    StakeholderUtilitySummary,
    TradeoffCertificate,
    load_normative_arbitration_result,
    persist_normative_arbitration_result,
)
from polisyos.ir.governance.problem_frame import NormativeArbitrationPolicy


def test_normative_arbitration_result_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    result = NormativeArbitrationResult(
        model_completeness=NormativeModelCompleteness.PARTIAL,
        option_matrix=[
            OptionOutcomeMatrix(option=ArbitrationOption.BASELINE, binding_values={"a": 0.0}),
            OptionOutcomeMatrix(option=ArbitrationOption.PROPOSAL, binding_values={"a": 1.0}),
        ],
        per_stakeholder_utility=[
            StakeholderUtilitySummary(
                stakeholder_id="workers",
                baseline_utility=0.0,
                proposal_utility=1.0,
                delta_utility=1.0,
                welfare_weight=2.0,
            )
        ],
        rights_audit=[],
        hard_constraint_audit=[],
        policy_outcomes=[
            PolicyOutcome(
                policy=NormativeArbitrationPolicy.WEIGHTED_WELFARE,
                selected_option=ArbitrationOption.PROPOSAL,
                rationale="aggregate delta positive",
                metrics={"weighted_delta": 2.0},
            )
        ],
        selected_policy=NormativeArbitrationPolicy.WEIGHTED_WELFARE,
        selected_option=ArbitrationOption.PROPOSAL,
        winners=["workers"],
        losers=[],
        residual_dissent=[
            ResidualDissent(
                policy=NormativeArbitrationPolicy.PARETO_FILTER,
                preferred_option=ArbitrationOption.INDETERMINATE,
                rationale="proposal is neutral",
            )
        ],
        warnings=["legacy_normative_synthesizer_used"],
        tradeoff_certificate=TradeoffCertificate(
            selected_policy=NormativeArbitrationPolicy.WEIGHTED_WELFARE,
            selected_option=ArbitrationOption.PROPOSAL,
            winners=["workers"],
            residual_dissent=[
                ResidualDissent(
                    policy=NormativeArbitrationPolicy.PARETO_FILTER,
                    preferred_option=ArbitrationOption.INDETERMINATE,
                    rationale="proposal is neutral",
                )
            ],
            notes=["partial_model"],
        ),
        provenance=NormativeProvenance(trinity_bundle_ref="sha256:" + "1" * 64),
    )

    ref = persist_normative_arbitration_result(store, result)
    loaded = load_normative_arbitration_result(store, ref)

    assert loaded.selected_policy == NormativeArbitrationPolicy.WEIGHTED_WELFARE
    assert loaded.selected_option == ArbitrationOption.PROPOSAL
    assert loaded.tradeoff_certificate.winners == ["workers"]
