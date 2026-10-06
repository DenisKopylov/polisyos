"""Actual generator checkpoint and owner-paired transfer activation consumers."""

import sys
from copy import deepcopy
from dataclasses import replace

import pytest

from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    SearchSpace,
)
from polisyos.scientist.methods.autotune.models import BenchmarkSplit, MetricDirection
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from tests.unit.scientist.methods.search.strategies.test_transfer import measured_history


def cold(seed=19):
    generator = BayesianCandidateGenerator(
        SearchSpace([{"name": "x", "lower": 0.0, "upper": 1.0}]), seed=seed
    )
    assert generator.botorch_available, "UNRUN: required actual optional backend"
    return generator


def test_public_checkpoint_preserves_next_actual_sobol_action():
    original = cold()
    original.generate([], None, {})
    state = original.get_state()
    resumed = cold()
    resumed.set_state(deepcopy(state))
    expected = original.generate([], None, {})
    actual = resumed.generate([], None, {})
    assert actual["x"] == expected["x"]
    assert actual["_strategy_metadata"]["source"] == "sobol_init"
    assert (
        resumed.get_state()["strategy_state"]["rng_state"]["sobol"]
        == original.get_state()["strategy_state"]["rng_state"]["sobol"]
    )


@pytest.mark.parametrize("mutation", ["metric", "bool_seed", "flag", "schema", "rng"])
def test_wrapper_refusal_is_atomic_for_actual_native_rng(mutation):
    generator = cold()
    generator.generate([], None, {})
    before = generator.get_state()
    invalid = deepcopy(before)
    if mutation == "metric":
        invalid["config"]["primary_metric"] = "foreign"
    elif mutation == "bool_seed":
        invalid["config"]["seed"] = True
    elif mutation == "flag":
        invalid["activity_started"] = "false"
    elif mutation == "schema":
        invalid["schema_version"] = None
    else:
        invalid["strategy_state"]["rng_state"]["python"] = {"codec": "foreign"}
    with pytest.raises(ValueError):
        generator.set_state(invalid)
    assert generator.get_state() == before


def test_changed_processed_history_refuses_before_next_native_suggest():
    generator = cold()
    history = [{"params": {"x": 0.2}, "score": 1.0, "stage_a_passed": True}]
    generator.generate(history, None, {})
    resumed = cold()
    resumed.set_state(generator.get_state())
    history[0]["score"] = 2.0
    with pytest.raises(ValueError, match="resume history differs"):
        resumed.generate(history, None, {})


def test_configure_transfer_requires_pre_activity_pair():
    generator = cold()
    generator.generate([], None, {})
    with pytest.raises(ValueError, match="before warm/history/generation"):
        generator.configure_transfer(object(), object())


def test_owner_configured_bridge_reaches_real_gp_and_wrapper_resume_without_mll_fit(tmp_path):
    _, _, manager, _, target, _, basis = measured_history(tmp_path, count=8)
    bridge = WarmStartBridge(manager)

    def receiver():
        generator = BayesianCandidateGenerator(
            SearchSpace(basis.bounds["parameters"]),
            primary_metric="score",
            direction=MetricDirection.MINIMIZE,
            compare_split=BenchmarkSplit.SELECTION,
            n_initial=3,
            seed=19,
        )
        generator.configure_transfer(bridge, target)
        generator._optimizer._config = replace(
            generator._optimizer._config,
            num_restarts=2,
            raw_samples=32,
            refit_interval=20,
            fallback_on_failure=False,
        )
        return generator

    counts = {"mll": 0}

    def observe(frame, event, arg):
        if (
            event == "call"
            and frame.f_code.co_name == "fit_gpytorch_mll"
            and frame.f_code.co_filename.endswith("botorch/fit.py")
        ):
            counts["mll"] += 1

    previous = sys.getprofile()
    sys.setprofile(observe)
    try:
        original = receiver()
        assert len(original._optimizer._warm_evals) == 8
        original.generate([], None, {})
        assert counts["mll"] == 1
        assert original._optimizer._model is not None
        state = original.get_state()
        resumed = receiver()
        resumed.set_state(deepcopy(state))
        assert counts["mll"] == 1
        assert (
            resumed._optimizer._fitted_train_X.tolist()
            == original._optimizer._fitted_train_X.tolist()
        )
        assert (
            resumed._optimizer._fitted_train_y_bo.tolist()
            == original._optimizer._fitted_train_y_bo.tolist()
        )
        expected = original.generate([], None, {})
        actual = resumed.generate([], None, {})
        assert actual["x"] == pytest.approx(expected["x"], abs=1e-12)
        assert actual["_strategy_metadata"]["source"] == "bayesian_acquisition"
        assert counts["mll"] == 1
    finally:
        sys.setprofile(previous)


