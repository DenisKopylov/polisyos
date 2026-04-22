from __future__ import annotations

import numpy as np
import pytest


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


def _symmetric_adjacency(n, rng):
    A = rng.uniform(0, 1, size=(n, n))
    A = (A + A.T) / 2
    np.fill_diagonal(A, 0)
    return A


class TestCommunityDetection:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.community.community_detection@1.0.0")
        rng = np.random.default_rng(42)
        state = {"adjacency": _symmetric_adjacency(10, rng)}
        result = method.pure_step(state, {"n_clusters": 3, "__seed__": 42})
        assert isinstance(result, dict)


class TestInputOutputNetwork:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.io.input_output_network@1.0.0")
        rng = np.random.default_rng(42)
        state = {"adjacency": rng.uniform(0, 1, size=(5, 5))}
        result = method.pure_step(state, {})
        assert isinstance(result, dict)


class TestNetworkDiffusion:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.diffusion.network_diffusion@1.0.0")
        rng = np.random.default_rng(42)
        n = 8
        state = {
            "adjacency": _symmetric_adjacency(n, rng),
            "node_states": rng.uniform(0, 1, size=n),
        }
        result = method.pure_step(state, {"diffusion_rate": 0.3, "n_steps": 5})
        assert isinstance(result, dict)


class TestNetworkMissingnessAssessment:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "network.missingness.network_missingness_assessment@0.1.0",
        )
        state = {
            "adjacency": np.array(
                [
                    [0.0, 1.0, 0.0],
                    [1.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0],
                ]
            ),
        }
        result = method.pure_step(
            state,
            {
                "mode": "bounds_only",
                "frame_observed": True,
                "estimands": ("edge_count", "giant_component"),
            },
        )
        assert isinstance(result, dict)
        assert result["result"].missingness_assessment is not None


class TestContagionModel:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.contagion.contagion_model@1.0.0")
        rng = np.random.default_rng(42)
        n = 10
        node_states = np.zeros(n)
        node_states[:2] = 1.0  # 2 initially infected
        state = {
            "adjacency": _symmetric_adjacency(n, rng),
            "node_states": node_states,
        }
        result = method.pure_step(state, {"beta": 0.4, "gamma": 0.1, "n_steps": 5, "__seed__": 42})
        assert isinstance(result, dict)


class TestPeerEffectDecomposition:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.peer_effects.peer_effect_decomposition@1.0.0")
        adjacency = np.array(
            [
                [0.0, 1.0, 0.4, 0.0, 0.0, 0.0],
                [1.0, 0.0, 0.8, 0.4, 0.0, 0.0],
                [0.4, 0.8, 0.0, 0.6, 0.3, 0.0],
                [0.0, 0.4, 0.6, 0.0, 0.7, 0.2],
                [0.0, 0.0, 0.3, 0.7, 0.0, 0.9],
                [0.0, 0.0, 0.0, 0.2, 0.9, 0.0],
            ]
        )
        features = np.array([[0.2], [0.7], [1.1], [1.4], [0.9], [0.4]])
        W = adjacency / np.maximum(adjacency.sum(axis=1, keepdims=True), 1.0)
        outcome = np.linalg.solve(np.eye(adjacency.shape[0]) - 0.15 * W, 0.6 * features[:, 0] + 0.25 * (W @ features[:, 0]))
        state = {
            "adjacency": adjacency,
            "node_features": features,
            "node_states": outcome,
        }
        result = method.pure_step(state, {"ci_level": 0.9})
        assert isinstance(result, dict)
        payload = result["result"].peer_effect_decomposition
        assert payload is not None
        assert payload.reduced_form_peer_multiplier is not None
        assert payload.diagnostics.identification_status in {"identified", "weakly_identified", "partially_identified"}


