from __future__ import annotations

import math

import numpy as np
import pytest


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


def _state() -> dict[str, np.ndarray]:
    return {
        "base_weights": np.array([3.0, 2.0], dtype=float),
        "candidate_record_index": np.array([0, 0, 1, 1], dtype=int),
        "candidate_state_index": np.array([0, 1, 1, 2], dtype=int),
        "prior_flows": np.array([2.0, 1.0, 1.0, 1.0], dtype=float),
        "target_state_totals": np.array([2.0, 2.0, 1.0], dtype=float),
    }


class TestDemographicConsistencyEstimator:
    def test_balances_rows_and_states(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "survey.demography.demographic_consistency@1.0.0",
        )
        result = method.pure_step(_state(), {"max_iterations": 100, "tolerance": 1e-10})
        payload = result["result"]

        assert np.allclose(payload.achieved_row_totals, payload.record_survivor_weights)
        assert np.allclose(payload.achieved_state_totals, payload.target_state_totals)
        assert payload.diagnostics["converged"] is True
        assert payload.diagnostics["max_row_gap"] <= 1e-10
        assert payload.diagnostics["max_final_state_gap"] <= 1e-10
        assert payload.diagnostics["structural_zero_violations"] == 0

    def test_handles_exits_entrants_and_sparse_structural_zeros(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "survey.demography.demographic_consistency@1.0.0",
        )
        state = {
            "base_weights": np.array([4.0, 4.0], dtype=float),
            "exit_weights": np.array([1.0, 0.0], dtype=float),
            "entrant_state_totals": np.array([0.0, 1.0], dtype=float),
            "candidate_record_index": np.array([0, 1], dtype=int),
            "candidate_state_index": np.array([0, 1], dtype=int),
            "prior_flows": np.array([1.0, 1.0], dtype=float),
            "target_state_totals": np.array([3.0, 5.0], dtype=float),
        }
        result = method.pure_step(state, {"tolerance": 1e-10})
        payload = result["result"]

        assert np.allclose(payload.calibrated_flows, np.array([3.0, 4.0]))
        assert np.allclose(payload.record_survivor_weights, np.array([3.0, 4.0]))
        assert np.allclose(payload.achieved_state_totals, np.array([3.0, 5.0]))
        assert math.isclose(
            payload.diagnostics["entrant_mass_total"], 1.0, rel_tol=0.0, abs_tol=1e-12
        )
        assert math.isclose(payload.diagnostics["exit_mass_total"], 1.0, rel_tol=0.0, abs_tol=1e-12)

    def test_reconciles_mass_when_targets_do_not_sum_to_available_survivors(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(
            isolated_registry,
            "survey.demography.demographic_consistency@1.0.0",
        )
        state = {
            "base_weights": np.array([2.0, 2.0], dtype=float),
            "candidate_record_index": np.array([0, 0, 1, 1], dtype=int),
            "candidate_state_index": np.array([0, 1, 0, 1], dtype=int),
            "prior_flows": np.array([1.0, 1.0, 1.0, 1.0], dtype=float),
            "target_state_totals": np.array([3.0, 0.5], dtype=float),
        }
        result = method.pure_step(
            state,
            {
                "tolerance": 1e-10,
                "reconciliation_mode": "scale_survivor_targets",
            },
        )
        payload = result["result"]
        expected = np.array([3.0, 0.5]) * (4.0 / 3.5)

        assert payload.diagnostics["mass_reconciliation_applied"] is True
        assert math.isclose(
            payload.diagnostics["mass_reconciliation_factor"],
            4.0 / 3.5,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        assert np.allclose(payload.reconciled_state_totals, expected)
        assert np.allclose(payload.achieved_state_totals, expected)

    def test_raises_when_sparse_constraints_are_infeasible(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "survey.demography.demographic_consistency@1.0.0",
        )
        state = {
            "base_weights": np.array([4.0, 4.0], dtype=float),
            "exit_weights": np.array([1.0, 0.0], dtype=float),
            "entrant_state_totals": np.array([0.0, 1.0], dtype=float),
            "candidate_record_index": np.array([0, 1], dtype=int),
            "candidate_state_index": np.array([0, 1], dtype=int),
            "prior_flows": np.array([1.0, 1.0], dtype=float),
            "target_state_totals": np.array([3.0, 4.0], dtype=float),
        }

        with pytest.raises(ValueError, match="did not converge"):
            method.pure_step(state, {"tolerance": 1e-10, "max_iterations": 25})

    def test_soft_constraints_improve_non_core_margin_fit(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "survey.demography.demographic_consistency@1.0.0",
        )
        state = {
            "base_weights": np.array([1.0, 1.0], dtype=float),
            "candidate_record_index": np.array([0, 0, 1, 1], dtype=int),
            "candidate_state_index": np.array([0, 1, 0, 1], dtype=int),
            "prior_flows": np.array([0.95, 0.05, 0.95, 0.05], dtype=float),
            "target_state_totals": np.array([1.0, 1.0], dtype=float),
            "soft_constraint_matrix": np.array([[0.0, 1.0, 0.0, 0.0]], dtype=float),
            "soft_target_totals": np.array([0.75], dtype=float),
            "soft_constraint_weights": np.array([25.0], dtype=float),
        }

        baseline = method.pure_step(
            {k: v for k, v in state.items() if not k.startswith("soft_")},
            {"tolerance": 1e-10},
        )["result"]
        softened = method.pure_step(
            state,
            {
                "tolerance": 1e-10,
                "soft_iterations": 8,
                "soft_step_size": 0.35,
                "soft_tolerance": 1e-3,
            },
        )["result"]

        baseline_soft_total = float(
            (state["soft_constraint_matrix"] @ baseline.calibrated_flows).item()
        )
        baseline_gap = abs(baseline_soft_total - 0.75)
        soft_gap = softened.diagnostics["soft_max_gap"]
        assert soft_gap < baseline_gap


class TestCCEBEstimator:
    def test_matches_demographic_consistency_core(self, isolated_registry) -> None:
        cceb = _method_or_skip(isolated_registry, "survey.demography.cceb@1.0.0")
        generic = _method_or_skip(
            isolated_registry,
            "survey.demography.demographic_consistency@1.0.0",
        )
        params = {"max_iterations": 100, "tolerance": 1e-10}

        cceb_result = cceb.pure_step(_state(), params)["result"]
        generic_result = generic.pure_step(_state(), params)["result"]

        assert np.allclose(cceb_result.calibrated_flows, generic_result.calibrated_flows)
        assert np.allclose(cceb_result.achieved_state_totals, generic_result.achieved_state_totals)
        assert math.isclose(
            cceb_result.diagnostics["entropic_objective"],
            generic_result.diagnostics["entropic_objective"],
            rel_tol=0.0,
            abs_tol=1e-12,
        )
