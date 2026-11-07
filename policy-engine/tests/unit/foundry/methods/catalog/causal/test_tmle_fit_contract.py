"""Behavioral witnesses for content-bound nuisance reuse and bounded targeting."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import threading
import time
from dataclasses import fields, replace

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal import tmle_core as core
from polisyos.foundry.methods.catalog.causal.treatment_effects import TMLEEstimator


def _dgp(seed: int = 73, n: int = 600) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    w = rng.choice([-1.0, 1.0], size=n)
    a = rng.binomial(1, 0.5, size=n).astype(float)
    # Q0(w)=.25+.1w, Q1(w)=.55+.1w: analytic population ATE=.30.
    y = rng.binomial(1, 0.25 + 0.1 * w + 0.3 * a).astype(float)
    return w[:, None], a, y


def _params(**changes: object) -> dict[str, object]:
    return {
        "propensity_backend": "logistic",
        "outcome_backend": "linear",
        "calibration_mode": "none",
        "outcome_scaling": "raw",
        "crossfit_folds": 3,
        "n_repeats": 2,
        "random_seed": 18,
        "ci_mode": "wald",
        "inference_profile": "regular_iid",
        "coverage_guard": "off",
        **changes,
    }


@pytest.fixture(autouse=True)
def _isolated_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(core, "_SHARED_NUISANCE_CACHE", {})
    monkeypatch.setattr(core, "_SHARED_NUISANCE_CACHE_ORDER", [])


def _start_pool_parent_context(store, bundle, run_id: str):
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

    run = RunContext.start(
        store=store,
        registry_bundle=bundle.bundle_ref,
        run_id=run_id,
        run_dir=store.root / "runs" / run_id,
        tenant_id=store._tenant_id,
        cell_id=store._cell_id,
    )
    return ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"test.tmle_pool.{run_id}"),
    )


def _bound_pool_task(node, alias: str, state, parent_context, *, priority: int = 0):
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        serialize_state,
        serialize_timeout_context,
        worker_dispatch_sha256,
    )
    from polisyos.scientist.orchestration.engine.runner.worker_pool import NodeTask

    state_bytes = serialize_state(state)
    context_meta = serialize_timeout_context(parent_context, expected_run_id=state.run_id)
    dispatch = {
        "node_id": str(node.spec.metadata.component_id),
        "alias": alias,
        "params": {},
        "state_bytes": state_bytes,
        "trace_carrier": {},
        "timeout_s": None,
        "max_retries": 0,
        "context_meta": context_meta,
    }
    return NodeTask(
        node_id=dispatch["node_id"],
        alias=alias,
        params={},
        state_bytes=state_bytes,
        trace_carrier={},
        context_meta=context_meta,
        priority=priority,
        worker_invocation_id=secrets.token_hex(32),
        worker_dispatch_sha256=worker_dispatch_sha256(**dispatch),
    )


def _current_native_study_result(x, treatment, outcome, *, study: str, fitting_params=None):
    """Exercise the actual fit once, then rebind only its diagnostic policy."""
    from polisyos.common.serialization import to_python_data

    cold_params = _params(
        __shared_nuisance_key=study,
        min_effective_sample_size=48,
        coverage_guard="ess_aware",
        **(fitting_params or {}),
    )
    source = {"X": x, "treatment": treatment, "outcome": outcome}
    cold = TMLEEstimator.pure_step(source, cold_params)
    current_params = {**cold_params, "min_effective_sample_size": 100, "coverage_guard": "off"}
    current = TMLEEstimator.pure_step(source, current_params)
    old_diagnostics = cold["result"]["nuisance_diagnostics"]
    current_diagnostics = current["result"]["nuisance_diagnostics"]
    assert old_diagnostics["fit_identity"] == current_diagnostics["fit_identity"]
    assert old_diagnostics["min_effective_sample_size"] == 48
    assert old_diagnostics["coverage_guard"] == "ess_aware"
    assert current_diagnostics["min_effective_sample_size"] == 100
    assert current_diagnostics["coverage_guard"] == "off"
    assert current["report"].method_params["min_effective_sample_size"] == 100
    assert current["report"].method_params["coverage_guard"] == "off"
    return to_python_data(current, sort_keys=True)


def _persist_native_study(ctx, x, treatment, outcome, payload):
    from polisyos.core.artifacts.manifest import InputRef
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.canon import CanonSpec

    source_ref = ctx.store.put_json(
        {"X": x.tolist(), "treatment": treatment.tolist(), "outcome": outcome.tolist()},
        PutOptions(kind="test.tmle_source", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return ctx.store.put_json(
        {**payload, "source_ref": source_ref.model_dump(mode="json")},
        PutOptions(
            kind="test.tmle_result",
            media_type="application/json",
            inputs=[
                InputRef(
                    artifact_id=source_ref.artifact_id,
                    role="input:causal_observations",
                    manifest_profile_sha256=source_ref.manifest_profile_sha256,
                )
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _read_current_native_study(reader, ref):
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.ir.analytics.causal import CausalEffectReport
    from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope

    payload = from_canonical_bytes(reader.get_bytes(ref))
    result = payload["result"]
    report = CausalEffectReport.model_validate(payload["report"])
    envelope = UncertaintyEnvelope.model_validate(payload["envelope"])
    source_ref = ArtifactRef.model_validate(payload["source_ref"])
    source = from_canonical_bytes(reader.get_bytes(source_ref))
    manifest_input = reader.get_manifest(ref).inputs[0]
    assert manifest_input.artifact_id == source_ref.artifact_id
    assert manifest_input.manifest_profile_sha256 == source_ref.manifest_profile_sha256
    assert result["nuisance_diagnostics"]["fit_identity"] == core._fit_identity(
        np.asarray(source["X"], dtype=float),
        np.asarray(source["treatment"], dtype=float),
        np.asarray(source["outcome"], dtype=float),
        core.ATENuisanceContract.from_params(result["nuisance_contract"]),
    )
    assert report.point_estimate == result["ate"]
    assert report.confidence_interval == (result["ci_lower"], result["ci_upper"])
    assert report.method_params["min_effective_sample_size"] == 100
    assert report.method_params["coverage_guard"] == "off"
    assert result["nuisance_diagnostics"]["min_effective_sample_size"] == 100
    assert result["nuisance_diagnostics"]["coverage_guard"] == "off"
    assert report.metadata["assumption_basis"] == "consumer_asserted"
    assert report.metadata["gate_eligible"] is False
    assert result["gate_eligible"] is False
    assert envelope == report.to_uncertainty_envelope()
    assert envelope.gate_eligible is False
    return payload


def test_native_cold_warm_rebind_and_reader_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    x, a, y = _dgp()
    calls = []
    native = core._fit_crossfit_fold

    def observe(**kwargs):
        calls.append((kwargs["rep_seed"], kwargs["fold_id"]))
        return native(**kwargs)

    monkeypatch.setattr(core, "_fit_crossfit_fold", observe)
    params = _params(__shared_nuisance_key="study")
    contract = core.ATENuisanceContract.from_params(params)
    first = core.fit_crossfit_nuisance_bundle(x, a, y, contract, params)
    assert len(calls) == 6
    updated = replace(
        contract,
        min_effective_sample_size=1000,
        coverage_guard="ess_aware",
        overlap_diagnostic_policy="current-report-policy",
    )
    second = core.fit_crossfit_nuisance_bundle(x, a, y, updated, params)
    assert len(calls) == 6
    assert second.diagnostics()["min_effective_sample_size"] == 1000
    assert second.contract is updated
    assert first.contract is contract
    assert all(r["split_policy"] == "current-report-policy" for r in second.selection_manifest)
    for name in ("propensity", "mu1", "mu0", "trim_mask"):
        array = getattr(second, name)
        expected = array.copy()
        with pytest.raises(ValueError):
            array.setflags(write=True)
        array.shape = (1, array.size)
        fresh = core.fit_crossfit_nuisance_bundle(x, a, y, updated, params)
        np.testing.assert_array_equal(getattr(fresh, name), expected)
    second.selection_manifest[0]["split_policy"] = "corrupt-reader"
    fresh = core.fit_crossfit_nuisance_bundle(x, a, y, updated, params)
    assert fresh.selection_manifest[0]["split_policy"] == "current-report-policy"


@pytest.mark.parametrize("scaling", ["standardized", "raw+standardized", "raw", "auto"])
def test_continuous_nuisance_preprocessing_belongs_to_the_fit_fold(
    scaling: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A held-out outcome may change targeting, but cannot train its own nuisance."""
    n = 96
    x = np.linspace(-2.0, 2.0, n)[:, None]
    treatment = (np.arange(n) % 2).astype(float)
    outcome = 1.7 * x[:, 0] + 0.4 * treatment + 0.15 * np.sin(3 * x[:, 0])
    params = _params(
        outcome_backend="elastic_net",
        outcome_scaling=scaling,
        outcome_family="continuous",
        n_repeats=1,
        __shared_nuisance_key="continuous-fold-preprocessing",
    )
    contract = core.ATENuisanceContract.from_params(params)
    calls = []
    native = core._fit_crossfit_fold

    def observe(**kwargs):
        result = native(**kwargs)
        calls.append(
            {
                "fit_idx": kwargs["fit_idx"].copy(),
                "calib_idx": kwargs["calib_idx"].copy(),
                "test_idx": kwargs["test_idx"].copy(),
                "scaler": kwargs["scaler"],
                "result": result,
            }
        )
        return result

    monkeypatch.setattr(core, "_fit_crossfit_fold", observe)
    first = core.fit_crossfit_nuisance_bundle(x, treatment, outcome, contract, params)
    first_fold = calls[0]
    assert len(calls) == 3
    assert first_fold["result"]["outcome_backends"] == ["elastic_net", "elastic_net"]
    test_idx = first_fold["test_idx"]
    fit_idx = first_fold["fit_idx"]
    assert not np.intersect1d(test_idx, fit_idx).size

    heldout_changed = outcome.copy()
    heldout_changed[test_idx] += 30.0 * (1.0 + x[test_idx, 0])
    second = core.fit_crossfit_nuisance_bundle(x, treatment, heldout_changed, contract, params)
    second_fold = calls[3]
    assert len(calls) == 6  # Same label never licenses reuse after an actual Y change.
    assert first.fit_identity != second.fit_identity
    for arm in ("mu0", "mu1"):
        np.testing.assert_allclose(
            second_fold["result"][arm], first_fold["result"][arm], rtol=1e-12, atol=1e-12
        )
    assert second_fold["result"]["outcome_backends"] == first_fold["result"]["outcome_backends"]
    assert second_fold["scaler"] == first_fold["scaler"]
    assert first_fold["scaler"].mean == pytest.approx(np.mean(outcome[fit_idx]))
    assert first_fold["scaler"].scale == pytest.approx(np.std(outcome[fit_idx]))
    if scaling == "auto":
        assert not first_fold["scaler"].applied
        # The same held-out change would flip a forbidden full-data decision.
        assert np.std(heldout_changed) > 10.0
    recorded = first.split_manifest[0]["folds"][0]["outcome_preprocessing"]
    assert recorded["fit_indices_digest"] == core._hash_array(fit_idx)
    assert recorded["test_indices_digest"] == core._hash_array(test_idx)
    assert recorded["scope"] == "fold_fit_only"
    assert recorded["mean"] == first_fold["scaler"].mean
    assert recorded["scale"] == first_fold["scaler"].scale
    assert first.diagnostics()["outcome_scaler"]["scope"] == "targeting_reference_only"

    # The same actual fit must react to training outcomes, so invariance is not
    # a constant-output or cache-hit artifact.
    train_changed = outcome.copy()
    train_changed[fit_idx] += 2.0 * x[fit_idx, 0]
    third = core.fit_crossfit_nuisance_bundle(x, treatment, train_changed, contract, params)
    third_fold = calls[6]
    assert len(calls) == 9
    assert third.fit_identity not in {first.fit_identity, second.fit_identity}
    assert np.max(np.abs(third_fold["result"]["mu1"] - first_fold["result"]["mu1"])) > 0.1

    current = core.fit_crossfit_nuisance_bundle(
        x, treatment, outcome, replace(contract, min_effective_sample_size=1000), params
    )
    assert len(calls) == 9
    assert current.fit_identity == first.fit_identity
    assert current.diagnostics()["min_effective_sample_size"] == 1000
    assert first.diagnostics()["min_effective_sample_size"] == contract.min_effective_sample_size
    np.testing.assert_array_equal(current.mu1, first.mu1)
    current.split_manifest[0]["folds"][0]["outcome_preprocessing"]["mean"] = 900.0
    fresh = core.fit_crossfit_nuisance_bundle(x, treatment, outcome, contract, params)
    assert fresh.split_manifest[0]["folds"][0]["outcome_preprocessing"] == recorded


