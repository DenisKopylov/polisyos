"""Shared declared fixture inputs for native continuation consumers."""

from polisyos.scientist.methods.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.methods.search.strategies.types import Evaluation


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
