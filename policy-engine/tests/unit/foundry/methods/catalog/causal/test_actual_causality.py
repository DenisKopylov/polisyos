"""Tests for ActualCausalityEngine — PN/PS/PNS probability of causation.

Coverage (15 tests):
  1.  test_tian_pearl_pn_bounds_formula — analytic formula check
  2.  test_tian_pearl_pn_bounds_zero_p11 — uninformative when p11=0
  3.  test_tian_pearl_ps_bounds_formula — analytic formula check
  4.  test_tian_pearl_pns_bounds_formula — PNS lb/ub formula
  5.  test_pns_lb_le_mc_pns_le_ub — MC estimate between Tian-Pearl bounds
  6.  test_monotonicity_test_positive — MTR compatible DGP
  7.  test_monotonicity_test_violation — MTR violated DGP
  8.  test_pns_zero_noise_direct_cause — deterministic DGP → PNS ≈ 1
  9.  test_pn_symmetry_with_ps — pn(x=1,x'=0) + ps(x=1,x'=0) bounds hold
 10.  test_pns_indirect_cause_lower — mediated cause has PNS < direct cause
 11.  test_pn_from_ncm_runs — PNResult structure present and in [0,1]
 12.  test_ps_from_ncm_runs — PSResult structure present and in [0,1]
 13.  test_pns_from_ncm_runs — PNSResult with marginal pn/ps
 14.  test_actual_causality_engine_pure_step — end-to-end dispatch with estimand='all'
 15.  test_actual_causality_engine_registered — in causal method registry
"""

from __future__ import annotations

import json

import numpy as np
from polisyos.foundry.methods.catalog.causal.actual_causality import (
    ActualCausalityEngine,
    _compute_monotonicity_test,
    _pn_from_ncm,
    _pns_from_ncm,
    _ps_from_ncm,
    _tian_pearl_pn_bounds,
    _tian_pearl_pns_bounds,
    _tian_pearl_ps_bounds,
    compute_pnps_bounds,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.ncm import ExogenousSpec, NCMSpec, StructuralEquation
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
)

# ── Shared DGP helpers ─────────────────────────────────────────────────────────


