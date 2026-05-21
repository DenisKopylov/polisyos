# ruff: noqa: S101, TC003

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from tools.quality.validation import check_honest_diagnostics_proof_harness as harness

REPO_ROOT = Path(__file__).resolve().parents[3]
NEGATIVE_TEST_REF = (
    "tests/unit/runtime/quality/test_runtime_quality_negative.py::"
    "test_bundle_local_quality_evidence_paths_do_not_satisfy_runtime_ref_gates"
)
BUNDLE_PACKAGING_FILE = "tools/ops_runners/runtime/canary_evidence.py"
RUNTIME_EVENT = "polisyos.runtime.evidence.normative_applicability_report.v1"
SCORECARD_GATE = "lex_normative_applicability"
READINESS_CHECK = "production_quality.runtime_required_refs"
SCHEMA_CONTRACT = "runtime_quality.normative_applicability_report.v1"
MINIMAL_MCG_CATALOG = {
    "serious_canary_runtime_refs": "Runtime refs are emitted for the minimal harness fixture."
}


BASE_INVARIANT: dict[str, Any] = {
    "invariant_id": "HDS-MCG-001",
    "minimum_closeout_gate": "serious_canary_runtime_refs",
    "pql_id": "PQL-001",
    "final_owner": "runtime.quality.closeout",
    "producer_owners": ["lex.normative_applicability"],
    "runtime_event_names": [RUNTIME_EVENT],
    "required_artifact_kinds": ["normative_applicability_report"],
    "required_ref_keys": ["normative_applicability_report_ref"],
    "evidence_classes": ["authority_bearing"],
    "allowed_provenance_kinds": ["runtime_emitted"],
    "required_schema_contracts": [SCHEMA_CONTRACT],
    "scorecard_gate_names": [SCORECARD_GATE],
    "readiness_check": READINESS_CHECK,
    "approval_policy": "requires_verified_scorecard",
    "override_policy": "not_overridable",
    "non_overridable_blockers": ["authority_cas_missing"],
    "dashboard_projection_policy": "projection_only",
    "public_artifact_policy": "not_public_exportable",
    "conflict_policy": "fail_closed",
    "failure_code": "hds_runtime_refs_missing",
    "diagnostic_owner": "team-runtime",
    "dependencies": [],
    "consumers": ["runtime.scorecard"],
    "next_diagnostic_command": (
        "uv run pytest tests/unit/runtime/quality/"
        "test_runtime_quality_negative.py -q"
    ),
    "negative_tests": [NEGATIVE_TEST_REF],
}


BASE_FITNESS_FUNCTION: dict[str, Any] = {
    "fitness_id": "fitness.hds.mcg.001.runtime_refs",
    "invariant_id": "HDS-MCG-001",
    "minimum_closeout_gate": "serious_canary_runtime_refs",
    "pql_id": "PQL-001",
    "fitness_type": "negative_control",
    "failure_code": "hds_runtime_refs_missing",
    "runtime_events": [RUNTIME_EVENT],
    "cas_artifact_kinds": ["normative_applicability_report"],
    "ref_keys": ["normative_applicability_report_ref"],
    "bundle_packaging_files": [BUNDLE_PACKAGING_FILE],
    "scorecard_gates": [SCORECARD_GATE],
    "readiness_checks": [READINESS_CHECK],
    "approval_public_policies": [
        "requires_verified_scorecard",
        "not_public_exportable",
    ],
    "dashboard_projection_policies": ["projection_only"],
    "negative_tests": [NEGATIVE_TEST_REF],
    "next_diagnostic_commands": [
        "uv run pytest tests/unit/runtime/quality/test_runtime_quality_negative.py -q"
    ],
    "proof_sources": [NEGATIVE_TEST_REF],
}


def test_actual_repository_proof_harness_passes() -> None:
    payload = harness.build_proof_payload(repo_root=REPO_ROOT)

    assert payload["status"] == "pass", payload["violations"]
    assert payload["summary"]["invariant_count"] >= 1
    assert payload["summary"]["violation_count"] == 0


def test_proof_harness_accepts_complete_minimum_closeout_gate(tmp_path: Path) -> None:
    repo_root = _write_minimal_hds_repo(tmp_path)

    payload = harness.build_proof_payload(
        repo_root=repo_root,
        minimum_closeout_gates=MINIMAL_MCG_CATALOG,
    )

    assert payload["status"] == "pass"
    assert payload["summary"]["invariant_count"] == 1
    assert payload["violations"] == []
    proof = payload["invariant_proofs"][0]
    assert proof["invariant_id"] == "HDS-MCG-001"
    assert proof["proof_status"] == "pass"
    assert proof["negative_tests"] == [NEGATIVE_TEST_REF]


