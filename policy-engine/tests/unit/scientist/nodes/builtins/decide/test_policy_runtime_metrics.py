from __future__ import annotations

import math

from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.nodes.builtins.decide.policy_runtime_metrics import (
    _build_evidence_driven_simulation_metrics,
    _build_policy_simulation_results_impl,
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
    )

    assert artifact.provenance.backend_kind == "synthetic"
    assert artifact.provenance.promotable_source is False
    assert artifact.provenance.degradation_mode == "research_only"
    assert artifact.simulation_results["promotable_source"] is False
