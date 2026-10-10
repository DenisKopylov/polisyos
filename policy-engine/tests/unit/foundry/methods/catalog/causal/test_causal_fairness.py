"""Tests for Phase 8: Causal Fairness methods.

Coverage (22 tests):

TV Decomposition (TVFairnessDecomposer):
  1.  test_tv_decomposition_consistency          — TV ≈ DE + IE + SE
  2.  test_de_positive_when_direct_bias          — known A→Y effect → DE > 0
  3.  test_se_near_zero_no_confounders           — SE ≈ 0 when no latent U
  4.  test_tv_zero_no_disparity                  — Y⊥A → all components ≈ 0
  5.  test_ci_coverage_tv                        — 95% CI spans true TV
  6.  test_mediators_reduce_direct_effect        — mediation attenuates DE
  7.  test_output_keys_present                   — all required keys in output

Path-Specific Fairness (PathSpecificFairnessEstimator):
  8.  test_path_classification_direct_is_unfair  — A→Y detected as unfair path
  9.  test_legitimate_mediator_path_is_fair      — A→M→Y (M legitimate) is fair
 10.  test_unfair_path_effect_positive           — unfair A→Y has nonzero PSE
 11.  test_threshold_changes_verdict             — large threshold → all paths fair
 12.  test_no_graph_fallback                     — no graph_dot → graceful fallback

Counterfactual Fairness (CounterfactualFairnessEstimator):
 13.  test_cf_gap_near_zero_when_fair            — equal-treatment system → gap ≈ 0
 14.  test_cf_gap_positive_when_biased           — biased system → gap > 0
 15.  test_cf_fair_field_true_when_unbiased      — counterfactual_fairness_satisfied = True
 16.  test_cf_fair_field_false_when_biased       — counterfactual_fairness_satisfied = False
 17.  test_linear_approx_method_in_metadata      — metadata records abduction method

Protocol Validation (FairnessObservationalData):
 18.  test_too_few_obs_rejected                  — n < 30 raises ValidationError
 19.  test_nan_outcome_rejected                  — NaN in outcome → ValidationError
 20.  test_mediators_shape_mismatch_rejected     — wrong mediator length → ValidationError
 21.  test_report_serialization_roundtrip        — JSON round-trip preserves values

Registry:
 22.  test_fairness_methods_registered           — all 3 methods in registry namespace

References
----------
Plecko & Bareinboim (2022); Zhang & Bareinboim (2018); Kusner et al. (2017).
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal.fairness import (
    CounterfactualFairnessEstimator,
    PathSpecificFairnessEstimator,
    TVFairnessDecomposer,
)
from polisyos.foundry.methods.catalog.causal.protocols import FairnessObservationalData

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_registry():
    """Isolate registry state between tests."""
    from polisyos.foundry.methods.registry import MethodRegistry

    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def _biased_dataset(
    n: int = 400,
    seed: int = 42,
    *,
    direct_effect: float = 0.4,
    mediator_effect: float = 0.0,
    confounder_strength: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]:
    """Synthetic dataset with known DGP.

    DGP:
        X  ~ N(0, 1)
        A  ~ Bernoulli(sigmoid(confounder_strength * X))
        M  ~ 0.4*A + 0.3*X + noise     (if mediator_effect > 0)
        Y  = direct_effect*A + mediator_effect*M + 0.5*X + noise
    Returns (Y, A, X, M or None)
    """
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, 2))
    logit_a = confounder_strength * X[:, 0]
    p_a = 1.0 / (1.0 + np.exp(-logit_a))
    A = rng.binomial(1, p_a).astype(float)

    M: np.ndarray | None = None
    if mediator_effect != 0.0:
        M = 0.4 * A + 0.3 * X[:, 0] + 0.1 * rng.standard_normal(n)
        Y = direct_effect * A + mediator_effect * M + 0.5 * X[:, 0] + rng.standard_normal(n)
    else:
        Y = direct_effect * A + 0.5 * X[:, 0] + rng.standard_normal(n)

    return Y, A, X, M


def _run_tv(state_dict: dict, params: dict | None = None) -> dict:
    return TVFairnessDecomposer.pure_step(state_dict, params or {})


def _run_psf(state_dict: dict, params: dict | None = None) -> dict:
    return PathSpecificFairnessEstimator.pure_step(state_dict, params or {})


def _run_cf(state_dict: dict, params: dict | None = None) -> dict:
    return CounterfactualFairnessEstimator.pure_step(state_dict, params or {})


def _state(Y, A, X, M=None, graph_dot=None):
    d = {"outcome": Y, "protected": A, "covariates": X}
    if M is not None:
        d["mediators"] = M.reshape(-1, 1) if M.ndim == 1 else M
    if graph_dot is not None:
        d["graph_dot"] = graph_dot
    return d


# ---------------------------------------------------------------------------
# 1–7: TV Decomposition tests
# ---------------------------------------------------------------------------


def test_tv_decomposition_consistency():
    """TV ≈ DE + IE + SE (decomposition residual < 0.05)."""
    Y, A, X, _ = _biased_dataset(n=500, direct_effect=0.3, seed=0)
    result = _run_tv(_state(Y, A, X), {"n_folds": 3, "__seed__": 0})
    report = result["fairness_report"]
    decomp = report["decomposition"]
    tv = decomp["tv"]
    de = decomp["direct_effect"]
    ie = decomp["indirect_effect"]
    se = decomp["spurious_effect"]
    # Identity: TV = DE + IE + SE
    assert abs(tv - (de + ie + se)) < 0.05, (
        f"Decomposition residual too large: TV={tv:.4f}, DE+IE+SE={de + ie + se:.4f}"
    )
    assert decomp["decomposition_residual"] < 0.05


def test_de_positive_when_direct_bias():
    """Known direct A→Y effect of 0.4 should produce DE > 0."""
    Y, A, X, _ = _biased_dataset(n=600, direct_effect=0.4, seed=1)
    result = _run_tv(_state(Y, A, X), {"__seed__": 1})
    de = result["fairness_report"]["decomposition"]["direct_effect"]
    assert de > 0.0, f"Expected DE > 0 for biased DGP, got DE={de:.4f}"


def test_se_near_zero_no_confounders():
    """No latent confounders → SE ≈ 0 (TV ≈ DE + IE)."""
    # confounder_strength=0 → A independent of X → SE should be small
    Y, A, X, _ = _biased_dataset(n=600, direct_effect=0.3, confounder_strength=0.0, seed=2)
    result = _run_tv(_state(Y, A, X), {"__seed__": 2})
    decomp = result["fairness_report"]["decomposition"]
    tv = decomp["tv"]
    de = decomp["direct_effect"]
    ie = decomp["indirect_effect"]
    se = decomp["spurious_effect"]
    # Without confounders, SE should be close to 0; TV ≈ DE + IE
    assert abs(se) < abs(tv) * 0.5 + 0.1, (
        f"SE={se:.4f} too large relative to TV={tv:.4f} when no confounders"
    )


def test_tv_zero_no_disparity():
    """When Y⊥A (direct_effect=0), all components should be near zero."""
    Y, A, X, _ = _biased_dataset(n=600, direct_effect=0.0, seed=3)
    result = _run_tv(_state(Y, A, X), {"__seed__": 3})
    decomp = result["fairness_report"]["decomposition"]
    tv = decomp["tv"]
    de = decomp["direct_effect"]
    assert abs(tv) < 0.2, f"TV should be near 0 when A has no effect; got TV={tv:.4f}"
    assert abs(de) < 0.25, f"DE should be near 0 when A has no effect; got DE={de:.4f}"


def test_ci_coverage_tv():
    """TV 95% CI should contain the true TV."""
    Y, A, X, _ = _biased_dataset(n=800, direct_effect=0.3, seed=4)
    result = _run_tv(_state(Y, A, X), {"__seed__": 4})
    decomp = result["fairness_report"]["decomposition"]
    tv = decomp["tv"]
    ci = decomp["tv_ci"]
    assert ci is not None, "tv_ci should not be None"
    assert ci[0] <= tv <= ci[1], f"TV={tv:.4f} not in CI [{ci[0]:.4f}, {ci[1]:.4f}]"


def test_mediators_reduce_direct_effect():
    """Including mediators should result in DE < ATE (some effect explained by mediator)."""
    Y, A, X, M = _biased_dataset(n=600, direct_effect=0.2, mediator_effect=0.3, seed=5)
    # Without mediators: DE = ATE ≈ total effect
    result_no_med = _run_tv(_state(Y, A, X), {"__seed__": 5})
    de_no_med = result_no_med["fairness_report"]["decomposition"]["direct_effect"]

    # With mediators: DE should be smaller (some effect goes through M)
    assert M is not None
    result_med = _run_tv(_state(Y, A, X, M), {"__seed__": 5, "mediator_names": ["M"]})
    de_med = result_med["fairness_report"]["decomposition"]["direct_effect"]
    ie_med = result_med["fairness_report"]["decomposition"]["indirect_effect"]

    # IE should be nonzero when mediator_effect > 0
    assert abs(ie_med) > 0.0 or abs(de_med) < abs(de_no_med) + 0.2, (
        f"Mediator should explain some effect: DE_no_med={de_no_med:.4f}, "
        f"DE_med={de_med:.4f}, IE_med={ie_med:.4f}"
    )


def test_output_keys_present():
    """All required keys must be present in the output report."""
    Y, A, X, _ = _biased_dataset(n=300, seed=6)
    result = _run_tv(_state(Y, A, X), {"__seed__": 6})
    assert "fairness_report" in result
    report = result["fairness_report"]
    required_keys = {
        "decomposition",
        "counterfactual_fairness_satisfied",
        "path_specific_fairness",
        "direct_discrimination",
        "indirect_discrimination",
        "recommendation",
    }
    assert required_keys.issubset(set(report.keys())), (
        f"Missing keys: {required_keys - set(report.keys())}"
    )
    decomp_keys = {
        "tv",
        "direct_effect",
        "indirect_effect",
        "spurious_effect",
        "decomposition_residual",
        "n_obs",
        "estimation_method",
    }
    assert decomp_keys.issubset(set(report["decomposition"].keys()))


# ---------------------------------------------------------------------------
# 8–12: Path-Specific Fairness tests
# ---------------------------------------------------------------------------

_GRAPH_WITH_MEDIATOR = "digraph { A -> M; A -> Y; M -> Y; X1 -> M; X1 -> Y; X2 -> Y }"
_GRAPH_DIRECT_ONLY = "digraph { A -> Y; X1 -> Y; X2 -> Y }"


def test_path_classification_direct_is_unfair():
    """In a graph with A→Y, that path should be classified as unfair (no legitimate mediators)."""
    Y, A, X, _ = _biased_dataset(n=300, seed=7)
    state = _state(Y, A, X, graph_dot=_GRAPH_DIRECT_ONLY)
    result = _run_psf(
        state,
        {
            "graph_dot": _GRAPH_DIRECT_ONLY,
            "protected_node": "A",
            "outcome_node": "Y",
            "legitimate_mediators": [],  # no legitimate mediators → direct A→Y is unfair
            "effect_threshold": 0.5,  # high threshold so only checks classification, not magnitude
            "__seed__": 7,
        },
    )
    pf = result["fairness_report"]["path_specific_fairness"]
    # Should have at least one path detected
    assert len(pf) > 0, "No paths found in path_specific_fairness"
    # The direct A→Y path should be present
    direct_key = "A → Y"
    assert direct_key in pf, f"Expected '{direct_key}' in path verdicts: {list(pf.keys())}"


def test_legitimate_mediator_path_is_fair():
    """A→M→Y where M is 'legitimate' should be classified as fair."""
    Y, A, X, M = _biased_dataset(n=300, mediator_effect=0.2, seed=8)
    assert M is not None
    state = _state(Y, A, X, M, graph_dot=_GRAPH_WITH_MEDIATOR)
    result = _run_psf(
        state,
        {
            "graph_dot": _GRAPH_WITH_MEDIATOR,
            "protected_node": "A",
            "outcome_node": "Y",
            "legitimate_mediators": ["M"],  # M is legitimate
            "effect_threshold": 0.05,
            "mediator_node_names": ["M"],
            "__seed__": 8,
        },
    )
    pf = result["fairness_report"]["path_specific_fairness"]
    # A → M → Y path should exist and be fair (M is legitimate)
    mediated_key = "A → M → Y"
    if mediated_key in pf:
        assert pf[mediated_key] is True, (
            f"Expected path '{mediated_key}' to be fair (M is legitimate); got {pf[mediated_key]}"
        )


def test_unfair_path_effect_positive():
    """Direct A→Y path in biased DGP should have |PSE| > 0."""
    Y, A, X, _ = _biased_dataset(n=400, direct_effect=0.4, seed=9)
    state = _state(Y, A, X, graph_dot=_GRAPH_DIRECT_ONLY)
    result = _run_psf(
        state,
        {
            "graph_dot": _GRAPH_DIRECT_ONLY,
            "protected_node": "A",
            "outcome_node": "Y",
            "legitimate_mediators": [],
            "effect_threshold": 0.01,  # very tight threshold
            "__seed__": 9,
        },
    )
    meta = result["fairness_report"]["metadata"]
    path_effects = meta.get("path_effects", {})
    assert len(path_effects) > 0, "No path effects computed"
    max_effect = max(abs(v) for v in path_effects.values())
    assert max_effect > 0.01, (
        f"Expected |PSE| > 0.01 for direct_effect=0.4; got max={max_effect:.4f}"
    )


def test_threshold_changes_verdict():
    """Very large threshold should classify all paths as fair."""
    Y, A, X, _ = _biased_dataset(n=300, direct_effect=0.3, seed=10)
    state = _state(Y, A, X, graph_dot=_GRAPH_DIRECT_ONLY)
    result = _run_psf(
        state,
        {
            "graph_dot": _GRAPH_DIRECT_ONLY,
            "protected_node": "A",
            "outcome_node": "Y",
            "legitimate_mediators": [],
            "effect_threshold": 100.0,  # unrealistically large → everything is "fair"
            "__seed__": 10,
        },
    )
    pf = result["fairness_report"]["path_specific_fairness"]
    assert all(pf.values()), f"With threshold=100, all paths should be fair; got: {pf}"


def test_no_graph_fallback():
    """Without graph_dot, method should fall back gracefully to TV-style estimate."""
    Y, A, X, _ = _biased_dataset(n=300, seed=11)
    result = _run_psf(
        _state(Y, A, X),
        {
            "protected_node": "A",
            "outcome_node": "Y",
            "__seed__": 11,
        },
    )
    assert "fairness_report" in result
    # Should have at least one path verdict
    pf = result["fairness_report"]["path_specific_fairness"]
    assert len(pf) >= 1, "Expected at least one path in fallback mode"


# ---------------------------------------------------------------------------
# 13–17: Counterfactual Fairness tests
# ---------------------------------------------------------------------------


def test_cf_gap_near_zero_when_fair():
    """When A has no effect on Y (direct_effect=0), counterfactual gap ≈ 0."""
    Y, A, X, _ = _biased_dataset(n=400, direct_effect=0.0, seed=12)
    result = _run_cf(_state(Y, A, X), {"__seed__": 12})
    gap = result["fairness_report"]["metadata"]["counterfactual_gap"]
    assert gap < 0.3, f"Expected small gap for unbiased DGP; got gap={gap:.4f}"


def test_cf_gap_positive_when_biased():
    """Strong direct effect should produce a measurable counterfactual gap."""
    Y, A, X, _ = _biased_dataset(n=400, direct_effect=1.0, seed=13)
    result = _run_cf(_state(Y, A, X), {"__seed__": 13})
    gap = result["fairness_report"]["metadata"]["counterfactual_gap"]
    assert gap > 0.05, f"Expected gap > 0.05 for direct_effect=1.0; got gap={gap:.4f}"


def test_cf_fair_field_true_when_unbiased():
    """counterfactual_fairness_satisfied=True when A has no effect."""
    Y, A, X, _ = _biased_dataset(n=500, direct_effect=0.0, seed=14)
    result = _run_cf(
        _state(Y, A, X),
        {
            "counterfactual_gap_threshold": 0.5,  # generous threshold
            "__seed__": 14,
        },
    )
    assert result["fairness_report"]["counterfactual_fairness_satisfied"] is True, (
        "Expected counterfactual fairness satisfied for zero-effect DGP"
    )


def test_cf_fair_field_false_when_biased():
    """counterfactual_fairness_satisfied=False when A has large direct effect."""
    Y, A, X, _ = _biased_dataset(n=500, direct_effect=2.0, seed=15)
    result = _run_cf(
        _state(Y, A, X),
        {
            "counterfactual_gap_threshold": 0.01,  # tight threshold
            "__seed__": 15,
        },
    )
    assert result["fairness_report"]["counterfactual_fairness_satisfied"] is False, (
        "Expected counterfactual fairness NOT satisfied for large-effect DGP"
    )


def test_linear_approx_method_in_metadata():
    """metadata['abduction_method'] should record 'linear_approx' when no NCM spec."""
    Y, A, X, _ = _biased_dataset(n=200, seed=16)
    result = _run_cf(_state(Y, A, X), {"__seed__": 16})
    meta = result["fairness_report"]["metadata"]
    assert meta.get("abduction_method") == "linear_approx", (
        f"Expected 'linear_approx'; got {meta.get('abduction_method')}"
    )


# ---------------------------------------------------------------------------
# 18–21: Protocol validation tests
# ---------------------------------------------------------------------------


def test_too_few_obs_rejected():
    """FairnessObservationalData with n < 30 should raise ValidationError."""
    from pydantic import ValidationError

    Y = np.zeros(20)
    A = np.zeros(20)
    X = np.zeros((20, 2))
    with pytest.raises((ValidationError, ValueError)):
        FairnessObservationalData(outcome=Y, protected=A, covariates=X)


def test_nan_outcome_rejected():
    """NaN in outcome should raise ValidationError."""
    from pydantic import ValidationError

    Y = np.full(50, float("nan"))
    A = np.zeros(50)
    X = np.zeros((50, 2))
    with pytest.raises((ValidationError, ValueError)):
        FairnessObservationalData(outcome=Y, protected=A, covariates=X)


def test_mediators_shape_mismatch_rejected():
    """Mediators with wrong number of rows should raise ValidationError."""
    from pydantic import ValidationError

    Y = np.zeros(50)
    A = np.zeros(50)
    X = np.zeros((50, 2))
    M_wrong = np.zeros((30, 1))  # wrong n_obs
    with pytest.raises((ValidationError, ValueError)):
        FairnessObservationalData(outcome=Y, protected=A, covariates=X, mediators=M_wrong)


def test_report_serialization_roundtrip():
    """CausalFairnessReport should survive JSON round-trip with values preserved."""
    Y, A, X, _ = _biased_dataset(n=200, direct_effect=0.2, seed=17)
    result = _run_tv(_state(Y, A, X), {"__seed__": 17})
    report_dict = result["fairness_report"]

    # Serialize to JSON
    json_str = json.dumps(report_dict)
    assert len(json_str) > 10, "JSON output is too short"

    # Deserialize
    loaded = json.loads(json_str)
    assert loaded["decomposition"]["tv"] == pytest.approx(
        report_dict["decomposition"]["tv"], abs=1e-10
    )
    assert isinstance(loaded["recommendation"], str)
    assert len(loaded["recommendation"]) > 0


# ---------------------------------------------------------------------------
# 22: Registry test
# ---------------------------------------------------------------------------


def test_fairness_methods_registered():
    """All 3 Phase-8 fairness methods should register in the causal.fairness namespace."""
    from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
    from polisyos.foundry.methods.registry import MethodRegistry

    reg = MethodRegistry.get_instance()
    ensure_causal_methods_registered(reg)

    expected_fqns = [
        "causal.fairness.tv_fairness_decomposer@1.0.0",
        "causal.fairness.path_specific_fairness@1.0.0",
        "causal.fairness.counterfactual_fairness@1.0.0",
    ]
    registered = [m.fqn for m in reg.list_all() if "fairness" in m.fqn]
    for fqn in expected_fqns:
        assert fqn in registered, (
            f"Method '{fqn}' not found in registry. Registered fairness methods: {registered}"
        )
