from __future__ import annotations

import json
from pathlib import Path

from polisyos.foundry.validation.phase2_closure import (
    build_foundry_phase2_closure_report,
    normalize_phase2_artifact_family,
)

_ACCEPTANCE_FILE = "tests/unit/foundry/validation/test_phase2_acceptance.py"
_ACCEPTANCE_NAME = "test_distributional_frontier_acceptance"
_ACCEPTANCE_NODE = f"{_ACCEPTANCE_FILE}::{_ACCEPTANCE_NAME}"
_JUDGE_FILE = "tests/unit/foundry/validation/test_phase2_judge_stack.py"
_JUDGE_NAME = "test_phase2_distributional_frontier_six_judge_promote"
_JUDGE_NODE = f"{_JUDGE_FILE}::{_JUDGE_NAME}"


def _write_manifest(
    path: Path,
    *,
    typed_targets: list[str] | None = None,
    acceptance_node: str = _ACCEPTANCE_NODE,
    judge_node: str = _JUDGE_NODE,
) -> None:
    path.write_text(
        json.dumps(
            {
                "phase_id": "foundry.phase2",
                "blocking_transition": "PROOF_ONLY->ENGINEER_READY",
                "source_of_truth": {
                    "acceptance_doc": "docs/reference/foundry/phase2-acceptance.md",
                    "validator": "tools/quality/validation/validate_foundry_phase2_closure.py",
                },
                "tracks": [
                    {
                        "track_id": "P2.04",
                        "artifact_family": "distributional_frontier",
                        "typed_targets": typed_targets
                        or ["polisyos.ir.analytics.distributional.DistributionalBoundsBundle"],
                        "required_acceptance_tests": [acceptance_node],
                        "required_benchmarks": ["phase2_distributional_frontier"],
                        "required_synthetic_world_checks": [acceptance_node],
                        "required_judge_verdicts": [judge_node],
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


def _write_junit(
    path: Path,
    *,
    file_name: str = _ACCEPTANCE_FILE,
    classname: str | None = None,
    test_name: str = _ACCEPTANCE_NAME,
    passed: bool = True,
    include_file: bool = True,
) -> None:
    attrs: list[str] = []
    if include_file and file_name:
        attrs.append(f'file="{file_name}"')
    if classname:
        attrs.append(f'classname="{classname}"')
    attrs.append(f'name="{test_name}"')
    rendered_attrs = " ".join(attrs)
    testcase = (
        f"  <testcase {rendered_attrs} />"
        if passed
        else (f'  <testcase {rendered_attrs}><failure message="boom" /></testcase>')
    )
    path.write_text(
        f'<testsuite name="phase2">\n{testcase}\n</testsuite>\n',
        encoding="utf-8",
    )


def _write_benchmarks(
    path: Path,
    *,
    benchmarks: list[dict[str, object]] | None = None,
) -> None:
    payload = {
        "benchmarks": benchmarks or [{"name": "phase2_distributional_frontier", "status": "pass"}]
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_evidence(
    path: Path,
    *,
    synthetic_status: str | None = "pass",
    judge_status: str | None = "promote",
    acceptance_node: str = _ACCEPTANCE_NODE,
    judge_node: str = _JUDGE_NODE,
) -> None:
    track: dict[str, object] = {}
    if synthetic_status is not None:
        track["synthetic_world_checks"] = {acceptance_node: synthetic_status}
    if judge_status is not None:
        track["judge_verdicts"] = {judge_node: {"composite_decision": judge_status}}
    payload = {"phase_id": "foundry.phase2", "tracks": {"P2.04": track}}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_report(tmp_path: Path):
    return build_foundry_phase2_closure_report(
        repo_root=Path(__file__).resolve().parents[4],
        manifest_path=tmp_path / "manifest.json",
        acceptance_junit_xml=tmp_path / "acceptance.xml",
        benchmark_report=tmp_path / "benchmarks.json",
        evidence_report=tmp_path / "evidence.json",
    )


def test_build_foundry_phase2_closure_report_all_green(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "manifest.json")
    _write_junit(tmp_path / "acceptance.xml")
    _write_benchmarks(tmp_path / "benchmarks.json")
    _write_evidence(tmp_path / "evidence.json")

    report = _build_report(tmp_path)

    assert report.overall_status == "complete"
    assert report.tracks["P2.04"].passes_all is True
    assert report.artifact_families["distributional_frontier"].passes_all is True


def test_build_foundry_phase2_closure_report_flags_missing_typed_target_mapping(
    tmp_path: Path,
) -> None:
    _write_manifest(
        tmp_path / "manifest.json",
        typed_targets=[
            "polisyos.ir.analytics.distributional.DistributionalBoundsBundle",
            "polisyos.ir.analytics.distributional.MissingSurface",
        ],
    )
    _write_junit(tmp_path / "acceptance.xml")
    _write_benchmarks(tmp_path / "benchmarks.json")
    _write_evidence(tmp_path / "evidence.json")

    report = _build_report(tmp_path)

    assert report.overall_status == "incomplete"
    assert report.tracks["P2.04"].status == "missing_typed_target_mapping"
    assert (
        "missing_typed_target_mapping:P2.04:polisyos.ir.analytics.distributional.MissingSurface"
        in report.notes
    )


def test_build_foundry_phase2_closure_report_flags_missing_benchmark(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "manifest.json")
    _write_junit(tmp_path / "acceptance.xml")
    _write_benchmarks(
        tmp_path / "benchmarks.json", benchmarks=[{"name": "other", "status": "pass"}]
    )
    _write_evidence(tmp_path / "evidence.json")

    report = _build_report(tmp_path)

    assert report.tracks["P2.04"].status == "stale_manifest"
    assert "stale_manifest:benchmark_missing:P2.04:phase2_distributional_frontier" in report.notes


def test_build_foundry_phase2_closure_report_flags_missing_synthetic_world_check(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path / "manifest.json")
    _write_junit(tmp_path / "acceptance.xml")
    _write_benchmarks(tmp_path / "benchmarks.json")
    _write_evidence(tmp_path / "evidence.json", synthetic_status=None)

    report = _build_report(tmp_path)

    assert report.tracks["P2.04"].status == "synthetic_world_missing"
    assert f"missing_synthetic_world:P2.04:{_ACCEPTANCE_NODE}" in report.notes


def test_build_foundry_phase2_closure_report_flags_missing_judge_verdict(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "manifest.json")
    _write_junit(tmp_path / "acceptance.xml")
    _write_benchmarks(tmp_path / "benchmarks.json")
    _write_evidence(tmp_path / "evidence.json", judge_status=None)

    report = _build_report(tmp_path)

    assert report.tracks["P2.04"].status == "judge_verdict_missing"
    assert f"missing_judge_verdict:P2.04:{_JUDGE_NODE}" in report.notes


def test_build_foundry_phase2_closure_report_supports_multi_target_tracks(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path / "manifest.json",
        typed_targets=[
            "polisyos.foundry.methods.catalog.network.generative_protocols.ERGMResult",
            "polisyos.foundry.methods.catalog.network.generative_protocols.SBMStratificationResult",
        ],
    )
    _write_junit(tmp_path / "acceptance.xml")
    _write_benchmarks(tmp_path / "benchmarks.json")
    _write_evidence(tmp_path / "evidence.json")

    report = _build_report(tmp_path)

    assert report.tracks["P2.04"].status == "pass"
    assert report.tracks["P2.04"].missing_typed_targets == ()


def test_build_foundry_phase2_closure_report_matches_parameterized_junit_to_base_nodeid(
    tmp_path: Path,
) -> None:
    acceptance_node = (
        "tests/unit/foundry/methods/catalog/causal/test_distributional_bounds.py::"
        "test_distributional_bounds_engine_routes_mtr_and_sd_inequality_families"
    )
    _write_manifest(tmp_path / "manifest.json", acceptance_node=acceptance_node)
    _write_junit(
        tmp_path / "acceptance.xml",
        classname="tests.unit.foundry.methods.catalog.causal.test_distributional_bounds",
        test_name=(
            "test_distributional_bounds_engine_routes_mtr_and_sd_inequality_families"
            "[sd_theil-theil_t-params3-sd_theil]"
        ),
        include_file=False,
    )
    _write_benchmarks(tmp_path / "benchmarks.json")
    _write_evidence(tmp_path / "evidence.json", acceptance_node=acceptance_node)

    report = _build_report(tmp_path)

    assert report.tracks["P2.04"].status == "pass"
    assert report.tracks["P2.04"].missing_acceptance_tests == ()


def test_build_foundry_phase2_closure_report_matches_classname_only_junit_to_class_nodeid(
    tmp_path: Path,
) -> None:
    acceptance_node = (
        "tests/unit/foundry/methods/catalog/distributional/test_mobility.py::"
        "TestTransitionMatrix::"
        "test_attrition_adjusted_ipcw_recovers_balanced_rows_and_persists_bounds"
    )
    _write_manifest(tmp_path / "manifest.json", acceptance_node=acceptance_node)
    _write_junit(
        tmp_path / "acceptance.xml",
        classname="tests.unit.foundry.methods.catalog.distributional.test_mobility.TestTransitionMatrix",
        test_name="test_attrition_adjusted_ipcw_recovers_balanced_rows_and_persists_bounds",
        include_file=False,
    )
    _write_benchmarks(tmp_path / "benchmarks.json")
    _write_evidence(tmp_path / "evidence.json", acceptance_node=acceptance_node)

    report = _build_report(tmp_path)

    assert report.tracks["P2.04"].status == "pass"
    assert report.tracks["P2.04"].missing_acceptance_tests == ()


def test_normalize_phase2_artifact_family_maps_frontier_hints() -> None:
    assert (
        normalize_phase2_artifact_family(
            "causal_core",
            estimator_name="network_missingness_frontier",
            query_type="partial_observability_bounds",
        )
        == "network_identification"
    )
    assert (
        normalize_phase2_artifact_family(
            "causal_core",
            estimator_name="state_dependent_threshold",
            query_type="threshold_identification",
        )
        == "econometrics_frontier"
    )
