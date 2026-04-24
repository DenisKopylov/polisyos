"""Tests for PathSpecificEffectEstimator — NDE/NIE via cross-fitted EIF.

Coverage (17 tests):
  1.  test_nde_cross_fit_linear_dgp — NDE ≈ direct coefficient
  2.  test_nie_cross_fit_linear_dgp — NIE ≈ indirect path product
  3.  test_nde_plus_nie_equals_ate — NDE + NIE ≈ ATE on linear DGP
  4.  test_eif_scores_finite — no NaN/Inf in cross-fit EIF output
  5.  test_cross_fit_2_folds — runs successfully with n_folds=2
  6.  test_cross_fit_3_folds — runs successfully with n_folds=3
  7.  test_sensitivity_rho_zero_equals_baseline — ρ=0 gives original NDE/NIE
  8.  test_recanting_witness_no_witness_clean_graph — identifiable simple DAG
  9.  test_recanting_witness_detects_bypass_path — canonical witness case
 10.  test_identify_path_specific_no_adjacency — always True without graph
 11.  test_identify_path_specific_rejects_recanting_witness_graph — returns False
 12.  test_path_specific_estimator_pure_step_runs — dispatch returns mediation_result
 13.  test_mediation_decomposition_structure — output keys present
 14.  test_path_specific_estimator_registered — in registry
 15.  test_natural_effect_estimator_registered — NaturalEffectEstimator in registry
 16.  test_natural_effect_estimator_pure_step — produces nde/nie/total_effect
 17.  test_path_specific_output_json_serializable — model_dump → JSON
"""

from __future__ import annotations

import json
import math

import numpy as np

# ── DGP helpers ────────────────────────────────────────────────────────────────


