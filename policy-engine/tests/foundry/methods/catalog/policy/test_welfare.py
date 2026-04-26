from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.policy.evaluation import BudgetImpactEstimator
from polisyos.foundry.methods.catalog.policy.welfare import (
    AtkinsonSWFEstimator,
    CostBenefitAnalysisEstimator,
    CostEffectivenessEstimator,
    RawlsianSWFEstimator,
    SenCapabilityEstimator,
    StateDependentInverseSocialWeightsEstimator,
    UtilitarianSWFEstimator,
    clear_social_weight_manifest_registry,
    resolve_social_weight_schedule,
)
from polisyos.ir.analytics.phase4_dynamics import Phase4DynamicsGateError


def _inverse_tax_rates(
    incomes: np.ndarray,
    density_row: np.ndarray,
    elasticity_row: np.ndarray,
    weights: np.ndarray,
) -> np.ndarray:
    mass = density_row / np.sum(density_row)
    tail_mass = np.cumsum(mass[::-1])[::-1]
    pareto_like = np.maximum(incomes, 1.0) * mass / np.maximum(tail_mass, 1.0e-8)
    tau = (1.0 - weights) / np.maximum(1.0 - weights + pareto_like * elasticity_row, 1.0e-8)
    return np.clip(tau, 0.0, 0.95)


def _make_inverse_problem(
    basis_matrix: np.ndarray,
    beta_true: np.ndarray,
    *,
    densities: np.ndarray | None = None,
    elasticities: np.ndarray | None = None,
) -> tuple[dict[str, np.ndarray], np.ndarray]:
    income_grid = np.array([10.0, 18.0, 28.0, 42.0, 65.0, 95.0], dtype=float)
    weights_true = basis_matrix @ beta_true
    assert np.all(weights_true > 0.0)
    assert np.all(weights_true <= 1.0 + 1.0e-8)

    if densities is None:
        densities = np.array(
            [
                [0.22, 0.20, 0.18, 0.16, 0.14, 0.10],
                [0.12, 0.14, 0.17, 0.18, 0.19, 0.20],
            ],
            dtype=float,
        )
    if elasticities is None:
        elasticities = np.array(
            [
                [0.18, 0.20, 0.22, 0.24, 0.26, 0.28],
                [0.16, 0.19, 0.21, 0.23, 0.25, 0.27],
            ],
            dtype=float,
        )

    marginal_tax_rates = np.vstack(
        [
            _inverse_tax_rates(income_grid, densities[idx], elasticities[idx], weights_true)
            for idx in range(densities.shape[0])
        ]
    )
    state = {
        "income_grid": income_grid,
        "marginal_tax_rates": marginal_tax_rates,
        "density": densities,
        "elasticities": elasticities[:, :, None],
        "state_features": np.linspace(0.0, 1.0, income_grid.size)[:, None],
        "basis_matrix": basis_matrix,
    }
    return state, weights_true


class TestCostBenefitAnalysis:
    def test_positive_npv(self):
        state = {
            "benefits": np.array([0, 100, 200, 300]),
            "costs": np.array([500, 50, 50, 50]),
        }
        result = CostBenefitAnalysisEstimator.pure_step(state, {"discount_rate": 0.0})["result"]
        assert result["npv"] == pytest.approx(-50.0)
        assert result["bcr"] == pytest.approx(600.0 / 650.0, rel=1e-4)
        assert result["n_periods"] == 4

    def test_zero_discount_rate(self):
        state = {
            "benefits": np.array([100, 100]),
            "costs": np.array([50, 50]),
        }
        result = CostBenefitAnalysisEstimator.pure_step(state, {"discount_rate": 0.0})["result"]
        assert result["npv"] == pytest.approx(100.0)
        assert result["bcr"] == pytest.approx(2.0)

    def test_irr_found(self):
        state = {
            "benefits": np.array([0, 200, 200]),
            "costs": np.array([300, 0, 0]),
        }
        result = CostBenefitAnalysisEstimator.pure_step(state, {"discount_rate": 0.05})["result"]
        assert result["irr"] is not None
        assert result["irr"] > 0

    def test_shape_mismatch(self):
        with pytest.raises(ValueError, match="same length"):
            CostBenefitAnalysisEstimator.pure_step(
                {"benefits": np.array([1, 2]), "costs": np.array([1])}, {}
            )

    def test_phase4_gate_blocks_long_cost_benefit_without_calibrated_regime(self):
        state = {
            "benefits": np.ones(13, dtype=float),
            "costs": np.zeros(13, dtype=float),
        }

        with pytest.raises(Phase4DynamicsGateError):
            CostBenefitAnalysisEstimator.pure_step(state, {})

        result = CostBenefitAnalysisEstimator.pure_step(
            state,
            {"regime_shift_forecast_bundle": {"regime_status": "calibrated"}},
        )["result"]
        assert result["phase4_gate_verdict"]["status"] == "allowed"
        assert result["phase4_gate_verdict"]["checked_regime_bundle"] is True


