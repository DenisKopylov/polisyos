"""Native B54 cache and bounded B56 cross-fit witnesses on a known DGP.

The oracle is a constant additive treatment effect, not admitted real data or
a coverage claim. Observers call the real sklearn fit and cross-fit paths.
The external executor in the B56 test is an explicit test resource, not a
production study admission service.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from typing import Any

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal import tmle_core
from polisyos.foundry.methods.catalog.causal.treatment_effects import (
    AIPWEstimator,
    TMLEEstimator,
)

FIT_CHANGES: dict[str, Any] = {
    "nuisance_model_family": "parametric",
    "propensity_backend": "logistic",
    "propensity_backend_candidates": ("logistic",),
    "outcome_backend": "linear",
    "outcome_backend_candidates": ("linear",),
    "selection_objective": "mse",
    "calibration_mode": "uncalibrated",
    "crossfit_folds": 3,
    "n_repeats": 2,
    "random_seed": 29,
    "random_seed_manifest": (29,),
    "propensity_clipping": 0.02,
    "propensity_trimming": 0.03,
    "outcome_scaling": "raw+standardized",
    "calibration_fraction": 0.1,
    "min_calibration_size": 3,
}
VIEW_CHANGES: dict[str, Any] = {
    "backend_selection_policy": "reported-policy",
    "inference_backend": "bootstrap_eif",
    "bootstrap_draws": 41,
    "feature_importance_mode": "none",
    "min_effective_sample_size": 100.0,
    "ci_mode": "conservative",
    "coverage_guard": "off",
    "overlap_diagnostic_policy": "current-ess-policy",
    "weak_overlap_mode": "trimmed_dr",
    "overlap_guard": 0.15,
    "parallel_folds": True,
    "max_parallel_folds": 2,
    "max_targeting_iter": 4,
    "targeting_step_limit": 7.0,
}


def _data() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate Y = 1.75 T + linear baseline + independent mean-zero noise."""
    rng = np.random.default_rng(81)
    x = rng.normal(size=(256, 2))
    propensity = 1.0 / (1.0 + np.exp(-0.3 * x[:, 0]))
    t = rng.binomial(1, propensity).astype(float)
    y = 1.75 * t + 0.5 * x[:, 0] - 0.2 * x[:, 1] + rng.normal(0.0, 0.15, len(t))
    return x, t, y


def _contract() -> tmle_core.ATENuisanceContract:
    return tmle_core.ATENuisanceContract(
        propensity_backend="logistic_regression",
        outcome_backend="linear_regression",
        calibration_mode="none",
        calibration_fraction=0.0,
        min_calibration_size=0,
        crossfit_folds=2,
        n_repeats=1,
        random_seed=17,
        parallel_folds=False,
        max_parallel_folds=1,
        outcome_scaling="raw",
        inference_backend="wald",
        bootstrap_draws=40,
        min_effective_sample_size=48.0,
        coverage_guard="ess_aware",
    )


@pytest.fixture
def observed_native_fits(monkeypatch: pytest.MonkeyPatch) -> list[tmle_core.ATENuisanceContract]:
    """Count real uncached fits and isolate cache state between tests."""
    monkeypatch.setattr(tmle_core, "_SHARED_NUISANCE_CACHE", {})
    monkeypatch.setattr(tmle_core, "_SHARED_NUISANCE_CACHE_ORDER", [])
    calls: list[tmle_core.ATENuisanceContract] = []
    native_fit = tmle_core._fit_crossfit_nuisance_bundle_uncached

    def observe(
        x: np.ndarray, t: np.ndarray, y: np.ndarray, contract: tmle_core.ATENuisanceContract
    ) -> tmle_core.ATENuisanceBundle:
        calls.append(contract)
        return native_fit(x, t, y, contract)

    monkeypatch.setattr(tmle_core, "_fit_crossfit_nuisance_bundle_uncached", observe)
    return calls


def _assert_native_backend(bundle: tmle_core.ATENuisanceBundle) -> None:
    """Reject fallback-as-native witnesses using the actual instantiated model."""
    model, _ = tmle_core._instantiate_propensity_model("logistic_regression", seed=17)
    regression, _ = tmle_core._instantiate_regression_model("linear_regression", seed=17)
    assert type(model).__module__.startswith("sklearn.")
    assert type(regression).__module__.startswith("sklearn.")
    assert set(bundle.propensity_backends) == {"logistic_regression"}
    assert set(bundle.outcome_backends) == {"compat_linear_regression"}