@pytest.mark.parametrize("scaling", ["raw", "standardized"])
def test_empty_arm_nuisance_fallback_uses_only_permitted_fold_fit_rows(scaling: str) -> None:
    """An absent arm cannot import held-out outcomes through its constant fallback."""
    x = np.arange(6, dtype=float)[:, None]
    treatment = np.array([0.0, 0.0, 0.0, 0.0, 1.0, 1.0])
    outcome = np.array([1.0, 2.0, 3.0, 4.0, 20.0, 30.0])
    fit_idx = np.arange(4)
    test_idx = np.array([4, 5])
    contract = core.ATENuisanceContract.from_params(_params(outcome_scaling=scaling))

    def fold(y):
        scaler = core.fit_outcome_scaler(y[fit_idx], scaling)
        return core._fit_crossfit_fold(
            X=x,
            T=treatment,
            Y_scaled=core.scale_outcome(y, scaler),
            scaler=scaler,
            contract=contract,
            rep_seed=18,
            fold_id=0,
            fit_idx=fit_idx,
            calib_idx=np.array([], dtype=int),
            test_idx=test_idx,
        )

    first = fold(outcome)
    changed = outcome.copy()
    changed[test_idx] += 900.0
    second = fold(changed)
    assert first["outcome_backends"][0] == "constant"
    np.testing.assert_allclose(first["mu1"], np.mean(outcome[fit_idx]), rtol=0.0, atol=1e-12)
    np.testing.assert_array_equal(first["mu1"], second["mu1"])
    np.testing.assert_array_equal(first["mu0"], second["mu0"])
    assert first["selection_records"][1]["fallback_indices_digest"] == core._hash_array(fit_idx)
    changed[fit_idx] += 2.0
    third = fold(changed)
    np.testing.assert_allclose(third["mu1"], first["mu1"] + 2.0, rtol=0.0, atol=1e-12)