def test_budget_impact_phase4_gate_records_short_horizon_verdict() -> None:
    result = BudgetImpactEstimator.pure_step(
        {
            "revenue_effects": np.array([2.0, 3.0]),
            "expenditure_effects": np.array([1.0, 1.0]),
        },
        {},
    )["result"]

    assert result["phase4_gate_verdict"]["status"] == "allowed"
    assert result["phase4_gate_verdict"]["horizon"] == 2


class TestCostEffectiveness:
    def test_icer_computation(self):
        state = {
            "costs": np.array([100, 200, 150]),
            "effects": np.array([10, 30, 20]),
        }
        result = CostEffectivenessEstimator.pure_step(state, {"baseline_index": 0})["result"]
        assert result["icers"][0] is None  # baseline
        assert result["icers"][1] == pytest.approx(5.0)  # (200-100)/(30-10)


class TestSWFs:
    def test_utilitarian(self):
        result = UtilitarianSWFEstimator.pure_step(np.array([10, 20, 30]), {})["result"]
        assert result["welfare"] == pytest.approx(60.0)
        assert result["mean_utility"] == pytest.approx(20.0)

    def test_rawlsian(self):
        result = RawlsianSWFEstimator.pure_step(np.array([10, 20, 30]), {})["result"]
        assert result["welfare"] == pytest.approx(10.0)
        assert result["min_index"] == 0

    def test_atkinson_swf(self):
        values = np.array([10, 20, 30, 40, 50])
        result = AtkinsonSWFEstimator.pure_step(values, {"epsilon": 0.5})["result"]
        assert result["welfare"] > 0
        assert result["ede_income"] <= float(np.mean(values))

    def test_atkinson_swf_equal(self):
        values = np.array([100.0, 100.0, 100.0])
        result = AtkinsonSWFEstimator.pure_step(values, {"epsilon": 1.0})["result"]
        assert result["ede_income"] == pytest.approx(100.0, rel=1e-4)

    def test_sen_capability(self):
        # Equal distribution → Gini = 0 → welfare = mean
        values = np.array([100.0, 100.0, 100.0])
        result = SenCapabilityEstimator.pure_step(values, {})["result"]
        assert result["gini"] == pytest.approx(0.0, abs=1e-6)
        assert result["welfare"] == pytest.approx(100.0, abs=1e-4)

    def test_sen_unequal(self):
        values = np.array([0.0, 0.0, 0.0, 0.0, 100.0])
        result = SenCapabilityEstimator.pure_step(values, {})["result"]
        assert result["gini"] > 0.5
        assert result["welfare"] < float(np.mean(values))


