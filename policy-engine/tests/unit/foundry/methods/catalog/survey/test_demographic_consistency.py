from __future__ import annotations

import math

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.survey.demographic_consistency import (
    _relative_interior_support,
)



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

    def test_exact_reconciled_triangular_boundary_fixture_converges(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(
            isolated_registry,
            "survey.demography.demographic_consistency@1.0.0",
        )
        state = {
            "base_weights": np.array([1.0, 2.0], dtype=float),
            "candidate_record_index": np.array([0, 0, 1], dtype=int),
            "candidate_state_index": np.array([0, 1, 1], dtype=int),
            "prior_flows": np.array([0.8, 0.2, 1.0], dtype=float),
            "target_state_totals": np.array([10.0, 20.0], dtype=float),
        }
        result = method.pure_step(
            state, {"max_iterations": 250, "tolerance": 1e-8}
        )["result"]

        assert np.allclose(result.calibrated_flows, np.array([1.0, 0.0, 2.0]))
        assert np.allclose(result.achieved_row_totals, np.array([1.0, 2.0]))
        assert np.allclose(result.achieved_state_totals, np.array([1.0, 2.0]))
        assert result.diagnostics["mass_reconciliation_applied"] is True
        assert result.diagnostics["converged"] is True
        assert result.diagnostics["structural_zero_violations"] == 0

    def test_balances_fractional_boundary_support_and_label_permutation(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(
            isolated_registry,
            "survey.demography.demographic_consistency@1.0.0",
        )
        state = {
            "base_weights": np.array([0.5, 1.25], dtype=float),
            "candidate_record_index": np.array([0, 0, 1], dtype=int),
            "candidate_state_index": np.array([0, 1, 1], dtype=int),
            "prior_flows": np.array([0.3, 0.2, 1.25], dtype=float),
            "target_state_totals": np.array([0.5, 1.25], dtype=float),
        }
        original_prior = state["prior_flows"].copy()
        params = {"max_iterations": 4, "tolerance": 1e-10}
        result = method.pure_step(state, params)["result"]

        assert np.allclose(result.calibrated_flows, np.array([0.5, 0.0, 1.25]))
        assert np.allclose(result.achieved_row_totals, state["base_weights"])
        assert np.allclose(result.achieved_state_totals, state["target_state_totals"])
        assert result.diagnostics["converged"] is True
        assert result.diagnostics["structural_zero_violations"] == 0
        assert np.array_equal(state["prior_flows"], original_prior)

        permuted = {
            "base_weights": np.array([1.25, 0.5], dtype=float),
            "candidate_record_index": np.array([1, 0, 1], dtype=int),
            "candidate_state_index": np.array([0, 0, 1], dtype=int),
            "prior_flows": np.array([0.2, 1.25, 0.3], dtype=float),
            "target_state_totals": np.array([1.25, 0.5], dtype=float),
        }
        permuted_result = method.pure_step(permuted, params)["result"]
        actual_by_pair = dict(
            zip(
                zip(
                    permuted_result.candidate_record_index,
                    permuted_result.candidate_state_index,
                    strict=True,
                ),
                permuted_result.calibrated_flows,
                strict=True,
            )
        )
        expected_by_pair = {(0, 0): 0.5, (0, 1): 0.0, (1, 1): 1.25}
        for pair, expected in expected_by_pair.items():
            permuted_pair = (1 - pair[0], 1 - pair[1])
            assert math.isclose(actual_by_pair[permuted_pair], expected, abs_tol=1e-10)

    def test_keeps_edges_that_can_carry_mass_on_an_alternating_cycle(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(
            isolated_registry,
            "survey.demography.demographic_consistency@1.0.0",
        )
        state = {
            "base_weights": np.array([1.0, 1.0], dtype=float),
            "candidate_record_index": np.array([0, 0, 1, 1], dtype=int),
            "candidate_state_index": np.array([0, 1, 0, 1], dtype=int),
            "prior_flows": np.array([0.8, 0.2, 0.1, 0.9], dtype=float),
            "target_state_totals": np.array([1.0, 1.0], dtype=float),
        }
        result = method.pure_step(
            state, {"max_iterations": 100, "tolerance": 1e-10}
        )["result"]

        assert np.all(result.calibrated_flows > 0.0)
        assert np.allclose(result.achieved_row_totals, state["base_weights"])
        assert np.allclose(result.achieved_state_totals, state["target_state_totals"])
        assert result.diagnostics["converged"] is True

    def test_hall_infeasible_sparse_margins_still_refuse(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "survey.demography.demographic_consistency@1.0.0",
        )
        state = {
            "base_weights": np.array([1.0, 1.0, 1.0], dtype=float),
            "candidate_record_index": np.array([0, 1, 2], dtype=int),
            "candidate_state_index": np.array([0, 0, 1], dtype=int),
            "prior_flows": np.array([1.0, 1.0, 1.0], dtype=float),
            "target_state_totals": np.array([1.5, 1.5], dtype=float),
        }

        with pytest.raises(ValueError, match="did not converge"):
            method.pure_step(
                state,
                {"max_iterations": 25, "tolerance": 1e-10, "require_convergence": True},
            )

    def test_zero_survivor_population_remains_a_valid_boundary(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "survey.demography.demographic_consistency@1.0.0",
        )
        state = {
            "base_weights": np.array([1.0, 2.0], dtype=float),
            "exit_weights": np.array([1.0, 2.0], dtype=float),
            "candidate_record_index": np.array([0, 0, 1], dtype=int),
            "candidate_state_index": np.array([0, 1, 1], dtype=int),
            "prior_flows": np.array([0.8, 0.2, 1.0], dtype=float),
            "target_state_totals": np.array([0.0, 0.0], dtype=float),
        }

        result = method.pure_step(
            state, {"max_iterations": 4, "tolerance": 1e-8}
        )["result"]

        assert np.array_equal(result.calibrated_flows, np.zeros(3))
        assert np.array_equal(result.record_survivor_weights, np.zeros(2))
        assert np.array_equal(result.achieved_state_totals, np.zeros(2))
        assert np.array_equal(result.exit_weights, state["exit_weights"])
        assert result.diagnostics["converged"] is True
        assert result.diagnostics["structural_zero_violations"] == 0

    def test_one_ulp_mass_gap_keeps_the_support_proof_conservative(self) -> None:
        requested_tolerance = 1e-8
        adjacent_total = math.nextafter(1.0, math.inf)
        assert 0.0 < adjacent_total - 1.0 < requested_tolerance

        support_proof = _relative_interior_support(
            np.array([1.0]),
            np.array([adjacent_total]),
            np.array([0], dtype=int),
            np.array([0], dtype=int),
            np.array([1.0]),
        )

        # The estimator's requested tolerance may accept this tiny discrepancy,
        # but it is not an exact transportation witness for pruning support.
        assert support_proof is None

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
