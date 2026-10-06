"""Real CAS bridge admission and faithful, non-promoting reverse replay."""

from __future__ import annotations

from copy import deepcopy

import pytest

from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from polisyos.scientist.methods.search.objective import OptimizationDirection
from tests.unit.scientist.methods.search.strategies.test_transfer import measured_history


def test_loads_native_discovery_and_uses_same_canonical_reader_for_replay(tmp_path):
    _, _, manager, _, target, _, basis = measured_history(tmp_path)
    bridge = WarmStartBridge(manager, max_evals=3)
    assert bridge.target_basis(target).identity_digest() == basis.identity_digest()
    rows = bridge.load_warm_start(target)
    assert len(rows) == 3
    assert bridge.admit_warm_start(rows, bridge.target_basis(target)) == rows
    assert bridge.last_admission_report["accepted"] == 3


@pytest.mark.parametrize("direction", list(OptimizationDirection))
def test_reverse_replay_preserves_original_metric_ref_and_metadata_without_promotion(
    tmp_path, direction
):
    _, _, manager, _, target, _, basis = measured_history(tmp_path, direction=direction, count=2)
    bridge = WarmStartBridge(manager)
    rows = bridge.load_warm_start(target)
    original_copy = deepcopy(rows)
    benchmarks = bridge.evaluations_to_benchmarks(rows, target_basis=basis, loop_id="receiving")
    assert rows == original_copy
    assert len(benchmarks) == 2
    for row, benchmark in zip(rows, benchmarks, strict=True):
        assert benchmark.selection_metrics == {"score": row.objectives[0].raw_value}
        assert benchmark.candidate_ref.model_dump(mode="json") == row.metadata["candidate_ref"]
        assert benchmark.sample_counts == {"selection": 11}
        assert benchmark.guardrails == {"finite": True}
        assert benchmark.notes == ["analytic fixture measurement"]
        assert benchmark.suite_version == "1.0"
        assert benchmark.metadata["replica_id"] == row.metadata["replica_id"]
        assert benchmark.metadata["provenance_ref"] == row.provenance_ref
        assert benchmark.metadata["source_loop_id"] == "analytic"
        assert benchmark.metadata["numeric_transfer_basis"] == basis.model_dump(mode="json")
        assert benchmark.holdout_metrics == {} and benchmark.promotable is False
        assert benchmark.status == "warm_start_limited"


def test_reverse_replay_refuses_unresolved_or_modified_observations(tmp_path):
    _, _, manager, _, target, originals, basis = measured_history(tmp_path, count=2)
    bridge = WarmStartBridge(manager)
    assert bridge.evaluations_to_benchmarks(originals, target_basis=basis, loop_id="receiver") == []
    rows = bridge.load_warm_start(target)
    rows[0].scalar_score += 99
    assert len(bridge.evaluations_to_benchmarks(rows, target_basis=basis, loop_id="receiver")) == 1
    assert bridge.last_admission_report["rejected"] == 1


def test_reverse_replay_requires_the_configured_metric(tmp_path):
    _, _, manager, _, target, _, basis = measured_history(tmp_path, count=2)
    bridge = WarmStartBridge(manager)
    with pytest.raises(ValueError, match="metric disagrees"):
        bridge.evaluations_to_benchmarks(
            bridge.load_warm_start(target),
            target_basis=basis,
            loop_id="receiver",
            primary_metric="invented",
        )
