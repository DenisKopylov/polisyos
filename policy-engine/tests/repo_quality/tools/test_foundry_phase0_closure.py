from __future__ import annotations

import json
from pathlib import Path

from benchmarks.synthetic_world.phase0_seed_benchmark import _build_report
from tools.quality.validation import validate_foundry_phase0_closure


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_foundry_phase0_closure_validator_builds_passing_report(tmp_path: Path) -> None:
    benchmark_json = tmp_path / "foundry-phase0-benchmark.json"
    output_json = tmp_path / "foundry-phase0-closure.json"
    benchmark_json.write_text(
        json.dumps(_build_report("smoke", quiet=True), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    exit_code = validate_foundry_phase0_closure.main(
        [
            "--repo-root",
            str(_repo_root()),
            "--benchmark-report",
            str(benchmark_json),
            "--output",
            str(output_json),
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    checks = {item["check_id"]: item for item in payload["checks"]}

    assert exit_code == 0
    assert payload["assessment_id"] == "foundry_phase0_closure"
    assert payload["overall_status"] == "complete"
    assert checks["statistical_tolerance_budget_validation"]["status"] == "complete"
    assert checks["synthetic_world_smoke_benchmark"]["status"] == "complete"


def test_foundry_phase0_closure_validator_fails_when_benchmark_regresses(tmp_path: Path) -> None:
    benchmark_json = tmp_path / "foundry-phase0-benchmark.json"
    output_json = tmp_path / "foundry-phase0-closure.json"
    payload = _build_report("smoke", quiet=True)
    payload["aggregate_metrics"]["target_coverage_rate"] = 0.75
    for case in payload.get("cases", []):
        metadata = dict(case.get("metadata") or {})
        metadata["calibrated_world"] = False
        case["metadata"] = metadata
    benchmark_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    exit_code = validate_foundry_phase0_closure.main(
        [
            "--repo-root",
            str(_repo_root()),
            "--benchmark-report",
            str(benchmark_json),
            "--output",
            str(output_json),
        ]
    )

    report = json.loads(output_json.read_text(encoding="utf-8"))
    checks = {item["check_id"]: item for item in report["checks"]}

    assert exit_code == 1
    assert report["overall_status"] == "incomplete"
    assert checks["synthetic_world_smoke_benchmark"]["status"] == "incomplete"
