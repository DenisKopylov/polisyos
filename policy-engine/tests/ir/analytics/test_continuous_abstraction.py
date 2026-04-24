from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.abstraction import (
    AbstractionPreservationType,
    ContinuousApproximateAbstractionConfig,
    FiniteStateAbstractionMap,
    VariableStateAbstraction,
    abstraction_error_bound_spec,
    abstraction_recommendation_margin_required,
    persist_finite_state_abstraction_map,
    verify_continuous_approximate_abstraction,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
)


def _artifact_ref(seed: str, *, kind: str = "ir.causal_graph_model") -> dict[str, str]:
    return {
        "artifact_id": "sha256:" + seed * 64,
        "kind": kind,
        "media_type": "application/json",
    }


def _continuous_map() -> FiniteStateAbstractionMap:
    return FiniteStateAbstractionMap(
        variable_maps=(
            VariableStateAbstraction(
                micro_variable="T_m",
                macro_variable="T",
                state_map={"__continuous__": "__continuous__"},
            ),
            VariableStateAbstraction(
                micro_variable="Y_m",
                macro_variable="Y",
                state_map={"__continuous__": "__continuous__"},
            ),
        )
    )


def _linear_gaussian_scm(
    *,
    macro: bool,
    outcome_intercept: float,
    outcome_slope: float,
    outcome_noise_std: float,
) -> StructuralCausalModelSpec:
    treatment = "T" if macro else "T_m"
    outcome = "Y" if macro else "Y_m"
    return StructuralCausalModelSpec(
        graph=CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=[treatment, outcome],
            edges=[CausalEdge(src=treatment, dst=outcome)],
            discovery_method="test",
        ),
        fitted=True,
        fit_method="manual",
        mechanisms=[
            NodeMechanism(
                variable=treatment,
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.0, "std": 1.0},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable=outcome,
                parents=[treatment],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": outcome_intercept,
                    "coefficients": {treatment: outcome_slope},
                    "noise_std": outcome_noise_std,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
    )


def test_verify_continuous_linear_gaussian_policy_value_certificate(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "continuous-linear-gaussian")
    abstraction_map = _continuous_map()
    map_ref = persist_finite_state_abstraction_map(store, abstraction_map)

    certificate = verify_continuous_approximate_abstraction(
        _linear_gaussian_scm(
            macro=False,
            outcome_intercept=0.2,
            outcome_slope=1.2,
            outcome_noise_std=0.1,
        ),
        _linear_gaussian_scm(
            macro=True,
            outcome_intercept=0.1,
            outcome_slope=1.0,
            outcome_noise_std=0.2,
        ),
        abstraction_map,
        bound_config=ContinuousApproximateAbstractionConfig(
            family="continuous_linear_gaussian",
            preservation_type=AbstractionPreservationType.POLICY_VALUE_ONLY,
            intervention_ranges={"T": (-1.0, 1.0)},
            policy_value_weights={"Y": 1.0},
            state_weights={"T": 1.0, "Y": 1.0},
            proof_obligations_satisfied=("linear_gaussian_closed_form",),
        ),
        micro_graph_ref=_artifact_ref("a"),
        macro_graph_ref=_artifact_ref("b"),
        abstraction_map_ref=map_ref,
        preserved_queries=("policy_value:planner_welfare",),
    )

    assert certificate.preservation_type is AbstractionPreservationType.POLICY_VALUE_ONLY
    assert certificate.error_bound == pytest.approx(0.3)
    assert abstraction_recommendation_margin_required(certificate) == pytest.approx(0.6)
    assert "tightness_status=exact_on_linear_gaussian" in certificate.validation_notes
    assert abstraction_error_bound_spec(certificate) == {
        "scope": {
            "query_family": "policy_value",
            "interventions": "hard_or_soft_declared_scope",
            "action_domain": "compact_box",
        },
        "state_metric": "weighted_l1",
        "distribution_metric": "wasserstein_2_gaussian",
        "value_lipschitz_constant": 1.0,
        "global_state_bound": pytest.approx(0.3),
        "recommendation_margin_required": pytest.approx(0.6),
        "gain_matrix_spectral_radius": 0.0,
        "tightness_status": "exact_on_linear_gaussian",
        "bound_kind": "linear_policy_value_exact",
        "error_metric": "policy_value_upper_bound",
        "error_scope": "hard_or_soft_declared_scope",
    }