def test_all_contract_axes_have_an_explicit_fit_or_current_view_role() -> None:
    """Walk the whole dataclass field denominator, including future additions."""
    actual_fields = {item.name for item in fields(tmle_core.ATENuisanceContract)}
    assert not set(FIT_CHANGES) & set(VIEW_CHANGES)
    assert set(FIT_CHANGES) | set(VIEW_CHANGES) == actual_fields
    original = _contract()
    for name, value in {**FIT_CHANGES, **VIEW_CHANGES}.items():
        assert getattr(original, name) != value


@pytest.mark.parametrize("field_name", list(FIT_CHANGES))
def test_every_scientific_contract_axis_recomputes_native_fit(
    field_name: str, observed_native_fits: list[tmle_core.ATENuisanceContract]
) -> None:
    """B54: fitting/split policy changes cannot borrow the preceding fit."""
    x, t, y = _data()
    original = _contract()
    cold = tmle_core.fit_crossfit_nuisance_bundle(x, t, y, original)
    changed = replace(original, **{field_name: FIT_CHANGES[field_name]})
    warm = tmle_core.fit_crossfit_nuisance_bundle(x, t, y, changed)
    assert observed_native_fits == [original, changed]
    _assert_native_backend(cold)
    _assert_native_backend(warm)


@pytest.mark.parametrize("namespace", [None, "same-declared-source"])
@pytest.mark.parametrize("dimension", ["X", "T", "Y"])
def test_full_data_identity_is_required_even_with_an_explicit_namespace(
    namespace: str | None,
    dimension: str,
    observed_native_fits: list[tmle_core.ATENuisanceContract],
) -> None:
    """B54 negative: a matching caller label cannot stand in for source bytes."""
    x, t, y = _data()
    arrays = {"X": x, "T": t, "Y": y}
    params = {} if namespace is None else {"__shared_nuisance_key": namespace}
    cold = tmle_core.fit_crossfit_nuisance_bundle(x, t, y, _contract(), params)
    changed = {name: value.copy() for name, value in arrays.items()}
    if dimension == "T":
        changed[dimension][0] = 1.0 - changed[dimension][0]
    else:
        changed[dimension].flat[0] += 10.0
    warm = tmle_core.fit_crossfit_nuisance_bundle(
        changed["X"], changed["T"], changed["Y"], _contract(), params
    )
    assert len(observed_native_fits) == 2
    assert not np.shares_memory(cold.mu1, warm.mu1)


def test_current_diagnostics_reuse_immutable_fit_and_isolate_every_reader(
    observed_native_fits: list[tmle_core.ATENuisanceContract],
) -> None:
    """B54: native predictions are shared without mutable cache ownership."""
    x, t, y = _data()
    original = _contract()
    cold = tmle_core.fit_crossfit_nuisance_bundle(x, t, y, original)
    expected_manifest = deepcopy(cold.selection_manifest)
    changed = replace(original, **VIEW_CHANGES)
    warm = tmle_core.fit_crossfit_nuisance_bundle(x, t, y, changed)
    assert observed_native_fits == [original]
    assert warm.contract is changed
    assert warm.diagnostics()["min_effective_sample_size"] == 100.0
    assert warm.diagnostics()["coverage_guard"] == "off"
    assert all(r["split_policy"] == "current-ess-policy" for r in warm.selection_manifest)
    for name in ("propensity", "mu1", "mu0", "trim_mask"):
        first_array = getattr(cold, name)
        second_array = getattr(warm, name)
        assert first_array is not second_array
        assert np.shares_memory(first_array, second_array)
        with pytest.raises(ValueError):
            first_array.setflags(write=True)
        with pytest.raises(ValueError):
            first_array.flat[0] = 0
        first_array.shape = (first_array.size, 1)
        assert second_array.shape == (len(y),)
    cold.split_manifest[0]["folds"].clear()
    cold.selection_manifest[0]["tested_propensity_backends"].append("consumer-mutation")
    cold.calibration_modes.clear()
    cold.propensity_backends.clear()
    cold.outcome_backends.clear()
    with pytest.raises(FrozenInstanceError):
        cold.scaler.mean = 999.0
    with pytest.raises(FrozenInstanceError):
        cold.scaler.scale = 999.0
    diagnostics = warm.diagnostics()
    diagnostics["selection_manifest"][0]["tested_propensity_backends"].clear()
    third = tmle_core.fit_crossfit_nuisance_bundle(x, t, y, original)
    assert observed_native_fits == [original]
    assert len(third.split_manifest[0]["folds"]) == 2
    assert third.selection_manifest == expected_manifest
    assert third.calibration_modes == ["none", "none"]
    assert third.scaler.mean != 999.0 and third.scaler.scale != 999.0
    _assert_native_backend(third)


