from __future__ import annotations

from unittest.mock import patch

from polisyos.pdc import OperationClass
from polisyos.runtime.quality.workspace.spine_repair_gates import (
    BlockedInputProducer,
    GovernanceTailVerifier,
    LexBoundsApplicabilityGate,
)
from polisyos.scientist import api as scientist_api
from polisyos.scientist.policy_design import search as policy_search


def test_lex_bounds_gate_does_not_coerce_none_to_zero() -> None:
    result = LexBoundsApplicabilityGate().evaluate(
        workspace_id="ws-phase2",
        invocation_id="invoke-refine",
        lower=None,
        upper=10.0,
    )

    assert result.applicability.status == "repair_required"
    assert result.blocker is not None
    assert result.blocker.operation_class == OperationClass.REFINE
    assert result.blocker.missing_input == "lower_bound"
    assert result.frontier_payload["bounds"] == {"lower": None, "upper": 10.0}


def test_lex_bounds_gate_accepts_valid_bounded_frontier() -> None:
    result = LexBoundsApplicabilityGate().evaluate(
        workspace_id="ws-phase2",
        invocation_id="invoke-refine",
        lower=-1.0,
        upper=2.5,
    )

    assert result.applicability.status == "applicable"
    assert result.blocker is None
    assert result.frontier_payload["bounded_frontier"] is True


def test_lex_bounds_gate_delegates_to_policy_search_repair() -> None:
    expected = policy_search.derive_phase2_parameter_bounds(
        workspace_id="ws-phase2",
        invocation_id="invoke-refine",
        default=1.0,
        lower=None,
        upper=10.0,
    )
    with patch.object(policy_search, "derive_phase2_parameter_bounds") as derive:
        derive.return_value = expected

        result = LexBoundsApplicabilityGate().evaluate(
            workspace_id="ws-phase2",
            invocation_id="invoke-refine",
            lower=None,
            upper=10.0,
        )

    derive.assert_called_once()
    assert result.applicability.status == "repair_required"


def test_policy_search_phase2_bounds_derivation_blocks_missing_bounds() -> None:
    assert hasattr(policy_search, "derive_phase2_parameter_bounds")
    result = policy_search.derive_phase2_parameter_bounds(
        workspace_id="ws-phase2",
        invocation_id="invoke-refine",
        default=10.0,
        lower=None,
        upper=None,
    )

    assert result.applicability.status == "repair_required"
    assert result.blocker is not None
    assert result.frontier_payload["bounds"] == {"lower": None, "upper": None}


def test_blocked_input_producer_emits_required_causal_port_blockers() -> None:
    blockers = BlockedInputProducer().produce(
        workspace_id="ws-phase2",
        invocation_id="invoke-causal",
        state_facts={},
        required_inputs=["causal_variables", "data_causal_graph", "observational_data_ref"],
    )

    assert {blocker.missing_input for blocker in blockers} == {
        "causal_variables",
        "data_causal_graph",
        "observational_data_ref",
    }
    assert all(blocker.producer_missing_label == "producer_missing" for blocker in blockers)


def test_governance_tail_verifier_blocks_warning_only_normative_authority() -> None:
    verdict = GovernanceTailVerifier().verify(
        workspace_id="ws-phase2",
        invocation_id="invoke-governance",
        normative_result={"warnings": ["legacy_normative_synthesizer_used"]},
        judge_verdict={"composite_decision": "promote"},
    )

    assert verdict.applicability.status == "repair_required"
    assert verdict.blocker is not None
    assert verdict.blocker.blocked_port == "governance.authority"


def test_governance_tail_verifier_delegates_to_governance_node_owner() -> None:
    real_verify = scientist_api.verify_phase2_governance_tail
    with patch.object(scientist_api, "verify_phase2_governance_tail") as verify:
        verify.side_effect = real_verify
        verdict = GovernanceTailVerifier().verify(
            workspace_id="ws-phase2",
            invocation_id="invoke-governance",
            normative_result={"warnings": [], "model_completeness": "declared_complete"},
            judge_verdict={
                "composite_decision": "promote",
                "per_judge": {
                    "structural": {},
                    "statistical": {},
                    "robustness": {},
                    "governance": {},
                    "reproducibility": {},
                    "compute": {},
                },
            },
        )

    verify.assert_called_once()
    assert verdict.applicability.status == "applicable"


def test_governance_tail_verifier_blocks_partial_judge_stack_verdict() -> None:
    verdict = GovernanceTailVerifier().verify(
        workspace_id="ws-phase2",
        invocation_id="invoke-governance",
        normative_result={"warnings": [], "model_completeness": "declared_complete"},
        judge_verdict={"composite_decision": "promote", "per_judge": {"structural": {}}},
    )

    assert verdict.applicability.status == "repair_required"
    assert verdict.blocker is not None


def test_governance_tail_verifier_accepts_valid_six_judge_stack_verdict() -> None:
    verdict = GovernanceTailVerifier().verify(
        workspace_id="ws-phase2",
        invocation_id="invoke-governance",
        normative_result={"warnings": [], "model_completeness": "declared_complete"},
        judge_verdict={
            "composite_decision": "promote",
            "per_judge": {
                "structural": {},
                "statistical": {},
                "robustness": {},
                "governance": {},
                "reproducibility": {},
                "compute": {},
            },
        },
    )

    assert verdict.applicability.status == "applicable"
    assert verdict.blocker is None
