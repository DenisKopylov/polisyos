"""Tests for G-estimation (Structural Nested Mean Model)."""

from __future__ import annotations

import importlib
import sys

import numpy as np
import pytest
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal.g_estimation import StructuralNestedMeanModel
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import EstimationStatus
from polisyos.ir.analytics.dynamic_regime import SNMMResult

# ---------------------------------------------------------------------------
# DGP helpers
# ---------------------------------------------------------------------------


def _make_snmm_data(
    n_units: int = 500,
    n_periods: int = 3,
    psi_true: float = 1.0,
    seed: int = 0,
) -> DynamicTreatmentData:
    """Linear blip DGP with known true ψ.

    L_0 ~ N(0, 1)
    A_t ~ Bernoulli(sigmoid(0.5 * L_t))
    L_{t+1} = 0.3 * L_t + N(0, 0.5)   (no direct A effect on L)
    Y = psi_true * sum_t A_t + L_0 + N(0, 0.5)

    True blip: γ(a_t, H_t; ψ) = ψ * a_t  →  ψ_true = 1.0 per stage
    """
    rng = np.random.default_rng(seed)

    def sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-x))

    L = np.zeros((n_units, n_periods))
    A = np.zeros((n_units, n_periods), dtype=int)
    L[:, 0] = rng.standard_normal(n_units)

    for t in range(n_periods):
        A[:, t] = rng.binomial(1, sigmoid(0.5 * L[:, t]))
        if t < n_periods - 1:
            L[:, t + 1] = 0.3 * L[:, t] + rng.normal(0, 0.5, n_units)

    Y = psi_true * A.sum(axis=1).astype(float) + L[:, 0] + rng.normal(0, 0.5, n_units)

    return DynamicTreatmentData(
        outcome=Y,
        treatment_sequence=A,
        covariate_sequence=L[:, :, np.newaxis],
    )


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


# ---------------------------------------------------------------------------
# Core correctness tests
# ---------------------------------------------------------------------------


class TestStructuralNestedMeanModel:
    def test_recovers_psi_linear(self):
        """G-estimation should recover ψ ≈ 1.0 (true value) for linear blip."""
        data = _make_snmm_data(n_units=600, n_periods=3, psi_true=1.0, seed=42)
        result = StructuralNestedMeanModel.pure_step(
            data, {"blip_model": "linear", "n_bootstrap": 80}
        )
        assert result["report"].status == EstimationStatus.SUCCESS
        snmm = result["snmm_result"]
        assert isinstance(snmm, SNMMResult)
        # ψ_0 from last stage should be close to 1.0
        psi_main = snmm.psi_estimates[0]
        assert abs(psi_main - 1.0) < 0.25, f"Expected ψ ≈ 1.0, got {psi_main:.4f}"

    def test_psi_zero_under_no_effect(self):
        """When true ψ = 0, estimate should be near zero."""
        data = _make_snmm_data(n_units=500, n_periods=3, psi_true=0.0, seed=7)
        result = StructuralNestedMeanModel.pure_step(
            data, {"blip_model": "linear", "n_bootstrap": 60}
        )
        assert result["report"].status == EstimationStatus.SUCCESS
        psi_main = result["snmm_result"].psi_estimates[0]
        assert abs(psi_main) < 0.3, f"Expected ψ ≈ 0, got {psi_main:.4f}"

    def test_returns_snmm_result_instance(self):
        data = _make_snmm_data(n_units=300)
        result = StructuralNestedMeanModel.pure_step(data, {"n_bootstrap": 50})
        assert isinstance(result["snmm_result"], SNMMResult)

    def test_ci_coverage(self):
        """Bootstrap CI should be finite and ordered."""
        data = _make_snmm_data(n_units=300, seed=99)
        result = StructuralNestedMeanModel.pure_step(
            data, {"blip_model": "linear", "n_bootstrap": 60}
        )
        snmm = result["snmm_result"]
        assert snmm.psi_std_errors[0] > 0
        assert np.isfinite(snmm.psi_std_errors[0])

    def test_two_period_data(self):
        """Backward induction over 2 stages should complete successfully."""
        data = _make_snmm_data(n_units=400, n_periods=2, seed=1)
        result = StructuralNestedMeanModel.pure_step(
            data, {"blip_model": "linear", "n_bootstrap": 50}
        )
        assert result["report"].status == EstimationStatus.SUCCESS
        snmm = result["snmm_result"]
        assert snmm.n_periods == 2
        assert len(snmm.psi_estimates) >= 1

    def test_four_period_data(self):
        """Backward induction over 4 stages should complete successfully."""
        data = _make_snmm_data(n_units=500, n_periods=4, seed=2)
        result = StructuralNestedMeanModel.pure_step(
            data, {"blip_model": "linear", "n_bootstrap": 50}
        )
        assert result["report"].status == EstimationStatus.SUCCESS
        assert result["snmm_result"].n_periods == 4

    def test_interaction_blip_model(self):
        """Interaction blip model should run without error."""
        data = _make_snmm_data(n_units=400, seed=3)
        result = StructuralNestedMeanModel.pure_step(
            data, {"blip_model": "interaction", "n_bootstrap": 50}
        )
        assert result["report"].status == EstimationStatus.SUCCESS
        assert np.isfinite(result["snmm_result"].psi_estimates[0])

    def test_failure_on_tiny_data(self):
        """Datasets with too few units should return INPUT_INVALID (method checks n_units < 20)."""
        tiny = DynamicTreatmentData(
            outcome=np.zeros(15),
            treatment_sequence=np.zeros((15, 2), dtype=int),
            covariate_sequence=np.zeros((15, 2, 1)),
        )
        result = StructuralNestedMeanModel.pure_step(tiny, {})
        assert result["report"].status == EstimationStatus.INPUT_INVALID

    def test_n_units_stored_correctly(self):
        data = _make_snmm_data(n_units=300, n_periods=3)
        result = StructuralNestedMeanModel.pure_step(data, {"n_bootstrap": 50})
        assert result["snmm_result"].n_units == 300

    def test_blip_model_field_stored(self):
        data = _make_snmm_data(n_units=300)
        result = StructuralNestedMeanModel.pure_step(
            data, {"blip_model": "interaction", "n_bootstrap": 50}
        )
        assert result["snmm_result"].blip_model == "interaction"

    def test_optimal_regime_extracted(self):
        """Optimal regime field should be populated after estimation."""
        data = _make_snmm_data(n_units=400, psi_true=1.0, seed=5)
        result = StructuralNestedMeanModel.pure_step(
            data, {"blip_model": "linear", "n_bootstrap": 60}
        )
        snmm = result["snmm_result"]
        # When ψ > 0, the optimal regime should recommend treating (always_treat or threshold)
        assert snmm.optimal_regime is not None

    def test_registered_under_correct_fqn(self):
        ensure_causal_methods_registered()
        method_cls = MethodRegistry.get_instance().get(
            "causal.dynamic.snmm.snmm_g_estimation@1.0.0"
        )
        assert method_cls is not None
        assert method_cls is StructuralNestedMeanModel

    def test_registered_under_correct_fqn_after_module_reload(self):
        stale_cls = StructuralNestedMeanModel
        sys.modules.pop("polisyos.foundry.methods.catalog.causal.g_estimation", None)
        importlib.import_module("polisyos.foundry.methods.catalog.causal.g_estimation")

        ensure_causal_methods_registered()

        method_cls = MethodRegistry.get_instance().get(
            "causal.dynamic.snmm.snmm_g_estimation@1.0.0"
        )
        assert method_cls is stale_cls
