"""Test-first witnesses for the FIT-01 nuisance fit-core contract.

The B54 witnesses use a synthetic cached bundle and monkeypatch the uncached
fit boundary, so they exercise cache identity, contract rebinding, and
ownership without fitting a model.  The B56 witness replaces one fold with a
small deterministic callback and checks that an explicit worker cap does not
drop folds, repeats, or seeds.

These are intentionally lightweight L-job selectors.  A future native seam
must remain a separate N/C selector; it must exercise one bounded real fit in
K4 and must not be inferred from this synthetic corpus.

Expected current-base controls: the diagnostic-rebind and consumer-isolation
tests are RED; data/seed invalidation and explicit-cap-one preservation are
positive controls expected to stay GREEN.
"""

from __future__ import annotations

import threading
import time
from contextlib import suppress
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

import polisyos.foundry.methods.catalog.causal.tmle_core as tmle_core

pytestmark = pytest.mark.unit


def _inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return a deterministic small input set for cache-key witnesses."""
    covariates = np.asarray(
        [
            [-1.0, 0.0],
            [-0.5, 1.0],
            [0.0, -1.0],
            [0.5, 0.5],
            [1.0, -0.5],
            [1.5, 1.0],
        ],
        dtype=float,
    )
    treatment = np.asarray([0.0, 1.0, 0.0, 1.0, 0.0, 1.0], dtype=float)
    outcome = np.asarray([0.0, 1.5, 0.5, 2.0, 1.0, 2.5], dtype=float)
    return covariates, treatment, outcome


def _contract(**changes: Any) -> tmle_core.ATENuisanceContract:
    """Build a small, stable contract while making changes explicit."""
    return tmle_core.ATENuisanceContract(
        crossfit_folds=2,
        n_repeats=2,
        random_seed=17,
        parallel_folds=True,
        max_parallel_folds=1,
        **changes,
    )


def _synthetic_bundle(
    covariates: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    contract: tmle_core.ATENuisanceContract,
) -> tmle_core.ATENuisanceBundle:
    """Create a fit-like bundle without invoking a model backend."""
    del covariates, treatment, outcome
    scaler = SimpleNamespace(mean=0.0, scale=1.0, applied=False)
    return tmle_core.ATENuisanceBundle(
        propensity=np.asarray([0.25, 0.50, 0.75, 0.25, 0.50, 0.75], dtype=float),
        mu1=np.asarray([1.0, 1.1, 1.2, 1.3, 1.4, 1.5], dtype=float),
        mu0=np.asarray([0.2, 0.3, 0.4, 0.5, 0.6, 0.7], dtype=float),
        trim_mask=np.ones(6, dtype=bool),
        scaler=scaler,
        contract=contract,
        split_manifest=[
            {"repeat": 0, "seed": contract.random_seed, "folds": [{"fold": 0}]}
        ],
        calibration_modes=["none"],
        propensity_backends=["synthetic"],
        outcome_backends=["synthetic"],
        selection_manifest=[{"selected": "synthetic"}],
    )


@pytest.fixture
def isolated_shared_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep each witness independent of process-global cache state."""
    monkeypatch.setattr(tmle_core, "_SHARED_NUISANCE_CACHE", {})
    monkeypatch.setattr(tmle_core, "_SHARED_NUISANCE_CACHE_ORDER", [])