def test_missing_configured_pair_refuses_without_changing_native_receiver():
    generator = cold()
    before = generator.get_state()
    with pytest.raises(ValueError, match="paired bridge"):
        generator.configure_transfer(None, None)
    assert generator.get_state() == before


def test_standalone_current_transferred_rows_are_readmitted_before_model_restore(tmp_path):
    from types import SimpleNamespace

    from polisyos.core.artifacts.manifest import ArtifactRef

    store, _, manager, source, target, original, basis = measured_history(tmp_path, count=8)
    for row in original:
        row.metadata.update(
            source="search_iteration",
            params_normalized=list(row.params_normalized),
            candidate_id=row.candidate_id,
            provenance_ref=row.provenance_ref,
        )
    source.history_ref = manager.register_run(source, original)
    rows = manager.get_warm_start_evaluations([source], max_evals=8, target_fingerprint=target)
    bridge = WarmStartBridge(manager, max_evals=0)

    def receiver():
        generator = BayesianCandidateGenerator(
            SearchSpace(basis.bounds["parameters"]),
            primary_metric="score",
            direction=MetricDirection.MINIMIZE,
            compare_split=BenchmarkSplit.SELECTION,
            n_initial=3,
            seed=19,
        )
        generator.configure_transfer(bridge, target)
        generator._optimizer._config = replace(
            generator._optimizer._config,
            num_restarts=2,
            raw_samples=32,
            refit_interval=20,
            fallback_on_failure=False,
        )
        return generator

    history = [
        SimpleNamespace(
            candidate={"params": row.params},
            stage_b_result=row.stage_b_result,
            metadata=row.metadata,
            objective_value=row.scalar_score,
            stage_a_passed=True,
            timestamp=row.timestamp,
            duration_seconds=row.wall_time_seconds,
        )
        for row in rows
    ]
    original_generator = receiver()
    assert not original_generator._optimizer._warm_evals
    original_generator.generate(history, None, {})
    assert len(original_generator._optimizer._fitted_train_X) == 8
    checkpoint = original_generator.get_state()
    assert len(checkpoint["history_rows"]) == 8
    restored = receiver()
    restored.set_state(deepcopy(checkpoint))
    assert (
        restored._optimizer._fitted_train_X.tolist()
        == original_generator._optimizer._fitted_train_X.tolist()
    )
    assert (
        restored._optimizer._fitted_train_y_bo.tolist()
        == original_generator._optimizer._fitted_train_y_bo.tolist()
    )

    # Coverage cannot be removed while the fitted model and history markers remain.
    invalid = deepcopy(checkpoint)
    invalid["history_rows"] = []
    peer = receiver()
    before = peer.get_state()
    with pytest.raises(ValueError, match="coverage"):
        peer.set_state(invalid)
    assert peer.get_state() == before

    # Falsify source declarations coherently with the wrapper checksum. The
    # actual same CAS reader, not presence or a saved digest, must decide them.
    for mutation in ("direction", "reference", "outcome"):
        invalid = deepcopy(checkpoint)
        record = invalid["history_rows"][0]["evaluation"]
        if mutation == "direction":
            record["metadata"]["numeric_transfer_basis"]["direction"] = "maximize"
        elif mutation == "reference":
            record["metadata"]["evaluation_ref"]["artifact_id"] = "sha256:" + "f" * 64
        else:
            record["stage_a_passed"] = False
        decoded = original_generator._optimizer._decode_evaluation(record)
        invalid["history_digests"][0] = original_generator._history_row_digest(decoded)
        peer = receiver()
        before = peer.get_state()
        with pytest.raises(ValueError):
            peer.set_state(invalid)
        assert peer.get_state() == before
        assert peer._optimizer._model is None

    # Same full reference, changed original bytes: all checkpoint fields,
    # corpus/model hashes, coordinates and direction markers remain intact.
    original_ref = ArtifactRef.model_validate(rows[0].metadata["evaluation_ref"])
    blob, _ = store._paths(original_ref.artifact_id)
    blob.write_bytes(b"changed original measurement under unchanged full reference")
    peer = receiver()
    before = peer.get_state()
    with pytest.raises(ValueError):
        peer.set_state(deepcopy(checkpoint))
    assert peer.get_state() == before
    assert peer._optimizer._model is None