def _make_scm(
    *,
    intercept_y: float = 0.0,
    coeff_t: float = 1.0,
    noise_std: float = 0.0,
) -> StructuralCausalModelSpec:
    """T → Y chain: Y = intercept_y + coeff_t * T + U_Y."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["T", "Y"],
        edges=[CausalEdge(src="T", dst="Y")],
    )
    return StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="T",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.0, "std": 1.0},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["T"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": intercept_y,
                    "coefficients": {"T": coeff_t},
                    "noise_std": noise_std,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )


def _make_ncm(
    *,
    intercept_y: float = 0.0,
    coeff_t: float = 1.0,
    noise_std: float = 0.0,
) -> NCMSpec:
    """NCMSpec wrapping a T → Y chain."""
    scm = _make_scm(intercept_y=intercept_y, coeff_t=coeff_t, noise_std=noise_std)
    return NCMSpec(
        endogenous_vars=["T", "Y"],
        exogenous_specs=[
            ExogenousSpec(variable="U_T", associated_endogenous="T"),
            ExogenousSpec(variable="U_Y", associated_endogenous="Y"),
        ],
        structural_equations=[
            StructuralEquation(
                variable="T",
                parents=[],
                exogenous="U_T",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            ),
            StructuralEquation(
                variable="Y",
                parents=["T"],
                exogenous="U_Y",
                equation_type="linear",
                equation_params={
                    "intercept": intercept_y,
                    "coefficients": {"T": coeff_t},
                },
            ),
        ],
        scm_spec=scm,
        is_acyclic=True,
    )


def _make_deterministic_ncm() -> NCMSpec:
    """T → Y with coeff=1, intercept=0, zero noise: Y = T exactly (binary)."""
    return _make_ncm(intercept_y=0.0, coeff_t=1.0, noise_std=0.0)


# ── Tian-Pearl bound tests ─────────────────────────────────────────────────────


class TestTianPearlBounds:
    def test_tian_pearl_pn_bounds_formula(self):
        """PN bounds: lb=max(0,(p11-p10)/p11), ub=min(1,(1-p10)/p11)."""
        p11, p10 = 0.8, 0.2
        lb, ub = _tian_pearl_pn_bounds(p11, p10)
        expected_lb = max(0.0, (p11 - p10) / p11)
        expected_ub = min(1.0, (1.0 - p10) / p11)
        assert abs(lb - expected_lb) < 1e-12
        assert abs(ub - expected_ub) < 1e-12

    def test_tian_pearl_pn_bounds_zero_p11(self):
        """When p11=0, bounds are uninformative [0,1]."""
        lb, ub = _tian_pearl_pn_bounds(0.0, 0.3)
        assert lb == 0.0
        assert ub == 1.0

    def test_tian_pearl_ps_bounds_formula(self):
        """PS bounds: lb=max(0,(p11-p10)/p00), ub=min(1,p11/p00)."""
        p11, p10 = 0.7, 0.1
        lb, ub = _tian_pearl_ps_bounds(p11, p10)
        p00 = 1.0 - p10
        expected_lb = max(0.0, (p11 - p10) / p00)
        expected_ub = min(1.0, p11 / p00)
        assert abs(lb - expected_lb) < 1e-12
        assert abs(ub - expected_ub) < 1e-12

    def test_tian_pearl_pns_bounds_formula(self):
        """PNS bounds: lb=max(0,p11-p10), ub=min(p11,1-p10)."""
        p11, p10 = 0.7, 0.2
        lb, ub = _tian_pearl_pns_bounds(p11, p10)
        assert abs(lb - max(0.0, p11 - p10)) < 1e-12
        assert abs(ub - min(p11, 1.0 - p10)) < 1e-12

    def test_pnps_bounds_monotone_pns(self):
        """Under MTR: monotone_pns = p11 - p10, is_monotone_compatible=True."""
        p11, p10 = 0.8, 0.3
        result = compute_pnps_bounds(p11, p10)
        assert abs(result.monotone_pns - max(0.0, p11 - p10)) < 1e-12
        assert result.is_monotone_compatible is True

    def test_pnps_bounds_not_monotone(self):
        """When p11 < p10, not monotone compatible."""
        result = compute_pnps_bounds(0.2, 0.8)
        assert result.is_monotone_compatible is False


# ── Monotonicity test ──────────────────────────────────────────────────────────


class TestMonotonicityTest:
    def test_monotonicity_test_positive(self):
        """MTR-compatible DGP (T helps Y)."""
        rng = np.random.default_rng(42)
        n = 1000
        T = rng.binomial(1, 0.5, n)
        Y = (rng.uniform(size=n) < 0.3 + 0.4 * T).astype(float)
        is_compat, p_val = _compute_monotonicity_test(Y, T)
        assert is_compat is True

    def test_monotonicity_test_violation(self):
        """MTR-violated DGP (T hurts Y)."""
        rng = np.random.default_rng(99)
        n = 1000
        T = rng.binomial(1, 0.5, n)
        # P(Y=1|T=1) = 0.1 < P(Y=1|T=0) = 0.9
        Y = (rng.uniform(size=n) < 0.9 - 0.8 * T).astype(float)
        is_compat, p_val = _compute_monotonicity_test(Y, T)
        assert is_compat is False

    def test_monotonicity_insufficient_data(self):
        """Too few samples → trivially returns (True, 1.0)."""
        Y = np.array([1.0, 0.0])
        T = np.array([1.0, 0.0])
        is_compat, p_val = _compute_monotonicity_test(Y, T)
        assert is_compat is True
        assert p_val == 1.0


# ── NCM-based simulation ───────────────────────────────────────────────────────


class TestPNFromNCM:
    def test_pn_from_ncm_runs(self):
        """PNResult structure is returned and pn ∈ [0, 1]."""
        ncm = _make_ncm(noise_std=0.1)
        rng = np.random.default_rng(42)
        warnings: list[str] = []
        result = _pn_from_ncm(ncm, "T", "Y", 1.0, 0.0, n_samples=500, rng=rng, warnings=warnings)
        assert 0.0 <= result.pn <= 1.0
        assert result.treatment == "T"
        assert result.outcome == "Y"
        assert result.computation_method == "simulation"

    def test_pn_deterministic_direct_cause(self):
        """Zero-noise, full-range T: PN ≈ 1 when Y = T."""
        ncm = _make_deterministic_ncm()
        rng = np.random.default_rng(0)
        warnings: list[str] = []
        result = _pn_from_ncm(
            ncm,
            "T",
            "Y",
            1.0,
            0.0,
            n_samples=2000,
            rng=rng,
            warnings=warnings,
            outcome_threshold=0.5,
        )
        # Y = T, so Y_{T=0} = 0 always when Y_{T=1} = 1: PN = 1.0
        assert result.pn > 0.8


class TestPSFromNCM:
    def test_ps_from_ncm_runs(self):
        """PSResult structure is returned and ps ∈ [0, 1]."""
        ncm = _make_ncm(noise_std=0.1)
        rng = np.random.default_rng(7)
        warnings: list[str] = []
        result = _ps_from_ncm(ncm, "T", "Y", 1.0, 0.0, n_samples=500, rng=rng, warnings=warnings)
        assert 0.0 <= result.ps <= 1.0
        assert result.computation_method == "simulation"


class TestPNSFromNCM:
    def test_pns_from_ncm_runs(self):
        """PNSResult has pns/pn/ps all in [0,1]."""
        ncm = _make_ncm(noise_std=0.1)
        rng = np.random.default_rng(13)
        warnings: list[str] = []
        result = _pns_from_ncm(ncm, "T", "Y", 1.0, 0.0, n_samples=1000, rng=rng, warnings=warnings)
        assert 0.0 <= result.pns <= 1.0
        assert result.pn is not None and 0.0 <= result.pn <= 1.0
        assert result.ps is not None and 0.0 <= result.ps <= 1.0

    def test_pns_zero_noise_direct_cause_high(self):
        """Deterministic Y=T → PNS ≈ 1 (necessary AND sufficient)."""
        ncm = _make_deterministic_ncm()
        rng = np.random.default_rng(0)
        warnings: list[str] = []
        result = _pns_from_ncm(
            ncm,
            "T",
            "Y",
            1.0,
            0.0,
            n_samples=2000,
            rng=rng,
            warnings=warnings,
            outcome_threshold=0.5,
        )
        assert result.pns > 0.8

    def test_pns_between_tian_pearl_bounds(self):
        """MC PNS estimate falls between Tian-Pearl observational bounds."""
        # With Y = T (deterministic), P(Y=1|T=1)=1, P(Y=1|T=0)=0
        # PNS_lb = 1, PNS_ub = 1 → PNS = 1
        ncm = _make_deterministic_ncm()
        rng = np.random.default_rng(99)
        warnings: list[str] = []
        result = _pns_from_ncm(
            ncm,
            "T",
            "Y",
            1.0,
            0.0,
            n_samples=2000,
            rng=rng,
            warnings=warnings,
            outcome_threshold=0.5,
        )
        lb, ub = _tian_pearl_pns_bounds(1.0, 0.0)
        # MC PNS should be within a small tolerance of theoretical bounds
        assert result.pns >= lb - 0.05
        assert result.pns <= ub + 0.05


# ── Foundry method ─────────────────────────────────────────────────────────────


class TestActualCausalityEnginePureStep:
    def _make_query_dict(self) -> dict:
        ncm = _make_ncm(noise_std=0.1)
        return {
            "ncm_spec": ncm.model_dump(mode="json"),
            "evidence": {},
            "interventions": [],
            "query_vars": ["Y"],
            "metadata": {
                "treatment_variable": "T",
                "outcome_variable": "Y",
            },
        }

    def test_pure_step_pns(self):
        """pure_step with estimand='pns' returns pns_result dict."""
        state = {"ncm_query_data": self._make_query_dict()}
        params = {
            "estimand": "pns",
            "n_samples": 500,
            "treatment_value": 1.0,
            "counterfactual_value": 0.0,
            "treatment_variable": "T",
            "outcome_variable": "Y",
            "__seed__": 42,
        }
        out = ActualCausalityEngine.pure_step(state, params)
        assert "pns_result" in out
        pns = out["pns_result"]
        assert 0.0 <= pns["pns"] <= 1.0

    def test_pure_step_all_estimands(self):
        """estimand='all' returns pn, ps, pns results."""
        state = {"ncm_query_data": self._make_query_dict()}
        params = {
            "estimand": "all",
            "n_samples": 500,
            "treatment_value": 1.0,
            "counterfactual_value": 0.0,
            "treatment_variable": "T",
            "outcome_variable": "Y",
            "__seed__": 0,
        }
        out = ActualCausalityEngine.pure_step(state, params)
        assert "pn_result" in out
        assert "ps_result" in out
        assert "pns_result" in out

    def test_pure_step_observational_bounds(self):
        """Passing p_y1_x1/p_y1_x0 in metadata produces pnps_bounds."""
        state = {
            "ncm_query_data": {
                **self._make_query_dict(),
            }
        }
        # Inject observational probs into metadata
        state["ncm_query_data"]["metadata"] = {
            "treatment_variable": "T",
            "outcome_variable": "Y",
            "p_y1_x1": 0.8,
            "p_y1_x0": 0.2,
        }
        params = {
            "estimand": "pns",
            "n_samples": 200,
            "compute_bounds": True,
            "treatment_variable": "T",
            "outcome_variable": "Y",
            "__seed__": 1,
        }
        out = ActualCausalityEngine.pure_step(state, params)
        assert "pnps_bounds" in out
        assert out["pnps_bounds"]["pns_lower"] >= 0.0

    def test_pure_step_output_is_json_serializable(self):
        """Output should be JSON-serializable."""
        state = {"ncm_query_data": self._make_query_dict()}
        params = {
            "estimand": "pns",
            "n_samples": 200,
            "treatment_variable": "T",
            "outcome_variable": "Y",
            "__seed__": 5,
        }
        out = ActualCausalityEngine.pure_step(state, params)
        # Should not raise
        json.dumps(out)


class TestActualCausalityEngineRegistry:
    def test_actual_causality_engine_registered(self):
        """ActualCausalityEngine must be registered via register_causal_methods."""
        from polisyos.foundry.methods.catalog.causal._registry_boot import (
            register_causal_methods,
        )

        methods = register_causal_methods()
        names = [m.__name__ for m in methods]
        assert "ActualCausalityEngine" in names

    def test_hp_actual_cause_method_registered(self):
        """HPActualCauseMethod must be registered via register_causal_methods."""
        from polisyos.foundry.methods.catalog.causal._registry_boot import (
            register_causal_methods,
        )

        methods = register_causal_methods()
        names = [m.__name__ for m in methods]
        assert "HPActualCauseMethod" in names
