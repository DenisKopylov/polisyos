"""Regression tests for the bounded DOE-01 execution contract."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import numpy as np
import pytest

from polisyos.scientist.methods.doe import sampling as sampling_module
from polisyos.scientist.methods.doe.adaptive import AdaptiveSampler, ConvergenceConfig
from polisyos.scientist.methods.doe.designs import (
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec,
    SensitivityMethod,
    SensitivityPlan,
    SensitivityResult,
)


@pytest.fixture
def _bounded_adaptive_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the coordinator without making DOE-01 a SALib installation test."""
    from polisyos.scientist.methods.doe import analysis

    def samples(plan: SensitivityPlan) -> np.ndarray:
        rows = plan.estimated_runs
        grid = np.arange(rows * len(plan.parameter_specs), dtype=float)
        return grid.reshape(rows, len(plan.parameter_specs)) / max(rows, 1)

    def analyze(
        plan: SensitivityPlan,
        rows: np.ndarray,
        outputs: np.ndarray,
    ) -> SensitivityResult:
        if outputs.ndim != 1 or len(outputs) != len(rows):
            raise ValueError("invalid analyzer inputs")
        return SensitivityResult(
            method=plan.method,
            parameter_names=[item.name for item in plan.parameter_specs],
            mu_star={
                item.name: float(index + 1) for index, item in enumerate(plan.parameter_specs)
            },
            ranking=[item.name for item in reversed(plan.parameter_specs)],
            total_runs=len(rows),
            successful_runs=len(outputs),
        )

    monkeypatch.setattr(sampling_module, "generate_sensitivity_samples", samples)
    monkeypatch.setattr(analysis, "analyze_sensitivity", analyze)


@pytest.fixture
def _real_salib_152() -> None:
    """Skip only when the actual supported SALib profile is unavailable."""
    try:
        actual_version = version("SALib")
    except PackageNotFoundError:
        pytest.skip("real adaptive backend requires SALib 1.5.2")
    if actual_version != "1.5.2":
        pytest.skip(f"real adaptive backend requires SALib 1.5.2, got {actual_version}")