def test_proof_harness_reports_missing_registry_field(tmp_path: Path) -> None:
    invariant = copy.deepcopy(BASE_INVARIANT)
    invariant.pop("failure_code")
    repo_root = _write_minimal_hds_repo(tmp_path, invariant=invariant)

    payload = harness.build_proof_payload(
        repo_root=repo_root,
        minimum_closeout_gates=MINIMAL_MCG_CATALOG,
    )

    assert payload["status"] == "fail"
    assert _violation_codes(payload) >= {"hds_invariant_registry_field_missing"}
    assert _proof_types(payload) >= {"invariant_registry_field"}


def test_proof_harness_reports_missing_negative_test(tmp_path: Path) -> None:
    invariant = copy.deepcopy(BASE_INVARIANT)
    invariant["negative_tests"] = []
    fitness = copy.deepcopy(BASE_FITNESS_FUNCTION)
    fitness["negative_tests"] = []
    repo_root = _write_minimal_hds_repo(
        tmp_path,
        invariant=invariant,
        fitness_function=fitness,
    )

    payload = harness.build_proof_payload(
        repo_root=repo_root,
        minimum_closeout_gates=MINIMAL_MCG_CATALOG,
    )

    assert payload["status"] == "fail"
    assert _violation_codes(payload) >= {"hds_proof_missing_negative_test"}
    assert _proof_types(payload) >= {"negative_test"}


def test_proof_harness_reports_missing_runtime_event(tmp_path: Path) -> None:
    repo_root = _write_minimal_hds_repo(tmp_path, event_names=[])

    payload = harness.build_proof_payload(
        repo_root=repo_root,
        minimum_closeout_gates=MINIMAL_MCG_CATALOG,
    )

    assert payload["status"] == "fail"
    assert _violation_codes(payload) >= {"hds_proof_missing_runtime_event"}
    assert _proof_types(payload) >= {"runtime_event"}


def test_proof_harness_reports_missing_scorecard_gate_registry_row(
    tmp_path: Path,
) -> None:
    repo_root = _write_minimal_hds_repo(tmp_path, include_scorecard_gate_row=False)

    payload = harness.build_proof_payload(
        repo_root=repo_root,
        minimum_closeout_gates=MINIMAL_MCG_CATALOG,
    )

    assert payload["status"] == "fail"
    assert _violation_codes(payload) >= {"hds_proof_missing_scorecard_gate"}
    assert _proof_types(payload) >= {"scorecard_gate"}


def test_proof_harness_reports_unknown_readiness_check_name(tmp_path: Path) -> None:
    invariant = copy.deepcopy(BASE_INVARIANT)
    invariant["readiness_check"] = "production_quality.not_a_real_check"
    fitness = copy.deepcopy(BASE_FITNESS_FUNCTION)
    fitness["readiness_checks"] = ["production_quality.not_a_real_check"]
    repo_root = _write_minimal_hds_repo(
        tmp_path,
        invariant=invariant,
        fitness_function=fitness,
    )

    payload = harness.build_proof_payload(
        repo_root=repo_root,
        minimum_closeout_gates=MINIMAL_MCG_CATALOG,
    )

    assert payload["status"] == "fail"
    assert _violation_codes(payload) >= {"hds_proof_missing_readiness_check"}
    assert _proof_types(payload) >= {"readiness_check"}


def test_proof_harness_reports_missing_readiness_check(tmp_path: Path) -> None:
    fitness = copy.deepcopy(BASE_FITNESS_FUNCTION)
    fitness["readiness_checks"] = []
    repo_root = _write_minimal_hds_repo(tmp_path, fitness_function=fitness)

    payload = harness.build_proof_payload(
        repo_root=repo_root,
        minimum_closeout_gates=MINIMAL_MCG_CATALOG,
    )

    assert payload["status"] == "fail"
    assert _violation_codes(payload) >= {"hds_proof_missing_readiness_check"}
    assert _proof_types(payload) >= {"readiness_check"}


