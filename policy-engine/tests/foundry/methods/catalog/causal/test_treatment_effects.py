from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../src"))

from polisyos.foundry.methods.catalog.causal._common import bootstrap_ci
from polisyos.foundry.methods.catalog.causal.tmle_core import (
    ATENuisanceBundle,
    ATENuisanceContract,
    _interval_from_eif,
    fit_aipw_ate,
    fit_tmle_ate,
)
from polisyos.foundry.methods.catalog.causal.treatment_effects import (
    AIPWEstimator,
    IPWEstimator,
    TMLEEstimator,
)


def _make_state(n: int = 180, seed: int = 7) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 4))
    logit = 0.45 * X[:, 0] - 0.25 * X[:, 1] + 0.15 * X[:, 2]
    propensity = 1.0 / (1.0 + np.exp(-logit))
    treatment = rng.binomial(1, np.clip(propensity, 0.05, 0.95)).astype(float)
    outcome = 1.5 * treatment + 0.4 * X[:, 0] - 0.3 * X[:, 1] ** 2 + 0.2 * X[:, 2] * treatment
    outcome = outcome + rng.normal(scale=0.2, size=n)
    return {"X": X, "treatment": treatment, "outcome": outcome}


def _params() -> dict[str, object]:
    return {
        "random_seed": 19,
        "random_seed_manifest": [19, 101],
        "crossfit_folds": 3,
        "n_repeats": 2,
        "bootstrap_draws": 40,
        "propensity_backend": "lightgbm",
        "outcome_backend": "lightgbm",
        "propensity_backend_candidates": ["lightgbm", "rf"],
        "outcome_backend_candidates": ["lightgbm", "elastic_net"],
        "backend_selection_policy": "causal_risk+overlap",
        "selection_objective": "causal_risk",
        "overlap_diagnostic_policy": "crossfit_ntv_proxy+ess",
        "calibration_mode": "sigmoid",
        "calibration_fraction": 0.2,
        "min_calibration_size": 12,
        "min_effective_sample_size": 60,
        "propensity_clipping": 0.01,
        "propensity_trimming": 0.02,
        "outcome_scaling": "raw+standardized",
        "inference_backend": "bootstrap_eif",
        "ci_mode": "auto",
        "coverage_guard": "ess_aware",
        "overlap_guard": 0.1,
        "weak_overlap_mode": "trimmed_dr",
    }


def test_aipw_emits_bootstrap_eif_contract_and_diagnostics():
    state = _make_state()
    result = AIPWEstimator.pure_step(state, _params())
    inner = result["result"]

    assert inner["interval_method"].startswith("bootstrap_eif")
    assert inner["ci_lower"] <= inner["ate"] <= inner["ci_upper"]
    assert inner["nuisance_contract"]["propensity_backend"] == "lightgbm"
    assert inner["nuisance_contract"]["outcome_backend"] == "lightgbm"
    assert inner["nuisance_contract"]["calibration_mode"] == "sigmoid"
    assert inner["nuisance_contract"]["min_calibration_size"] == 12
    assert inner["nuisance_contract"]["ci_mode"] == "auto"
    assert inner["nuisance_contract"]["selection_objective"] == "causal_risk"
    assert inner["nuisance_contract"]["propensity_backend_candidates"]
    assert inner["nuisance_contract"]["outcome_backend_candidates"]
    assert inner["nuisance_contract"]["weak_overlap_mode"] == "trimmed_dr"
    assert inner["nuisance_config"]["n_repeats"] == 2
    assert "effective_sample_size" in inner["nuisance_diagnostics"]
    assert "overlap_ntv" in inner["nuisance_diagnostics"]
    assert "split_manifest" in inner["nuisance_diagnostics"]
    assert "coverage_guard_triggered" in inner["nuisance_diagnostics"]
    assert len(inner["nuisance_diagnostics"]["split_manifest"]) == 2
    assert inner["selection_manifest"]["selection_objective"] == "causal_risk"
    assert inner["selection_manifest"]["tested_propensity_backends"]
    assert inner["selection_manifest"]["tested_outcome_backends"]


def test_tmle_targets_deterministically_and_reports_targeting_summary():
    state = _make_state()
    params = _params()

    first = TMLEEstimator.pure_step(state, params)
    second = TMLEEstimator.pure_step(state, params)
    inner = first["result"]

    assert inner["interval_method"].startswith("bootstrap_eif")
    assert inner["ci_lower"] <= inner["ate"] <= inner["ci_upper"]
    assert inner["targeting_summary"]["n_iterations"] >= 1
    assert len(inner["targeting_summary"]["history"]) >= 1
    assert np.isfinite(inner["targeting_summary"]["history"][0]["epsilon"])
    assert first["result"]["ate"] == second["result"]["ate"]
    assert first["result"]["ci_lower"] == second["result"]["ci_lower"]
    assert first["result"]["ci_upper"] == second["result"]["ci_upper"]


