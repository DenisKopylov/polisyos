from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from benchmarks.suite_registry import alias_targets, spec_by_suite_id
from benchmarks.synthetic_world.phase0_seed_benchmark import _build_report


def test_synthetic_world_suite_registry_entry_is_exposed() -> None:
    spec = spec_by_suite_id("synthetic_world_seed")
    assert spec.family == "synthetic_world"
    assert spec.script_relpath == "synthetic_world/phase0_seed_benchmark.py"
    assert "synthetic_world_seed" in {item.suite_id for item in alias_targets("synthetic_worlds")}


def test_synthetic_world_seed_benchmark_report_is_green() -> None:
    payload = _build_report("smoke", quiet=True)
    assert payload["suite_id"] == "synthetic_world_seed"
    assert payload["overall_status"] == "passed"
    assert payload["aggregate_metrics"]["target_coverage_rate"] == 1.0
    assert payload["aggregate_metrics"]["deterministic_replay_rate"] == 1.0
    assert len(payload["cases"]) == 4
