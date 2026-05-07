from __future__ import annotations

import hashlib

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    AbstractionPreservationType,
)
from polisyos.ir.analytics.strategic import (
    FiniteStrategicPayoffTable,
    StrategicEquilibriumConcept,
    StrategicSCM,
    encode_action_profile,
)
from polisyos.ir.refs import FiniteStateAbstractionMapRef, StrategicPayoffTableRef
from polisyos.scientist.methods.autotune.models import BenchmarkSplit
from polisyos.scientist.methods.backtesting.abstraction_suite import run_abstraction_challenge_suite
from polisyos.scientist.methods.backtesting.strategic_suite import run_strategic_challenge_suites
from polisyos.scientist.orchestration.kernel.budgets import ComputeBudget


def _ref(seed: str, *, kind: str = "scientist.test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(
            f"sha256:{hashlib.sha256(seed.encode()).hexdigest()}"
        ),
        kind=kind,
        media_type="application/json",
    )


def _strategic_contract_and_tables() -> tuple[StrategicSCM, dict[str, FiniteStrategicPayoffTable]]:
    agents = ("leader", "follower")
    action_spaces = {
        "leader": ("L1", "L2"),
        "follower": ("F1", "F2"),
    }
    leader_payoffs = {
        encode_action_profile({"leader": "L1", "follower": "F1"}, agent_order=agents): 3.0,
        encode_action_profile({"leader": "L1", "follower": "F2"}, agent_order=agents): 1.0,
        encode_action_profile({"leader": "L2", "follower": "F1"}, agent_order=agents): 2.0,
        encode_action_profile({"leader": "L2", "follower": "F2"}, agent_order=agents): 0.0,
    }
    follower_payoffs = {
        encode_action_profile({"leader": "L1", "follower": "F1"}, agent_order=agents): 2.0,
        encode_action_profile({"leader": "L1", "follower": "F2"}, agent_order=agents): 0.0,
        encode_action_profile({"leader": "L2", "follower": "F1"}, agent_order=agents): 1.0,
        encode_action_profile({"leader": "L2", "follower": "F2"}, agent_order=agents): 3.0,
    }
    tables = {
        "leader": FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=agents,
            action_spaces=action_spaces,
            payoffs=leader_payoffs,
        ),
        "follower": FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=agents,
            action_spaces=action_spaces,
            payoffs=follower_payoffs,
        ),
    }
    contract = StrategicSCM(
        base_graph_ref=_ref("a", kind="ir.causal_graph_model").model_dump(mode="json"),
        strategic_agents=agents,
        utility_refs={
            "leader": StrategicPayoffTableRef.model_validate(
                _ref("b", kind="ir.strategic_payoff_table").model_dump(mode="json")
            ),
            "follower": StrategicPayoffTableRef.model_validate(
                _ref("c", kind="ir.strategic_payoff_table").model_dump(mode="json")
            ),
        },
        policy_rule_ref=_ref("d", kind="scientist.policy_candidate_schema").model_dump(mode="json"),
        equilibrium_concept=StrategicEquilibriumConcept.STACKELBERG,
        compute_budget=ComputeBudget(max_sim_runs=16.0),
    )
    return contract, tables


def _exact_certificate() -> tuple[AbstractionCertificate, ArtifactRef]:
    abstraction_map_ref = FiniteStateAbstractionMapRef.model_validate(
        _ref("m", kind="ir.finite_state_abstraction_map").model_dump(mode="json")
    )
    certificate = AbstractionCertificate(
        micro_graph_ref=_ref("x", kind="ir.causal_graph_model").model_dump(mode="json"),
        macro_graph_ref=_ref("y", kind="ir.causal_graph_model").model_dump(mode="json"),
        abstraction_map_ref=abstraction_map_ref,
        preservation_type=AbstractionPreservationType.EXACT,
        preserved_queries=("policy_value",),
    )
    return certificate, abstraction_map_ref


def _approximate_certificate() -> tuple[AbstractionCertificate, ArtifactRef]:
    abstraction_map_ref = FiniteStateAbstractionMapRef.model_validate(
        _ref("ma", kind="ir.finite_state_abstraction_map").model_dump(mode="json")
    )
    certificate = AbstractionCertificate(
        micro_graph_ref=_ref("xa", kind="ir.causal_graph_model").model_dump(mode="json"),
        macro_graph_ref=_ref("ya", kind="ir.causal_graph_model").model_dump(mode="json"),
        abstraction_map_ref=abstraction_map_ref,
        preservation_type=AbstractionPreservationType.APPROXIMATE,
        preserved_queries=(
            "mean_potential_outcome:type_mean",
            "ate:type_mean",
            "policy_value:weighted_type_mean",
        ),
        error_bound=0.05,
        metadata={
            "abstraction_family": "type_mean_affine",
            "allowed_intervention_family": "type_symmetric",
            "intervention_family_verified": True,
            "proof_obligations_satisfied": [
                "within_type_exchangeability",
                "mean_closure",
                "admissible_omega_map",
            ],
            "estimand_error_bounds": {
                "mean_potential_outcome:type_mean": 0.03,
                "ate:type_mean": 0.05,
                "policy_value:weighted_type_mean": 0.02,
            },
            "diagnostics": {"within_type_dispersion": {"max": 0.1}},
            "non_preserved_queries": ["unit_level_potential_outcome"],
        },
    )
    return certificate, abstraction_map_ref