def test_outcome_nuisance_without_permitted_training_rows_refuses() -> None:
    with pytest.raises(ValueError, match="no permitted fold-fit support"):
        core._fit_regression_backend(
            np.arange(4, dtype=float)[:, None],
            np.arange(4, dtype=float),
            np.array([], dtype=int),
            np.array([0, 1]),
            core.ATENuisanceContract.from_params(_params()),
            seed=18,
        )


@pytest.mark.parametrize("axis", ["X", "T", "Y", "seed", "folds", "model", "split"])
def test_same_caller_label_does_not_bypass_fit_identity(axis: str) -> None:
    x, a, y = _dgp(n=120)
    params = _params(__shared_nuisance_key="same-label", n_repeats=1)
    contract = core.ATENuisanceContract.from_params(params)
    original = core.fit_crossfit_nuisance_bundle(x, a, y, contract, params)
    x2, a2, y2 = x.copy(), a.copy(), y.copy()
    updated = contract
    if axis == "X":
        x2[0] += 0.25
    elif axis == "T":
        a2[0] = 1 - a2[0]
    elif axis == "Y":
        y2[0] = 1 - y2[0]
    elif axis == "seed":
        updated = replace(contract, random_seed=41)
    elif axis == "folds":
        updated = replace(contract, crossfit_folds=4)
    elif axis == "model":
        updated = replace(contract, outcome_backend="elastic_net")
    elif axis == "split":
        updated = replace(contract, calibration_fraction=0.3)
    changed = core.fit_crossfit_nuisance_bundle(x2, a2, y2, updated, params)
    assert changed.fit_identity != original.fit_identity
    assert len(core._SHARED_NUISANCE_CACHE) == 2


def test_precomputed_bundle_is_content_bound_and_reader_isolated() -> None:
    x, a, y = _dgp(n=120)
    params = _params(n_repeats=1)
    contract = core.ATENuisanceContract.from_params(params)
    bundle = core.fit_crossfit_nuisance_bundle(x, a, y, contract, params)
    precomputed = {**params, "__shared_nuisance_bundle": bundle}
    accepted = core.fit_crossfit_nuisance_bundle(x, a, y, contract, precomputed)
    assert accepted is not bundle
    bundle.mu1 = np.full(y.size, 900.0)
    verified = core.fit_crossfit_nuisance_bundle(x, a, y, contract, precomputed)
    assert np.max(verified.mu1) < 2  # offered predictions do not override the issued core
    changed = y.copy()
    changed[0] = 1 - changed[0]
    with pytest.raises(ValueError, match="identity"):
        core.fit_crossfit_nuisance_bundle(x, a, changed, contract, precomputed)
    bundle.fit_identity = None
    with pytest.raises(ValueError, match="identity"):
        core.fit_crossfit_nuisance_bundle(x, a, y, contract, precomputed)


