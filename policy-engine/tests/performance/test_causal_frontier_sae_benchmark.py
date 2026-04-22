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
from benchmarks.survey.causal_frontier_sae_benchmark import _build_report


def test_causal_frontier_suite_registry_entry_is_exposed() -> None:
    spec = spec_by_suite_id("survey_causal_frontier_sae")
    assert spec is not None
    assert spec.family == "survey"
    assert spec.script_relpath == "survey/causal_frontier_sae_benchmark.py"
    assert "survey_causal_frontier_sae" in {item.suite_id for item in alias_targets("track_5_2")}


def test_causal_frontier_benchmark_report_is_green() -> None:
    payload = _build_report("smoke", quiet=True)
    assert payload["suite_id"] == "survey_causal_frontier_sae"
    assert payload["overall_status"] == "passed"
    assert payload["aggregate_metrics"]["null_false_alert_rate"] == 0.0
    assert payload["aggregate_metrics"]["jump_detection_rate"] == 1.0
    assert payload["aggregate_metrics"]["mean_tau_abs_error_improvement"] > 0.0
    assert len(payload["cases"]) == 4
