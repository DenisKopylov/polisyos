"""Characterize the public policy-runtime support facade."""

from __future__ import annotations

import inspect

from polisyos.scientist.nodes.builtins.decide import policy_runtime_support
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector


def test_support_facade_keeps_public_runtime_types_and_producer_entry_points() -> None:
    """Runtime contracts and the production/promotion owners stay canonical."""
    module_name = "polisyos.scientist.nodes.builtins.decide.policy_runtime_support"

    for runtime_type in (
        policy_runtime_support.PolicyRuntimeEvaluationSafetyError,
        policy_runtime_support.PolicyRuntimeProvenance,
        policy_runtime_support.PolicyRuntimeEvaluationArtifact,
        policy_runtime_support.LatentDiscoveryBundleResolution,
        policy_runtime_support.PolicyEvaluationBackend,
        policy_runtime_support.ProductionPolicyEvaluationBackend,
        policy_runtime_support.SyntheticPolicyEvaluationBackend,
    ):
        assert runtime_type.__module__ == module_name

    assert policy_runtime_support.run_promotion_with_evidence.__module__ == module_name
    assert tuple(
        inspect.signature(policy_runtime_support.build_policy_runtime_evaluation).parameters
    ) == (
        "candidate",
        "backend",
        "fidelity",
        "simulation_metrics",
        "uncertainty",
        "distributional_report",
        "causal_effect_report",
        "cross_graph_profile",
        "governance_report",
        "ambiguity_certificate",
    )
    assert tuple(
        inspect.signature(policy_runtime_support.run_promotion_with_evidence).parameters
    ) == (
        "ctx",
        "state",
        "candidate",
        "candidate_ref",
        "evaluation_vector",
        "evidence_bundle",
        "promotion_context",
        "evaluation_provenance",
    )


def test_facade_projection_preserves_uninstrumented_draw_status() -> None:
    """Metric wrappers keep the current result values and honest draw status."""
    evaluation = PolicyEvaluationVector(candidate_id="candidate_facade")

    result = policy_runtime_support.build_policy_simulation_results(
        evaluation,
        fidelity="medium",
        uncertainty=None,
        base_metrics={
            "policy_value": 0.4,
            "employment": 0.2,
            "welfare": 0.3,
            "budget_penalty": 0.25,
        },
    )

    assert result["policy_value"] == 0.4
    assert result["employment"] == 0.2
    assert result["welfare"] == 0.3
    assert result["gov_balance"] == -0.25
    assert result["bootstrap"] == {
        "ci_width": 0.1,
        "requested_draw_count": 64,
        "requested_draw_source": "fidelity_default",
        "draw_execution_status": "not_instrumented",
        "attempted_draw_count": None,
        "successful_draw_count": None,
        "failed_draw_count": None,
        "unattempted_draw_count": None,
        "fidelity": "medium",
    }