def test_diagnostic_contract_change_reuses_fit_and_rebinds_current_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    isolated_shared_cache: None,
) -> None:
    """B54: threshold/mode changes reuse fit bytes but refresh diagnostics."""
    covariates, treatment, outcome = _inputs()
    calls: list[tmle_core.ATENuisanceContract] = []

    def fake_uncached(
        fit_covariates: np.ndarray,
        fit_treatment: np.ndarray,
        fit_outcome: np.ndarray,
        contract: tmle_core.ATENuisanceContract,
    ) -> tmle_core.ATENuisanceBundle:
        calls.append(contract)
        return _synthetic_bundle(fit_covariates, fit_treatment, fit_outcome, contract)

    monkeypatch.setattr(tmle_core, "_fit_crossfit_nuisance_bundle_uncached", fake_uncached)

    cold_contract = _contract(min_effective_sample_size=48.0, coverage_guard="ess_aware")
    warm_contract = replace(
        cold_contract,
        min_effective_sample_size=100.0,
        coverage_guard="off",
    )
    cold = tmle_core.fit_crossfit_nuisance_bundle(
        covariates, treatment, outcome, cold_contract
    )
    warm = tmle_core.fit_crossfit_nuisance_bundle(
        covariates, treatment, outcome, warm_contract
    )

    assert len(calls) == 1
    assert warm is not cold
    assert np.array_equal(warm.propensity, cold.propensity)
    assert cold.contract.min_effective_sample_size == 48.0
    assert cold.contract.coverage_guard == "ess_aware"
    assert warm.contract.min_effective_sample_size == 100.0
    assert warm.contract.coverage_guard == "off"
    assert warm.diagnostics()["min_effective_sample_size"] == 100.0
    assert warm.diagnostics()["coverage_guard"] == "off"


def test_cached_fit_isolation_prevents_one_consumer_mutating_the_next_hit(
    monkeypatch: pytest.MonkeyPatch,
    isolated_shared_cache: None,
) -> None:
    """B54: arrays and nested metadata are owned by one returned hit."""
    covariates, treatment, outcome = _inputs()
    contract = _contract()

    monkeypatch.setattr(
        tmle_core,
        "_fit_crossfit_nuisance_bundle_uncached",
        lambda covariates, treatment, outcome, contract: _synthetic_bundle(
            covariates,
            treatment,
            outcome,
            contract,
        ),
    )

    first = tmle_core.fit_crossfit_nuisance_bundle(
        covariates, treatment, outcome, contract
    )
    expected_propensity = first.propensity.copy()
    expected_manifest = deepcopy(first.split_manifest)

    # A read-only fit core is an accepted implementation of the boundary.
    with suppress(ValueError):
        first.propensity[0] = 0.99

    # A deeply immutable metadata projection is also a valid boundary.
    with suppress(AttributeError, TypeError):
        first.split_manifest[0]["folds"].append({"fold": 99})

    with suppress(AttributeError, TypeError):
        first.calibration_modes.append("consumer-mutation")

    second = tmle_core.fit_crossfit_nuisance_bundle(
        covariates, treatment, outcome, contract
    )

    assert second is not first
    assert np.array_equal(second.propensity, expected_propensity)
    assert len(second.split_manifest) == len(expected_manifest) == 1
    assert len(second.split_manifest[0]["folds"]) == 1
    assert (
        second.split_manifest[0]["folds"][0]["fold"]
        == expected_manifest[0]["folds"][0]["fold"]
    )
    assert "consumer-mutation" not in second.calibration_modes


@pytest.mark.parametrize("changed_dimension", ["data", "seed"])
def test_changed_data_or_seed_requires_a_new_fit(
    monkeypatch: pytest.MonkeyPatch,
    isolated_shared_cache: None,
    changed_dimension: str,
) -> None:
    """B54 positive control: scientific inputs never reuse an old fit core."""
    covariates, treatment, outcome = _inputs()
    calls: list[tuple[np.ndarray, int]] = []

    def fake_uncached(
        fit_covariates: np.ndarray,
        fit_treatment: np.ndarray,
        fit_outcome: np.ndarray,
        contract: tmle_core.ATENuisanceContract,
    ) -> tmle_core.ATENuisanceBundle:
        del fit_treatment, fit_outcome
        calls.append((fit_covariates.copy(), contract.random_seed))
        return _synthetic_bundle(fit_covariates, treatment, outcome, contract)

    monkeypatch.setattr(tmle_core, "_fit_crossfit_nuisance_bundle_uncached", fake_uncached)
    contract = _contract()
    tmle_core.fit_crossfit_nuisance_bundle(
        covariates, treatment, outcome, contract
    )

    if changed_dimension == "data":
        changed_covariates = covariates.copy()
        changed_covariates[0, 0] += 1.0
        changed_contract = contract
    else:
        changed_covariates = covariates
        changed_contract = replace(contract, random_seed=contract.random_seed + 1)

    tmle_core.fit_crossfit_nuisance_bundle(
        changed_covariates,
        treatment,
        outcome,
        changed_contract,
    )

    assert len(calls) == 2
    assert not np.array_equal(calls[0][0], calls[1][0]) or calls[0][1] != calls[1][1]


