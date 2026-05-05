from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "phase_id": "foundry.phase2",
                "tracks": [
                    {
                        "track_id": "P2.04",
                        "artifact_family": "distributional_frontier",
                        "typed_targets": [
                            "polisyos.ir.analytics.distributional.DistributionalBoundsBundle"
                        ],
                        "required_acceptance_tests": [
                            "tests/unit/foundry/methods/catalog/causal/test_distributional_bounds.py::"
                            "test_distributional_bounds_engine_routes_mtr_and_sd_inequality_families"
                        ],
                        "required_benchmarks": ["phase2_distributional_frontier"],
                        "required_synthetic_world_checks": [
                            "tests/unit/foundry/methods/catalog/causal/test_distributional_bounds.py::"
                            "test_distributional_bounds_engine_routes_mtr_and_sd_inequality_families"
                        ],
                        "required_judge_verdicts": [
                            "tests/unit/foundry/validation/test_phase2_judge_stack.py::"
                            "test_phase2_distributional_frontier_six_judge_promote"
                        ],
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


def _write_junit_reports(acceptance_path: Path, judge_path: Path) -> None:
    acceptance_path.write_text(
        '<testsuite name="phase2-acceptance">\n'
        "  <testcase "
        'classname="tests.unit.foundry.methods.catalog.causal.test_distributional_bounds" '
        'name="test_distributional_bounds_engine_routes_mtr_and_sd_inequality_families'
        '[sd_theil-theil_t-params3-sd_theil]" />\n'
        "</testsuite>\n",
        encoding="utf-8",
    )
    judge_path.write_text(
        '<testsuite name="phase2-judges">\n'
        "  <testcase "
        'classname="tests.unit.foundry.validation.test_phase2_judge_stack" '
        'name="test_phase2_distributional_frontier_six_judge_promote" />\n'
        "</testsuite>\n",
        encoding="utf-8",
    )


def test_generate_foundry_phase2_evidence_matches_pytest_junit_variants(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    acceptance_path = tmp_path / "acceptance.xml"
    judge_path = tmp_path / "judge.xml"
    output_path = tmp_path / "evidence.json"

    _write_manifest(manifest_path)
    _write_junit_reports(acceptance_path, judge_path)

    completed = subprocess.run(
        [
            sys.executable,
            "tools/quality/validation/generate_foundry_phase2_evidence.py",
            "--manifest",
            str(manifest_path),
            "--acceptance-junit-xml",
            str(acceptance_path),
            "--judge-junit-xml",
            str(judge_path),
            "--output",
            str(output_path),
        ],
        check=True,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    track = payload["tracks"]["P2.04"]
    assert (
        track["synthetic_world_checks"][
            "tests/unit/foundry/methods/catalog/causal/test_distributional_bounds.py::"
            "test_distributional_bounds_engine_routes_mtr_and_sd_inequality_families"
        ]
        == "pass"
    )
    assert (
        track["judge_verdicts"][
            "tests/unit/foundry/validation/test_phase2_judge_stack.py::"
            "test_phase2_distributional_frontier_six_judge_promote"
        ]["composite_decision"]
        == "promote"
    )
