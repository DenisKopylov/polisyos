"""Behavioral witnesses for content-bound nuisance reuse and bounded targeting."""

from __future__ import annotations

import asyncio
import json
import threading
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


def test_effective_fold_policy_retains_all_folds_and_native_results() -> None:
    x, a, y = _dgp(n=240)
    serial, _ = core.fit_tmle_ate(x, a, y, _params(parallel_folds=False))
    requested_parallel, bundle = core.fit_tmle_ate(
        x,
        a,
        y,
        _params(parallel_folds=True, max_parallel_folds=0, __disable_shared_nuisance_cache=True),
    )
    assert bundle.diagnostics()["execution_policy"]["effective_fold_workers"] == 1
    assert sum(len(r["folds"]) for r in bundle.split_manifest) == 6
    np.testing.assert_array_equal(requested_parallel.eif_values, serial.eif_values)
    assert requested_parallel.ate == serial.ate
    assert requested_parallel.ci_lower == serial.ci_lower
    assert requested_parallel.ci_upper == serial.ci_upper


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


@pytest.mark.parametrize("budget", [1, 2])
def test_native_studies_wait_in_actual_worker_pool_without_nested_fold_fanout(
    budget: int,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Run real node dispatch, native models and CAS readback under pool pressure."""
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
    from polisyos.scientist.orchestration.engine import registry
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
    from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        deserialize_outcome,
        serialize_state,
    )
    from polisyos.scientist.orchestration.engine.runner.worker_pool import NodeTask
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    release = threading.Event()
    lock = threading.Lock()
    active = peak = 0
    calls = []
    native = core._fit_crossfit_fold

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
            x, a, y = _dgp(seed=state.params["study_seed"], n=120)
            result = TMLEEstimator.pure_step(
                {"X": x, "treatment": a, "outcome": y},
                _params(__disable_shared_nuisance_cache=True),
            )["result"]
            ref = ctx.store.put_json(
                result,
                PutOptions(kind="test.tmle_result", media_type="application/json"),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            state.artifacts_index["tmle_result"] = ref
            return NodeOutcome(status="ok", state=state, artifacts=[ref])

    node = StudyNode()
    monkeypatch.setattr(registry, "discover_nodes", lambda actual: actual.register(node))

    async def run():
        nonlocal active, peak
        loop = asyncio.get_running_loop()
        admitted = asyncio.Event()

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
        pool = LocalWorkerPool(max_workers=budget)
        try:
            futures = []
            for study in range(4):
                state = ExperimentState(run_id=f"study-{study}", params={"study_seed": study + 71})
                futures.append(
                    await pool.submit(
                        NodeTask(
                            node_id=str(node.spec.metadata.component_id),
                            alias=f"study-{study}",
                            params={},
                            state_bytes=serialize_state(state),
                            trace_carrier={},
                            context_meta={
                                "run_id": state.run_id,
                                "store_backend": "filesystem",
                                "store_root": str(tmp_path / "cas"),
                            },
                        )
                    )
                )
            await asyncio.wait_for(admitted.wait(), timeout=20)
            capacity = await pool.current_capacity()
            assert capacity.active_tasks == budget
            assert capacity.queue_depth == 4 - budget
            assert peak == budget
            release.set()
            results = await asyncio.wait_for(asyncio.gather(*futures), timeout=60)
            assert len(calls) == 24  # all 4 studies × 2 repeats × 3 folds actually executed
            assert peak <= budget
            reader = FileSystemCAS(tmp_path / "cas")
            for result_bytes in results:
                outcome = deserialize_outcome(result_bytes)
                assert outcome.status == "ok"
                ref = ArtifactRef.model_validate(outcome.state.artifacts_index["tmle_result"])
                payload = json.loads(reader.get_bytes(ref))
                assert payload["targeting_summary"]["converged"]
                for repeat in payload["nuisance_diagnostics"]["split_manifest"]:
                    held_out = [i for fold in repeat["folds"] for i in fold["test_indices"]]
                    assert sorted(held_out) == list(range(120))
                assert (
                    payload["nuisance_diagnostics"]["execution_policy"]["effective_fold_workers"]
                    == 1
                )
        finally:
            release.set()
            await pool.shutdown()

    asyncio.run(run())