@pytest.mark.parametrize("name", ["DRLearnerEstimator", "RLearnerEstimator"])
def test_sibling_meta_learners_resolve_offered_predictions_from_the_controlled_core(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sibling consumer cannot use mutable offered predictions as fit authority."""
    from polisyos.foundry.methods.catalog.causal import advanced_designs

    x, treatment, outcome = _dgp(n=120)
    params = _params(n_repeats=1, nuisance_model_family="linear", bootstrap_draws=20)
    contract = core.ATENuisanceContract.from_params(params)
    calls = []
    native = core._fit_crossfit_fold

    def observe(**kwargs):
        calls.append((kwargs["rep_seed"], kwargs["fold_id"]))
        return native(**kwargs)

    monkeypatch.setattr(core, "_fit_crossfit_fold", observe)
    offered = core.fit_crossfit_nuisance_bundle(x, treatment, outcome, contract, params)
    current = {
        **params,
        "__shared_nuisance_bundle": offered,
        "min_effective_sample_size": 100,
        "coverage_guard": "off",
    }
    estimator = getattr(advanced_designs, name)
    state = {"X": x, "treatment": treatment, "outcome": outcome}
    baseline = estimator.pure_step(state, current)["result"]
    assert np.isfinite(baseline["ate"])
    offered.mu1 = np.full(outcome.size, 900.0)
    offered.scaler = replace(offered.scaler, mean=900.0)
    offered.selection_manifest.clear()
    replay = estimator.pure_step(state, current)["result"]
    assert replay == baseline
    assert len(calls) == 3
    core_info = replay["nuisance_diagnostics"]["backend_info"]
    assert core_info["fit_identity"] == offered.fit_identity
    assert core_info["native_contract"]["min_effective_sample_size"] == 100
    assert offered.contract.min_effective_sample_size == contract.min_effective_sample_size
    different_outcome = outcome.copy()
    different_outcome[0] = 1 - different_outcome[0]
    wrong_state = {**state, "outcome": different_outcome}
    if name == "DRLearnerEstimator":
        refused = estimator.pure_step(wrong_state, current)["result"]
        assert refused["failed"] is True
        assert "identity" in refused["fail_reason"]
        assert not np.isfinite(refused["ate"])
    else:
        with pytest.raises(ValueError, match="identity"):
            estimator.pure_step(wrong_state, current)
    assert len(calls) == 3
    assert len(core._SHARED_NUISANCE_CACHE) == 1


@pytest.mark.parametrize("change", ["source", "unknown_identity", "evicted_core"])
def test_sibling_nuisance_resolver_cannot_fallback_after_offered_core_refusal(change: str) -> None:
    from polisyos.foundry.methods.catalog.causal import advanced_designs

    x, treatment, outcome = _dgp(n=120)
    params = _params(n_repeats=1, nuisance_model_family="linear")
    contract = core.ATENuisanceContract.from_params(params)
    offered = core.fit_crossfit_nuisance_bundle(x, treatment, outcome, contract, params)
    if change == "source":
        outcome = outcome.copy()
        outcome[0] = 1 - outcome[0]
    elif change == "unknown_identity":
        offered.fit_identity = "unissued-fit"
    else:
        core._SHARED_NUISANCE_CACHE.clear()
        core._SHARED_NUISANCE_CACHE_ORDER.clear()
    with pytest.raises(ValueError, match="identity|controlled|issued"):
        advanced_designs._resolve_nuisance_outputs(
            x, treatment, outcome, params={**params, "__shared_nuisance_bundle": offered}
        )


def test_native_binary_target_score_ate_and_eif_oracle() -> None:
    x, a, y = _dgp(n=3000)
    result, bundle = core.fit_tmle_ate(x, a, y, _params())
    summary = result.targeting_summary
    assert summary["fluctuation_link"] == "logit"
    assert summary["converged"]
    assert abs(summary["targeting_score"]) < 1e-8
    assert 0 <= summary["targeted_q_min"] <= summary["targeted_q_max"] <= 1
    assert abs(result.ate - 0.3) < 0.06
    assert result.ci_lower < 0.3 < result.ci_upper
    independent_se = np.std(result.eif_values, ddof=1) / np.sqrt(len(y))
    assert result.standard_error == pytest.approx(independent_se)
    assert result.ci_upper - result.ate == pytest.approx(1.959963984540054 * independent_se)
    assert result.interval_method == "wald_eif_regular_iid"
    assert len(bundle.split_manifest) == 2
    assert sum(len(r["folds"]) for r in bundle.split_manifest) == 6


def test_poor_bounded_initial_predictions_use_logit_not_clipped_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    x, a, y = _dgp()
    contract = core.ATENuisanceContract.from_params(_params())
    native = core.fit_crossfit_nuisance_bundle(x, a, y, contract)
    native.mu1 = np.full(y.size, 0.01)
    native.mu0 = np.full(y.size, 0.99)
    monkeypatch.setattr(core, "fit_crossfit_nuisance_bundle", lambda *args: native)
    result, _ = core.fit_tmle_ate(x, a, y, _params(outcome_family="bounded"))
    summary = result.targeting_summary
    assert summary["fluctuation_link"] == "logit"
    assert abs(summary["targeting_score"]) < 1e-8
    assert 0 <= summary["targeted_q_min"] <= summary["targeted_q_max"] <= 1
    assert -1 <= result.ate <= 1


def test_observed_positivity_failure_is_limited_at_actual_method_consumer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    x, a, y = _dgp()
    contract = core.ATENuisanceContract.from_params(_params())
    native = core.fit_crossfit_nuisance_bundle(x, a, y, contract)
    native.propensity = np.full(y.size, contract.propensity_clipping)
    monkeypatch.setattr(core, "fit_crossfit_nuisance_bundle", lambda *args: native)
    payload = TMLEEstimator.pure_step({"X": x, "treatment": a, "outcome": y}, _params())
    output = payload["result"]
    assert output["status"] == "limited"
    assert output["gate_eligible"] is False
    assert output["ci_lower"] is None and output["ci_upper"] is None
    assert "observed_positivity_failure" in output["inference_limitations"]


@pytest.mark.parametrize("max_parallel_folds", [0, 1, 2])
def test_effective_fold_policy_retains_all_folds_and_native_results(
    max_parallel_folds: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    x, a, y = _dgp(n=240)
    calls = []
    native = core._fit_crossfit_fold

    def observe(**kwargs):
        calls.append((kwargs["rep_seed"], kwargs["fold_id"], kwargs["test_idx"].tolist()))
        return native(**kwargs)

    monkeypatch.setattr(core, "_fit_crossfit_fold", observe)
    serial, _ = core.fit_tmle_ate(x, a, y, _params(parallel_folds=False))
    assert len(calls) == 6
    requested_parallel, bundle = core.fit_tmle_ate(
        x,
        a,
        y,
        _params(
            parallel_folds=True,
            max_parallel_folds=max_parallel_folds,
            __disable_shared_nuisance_cache=True,
        ),
    )
    assert len(calls) == 12
    assert calls[:6] == calls[6:]
    assert [(seed, fold) for seed, fold, _ in calls[:6]] == [
        (seed, fold) for seed in (18, 1015) for fold in range(3)
    ]
    for seed in (18, 1015):
        held_out = [i for observed, _, indices in calls[:6] if observed == seed for i in indices]
        assert sorted(held_out) == list(range(240))
    assert bundle.diagnostics()["execution_policy"]["effective_fold_workers"] == 1
    assert bundle.diagnostics()["execution_policy"]["requested_parallel_folds"] is True
    assert (
        bundle.diagnostics()["execution_policy"]["requested_max_parallel_folds"]
        == max_parallel_folds
    )
    assert sum(len(r["folds"]) for r in bundle.split_manifest) == 6
    np.testing.assert_array_equal(requested_parallel.eif_values, serial.eif_values)
    assert requested_parallel.ate == serial.ate
    assert requested_parallel.ci_lower == serial.ci_lower
    assert requested_parallel.ci_upper == serial.ci_upper


def test_numerical_fold_oracle_detects_dropped_contribution_with_complete_task_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing one native contribution must fail even if all task labels survive."""
    x, treatment, outcome = _dgp(n=240)
    baseline, _ = core.fit_tmle_ate(x, treatment, outcome, _params(parallel_folds=False))
    native = core._fit_crossfit_fold
    actual_calls = []

    def discard_first_contribution(**kwargs):
        result = native(**kwargs)
        actual_calls.append((kwargs["rep_seed"], kwargs["fold_id"]))
        if kwargs["rep_seed"] == 18 and kwargs["fold_id"] == 0:
            # Execute the real models, then remove only their scientific
            # contribution. Backend/task/selection markers remain unchanged.
            return {
                **result,
                "test_idx": np.array([], dtype=int),
                "propensity": np.array([], dtype=float),
                "mu1": np.array([], dtype=float),
                "mu0": np.array([], dtype=float),
            }
        return result

    monkeypatch.setattr(core, "_fit_crossfit_fold", discard_first_contribution)
    damaged, bundle = core.fit_tmle_ate(
        x,
        treatment,
        outcome,
        _params(parallel_folds=True, max_parallel_folds=2, __disable_shared_nuisance_cache=True),
    )
    assert len(actual_calls) == 6
    assert actual_calls == [(seed, fold) for seed in (18, 1015) for fold in range(3)]
    assert sum(len(repeat["folds"]) for repeat in bundle.split_manifest) == 6
    assert len(bundle.outcome_backends) == 12
    assert bundle.diagnostics()["execution_policy"]["effective_fold_workers"] == 1
    with pytest.raises(AssertionError, match="Arrays are not equal"):
        np.testing.assert_array_equal(damaged.eif_values, baseline.eif_values)
    print(
        json.dumps(
            {
                "control": "one_native_fold_contribution_removed",
                "actual_native_fold_calls": len(actual_calls),
                "declared_fold_markers": 6,
                "outcome_backend_markers": len(bundle.outcome_backends),
                "maximum_absolute_eif_difference": float(
                    np.max(np.abs(damaged.eif_values - baseline.eif_values))
                ),
                "numerical_oracle": "array_equality_rejected",
            }
        )
    )


_FIT_CHANGES = {
    "nuisance_model_family": "linear",
    "propensity_backend": "compat",
    "propensity_backend_candidates": ("logistic", "compat"),
    "outcome_backend": "elastic_net",
    "outcome_backend_candidates": ("linear", "elastic_net"),
    "backend_selection_policy": "different-selection-policy",
    "selection_objective": "prediction",
    "calibration_mode": "sigmoid",
    "crossfit_folds": 4,
    "n_repeats": 2,
    "random_seed": 53,
    "random_seed_manifest": (53, 59),
    "propensity_clipping": 0.03,
    "propensity_trimming": 0.04,
    "outcome_scaling": "standardized",
    "calibration_fraction": 0.3,
    "min_calibration_size": 30,
}
_VIEW_CHANGES = {
    "inference_backend": "wald",
    "bootstrap_draws": 80,
    "feature_importance_mode": "permutation",
    "min_effective_sample_size": 1000,
    "ci_mode": "conservative",
    "coverage_guard": "ess_aware",
    "overlap_diagnostic_policy": "new-policy",
    "weak_overlap_mode": "trimmed_dr",
    "overlap_guard": 0.2,
    "parallel_folds": False,
    "max_parallel_folds": 2,
    "max_targeting_iter": 5,
    "targeting_step_limit": 2.0,
    "outcome_family": "bounded",
    "inference_profile": "clustered",
}


def test_every_contract_field_has_a_fit_or_current_view_policy() -> None:
    assert set(_FIT_CHANGES).isdisjoint(_VIEW_CHANGES)
    assert set(_FIT_CHANGES) | set(_VIEW_CHANGES) == {
        field.name for field in fields(core.ATENuisanceContract)
    }


@pytest.mark.parametrize("name,value", list(_FIT_CHANGES.items()) + list(_VIEW_CHANGES.items()))
def test_all_contract_axes_by_actual_native_fit_calls(
    name: str,
    value: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    x, a, y = _dgp(n=100)
    params = _params(n_repeats=1, __shared_nuisance_key="contract-axis")
    contract = core.ATENuisanceContract.from_params(params)
    calls = 0
    native = core._fit_crossfit_fold

    def observe(**kwargs):
        nonlocal calls
        calls += 1
        return native(**kwargs)

    monkeypatch.setattr(core, "_fit_crossfit_fold", observe)
    first = core.fit_crossfit_nuisance_bundle(x, a, y, contract, params)
    changed = replace(contract, **{name: value})
    assert getattr(contract, name) != value
    current = core.fit_crossfit_nuisance_bundle(x, a, y, changed, params)
    if name in _FIT_CHANGES:
        assert calls == 3 + changed.n_repeats * changed.crossfit_folds
        assert current.fit_identity != first.fit_identity
    else:
        assert calls == 3
        assert current.fit_identity == first.fit_identity
        assert current.contract is changed


def test_regular_iid_native_binary_dgp_coverage_pilot() -> None:
    """Finite seeded pilot, not coverage for admitted real data or arbitrary nuisances."""
    from scipy.stats import binomtest

    covered = 0
    errors = []
    repetitions = 120
    for seed in range(1000, 1000 + repetitions):
        x, a, y = _dgp(seed=seed, n=1000)
        fit, _ = core.fit_tmle_ate(
            x, a, y, _params(n_repeats=1, __disable_shared_nuisance_cache=True)
        )
        assert not fit.inference_limitations
        covered += int(fit.ci_lower <= 0.3 <= fit.ci_upper)
        errors.append(fit.ate - 0.3)
    exact = binomtest(covered, repetitions, p=0.95)
    interval = exact.proportion_ci(confidence_level=0.95, method="exact")
    print(
        json.dumps(
            {
                "profile": "known_randomized_binary_iid_dgp",
                "repetitions": repetitions,
                "n": 1000,
                "analytic_ate": 0.3,
                "covered": covered,
                "coverage": covered / repetitions,
                "binomial_95_interval": [interval.low, interval.high],
                "null_coverage_0_95_pvalue": exact.pvalue,
                "mean_error": np.mean(errors),
            }
        )
    )
    assert exact.pvalue > 0.01
    assert abs(np.mean(errors)) < 0.02


@pytest.mark.parametrize("profile", ["clustered", "unknown"])
def test_unsupported_inference_profiles_do_not_emit_an_interval(profile: str) -> None:
    x, a, y = _dgp()
    fit, _ = core.fit_tmle_ate(x, a, y, _params(inference_profile=profile))
    assert fit.ci_lower is None and fit.ci_upper is None
    assert fit.inference_limitations == ("unsupported_inference_profile",)


@pytest.mark.parametrize(
    ("submission_mode", "budget", "sample_size", "outcome_backend"),
    [
        ("serial", 1, 120, "linear"),
        ("queued", 1, 120, "linear"),
        ("queued", 2, 120, "linear"),
        ("serial", 1, 600, "elastic_net"),
        ("queued", 1, 600, "elastic_net"),
        ("queued", 2, 600, "elastic_net"),
    ],
    ids=[
        "serial-baseline",
        "outer-1",
        "outer-2",
        "n600-elastic-serial",
        "n600-elastic-outer-1",
        "n600-elastic-outer-2",
    ],
)
def test_native_studies_wait_in_actual_worker_pool_without_nested_fold_fanout(
    submission_mode: str,
    budget: int,
    sample_size: int,
    outcome_backend: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Run real node dispatch, native models and CAS readback under pool pressure."""
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.security import tenant_scope
    from polisyos.scientist.orchestration.engine import registry
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
    from polisyos.scientist.orchestration.engine.runner import local_pool as pool_module
    from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool
    from polisyos.scientist.orchestration.engine.runner.serialization import deserialize_outcome
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    release = threading.Event()
    lock = threading.Lock()
    active = peak = 0
    calls = []
    submitted_at = {}
    dispatched_at = {}
    numerical_results = []
    native = core._fit_crossfit_fold
    native_dispatch = pool_module._run_parent_receipt_task

    async def observe_dispatch(payload, **kwargs):
        dispatched_at[payload["alias"]] = time.perf_counter()
        return await native_dispatch(payload, **kwargs)

    monkeypatch.setattr(pool_module, "_run_parent_receipt_task", observe_dispatch)

    class StudyNode:
        spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.tests.tmle_pool@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                capabilities=Capability.SCIENTIST_NODE,
                abi_targets={},
            ),
            state_reads=["params"],
            state_writes=["artifacts_index"],
            produces=["tmle_result"],
        )

        def execute(self, ctx, state):
            fitting_params = {}
            if outcome_backend == "elastic_net":
                rng = np.random.default_rng(state.params["study_seed"])
                x = rng.normal(size=(sample_size, 2))
                a = rng.binomial(1, 0.5, size=sample_size).astype(float)
                y = (
                    1.7 * x[:, 0]
                    + 0.4 * a
                    + 0.15 * np.sin(3.0 * x[:, 0])
                    + rng.normal(scale=0.2, size=sample_size)
                )
                fitting_params = {
                    "outcome_backend": "elastic_net",
                    "outcome_scaling": "standardized",
                    "outcome_family": "continuous",
                }
            else:
                x, a, y = _dgp(seed=state.params["study_seed"], n=sample_size)
            result = _current_native_study_result(
                x, a, y, study=state.run_id, fitting_params=fitting_params
            )
            if outcome_backend == "elastic_net":
                diagnostics = result["result"]["nuisance_diagnostics"]
                assert set(diagnostics["outcome_backends"]) == {"elastic_net"}
                assert set(diagnostics["propensity_backends"]) == {"logistic_regression"}
            ref = _persist_native_study(ctx, x, a, y, result)
            state.artifacts_index["tmle_result"] = ref
            ctx.run.add_output(ref)
            return NodeOutcome(status="ok", state=state, artifacts=[ref])

    node = StudyNode()

    def discover_test_node(
        actual,
        *,
        components_index=None,
        include_entry_points=True,
        include_builtin_nodes=True,
        include_dev_scan=True,
    ):
        actual.register(node)
        return registry.NodeBootstrapReport(registered=[str(node.spec.metadata.component_id)])

    monkeypatch.setattr(registry, "discover_nodes", discover_test_node)

    async def run():
        nonlocal active, peak
        loop = asyncio.get_running_loop()
        admitted = asyncio.Event()
        tenant_id = "tenant-tmle-local-pool"
        cell_id = "cell-tmle-local-pool"

        def observe(**kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                calls.append((kwargs["rep_seed"], kwargs["fold_id"], kwargs["test_idx"].copy()))
                if active == budget:
                    loop.call_soon_threadsafe(admitted.set)
            try:
                assert release.wait(timeout=20), "pool barrier was not released"
                return native(**kwargs)
            finally:
                with lock:
                    active -= 1

        monkeypatch.setattr(core, "_fit_crossfit_fold", observe)
        if submission_mode == "serial":
            release.set()
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            store = FileSystemCAS(
                tmp_path / "cas",
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            bundle = build_default_registry_bundle(store, return_selected_profile=True)
            pool = LocalWorkerPool(max_workers=budget)
            parent_contexts = []
            try:
                futures = []
                serial_results = []
                started_at = time.perf_counter()
                for study in range(4):
                    state = ExperimentState(
                        run_id=f"study-{study}",
                        params={"study_seed": study + 71},
                    )
                    parent_context = _start_pool_parent_context(store, bundle, state.run_id)
                    parent_contexts.append(parent_context)
                    task = _bound_pool_task(node, f"study-{study}", state, parent_context)
                    submitted_at[task.alias] = time.perf_counter()
                    future = await pool.submit_with_parent_context(task, parent_context)
                    futures.append(future)
                    if submission_mode == "serial":
                        serial_results.append(await asyncio.wait_for(future, timeout=60))
                if submission_mode == "queued":
                    await asyncio.wait_for(admitted.wait(), timeout=20)
                    capacity = await pool.current_capacity()
                    assert capacity.active_tasks == budget
                    assert capacity.queue_depth == 4 - budget
                    assert peak == budget
                    release.set()
                    results = await asyncio.wait_for(asyncio.gather(*futures), timeout=60)
                else:
                    results = serial_results
                elapsed = time.perf_counter() - started_at
                assert len(calls) == 24  # all 4 studies × 2 repeats × 3 folds actually executed
                assert peak <= budget
                reader = FileSystemCAS(
                    tmp_path / "cas",
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                )
                for result_bytes, parent_context in zip(results, parent_contexts, strict=True):
                    outcome = deserialize_outcome(result_bytes)
                    assert outcome.status == "ok"
                    ref = ArtifactRef.model_validate(outcome.state.artifacts_index["tmle_result"])
                    saved = _read_current_native_study(reader, ref)
                    payload = saved["result"]
                    numerical_results.append(
                        {
                            "run_id": outcome.state.run_id,
                            "fit_identity": payload["nuisance_diagnostics"]["fit_identity"],
                            "ate": payload["ate"],
                            "ci": [payload["ci_lower"], payload["ci_upper"]],
                        }
                    )
                    assert payload["targeting_summary"]["converged"]
                    assert ref in parent_context.run.run_manifest.outputs
                    assert parent_context.run.trace_path is not None
                    trace = [
                        json.loads(line)
                        for line in parent_context.run.trace_path.read_text(
                            encoding="utf-8"
                        ).splitlines()
                    ]
                    assert sum(item["event"] == "RUN_STARTED" for item in trace) == 1
                    assert sum(item["event"] == "RUN_OUTPUT_ADDED" for item in trace) == 1
                    assert sum(item["event"] == "WORKER_INVOCATION_STARTED" for item in trace) == 1
                    assert (
                        sum(item["event"] == "WORKER_INVOCATION_COMPLETED" for item in trace) == 1
                    )
                    for repeat in payload["nuisance_diagnostics"]["split_manifest"]:
                        held_out = [i for fold in repeat["folds"] for i in fold["test_indices"]]
                        assert sorted(held_out) == list(range(sample_size))
                    assert (
                        payload["nuisance_diagnostics"]["execution_policy"][
                            "effective_fold_workers"
                        ]
                        == 1
                    )
                print(
                    json.dumps(
                        {
                            "profile": f"native_tmle_logistic_{outcome_backend}_n{sample_size}_cpu1",
                            "cache_mode": "four_cold_studies_with_diagnostic_only_hit",
                            "submission_mode": submission_mode,
                            "outer_budget": budget,
                            "study_seeds": [71, 72, 73, 74],
                            "scientific_studies": 4,
                            "scientific_fold_tasks": len(calls),
                            "wall_seconds": elapsed,
                            "peak_active_fold_work": peak,
                            "active_work_unit": "executing_native_fold_callbacks_not_OS_threads",
                            "queue_wait_scope": "submit_with_parent_context_to_admitted_receipt_dispatch_includes_scheduling",
                            "queue_wait_seconds": {
                                key: dispatched_at[key] - submitted_at[key]
                                for key in sorted(submitted_at)
                            },
                            "results": numerical_results,
                            "peak_RSS": "measured_by_retained_supervisor_per_process_command",
                        }
                    )
                )
            finally:
                release.set()
                await pool.shutdown()
                for parent_context in parent_contexts:
                    run_context = parent_context.run
                    if not run_context._closed and not run_context._suspended:
                        run_context.suspend_for_resume()

    asyncio.run(run())


def test_failed_native_study_releases_shared_pool_slot_for_waiting_study(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """A real native failure releases its shared slot without losing sibling folds."""
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.security import tenant_scope
    from polisyos.scientist.orchestration.engine import registry
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
    from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool
    from polisyos.scientist.orchestration.engine.runner.serialization import deserialize_outcome
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    with pytest.raises(ValueError, match="max_workers must be >= 1"):
        LocalWorkerPool(max_workers=0)

    release_failed_fold = threading.Event()
    current_study = threading.local()
    lock = threading.Lock()
    active = peak = 0
    calls: list[tuple[str, int, int]] = []
    native = core._fit_crossfit_fold

    class StudyNode:
        spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.tests.tmle_pool_failure@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                capabilities=Capability.SCIENTIST_NODE,
                abi_targets={},
            ),
            state_reads=["params"],
            state_writes=["artifacts_index"],
            produces=["tmle_result"],
        )

        def execute(self, ctx, state):
            current_study.run_id = state.run_id
            try:
                x, a, y = _dgp(seed=state.params["study_seed"], n=120)
                result = _current_native_study_result(x, a, y, study=state.run_id)
            finally:
                del current_study.run_id

            if state.params.get("fail_after_fit"):
                raise RuntimeError("study failed after all native folds")
            ref = _persist_native_study(ctx, x, a, y, result)
            state.artifacts_index["tmle_result"] = ref
            ctx.run.add_output(ref)
            return NodeOutcome(status="ok", state=state, artifacts=[ref])

    node = StudyNode()

    def discover_test_node(
        actual,
        *,
        components_index=None,
        include_entry_points=True,
        include_builtin_nodes=True,
        include_dev_scan=True,
    ):
        actual.register(node)
        return registry.NodeBootstrapReport(registered=[str(node.spec.metadata.component_id)])

    monkeypatch.setattr(registry, "discover_nodes", discover_test_node)

    async def run() -> None:
        nonlocal active, peak
        loop = asyncio.get_running_loop()
        failed_fold = asyncio.Event()
        tenant_id = "tenant-tmle-pool-failure"
        cell_id = "cell-tmle-pool-failure"

        def observe(**kwargs):
            nonlocal active, peak
            run_id = current_study.run_id
            with lock:
                active += 1
                peak = max(peak, active)
                calls.append((run_id, kwargs["rep_seed"], kwargs["fold_id"]))
            if run_id == "study-fails" and kwargs["rep_seed"] == 1015 and kwargs["fold_id"] == 2:
                loop.call_soon_threadsafe(failed_fold.set)
                assert release_failed_fold.wait(timeout=20), "failure boundary was not released"
            try:
                return native(**kwargs)
            finally:
                with lock:
                    active -= 1

        monkeypatch.setattr(core, "_fit_crossfit_fold", observe)
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            store = FileSystemCAS(
                tmp_path / "cas",
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            bundle = build_default_registry_bundle(store, return_selected_profile=True)
            pool = LocalWorkerPool(max_workers=1)
            parent_contexts = {}
            try:
                tasks = []
                for run_id, seed, fail_after_fit, priority in (
                    ("study-fails", 71, True, 1),
                    ("study-survives", 72, False, 0),
                ):
                    state = ExperimentState(
                        run_id=run_id,
                        params={"study_seed": seed, "fail_after_fit": fail_after_fit},
                    )
                    parent_context = _start_pool_parent_context(store, bundle, run_id)
                    parent_contexts[run_id] = parent_context
                    task = _bound_pool_task(
                        node,
                        run_id,
                        state,
                        parent_context,
                        priority=priority,
                    )
                    tasks.append(await pool.submit_with_parent_context(task, parent_context))

                await asyncio.wait_for(failed_fold.wait(), timeout=20)
                capacity = await pool.current_capacity()
                assert capacity.total_workers == 1
                assert capacity.active_tasks == 1
                assert capacity.queue_depth == 1
                release_failed_fold.set()

                with pytest.raises(RuntimeError, match="study failed after all native folds"):
                    await asyncio.wait_for(tasks[0], timeout=60)
                surviving_bytes = await asyncio.wait_for(tasks[1], timeout=60)
                capacity = await pool.current_capacity()
                assert capacity.active_tasks == 0
                assert capacity.queue_depth == 0
                assert peak == 1

                expected = [(18, fold) for fold in range(3)] + [(1015, fold) for fold in range(3)]
                by_study = {
                    run_id: [
                        (seed, fold) for observed_id, seed, fold in calls if observed_id == run_id
                    ]
                    for run_id in ("study-fails", "study-survives")
                }
                assert by_study == {"study-fails": expected, "study-survives": expected}
                assert len(calls) == 12

                outcome = deserialize_outcome(surviving_bytes)
                assert outcome.status == "ok"
                assert outcome.state.run_id == "study-survives"
                ref = ArtifactRef.model_validate(outcome.state.artifacts_index["tmle_result"])
                reader = FileSystemCAS(
                    tmp_path / "cas",
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                )
                payload = _read_current_native_study(reader, ref)["result"]
                assert payload["targeting_summary"]["converged"]
                assert ref in parent_contexts["study-survives"].run.run_manifest.outputs
                for run_id, parent_context in parent_contexts.items():
                    assert parent_context.run.trace_path is not None
                    trace = [
                        json.loads(line)
                        for line in parent_context.run.trace_path.read_text(
                            encoding="utf-8"
                        ).splitlines()
                    ]
                    assert sum(item["event"] == "RUN_STARTED" for item in trace) == 1
                    assert sum(item["event"] == "WORKER_INVOCATION_STARTED" for item in trace) == 1
                    assert (
                        sum(item["event"] == "WORKER_INVOCATION_COMPLETED" for item in trace) == 1
                    )
                    assert sum(item["event"] == "RUN_OUTPUT_ADDED" for item in trace) == int(
                        run_id == "study-survives"
                    )
                splits = payload["nuisance_diagnostics"]["split_manifest"]
                assert [
                    (repeat["seed"], [fold["fold"] for fold in repeat["folds"]])
                    for repeat in splits
                ] == [(18, [0, 1, 2]), (1015, [0, 1, 2])]
                for repeat in splits:
                    held_out = [index for fold in repeat["folds"] for index in fold["test_indices"]]
                    assert sorted(held_out) == list(range(120))
                assert (
                    payload["nuisance_diagnostics"]["execution_policy"]["effective_fold_workers"]
                    == 1
                )
            finally:
                release_failed_fold.set()
                await pool.shutdown()
                for parent_context in parent_contexts.values():
                    run_context = parent_context.run
                    if not run_context._closed and not run_context._suspended:
                        run_context.suspend_for_resume()

    asyncio.run(run())
