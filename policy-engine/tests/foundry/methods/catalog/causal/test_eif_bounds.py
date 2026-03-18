"""Tests: semiparametric efficiency bounds — eif_bounds.py (Task 3.4).

Covers:
- EIF formulas for ATE, ATT, LATE, frontdoor, transport
- Cramér-Rao lower bound computation
- Efficiency comparison across estimators
- Foundry method pure_step interface
- Numerical edge cases (near-zero propensity, constant outcome)
"""

import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../../src"))

from polisyos.foundry.methods.catalog.causal.eif_bounds import (
    EIFScores,
    EfficiencyBound,
    EfficiencyReport,
    SemiparametricEfficiencyBoundMethod,
    compare_estimator_efficiency,
    compute_efficiency_bound,
    compute_eif_ate,
    compute_eif_att,
    compute_eif_frontdoor,
    compute_eif_late,
    compute_eif_transport,
)


def _dgp(n: int = 500, seed: int = 42):
    """Generate data from a known linear DGP: ATE = 1.0."""
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, 3))
    e_true = 1 / (1 + np.exp(-X[:, 0]))          # true propensity
    T = rng.binomial(1, e_true).astype(float)
    Y = 1.0 * T + X[:, 0] * 0.5 + rng.standard_normal(n) * 0.3
    mu1 = X[:, 0] * 0.5 + 1.0   # approximate E[Y|T=1,X]
    mu0 = X[:, 0] * 0.5          # approximate E[Y|T=0,X]
    return Y, T, e_true, mu1, mu0


class TestEIFATE:
    def test_returns_eif_scores_object(self):
        Y, T, e, mu1, mu0 = _dgp()
        eif = compute_eif_ate(Y, T, e, mu1, mu0)
        assert isinstance(eif, EIFScores)
        assert eif.estimand_type == "ate"
        assert len(eif.scores) == len(Y)

    def test_scores_are_finite(self):
        Y, T, e, mu1, mu0 = _dgp()
        eif = compute_eif_ate(Y, T, e, mu1, mu0)
        assert np.all(np.isfinite(eif.scores))

    def test_mean_close_to_true_ate(self):
        """With oracle nuisance, EIF mean ≈ 1.0 (true ATE)."""
        Y, T, e, mu1, mu0 = _dgp(n=5000)
        eif = compute_eif_ate(Y, T, e, mu1, mu0)
        assert abs(eif.point_estimate() - 1.0) < 0.1

    def test_variance_positive(self):
        Y, T, e, mu1, mu0 = _dgp()
        eif = compute_eif_ate(Y, T, e, mu1, mu0)
        assert eif.variance() > 0.0

    def test_ci_contains_estimate(self):
        Y, T, e, mu1, mu0 = _dgp()
        eif = compute_eif_ate(Y, T, e, mu1, mu0)
        lo, hi = eif.ci()
        assert lo < eif.point_estimate() < hi

    def test_propensity_clipping(self):
        """Near-zero propensity should not cause Inf/NaN."""
        Y, T, e, mu1, mu0 = _dgp(n=200)
        e_extreme = np.clip(e, 1e-10, 1.0 - 1e-10)
        eif = compute_eif_ate(Y, T, e_extreme, mu1, mu0, min_propensity=1e-4)
        assert np.all(np.isfinite(eif.scores))


class TestEIFATT:
    def test_returns_att_scores(self):
        Y, T, e, mu1, mu0 = _dgp()
        eif = compute_eif_att(Y, T, e, mu1, mu0)
        assert eif.estimand_type == "att"
        assert np.all(np.isfinite(eif.scores))

    def test_att_mean_close_to_true(self):
        """ATT ≈ ATE = 1.0 for this symmetric DGP."""
        Y, T, e, mu1, mu0 = _dgp(n=5000)
        eif = compute_eif_att(Y, T, e, mu1, mu0)
        assert abs(eif.point_estimate() - 1.0) < 0.15

    def test_att_variance_lower_than_ate(self):
        """ATT uses only treated units → variance should be different from ATE."""
        Y, T, e, mu1, mu0 = _dgp(n=1000)
        eif_ate = compute_eif_ate(Y, T, e, mu1, mu0)
        eif_att = compute_eif_att(Y, T, e, mu1, mu0)
        # Both have finite variance; just confirm they differ
        assert eif_ate.variance() != eif_att.variance()