class TestMultiplexNetwork:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.multiplex.multiplex_network@1.0.0")
        rng = np.random.default_rng(42)
        n = 6
        layers = np.stack([_symmetric_adjacency(n, rng) for _ in range(3)])
        state = {"adjacency_layers": layers}
        result = method.pure_step(state, {})
        assert isinstance(result, dict)


class TestStrategicNetworkFormation:
    def test_event_history_route_is_used_when_available(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.formation.strategic_formation@0.1.0")
        adjacency = np.array(
            [
                [0.0, 1.0, 0.0, 0.0],
                [1.0, 0.0, 1.0, 0.0],
                [0.0, 1.0, 0.0, 1.0],
                [0.0, 0.0, 1.0, 0.0],
            ]
        )
        dyad_features = np.zeros((4, 4, 1), dtype=float)
        dyad_features[0, 1, 0] = dyad_features[1, 0, 0] = 0.2
        dyad_features[1, 2, 0] = dyad_features[2, 1, 0] = 0.8
        dyad_features[2, 3, 0] = dyad_features[3, 2, 0] = 1.1
        state = {
            "adjacency": adjacency,
            "dyad_features": dyad_features,
            "initial_adjacency": np.zeros_like(adjacency),
            "formation_events": (
                {"i": 0, "j": 1, "next_state": 1},
                {"i": 1, "j": 2, "next_state": 1},
                {"i": 2, "j": 3, "next_state": 1},
                {"i": 0, "j": 2, "next_state": 0},
                {"i": 1, "j": 3, "next_state": 0},
                {"i": 0, "j": 3, "next_state": 0},
            ),
        }
        result = method.pure_step(state, {"prefer_event_history": True})
        payload = result["result"].formation_diagnostic
        assert payload is not None
        assert payload.strategy_used == "event_history_mle"
        assert payload.event_history_used is True
        assert payload.observed_events == 6
        assert payload.uncertainty_summary is not None
        assert payload.validation_summary is not None

    def test_event_level_covariates_count_toward_policy_support(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.formation.strategic_formation@0.1.0")
        adjacency = np.array(
            [
                [0.0, 1.0, 0.0, 0.0],
                [1.0, 0.0, 1.0, 0.0],
                [0.0, 1.0, 0.0, 1.0],
                [0.0, 0.0, 1.0, 0.0],
            ]
        )
        state = {
            "adjacency": adjacency,
            "initial_adjacency": np.zeros_like(adjacency),
            "formation_events": (
                {"i": 0, "j": 1, "next_state": 1, "dyad_covariates": (0.2,)},
                {"i": 1, "j": 2, "next_state": 1, "dyad_covariates": (0.8,)},
                {"i": 2, "j": 3, "next_state": 1, "dyad_covariates": (1.1,)},
                {"i": 0, "j": 2, "next_state": 0, "dyad_covariates": (0.1,)},
                {"i": 1, "j": 3, "next_state": 0, "dyad_covariates": (0.3,)},
                {"i": 0, "j": 3, "next_state": 0, "dyad_covariates": (0.0,)},
            ),
        }
        result = method.pure_step(state, {"prefer_event_history": True})
        payload = result["result"].formation_diagnostic
        assert payload is not None
        assert payload.strategy_used == "event_history_mle"
        assert payload.dyad_feature_dimension == 1
        assert payload.dyad_feature_support > 0.0
        assert payload.policy_counterfactual_ready is False

    def test_cross_sectional_route_uses_stationary_mcmc_mle(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.formation.strategic_formation@0.1.0")
        adjacency = np.array(
            [
                [0.0, 1.0, 1.0, 0.0, 0.0],
                [1.0, 0.0, 1.0, 1.0, 0.0],
                [1.0, 1.0, 0.0, 1.0, 0.0],
                [0.0, 1.0, 1.0, 0.0, 1.0],
                [0.0, 0.0, 0.0, 1.0, 0.0],
            ]
        )
        dyad_features = np.zeros((5, 5, 2), dtype=float)
        dyad_features[..., 0] = np.array(
            [
                [0.0, 0.1, 0.2, 0.9, 1.2],
                [0.1, 0.0, 0.3, 0.4, 1.0],
                [0.2, 0.3, 0.0, 0.2, 1.1],
                [0.9, 0.4, 0.2, 0.0, 0.3],
                [1.2, 1.0, 1.1, 0.3, 0.0],
            ]
        )
        dyad_features[..., 1] = np.array(
            [
                [0.0, 1.0, 1.0, 0.2, 0.1],
                [1.0, 0.0, 1.0, 0.8, 0.3],
                [1.0, 1.0, 0.0, 0.7, 0.2],
                [0.2, 0.8, 0.7, 0.0, 1.0],
                [0.1, 0.3, 0.2, 1.0, 0.0],
            ]
        )
        result = method.pure_step(
            {"adjacency": adjacency, "dyad_features": dyad_features},
            {
                "prefer_event_history": False,
                "sa_iterations": 4,
                "sa_batch_draws": 4,
                "predictive_draws": 8,
                "bootstrap_draws": 6,
            },
        )
        payload = result["result"].formation_diagnostic
        assert payload is not None
        assert payload.strategy_used == "stationary_mcmc_mle"
        assert payload.identification_status in {"point_identified", "weakly_identified"}
        assert "intercept" in payload.parameter_estimates
        assert payload.warm_start_used is True
        assert payload.uncertainty_summary is not None
        assert payload.validation_summary is not None

    def test_counterfactual_summary_is_returned_when_policy_shock_is_available(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.formation.strategic_formation@0.1.0")
        adjacency = np.array(
            [
                [0.0, 1.0, 1.0, 0.0, 0.0],
                [1.0, 0.0, 1.0, 1.0, 0.0],
                [1.0, 1.0, 0.0, 1.0, 0.0],
                [0.0, 1.0, 1.0, 0.0, 1.0],
                [0.0, 0.0, 0.0, 1.0, 0.0],
            ]
        )
        dyad_features = np.zeros((5, 5, 1), dtype=float)
        dyad_features[..., 0] = np.array(
            [
                [0.0, 0.1, 0.2, 0.9, 1.2],
                [0.1, 0.0, 0.3, 0.4, 1.0],
                [0.2, 0.3, 0.0, 0.2, 1.1],
                [0.9, 0.4, 0.2, 0.0, 0.3],
                [1.2, 1.0, 1.1, 0.3, 0.0],
            ]
        )
        policy_shock = np.zeros_like(dyad_features)
        policy_shock[..., 0] = 0.2
        result = method.pure_step(
            {
                "adjacency": adjacency,
                "dyad_features": dyad_features,
                "policy_shock": policy_shock,
            },
            {
                "prefer_event_history": False,
                "sa_iterations": 4,
                "sa_batch_draws": 4,
                "predictive_draws": 8,
                "bootstrap_draws": 6,
                "counterfactual_draws": 6,
            },
        )
        payload = result["result"].formation_diagnostic
        assert payload is not None
        assert payload.policy_counterfactual_ready is True
        assert payload.counterfactual_summary is not None
        assert "density" in payload.counterfactual_summary.effects

    def test_fallback_returns_identified_set_when_support_is_weak(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.formation.strategic_formation@0.1.0")
        adjacency = np.array(
            [
                [0.0, 1.0, 0.0, 0.0],
                [1.0, 0.0, 1.0, 0.0],
                [0.0, 1.0, 0.0, 1.0],
                [0.0, 0.0, 1.0, 0.0],
            ]
        )
        result = method.pure_step({"adjacency": adjacency}, {})
        payload = result["result"].formation_diagnostic
        assert payload is not None
        assert payload.strategy_used == "moment_inequality_fallback"
        assert payload.identified_set is not None
        assert "triadic_closure" in payload.identified_set.parameter_bounds