def test_explicit_cap_one_preserves_all_fold_repeat_seeds_without_model_training(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B56: worker cap changes execution, not the scientific cross-fit plan."""
    covariates = np.arange(24, dtype=float).reshape(12, 2)
    treatment = np.asarray([0.0, 1.0] * 6, dtype=float)
    outcome = np.linspace(0.0, 1.0, 12)
    contract = tmle_core.ATENuisanceContract(
        crossfit_folds=3,
        n_repeats=2,
        random_seed=31,
        random_seed_manifest=(31, 211),
        parallel_folds=True,
        max_parallel_folds=1,
    )
    active = 0
    max_active = 0
    active_lock = threading.Lock()
    seen: list[tuple[int, int]] = []

    def fake_fold(**kwargs: Any) -> dict[str, Any]:
        nonlocal active, max_active
        with active_lock:
            active += 1
            max_active = max(max_active, active)
            seen.append((int(kwargs["rep_seed"]), int(kwargs["fold_id"])))
        try:
            # This is deliberately tiny; it creates overlap opportunities if
            # a future implementation ignores the explicit cap.
            time.sleep(0.002)
            test_idx = np.asarray(kwargs["test_idx"], dtype=int)
            fold_id = int(kwargs["fold_id"])
            rep_seed = int(kwargs["rep_seed"])
            return {
                "test_idx": test_idx,
                "propensity": np.full(test_idx.size, 0.5),
                "mu1": np.full(test_idx.size, 1.0 + fold_id),
                "mu0": np.full(test_idx.size, 0.25 + (rep_seed % 7) / 100.0),
                "prop_backend": "synthetic",
                "calibration_mode": "none",
                "outcome_backends": ["synthetic", "synthetic"],
                "selection_records": [],
            }
        finally:
            with active_lock:
                active -= 1

    monkeypatch.setattr(tmle_core, "_fit_crossfit_fold", fake_fold)

    capped = tmle_core._fit_crossfit_nuisance_bundle_uncached(
        covariates, treatment, outcome, contract
    )
    serial = tmle_core._fit_crossfit_nuisance_bundle_uncached(
        covariates,
        treatment,
        outcome,
        replace(contract, parallel_folds=False),
    )

    assert max_active == 1
    assert sorted(seen[: contract.crossfit_folds * contract.n_repeats]) == sorted(
        (seed, fold)
        for seed in contract.random_seed_manifest
        for fold in range(contract.crossfit_folds)
    )
    assert capped.split_manifest == serial.split_manifest
    assert np.array_equal(capped.propensity, serial.propensity)
    assert np.array_equal(capped.mu1, serial.mu1)
    assert np.array_equal(capped.mu0, serial.mu0)


@pytest.mark.slow
def test_native_fit_preserves_all_folds_repeats_and_seeds() -> None:
    """Future N/C seam: one bounded real fit keeps the complete study plan."""
    covariates, treatment, outcome = _inputs()
    contract = tmle_core.ATENuisanceContract(
        propensity_backend="logistic_regression",
        outcome_backend="linear_regression",
        calibration_mode="none",
        min_calibration_size=0,
        crossfit_folds=2,
        n_repeats=2,
        random_seed=31,
        random_seed_manifest=(31, 211),
        parallel_folds=True,
        max_parallel_folds=1,
    )

    bundle = tmle_core.fit_crossfit_nuisance_bundle(
        covariates,
        treatment,
        outcome,
        contract,
        {"__disable_shared_nuisance_cache": True},
    )

    assert len(bundle.split_manifest) == contract.n_repeats
    assert [entry["seed"] for entry in bundle.split_manifest] == [31, 211]
    assert all(
        len(entry["folds"]) == contract.crossfit_folds
        for entry in bundle.split_manifest
    )
    assert bundle.propensity.shape == treatment.shape
    assert np.all(np.isfinite(bundle.propensity))
    assert np.all(np.isfinite(bundle.mu1))
    assert np.all(np.isfinite(bundle.mu0))
