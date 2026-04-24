from __future__ import annotations

import numpy as np


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


def _baseline_state(observability_rate: float = 1.0) -> dict[str, object]:
    adjacency = np.array(
        [
            [0.0, 1.0, 0.3, 0.0, 0.2, 0.0, 0.0, 0.0],
            [1.0, 0.0, 0.8, 0.5, 0.0, 0.1, 0.0, 0.0],
            [0.3, 0.8, 0.0, 0.7, 0.4, 0.0, 0.2, 0.0],
            [0.0, 0.5, 0.7, 0.0, 0.6, 0.3, 0.0, 0.1],
            [0.2, 0.0, 0.4, 0.6, 0.0, 0.9, 0.3, 0.0],
            [0.0, 0.1, 0.0, 0.3, 0.9, 0.0, 0.8, 0.4],
            [0.0, 0.0, 0.2, 0.0, 0.3, 0.8, 0.0, 1.0],
            [0.0, 0.0, 0.0, 0.1, 0.0, 0.4, 1.0, 0.0],
        ]
    )
    features = np.array([[0.1], [0.5], [0.9], [1.4], [1.1], [0.6], [0.3], [1.0]])
    row_sums = np.maximum(adjacency.sum(axis=1, keepdims=True), 1.0)
    W = adjacency / row_sums
    outcome = np.linalg.solve(
        np.eye(adjacency.shape[0]) - 0.2 * W,
        0.7 * features[:, 0] + 0.25 * (W @ features[:, 0]),
    )
    return {
        "adjacency": adjacency,
        "node_features": features,
        "node_states": outcome,
        "metadata": {"network_observability_rate": observability_rate},
    }


def _panel_payload() -> dict[str, np.ndarray]:
    base = _baseline_state()
    adjacency = np.asarray(base["adjacency"], dtype=float)
    features = np.asarray(base["node_features"], dtype=float)
    row_sums = np.maximum(adjacency.sum(axis=1, keepdims=True), 1.0)
    W0 = adjacency / row_sums

    adjacency_1 = adjacency.copy()
    adjacency_1[0, 3] = 0.25
    adjacency_1[3, 0] = 0.25
    adjacency_1[1, 6] = 0.15
    adjacency_1[6, 1] = 0.15
    adjacency_2 = adjacency.copy()
    adjacency_2[2, 7] = 0.35
    adjacency_2[7, 2] = 0.35
    adjacency_2[4, 0] = 0.30
    adjacency_2[0, 4] = 0.30

    W1 = adjacency_1 / np.maximum(adjacency_1.sum(axis=1, keepdims=True), 1.0)
    W2 = adjacency_2 / np.maximum(adjacency_2.sum(axis=1, keepdims=True), 1.0)

    features_panel = np.stack(
        [
            features,
            features + np.linspace(0.05, 0.12, features.shape[0]).reshape(-1, 1),
            features + np.linspace(0.10, 0.18, features.shape[0]).reshape(-1, 1),
        ],
        axis=0,
    )
    treatment_panel = np.array(
        [
            [0, 1, 0, 1, 0, 1, 0, 1],
            [1, 1, 0, 1, 0, 0, 1, 0],
            [1, 0, 1, 1, 0, 0, 1, 1],
        ],
        dtype=float,
    )
    y0 = np.asarray(base["node_states"], dtype=float)
    y1 = (
        0.55 * y0
        + 0.60 * features_panel[1, :, 0]
        + 0.18 * (W1 @ y0)
        + 0.14 * (W1 @ features_panel[1, :, 0])
        + 0.12 * treatment_panel[1]
        + 0.05 * (W1 @ treatment_panel[1])
    )
    y2 = (
        0.55 * y1
        + 0.60 * features_panel[2, :, 0]
        + 0.18 * (W2 @ y1)
        + 0.14 * (W2 @ features_panel[2, :, 0])
        + 0.12 * treatment_panel[2]
        + 0.05 * (W2 @ treatment_panel[2])
    )
    return {
        "panel_outcomes": np.stack([y0, y1, y2], axis=0),
        "panel_features": features_panel,
        "panel_adjacency": np.stack([adjacency, adjacency_1, adjacency_2], axis=0),
        "panel_treatment": treatment_panel,
    }


def test_peer_effect_decomposition_identified_route(isolated_registry) -> None:
    method = _method_or_skip(
        isolated_registry, "network.peer_effects.peer_effect_decomposition@1.0.0"
    )
    result = method.pure_step(
        _baseline_state(),
        {"weak_iv_threshold": 0.1, "ci_level": 0.9},
    )

    decomposition = result["result"].peer_effect_decomposition
    assert decomposition is not None
    assert decomposition.diagnostics.identification_status == "identified"
    assert decomposition.endogenous_effect is not None
    assert decomposition.contextual_effect is not None
    assert decomposition.total_peer_effect is not None
    assert decomposition.reduced_form_peer_multiplier is not None


def test_peer_effect_decomposition_blocks_partial_network(isolated_registry) -> None:
    method = _method_or_skip(
        isolated_registry, "network.peer_effects.peer_effect_decomposition@1.0.0"
    )
    result = method.pure_step(_baseline_state(observability_rate=0.55), {})

    decomposition = result["result"].peer_effect_decomposition
    assert decomposition is not None
    assert decomposition.diagnostics.identification_status == "partially_identified"
    assert decomposition.diagnostics.blocking_reason == "not_identified_partial_network"
    assert decomposition.endogenous_effect is None
    assert decomposition.contextual_effect is None
    assert decomposition.reduced_form_peer_multiplier is not None
    assert decomposition.endogenous_bounds is not None
    assert decomposition.contextual_bounds is not None


