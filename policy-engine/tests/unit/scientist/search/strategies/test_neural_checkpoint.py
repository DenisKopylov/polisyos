"""Native CAS warm-corpus continuation for the supported neural CPU profile."""

from __future__ import annotations

from copy import deepcopy

import pytest

from polisyos.core import artifacts
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from polisyos.scientist.methods.search.strategies.neural import (
    NeuralSearchConfig,
    NeuralSearchStrategy,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import StrategyState
from tests.unit.scientist.methods.search.strategies.test_transfer import measured_history

pytest.importorskip("hnswlib", reason="UNRUN: native CAS/ANN producer requires hnswlib")
pytest.importorskip("torch", reason="UNRUN: native neural continuation requires Torch")
pytest.importorskip("botorch", reason="UNRUN: native neural continuation requires BoTorch")
pytest.importorskip("gpytorch", reason="UNRUN: native neural continuation requires GPyTorch")
pytestmark = pytest.mark.integration


def _prepared(tmp_path, *, n_initial=10, count=3):
    store, _, manager, source, target, _, basis = measured_history(tmp_path, count=count)
    bridge = WarmStartBridge(manager)
    space = SearchSpace(bounds=manager._space(basis).bounds)
    config = NeuralSearchConfig(n_initial=n_initial, seed=19)
    strategy = NeuralSearchStrategy(
        space,
        config=config,
        numerical_basis=basis,
        warm_start_admission=bridge.admit_warm_start,
    )
    rows = bridge.load_warm_start(target)
    assert len(rows) == count
    strategy.warm_start(rows)
    return store, bridge, space, config, strategy, rows, basis


def _persist_state(store, strategy):
    return store.put_bytes(
        strategy.get_state().to_artifact(),
        artifacts.PutOptions(kind="search.strategy_state", media_type="application/octet-stream"),
    )


def _fresh(space, config, bridge, basis):
    return NeuralSearchStrategy(
        space,
        config=config,
        numerical_basis=basis,
        warm_start_admission=bridge.admit_warm_start,
    )


def test_actual_cas_checkpoint_restores_corpus_and_next_sobol_proposal(tmp_path):
    store, bridge, space, config, live, rows, basis = _prepared(tmp_path)
    live.suggest([])
    ref = _persist_state(store, live)
    fresh = _fresh(space, config.model_copy(update={"seed": 999}), bridge, basis)
    fresh.set_state(StrategyState.from_artifact(store.get_bytes(ref)))
    assert fresh._warm_data == rows == live._warm_data
    assert (
        fresh.get_state().metadata["warm_evaluations"]
        == live.get_state().metadata["warm_evaluations"]
    )
    uninterrupted = live.suggest([])
    resumed = fresh.suggest([])
    assert uninterrupted.source_strategy == resumed.source_strategy == "neural_sobol_init"
    assert uninterrupted.params_normalized == resumed.params_normalized
    assert uninterrupted.params == resumed.params
    assert fresh._sobol_cursor == live._sobol_cursor
    assert fresh._config.seed == 19
    print("ACTUAL_NEURAL_CAS_RESUME", len(rows), len(fresh._warm_data), resumed.params)


@pytest.mark.parametrize("phase", ["restore", "ask", "checkpoint"])
def test_same_ref_changed_original_bytes_refuses_before_model_use(tmp_path, phase):
    store, bridge, space, config, live, rows, basis = _prepared(tmp_path)
    state_ref = _persist_state(store, live)
    original = artifacts.ArtifactRef.model_validate(rows[0].metadata["evaluation_ref"])
    blob, _ = store._paths(original.artifact_id)
    blob.write_bytes(b"changed original evaluation content under preserved reference")
    before = live._iteration

    def operation():
        if phase == "restore":
            _fresh(space, config, bridge, basis).set_state(
                StrategyState.from_artifact(store.get_bytes(state_ref))
            )
        elif phase == "ask":
            live.suggest([])
        else:
            live.get_state()

    with pytest.raises(ValueError, match="no longer admitted"):
        operation()
    assert live._iteration == before
    assert len(live._warm_data) == 3


@pytest.mark.parametrize("field", ["scalar_score", "stage_a_passed", "candidate_id"])
def test_recomputed_checkpoint_digest_cannot_replace_original_measurement(tmp_path, field):
    store, bridge, space, config, live, _, basis = _prepared(tmp_path)
    state = StrategyState.from_artifact(store.get_bytes(_persist_state(store, live)))
    row = state.metadata["warm_evaluations"][0]
    row[field] = {"scalar_score": 999.0, "stage_a_passed": "false", "candidate_id": "other"}[field]
    # Preserve every origin/basis/ref marker and recompute only the local digest.
    state.metadata["warm_corpus_sha256"] = live._corpus_digest(state.metadata)
    fresh = _fresh(space, config, bridge, basis)
    with pytest.raises(ValueError, match="(no longer admitted|malformed)"):
        fresh.set_state(state)
    assert fresh._warm_data == []
    assert fresh._iteration == 0


@pytest.mark.parametrize("field", ["numerical_basis", "backend", "config", "warm_start_count"])
def test_checkpoint_changed_basis_or_configuration_is_not_a_resume(tmp_path, field):
    store, bridge, space, config, live, _, basis = _prepared(tmp_path)
    state = StrategyState.from_artifact(store.get_bytes(_persist_state(store, live)))
    if field == "numerical_basis":
        state.metadata[field]["bounds"]["parameters"][0]["lower"] = False
    elif field == "backend":
        state.metadata[field]["botorch"] = "unsupported"
    elif field == "config":
        state.metadata[field]["n_initial"] = True
    else:
        state.metadata[field] = True
    state.metadata["warm_corpus_sha256"] = live._corpus_digest(state.metadata)
    with pytest.raises(ValueError):
        _fresh(space, config, bridge, basis).set_state(state)


def test_count_only_legacy_warm_state_is_visibly_unsupported(tmp_path):
    _, bridge, space, config, live, _, basis = _prepared(tmp_path)
    state = live.get_state()
    state.metadata = {"warm_start_count": 3, "config": config.model_dump()}
    with pytest.raises(ValueError, match="warm corpus state profile"):
        _fresh(space, config, bridge, basis).set_state(state)


def test_warm_rows_require_the_configured_target_and_canonical_reader(tmp_path):
    _, _, space, _, _, rows, basis = _prepared(tmp_path)
    bare = NeuralSearchStrategy(space)
    bare.warm_start(rows)
    assert bare._warm_data == []
    assert len(bare.last_warm_start_report) == len(rows)
    with pytest.raises(ValueError, match="both"):
        NeuralSearchStrategy(space, numerical_basis=basis)


def test_caller_mutation_and_duplicate_artifact_do_not_change_training_corpus(tmp_path):
    _, _, _, _, live, rows, _ = _prepared(tmp_path)
    duplicate = deepcopy(rows)
    rows[0].params["x"] = 2.0
    corpus = live._training_corpus(duplicate)
    assert len(corpus) == 3
    assert all(0 < row.params["x"] < 1 for row in corpus)
    assert len(live._warm_data) == 3


def test_native_single_task_gp_next_proposal_matches_fresh_cas_resume(tmp_path, monkeypatch):
    """Observe genuine fits and native EI; no model/acquisition is substituted."""
    import torch
    from botorch.models import SingleTaskGP

    from polisyos.scientist.methods.search.strategies import _deps

    store, bridge, space, config, live, rows, basis = _prepared(tmp_path, n_initial=8, count=8)
    fits = []
    native_fit = _deps.fit_gpytorch_mll

    def observe_actual_fit(mll, *args, **kwargs):
        assert isinstance(mll.model, SingleTaskGP)
        result = native_fit(mll, *args, **kwargs)
        fits.append(mll.model)
        return result

    monkeypatch.setattr(_deps, "fit_gpytorch_mll", observe_actual_fit)
    ambient_rng = torch.random.get_rng_state().clone()
    first = live.suggest([])
    assert first.source_strategy == "neural_gp"
    assert len(fits) == 1
    assert torch.equal(torch.random.get_rng_state(), ambient_rng)
    ref = _persist_state(store, live)
    fresh = _fresh(space, config, bridge, basis)
    fresh.set_state(StrategyState.from_artifact(store.get_bytes(ref)))
    assert len(fits) == 1, "restore admits rows without fitting a replacement model"
    assert fresh._warm_data == rows == live._warm_data
    uninterrupted = live.suggest([])
    resumed = fresh.suggest([])
    assert len(fits) == 3
    assert uninterrupted.source_strategy == resumed.source_strategy == "neural_gp"
    assert resumed.params_normalized == pytest.approx(uninterrupted.params_normalized, abs=1e-10)
    assert resumed.predicted_mean == pytest.approx(uninterrupted.predicted_mean, abs=1e-10)
    assert resumed.predicted_std == pytest.approx(uninterrupted.predicted_std, abs=1e-10)
    assert resumed.acquisition_value == pytest.approx(uninterrupted.acquisition_value, abs=1e-10)
    expected_x = torch.tensor([row.params_normalized for row in rows], dtype=torch.double)
    expected_y = torch.tensor([[-row.scalar_score] for row in rows], dtype=torch.double)
    for model in fits:
        assert torch.equal(model.train_inputs[0], expected_x)
        raw_targets = model.outcome_transform.untransform(model.train_targets.reshape(-1, 1))[0]
        assert torch.allclose(raw_targets, expected_y, rtol=0, atol=1e-14)
    assert fresh._rng.getstate() == live._rng.getstate()
    print("ACTUAL_NATIVE_NEURAL_FITS", len(fits), "CORPUS", len(rows), "RESUMED", resumed.params)