@pytest.mark.parametrize("estimator", [AIPWEstimator, TMLEEstimator])
def test_actual_consumers_refresh_policy_and_match_known_dgp(
    estimator: Any, observed_native_fits: list[tmle_core.ATENuisanceContract]
) -> None:
    """B54: real facade payloads track current analysis with the same fit."""
    x, t, y = _data()
    state = {"X": x, "treatment": t, "outcome": y}
    params = _contract().as_contract_payload()
    first = estimator.pure_step(state, params)["result"]
    current = {**params, "min_effective_sample_size": 1000.0}
    second = estimator.pure_step(state, current)["result"]
    assert len(observed_native_fits) == 1
    assert abs(first["ate"] - 1.75) < 0.06
    assert second["ate"] == first["ate"]
    assert second["standard_error"] == first["standard_error"] > 0.0
    assert second["nuisance_diagnostics"]["coverage_guard_triggered"] is True
    assert first["nuisance_diagnostics"]["coverage_guard_triggered"] is False
    assert second["ci_upper"] - second["ci_lower"] > first["ci_upper"] - first["ci_lower"]
    assert second["nuisance_contract"]["min_effective_sample_size"] == 1000.0
    shifted = estimator.pure_step({**state, "outcome": y + 0.6 * t}, params)["result"]
    assert len(observed_native_fits) == 2
    assert shifted["ate"] - first["ate"] == pytest.approx(0.6, abs=1e-10)
    null_treatment = np.random.default_rng(91).permutation(t)
    negative = estimator.pure_step({**state, "treatment": null_treatment}, params)["result"]
    assert abs(negative["ate"]) < 0.3
    assert len(observed_native_fits) == 3


def test_parallelism_preserves_native_crossfit_plan_and_measured_uncertainty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B56 bounded: real folds are disjoint and external cap preserves results."""
    x, t, y = _data()
    params = _contract().as_contract_payload()
    params.update(
        crossfit_folds=3,
        n_repeats=2,
        random_seed_manifest=[17, 211],
        __disable_shared_nuisance_cache=True,
    )
    native_fold = tmle_core._fit_crossfit_fold
    executions: dict[str, list[tuple[int, int, tuple[int, ...]]]] = {}
    active = 0
    peak_active = 0
    lock = threading.Lock()
    run_name = "serial"

    def observe(**kwargs: Any) -> dict[str, Any]:
        nonlocal active, peak_active
        heldout = np.asarray(kwargs["test_idx"])
        fit_indices = np.asarray(kwargs["fit_idx"])
        calibration = np.asarray(kwargs["calib_idx"])
        assert not np.intersect1d(fit_indices, heldout).size
        assert not np.intersect1d(calibration, heldout).size
        assert not np.intersect1d(fit_indices, calibration).size
        assert len(np.union1d(np.union1d(fit_indices, calibration), heldout)) == len(y)
        with lock:
            active += 1
            peak_active = max(peak_active, active)
            executions.setdefault(run_name, []).append(
                (kwargs["rep_seed"], kwargs["fold_id"], tuple(heldout.tolist()))
            )
        try:
            return native_fold(**kwargs)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(tmle_core, "_fit_crossfit_fold", observe)
    serial, serial_bundle = tmle_core.fit_tmle_ate(x, t, y, params)
    run_name = "parallel"
    parallel, parallel_bundle = tmle_core.fit_tmle_ate(
        x, t, y, {**params, "parallel_folds": True, "max_parallel_folds": 2}
    )
    run_name = "external-cap-one"
    peak_active = 0
    with ThreadPoolExecutor(max_workers=1) as external_resource:
        submitted = [
            external_resource.submit(
                tmle_core.fit_tmle_ate,
                x,
                t,
                y,
                {**params, "parallel_folds": True, "max_parallel_folds": 1},
            )
            for _ in range(2)
        ]
        external_results = [future.result(timeout=30) for future in submitted]
    assert peak_active == 1
    expected = sorted(executions["serial"])
    assert sorted(executions["parallel"]) == expected
    assert sorted(executions["external-cap-one"]) == sorted(expected * 2)
    for seed in (17, 211):
        heldout_indices = [i for s, _, indices in expected if s == seed for i in indices]
        assert sorted(heldout_indices) == list(range(len(y)))
    assert serial_bundle.split_manifest == parallel_bundle.split_manifest
    for result, bundle in [(parallel, parallel_bundle), *external_results]:
        _assert_native_backend(bundle)
        assert bundle.split_manifest == serial_bundle.split_manifest
        for name in ("propensity", "mu1", "mu0", "trim_mask"):
            np.testing.assert_array_equal(getattr(bundle, name), getattr(serial_bundle, name))
        for name in ("ate", "standard_error", "ci_lower", "ci_upper"):
            assert getattr(result, name) == getattr(serial, name)
        np.testing.assert_array_equal(result.eif_values, serial.eif_values)
        assert result.standard_error > 0.0