@pytest.mark.parametrize(
    "proof_source",
    [
        "architecture/baselines/production_quality/evidence_inventory.json",
        "tests/fixtures/runtime_quality/invariant_registry/runtime_authority_invariant_pass.json",
        "quality_evidence/quality_scorecard.json",
        "docs/runbooks/honest-diagnostics.md",
        "apps/runtime-dashboard/src/features/runs/components/CloseoutProjection.tsx",
    ],
)
def test_proof_harness_rejects_non_runtime_sources_as_only_proof(
    proof_source: str,
    tmp_path: Path,
) -> None:
    fitness = copy.deepcopy(BASE_FITNESS_FUNCTION)
    fitness["proof_sources"] = [proof_source]
    repo_root = _write_minimal_hds_repo(tmp_path, fitness_function=fitness)

    payload = harness.build_proof_payload(
        repo_root=repo_root,
        minimum_closeout_gates=MINIMAL_MCG_CATALOG,
    )

    assert payload["status"] == "fail"
    assert _violation_codes(payload) >= {"hds_proof_missing_admissible_source"}
    assert _proof_types(payload) >= {"admissible_proof_source"}


def test_proof_harness_rejects_scorecard_gate_without_runtime_producer_evidence(
    tmp_path: Path,
) -> None:
    repo_root = _write_minimal_hds_repo(tmp_path, event_authority_role="projection_only")

    payload = harness.build_proof_payload(
        repo_root=repo_root,
        minimum_closeout_gates=MINIMAL_MCG_CATALOG,
    )

    assert payload["status"] == "fail"
    assert _violation_codes(payload) >= {"hds_proof_missing_runtime_producer_evidence"}
    assert _proof_types(payload) >= {"runtime_producer_evidence"}


def test_proof_harness_reports_orphan_scorecard_gate(tmp_path: Path) -> None:
    repo_root = _write_minimal_hds_repo(tmp_path, extra_scorecard_gate="orphan_gate")

    payload = harness.build_proof_payload(
        repo_root=repo_root,
        minimum_closeout_gates=MINIMAL_MCG_CATALOG,
    )

    assert payload["status"] == "fail"
    assert _violation_codes(payload) >= {"hds_orphan_scorecard_gate"}