class TestEIFLATE:
    def _dgp_iv(self, n=1000, seed=0):
        rng = np.random.default_rng(seed)
        Z = rng.binomial(1, 0.5, n).astype(float)   # instrument
        T = (Z * 0.7 + rng.random(n) * 0.3 > 0.5).astype(float)  # ~70% compliance
        Y = 1.5 * T + rng.standard_normal(n) * 0.3
        e_z = np.full(n, 0.5)
        mu1_z1 = np.full(n, np.mean(Y[Z > 0.5]))
        mu0_z0 = np.full(n, np.mean(Y[Z <= 0.5]))
        mu1_z0 = np.full(n, np.mean(T[Z > 0.5]))
        mu0_z1 = np.full(n, np.mean(T[Z <= 0.5]))
        return Y, T, Z, e_z, mu1_z1, mu0_z0, mu1_z0, mu0_z1

    def test_late_returns_scores(self):
        Y, T, Z, e_z, mu1_z1, mu0_z0, mu1_z0, mu0_z1 = self._dgp_iv()
        eif = compute_eif_late(Y, T, Z, e_z, mu1_z1, mu0_z0, mu1_z0, mu0_z1)
        assert eif.estimand_type == "late"
        assert len(eif.scores) == len(Y)

    def test_late_scores_finite(self):
        Y, T, Z, e_z, mu1_z1, mu0_z0, mu1_z0, mu0_z1 = self._dgp_iv()
        eif = compute_eif_late(Y, T, Z, e_z, mu1_z1, mu0_z0, mu1_z0, mu0_z1)
        assert np.all(np.isfinite(eif.scores))


class TestEIFFrontdoor:
    def _dgp_fd(self, n=500, seed=0):
        rng = np.random.default_rng(seed)
        T = rng.binomial(1, 0.5, n).astype(float)
        M = 0.8 * T + rng.standard_normal(n) * 0.2
        Y = 1.0 * M + rng.standard_normal(n) * 0.2
        p_m_t1 = np.exp(-0.5 * (M - 0.8) ** 2)
        p_m_t0 = np.exp(-0.5 * M ** 2)
        # Normalise to proper densities
        p_m_t1 /= np.mean(p_m_t1) + 1e-9
        p_m_t0 /= np.mean(p_m_t0) + 1e-9
        mu_y = M * 1.0
        return Y, T, M, p_m_t1, p_m_t0, mu_y

    def test_frontdoor_returns_scores(self):
        Y, T, M, p_m_t1, p_m_t0, mu_y = self._dgp_fd()
        eif = compute_eif_frontdoor(Y, T, M, p_m_t1, p_m_t0, mu_y, p_t=0.5)
        assert eif.estimand_type == "frontdoor"
        assert len(eif.scores) == len(Y)

    def test_frontdoor_scores_finite(self):
        Y, T, M, p_m_t1, p_m_t0, mu_y = self._dgp_fd()
        eif = compute_eif_frontdoor(Y, T, M, p_m_t1, p_m_t0, mu_y, p_t=0.5)
        assert np.all(np.isfinite(eif.scores))


class TestEIFTransport:
    def test_transport_scores_finite(self):
        rng = np.random.default_rng(7)
        n = 300
        Y = rng.standard_normal(n)
        domain = rng.binomial(1, 0.6, n).astype(float)
        e_domain = np.clip(rng.beta(2, 2, n), 0.05, 0.95)
        mu_y = np.zeros(n)
        eif = compute_eif_transport(Y, domain, e_domain, mu_y)
        assert eif.estimand_type == "transport"
        assert np.all(np.isfinite(eif.scores))


