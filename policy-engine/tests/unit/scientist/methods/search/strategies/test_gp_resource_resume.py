"""A genuine resource fallback may defer a scheduled fit across a checkpoint."""

from __future__ import annotations

from dataclasses import replace

import pytest

from polisyos.scientist.methods.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.methods.search.strategies.resource_arbiter import (
    ResourceArbiter,
    ResourcePolicy,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    AcquisitionType,
    Evaluation,
    ParameterBounds,
    StrategyState,
)


def test_real_hard_limit_checkpoint_preserves_due_refit() -> None:
    space = SearchSpace([ParameterBounds("x")])
    config = BayesianConfig(
        n_initial=3,
        refit_interval=1,
        num_restarts=1,
        raw_samples=8,
        acquisition=AcquisitionType.UCB,
        fallback_on_failure=False,
    )
    policy = ResourcePolicy(soft_rss_mb=100000, hard_rss_mb=100000, enable_cleanup=False)
    original = BayesianOptimizer(space, replace(config), ResourceArbiter(policy))
    history = [
        Evaluation(
            candidate_id=f"observation-{index}",
            params={"x": value},
            params_normalized=(value,),
            objectives=[],
            scalar_score=(value - 0.4) ** 2,
            stage_a_passed=True,
        )
        for index, value in enumerate((0.0, 0.5, 1.0, 0.2))
    ]
    assert original.suggest(history[:3]).source_strategy == "bayesian_acquisition"
    old_model = original._model
    policy.soft_rss_mb = policy.hard_rss_mb = 0
    assert original.suggest(history).source_strategy == "random_hard_limit"
    assert original._model is old_model
    produced = StrategyState.from_artifact(original.get_state().to_artifact())
    assert produced.iteration == 4 and produced.metadata["last_refit_iteration"] == 3
    assert len(produced.metadata["train_X"]) == len(produced.metadata["refit_train_X"]) == 3

    restored = BayesianOptimizer(
        space,
        replace(config),
        ResourceArbiter(
            ResourcePolicy(soft_rss_mb=100000, hard_rss_mb=100000, enable_cleanup=False)
        ),
    )
    restored.set_state(produced)
    restored_model = restored._model
    invalid = StrategyState.from_artifact(produced.to_artifact())
    invalid.metadata["last_refit_iteration"] = invalid.iteration + 1
    with pytest.raises(ValueError, match="refit counters"):
        restored.set_state(invalid)
    assert restored._model is restored_model
    assert restored.get_state().to_artifact() == produced.to_artifact()

    # The lifted production arbiter permits the same due real fit after resume.
    assert restored.suggest(history).source_strategy == "bayesian_acquisition"
    assert restored._model is not restored_model
    resumed = restored.get_state()
    assert resumed.metadata["last_refit_iteration"] == 4
    assert resumed.metadata["last_train_size"] == len(resumed.metadata["refit_train_X"]) == 4