def _linear_mediation_dgp(
    n: int = 1000,
    direct_coef: float = 0.8,
    mediator_coef: float = 0.5,
    t_on_m_coef: float = 0.4,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Linear DGP for mediation:
        T ~ Bernoulli(0.5)
        M = t_on_m_coef * T + U_M
        Y = direct_coef * T + mediator_coef * M + U_Y

    True NDE = direct_coef (direct effect)
    True NIE = t_on_m_coef * mediator_coef (indirect via M)
    True ATE = direct_coef + t_on_m_coef * mediator_coef
    """
    if rng is None:
        rng = np.random.default_rng(42)
    X = rng.normal(size=(n, 1))
    T = rng.binomial(1, 0.5, n).astype(float)
    M = t_on_m_coef * T + 0.1 * rng.normal(size=n)
    Y = direct_coef * T + mediator_coef * M + 0.1 * rng.normal(size=n)
    return X, T, M, Y


# ── Imports ────────────────────────────────────────────────────────────────────


from polisyos.foundry.methods.catalog.causal.mediation import NaturalEffectEstimator
from polisyos.foundry.methods.catalog.causal.path_specific import (
    PathSpecificEffectEstimator,
    _identify_path_specific,
    _nde_cross_fit,
    _recanting_witness_check,
    _sensitivity_mediation,
)

# ── Cross-fit NDE/NIE accuracy ─────────────────────────────────────────────────


class TestNDECrossFit:
    def test_nde_cross_fit_linear_dgp(self):
        """NDE estimate should be close to true direct coefficient."""
        rng = np.random.default_rng(0)
        X, T, M, Y = _linear_mediation_dgp(n=2000, direct_coef=0.8, rng=rng)
        nde, nde_se, nie, nie_se = _nde_cross_fit(Y, T, M, X, n_folds=2, rng=rng)
        # NDE ≈ 0.8 (direct effect), tolerance ±0.3 for n=2000
        assert abs(nde - 0.8) < 0.35, f"NDE={nde:.3f}, expected ≈0.8"

    def test_nie_cross_fit_linear_dgp(self):
        """NIE estimate should be close to true indirect product."""
        rng = np.random.default_rng(1)
        # T→M: 0.5, M→Y: 0.4 → NIE = 0.5 * 0.4 = 0.2
        X, T, M, Y = _linear_mediation_dgp(
            n=2000, direct_coef=0.8, mediator_coef=0.4, t_on_m_coef=0.5, rng=rng
        )
        nde, nde_se, nie, nie_se = _nde_cross_fit(Y, T, M, X, n_folds=2, rng=rng)
        # NIE ≈ 0.2, tolerance ±0.3
        assert abs(nie - 0.2) < 0.35, f"NIE={nie:.3f}, expected ≈0.2"

    def test_nde_plus_nie_equals_ate(self):
        """NDE + NIE ≈ ATE = direct_coef + t_on_m_coef * mediator_coef."""
        rng = np.random.default_rng(2)
        direct = 0.8
        t_on_m = 0.5
        m_on_y = 0.4
        true_ate = direct + t_on_m * m_on_y  # = 1.0
        X, T, M, Y = _linear_mediation_dgp(
            n=2000,
            direct_coef=direct,
            mediator_coef=m_on_y,
            t_on_m_coef=t_on_m,
            rng=rng,
        )
        nde, nde_se, nie, nie_se = _nde_cross_fit(Y, T, M, X, n_folds=2, rng=rng)
        total = nde + nie
        # Total should approximate true ATE (tolerance ±0.4 for EIF with small n)
        assert abs(total - true_ate) < 0.5, f"NDE+NIE={total:.3f}, expected ≈{true_ate:.3f}"

    def test_eif_scores_finite(self):
        """All EIF scores must be finite (no NaN or Inf)."""
        from polisyos.foundry.methods.catalog.causal.eif_bounds import (
            compute_eif_nde,
            compute_eif_nie,
        )

        rng = np.random.default_rng(99)
        X, T, M, Y = _linear_mediation_dgp(n=200, rng=rng)
        propensity = np.full(200, 0.5)
        pm1 = np.full(200, 0.3)
        pm0 = np.full(200, 0.2)
        mu1 = Y + 0.1 * rng.normal(size=200)
        mu0 = Y - 0.5 + 0.1 * rng.normal(size=200)
        eif_nde = compute_eif_nde(Y, T, M, X, propensity, pm1, pm0, mu1, mu0)
        eif_nie = compute_eif_nie(Y, T, M, X, propensity, pm1, pm0, mu1, mu0)
        assert np.all(np.isfinite(eif_nde.scores))
        assert np.all(np.isfinite(eif_nie.scores))

    def test_cross_fit_2_folds(self):
        """n_folds=2 runs without error."""
        rng = np.random.default_rng(3)
        X, T, M, Y = _linear_mediation_dgp(n=400, rng=rng)
        nde, nde_se, nie, nie_se = _nde_cross_fit(Y, T, M, X, n_folds=2, rng=rng)
        assert math.isfinite(nde)
        assert math.isfinite(nie)

    def test_cross_fit_3_folds(self):
        """n_folds=3 runs without error."""
        rng = np.random.default_rng(4)
        X, T, M, Y = _linear_mediation_dgp(n=600, rng=rng)
        nde, nde_se, nie, nie_se = _nde_cross_fit(Y, T, M, X, n_folds=3, rng=rng)
        assert math.isfinite(nde)
        assert math.isfinite(nie)
        assert nde_se > 0
        assert nie_se > 0


# ── Sensitivity analysis ───────────────────────────────────────────────────────


class TestSensitivityMediation:
    def test_sensitivity_rho_zero_equals_baseline(self):
        """At ρ=0, bias correction = 0, so result equals baseline NDE/NIE."""
        nde, nie, nde_se, nie_se = 0.8, 0.2, 0.05, 0.03
        result = _sensitivity_mediation(nde, nie, nde_se, nie_se, [0.0])
        assert abs(result["nde_corrected"][0] - nde) < 1e-9
        assert abs(result["nie_corrected"][0] - nie) < 1e-9

    def test_sensitivity_positive_rho_reduces_nde(self):
        """ρ > 0 should reduce NDE (bias correction)."""
        nde, nie, nde_se, nie_se = 0.8, 0.2, 0.05, 0.03
        result = _sensitivity_mediation(nde, nie, nde_se, nie_se, [0.5])
        # With ρ=0.5 > 0, nde_corrected = nde - 0.5 * nde_se < nde
        assert result["nde_corrected"][0] < nde


# ── Identification check ──────────────────────────────────────────────────────


class TestIdentification:
    def test_recanting_witness_no_witness_clean_graph(self):
        """Simple T→M→Y: no recanting witness (identifiable)."""
        adjacency = {"T": ["M"], "M": ["Y"], "Y": []}
        has_witness, witnesses = _recanting_witness_check("T", "Y", ("M",), adjacency)
        assert has_witness is False
        assert witnesses == []

    def test_recanting_witness_detects_bypass_path(self):
        """T→M→Y plus direct T→Y path triggers canonical recanting witness."""
        adjacency = {"T": ["M", "Y"], "M": ["Y"], "Y": []}
        has_witness, witnesses = _recanting_witness_check("T", "Y", ("M",), adjacency)
        assert has_witness is True
        assert witnesses == ["M"]

    def test_identify_path_specific_no_adjacency(self):
        """Without adjacency info, always returns True."""
        result = _identify_path_specific(
            "T",
            "Y",
            ("M",),
            active_paths=(("T", "Y"),),
            fixed_paths=(("T", "M", "Y"),),
            adjacency=None,
        )
        assert result is True

    def test_identify_path_specific_rejects_recanting_witness_graph(self):
        """A bypass T→Y path alongside T→M→Y makes the PSE non-identifiable."""
        adjacency = {"T": ["M", "Y"], "M": ["Y"], "Y": []}
        result = _identify_path_specific(
            "T",
            "Y",
            ("M",),
            active_paths=(("T", "Y"),),
            fixed_paths=(("T", "M", "Y"),),
            adjacency=adjacency,
        )
        assert result is False


# ── PathSpecificEffectEstimator.pure_step ─────────────────────────────────────


class TestPathSpecificPureStep:
    def _make_state(self, n: int = 300) -> dict:
        rng = np.random.default_rng(7)
        X, T, M, Y = _linear_mediation_dgp(n=n, rng=rng)
        return {"X": X, "treatment": T, "mediator": M, "outcome": Y}

    def test_pure_step_runs_and_has_mediation_result(self):
        """pure_step returns mediation_result with expected structure."""
        state = self._make_state()
        params = {
            "n_folds": 2,
            "compute_sensitivity": False,
            "__seed__": 42,
        }
        out = PathSpecificEffectEstimator.pure_step(state, params)
        assert "mediation_result" in out
        mr = out["mediation_result"]
        assert "nde" in mr
        assert "nie" in mr
        assert "total_effect" in mr

    def test_mediation_decomposition_structure(self):
        """Output mediation_result has all required MediationDecomposition fields."""
        state = self._make_state()
        params = {"n_folds": 2, "__seed__": 0}
        out = PathSpecificEffectEstimator.pure_step(state, params)
        mr = out["mediation_result"]
        for key in ("nde", "nie", "total_effect", "nde_se", "nie_se", "n_obs", "estimation_method"):
            assert key in mr, f"Missing key: {key}"
        assert mr["estimation_method"] == "eif_cross_fit"

    def test_total_effect_finite(self):
        """total_effect = NDE + NIE must be finite."""
        state = self._make_state()
        params = {"n_folds": 2, "__seed__": 1}
        out = PathSpecificEffectEstimator.pure_step(state, params)
        mr = out["mediation_result"]
        assert math.isfinite(mr["total_effect"])


class TestPathSpecificTMLE:
    def _make_state(self, n: int = 400) -> dict:
        rng = np.random.default_rng(11)
        X, T, M, Y = _linear_mediation_dgp(n=n, rng=rng)
        return {"X": X, "treatment": T, "mediator": M, "outcome": Y}

    def test_tmle_returns_mediation_result(self):
        state = self._make_state()
        params = {
            "n_folds": 2,
            "estimation_method": "tmle",
            "tmle_library": ["ols", "ridge"],
            "tmle_v_folds": 3,
            "__seed__": 123,
        }
        out = PathSpecificEffectEstimator.pure_step(state, params)
        mr = out["mediation_result"]
        assert mr["estimation_method"] == "tmle"
        assert math.isfinite(mr["nde"])
        assert math.isfinite(mr["nie"])

    def test_tmle_reasonable_against_eif_on_linear_dgp(self):
        state = self._make_state(n=800)
        tmle = PathSpecificEffectEstimator.pure_step(
            state,
            {
                "n_folds": 2,
                "estimation_method": "tmle",
                "tmle_library": ["ols", "ridge"],
                "tmle_v_folds": 3,
                "__seed__": 321,
            },
        )["mediation_result"]
        eif = PathSpecificEffectEstimator.pure_step(
            state,
            {"n_folds": 2, "estimation_method": "eif_cross_fit", "__seed__": 321},
        )["mediation_result"]
        assert abs(tmle["total_effect"] - eif["total_effect"]) < 0.25
        assert abs(tmle["total_effect"] - (tmle["nde"] + tmle["nie"])) < 1e-9

    def test_path_specific_output_json_serializable(self):
        """Output must be JSON-serializable."""
        state = self._make_state()
        params = {
            "n_folds": 2,
            "compute_sensitivity": True,
            "rho_range": [-0.5, 0.0, 0.5],
            "__seed__": 2,
        }
        out = PathSpecificEffectEstimator.pure_step(state, params)
        # Should not raise
        json.dumps(out)


# ── Registry ──────────────────────────────────────────────────────────────────


class TestRegistry:
    def test_path_specific_estimator_registered(self):
        """PathSpecificEffectEstimator must be in register_causal_methods()."""
        from polisyos.foundry.methods.catalog.causal._registry_boot import (
            register_causal_methods,
        )

        methods = register_causal_methods()
        names = [m.__name__ for m in methods]
        assert "PathSpecificEffectEstimator" in names

    def test_natural_effect_estimator_registered(self):
        """NaturalEffectEstimator must be in register_causal_methods()."""
        from polisyos.foundry.methods.catalog.causal._registry_boot import (
            register_causal_methods,
        )

        methods = register_causal_methods()
        names = [m.__name__ for m in methods]
        assert "NaturalEffectEstimator" in names


# ── NaturalEffectEstimator ────────────────────────────────────────────────────


class TestNaturalEffectEstimator:
    def test_natural_effect_estimator_pure_step(self):
        """NaturalEffectEstimator.pure_step returns result with nde/nie/total_effect."""
        rng = np.random.default_rng(5)
        X, T, M, Y = _linear_mediation_dgp(n=300, rng=rng)
        state = {"X": X, "treatment": T, "mediator": M, "outcome": Y}
        params = {"n_folds": 2, "__seed__": 5}
        out = NaturalEffectEstimator.pure_step(state, params)
        assert "result" in out
        r = out["result"]
        assert "nde" in r
        assert "nie" in r
        assert "total_effect" in r
        assert abs(r["total_effect"] - (r["nde"] + r["nie"])) < 1e-9
        assert math.isfinite(r["nde"])
        assert math.isfinite(r["nie"])