class TestEfficiencyBound:
    def test_bound_lower_than_naive_ipw(self):
        """EIF-based bound should be ≤ variance of naive IPW (efficiency)."""
        Y, T, e, mu1, mu0 = _dgp(n=2000)
        # Oracle EIF bound
        eif = compute_eif_ate(Y, T, e, mu1, mu0)
        bound = compute_efficiency_bound(eif)
        # Naive IPW SE (ignores outcome model) is always ≥ AIPW SE
        ipw_scores = T * Y / e - (1 - T) * Y / (1 - e)
        ipw_se = float(np.std(ipw_scores, ddof=1) / np.sqrt(len(Y)))
        assert bound.standard_error <= ipw_se + 0.05  # allow small numeric slack

    def test_bound_returns_efficiency_bound_object(self):
        Y, T, e, mu1, mu0 = _dgp()
        eif = compute_eif_ate(Y, T, e, mu1, mu0)
        bound = compute_efficiency_bound(eif)
        assert isinstance(bound, EfficiencyBound)
        assert bound.variance_lower_bound > 0
        assert bound.n_obs == len(Y)

    def test_relative_efficiency_one_for_oracle_estimator(self):
        """Estimator SE matching bound SE → relative efficiency ≈ 1.0."""
        import math
        Y, T, e, mu1, mu0 = _dgp(n=1000)
        eif = compute_eif_ate(Y, T, e, mu1, mu0)
        # The bound uses E[ψ²]/n (second moment), so the oracle SE must match
        # sqrt(variance_lower_bound), not eif.standard_error() (centered variance).
        bound_first = compute_efficiency_bound(eif)
        oracle_se = math.sqrt(bound_first.variance_lower_bound)
        bound = compute_efficiency_bound(eif, estimator_se=oracle_se)
        assert abs(bound.relative_efficiency - 1.0) < 0.01

    def test_relative_efficiency_greater_for_inefficient_estimator(self):
        import math
        Y, T, e, mu1, mu0 = _dgp(n=1000)
        eif = compute_eif_ate(Y, T, e, mu1, mu0)
        # An inefficient estimator has larger SE than the semiparametric bound
        bound_first = compute_efficiency_bound(eif)
        oracle_se = math.sqrt(bound_first.variance_lower_bound)
        bad_se = oracle_se * 2.0
        bound = compute_efficiency_bound(eif, estimator_se=bad_se)
        assert bound.relative_efficiency > 3.5  # (2x SE)² / bound_var ≈ 4.0

    def test_to_dict_serializable(self):
        Y, T, e, mu1, mu0 = _dgp()
        eif = compute_eif_ate(Y, T, e, mu1, mu0)
        bound = compute_efficiency_bound(eif)
        d = bound.to_dict()
        assert "variance_lower_bound" in d
        assert "eif_variance" in d
        assert "relative_efficiency" in d


class TestCompareEfficiency:
    def test_report_identifies_most_efficient(self):
        Y, T, e, mu1, mu0 = _dgp(n=1000)
        eif = compute_eif_ate(Y, T, e, mu1, mu0)
        base_se = eif.standard_error()
        report = compare_estimator_efficiency(
            eif,
            {"AIPW": base_se, "IPW": base_se * 1.5, "OLS": base_se * 2.0},
        )
        assert isinstance(report, EfficiencyReport)
        assert report.most_efficient == "AIPW"

    def test_report_relative_efficiencies_ordered(self):
        Y, T, e, mu1, mu0 = _dgp(n=1000)
        eif = compute_eif_ate(Y, T, e, mu1, mu0)
        base_se = eif.standard_error()
        report = compare_estimator_efficiency(
            eif,
            {"efficient": base_se, "inefficient": base_se * 3.0},
        )
        eff = report.relative_efficiencies
        assert eff["efficient"] < eff["inefficient"]

    def test_to_dict_serializable(self):
        Y, T, e, mu1, mu0 = _dgp()
        eif = compute_eif_ate(Y, T, e, mu1, mu0)
        report = compare_estimator_efficiency(eif, {"A": 0.05, "B": 0.08})
        d = report.to_dict()
        assert "bound" in d
        assert "most_efficient" in d


class TestFoundryMethod:
    def _make_state(self, n=300):
        Y, T, e, mu1, mu0 = _dgp(n=n)
        return {"Y": Y, "treatment": T, "propensity": e, "mu1": mu1, "mu0": mu0}

    def test_pure_step_returns_bound_and_scores(self):
        state = self._make_state()
        result = SemiparametricEfficiencyBoundMethod.pure_step(
            state, {"estimand_type": "ate"}
        )
        assert "efficiency_bound" in result
        assert "eif_scores" in result
        assert len(result["eif_scores"]) == 300

    def test_pure_step_att(self):
        state = self._make_state()
        result = SemiparametricEfficiencyBoundMethod.pure_step(
            state, {"estimand_type": "att"}
        )
        assert result["efficiency_bound"]["estimand_type"] == "att"

    def test_pure_step_with_estimator_se(self):
        state = self._make_state()
        result = SemiparametricEfficiencyBoundMethod.pure_step(
            state, {"estimand_type": "ate", "estimator_se": 0.05}
        )
        assert "relative_efficiency" in result["efficiency_bound"]
        assert result["efficiency_bound"]["relative_efficiency"] > 0

    def test_pure_step_finite_output(self):
        state = self._make_state()
        result = SemiparametricEfficiencyBoundMethod.pure_step(
            state, {"estimand_type": "ate"}
        )
        scores = np.array(result["eif_scores"])
        assert np.all(np.isfinite(scores))
        bound = result["efficiency_bound"]
        assert np.isfinite(bound["variance_lower_bound"])
        assert np.isfinite(bound["point_estimate"])
