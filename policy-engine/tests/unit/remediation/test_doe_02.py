"""Distinguishing witnesses for the DOE-02 distribution and RNG contract."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.scientist.methods.doe import analysis as analysis_module
from polisyos.scientist.methods.doe import sampling as sampling_module
from polisyos.scientist.methods.doe.designs import (
    LognormalDistributionSpecV1,
    NormalDistributionSpecV1,
    ParameterDist,
    ParameterSpec,
    SensitivityMethod,
    SensitivityPlan,
    TriangularDistributionSpecV1,
    _build_salib_problem,
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

    errors: list[str] = []
    for operation in (
        lambda: sampling_module.generate_sensitivity_samples(plan),
        lambda: analysis_module._plan_to_salib_problem(plan),
    ):
        try:
            operation()
        except ValueError as exc:
            errors.append(str(exc))

    assert len(errors) == 2
    assert all("DistributionSpecV1" in error for error in errors)


def test_explicit_normal_uses_bounded_truncated_samples_and_roundtrips() -> None:
    """Normal moments are explicit and samples remain inside physical support."""
    plan = SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[
            ParameterSpec(
                name="x",
                lower_bound=-1.0,
                upper_bound=1.0,
                distribution=ParameterDist.NORMAL,
                distribution_spec=NormalDistributionSpecV1(mean=0.0, std=0.35),
            ),
        ],
        n_trajectories=16,
        seed=13,
    )

    problem, fingerprint = _build_salib_problem(plan)
    assert problem["dists"] == ["truncnorm"]
    assert problem["bounds"] == [[-1.0, 1.0, 0.0, 0.35]]
    samples = sampling_module.generate_sensitivity_samples(plan)
    quantiles = np.quantile(samples[:, 0], [0.1, 0.5, 0.9])
    assert np.all(np.isfinite(samples))
    assert np.all((samples[:, 0] >= -1.0) & (samples[:, 0] <= 1.0))
    assert -1.0 <= quantiles[0] <= quantiles[1] <= quantiles[2] <= 1.0
    assert quantiles[1] == pytest.approx(0.0, abs=0.25)

    restored = SensitivityPlan.model_validate(plan.model_dump(mode="json"))
    restored_problem, restored_fingerprint = _build_salib_problem(restored)
    assert restored_problem == problem
    assert restored_fingerprint == fingerprint


def test_explicit_triangular_uses_mode_fraction_and_support() -> None:
    """Triangular mode is represented as a fraction of the physical support."""
    plan = SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[
            ParameterSpec(
                name="x",
                lower_bound=0.0,
                upper_bound=1.0,
                distribution=ParameterDist.TRIANGULAR,
                distribution_spec=TriangularDistributionSpecV1(mode_fraction=0.75),
            ),
        ],
        n_trajectories=16,
        seed=23,
    )

    problem, _ = _build_salib_problem(plan)
    assert problem["dists"] == ["triang"]
    assert problem["bounds"] == [[0.0, 1.0, 0.75]]
    samples = sampling_module.generate_sensitivity_samples(plan)
    assert np.all((samples[:, 0] >= 0.0) & (samples[:, 0] <= 1.0))
    assert float(np.quantile(samples[:, 0], 0.5)) > 0.4


def test_bounded_distribution_shapes_match_scipy_and_not_uniform() -> None:
    """Pinned SciPy quantiles distinguish each bounded mapping from uniform."""
    from scipy.stats import triang, truncnorm, uniform

    quantile_levels = np.array([0.1, 0.5, 0.9])

    normal_plan = SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[
            ParameterSpec(
                name="x",
                lower_bound=-1.0,
                upper_bound=1.0,
                distribution=ParameterDist.NORMAL,
                distribution_spec=NormalDistributionSpecV1(mean=0.0, std=0.35),
            ),
        ],
        n_trajectories=64,
        seed=71,
    )
    triangular_plan = SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[
            ParameterSpec(
                name="x",
                lower_bound=0.0,
                upper_bound=1.0,
                distribution=ParameterDist.TRIANGULAR,
                distribution_spec=TriangularDistributionSpecV1(mode_fraction=0.75),
            ),
        ],
        n_trajectories=64,
        seed=73,
    )

    normal_samples = sampling_module.generate_sensitivity_samples(normal_plan)[:, 0]
    triangular_samples = sampling_module.generate_sensitivity_samples(triangular_plan)[:, 0]
    normal_reference = truncnorm(
        (-1.0 - 0.0) / 0.35,
        (1.0 - 0.0) / 0.35,
        loc=0.0,
        scale=0.35,
    )
    triangular_reference = triang(0.75, loc=0.0, scale=1.0)
    normal_uniform = uniform(loc=-1.0, scale=2.0)
    triangular_uniform = uniform(loc=0.0, scale=1.0)

    for samples, reference, uniform_reference in (
        (normal_samples, normal_reference, normal_uniform),
        (triangular_samples, triangular_reference, triangular_uniform),
    ):
        observed = np.quantile(samples, quantile_levels)
        expected = reference.ppf(quantile_levels)
        uniform_expected = uniform_reference.ppf(quantile_levels)
        reference_error = float(np.max(np.abs(observed - expected)))
        uniform_error = float(np.max(np.abs(observed - uniform_expected)))
        assert reference_error < 0.15
        assert reference_error < uniform_error


def test_analysis_metadata_fingerprint_matches_canonical_distribution_mapping() -> None:
    """Analysis receipts bind to the exact mapping used to create the plan."""
    plan = SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[
            ParameterSpec(
                name="x",
                lower_bound=-1.0,
                upper_bound=1.0,
                distribution=ParameterDist.NORMAL,
                distribution_spec=NormalDistributionSpecV1(mean=0.0, std=0.35),
            ),
        ],
        n_trajectories=16,
        seed=79,
    )
    samples = sampling_module.generate_sensitivity_samples(plan)
    result = analysis_module.analyze_sensitivity(plan, samples, samples[:, 0] ** 2)
    _, fingerprint = _build_salib_problem(plan)

    assert result.metadata["distribution_mapping_fingerprint"] == fingerprint
    assert result.metadata["distribution_schema_version"] == "doe-distribution-v1"
    assert result.metadata["salib_backend"] == "SALib@1.5.2"
    assert result.metadata["plan_seed"] == 79


def test_unsupported_lognormal_and_malformed_specs_fail_closed() -> None:
    """No unbounded lognormal mapping or invalid typed parameters is admitted."""
    with pytest.raises(ValueError):
        ParameterSpec(
            name="x",
            lower_bound=0.0,
            upper_bound=1.0,
            distribution=ParameterDist.NORMAL,
            distribution_spec=NormalDistributionSpecV1(mean=0.0, std=0.0),
        )

    plan = SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[
            ParameterSpec(
                name="x",
                lower_bound=0.1,
                upper_bound=2.0,
                distribution=ParameterDist.LOGNORMAL,
                distribution_spec=LognormalDistributionSpecV1(log_mean=0.0, log_std=0.2),
            ),
        ],
        n_trajectories=2,
        seed=13,
    )
    with pytest.raises(ValueError, match="compatibility_pending"):
        sampling_module.generate_sensitivity_samples(plan)
    with pytest.raises(ValueError, match="compatibility_pending"):
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