class TestStateDependentInverseSocialWeights:
    def test_inverse_weights_recovers_known_beta_two_regimes(self):
        x = np.linspace(0.0, 1.0, 6)
        basis_matrix = np.column_stack([np.ones_like(x), x, x**2])
        beta_true = np.array([1.0, -0.24, 0.04], dtype=float)
        state, weights_true = _make_inverse_problem(basis_matrix, beta_true)

        result = StateDependentInverseSocialWeightsEstimator.pure_step(
            state,
            {
                "normalization": "reference_cell",
                "reference_index": 0,
                "ridge": 1.0e-10,
                "smoothing": 1.0e-10,
                "damping": 1.0,
                "tol": 1.0e-10,
            },
        )["result"]

        assert result["converged"] is True
        assert result["identified_rank"] == basis_matrix.shape[1]
        assert np.asarray(result["coefficients"]) == pytest.approx(beta_true, abs=5.0e-4)
        assert np.asarray(result["weights_on_grid"]) == pytest.approx(weights_true, abs=5.0e-4)

    def test_single_regime_rank_deficiency_flagged(self):
        x = np.linspace(0.0, 1.0, 6)
        basis_matrix = np.column_stack([np.ones_like(x), x, 2.0 * x])
        beta_true = np.array([1.0, -0.1, -0.05], dtype=float)
        densities = np.array([[0.28, 0.21, 0.18, 0.14, 0.11, 0.08]], dtype=float)
        elasticities = np.array([[0.20, 0.22, 0.24, 0.26, 0.28, 0.30]], dtype=float)
        state, _ = _make_inverse_problem(
            basis_matrix,
            beta_true,
            densities=densities,
            elasticities=elasticities,
        )

        result = StateDependentInverseSocialWeightsEstimator.pure_step(
            state,
            {
                "normalization": "reference_cell",
                "reference_index": 0,
                "ridge": 1.0e-10,
                "smoothing": 1.0e-10,
            },
        )["result"]

        assert result["identified_rank"] < basis_matrix.shape[1]
        assert result["rank_deficient"] is True
        assert result["converged"] is False

    def test_social_weight_ref_deterministic(self):
        x = np.linspace(0.0, 1.0, 6)
        basis_matrix = np.column_stack([np.ones_like(x), x, x**2])
        beta_true = np.array([1.0, -0.24, 0.04], dtype=float)
        state, _ = _make_inverse_problem(basis_matrix, beta_true)
        params = {
            "normalization": "reference_cell",
            "reference_index": 0,
            "ridge": 1.0e-10,
            "smoothing": 1.0e-10,
        }

        result_a = StateDependentInverseSocialWeightsEstimator.pure_step(state, params)["result"]
        result_b = StateDependentInverseSocialWeightsEstimator.pure_step(state, params)["result"]

        assert result_a["social_weight_ref"] == result_b["social_weight_ref"]

    def test_social_weight_manifest_resolves_schedule(self):
        clear_social_weight_manifest_registry()
        x = np.linspace(0.0, 1.0, 6)
        basis_matrix = np.column_stack([np.ones_like(x), x, x**2])
        beta_true = np.array([1.0, -0.24, 0.04], dtype=float)
        state, _ = _make_inverse_problem(basis_matrix, beta_true)

        result = StateDependentInverseSocialWeightsEstimator.pure_step(
            state,
            {
                "normalization": "reference_cell",
                "reference_index": 0,
                "ridge": 1.0e-10,
                "smoothing": 1.0e-10,
            },
        )["result"]
        schedule = resolve_social_weight_schedule(result["social_weight_ref"])

        assert schedule is not None
        assert np.asarray(schedule["income_grid"]) == pytest.approx(state["income_grid"])
        assert np.asarray(schedule["weights_on_grid"]) == pytest.approx(result["weights_on_grid"])
        assert result["manifest"]["income_grid"] == pytest.approx(state["income_grid"])
        assert result["manifest"]["weights_on_grid"] == pytest.approx(result["weights_on_grid"])

    def test_social_weight_ref_changes_when_basis_changes(self):
        x = np.linspace(0.0, 1.0, 6)
        basis_a = np.column_stack([np.ones_like(x), x, x**2])
        basis_b = np.column_stack([np.ones_like(x), x, x**3])
        beta_true = np.array([1.0, -0.24, 0.04], dtype=float)
        state_a, _ = _make_inverse_problem(basis_a, beta_true)
        state_b, _ = _make_inverse_problem(basis_b, beta_true)
        params = {
            "normalization": "reference_cell",
            "reference_index": 0,
            "ridge": 1.0e-10,
            "smoothing": 1.0e-10,
        }

        result_a = StateDependentInverseSocialWeightsEstimator.pure_step(state_a, params)["result"]
        result_b = StateDependentInverseSocialWeightsEstimator.pure_step(state_b, params)["result"]

        assert result_a["social_weight_ref"] != result_b["social_weight_ref"]

    def test_weights_normalized_and_nonnegative(self):
        x = np.linspace(0.0, 1.0, 6)
        basis_matrix = np.column_stack([np.ones_like(x), x, x**2])
        beta_true = np.array([0.9, -0.15, 0.02], dtype=float)
        state, _ = _make_inverse_problem(basis_matrix, beta_true)

        result = StateDependentInverseSocialWeightsEstimator.pure_step(
            state,
            {
                "normalization": "mean_one",
                "ridge": 1.0e-10,
                "smoothing": 1.0e-10,
            },
        )["result"]

        densities = np.asarray(state["density"], dtype=float)
        mean_density = densities / densities.sum(axis=1, keepdims=True)
        mean_density = np.mean(mean_density, axis=0)
        weights = np.asarray(result["weights_on_grid"], dtype=float)

        assert np.min(weights) >= -1.0e-9
        assert float(np.dot(mean_density, weights)) == pytest.approx(1.0, abs=1.0e-8)

    def test_online_update_reduces_residual_norm(self):
        x = np.linspace(0.0, 1.0, 6)
        basis_matrix = np.column_stack([np.ones_like(x), x, x**2])
        beta_true = np.array([1.0, -0.20, 0.02], dtype=float)
        densities = np.array([[0.10, 0.12, 0.16, 0.18, 0.20, 0.24]], dtype=float)
        elasticities = np.array([[0.16, 0.18, 0.20, 0.22, 0.24, 0.26]], dtype=float)
        state, weights_true = _make_inverse_problem(
            basis_matrix,
            beta_true,
            densities=densities,
            elasticities=elasticities,
        )
        previous_coefficients = np.zeros(basis_matrix.shape[1], dtype=float)
        pre_update_norm = float(
            np.sqrt(
                np.sum(
                    (densities[0] / np.sum(densities[0]))
                    * (basis_matrix @ previous_coefficients - weights_true) ** 2
                )
            )
        )

        update_state = dict(state)
        update_state["previous_coefficients"] = previous_coefficients
        update_state["previous_precision"] = np.eye(basis_matrix.shape[1], dtype=float) * 10.0
        result = StateDependentInverseSocialWeightsEstimator.pure_step(
            update_state,
            {
                "solver_mode": "online",
                "normalization": "reference_cell",
                "reference_index": 0,
                "ridge": 1.0e-6,
                "smoothing": 1.0e-8,
            },
        )["result"]

        post_update_coefficients = np.asarray(result["coefficients"], dtype=float)
        post_update_norm = float(
            np.sqrt(
                np.sum(
                    (densities[0] / np.sum(densities[0]))
                    * (basis_matrix @ post_update_coefficients - weights_true) ** 2
                )
            )
        )

        assert post_update_norm < pre_update_norm

    def test_elasticity_sensitivity_envelope_reported(self):
        x = np.linspace(0.0, 1.0, 6)
        basis_matrix = np.column_stack([np.ones_like(x), x, x**2])
        beta_true = np.array([1.0, -0.22, 0.03], dtype=float)
        state, _ = _make_inverse_problem(basis_matrix, beta_true)

        result = StateDependentInverseSocialWeightsEstimator.pure_step(
            state,
            {
                "normalization": "reference_cell",
                "reference_index": 0,
            },
        )["result"]

        assert "sensitivity_to_elasticity_low" in result
        assert "sensitivity_to_elasticity_high" in result
        assert result["sensitivity_to_elasticity_low"] >= 0.0
        assert result["sensitivity_to_elasticity_high"] >= 0.0