def test_tmle_helper_and_aipw_helper_share_stable_contract():
    state = _make_state()
    params = _params()

    aipw_result, aipw_bundle = fit_aipw_ate(state["X"], state["treatment"], state["outcome"], params)
    tmle_result, tmle_bundle = fit_tmle_ate(state["X"], state["treatment"], state["outcome"], params)

    assert aipw_result.interval_method.startswith("bootstrap_eif")
    assert tmle_result.interval_method.startswith("bootstrap_eif")
    assert aipw_bundle.contract.random_seed_manifest == (19, 101)
    assert tmle_bundle.contract.random_seed_manifest == (19, 101)
    assert aipw_bundle.diagnostics()["calibration_modes"]
    assert tmle_bundle.diagnostics()["propensity_backends"]
    assert aipw_bundle.contract.selection_objective == "causal_risk"
    assert tmle_bundle.contract.selection_objective == "causal_risk"
    assert aipw_bundle.contract.propensity_backend_candidates
    assert tmle_bundle.contract.outcome_backend_candidates
    assert aipw_bundle is tmle_bundle


def test_aipw_does_not_delegate_to_dml_when_econml_backend_is_requested():
    state = _make_state()
    params = {**_params(), "estimation_backend": "econml_direct"}

    with patch(
        "polisyos.foundry.methods.catalog.causal.dml.DoubleMachineLearning.pure_step",
        side_effect=AssertionError("AIPWEstimator should not delegate to DML"),
    ):
        result = AIPWEstimator.pure_step(state, params)

    assert np.isfinite(result["result"]["ate"])
    assert result["result"]["interval_method"].startswith("bootstrap_eif")


def test_overlap_ntv_triggers_coverage_guard_interval_inflation() -> None:
    contract = ATENuisanceContract(
        min_effective_sample_size=24.0,
        ci_mode="auto",
        coverage_guard="ess_aware",
        overlap_guard=0.1,
    )
    scaler = SimpleNamespace(mean=0.0, scale=1.0, applied=False)
    eif_values = np.linspace(-0.25, 0.25, 200)
    low_overlap = ATENuisanceBundle(
        propensity=np.full(200, 0.5, dtype=float),
        mu1=np.ones(200, dtype=float),
        mu0=np.zeros(200, dtype=float),
        trim_mask=np.ones(200, dtype=bool),
        scaler=scaler,
        contract=contract,
    )
    high_overlap_skew = ATENuisanceBundle(
        propensity=np.concatenate([np.full(100, 0.9), np.full(100, 0.1)]).astype(float),
        mu1=np.ones(200, dtype=float),
        mu0=np.zeros(200, dtype=float),
        trim_mask=np.ones(200, dtype=bool),
        scaler=scaler,
        contract=contract,
    )

    low_diag = low_overlap.diagnostics()
    high_diag = high_overlap_skew.diagnostics()
    assert low_diag["coverage_guard_triggered"] is False
    assert high_diag["coverage_guard_triggered"] is True
    assert high_diag["overlap_ntv"] > high_diag["overlap_ntv_guard_threshold"]

    _, _, low_ci_lo, low_ci_hi, low_method = _interval_from_eif(
        2.0,
        eif_values,
        contract,
        seed_offset=0,
        nuisance=low_overlap,
    )
    _, _, high_ci_lo, high_ci_hi, high_method = _interval_from_eif(
        2.0,
        eif_values,
        contract,
        seed_offset=1,
        nuisance=high_overlap_skew,
    )

    assert low_method == "bootstrap_eif"
    assert high_method.endswith("+coverage_guard")
    assert (high_ci_hi - high_ci_lo) > (low_ci_hi - low_ci_lo)


def test_ipw_uses_hajek_interval_and_weight_diagnostics() -> None:
    state = _make_state()
    result = IPWEstimator.pure_step(state, {"trimming": 0.02})
    inner = result["result"]

    assert inner["interval_method"] == "hajek_influence"
    assert inner["ci_lower"] <= inner["ate"] <= inner["ci_upper"]
    assert inner["effective_sample_size_treated"] > 0
    assert inner["effective_sample_size_control"] > 0
    assert inner["n_clipped_propensities"] >= 0


def test_bootstrap_ci_ignores_non_finite_draws() -> None:
    lower, upper = bootstrap_ci(np.array([np.nan, 1.0, 2.0, np.inf]), confidence_level=0.9)

    assert lower == pytest.approx(1.05)
    assert upper == pytest.approx(1.95)
