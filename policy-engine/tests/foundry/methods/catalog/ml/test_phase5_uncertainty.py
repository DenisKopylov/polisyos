from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.ml import (
    PredictionResult,
    WeightedConformalQuantile,
    ensure_ml_methods_registered,
    evaluate_conformal_acceptance_gate,
    update_conditional_coverage_diagnostic_with_outcomes,
)
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _prediction_result() -> PredictionResult:
    rng = np.random.default_rng(501)
    n_obs = 80
    x0 = rng.normal(size=n_obs)
    predictions = 1.0 + 1.5 * x0
    group = np.where(np.arange(n_obs) < n_obs // 2, "urban", "rural")
    noise_scale = np.where(group == "urban", 0.12, 0.35)
    target = predictions + rng.normal(scale=noise_scale)
    return PredictionResult(
        method_name="ft_transformer",
        predictions=predictions,
        target=target,
        metadata={"group_values": group},
    )


def _classification_payload() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    rng = np.random.default_rng(541)
    n_obs = 96
    n_classes = 4
    target = np.arange(n_obs, dtype=int) % n_classes
    group = np.where(np.arange(n_obs) < n_obs // 2, "north", "south")
    logits = rng.normal(scale=0.35, size=(n_obs, n_classes))
    logits[np.arange(n_obs), target] += 2.0
    logits[:, 0] += 0.15
    exp_values = np.exp(logits - np.max(logits, axis=1, keepdims=True))
    probabilities = exp_values / np.sum(exp_values, axis=1, keepdims=True)
    class_clusters = ["common", "common", "tail", "tail"]
    return probabilities, target, group, class_clusters


def _ring_graph(n_nodes: int) -> np.ndarray:
    adjacency = np.zeros((n_nodes, n_nodes), dtype=float)
    for idx in range(n_nodes):
        adjacency[idx, (idx - 1) % n_nodes] = 1.0
        adjacency[idx, (idx + 1) % n_nodes] = 1.0
    return adjacency


def test_mondrian_cqr_conformalizer_emits_group_diagnostic() -> None:
    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    prediction_result = _prediction_result()
    target = np.asarray(prediction_result.target, dtype=float)
    predictions = np.asarray(prediction_result.predictions, dtype=float)
    group = np.asarray(prediction_result.metadata["group_values"], dtype=str)
    width = np.where(group == "urban", 0.10, 0.22)

    method_cls = registry.get("ml.uncertainty.mondrian_cqr@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={
            "prediction_result": prediction_result,
            "lower_quantile_predictions": predictions - width,
            "upper_quantile_predictions": predictions + width,
        },
        params={
            "alpha": 0.1,
            "min_calibration_per_group": 20,
        },
        seed=503,
    ).output["result"]

    diagnostic = result.conditional_coverage_diagnostic
    assert diagnostic is not None
    assert diagnostic.method_spec.family == "mondrian_cqr"
    assert "group_conditional" in diagnostic.method_spec.guarantee_scope
    assert {group.group_value for group in diagnostic.groups} == {"rural", "urban"}
    assert all(group.guarantee_supported for group in diagnostic.groups)
    assert result.coverage == pytest.approx(float(np.mean((target >= result.lower) & (target <= result.upper))))


def test_mondrian_cqr_marks_low_support_without_claiming_group_coverage() -> None:
    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    prediction_result = _prediction_result()
    predictions = np.asarray(prediction_result.predictions, dtype=float)

    method_cls = registry.get("ml.uncertainty.mondrian_cqr@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={
            "prediction_result": prediction_result,
            "lower_quantile_predictions": predictions - 0.2,
            "upper_quantile_predictions": predictions + 0.2,
        },
        params={
            "alpha": 0.1,
            "min_calibration_per_group": 60,
            "fail_on_unsupported_group": False,
        },
        seed=509,
    ).output["result"]

    diagnostic = result.conditional_coverage_diagnostic
    assert diagnostic is not None
    assert diagnostic.status == "unsupported"
    assert diagnostic.recommended_action == "pool_or_cluster_groups"
    assert {group.support_status for group in diagnostic.groups} == {"low_n"}


