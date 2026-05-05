from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.benchmark, pytest.mark.performance]

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
sys.modules.pop("benchmarks", None)

_MODULE_PATH = REPO_ROOT / "benchmarks" / "composition" / "compositional_causality_benchmark.py"
_SPEC = importlib.util.spec_from_file_location("composition_benchmark", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

CIRCUIT = _MODULE.CIRCUIT
_report_to_dict = _MODULE._report_to_dict
build_harness = _MODULE.build_harness

from benchmarks.reporting import build_preflight
from benchmarks.runtime import resolve_mode
from benchmarks.suite_registry import spec_by_suite_id


def test_compositional_causality_harness_runs_green() -> None:
    harness = build_harness()
    report = harness.run(circuit=CIRCUIT)

    assert report.n_total() >= 10
    assert report.n_total() == report.n_passed()
    replay_cases = [
        case
        for case in report.cases
        if (case.result_payload or {}).get("mode") == "scientist_bridge_compare"
    ]
    assert len(replay_cases) >= 3
    assert all(case.result_payload.get("scientist_equivalent") for case in replay_cases)


def test_compositional_causality_report_payload_contains_b5_metrics() -> None:
    harness = build_harness()
    report = harness.run(circuit=CIRCUIT)
    mode = resolve_mode("smoke").value
    preflight = build_preflight(mode=mode, data_source="curated_composition_fixtures")
    payload = _report_to_dict(report, mode=mode, preflight=preflight)

    assert payload["suite_id"] == "capability_compositional_causality"
    assert payload["aggregate_metrics"]["composition_status_distribution"]["preserved"] >= 1
    assert payload["aggregate_metrics"]["composition_status_distribution"]["broken"] >= 1
    assert payload["aggregate_metrics"]["query_preservation_status_distribution"]["preserved"] >= 1
    assert payload["aggregate_metrics"]["query_preservation_status_distribution"]["broken"] >= 1
    assert payload["aggregate_metrics"]["query_preservation_status_distribution"]["unknown"] >= 1
    assert payload["aggregate_metrics"]["failure_card_coverage"]["expected_negative_cases"] >= 1


def test_compositional_causality_suite_is_registered() -> None:
    spec = spec_by_suite_id("capability_compositional_causality")

    assert spec.suite_id == "capability_compositional_causality"
    assert spec.script_relpath == "composition/compositional_causality_benchmark.py"


def test_scientist_bridge_case_normalizes_broken_graph_visibility() -> None:
    spec = next(
        item for item in _MODULE._specs() if item.name == "composition::disconnected_extra_fragment"
    )

    payload = _MODULE._run_spec(spec)

    assert payload["mode"] == "scientist_bridge_compare"
    assert payload["composition_status"] == "broken"
    assert payload["scientist_equivalent"] is True
    assert payload["composed_graph_signature"] is None
    assert payload["persisted_artifacts"]["composed_graph"] is False


def test_scientist_bridge_case_keeps_deferred_graph_visibility() -> None:
    spec = next(
        item for item in _MODULE._specs() if item.name == "composition::proxy_deferred_review"
    )

    payload = _MODULE._run_spec(spec)

    assert payload["mode"] == "scientist_bridge_compare"
    assert payload["composition_status"] == "deferred"
    assert payload["scientist_equivalent"] is True
    assert payload["composed_graph_signature"] is not None
    assert payload["persisted_artifacts"]["composed_graph"] is True
