"""Mutated DOE requests re-enter structural/budget admission before native work."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

pytest.importorskip("SALib")

from SALib.sample import morris

from polisyos.scientist.methods.doe import analysis, designs, sampling
from polisyos.scientist.methods.doe._receipt import _persist_analysis
from polisyos.scientist.methods.doe.adaptive import AdaptiveSampler
from polisyos.scientist.methods.doe.designs import ParameterSpec, SensitivityPlan
from polisyos.scientist.methods.doe.multi_output import MultiOutputAnalyzer
from polisyos.scientist.methods.doe.stability import RankingStabilityChecker


def _plan() -> SensitivityPlan:
    return SensitivityPlan(
        parameters=["x"], n_trajectories=1, max_estimated_runs=2, seed=7, input_law="independent"
    )


def _invalid_plan(mutation: str) -> SensitivityPlan:
    plan = _plan()
    if mutation == "n":
        plan.n_trajectories = 4
    elif mutation == "k":
        plan.parameter_specs.append(ParameterSpec(name="z", lower_bound=0, upper_bound=1))
    elif mutation == "method":
        plan.method = designs.SensitivityMethod.SOBOL
    elif mutation == "cap":
        plan.max_estimated_runs = 1
    elif mutation == "copy":
        plan = plan.model_copy(update={"n_trajectories": 4})
    elif mutation == "construct":
        plan = SensitivityPlan.model_construct(
            parameters=["x"], n_trajectories=4, max_estimated_runs=2, seed=7
        )
    elif mutation == "invalid_n":
        plan.n_trajectories = -1
    elif mutation == "nested_bounds":
        plan.parameter_specs[0].upper_bound = -1
    else:
        raise AssertionError(mutation)
    return plan


@pytest.mark.parametrize(
    "mutation", ["n", "k", "method", "cap", "copy", "construct", "invalid_n", "nested_bounds"]
)
@pytest.mark.parametrize(
    "boundary",
    [
        "sampling",
        "analysis",
        "identity",
        "problem",
        "preparation",
        "adaptive",
        "PCA",
        "stability",
        "persist",
    ],
)
def test_all_materializers_readmit_before_backend_or_callbacks(monkeypatch, mutation, boundary):
    plan = _invalid_plan(mutation)
    backend_calls = []
    from SALib.analyze import morris as morris_analyzer
    from SALib.analyze import sobol as sobol_analyzer
    from SALib.sample import fast_sampler, sobol

    def forbidden(*args, **kwargs):
        backend_calls.append((args, kwargs))
        raise AssertionError("backend/callback reached before readmission")

    for module, name in [
        (morris, "sample"),
        (sobol, "sample"),
        (fast_sampler, "sample"),
        (morris_analyzer, "analyze"),
        (sobol_analyzer, "analyze"),
    ]:
        monkeypatch.setattr(module, name, forbidden)
    x = np.zeros((2, 1))
    y = np.zeros(2)
    entrypoints = {
        "sampling": lambda: sampling.generate_sensitivity_samples(plan),
        "analysis": lambda: analysis.analyze_sensitivity(plan, x, y),
        "identity": lambda: analysis._analysis_identity(plan, x, y),
        "problem": lambda: designs._build_salib_problem(plan),
        "preparation": lambda: analysis._prepare_analysis_inputs(plan, x, y),
        "adaptive": lambda: AdaptiveSampler(plan).run(forbidden),
        "PCA": lambda: MultiOutputAnalyzer().analyze(plan, x, np.zeros((2, 2))),
        "stability": lambda: RankingStabilityChecker().check(plan, x, y),
        "persist": lambda: _persist_analysis(None, plan, x, y, None),
    }
    with pytest.raises(ValidationError):
        entrypoints[boundary]()
    assert backend_calls == []


def test_supported_morris_and_sobol_native_sample_analyzer_oracles():
    morris_plan = SensitivityPlan(
        parameters=["x", "z"], n_trajectories=16, max_estimated_runs=48, seed=23
    )
    x = sampling.generate_sensitivity_samples(morris_plan)
    result = analysis.analyze_sensitivity(morris_plan, x, 2 * x[:, 0] + 3 * x[:, 1])
    assert len(x) == result.total_runs == result.successful_runs == 48
    assert result.failed_runs == 0
    assert result.mu_star == pytest.approx({"x": 2.0, "z": 3.0})
    sobol_plan = SensitivityPlan(
        parameters=["x", "z"],
        method="sobol",
        input_law="independent",
        n_trajectories=256,
        max_estimated_runs=1536,
        seed=23,
    )
    x = sampling.generate_sensitivity_samples(sobol_plan)
    result = analysis.analyze_sensitivity(sobol_plan, x, 2 * x[:, 0] + 3 * x[:, 1])
    assert len(x) == result.total_runs == result.successful_runs == 1536
    assert result.s1 == pytest.approx({"x": 4 / 13, "z": 9 / 13}, abs=0.015)
    assert result.st == pytest.approx({"x": 4 / 13, "z": 9 / 13}, abs=0.015)


def test_explicit_large_run_override_remains_effective():
    plan = _plan()
    plan.n_trajectories = 4
    plan.allow_large_run = True
    x = sampling.generate_sensitivity_samples(plan)
    assert len(x) == 8 > plan.max_estimated_runs
    result = analysis.analyze_sensitivity(plan, x, x[:, 0])
    assert result.mu_star["x"] == pytest.approx(1.0)


def test_sampler_consumes_snapshot_after_original_mutates(monkeypatch):
    plan = _plan()
    native = morris.sample
    calls = []

    def mutate_original(problem, **kwargs):
        calls.append(kwargs["N"])
        plan.n_trajectories = 100
        plan.parameter_specs[0].upper_bound = -1
        return native(problem, **kwargs)

    monkeypatch.setattr(morris, "sample", mutate_original)
    x = sampling.generate_sensitivity_samples(plan)
    assert calls == [1]
    assert x.shape == (2, 1)
    assert plan.n_trajectories == 100 and plan.parameter_specs[0].upper_bound == -1


def test_adaptive_callback_mutation_does_not_change_effective_plan():
    from polisyos.scientist.methods.doe.adaptive import ConvergenceConfig

    plan = SensitivityPlan(parameters=["x"], n_trajectories=4, max_estimated_runs=8, seed=7)
    calls = []

    def evaluator(x):
        calls.append(len(x))
        plan.n_trajectories = 1000
        plan.max_estimated_runs = 1
        return x[:, 0]

    result = AdaptiveSampler(plan, ConvergenceConfig(max_rounds=1)).run(evaluator)
    assert calls == [8]
    assert result.total_evaluations == 8
    assert result.final_result.mu_star["x"] == pytest.approx(1.0)


def test_readmission_property_removal_exposes_over_cap_native_sample(monkeypatch):
    # Remove only admission code, keeping its object identity and imported aliases.
    def bypass(plan):
        return plan

    monkeypatch.setattr(designs._admit_sensitivity_plan, "__code__", bypass.__code__)
    plan = _invalid_plan("n")
    x = sampling.generate_sensitivity_samples(plan)
    assert len(x) == plan.estimated_runs == 8 > plan.max_estimated_runs