def test_normalized_residual_mondrian_uses_scale_and_delayed_outcomes() -> None:
    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    prediction_result = _prediction_result()
    target = np.asarray(prediction_result.target, dtype=float)
    predictions = np.asarray(prediction_result.predictions, dtype=float)
    residual_scale = np.where(np.asarray(prediction_result.metadata["group_values"]) == "urban", 0.12, 0.35)

    method_cls = registry.get("ml.uncertainty.normalized_residual_mondrian@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={"prediction_result": prediction_result, "residual_scale": residual_scale},
        params={
            "alpha": 0.1,
            "min_calibration_per_group": 20,
        },
        seed=521,
    ).output["result"]

    assert result.method_name == "normalized_residual_mondrian"
    assert result.metadata["scale_source"] == "provided"
    assert result.conditional_coverage_diagnostic is not None
    updated = update_conditional_coverage_diagnostic_with_outcomes(
        result,
        target,
        group_values=prediction_result.metadata["group_values"],
        features=np.column_stack([predictions, residual_scale]),
        feature_names=["prediction", "residual_scale"],
        min_evaluation_per_group=20,
    )
    assert updated.coverage is not None
    assert updated.conditional_coverage_diagnostic is not None
    assert updated.conditional_coverage_diagnostic.ert is not None
    assert updated.conditional_coverage_diagnostic.ert.evaluated is True


def test_weighted_conformal_quantile_enforces_effective_sample_size() -> None:
    quantile = WeightedConformalQuantile(alpha=0.1, min_effective_sample_size=3.0)

    with pytest.raises(ValueError, match="effective sample size"):
        quantile.quantile([0.1, 0.2, 0.3, 0.4], [1.0, 0.0, 0.0, 0.0])

    q_hat, ess = quantile.quantile([0.1, 0.2, 0.3, 0.4], [1.0, 1.0, 1.0, 1.0])
    assert q_hat >= 0.3
    assert ess == pytest.approx(4.0)


def test_mondrian_aps_raps_supports_class_cluster_diagnostics() -> None:
    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    probabilities, target, group, class_clusters = _classification_payload()

    method_cls = registry.get("ml.uncertainty.mondrian_aps_raps@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={
            "method_name": "ft_transformer_classifier",
            "class_probabilities": probabilities,
            "target": target,
            "group_values": group,
            "class_clusters": class_clusters,
        },
        params={
            "alpha": 0.1,
            "score_type": "raps",
            "class_conditioning": "class_cluster",
            "min_calibration_per_group": 10,
            "rare_class_threshold": 30,
        },
        seed=547,
    ).output["result"]

    diagnostic = result.conditional_coverage_diagnostic
    assert result.method_name == "mondrian_aps_raps"
    assert diagnostic is not None
    assert diagnostic.method_spec.family == "mondrian_raps"
    assert "class_conditional" in diagnostic.method_spec.guarantee_scope
    assert result.metadata["macro_coverage"] is not None
    assert "rare_class_shortfall" in result.metadata
    assert all(values for values in result.prediction_sets)
    gate = evaluate_conformal_acceptance_gate(result, epsilon_m=0.5, epsilon_g=0.5)
    assert gate["method_family"] == "mondrian_raps"
    assert gate["status"] in {"pass", "warn", "fail"}


def test_graph_aware_conformal_reports_topology_bins() -> None:
    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    probabilities, target, _, _ = _classification_payload()
    probabilities = probabilities[:64]
    target = target[:64]
    adjacency = _ring_graph(probabilities.shape[0])
    node_features = np.column_stack(
        [
            np.sin(np.arange(probabilities.shape[0]) / 5.0),
            np.cos(np.arange(probabilities.shape[0]) / 7.0),
        ]
    )
    community = np.where(np.arange(probabilities.shape[0]) < 32, "left", "right")
    temporal = np.where(np.arange(probabilities.shape[0]) % 2 == 0, "early", "late")

    method_cls = registry.get("ml.uncertainty.graph_aware_conformal@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={
            "method_name": "graph_conv_classifier",
            "class_probabilities": probabilities,
            "target": target,
            "adjacency_matrix": adjacency,
            "node_features": node_features,
            "community": community,
            "temporal_bin": temporal,
        },
        params={
            "alpha": 0.1,
            "score_type": "aps",
            "graph_method": "snaps",
            "graph_smoothing": 0.25,
            "min_calibration_per_group": 8,
            "min_graph_effective_sample_size": 4,
        },
        seed=557,
    ).output["result"]

    diagnostic = result.conditional_coverage_diagnostic
    assert result.method_name == "graph_aware_conformal"
    assert diagnostic is not None
    assert diagnostic.graph is not None
    assert diagnostic.method_spec.family == "graph_snaps"
    assert diagnostic.graph.effective_sample_size == probabilities.shape[0]
    assert diagnostic.graph.degree_bin_coverage
    assert diagnostic.graph.community_coverage
    assert diagnostic.graph.homophily_bin_coverage
    assert diagnostic.graph.temporal_bin_coverage
    gate = evaluate_conformal_acceptance_gate(result, epsilon_m=0.5, epsilon_g=0.5)
    assert gate["method_family"] == "graph_snaps"
    assert "target_coverage" in gate
