"""Actual optional GP continuation consumers; no analytic expected-value oracle."""

import copy
from unittest.mock import patch

import pytest

from polisyos.scientist.methods.search.strategies import bayesian as module
from polisyos.scientist.methods.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.methods.search.strategies.resource_arbiter import (
    ResourceArbiter,
    ResourcePolicy,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    ParameterBounds,
    StrategyState,
)


def rows(space, n):
    return [
        Evaluation(
            f"row-{i}",
            {"x": (i + 1) / 16},
            space.normalize({"x": (i + 1) / 16}),
            [],
            4 + ((i + 1) / 16 - 0.4) ** 2,
            True,
            provenance_ref=f"fixture/{i}",
        )
        for i in range(n)
    ]


def optimizer(space, interval=5, arbiter=None):
    return BayesianOptimizer(
        space,
        BayesianConfig(
            n_initial=3,
            seed=37,
            num_restarts=2,
            raw_samples=16,
            refit_interval=interval,
            fallback_on_failure=False,
        ),
        arbiter,
    )


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
def test_actual_hard_resource_fallback_checkpoint_preserves_due_fit():
    space = SearchSpace([ParameterBounds("x")])
    arbiter = ResourceArbiter(ResourcePolicy(enable_cleanup=False))
    original = optimizer(space, interval=1, arbiter=arbiter)
    real_fit = module.fit_gpytorch_mll
    with patch.object(module, "fit_gpytorch_mll", wraps=real_fit) as fit:
        original.suggest(rows(space, 3))
        assert fit.call_count == 1
        arbiter.policy.hard_rss_mb = 0
        assert original.suggest(rows(space, 4)).source_strategy == "random_hard_limit"
        state = StrategyState.from_artifact(original.get_state().to_artifact())
        assert state.iteration == 4 and state.metadata["last_refit_iteration"] == 3
        restored = optimizer(space, interval=1)
        restored.set_state(state)
        arbiter.policy.hard_rss_mb = 13_000
        assert restored.suggest(rows(space, 4)).params == original.suggest(rows(space, 4)).params
        assert fit.call_count == 3
        assert restored._fitted_train_X.shape == (4, 1)
        future = copy.deepcopy(state)
        future.metadata["last_refit_iteration"] = 5
        before = restored.get_state().to_artifact()
        with pytest.raises(ValueError):
            restored.set_state(future)
        assert restored.get_state().to_artifact() == before


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