def test_grid_extreme_materializes_only_the_declared_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The capped GRID_EXTREME prefix must not enumerate the full product first."""
    original_product = sampling_module.itertools.product
    yielded = 0

    def counted_product(*iterables: object):
        nonlocal yielded
        for corner in original_product(*iterables):
            yielded += 1
            yield corner

    monkeypatch.setattr(sampling_module.itertools, "product", counted_product)
    plan = AdversarialPlan(
        parameter_specs=[
            ParameterSpec(name=f"x{i}", lower_bound=0.0, upper_bound=1.0) for i in range(12)
        ],
        strategy=AdversarialStrategy.GRID_EXTREME,
        max_iterations=3,
    )

    samples = sampling_module.generate_adversarial_samples(plan)

    assert samples.shape == (3, 12)
    assert yielded == 3
    assert samples.base is None


def _adaptive_plan(
    *,
    n_trajectories: int,
    max_estimated_runs: int,
    allow_large_run: bool,
) -> SensitivityPlan:
    return SensitivityPlan(
        method=SensitivityMethod.MORRIS,
        parameter_specs=[
            ParameterSpec(name="x1", lower_bound=0.0, upper_bound=1.0),
            ParameterSpec(name="x2", lower_bound=0.0, upper_bound=1.0),
        ],
        n_trajectories=n_trajectories,
        seed=17,
        max_estimated_runs=max_estimated_runs,
        allow_large_run=allow_large_run,
    )


@pytest.mark.usefixtures("_real_salib_152")
def test_adaptive_sampler_returns_last_completed_round_without_hidden_evaluation() -> None:
    """Exhausting rounds must not evaluate an unrecorded extra sample batch."""
    calls: list[np.ndarray] = []

    def evaluator(samples: np.ndarray) -> np.ndarray:
        calls.append(samples.copy())
        return samples[:, 0] + 2.0 * samples[:, 1]

    result = AdaptiveSampler(
        _adaptive_plan(n_trajectories=2, max_estimated_runs=100, allow_large_run=True),
        convergence=ConvergenceConfig(
            max_rounds=2,
            ranking_stability_threshold=1.01,
            trajectory_step=1,
        ),
    ).run(evaluator)

    assert len(calls) == 2
    assert result.total_evaluations == sum(len(batch) for batch in calls)
    assert result.final_result.total_runs == len(calls[-1])
    assert result.stop_reason == "max_rounds_reached"


@pytest.mark.usefixtures("_real_salib_152")
def test_adaptive_sampler_stops_before_oversized_follow_up_without_override() -> None:
    """A false large-run permission must stop before evaluator work exceeds the cap."""
    calls: list[np.ndarray] = []

    def evaluator(samples: np.ndarray) -> np.ndarray:
        calls.append(samples.copy())
        return samples[:, 0] + samples[:, 1]

    result = AdaptiveSampler(
        _adaptive_plan(n_trajectories=1, max_estimated_runs=3, allow_large_run=False),
        convergence=ConvergenceConfig(
            max_rounds=3,
            ranking_stability_threshold=1.01,
            trajectory_step=1,
        ),
    ).run(evaluator)

    assert len(calls) == 1
    assert len(result.rounds) == 1
    assert result.total_evaluations == len(calls[0])
    assert result.stop_reason == "max_estimated_runs_exceeded"


@pytest.mark.usefixtures("_real_salib_152")
def test_adaptive_sampler_returns_last_result_when_later_round_fails() -> None:
    """A later round failure must preserve the last completed result."""
    calls: list[np.ndarray] = []

    def evaluator(samples: np.ndarray) -> np.ndarray:
        calls.append(samples.copy())
        if len(calls) == 2:
            raise ValueError("later round failed")
        return samples[:, 0] + samples[:, 1]

    result = AdaptiveSampler(
        _adaptive_plan(n_trajectories=1, max_estimated_runs=100, allow_large_run=True),
        convergence=ConvergenceConfig(
            max_rounds=3,
            ranking_stability_threshold=1.01,
            trajectory_step=1,
        ),
    ).run(evaluator)

    assert len(calls) == 2
    assert len(result.rounds) == 1
    assert result.total_evaluations == len(calls[0])
    assert result.final_result.total_runs == len(calls[0])
    assert result.stop_reason == "adaptive_evaluation_failed:ValueError"
    assert result.attempts[-1].phase == "evaluation"
    assert result.attempts[-1].evaluator_completed is None


@pytest.mark.usefixtures("_real_salib_152")
def test_adaptive_sampler_propagates_first_round_failure() -> None:
    """A failure before any completed round must remain an ordinary error."""

    def evaluator(_: np.ndarray) -> np.ndarray:
        raise ValueError("first round failed")

    with pytest.raises(ValueError, match="first round failed"):
        AdaptiveSampler(
            _adaptive_plan(n_trajectories=1, max_estimated_runs=100, allow_large_run=True),
            convergence=ConvergenceConfig(max_rounds=2),
        ).run(evaluator)


def test_adaptive_sampler_rejects_zero_round_budget_before_evaluation() -> None:
    with pytest.raises(ValueError, match="max_rounds"):
        ConvergenceConfig(max_rounds=0)


@pytest.mark.parametrize(
    ("failed_phase", "expected_completed"),
    [("generation", 0), ("evaluation", None), ("analysis", 3)],
)
def test_adaptive_sampler_records_failure_phase_without_inventing_work(
    monkeypatch: pytest.MonkeyPatch,
    failed_phase: str,
    expected_completed: int | None,
) -> None:
    """Equal exception types in distinct phases retain different work facts."""
    from polisyos.scientist.methods.doe import analysis

    sample_calls = 0
    evaluator_calls = 0
    analysis_calls = 0

    def samples(_: SensitivityPlan) -> np.ndarray:
        nonlocal sample_calls
        sample_calls += 1
        if sample_calls == 2 and failed_phase == "generation":
            raise ValueError("phase failure")
        return np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]])

    def analyze(plan: SensitivityPlan, rows: np.ndarray, outputs: np.ndarray) -> SensitivityResult:
        nonlocal analysis_calls
        analysis_calls += 1
        if analysis_calls == 2 and failed_phase == "analysis":
            raise ValueError("phase failure")
        return SensitivityResult(
            method=plan.method,
            parameter_names=[item.name for item in plan.parameter_specs],
            mu_star={"x1": 1.0, "x2": 0.5},
            ranking=["x1", "x2"],
            total_runs=len(rows),
            successful_runs=len(outputs),
        )

    def evaluator(rows: np.ndarray) -> np.ndarray:
        nonlocal evaluator_calls
        evaluator_calls += 1
        if evaluator_calls == 2 and failed_phase == "evaluation":
            raise ValueError("phase failure")
        return rows[:, 0] + rows[:, 1]

    monkeypatch.setattr(sampling_module, "generate_sensitivity_samples", samples)
    monkeypatch.setattr(analysis, "analyze_sensitivity", analyze)
    result = AdaptiveSampler(
        _adaptive_plan(n_trajectories=1, max_estimated_runs=100, allow_large_run=True),
        convergence=ConvergenceConfig(
            max_rounds=2,
            ranking_stability_threshold=1.01,
            trajectory_step=1,
        ),
    ).run(evaluator)

    assert result.attempts[-1].phase == failed_phase
    assert result.attempts[-1].evaluator_completed == expected_completed
    assert result.attempts[-1].error_type == "ValueError"
    assert evaluator_calls == (1 if failed_phase == "generation" else 2)
    assert analysis_calls == (1 if failed_phase != "analysis" else 2)
    assert result.total_evaluations == (3 if failed_phase != "analysis" else 6)


@pytest.mark.usefixtures("_bounded_adaptive_backends")
@pytest.mark.parametrize(
    "malformed",
    [np.array(1.0), np.ones((3, 1)), np.ones((2,))],
    ids=["scalar", "two-dimensional", "wrong-length"],
)
def test_adaptive_sampler_retains_completed_round_after_malformed_output(
    malformed: np.ndarray,
) -> None:
    """Output validation belongs to the evaluation attempt boundary."""
    calls = 0

    def evaluator(rows: np.ndarray) -> np.ndarray:
        nonlocal calls
        calls += 1
        if calls == 2:
            return malformed
        return rows[:, 0] + rows[:, 1]

    result = AdaptiveSampler(
        _adaptive_plan(n_trajectories=1, max_estimated_runs=100, allow_large_run=True),
        convergence=ConvergenceConfig(
            max_rounds=2,
            ranking_stability_threshold=1.01,
            trajectory_step=1,
        ),
    ).run(evaluator)

    assert calls == 2
    assert len(result.rounds) == 1
    assert result.total_evaluations == result.final_result.total_runs
    assert result.stop_reason == "adaptive_evaluation_failed:ValueError"
    assert result.attempts[-1].phase == "evaluation"
    assert result.attempts[-1].evaluator_completed is None


@pytest.mark.usefixtures("_bounded_adaptive_backends")
def test_adaptive_sampler_propagates_malformed_first_output() -> None:
    """There is no prior scientific result to retain on a first-round failure."""
    with pytest.raises(ValueError, match="1-D array"):
        AdaptiveSampler(
            _adaptive_plan(n_trajectories=1, max_estimated_runs=100, allow_large_run=True),
            convergence=ConvergenceConfig(max_rounds=1),
        ).run(lambda _rows: np.array(1.0))


@pytest.mark.parametrize("malformed", [np.array(1.0), np.ones((3, 1))])
def test_adaptive_sampler_rejects_malformed_generated_samples(
    monkeypatch: pytest.MonkeyPatch,
    malformed: np.ndarray,
) -> None:
    """A malformed design is generation work, not an evaluator attempt."""
    evaluator_calls = 0

    def evaluator(_rows: np.ndarray) -> np.ndarray:
        nonlocal evaluator_calls
        evaluator_calls += 1
        return np.array([])

    monkeypatch.setattr(
        sampling_module,
        "generate_sensitivity_samples",
        lambda _plan: malformed,
    )
    with pytest.raises(ValueError, match=r"generated samples must be a 2-D array|column count"):
        AdaptiveSampler(
            _adaptive_plan(n_trajectories=1, max_estimated_runs=100, allow_large_run=True),
            convergence=ConvergenceConfig(max_rounds=1),
        ).run(evaluator)
    assert evaluator_calls == 0


@pytest.mark.usefixtures("_real_salib_152")
def test_adaptive_sampler_explicit_override_admits_oversized_follow_up() -> None:
    """The same cap that blocks a second round permits it only with explicit override."""
    calls: list[np.ndarray] = []

    def evaluator(samples: np.ndarray) -> np.ndarray:
        calls.append(samples.copy())
        return samples[:, 0] + samples[:, 1]

    result = AdaptiveSampler(
        _adaptive_plan(n_trajectories=1, max_estimated_runs=3, allow_large_run=True),
        convergence=ConvergenceConfig(
            max_rounds=2, ranking_stability_threshold=1.01, trajectory_step=1
        ),
    ).run(evaluator)

    assert [len(samples) for samples in calls] == [3, 6]
    assert len(result.rounds) == 2
    assert result.total_evaluations == 9
    assert [attempt.evaluator_completed for attempt in result.attempts] == [3, 6]
    assert result.final_result.total_runs == 6
    assert result.stop_reason == "max_rounds_reached"


@pytest.mark.usefixtures("_real_salib_152")
@pytest.mark.parametrize("second_output", ["valid", "scalar", "matrix", "short", "bad-generation"])
def test_adaptive_real_salib_boundary_and_last_result(
    monkeypatch: pytest.MonkeyPatch, second_output: str
) -> None:
    """Real SALib calls retain the last result if the next evaluator output is malformed."""
    from SALib.analyze import morris as morris_analyzer
    from SALib.sample import morris as morris_sampler

    from polisyos.scientist.methods.doe import analysis as analysis_module

    original_sample = morris_sampler.sample
    original_analyze = morris_analyzer.analyze
    original_doe_analyze = analysis_module.analyze_sensitivity
    backend_sample_calls = 0
    backend_analysis_calls = 0
    analyzed: list[SensitivityResult] = []
    evaluations: list[np.ndarray] = []

    def record_sample(*args, **kwargs):
        nonlocal backend_sample_calls
        backend_sample_calls += 1
        sample = original_sample(*args, **kwargs)
        if backend_sample_calls == 2 and second_output == "bad-generation":
            return np.array(1.0)
        return sample

    def record_analyze(*args, **kwargs):
        nonlocal backend_analysis_calls
        backend_analysis_calls += 1
        return original_analyze(*args, **kwargs)

    def record_doe_analysis(plan: SensitivityPlan, samples: np.ndarray, outputs: np.ndarray):
        result = original_doe_analyze(plan, samples, outputs)
        analyzed.append(result)
        return result

    monkeypatch.setattr(morris_sampler, "sample", record_sample)
    monkeypatch.setattr(morris_analyzer, "analyze", record_analyze)
    monkeypatch.setattr(analysis_module, "analyze_sensitivity", record_doe_analysis)

    def evaluator(samples: np.ndarray) -> np.ndarray:
        evaluations.append(samples.copy())
        if len(evaluations) == 2:
            if second_output == "scalar":
                return np.array(1.0)
            if second_output == "matrix":
                return np.ones((len(samples), 1))
            if second_output == "short":
                return np.ones(len(samples) - 1)
        return samples[:, 0] + 2.0 * samples[:, 1]

    result = AdaptiveSampler(
        _adaptive_plan(n_trajectories=2, max_estimated_runs=100, allow_large_run=True),
        convergence=ConvergenceConfig(
            max_rounds=2, ranking_stability_threshold=1.01, trajectory_step=1
        ),
    ).run(evaluator)

    expected_evaluations = [6] if second_output == "bad-generation" else [6, 9]
    assert [len(samples) for samples in evaluations] == expected_evaluations
    assert backend_sample_calls == 2
    if second_output == "valid":
        assert backend_analysis_calls == 2
        assert len(result.rounds) == 2
        assert result.final_result is analyzed[-1]
        assert result.total_evaluations == 15
        assert [attempt.phase for attempt in result.attempts] == ["completed", "completed"]
        assert result.stop_reason == "max_rounds_reached"
    else:
        assert backend_analysis_calls == 1
        assert len(result.rounds) == 1
        assert result.final_result is analyzed[0]
        assert result.total_evaluations == 6
        expected_phase = "generation" if second_output == "bad-generation" else "evaluation"
        assert result.attempts[-1].phase == expected_phase
        assert result.attempts[-1].planned_evaluations == 9
        if second_output == "bad-generation":
            assert result.attempts[-1].evaluator_completed == 0
        else:
            assert result.attempts[-1].evaluator_completed is None
        assert result.stop_reason == f"adaptive_{expected_phase}_failed:ValueError"
    # For y = x1 + 2*x2 on [0,1]^2, normalized Morris effects are 1 and 2.
    assert result.final_result.mu_star["x1"] == pytest.approx(1.0)
    assert result.final_result.mu_star["x2"] == pytest.approx(2.0)


@pytest.mark.usefixtures("_real_salib_152")
def test_adaptive_real_salib_propagates_first_malformed_output() -> None:
    """A real first-round design cannot turn a scalar output into a prior result."""
    with pytest.raises(ValueError, match="evaluator output must be a 1-D array"):
        AdaptiveSampler(
            _adaptive_plan(n_trajectories=2, max_estimated_runs=100, allow_large_run=True),
            convergence=ConvergenceConfig(max_rounds=1),
        ).run(lambda _rows: np.array(1.0))
