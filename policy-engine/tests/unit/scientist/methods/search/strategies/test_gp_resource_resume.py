"""A real hard-resource producer checkpoint preserves its due native fit."""

import copy
from unittest.mock import patch

import pytest

from polisyos.scientist.methods.search.strategies import bayesian as module
from polisyos.scientist.methods.search.strategies.resource_arbiter import (
    ResourceArbiter,
    ResourcePolicy,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    ParameterBounds,
    StrategyState,
)
from tests.unit.scientist.methods.search.strategies._continuation_fixture import optimizer, rows


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
