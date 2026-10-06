"""Actual optional GP continuation consumers; no analytic expected-value oracle."""

import copy
from unittest.mock import patch

import pytest

from polisyos.scientist.methods.search.strategies import bayesian as module
from polisyos.scientist.methods.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    ParameterBounds,
    StrategyState,
)
from tests.unit.scientist.methods.search.strategies._continuation_fixture import optimizer, rows


@pytest.mark.skipif(module.fit_gpytorch_mll is None, reason="optional GP stack unavailable")
def test_real_same_corpus_and_append_resume_do_not_fit():
    space = SearchSpace([ParameterBounds("x")])
    original = optimizer(space)
    history = rows(space, 6)
    real_fit = module.fit_gpytorch_mll
    with patch.object(module, "fit_gpytorch_mll", wraps=real_fit) as fit:
        assert original.suggest(history).source_strategy == "bayesian_acquisition"
        assert fit.call_count == 1
        state = StrategyState.from_artifact(original.get_state().to_artifact())
        restored = optimizer(space)
        restored.set_state(state)
        before = original._torch.get_rng_state().clone()
        assert restored.suggest(copy.deepcopy(history)).params == original.suggest(history).params
        assert fit.call_count == 1
        appended = rows(space, 7)
        assert restored.suggest(copy.deepcopy(appended)).params == original.suggest(appended).params
        assert fit.call_count == 1
        assert restored._fitted_train_X.shape == (7, 1)
        assert restored._torch.equal(before, restored._torch.get_rng_state())
        # Native changed corpus identity, even equal tensors, requires a due basis refit.
        changed = copy.deepcopy(appended)
        changed[0].provenance_ref = "fixture/independent-origin"
        restored.suggest(changed)
        assert fit.call_count > 1


@pytest.mark.skipif(module.fit_gpytorch_mll is None, reason="optional GP stack unavailable")
def test_saved_corpus_changed_with_model_markers_preserved_refuses_atomically():
    space = SearchSpace([ParameterBounds("x")])
    producer = optimizer(space)
    producer.suggest(rows(space, 6))
    saved = StrategyState.from_artifact(producer.get_state().to_artifact())
    for field in ("train_X", "train_y_bo", "refit_train_X", "refit_train_y_bo"):
        changed = copy.deepcopy(saved)
        changed.metadata[field][0][0] += 0.01
        before = producer.get_state().to_artifact()
        with pytest.raises(ValueError):
            producer.set_state(changed)
        assert producer.get_state().to_artifact() == before


@pytest.mark.parametrize("field", ["scalar_score", "params"])
@pytest.mark.skipif(module.fit_gpytorch_mll is None, reason="optional GP stack unavailable")
def test_saved_warm_content_changed_with_fitted_markers_preserved_refuses(field):
    space = SearchSpace([ParameterBounds("x")])
    basis = {
        "profile": "synthetic_scalar_gp.v1",
        "search_space_fingerprint": space.sobol_space_fingerprint(),
        "context_fingerprint": "fixture/warm-basis",
        "metric": "cost",
        "unit": "fixture_cost",
        "direction": "minimize",
    }
    producer = BayesianOptimizer(
        space,
        BayesianConfig(
            n_initial=3, seed=37, num_restarts=2, raw_samples=16, fallback_on_failure=False
        ),
        numerical_basis=basis,
    )
    warm = rows(space, 6)
    for evaluation in warm:
        evaluation.metadata["warm_start_compatibility"] = {
            "search_space_fingerprint": space.sobol_space_fingerprint(),
            "input_transform_fingerprint": "Normalize[0,1]",
            "outcome_transform_fingerprint": "Standardize[m=1]",
            "noise_model_fingerprint": "GaussianLikelihood[inferred]",
            "objective_fingerprint": "scalar_score[minimize]",
            "context_fingerprint": "fixture/warm-basis",
        }
    producer.warm_start(warm)
    producer.suggest([])
    changed = StrategyState.from_artifact(producer.get_state().to_artifact())
    if field == "scalar_score":
        changed.metadata["warm_evaluations"][0][field] += 0.2
    else:
        changed.metadata["warm_evaluations"][0][field]["x"] += 0.002
        changed.metadata["warm_evaluations"][0]["params_normalized"][0] += 0.002
    before = producer.get_state().to_artifact()
    try:
        producer.set_state(changed)
    except ValueError:
        assert producer.get_state().to_artifact() == before
        return
    real_fit = module.fit_gpytorch_mll
    with patch.object(module, "fit_gpytorch_mll", wraps=real_fit) as fit:
        producer.suggest([])
        print(
            "MARKER_PRESERVING_WARM_CHANGE_ADMITTED", field, "ACTUAL_EXTRA_MLL_FITS", fit.call_count
        )
    pytest.fail("Persisted warm content changed while fitted/model/corpus markers remained intact")


@pytest.mark.skipif(module.fit_gpytorch_mll is None, reason="optional GP stack unavailable")
def test_transferred_current_rows_cannot_bypass_configured_reader():
    space = SearchSpace([ParameterBounds("x")])
    strategy = optimizer(space)
    transferred = rows(space, 6)
    for row in transferred:
        row.metadata["numeric_transfer_basis"] = {"profile": "numeric_transfer_basis.v1"}
    with patch.object(module, "fit_gpytorch_mll", wraps=module.fit_gpytorch_mll) as fit:
        with pytest.raises(ValueError, match="configured CAS admission reader"):
            strategy.suggest(transferred)
        assert fit.call_count == 0
    assert strategy._model is None