def test_strategic_suites_emit_rotating_challenge_evaluations_for_raw_inputs() -> None:
    contract, tables = _strategic_contract_and_tables()
    results, warnings = run_strategic_challenge_suites(
        candidate_ref=_ref("p"),
        loop_id="loop-a",
        run_id="run-a",
        params={
            "strategic_scm": contract.model_dump(mode="json"),
            "strategic_payoff_tables": {
                agent: table.model_dump(mode="json") for agent, table in tables.items()
            },
            "baseline_policy_value": 0.5,
        },
        strategic_summary=None,
        abstraction_certificate=None,
    )

    assert warnings == ()
    assert {result.suite_id for result in results} == {
        "strategic_gaming_v1",
        "multiplicity_disclosure_v1",
    }
    for result in results:
        assert result.runtime_split_type is BenchmarkSplit.ROTATING_CHALLENGE
        assert (
            result.benchmark_evaluation.resolved_runtime_split_type()
            is BenchmarkSplit.ROTATING_CHALLENGE
        )
        assert result.benchmark_evaluation.promotable is True
        assert result.stress_test_report is None


def test_multiplicity_summary_audit_fails_without_explicit_disclosure() -> None:
    results, warnings = run_strategic_challenge_suites(
        candidate_ref=_ref("q"),
        loop_id="loop-a",
        run_id="run-a",
        params={},
        strategic_summary={
            "fallback_mode": "exact_equilibrium",
            "equilibrium_selection_dependence": "follower_best_response_tie_breaking",
            "closure_summary": {"mode": "exact_equilibrium", "equilibrium_count": 2},
        },
        abstraction_certificate=None,
    )

    assert warnings == ("phase_d4_strategic_suite_audit_only",)
    multiplicity = next(
        result for result in results if result.suite_id == "multiplicity_disclosure_v1"
    )
    assert (
        multiplicity.benchmark_evaluation.selection_metrics["undisclosed_multiplicity_rate"] == 1.0
    )
    assert multiplicity.benchmark_evaluation.promotable is False
    assert multiplicity.stress_test_report is not None


def test_multiplicity_summary_audit_passes_with_explicit_disclosure() -> None:
    results, _ = run_strategic_challenge_suites(
        candidate_ref=_ref("r"),
        loop_id="loop-a",
        run_id="run-a",
        params={},
        strategic_summary={
            "fallback_mode": "exact_equilibrium",
            "equilibrium_selection_dependence": "follower_best_response_tie_breaking",
            "multiplicity_note": "multiple_stackelberg_equilibria",
            "equilibrium_profiles": [
                {"leader": "L1", "follower": "F1"},
                {"leader": "L1", "follower": "F2"},
            ],
            "closure_summary": {"mode": "exact_equilibrium", "equilibrium_count": 2},
        },
        abstraction_certificate=None,
    )

    multiplicity = next(
        result for result in results if result.suite_id == "multiplicity_disclosure_v1"
    )
    assert (
        multiplicity.benchmark_evaluation.selection_metrics["undisclosed_multiplicity_rate"] == 0.0
    )
    assert multiplicity.benchmark_evaluation.promotable is True


def test_abstraction_suite_passes_for_exact_certificate_backed_macro_use() -> None:
    certificate, abstraction_map_ref = _exact_certificate()
    result, warnings = run_abstraction_challenge_suite(
        candidate_ref=_ref("s"),
        loop_id="loop-a",
        run_id="run-a",
        params={},
        strategic_summary={"fallback_mode": "macro_abstracted"},
        abstraction_certificate=certificate,
        abstraction_map_ref=abstraction_map_ref,
        abm_alignment_report=None,
    )

    assert warnings == ()
    assert result is not None
    assert result.benchmark_evaluation.selection_metrics["abstraction_leakage_rate"] == 0.0
    assert result.benchmark_evaluation.promotable is True


def test_abstraction_suite_passes_for_bounded_approximate_certificate_macro_use() -> None:
    certificate, abstraction_map_ref = _approximate_certificate()
    result, warnings = run_abstraction_challenge_suite(
        candidate_ref=_ref("sa"),
        loop_id="loop-a",
        run_id="run-a",
        params={},
        strategic_summary={"fallback_mode": "macro_abstracted"},
        abstraction_certificate=certificate,
        abstraction_map_ref=abstraction_map_ref,
        abm_alignment_report=None,
    )

    assert warnings == ()
    assert result is not None
    assert result.benchmark_evaluation.selection_metrics["abstraction_leakage_rate"] == 0.0
    assert result.benchmark_evaluation.promotable is True


def test_abstraction_suite_requires_heuristic_disclaimer_without_certificate() -> None:
    result, warnings = run_abstraction_challenge_suite(
        candidate_ref=_ref("t"),
        loop_id="loop-a",
        run_id="run-a",
        params={
            "abm_alignment_warnings": ["heuristic_aggregation_without_abstraction_certificate"]
        },
        strategic_summary=None,
        abstraction_certificate=None,
        abstraction_map_ref=None,
        abm_alignment_report=None,
    )

    assert warnings == ("phase_d4_abstraction_suite_audit_only",)
    assert result is not None
    assert result.benchmark_evaluation.selection_metrics["abstraction_leakage_rate"] == 0.0
    assert result.benchmark_evaluation.promotable is True


def test_abstraction_suite_fails_macro_shortcut_without_supported_certificate() -> None:
    result, _ = run_abstraction_challenge_suite(
        candidate_ref=_ref("u"),
        loop_id="loop-a",
        run_id="run-a",
        params={},
        strategic_summary={"fallback_mode": "macro_abstracted"},
        abstraction_certificate=None,
        abstraction_map_ref=None,
        abm_alignment_report=None,
    )

    assert result is not None
    assert result.benchmark_evaluation.selection_metrics["abstraction_leakage_rate"] == 1.0
    assert result.stress_test_report is not None
