"""Tests for WarmStartBridge."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from polisyos.scientist.autotune.warm_start import WarmStartBridge
from polisyos.scientist.search.strategies.transfer import RunFingerprint
from polisyos.scientist.search.strategies.types import Evaluation, EvaluationStatus
from polisyos.scientist.search.objective import ObjectiveValue, OptimizationDirection


def _make_eval(candidate_id: str, score: float, run_id: str = "") -> Evaluation:
    return Evaluation(
        candidate_id=candidate_id,
        params={"x": 0.5},
        params_normalized=(0.5,),
        objectives=[ObjectiveValue(name="score", raw_value=score, direction=OptimizationDirection.MINIMIZE)],
        scalar_score=score,
        stage_a_passed=True,
        status=EvaluationStatus.SUCCESS,
        metadata={"source_run_id": run_id},
    )


def _fingerprint(run_id: str = "new_run") -> RunFingerprint:
    return RunFingerprint(
        run_id=run_id,
        space_hash="abc123",
        objective_names=["score"],
        embedding=[0.1, 0.2, 0.3],
    )


class TestWarmStartBridge:
    def test_loads_from_transfer_manager(self):
        manager = MagicMock()
        similar = [
            RunFingerprint(run_id="old1", space_hash="x", objective_names=["score"]),
        ]
        manager.find_similar_runs.return_value = similar
        manager.get_warm_start_evaluations.return_value = [
            _make_eval("c1", 0.8, "old1"),
            _make_eval("c2", 0.6, "old1"),
        ]

        bridge = WarmStartBridge(manager, max_evals=10)
        evals = bridge.load_warm_start(_fingerprint())
        assert len(evals) == 2
        manager.find_similar_runs.assert_called_once()

    def test_no_similar_runs(self):
        manager = MagicMock()
        manager.find_similar_runs.return_value = []
        bridge = WarmStartBridge(manager)
        evals = bridge.load_warm_start(_fingerprint())
        assert evals == []

    def test_partial_data(self):
        manager = MagicMock()
        manager.find_similar_runs.return_value = [
            RunFingerprint(run_id="old", space_hash="x", objective_names=["score"]),
        ]
        manager.get_warm_start_evaluations.return_value = [_make_eval("c1", 0.9)]
        bridge = WarmStartBridge(manager, max_evals=1)
        evals = bridge.load_warm_start(_fingerprint())
        assert len(evals) == 1

    def test_evaluations_to_benchmarks(self):
        evals = [_make_eval("c1", 0.8, "run1")]
        benchmarks = WarmStartBridge.evaluations_to_benchmarks(
            evals, loop_id="loop1", primary_metric="score",
        )
        assert len(benchmarks) == 1
        assert benchmarks[0].loop_id == "loop1"
        assert benchmarks[0].holdout_metrics["score"] == 0.8
        assert benchmarks[0].status == "warm_start"
