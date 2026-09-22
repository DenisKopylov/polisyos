"""Distinguishing witnesses for the DOE-02 distribution and RNG contract."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.scientist.methods.doe import analysis as analysis_module
from polisyos.scientist.methods.doe import sampling as sampling_module
from polisyos.scientist.methods.doe.designs import (
    ParameterDist,
    ParameterSpec,
    SensitivityMethod,
    SensitivityPlan,
    _derive_backend_seed,
)

SALib = pytest.importorskip("SALib", reason="DOE-02 requires the pinned SALib backend")


def _morris_plan(
    *,
    seed: int | None,
    distribution: ParameterDist = ParameterDist.UNIFORM,
) -> SensitivityPlan:
    return SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[
            ParameterSpec(
                name="x",
                lower_bound=-2.0,
                upper_bound=3.0,
                distribution=distribution,
            ),
        ],
        n_trajectories=2,
        seed=seed,
    )


def _numpy_state_equal(left: tuple[object, ...], right: tuple[object, ...]) -> bool:
    """Compare legacy NumPy RandomState snapshots without consuming either state."""
    return (
        left[0] == right[0]
        and np.array_equal(left[1], right[1])
        and left[2:] == right[2:]
    )


def test_legacy_nonuniform_plan_fails_closed_without_typed_distribution_spec() -> None:
    """Physical bounds must not be silently reinterpreted as SALib parameters."""
    plan = _morris_plan(seed=13, distribution=ParameterDist.NORMAL)

    with pytest.raises(ValueError, match="DistributionSpecV1"):
        sampling_module.generate_sensitivity_samples(plan)

    with pytest.raises(ValueError, match="DistributionSpecV1"):
        analysis_module._plan_to_salib_problem(plan)


def test_sampling_forwards_seed_without_resetting_external_numpy_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sampler seed belongs to the request, not to process-global NumPy state."""
    from SALib.sample import morris as morris_sampler

    captured: dict[str, object] = {}

    def fake_sample(
        problem: dict[str, object],
        *,
        N: int,
        num_levels: int,
        seed: object = None,
    ) -> np.ndarray:
        captured["seed"] = seed
        return np.zeros((N * 2, 1), dtype=float)

    monkeypatch.setattr(morris_sampler, "sample", fake_sample)

    np.random.seed(90210)
    before = np.random.get_state()
    sampling_module.generate_sensitivity_samples(_morris_plan(seed=13))
    after = np.random.get_state()

    assert _numpy_state_equal(before, after)
    assert captured["seed"] == _derive_backend_seed(13, "sampling:morris")


def test_analysis_forwards_seed_to_backend_without_global_rng_side_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Analysis resampling must use a request-local seed as well as sampling."""
    from SALib.analyze import morris as morris_analyzer

    captured: dict[str, object] = {}

    def fake_analyze(
        problem: dict[str, object],
        samples: np.ndarray,
        outputs: np.ndarray,
        *,
        conf_level: float,
        num_levels: int,
        seed: object = None,
    ) -> dict[str, list[float]]:
        captured["seed"] = seed
        return {"mu_star": [1.0], "sigma": [0.0]}

    monkeypatch.setattr(morris_analyzer, "analyze", fake_analyze)

    plan = SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[ParameterSpec(name="x", lower_bound=0.0, upper_bound=1.0)],
        n_trajectories=1,
        seed=29,
    )
    samples = np.zeros((2, 1), dtype=float)
    outputs = np.array([0.0, 1.0], dtype=float)
    np.random.seed(7341)
    before = np.random.get_state()

    analysis_module.analyze_sensitivity(plan, samples, outputs)

    after = np.random.get_state()
    assert _numpy_state_equal(before, after)
    assert captured["seed"] == _derive_backend_seed(29, "analysis:morris")


def test_seeded_fast_analysis_fails_closed_for_backend_global_rng() -> None:
    """The pinned FAST analyzer cannot provide in-process seeded isolation."""
    plan = SensitivityPlan(
        method=SensitivityMethod.FAST,
        parameter_specs=[ParameterSpec(name="x", lower_bound=0.0, upper_bound=1.0)],
        n_trajectories=1,
        seed=31,
    )

    with pytest.raises(ValueError, match="compatibility_pending"):
        analysis_module.analyze_sensitivity(
            plan,
            np.zeros((1, 1), dtype=float),
            np.array([0.0], dtype=float),
        )


def test_sampling_and_analysis_backend_streams_are_domain_separated() -> None:
    assert _derive_backend_seed(13, "sampling:morris") != _derive_backend_seed(
        13,
        "analysis:morris",
    )


def test_same_seed_replays_complete_morris_sample_matrix() -> None:
    """A repeated plan must reproduce its full backend sample matrix."""
    plan = _morris_plan(seed=41)

    first = sampling_module.generate_sensitivity_samples(plan)
    second = sampling_module.generate_sensitivity_samples(plan)

    assert np.array_equal(first, second)


def test_independent_seeded_plans_are_order_independent() -> None:
    """One request must not consume another request's random stream."""
    plans = {
        "left": _morris_plan(seed=101),
        "right": _morris_plan(seed=202),
    }

    first_order = {
        name: sampling_module.generate_sensitivity_samples(plans[name])
        for name in ("left", "right")
    }
    second_order = {
        name: sampling_module.generate_sensitivity_samples(plans[name])
        for name in ("right", "left")
    }

    assert np.array_equal(first_order["left"], second_order["left"])
    assert np.array_equal(first_order["right"], second_order["right"])
