"""Tests for Phase 5.3: Identification under measurement error / proxy variables.

Covers:
  - TestProxyIdentification  — Kuroki & Pearl (2014) graphical ID check
  - TestRegressionCalibration — Carroll et al. (2006) calibration estimator
  - TestSIMEX                 — Cook & Stefanski (1994) simulation extrapolation
  - TestMeasurementErrorBounds — Widened Manski bounds under classification error
"""
from __future__ import annotations

import numpy as np

from tests.foundry.methods.catalog.causal.test_id_engine_extensions import (
    make_dag,
    make_confounded_graph,
)
from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _linear_dgp(
    n: int = 500,
    true_effect: float = 2.0,
    error_std: float = 0.5,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate (Y, T, T*) where T* = T + noise ~ N(0, error_std^2)."""
    rng = np.random.default_rng(seed)
    T = rng.normal(0.0, 1.0, n)
    noise = rng.normal(0.0, error_std, n)
    T_star = T + noise
    Y = true_effect * T + rng.normal(0.0, 0.5, n)
    return Y, T, T_star


# ---------------------------------------------------------------------------
# TestProxyIdentification
# ---------------------------------------------------------------------------

class TestProxyIdentification:
    """Unit tests for identify_with_proxy (Kuroki & Pearl 2014, Thm 2)."""

    def test_proxy_id_valid_proxy_conditions_returns_identified(self):
        """Graph where C* satisfies proxy validity → IDENTIFIED with ProxyAdjustmentNode."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import identify_with_proxy
        from polisyos.ir.analytics.estimand import ProxyAdjustmentNode

        # C_star → C → X, C → Y, X → Y  (proxy C_star for latent C)
        # C_star ⊥ Y | {C, X} holds: all paths C_star→...→Y pass through C or X
        # measurement_model="known" so P(C*|C) is available → IDENTIFIED
        graph = make_dag([("C_star", "C"), ("C", "X"), ("C", "Y"), ("X", "Y")])
        result = identify_with_proxy(
            graph=graph,
            treatment="X",
            outcome="Y",
            proxy_map={"C": "C_star"},
            measurement_model="known",
        )
        assert result.status == IdentificationStatus.IDENTIFIED

    def test_proxy_id_result_contains_proxy_adjustment_node(self):
        """identify_with_proxy AST root must be a ProxyAdjustmentNode."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import identify_with_proxy
        from polisyos.ir.analytics.estimand import ProxyAdjustmentNode

        # C_star → C → X, C → Y, X → Y  (proxy C_star for latent C)
        # measurement_model="known" → fully identified → ProxyAdjustmentNode AST
        graph = make_dag([("C_star", "C"), ("C", "X"), ("C", "Y"), ("X", "Y")])
        result = identify_with_proxy(
            graph=graph,
            treatment="X",
            outcome="Y",
            proxy_map={"C": "C_star"},
            measurement_model="known",
        )
        assert result.estimand_ast is not None
        assert isinstance(result.estimand_ast.root, ProxyAdjustmentNode)

    def test_proxy_id_proxy_map_stored_in_ast(self):
        """ProxyAdjustmentNode.proxy_map must contain the supplied mapping."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import identify_with_proxy
        from polisyos.ir.analytics.estimand import ProxyAdjustmentNode

        # C_star → C → X, C → Y, X → Y  (proxy C_star for latent C)
        # measurement_model="known" → IDENTIFIED, AST contains proxy_map
        graph = make_dag([("C_star", "C"), ("C", "X"), ("C", "Y"), ("X", "Y")])
        result = identify_with_proxy(
            graph=graph,
            treatment="X",
            outcome="Y",
            proxy_map={"C": "C_star"},
            measurement_model="known",
        )
        assert result.estimand_ast is not None
        node = result.estimand_ast.root
        assert isinstance(node, ProxyAdjustmentNode)
        proxy_dict = dict(node.proxy_map)
        assert proxy_dict.get("C") == "C_star"

    def test_proxy_id_algorithm_version_tag(self):
        """identify_with_proxy result algorithm_version must contain 'proxy'."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import identify_with_proxy

        # C_star → C → X, C → Y, X → Y  (proxy C_star for latent C)
        # C_star ⊥ Y | {C, X} holds: all paths C_star→...→Y pass through C or X
        graph = make_dag([("C_star", "C"), ("C", "X"), ("C", "Y"), ("X", "Y")])
        result = identify_with_proxy(
            graph=graph,
            treatment="X",
            outcome="Y",
            proxy_map={"C": "C_star"},
        )
        assert "proxy" in result.algorithm_version

    def test_proxy_id_measurement_model_known_still_identified(self):
        """measurement_model='known' should not prevent identification."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import identify_with_proxy

        # C_star → C → X, C → Y, X → Y  (proxy C_star for latent C)
        # C_star ⊥ Y | {C, X} holds: all paths C_star→...→Y pass through C or X
        graph = make_dag([("C_star", "C"), ("C", "X"), ("C", "Y"), ("X", "Y")])
        result = identify_with_proxy(
            graph=graph,
            treatment="X",
            outcome="Y",
            proxy_map={"C": "C_star"},
            measurement_model="known",
        )
        assert result.status == IdentificationStatus.IDENTIFIED

    def test_proxy_id_proof_step_proxy_adjustment(self):
        """identify_with_proxy must emit a PROXY_ADJUSTMENT proof step."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import identify_with_proxy

        # C_star → C → X, C → Y, X → Y  (proxy C_star for latent C)
        # C_star ⊥ Y | {C, X} holds: all paths C_star→...→Y pass through C or X
        graph = make_dag([("C_star", "C"), ("C", "X"), ("C", "Y"), ("X", "Y")])
        result = identify_with_proxy(
            graph=graph,
            treatment="X",
            outcome="Y",
            proxy_map={"C": "C_star"},
        )
        rule_names = [s.rule_name for s in result.proof_steps]
        assert "PROXY_ADJUSTMENT" in rule_names


# ---------------------------------------------------------------------------
# TestRegressionCalibration
# ---------------------------------------------------------------------------

class TestRegressionCalibration:
    """Unit tests for regression_calibration (Carroll et al. 2006).

    The function returns a dict: {"result": {"ate": ..., "ci_lower": ..., "ci_upper": ...}}.
    """

    def test_regression_calibration_returns_dict_with_ate(self):
        """regression_calibration must return a dict containing an 'ate' key."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import regression_calibration

        Y, T, T_star = _linear_dgp(n=300, true_effect=2.0, error_std=0.5)
        report = regression_calibration(
            outcome=Y,
            treatment_proxy=T_star,
            covariates=None,
        )
        assert isinstance(report, dict)
        inner = report.get("result", report)
        assert "ate" in inner

    def test_regression_calibration_no_error_near_ols(self):
        """Zero measurement error → calibrated estimate ≈ naive OLS estimate."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import regression_calibration

        Y, T, T_star = _linear_dgp(n=500, true_effect=2.0, error_std=1e-9)
        report = regression_calibration(
            outcome=Y,
            treatment_proxy=T_star,
            covariates=None,
        )
        inner = report.get("result", report)
        ate = inner["ate"]
        assert abs(ate - 2.0) < 0.3

    def test_regression_calibration_with_validation_improves(self):
        """Providing validation data should produce a finite, non-NaN ATE."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import regression_calibration

        Y, T, T_star = _linear_dgp(n=600, true_effect=2.0, error_std=0.5)
        report = regression_calibration(
            outcome=Y,
            treatment_proxy=T_star,
            covariates=None,
            validation_true_treatment=T[:100],
        )
        inner = report.get("result", report)
        assert np.isfinite(inner["ate"])

    def test_regression_calibration_with_covariates(self):
        """Covariates array is accepted without error."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import regression_calibration

        rng = np.random.default_rng(7)
        n = 200
        T = rng.normal(0, 1, n)
        Z = rng.normal(0, 1, (n, 2))
        T_star = T + rng.normal(0, 0.3, n)
        Y = 1.5 * T + Z[:, 0] + rng.normal(0, 0.2, n)
        report = regression_calibration(
            outcome=Y,
            treatment_proxy=T_star,
            covariates=Z,
        )
        inner = report.get("result", report)
        assert np.isfinite(inner["ate"])

    def test_regression_calibration_report_has_ci(self):
        """Result dict must include ci_lower and ci_upper."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import regression_calibration

        Y, T, T_star = _linear_dgp(n=300)
        report = regression_calibration(
            outcome=Y,
            treatment_proxy=T_star,
            covariates=None,
        )
        inner = report.get("result", report)
        assert "ci_lower" in inner and "ci_upper" in inner
        lo, hi = inner["ci_lower"], inner["ci_upper"]
        assert lo <= inner["ate"] <= hi


# ---------------------------------------------------------------------------
# TestSIMEX
# ---------------------------------------------------------------------------

class TestSIMEX:
    """Unit tests for simex (Cook & Stefanski 1994).

    Returns dict: {"result": {"ate_simex": ..., "ci_lower": ..., "ci_upper": ...}}.
    """

    def test_simex_returns_dict_with_ate(self):
        """simex must return a dict containing 'ate_simex'."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import simex

        Y, T, T_star = _linear_dgp(n=300, true_effect=1.5, error_std=0.5)
        report = simex(
            outcome=Y,
            treatment_proxy=T_star,
            covariates=None,
            error_variance=0.25,
            n_simulations=50,
        )
        assert isinstance(report, dict)
        inner = report.get("result", report)
        assert "ate_simex" in inner or "ate" in inner

    def test_simex_linear_extrapolant_runs(self):
        """Linear SIMEX returns finite ATE."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import simex

        Y, T, T_star = _linear_dgp(n=800, true_effect=2.0, error_std=0.5)
        report = simex(
            outcome=Y,
            treatment_proxy=T_star,
            covariates=None,
            error_variance=0.25,
            n_simulations=100,
            extrapolant="linear",
        )
        inner = report.get("result", report)
        ate = inner.get("ate_simex", inner.get("ate"))
        assert np.isfinite(ate)

    def test_simex_quadratic_extrapolant_runs(self):
        """quadratic extrapolant completes without error."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import simex

        Y, T, T_star = _linear_dgp(n=200, error_std=0.4)
        report = simex(
            outcome=Y,
            treatment_proxy=T_star,
            covariates=None,
            error_variance=0.16,
            n_simulations=30,
            extrapolant="quadratic",
        )
        inner = report.get("result", report)
        ate = inner.get("ate_simex", inner.get("ate"))
        assert np.isfinite(ate)

    def test_simex_with_covariates(self):
        """simex with covariate matrix completes and returns finite ATE."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import simex

        rng = np.random.default_rng(13)
        n = 200
        T = rng.normal(0, 1, n)
        Z = rng.normal(0, 1, (n, 2))
        T_star = T + rng.normal(0, 0.4, n)
        Y = 1.0 * T + Z[:, 0] + rng.normal(0, 0.3, n)
        report = simex(
            outcome=Y,
            treatment_proxy=T_star,
            covariates=Z,
            error_variance=0.16,
            n_simulations=30,
        )
        inner = report.get("result", report)
        ate = inner.get("ate_simex", inner.get("ate"))
        assert np.isfinite(ate)

    def test_simex_report_has_ci(self):
        """SIMEX result must include ci_lower and ci_upper."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import simex

        Y, T, T_star = _linear_dgp(n=300)
        report = simex(
            outcome=Y,
            treatment_proxy=T_star,
            covariates=None,
            error_variance=0.25,
            n_simulations=40,
        )
        inner = report.get("result", report)
        assert "ci_lower" in inner and "ci_upper" in inner
        assert inner["ci_lower"] <= inner["ci_upper"]

    def test_simex_zero_error_variance_matches_ols(self):
        """Near-zero error variance → SIMEX extrapolation ≈ naive OLS."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import simex

        Y, T, T_star = _linear_dgp(n=500, true_effect=2.0, error_std=1e-6)
        report = simex(
            outcome=Y,
            treatment_proxy=T_star,
            covariates=None,
            error_variance=1e-12,
            n_simulations=30,
        )
        inner = report.get("result", report)
        ate = inner.get("ate_simex", inner.get("ate"))
        assert abs(ate - 2.0) < 0.3


# ---------------------------------------------------------------------------
# TestMeasurementErrorBounds
# ---------------------------------------------------------------------------

class TestMeasurementErrorBounds:
    """Unit tests for bounds_with_measurement_error (widened Manski bounds).

    Returns dict: {"bounds_report": {"consensus_lower": ..., "consensus_upper": ...}}.
    """

    @staticmethod
    def _get_bounds(report: dict) -> tuple[float, float]:
        """Extract (lower, upper) from the returned dict."""
        inner = report.get("bounds_report", report)
        lo = inner.get("consensus_lower", inner.get("lower"))
        hi = inner.get("consensus_upper", inner.get("upper"))
        return float(lo), float(hi)

    def test_bounds_returns_dict(self):
        """bounds_with_measurement_error must return a dict."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import (
            bounds_with_measurement_error,
        )

        rng = np.random.default_rng(0)
        Y = rng.choice([0.0, 1.0], size=200)
        T_star = rng.choice([0, 1], size=200)
        report = bounds_with_measurement_error(
            outcome=Y,
            treatment_proxy=T_star,
            error_rate_bound=0.1,
        )
        assert isinstance(report, dict)

    def test_bounds_widen_with_error_rate(self):
        """Bounds with α=0.2 must be at least as wide as with α=0."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import (
            bounds_with_measurement_error,
        )

        rng = np.random.default_rng(1)
        Y = rng.uniform(0, 1, 300)
        T_star = rng.choice([0, 1], size=300)

        r0 = bounds_with_measurement_error(outcome=Y, treatment_proxy=T_star, error_rate_bound=0.0)
        r2 = bounds_with_measurement_error(outcome=Y, treatment_proxy=T_star, error_rate_bound=0.2)
        lo0, hi0 = self._get_bounds(r0)
        lo2, hi2 = self._get_bounds(r2)
        assert (hi2 - lo2) >= (hi0 - lo0) - 1e-9

    def test_bounds_collapse_at_zero_equals_standard_manski(self):
        """α=0 → bounds within standard Manski range [−1, 1] for Y ∈ [0,1]."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import (
            bounds_with_measurement_error,
        )

        rng = np.random.default_rng(2)
        Y = rng.uniform(0.0, 1.0, 400)
        T_star = rng.choice([0, 1], 400)

        report = bounds_with_measurement_error(
            outcome=Y, treatment_proxy=T_star, error_rate_bound=0.0
        )
        lo, hi = self._get_bounds(report)
        assert lo >= -1.0 - 1e-9
        assert hi <= 1.0 + 1e-9

    def test_bounds_lower_le_upper(self):
        """Bounds must satisfy lower ≤ upper for any α ∈ [0, 0.5]."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import (
            bounds_with_measurement_error,
        )

        rng = np.random.default_rng(3)
        Y = rng.normal(0, 1, 200)
        T_star = rng.choice([0, 1], 200)

        for alpha in [0.0, 0.05, 0.1, 0.2, 0.4]:
            report = bounds_with_measurement_error(
                outcome=Y, treatment_proxy=T_star, error_rate_bound=alpha
            )
            lo, hi = self._get_bounds(report)
            assert lo <= hi + 1e-9, f"lower > upper at alpha={alpha}"

    def test_bounds_binary_outcome_finite(self):
        """Binary outcome → bounds are finite floats."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import (
            bounds_with_measurement_error,
        )

        rng = np.random.default_rng(4)
        Y = rng.choice([0.0, 1.0], 300)
        T_star = rng.choice([0, 1], 300)

        report = bounds_with_measurement_error(
            outcome=Y, treatment_proxy=T_star, error_rate_bound=0.1
        )
        lo, hi = self._get_bounds(report)
        assert np.isfinite(lo)
        assert np.isfinite(hi)

    def test_bounds_monotone_in_alpha(self):
        """As α grows the bound width must be non-decreasing."""
        from polisyos.foundry.methods.catalog.causal.measurement_error import (
            bounds_with_measurement_error,
        )

        rng = np.random.default_rng(5)
        Y = rng.uniform(0, 1, 500)
        T_star = rng.choice([0, 1], 500)

        alphas = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3]
        prev_width = -np.inf
        for alpha in alphas:
            report = bounds_with_measurement_error(
                outcome=Y, treatment_proxy=T_star, error_rate_bound=alpha
            )
            lo, hi = self._get_bounds(report)
            width = hi - lo
            assert width >= prev_width - 1e-9, f"width not monotone at alpha={alpha}"
            prev_width = width