def test_verify_continuous_lipschitz_dag_propagates_local_defects(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "continuous-lipschitz")
    abstraction_map = _continuous_map()
    map_ref = persist_finite_state_abstraction_map(store, abstraction_map)

    certificate = verify_continuous_approximate_abstraction(
        _linear_gaussian_scm(
            macro=False,
            outcome_intercept=0.0,
            outcome_slope=1.0,
            outcome_noise_std=0.0,
        ),
        _linear_gaussian_scm(
            macro=True,
            outcome_intercept=0.0,
            outcome_slope=1.0,
            outcome_noise_std=0.0,
        ),
        abstraction_map,
        bound_config=ContinuousApproximateAbstractionConfig(
            family="continuous_lipschitz_dag",
            preservation_type=AbstractionPreservationType.APPROXIMATE,
            local_mechanism_defects={"T": 0.1, "Y": 0.2},
            gain_matrix={"Y": {"T": 0.5}},
            value_lipschitz_constant=1.5,
            state_weights={"T": 1.0, "Y": 2.0},
            proof_obligations_satisfied=(
                "local_defect_certified",
                "gain_matrix_contracting",
            ),
        ),
        micro_graph_ref=_artifact_ref("c"),
        macro_graph_ref=_artifact_ref("d"),
        abstraction_map_ref=map_ref,
        preserved_queries=("policy_value:planner_welfare", "policy_rank:top2"),
    )

    assert certificate.preservation_type is AbstractionPreservationType.APPROXIMATE
    assert certificate.error_bound == pytest.approx(0.9)
    assert abstraction_recommendation_margin_required(certificate) == pytest.approx(1.8)
    assert certificate.metadata["diagnostics"]["global_error_bound_by_variable"] == {
        "T": pytest.approx(0.1),
        "Y": pytest.approx(0.25),
    }
    assert abstraction_error_bound_spec(certificate) == {
        "scope": {
            "query_family": "policy_value",
            "interventions": "hard_or_soft_declared_scope",
            "action_domain": "compact_box",
        },
        "state_metric": "weighted_l1",
        "distribution_metric": "wasserstein_1",
        "value_lipschitz_constant": 1.5,
        "global_state_bound": pytest.approx(0.6),
        "recommendation_margin_required": pytest.approx(1.8),
        "gain_matrix_spectral_radius": 0.0,
        "tightness_status": "upper_bound_only",
        "bound_kind": "policy_value_upper_bound",
        "error_metric": "policy_value_upper_bound",
        "error_scope": "hard_or_soft_declared_scope",
    }


def test_verify_continuous_abstraction_returns_invalid_for_incomplete_lipschitz_certificate(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "continuous-lipschitz-invalid")
    abstraction_map = _continuous_map()
    map_ref = persist_finite_state_abstraction_map(store, abstraction_map)

    certificate = verify_continuous_approximate_abstraction(
        _linear_gaussian_scm(
            macro=False,
            outcome_intercept=0.0,
            outcome_slope=1.0,
            outcome_noise_std=0.0,
        ),
        _linear_gaussian_scm(
            macro=True,
            outcome_intercept=0.0,
            outcome_slope=1.0,
            outcome_noise_std=0.0,
        ),
        abstraction_map,
        bound_config=ContinuousApproximateAbstractionConfig(
            family="continuous_lipschitz_dag",
            local_mechanism_defects={"T": 0.1},
            gain_matrix={"Y": {"T": 0.5}},
            value_lipschitz_constant=1.0,
        ),
        micro_graph_ref=_artifact_ref("e"),
        macro_graph_ref=_artifact_ref("f"),
        abstraction_map_ref=map_ref,
        preserved_queries=("policy_value:planner_welfare", "policy_rank:top2"),
    )

    assert certificate.preservation_type is AbstractionPreservationType.INVALID
    assert any(
        "missing=['Y']" in note or "missing=['Y']" in note for note in certificate.validation_notes
    )
