from __future__ import annotations

import numpy as np
from polisyos.scientist.methods.doe.designs import AdversarialPlan, AdversarialStrategy, ParameterSpec
from polisyos.scientist.methods.doe.sampling import generate_adversarial_samples


def test_generate_adversarial_grid_extreme_corners() -> None:
    plan = AdversarialPlan(
        parameter_specs=[
            ParameterSpec(name="x", lower_bound=-1.0, upper_bound=1.0),
            ParameterSpec(name="y", lower_bound=0.0, upper_bound=2.0),
        ],
        strategy=AdversarialStrategy.GRID_EXTREME,
        max_iterations=8,
    )

    samples = generate_adversarial_samples(plan)

    assert samples.shape == (4, 2)
    expected = {
        (-1.0, 0.0),
        (-1.0, 2.0),
        (1.0, 0.0),
        (1.0, 2.0),
    }
    assert {tuple(row) for row in samples} == expected


def test_generate_adversarial_random_tail_within_bounds() -> None:
    plan = AdversarialPlan(
        parameter_specs=[ParameterSpec(name="x", lower_bound=-2.0, upper_bound=2.0)],
        strategy=AdversarialStrategy.RANDOM_TAIL,
        max_iterations=20,
        seed=7,
        tail_percentile=0.1,
    )

    samples = generate_adversarial_samples(plan)

    assert samples.shape == (20, 1)
    assert np.all(samples[:, 0] >= -2.0)
    assert np.all(samples[:, 0] <= 2.0)
    assert np.any(samples[:, 0] <= -1.6) or np.any(samples[:, 0] >= 1.6)
