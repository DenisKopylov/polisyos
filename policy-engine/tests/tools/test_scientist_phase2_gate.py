from __future__ import annotations

import json
from pathlib import Path

from tools.ci import check_scientist_phase2_gate

_TRACK_ID = "P2.04"
_ACCEPTANCE_TEST = (
    "tests/foundry/methods/catalog/causal/test_distributional_bounds.py::"
    "test_distributional_bounds_engine_routes_mtr_and_sd_inequality_families"
)
_BENCHMARK_ID = "phase2_distributional_frontier"
_JUDGE_TEST = (
    "tests/foundry/validation/test_phase2_judge_stack.py::"
    "test_phase2_distributional_frontier_six_judge_promote"
)


def _write_manifest(path: Path, *, typed_target: str | None = None) -> None:
    path.write_text(
        json.dumps(
            {
                "phase_id": "foundry.phase2",
                "blocking_transition": "PROOF_ONLY->ENGINEER_READY",
                "source_of_truth": {
                    "acceptance_doc": "docs/reference/foundry/phase2-acceptance.md",
                    "validator": "tools/quality/validation/validate_foundry_phase2_closure.py",
                    "wrapper": "tools/ci/check_scientist_phase2_gate.py",
                },
                "tracks": [
                    {
                        "track_id": _TRACK_ID,
                        "artifact_family": "distributional_frontier",
                        "typed_targets": [
                            typed_target
                            or "polisyos.ir.analytics.distributional.DistributionalBoundsBundle"
                        ],
                        "required_acceptance_tests": [_ACCEPTANCE_TEST],
                        "required_benchmarks": [_BENCHMARK_ID],
                        "required_synthetic_world_checks": [_ACCEPTANCE_TEST],
                        "required_judge_verdicts": [_JUDGE_TEST],
                        "acceptance_predicate": "truth_in_envelope",
                        "blocking_transition": "PROOF_ONLY->ENGINEER_READY",
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_junit(path: Path, *, passed: bool = True, include_test: bool = True) -> None:
    if include_test:
        testcase = (
            "  <testcase "
            'file="tests/foundry/methods/catalog/causal/test_distributional_bounds.py" '
            'name="test_distributional_bounds_engine_routes_mtr_and_sd_inequality_families" />'
            if passed
            else (
                "  <testcase "
                'file="tests/foundry/methods/catalog/causal/test_distributional_bounds.py" '
                'name="test_distributional_bounds_engine_routes_mtr_and_sd_inequality_families">'
                '<failure message="boom" />'
                "</testcase>"
            )
        )
    else:
        testcase = '  <testcase file="tests/other.py" name="test_other" />'
    path.write_text(
        "<testsuite name=\"phase2\">\n"
        f"{testcase}\n"
        "</testsuite>\n",
        encoding="utf-8",
    )


def _write_benchmarks(
    path: Path,
    *,
    status: str = "pass",
    include_benchmark: bool = True,
) -> None:
    payload = {
        "benchmarks": (
            [{"name": _BENCHMARK_ID, "status": status}]
            if include_benchmark
            else [{"name": "other_benchmark", "status": "pass"}]
        )
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_evidence(
    path: Path,
    *,
    include_track: bool = True,
    include_synthetic: bool = True,
    include_judge: bool = True,
) -> None:
    tracks: dict[str, object] = {}
    if include_track:
        payload: dict[str, object] = {}
        if include_synthetic:
            payload["synthetic_world_checks"] = {_ACCEPTANCE_TEST: "pass"}
        if include_judge:
            payload["judge_verdicts"] = {_JUDGE_TEST: {"composite_decision": "promote"}}
        tracks[_TRACK_ID] = payload
    path.write_text(
        json.dumps({"phase_id": "foundry.phase2", "tracks": tracks}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run_gate(
    repo_root: Path,
    *,
    output_json: Path,
) -> tuple[int, dict[str, object]]:
    exit_code = check_scientist_phase2_gate.main(
        [
            "--repo-root",
            str(repo_root),
            "--manifest",
            "manifest.json",
            "--junit-xml",
            "phase2.xml",
            "--benchmark-json",
            "benchmarks.json",
            "--evidence-json",
            "evidence.json",
            "--output",
            str(output_json),
            "--output-format",
            "json",
        ]
    )
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    return exit_code, payload


def test_scientist_phase2_gate_all_green(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "manifest.json")
    _write_junit(tmp_path / "phase2.xml")
    _write_benchmarks(tmp_path / "benchmarks.json")
    _write_evidence(tmp_path / "evidence.json")

    exit_code, payload = _run_gate(tmp_path, output_json=tmp_path / "phase2-gate.json")

    assert exit_code == 0
    assert payload["assessment_id"] == "scientist_phase2_gate"
    assert payload["passes_all"] is True
    family = payload["phase2_closure"]["artifact_families"]["distributional_frontier"]
    track = payload["phase2_closure"]["tracks"][_TRACK_ID]
    assert family["passes_all"] is True
    assert family["status"] == "pass"
    assert track["status"] == "pass"


def test_scientist_phase2_gate_fails_on_missing_typed_target_mapping(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path / "manifest.json",
        typed_target="polisyos.ir.analytics.distributional.DoesNotExist",
    )
    _write_junit(tmp_path / "phase2.xml")
    _write_benchmarks(tmp_path / "benchmarks.json")
    _write_evidence(tmp_path / "evidence.json")

    exit_code, payload = _run_gate(tmp_path, output_json=tmp_path / "phase2-gate.json")

    assert exit_code == 1
    track = payload["phase2_closure"]["tracks"][_TRACK_ID]
    assert track["status"] == "missing_typed_target_mapping"
    assert (
        "missing_typed_target_mapping:P2.04:polisyos.ir.analytics.distributional.DoesNotExist"
        in payload["notes"]
    )


def test_scientist_phase2_gate_fails_on_failed_benchmark(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "manifest.json")
    _write_junit(tmp_path / "phase2.xml")
    _write_benchmarks(tmp_path / "benchmarks.json", status="fail")
    _write_evidence(tmp_path / "evidence.json")

    exit_code, payload = _run_gate(tmp_path, output_json=tmp_path / "phase2-gate.json")

    assert exit_code == 1
    track = payload["phase2_closure"]["tracks"][_TRACK_ID]
    assert track["status"] == "failed_benchmark"
    assert "failed_benchmark:P2.04:phase2_distributional_frontier" in payload["notes"]


def test_scientist_phase2_gate_fails_on_missing_judge_verdict(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "manifest.json")
    _write_junit(tmp_path / "phase2.xml")
    _write_benchmarks(tmp_path / "benchmarks.json")
    _write_evidence(tmp_path / "evidence.json", include_judge=False)

    exit_code, payload = _run_gate(tmp_path, output_json=tmp_path / "phase2-gate.json")

    assert exit_code == 1
    track = payload["phase2_closure"]["tracks"][_TRACK_ID]
    assert track["status"] == "judge_verdict_missing"
    assert f"missing_judge_verdict:{_TRACK_ID}:{_JUDGE_TEST}" in payload["notes"]


def test_scientist_phase2_gate_fails_on_missing_synthetic_world_verification(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "manifest.json")
    _write_junit(tmp_path / "phase2.xml")
    _write_benchmarks(tmp_path / "benchmarks.json")
    _write_evidence(tmp_path / "evidence.json", include_synthetic=False)

    exit_code, payload = _run_gate(tmp_path, output_json=tmp_path / "phase2-gate.json")

    assert exit_code == 1
    track = payload["phase2_closure"]["tracks"][_TRACK_ID]
    assert track["status"] == "synthetic_world_missing"
    assert f"missing_synthetic_world:{_TRACK_ID}:{_ACCEPTANCE_TEST}" in payload["notes"]


def test_scientist_phase2_gate_fails_on_stale_manifest_entry(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "manifest.json")
    _write_junit(tmp_path / "phase2.xml", include_test=False)
    _write_benchmarks(tmp_path / "benchmarks.json", include_benchmark=False)
    _write_evidence(tmp_path / "evidence.json")

    exit_code, payload = _run_gate(tmp_path, output_json=tmp_path / "phase2-gate.json")

    assert exit_code == 1
    track = payload["phase2_closure"]["tracks"][_TRACK_ID]
    assert track["status"] == "stale_manifest"
    assert f"stale_manifest:test_missing:{_TRACK_ID}:{_ACCEPTANCE_TEST}" in payload["notes"]
    assert f"stale_manifest:benchmark_missing:{_TRACK_ID}:{_BENCHMARK_ID}" in payload["notes"]
