from __future__ import annotations

import numpy as np
import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import (
    DynamicGraphDSCMData,
    DynamicGraphEvent,
    ensure_causal_methods_registered,
    estimate_dynamic_graph_dscm,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.phase4_dynamics import load_temporal_graph_causal_certificate


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _feedback_panel(seed: int = 11) -> DynamicGraphDSCMData:
    rng = np.random.default_rng(seed)
    n_units = 14
    n_periods = 12
    outcomes = np.zeros((n_periods, n_units), dtype=float)
    edges = np.zeros((n_periods, n_units, n_units), dtype=float)
    outcomes[0] = rng.normal(size=n_units)
    edges[0] = (rng.uniform(size=(n_units, n_units)) < 0.2).astype(float)
    np.fill_diagonal(edges[0], 0.0)

    for t_index in range(n_periods - 1):
        degree = edges[t_index].sum(axis=1)
        exposure = np.divide(
            edges[t_index] @ outcomes[t_index],
            degree,
            out=np.zeros(n_units, dtype=float),
            where=degree > 0.0,
        )
        outcomes[t_index + 1] = (
            0.25 * outcomes[t_index] + 1.25 * exposure + rng.normal(scale=0.05, size=n_units)
        )
        scores = np.full((n_units, n_units), -np.inf, dtype=float)
        for i in range(n_units):
            for j in range(n_units):
                if i == j:
                    continue
                scores[i, j] = -abs(outcomes[t_index, i] - outcomes[t_index, j])
                scores[i, j] += rng.normal(scale=0.05)
        threshold = float(np.quantile(scores[np.isfinite(scores)], 0.75))
        edges[t_index + 1] = (scores > threshold).astype(float)
        np.fill_diagonal(edges[t_index + 1], 0.0)

    return DynamicGraphDSCMData(
        edge_states=edges,
        node_outcomes=outcomes,
        directed=True,
        time_index=np.arange(n_periods, dtype=float),
    )


def test_dynamic_graph_dscm_detects_full_feedback_and_panel_fallback(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    data = _feedback_panel()
    result = estimate_dynamic_graph_dscm(
        data,
        {
            "alpha": 0.05,
            "artifact_store": store,
            "intervention": {
                "formation_multiplier": 0.8,
                "dissolution_multiplier": 1.2,
            },
        },
    )

    assert result.feedback_status == "full_feedback"
    assert result.processes["A"]["mechanisms"]["formation"] == "counting_intensity"
    assert result.estimator_api["causal_effect"]["method"] == "g_computation"
    assert {item["id"] for item in result.interventions}.issuperset(
        {"edge_intensity_shift", "block_feedback"}
    )
    assert result.local_dependence_graph["A_to_Y"].present
    assert result.local_dependence_graph["Y_to_A"].present
    assert {"P_to_A", "X_to_A", "X_to_Y"}.issubset(result.local_dependence_graph)
    assert result.loop_effect is not None
    assert result.fallback_used is True
    assert any("panel_fallback_used" in warning for warning in result.identification_warnings)
    assert "full_mean_outcome_effect" in result.causal_effect_curves
    assert "loop_mean_outcome_effect" in result.causal_effect_curves
    assert result.temporal_identification_certificate is not None
    assert result.local_independence_certificate is not None
    assert result.temporal_graph_causal_certificate is not None
    assert result.temporal_graph_causal_certificate.status == "identified"
    assert result.temporal_graph_causal_certificate_ref is not None
    loaded = load_temporal_graph_causal_certificate(
        store,
        result.temporal_graph_causal_certificate_ref,
    )
    assert loaded == result.temporal_graph_causal_certificate


def test_dynamic_graph_dscm_no_feedback_uses_no_loop_effect() -> None:
    rng = np.random.default_rng(123)
    n_units = 10
    n_periods = 8
    edges = np.zeros((n_periods, n_units, n_units), dtype=float)
    outcomes = rng.normal(size=(n_periods, n_units))
    for t_index in range(n_periods):
        random_edges = (rng.uniform(size=(n_units, n_units)) < 0.2).astype(float)
        np.fill_diagonal(random_edges, 0.0)
        edges[t_index] = random_edges
    data = DynamicGraphDSCMData(
        edge_states=edges,
        node_outcomes=outcomes,
        directed=True,
        time_index=np.arange(n_periods, dtype=float),
    )

    result = estimate_dynamic_graph_dscm(data, {"alpha": 1.0e-6})

    assert result.feedback_status == "no_feedback"
    assert result.loop_effect is None
    assert result.fallback_used is True


def test_dynamic_graph_dscm_dispatch_and_event_log_input() -> None:
    ensure_causal_methods_registered()
    method_cls = MethodRegistry.get_instance().get("causal.dynamic_graph.dscm@1.0.0")
    events = [
        DynamicGraphEvent(time=1.0, event_type="edge_formation", i=0, j=1),
        DynamicGraphEvent(time=1.0, event_type="outcome", i=0, value=1.0),
        DynamicGraphEvent(time=2.0, event_type="outcome", i=1, value=1.0),
        DynamicGraphEvent(time=3.0, event_type="edge_dissolution", i=0, j=1),
    ]
    data = DynamicGraphDSCMData(
        event_log=events,
        initial_edges=np.zeros((2, 2), dtype=float),
        initial_outcomes=np.zeros(2, dtype=float),
        directed=True,
    )

    dispatched = MethodDispatcher.get_instance().dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params={"alpha": 0.2},
        seed=7,
    )

    result = dispatched.output["result"]
    assert result.method_id == "causal.dynamic_graph.dscm"
    assert result.diagnostics["data_source"] == "event_log"
    assert result.temporal_graph_causal_certificate is not None
    assert "local_dependence_graph" in result.model_dump(mode="json")


def test_dynamic_graph_dscm_hybrid_covariate_and_observation_contract() -> None:
    data = _feedback_panel(seed=17)
    n_periods, n_units, _ = data.edge_states.shape
    covariates = np.repeat(np.linspace(0.0, 1.0, n_units)[None, :, None], n_periods, axis=0)
    policy = np.zeros((n_periods, n_units), dtype=float)
    policy[:, : n_units // 2] = 1.0
    events = [
        DynamicGraphEvent(time=1.0, event_type="policy", i=0, value=1.0),
        DynamicGraphEvent(
            time=1.0,
            event_type="covariate",
            i=0,
            value=2.0,
            metadata={"feature_index": 0},
        ),
    ]
    hybrid = DynamicGraphDSCMData(
        edge_states=data.edge_states,
        node_outcomes=data.node_outcomes,
        policy=policy,
        covariates=covariates,
        observation=np.ones((n_periods, n_units), dtype=float),
        event_log=events,
        directed=True,
        time_index=np.arange(n_periods, dtype=float),
    )

    result = estimate_dynamic_graph_dscm(
        hybrid,
        {
            "alpha": 0.2,
            "causal_effect_method": "likelihood_ratio_weighting",
            "latent_actor_effects": True,
        },
    )

    assert result.diagnostics["data_source"] == "hybrid"
    assert result.diagnostics["observation_process"]["declared"] is True
    assert result.estimator_api["causal_effect"]["method"] == "likelihood_ratio_weighting"
    assert result.estimator_api["adjustment"]["latent_actor_effects"] is True
    assert any("hybrid_data_used" in warning for warning in result.identification_warnings)
