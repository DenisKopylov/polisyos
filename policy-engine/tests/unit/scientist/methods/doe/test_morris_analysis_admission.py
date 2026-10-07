"""Actual Morris analysis work must fit its admitted trajectory plan."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

pytest.importorskip("SALib", reason="Morris admission controls need the native SALib backend")

from SALib.analyze import morris

from polisyos.core.artifacts import FileSystemCAS
from polisyos.scientist.methods.doe import analysis, designs
from polisyos.scientist.methods.doe._receipt import _load_analysis, _persist_analysis
from polisyos.scientist.methods.doe.designs import SensitivityPlan
from polisyos.scientist.methods.doe.morris_geometry import _validate_morris_plan_samples
from polisyos.scientist.methods.doe.multi_output import MultiOutputAnalyzer
from polisyos.scientist.methods.doe.stability import RankingStabilityChecker
from tests._helpers.artifacts import put_json_artifact


def _plan(*, trajectories: int = 1, **overrides: object) -> SensitivityPlan:
    arguments: dict[str, object] = {
        "parameters": ["x"],
        "n_trajectories": trajectories,
        "max_estimated_runs": 2 * trajectories,
        "seed": 23,
    }
    arguments.update(overrides)
    return SensitivityPlan.model_validate(arguments)


def _two_trajectories() -> tuple[np.ndarray, np.ndarray]:
    # Both blocks are valid SALib num_levels=4 paths. Their independent linear
    # truth is delta_y / delta_unit_x = 2 on either path.
    samples = np.array([[0.0], [2.0 / 3.0], [1.0 / 3.0], [1.0]])
    return samples, 2.0 * samples[:, 0]


def test_healthy_two_row_point_analysis_keeps_one_trajectory_limit(monkeypatch):
    samples, outputs = _two_trajectories()
    calls: list[int] = []
    native = morris.analyze

    def observe(problem, sample_rows, output_rows, **kwargs):
        calls.append(len(sample_rows))
        return native(problem, sample_rows, output_rows, **kwargs)

    monkeypatch.setattr(morris, "analyze", observe)
    result = analysis.analyze_sensitivity(_plan(), samples[:2], outputs[:2])

    assert calls == [2]
    assert result.total_runs == result.successful_runs == 2
    assert result.failed_runs == 0
    assert result.mu_star["x"] == pytest.approx(2.0)
    assert math.isnan(result.sigma["x"])
    assert result.metadata["uncertainty_status"] == "point_only_incomplete"
    assert result.metadata["population_law_status"] == "not_established"


@pytest.mark.parametrize(
    "boundary", ["point", "preparation", "identity", "geometry", "PCA", "stability", "persist"]
)
@pytest.mark.parametrize("override", [False, True])
def test_extra_valid_trajectories_refuse_before_native_work(monkeypatch, boundary, override):
    plan = _plan(allow_large_run=override, max_estimated_runs=100)
    samples, outputs = _two_trajectories()
    backend_calls: list[str] = []

    def forbidden(*args, **kwargs):
        backend_calls.append("native_analysis_or_PCA")
        raise AssertionError("actual-work admission must precede native analysis")

    monkeypatch.setattr(morris, "analyze", forbidden)
    monkeypatch.setattr(MultiOutputAnalyzer, "_run_pca", forbidden)
    entrypoints = {
        "point": lambda: analysis.analyze_sensitivity(plan, samples, outputs),
        "preparation": lambda: analysis._prepare_analysis_inputs(plan, samples, outputs),
        "identity": lambda: analysis._analysis_identity(plan, samples, outputs),
        "geometry": lambda: _validate_morris_plan_samples(plan, samples),
        "PCA": lambda: MultiOutputAnalyzer().analyze(
            plan, samples, np.column_stack([outputs, 3.0 * outputs])
        ),
        "stability": lambda: RankingStabilityChecker(n_bootstrap=5).check(plan, samples, outputs),
        # None is deliberate: refusal must precede result inspection/store use.
        "persist": lambda: _persist_analysis(None, plan, samples, outputs, None),
    }

    with pytest.raises(ValueError, match="actual Morris analysis rows exceed admitted plan"):
        entrypoints[boundary]()
    assert backend_calls == []


@pytest.mark.parametrize("policy", ["drop_failed", "impute_baseline"])
def test_failed_extra_trajectory_cannot_shrink_into_admitted_work(monkeypatch, policy):
    plan = _plan(run_failure_policy=policy, min_success_rate=0.5)
    samples, outputs = _two_trajectories()
    outputs[2:] = np.nan
    calls: list[int] = []

    def forbidden(*args, **kwargs):
        calls.append(1)
        raise AssertionError("failure policy must not erase excess original work")

    monkeypatch.setattr(morris, "analyze", forbidden)
    with pytest.raises(ValueError, match="actual Morris analysis rows exceed admitted plan"):
        analysis.analyze_sensitivity(plan, samples, outputs)
    assert calls == []


def test_explicit_larger_plan_admits_same_rows_and_preserves_effect_oracle():
    samples, outputs = _two_trajectories()
    plan = _plan(trajectories=2, max_estimated_runs=2, allow_large_run=True)

    result = analysis.analyze_sensitivity(plan, samples, outputs)

    assert result.total_runs == result.successful_runs == plan.estimated_runs == 4
    assert result.mu_star["x"] == pytest.approx(2.0)
    assert result.sigma["x"] == pytest.approx(0.0, abs=1e-14)
    assert result.metadata["original_trajectory_ids"] == [0, 1]


def test_admitted_original_work_keeps_whole_trajectory_drop_accounting():
    plan = _plan(trajectories=2, run_failure_policy="drop_failed", min_success_rate=0.5)
    samples, outputs = _two_trajectories()
    outputs[2] = np.nan

    result = analysis.analyze_sensitivity(plan, samples, outputs)

    assert result.total_runs == 4
    assert result.successful_runs == 3
    assert result.failed_runs == 1
    assert result.metadata["effective_run_count"] == 2
    assert result.metadata["effective_trajectory_ids"] == [0]
    assert result.metadata["dropped_trajectory_ids"] == [1]
    assert result.metadata["selection_bias_status"] == "not_established"


def test_fresh_receipt_reopen_binds_actual_work_and_refuses_forged_smaller_plan(store):
    samples, outputs = _two_trajectories()
    plan = _plan(trajectories=2)
    result = analysis.analyze_sensitivity(plan, samples, outputs)
    ref = _persist_analysis(store, plan, samples, outputs, result)
    fresh = FileSystemCAS(store.root)
    reopened = _load_analysis(fresh, ref)

    assert reopened == result
    assert reopened.metadata["ordered_samples_sha256"] == result.metadata["ordered_samples_sha256"]
    assert reopened.metadata["analysis_id"] == result.metadata["analysis_id"]
    payload = json.loads(fresh.get_bytes(ref))
    payload["plan"]["n_trajectories"] = 1
    payload["plan"]["max_estimated_runs"] = 2
    forged = put_json_artifact(store, payload, kind="doe_sensitivity_analysis")
    assert fresh.verify(forged).ok
    with pytest.raises(ValueError, match="actual Morris analysis rows exceed admitted plan"):
        _load_analysis(fresh, forged)


def test_removing_actual_work_property_reopens_excess_native_analysis(monkeypatch):
    # Keep the existing helper and all imported aliases. Remove only its
    # actual-work predicate while retaining the structural snapshot validation.
    def structural_only(plan, *, actual_run_count=None):
        return SensitivityPlan.model_validate(plan.model_dump(mode="python"))

    monkeypatch.setattr(designs._admit_sensitivity_plan, "__code__", structural_only.__code__)
    samples, outputs = _two_trajectories()
    result = analysis.analyze_sensitivity(_plan(), samples, outputs)

    assert result.total_runs == 4 > result.metadata["estimated_runs"] == 2
    assert result.mu_star["x"] == pytest.approx(2.0)
    assert result.sigma["x"] == pytest.approx(0.0, abs=1e-14)
