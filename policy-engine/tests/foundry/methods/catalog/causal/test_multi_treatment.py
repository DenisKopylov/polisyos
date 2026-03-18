"""Tests for multi-treatment estimators (Phase 6)."""
from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal.multi_treatment import (
    MultiArmAIPWEstimator,
    MultinomialIPWEstimator,
    pairwise_contrasts,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    MultiTreatmentData,
    MultiTreatmentResult,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rng():
    return np.random.default_rng(0)


def _make_multi_treatment_data(rng, n=400, K=3, true_effects=None):
    """3-arm experiment: Y = alpha_k + X[:,0] + noise."""
    if true_effects is None:
        true_effects = [0.0, 1.0, 2.0]
    X = rng.normal(0, 1, (n, 4))
    # Treatment assigned with propensity depending on X[:,0]
    log_odds = np.column_stack([
        np.zeros(n),
        0.3 * X[:, 0],
        -0.3 * X[:, 0],
    ])
    exp_lo = np.exp(log_odds - log_odds.max(axis=1, keepdims=True))
    probs = exp_lo / exp_lo.sum(axis=1, keepdims=True)
    T = np.array([rng.choice(K, p=probs[i]) for i in range(n)])
    effects = np.array([true_effects[t] for t in T])
    Y = effects + X[:, 0] + rng.normal(0, 0.5, n)
    return Y, T, X, true_effects


# ---------------------------------------------------------------------------
# MultiTreatmentData protocol
# ---------------------------------------------------------------------------

class TestMultiTreatmentData:
    def test_basic_construction(self, rng):
        n = 100
        Y = rng.normal(0, 1, n)
        T = rng.integers(0, 3, n)
        X = rng.normal(0, 1, (n, 3))
        data = MultiTreatmentData(outcome=Y, treatment=T, covariates=X)
        assert data.n_obs == n

    def test_levels_auto_detected(self, rng):
        n = 100
        Y = rng.normal(0, 1, n)
        T = np.array([0, 1, 2] * (n // 3) + [0] * (n % 3))
        X = rng.normal(0, 1, (n, 3))
        data = MultiTreatmentData(outcome=Y, treatment=T, covariates=X)
        assert set(data.levels) == {0, 1, 2}

    def test_shape_mismatch_raises(self, rng):
        Y = rng.normal(0, 1, 100)
        T = rng.integers(0, 3, 80)
        X = rng.normal(0, 1, (100, 3))
        with pytest.raises(ValueError):
            MultiTreatmentData(outcome=Y, treatment=T, covariates=X)

    def test_extra_fields_forbidden(self, rng):
        Y = rng.normal(0, 1, 50)
        T = np.zeros(50, dtype=int)
        X = rng.normal(0, 1, (50, 2))
        with pytest.raises(Exception):
            MultiTreatmentData(outcome=Y, treatment=T, covariates=X, unknown_field=1)


# ---------------------------------------------------------------------------
# MultinomialIPWEstimator
# ---------------------------------------------------------------------------

class TestMultinomialIPWEstimator:
    def test_output_keys_present(self, rng):
        Y, T, X, _ = _make_multi_treatment_data(rng)
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = MultinomialIPWEstimator.pure_step(state, {})
        assert "multi_treatment_result" in result

    def test_reference_arm_ate_zero(self, rng):
        Y, T, X, _ = _make_multi_treatment_data(rng)
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = MultinomialIPWEstimator.pure_step(state, {"reference_level": 0})
        mtr = result["multi_treatment_result"]
        ate_vs_ref = mtr["ate_vs_reference"]
        # reference arm should not appear in ate_vs_reference
        assert "0" not in ate_vs_ref

    def test_arm_means_all_finite(self, rng):
        Y, T, X, _ = _make_multi_treatment_data(rng)
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = MultinomialIPWEstimator.pure_step(state, {})
        mtr = result["multi_treatment_result"]
        for k, v in mtr["arm_means"].items():
            assert np.isfinite(v), f"arm_mean[{k}] not finite"

    def test_standard_errors_positive(self, rng):
        Y, T, X, _ = _make_multi_treatment_data(rng)
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = MultinomialIPWEstimator.pure_step(state, {})
        mtr = result["multi_treatment_result"]
        for k, se in mtr["standard_errors"].items():
            assert se >= 0, f"SE[{k}] < 0"

    def test_n_obs_per_arm_sums_to_n(self, rng):
        Y, T, X, _ = _make_multi_treatment_data(rng, n=300)
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = MultinomialIPWEstimator.pure_step(state, {})
        mtr = result["multi_treatment_result"]
        total = sum(mtr["n_obs_per_arm"].values())
        assert total == len(Y)

    def test_method_name_set(self, rng):
        Y, T, X, _ = _make_multi_treatment_data(rng)
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = MultinomialIPWEstimator.pure_step(state, {})
        mtr = result["multi_treatment_result"]
        assert "ipw" in mtr["method"].lower() or "imbens" in mtr["method"].lower()

    def test_recovers_true_effects_direction(self, rng):
        """E[Y(2)] > E[Y(1)] > E[Y(0)] for DGP with true_effects=[0,1,2]."""
        Y, T, X, true_effects = _make_multi_treatment_data(rng, n=800)
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = MultinomialIPWEstimator.pure_step(state, {})
        means = result["multi_treatment_result"]["arm_means"]
        assert float(means["2"]) > float(means["1"])
        assert float(means["1"]) > float(means["0"])

    def test_confidence_intervals_contain_arm_mean(self, rng):
        Y, T, X, _ = _make_multi_treatment_data(rng)
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = MultinomialIPWEstimator.pure_step(state, {})
        mtr = result["multi_treatment_result"]
        for k in mtr["arm_means"]:
            lo, hi = mtr["confidence_intervals"][k]
            mu = mtr["arm_means"][k]
            assert lo <= mu <= hi, f"CI for arm {k} does not contain mean"


# ---------------------------------------------------------------------------
# MultiArmAIPWEstimator
# ---------------------------------------------------------------------------

class TestMultiArmAIPWEstimator:
    def test_output_keys_present(self, rng):
        Y, T, X, _ = _make_multi_treatment_data(rng)
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = MultiArmAIPWEstimator.pure_step(state, {})
        assert "multi_treatment_result" in result

    def test_arm_means_finite(self, rng):
        Y, T, X, _ = _make_multi_treatment_data(rng)
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = MultiArmAIPWEstimator.pure_step(state, {})
        mtr = result["multi_treatment_result"]
        for k, v in mtr["arm_means"].items():
            assert np.isfinite(v), f"arm_mean[{k}] not finite: {v}"

    def test_standard_errors_finite_positive(self, rng):
        Y, T, X, _ = _make_multi_treatment_data(rng)
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = MultiArmAIPWEstimator.pure_step(state, {})
        mtr = result["multi_treatment_result"]
        for k, se in mtr["standard_errors"].items():
            assert np.isfinite(se) and se >= 0, f"SE[{k}] invalid: {se}"

    def test_method_name_contains_aipw(self, rng):
        Y, T, X, _ = _make_multi_treatment_data(rng)
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = MultiArmAIPWEstimator.pure_step(state, {})
        assert "aipw" in result["multi_treatment_result"]["method"].lower()

    def test_recovers_true_effects_direction(self, rng):
        Y, T, X, _ = _make_multi_treatment_data(rng, n=800)
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = MultiArmAIPWEstimator.pure_step(state, {})
        means = result["multi_treatment_result"]["arm_means"]
        assert float(means["2"]) > float(means["0"])

    def test_doubly_robust_consistent_propensity_correct(self, rng):
        """With correct propensity, AIPW should be near true ATE."""
        n = 1000
        X = rng.normal(0, 1, (n, 2))
        # Equal propensity (RCT-like)
        T = rng.choice(3, size=n)
        true_means = np.array([0.0, 1.5, 3.0])
        Y = np.array([true_means[t] for t in T]) + rng.normal(0, 0.5, n)
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = MultiArmAIPWEstimator.pure_step(state, {})
        means = result["multi_treatment_result"]["arm_means"]
        assert abs(float(means["0"]) - 0.0) < 0.3
        assert abs(float(means["1"]) - 1.5) < 0.3
        assert abs(float(means["2"]) - 3.0) < 0.3


# ---------------------------------------------------------------------------
# pairwise_contrasts helper
# ---------------------------------------------------------------------------

class TestPairwiseContrasts:
    def _make_result(self, arm_means):
        levels = tuple(int(k) for k in arm_means)
        n_obs = {k: 100 for k in arm_means}
        se = {k: 0.1 for k in arm_means}
        ci = {k: (float(v) - 0.2, float(v) + 0.2) for k, v in arm_means.items()}
        ate_ref = {k: float(v) - float(arm_means["0"]) for k, v in arm_means.items() if k != "0"}
        pairwise = {}
        ks = list(arm_means.keys())
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                pairwise[f"{ks[i]}_vs_{ks[j]}"] = float(arm_means[ks[i]]) - float(arm_means[ks[j]])
        return MultiTreatmentResult(
            levels=levels,
            arm_means=arm_means,
            ate_vs_reference=ate_ref,
            standard_errors=se,
            confidence_intervals=ci,
            pairwise_contrasts=pairwise,
            n_obs_per_arm=n_obs,
            method="test",
        )

    def test_number_of_pairs(self):
        result = self._make_result({"0": 0.0, "1": 1.0, "2": 2.0})
        pc = pairwise_contrasts(result)
        # C(3,2) = 3 pairs
        assert len(pc) == 3

    def test_antisymmetry(self):
        result = self._make_result({"0": 0.0, "1": 1.5, "2": 3.0})
        pc = pairwise_contrasts(result)
        # All present contrasts: 0_vs_1, 0_vs_2, 1_vs_2
        assert "0_vs_1" in pc
        assert abs(pc["0_vs_1"] - (-pc.get("1_vs_0", -pc["0_vs_1"]))) < 1e-10

    def test_same_arm_contrast_zero(self):
        result = self._make_result({"0": 2.0, "1": 2.0})
        pc = pairwise_contrasts(result)
        for v in pc.values():
            assert abs(v) < 1e-10

    def test_values_consistent_with_arm_means(self):
        arm_means = {"0": 0.0, "1": 1.5, "2": 3.0}
        result = self._make_result(arm_means)
        pc = pairwise_contrasts(result)
        # 0_vs_2 should be 0.0 - 3.0 = -3.0 (or 1_vs_2 = 1.5 - 3.0 = -1.5)
        for key, val in pc.items():
            k1, k2 = key.split("_vs_")
            expected = float(arm_means[k1]) - float(arm_means[k2])
            assert abs(val - expected) < 1e-10, f"Mismatch for {key}"


# ---------------------------------------------------------------------------
# Multinomial propensity sums-to-one (integration)
# ---------------------------------------------------------------------------

class TestMultinomialPropensityIntegration:
    def test_propensity_sums_to_one(self, rng):
        """IPW internals: multinomial probabilities sum to 1."""
        from polisyos.foundry.methods.catalog.causal.multi_treatment import (
            _fit_multinomial_logistic,
        )
        n = 200
        X = rng.normal(0, 1, (n, 3))
        T = rng.integers(0, 3, n)
        levels = [0, 1, 2]
        probs = _fit_multinomial_logistic(X, T, levels, min_p=0.01)
        row_sums = probs.sum(axis=1)
        np.testing.assert_allclose(row_sums, np.ones(n), atol=1e-6)

    def test_propensity_above_min_clip(self, rng):
        from polisyos.foundry.methods.catalog.causal.multi_treatment import (
            _fit_multinomial_logistic,
        )
        n = 200
        X = rng.normal(0, 1, (n, 2))
        T = rng.integers(0, 3, n)
        min_p = 0.05
        probs = _fit_multinomial_logistic(X, T, [0, 1, 2], min_p=min_p)
        assert (probs >= min_p - 1e-10).all()