def _write_minimal_hds_repo(
    tmp_path: Path,
    *,
    invariant: dict[str, Any] | None = None,
    fitness_function: dict[str, Any] | None = None,
    event_names: list[str] | None = None,
    event_authority_role: str = "runtime_authority",
    include_scorecard_gate_row: bool = True,
    extra_scorecard_gate: str | None = None,
) -> Path:
    repo_root = tmp_path
    production_quality = repo_root / "architecture" / "production_quality"
    baseline_dir = repo_root / "architecture" / "baselines" / "production_quality"
    tests_dir = repo_root / "tests" / "unit" / "runtime" / "quality"
    scorecard_dir = repo_root / "src" / "polisyos" / "runtime" / "quality"
    bundle_file = repo_root / BUNDLE_PACKAGING_FILE
    production_quality.mkdir(parents=True)
    baseline_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)
    scorecard_dir.mkdir(parents=True)
    bundle_file.parent.mkdir(parents=True)
    bundle_file.write_text("PACKAGES_RUNTIME_TRUTH = True\n", encoding="utf-8")
    (scorecard_dir / "scorecard.py").write_text(
        "\n".join(
            [
                "def build_quality_scorecard():",
                "    return _gate(",
                f'        name="{SCORECARD_GATE}",',
                '        stage="lex",',
                '        status="pass",',
                '        layer="lex",',
                '        message="ok",',
                "    )",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tests_dir / "test_runtime_quality_negative.py").write_text(
        "\n".join(
            [
                "def test_bundle_local_quality_evidence_paths_do_not_satisfy_runtime_ref_gates():",
                '    invariant_id = "HDS-MCG-001"',
                '    failure_code = "hds_runtime_refs_missing"',
                "    assert invariant_id and failure_code",
                "",
            ]
        ),
        encoding="utf-8",
    )

    invariant_payload = invariant if invariant is not None else BASE_INVARIANT
    fitness_payload = (
        fitness_function if fitness_function is not None else BASE_FITNESS_FUNCTION
    )
    _write_table_array(
        production_quality / "invariant_registry.toml",
        "invariants",
        [invariant_payload],
    )
    _write_event_registry(
        production_quality / "diagnostic_event_types.toml",
        event_names if event_names is not None else [RUNTIME_EVENT],
        authority_role=event_authority_role,
    )
    _write_source_truth_lattice(production_quality / "source_truth_lattice.toml")
    _write_schema_compatibility(production_quality / "schema_compatibility.toml")
    _write_mode_policy(production_quality / "mode_and_fallback_policy.toml")
    _write_fitness_registry(
        production_quality / "diagnostic_fitness_functions.toml",
        [fitness_payload],
        include_scorecard_gate_row=include_scorecard_gate_row,
        extra_scorecard_gate=extra_scorecard_gate,
    )
    (baseline_dir / "evidence_inventory.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.production_quality_evidence_inventory.v1",
                "quality_reports": [
                    {
                        "id": "lex.normative_evidence",
                        "status": "runtime_emitted",
                        "expected_ref": (
                            "runtime_quality_ref#"
                            "normative_applicability_report_ref"
                        ),
                        "producer": {"name": "lex.normative_applicability"},
                    }
                ],
                "serious_profile_required_refs": [],
                "validators": [],
                "quality_artifact_fields": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return repo_root


def _write_event_registry(
    path: Path,
    event_names: list[str],
    *,
    authority_role: str,
) -> None:
    lines = ['[registry]', 'name = "hds-test-events"', 'version = "1"', ""]
    for event_name in event_names:
        lines.extend(
            [
                "[[event_types]]",
                f"name = {_toml_value(event_name)}",
                'category = "runtime_evidence"',
                'description = "Runtime authority event for proof harness tests."',
                'owner = "lex.normative_applicability"',
                f"authority_role = {_toml_value(authority_role)}",
                "serious_no_sampling = true",
                'artifact_kinds = ["normative_applicability_report"]',
                'ref_keys = ["normative_applicability_report_ref"]',
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_source_truth_lattice(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "[[field_families]]",
                'name = "runtime_refs"',
                'authoritative_producer = "runtime.cas"',
                'required_ref_keys = ["normative_applicability_report_ref"]',
                'allowed_projection_surfaces = ["runtime.dashboard_projection"]',
                'allowed_package_surfaces = ["runtime.canary_bundle"]',
                f"bundle_packaging_files = [{_toml_value(BUNDLE_PACKAGING_FILE)}]",
                'conflict_failure_code = "hds_runtime_ref_authority_conflict"',
                'adapter_semantic_preservation_requirements = ["ref_identity"]',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_schema_compatibility(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "[[schema_compatibility]]",
                f"schema_contract = {_toml_value(SCHEMA_CONTRACT)}",
                'reader_contracts = ["runtime.scorecard", "runtime.readiness"]',
                'decision = "compatible"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_mode_policy(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "[[mode_policies]]",
                'profile = "production"',
                "closeout_allowed = true",
                'fallback_policy = "fail_closed"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_fitness_registry(
    path: Path,
    functions: list[dict[str, Any]],
    *,
    include_scorecard_gate_row: bool,
    extra_scorecard_gate: str | None,
) -> None:
    lines = [
        "[registry]",
        'schema_version = "policyos.diagnostic_fitness_functions.v1"',
        'owner = "team-assurance"',
        "",
    ]
    for function in functions:
        lines.extend(_render_table_array("fitness_functions", function))
    if include_scorecard_gate_row:
        lines.extend(
            [
                "[[scorecard_gates]]",
                f"gate_name = {_toml_value(SCORECARD_GATE)}",
                'invariant_id = "HDS-MCG-001"',
                "",
            ]
        )
    if extra_scorecard_gate:
        lines.extend(
            [
                "[[scorecard_gates]]",
                f"gate_name = {_toml_value(extra_scorecard_gate)}",
                'invariant_id = "HDS-MCG-404"',
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_table_array(path: Path, name: str, rows: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    for row in rows:
        lines.extend(_render_table_array(name, row))
    path.write_text("\n".join(lines), encoding="utf-8")


def _render_table_array(name: str, row: dict[str, Any]) -> list[str]:
    lines = [f"[[{name}]]"]
    for key, value in row.items():
        lines.append(f"{key} = {_toml_value(value)}")
    lines.append("")
    return lines


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if value is None:
        raise TypeError("TOML test fixtures do not use null values")
    return json.dumps(value)


def _violation_codes(payload: dict[str, Any]) -> set[str]:
    return {str(violation["code"]) for violation in payload["violations"]}


def _proof_types(payload: dict[str, Any]) -> set[str]:
    return {str(violation["proof_type"]) for violation in payload["violations"]}
