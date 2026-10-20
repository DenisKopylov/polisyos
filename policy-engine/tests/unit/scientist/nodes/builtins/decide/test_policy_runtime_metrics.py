from __future__ import annotations

import math

from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    ObjectiveScoreStatus,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_metrics import (
    _build_evidence_driven_simulation_metrics,
    _build_policy_simulation_results_impl,
    _policy_runtime_execution_metadata,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    SyntheticPolicyEvaluationBackend,
)
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema


def _candidate() -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="problem_runtime_metric_mapping",
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(policy_id="policy_runtime_metric_mapping"),
            model_spec=ModelSpec(
                model_id="model_runtime_metric_mapping",
                data_snapshot_ref="sha256:" + "1" * 64,
            ),
        ),
        candidate_id="candidate_runtime_metric_mapping",
    )


def test_metric_projection_uses_known_signal_and_drops_unknown_nonfinite_projection() -> None:
    candidate = _candidate()
    mapped, sources, notes = _build_evidence_driven_simulation_metrics(
        candidate,
        fidelity="full",
        simulation_metrics={
            "ate": 0.25,
            "opaque_nonfinite_signal": math.nan,
            "untyped_note": "not a metric",
        },
        uncertainty=None,
        distributional_report=None,
        causal_effect_report=None,
        cross_graph_profile=None,
        governance_report=None,
    )

    assert mapped["policy_value"] == 0.25
    assert math.isnan(mapped["opaque_nonfinite_signal"])
    assert "untyped_note" not in mapped
    assert sources == ("metrics_artifact",)
    assert notes == ()

    projected = _build_policy_simulation_results_impl(
        PolicyEvaluationVector(candidate_id=candidate.candidate_id),
        fidelity="full",
        uncertainty=None,
        base_metrics=mapped,
    )
    assert projected["policy_value"] == 0.25
    assert "opaque_nonfinite_signal" not in projected
    assert projected["evaluation_backend_kind"] == "unknown"
    assert projected["promotable_source"] is None


def test_fiscal_aliases_are_retained_but_unavailable_without_source_unit() -> None:
    candidate = _candidate()
    mapped, _, _ = _build_evidence_driven_simulation_metrics(
        candidate,
        fidelity="full",
        simulation_metrics={"budget_deficit": 100.0, "deficit": 100.0},
        uncertainty=None,
        distributional_report=None,
        causal_effect_report=None,
        cross_graph_profile=None,
        governance_report=None,
    )

    assert mapped["budget_deficit"] == 100.0
    assert mapped["deficit"] == 100.0
    assert "gov_balance" not in mapped
    assert "budget_penalty" in mapped

    projected = _build_policy_simulation_results_impl(
        PolicyEvaluationVector(candidate_id=candidate.candidate_id),
        fidelity="full",
        uncertainty=None,
        base_metrics=mapped,
    )
    assert projected["budget_deficit"] == 100.0
    assert projected["deficit"] == 100.0
    assert "gov_balance" not in projected
    assert projected["metric_units"] == {}
    assert projected["budget_deficit_objective_usable"] is False
    assert projected["budget_deficit_objective_value"] is None

    objective = BudgetDeficitObjective().evaluate(projected)
    assert objective.score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert objective.score_assessment is not None
    assert objective.score_assessment.limitation == "objective_rule_unit_not_established"
    assert objective.is_satisfied is False


def test_runtime_projection_binds_configured_count_without_claiming_executed_draws() -> None:
    execution = _policy_runtime_execution_metadata(
        evaluation_attempt_id="attempt:test",
        effective_estimation_config={"estimator": "matching", "n_bootstrap": 17},
    )
    projected = _build_policy_simulation_results_impl(
        PolicyEvaluationVector(candidate_id="candidate_runtime_projection"),
        fidelity="medium",
        uncertainty=None,
        runtime_execution=execution,
    )

    assert projected["bootstrap"]["requested_draw_count"] == 17
    assert projected["bootstrap"]["requested_draw_source"] == "effective_estimation_config"
    assert (
        projected["bootstrap"]["effective_estimation_config_sha256"]
        == execution["effective_estimation_config_sha256"]
    )
    assert projected["bootstrap"]["draw_execution_status"] == "not_instrumented"
    assert projected["bootstrap"]["attempted_draw_count"] is None
    assert projected["bootstrap"]["successful_draw_count"] is None
    assert projected["bootstrap"]["failed_draw_count"] is None
    assert projected["bootstrap"]["unattempted_draw_count"] is None


def test_runtime_projection_does_not_infer_draw_requests_from_fidelity() -> None:
    projected = _build_policy_simulation_results_impl(
        PolicyEvaluationVector(candidate_id="candidate_no_config"),
        fidelity="medium",
        uncertainty=None,
    )

    assert projected["bootstrap"]["requested_draw_count"] is None
    assert projected["bootstrap"]["requested_draw_source"] == "unavailable"
    assert projected["bootstrap"]["draw_execution_status"] == "not_instrumented"


def test_synthetic_backend_does_not_gain_promotion_authority_from_external_metrics() -> None:
    candidate = _candidate()
    artifact = SyntheticPolicyEvaluationBackend().evaluate(
        candidate,
        fidelity="full",
        simulation_metrics={
            "policy_value": 1.0,
            "opaque_nonfinite_signal": math.inf,
        },
        uncertainty=None,
        distributional_report=None,
        causal_effect_report=None,
        cross_graph_profile=None,
        governance_report=None,
        evaluation_attempt_id="attempt:synthetic-backend",
        effective_estimation_config={"estimator": "matching", "n_bootstrap": 23},
    )

    assert artifact.provenance.backend_kind == "synthetic"
    assert artifact.provenance.promotable_source is False
    assert artifact.provenance.degradation_mode == "research_only"
    assert artifact.simulation_results["promotable_source"] is False
    assert artifact.evaluation_vector.metadata["policy_runtime_invocation"] == {
        "evaluation_attempt_id": "attempt:synthetic-backend",
        "requested_draw_count": 23,
        "requested_draw_source": "effective_estimation_config",
        "effective_estimation_config_sha256": artifact.simulation_results["bootstrap"][
            "effective_estimation_config_sha256"
        ],
    }
    assert artifact.evaluation_vector.metadata["policy_runtime_fiscal_measurement"] == {
        "usable": False,
        "normalized_value": None,
        "source_values": {},
    }