def test_peer_effect_decomposition_graphical_reconstruction_route(isolated_registry) -> None:
    method = _method_or_skip(
        isolated_registry, "network.peer_effects.peer_effect_decomposition@1.0.0"
    )
    state = _baseline_state(observability_rate=0.55)
    state["metadata"]["can_reconstruct"] = True
    state["metadata"]["reconstructed_adjacency"] = np.asarray(state["adjacency"], dtype=float)

    result = method.pure_step(state, {"weak_iv_threshold": 0.0})

    decomposition = result["result"].peer_effect_decomposition
    assert decomposition is not None
    assert decomposition.diagnostics.strategy_used == "graphical_reconstruction"
    assert decomposition.diagnostics.identification_status == "identified"
    assert decomposition.endogenous_effect is not None
    assert decomposition.contextual_effect is not None


def test_peer_effect_decomposition_external_iv_route(isolated_registry) -> None:
    method = _method_or_skip(
        isolated_registry, "network.peer_effects.peer_effect_decomposition@1.0.0"
    )
    state = _baseline_state()
    features = np.asarray(state["node_features"], dtype=float)[:, 0]
    external_iv = np.column_stack([features**2, features**3])

    result = method.pure_step(
        state,
        {
            "strategy": "external_iv",
            "external_instruments": external_iv,
            "weak_iv_threshold": 0.0,
        },
    )

    decomposition = result["result"].peer_effect_decomposition
    assert decomposition is not None
    assert decomposition.diagnostics.strategy_used == "external_iv"
    assert decomposition.diagnostics.identification_status == "identified"
    assert decomposition.endogenous_effect is not None
    assert decomposition.contextual_effect is not None


def test_peer_effect_decomposition_control_function_route(isolated_registry) -> None:
    method = _method_or_skip(
        isolated_registry, "network.peer_effects.peer_effect_decomposition@1.0.0"
    )
    state = _baseline_state()
    state["metadata"]["network_endogenous"] = True
    control_residuals = np.column_stack(
        [
            np.asarray(state["node_features"], dtype=float)[:, 0] ** 2,
            np.linspace(-0.4, 0.4, 8),
        ]
    )

    result = method.pure_step(
        state,
        {
            "strategy": "control_function",
            "control_function_residuals": control_residuals,
            "weak_iv_threshold": 0.0,
        },
    )

    decomposition = result["result"].peer_effect_decomposition
    assert decomposition is not None
    assert decomposition.diagnostics.strategy_used == "control_function"
    assert decomposition.diagnostics.identification_status == "identified"
    assert decomposition.endogenous_effect is not None
    assert decomposition.contextual_effect is not None


def test_peer_effect_decomposition_leave_own_out_route(isolated_registry) -> None:
    method = _method_or_skip(
        isolated_registry, "network.peer_effects.peer_effect_decomposition@1.0.0"
    )
    state = _baseline_state()
    state["metadata"]["network_endogenous"] = True
    leave_own_out = np.asarray(state["adjacency"], dtype=float).copy()
    leave_own_out[0, 1] = 0.0
    leave_own_out[1, 0] = 0.0
    leave_own_out[4, 5] = 0.0
    leave_own_out[5, 4] = 0.0

    result = method.pure_step(
        state,
        {
            "strategy": "leave_own_out",
            "leave_own_out_adjacency": leave_own_out,
            "weak_iv_threshold": 0.0,
        },
    )

    decomposition = result["result"].peer_effect_decomposition
    assert decomposition is not None
    assert decomposition.diagnostics.strategy_used == "leave_own_out"
    assert decomposition.diagnostics.identification_status == "identified"
    assert decomposition.endogenous_effect is not None
    assert decomposition.contextual_effect is not None


def test_peer_effect_decomposition_panel_dynamic_contagion_route(isolated_registry) -> None:
    method = _method_or_skip(
        isolated_registry, "network.peer_effects.peer_effect_decomposition@1.0.0"
    )
    state = _baseline_state()
    panel_payload = _panel_payload()

    result = method.pure_step(
        state,
        {
            "strategy": "panel",
            "model_class": "dynamic_contagion",
            "panel_outcomes": panel_payload["panel_outcomes"],
            "panel_features": panel_payload["panel_features"],
            "panel_adjacency": panel_payload["panel_adjacency"],
            "panel_treatment": panel_payload["panel_treatment"],
            "weak_iv_threshold": 0.0,
        },
    )

    decomposition = result["result"].peer_effect_decomposition
    assert decomposition is not None
    assert decomposition.diagnostics.strategy_used == "panel"
    assert decomposition.model_class == "dynamic_contagion"
    assert decomposition.endogenous_effect is not None
    assert decomposition.contextual_effect is not None
    assert decomposition.direct_effect is not None
    assert decomposition.contagion_effect is not None
    assert decomposition.infectiousness_effect is not None


def test_peer_effect_decomposition_randomization_route(isolated_registry) -> None:
    method = _method_or_skip(
        isolated_registry, "network.peer_effects.peer_effect_decomposition@1.0.0"
    )
    state = _baseline_state()
    treatment = np.array([0, 1, 0, 1, 1, 0, 1, 0], dtype=float)

    result = method.pure_step(
        state,
        {
            "strategy": "randomization",
            "model_class": "potential_outcomes_network",
            "treatment": treatment,
            "assignment_probabilities": np.full(treatment.shape[0], 0.5),
        },
    )

    decomposition = result["result"].peer_effect_decomposition
    assert decomposition is not None
    assert decomposition.diagnostics.strategy_used == "randomization"
    assert decomposition.model_class == "potential_outcomes_network"
    assert decomposition.direct_effect is not None
    assert decomposition.spillover_effect is not None
    assert decomposition.endogenous_effect is None
    assert decomposition.contextual_effect is None
