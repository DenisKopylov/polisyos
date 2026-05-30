from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from tools.quality.validation import build_policy_design_case_wave40_readiness as build
from tools.quality.validation import check_policy_design_case_wave40_readiness as check

REPO_ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = Path(
    "_build/policy-design-case/rebaseline/wave-36/deterministic_canary_matrix.json"
)
SERIOUS_LANE_ID = (
    "profile-research__provider-simulated__data-canonical_production"
    "__scenario-public_golden__ui-api_only"
)


def test_wave40_build_records_final_readiness_bundle_coverage_and_exit_fence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wave40_dir = tmp_path / "wave-40"
    _patch_wave40_inputs(monkeypatch)
    wave35e_dir, wave35h_dir, matrix_path = _write_wave40_prerequisites(tmp_path)

    outputs = build.build_wave40_readiness_outputs(
        repo_root=REPO_ROOT,
        wave35e_dir=wave35e_dir,
        wave35h_dir=wave35h_dir,
        wave40_dir=wave40_dir,
        matrix_run_json=matrix_path,
    )

    closeout = outputs["closeout"]
    exit_fence = outputs["exit_fence"]

    assert closeout["schema_version"] == build.SCHEMA_VERSION
    assert closeout["status"] == "pass"
    assert closeout["readiness_aggregator"]["status"] == "pass"
    assert closeout["readiness_aggregator"]["minimum_closeout_gate_failure_count"] == 0
    assert closeout["bundle_inspection"]["selected_serious_count"] == 1
    assert closeout["coverage"]["summary"]["target_failure_count"] == 0
    assert closeout["static_inventory"]["counts_toward_runtime_closeout"] is False
    assert closeout["sdd_record_family_mapping"]["status"] == "pass"
    assert closeout["sdd_record_family_mapping"]["runtime_record_family_coverage"][
        "status"
    ] == "pass"
    assert closeout["pass1b_closeout"]["status"] == "pass"
    assert exit_fence["status"] == "pass"
    assert exit_fence["readiness_serious_failure_count"] == 0
    assert exit_fence["policy_design_case_coverage_targets_met"] is True
    assert exit_fence["static_inventory_is_producer_map_only"] is True

    assert check.validate_wave40_readiness(repo_root=REPO_ROOT, wave40_dir=wave40_dir) == []


def test_wave40_validator_rejects_static_inventory_as_runtime_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wave40_dir = tmp_path / "wave-40"
    _patch_wave40_inputs(monkeypatch)
    wave35e_dir, wave35h_dir, matrix_path = _write_wave40_prerequisites(tmp_path)
    build.build_wave40_readiness_outputs(
        repo_root=REPO_ROOT,
        wave35e_dir=wave35e_dir,
        wave35h_dir=wave35h_dir,
        wave40_dir=wave40_dir,
        matrix_run_json=matrix_path,
    )

    closeout_path = wave40_dir / build.CLOSEOUT_OUTPUT
    closeout = json.loads(closeout_path.read_text(encoding="utf-8"))
    closeout["static_inventory"]["counts_toward_runtime_closeout"] = True
    closeout_path.write_text(json.dumps(closeout, indent=2) + "\n", encoding="utf-8")

    errors = check.validate_wave40_readiness(repo_root=REPO_ROOT, wave40_dir=wave40_dir)

    assert any("static inventory" in error for error in errors)


def test_wave40_validator_rejects_pass1b_missing_owner_or_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wave40_dir = tmp_path / "wave-40"
    _patch_wave40_inputs(monkeypatch)
    wave35e_dir, wave35h_dir, matrix_path = _write_wave40_prerequisites(tmp_path)
    build.build_wave40_readiness_outputs(
        repo_root=REPO_ROOT,
        wave35e_dir=wave35e_dir,
        wave35h_dir=wave35h_dir,
        wave40_dir=wave40_dir,
        matrix_run_json=matrix_path,
    )

    closeout_path = wave40_dir / build.CLOSEOUT_OUTPUT
    closeout = json.loads(closeout_path.read_text(encoding="utf-8"))
    closeout["pass1b_closeout"]["pdd_rows"][0]["owner"] = ""
    closeout_path.write_text(json.dumps(closeout, indent=2) + "\n", encoding="utf-8")

    errors = check.validate_wave40_readiness(repo_root=REPO_ROOT, wave40_dir=wave40_dir)

    assert any("Pass 1B" in error and "owner" in error for error in errors)


def test_wave40_validator_rejects_sdd_mapping_without_runtime_record_family_coverage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wave40_dir = tmp_path / "wave-40"
    _patch_wave40_inputs(monkeypatch)
    wave35e_dir, wave35h_dir, matrix_path = _write_wave40_prerequisites(tmp_path)
    build.build_wave40_readiness_outputs(
        repo_root=REPO_ROOT,
        wave35e_dir=wave35e_dir,
        wave35h_dir=wave35h_dir,
        wave40_dir=wave40_dir,
        matrix_run_json=matrix_path,
    )

    closeout_path = wave40_dir / build.CLOSEOUT_OUTPUT
    closeout = json.loads(closeout_path.read_text(encoding="utf-8"))
    closeout["sdd_record_family_mapping"].pop("runtime_record_family_coverage", None)
    closeout_path.write_text(json.dumps(closeout, indent=2) + "\n", encoding="utf-8")

    errors = check.validate_wave40_readiness(repo_root=REPO_ROOT, wave40_dir=wave40_dir)

    assert any("runtime record-family coverage" in error for error in errors)


def _patch_wave40_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        build.check_policy_design_case_wave35h_provenance,
        "validate_wave35h_provenance",
        lambda **_kwargs: [],
    )
    monkeypatch.setattr(
        build.gate,
        "build_readiness_payload",
        lambda **_kwargs: _readiness_payload(),
    )
    monkeypatch.setattr(
        build.inspect_evidence_bundles,
        "build_evidence_bundle_inspection_report",
        lambda **_kwargs: _bundle_inspection_payload(),
    )
    monkeypatch.setattr(
        build.coverage,
        "build_coverage_payload",
        lambda **_kwargs: _coverage_payload(),
    )
    monkeypatch.setattr(
        build.drift,
        "build_policy_design_case_drift_payload",
        lambda **_kwargs: _drift_payload(),
    )
    monkeypatch.setattr(
        build.inventory,
        "build_inventory",
        lambda *_args, **_kwargs: _inventory_payload(),
    )
    monkeypatch.setattr(
        build,
        "build_policy_design_case_record_registry_report",
        lambda: _registry_report(),
    )
    monkeypatch.setattr(
        build.pass1b,
        "build_pass1b_hardening_payload",
        lambda **_kwargs: _pass1b_payload(),
    )


def _write_wave40_prerequisites(tmp_path: Path) -> tuple[Path, Path, Path]:
    wave35e_dir = tmp_path / "wave-35E"
    wave35h_dir = tmp_path / "wave-35H"
    matrix_path = tmp_path / MATRIX_PATH
    wave35e_dir.mkdir(parents=True)
    wave35h_dir.mkdir(parents=True)
    matrix_path.parent.mkdir(parents=True)
    _write_json(
        wave35h_dir / "wave35h_exit_fence.json",
        {
            "status": "pass",
            "wave40_authority_decision": "allowed",
            "runtime_owned_provenance_count": 6,
            "not_closeout_authority_count": 0,
        },
    )
    for filename in (
        "implementation_feasibility_ledger.json",
        "contestability_appeals_ledger.json",
    ):
        _write_json(
            wave35e_dir / filename,
            {
                "runtime_enforcement_evidence": {
                    "evidence_authority_class": "runtime_emitted",
                    "manual_assertion_remaining_count": 0,
                },
                "rows": [
                    {
                        "evidence_authority_class": "runtime_emitted",
                        "runtime_owned_provenance": {
                            "producer": "runtime.institutional_provenance",
                            "artifact_refs": ["quality_evidence/institutional.json"],
                        },
                    }
                ],
            },
        )
    _write_json(
        matrix_path,
        {
            "schema_version": "policyos.policy_design_case.deterministic_matrix.v1",
            "status": "pass",
            "lanes": [],
        },
    )
    return wave35e_dir, wave35h_dir, matrix_path


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _readiness_payload() -> dict[str, object]:
    return {
        "schema_version": "policyos.production_quality.best_in_class_readiness.v1",
        "status": "pass",
        "passes_required": True,
        "passes_all": True,
        "summary": {"status_counts": {"fail": 0, "warn": 0, "pass": 3}},
        "minimum_closeout_gate_failures": [],
        "minimum_closeout_gate_warnings": [],
        "component_failures": [],
        "component_warnings": [],
        "serious_evidence_bundles": [
            {"source": "matrix_run_json", "root": "serious-bundle"}
        ],
    }


def _bundle_inspection_payload() -> dict[str, object]:
    return {
        "schema_version": "policyos.policy_design_case.evidence_bundle_inspection.v1",
        "status": "pass",
        "summary": {
            "selected_serious_count": 1,
            "closeout_ready_count": 1,
            "finding_count": 0,
            "fail_count": 0,
            "warn_count": 0,
        },
        "bundle_inspections": [
            {"lane_id": SERIOUS_LANE_ID, "closeout_ready": True, "findings": []}
        ],
        "findings": [],
    }


def _coverage_payload() -> dict[str, object]:
    return {
        "schema_version": "policyos.policy_design_case.coverage.v1",
        "mode": "final_targets",
        "summary": {"status": "pass", "target_failure_count": 0, "target_failures": []},
        "metrics": {},
    }


def _drift_payload() -> dict[str, object]:
    return {
        "schema_version": "policyos.policy_design_case.drift.v1",
        "status": "pass",
        "reuse_violation_count": 0,
        "parallel_case_authority_violation_count": 0,
        "profile_taxonomy_violation_count": 0,
        "violations": [],
        "capability_map": {"target_capability_count": 27},
    }


def _inventory_payload() -> dict[str, object]:
    return {
        "schema_version": "policyos.production_quality.evidence_inventory.v1",
        "mode": "read_only_inventory",
        "summary": {
            "quality_report_status_counts": {
                "manual_input": 0,
                "fixture_input": 0,
                "missing": 0,
                "runtime_emitted": 2,
            },
            "required_ref_status_counts": {
                "manual_input": 0,
                "fixture_input": 0,
                "missing": 0,
                "runtime_emitted": 3,
            },
            "missing_or_input_required_producers": [],
        },
        "readiness_aggregator_contract": {
            "stable_json": True,
            "sort_keys": True,
            "blocking_statuses_for_serious_profile": [
                "manual_input",
                "fixture_input",
                "missing",
            ],
        },
    }


def _registry_report() -> dict[str, object]:
    row = {
        "family_id": "intent_authoring_and_capture_risk.v1",
        "producer_owner": "team-runtime-control",
        "schema_name": "policyos.policy_design_case.intent.v1",
        "scorecard_gate": "policy_design_case.intent.present_or_blocked",
        "readiness_check": "policy_design_case.minimum_record_registry",
        "enforcement_function": (
            "polisyos.runtime.quality.policy_design_case."
            "validate_policy_design_case_record_registry_payload"
        ),
        "next_diagnostic_command": (
            "uv run pytest "
            "tests/unit/runtime/quality/test_policy_design_case_record_registry.py -q"
        ),
        "maturity_floor": "stub_or_typed_blocker",
        "applicability_evidence": {"kind": "sdd_minimum_record_family"},
    }
    runtime_coverage_row = {
        "family_id": "intent_authoring_and_capture_risk.v1",
        "status": "pass",
        "schema_owner": "team-runtime-quality",
        "producer_owner": "team-runtime-control",
        "reader_owner": "team-quality-closeout",
        "schema_name": "policyos.policy_design_case.intent.v1",
        "scorecard_gate": "policy_design_case.intent.present_or_blocked",
        "readiness_gate": "policy_design_case.record_family_coverage",
        "runtime_record_count": 1,
        "authority_status": "runtime_authority_present",
        "governance_surfaces": [],
    }
    runtime_record = {
        "record_id": "intent-runtime-record-1",
        "family_id": "intent_authoring_and_capture_risk.v1",
        "schema_name": "policyos.policy_design_case.intent.v1",
        "producer_owner": "team-runtime-control",
        "reader_owner": "team-quality-closeout",
        "readiness_gate": "policy_design_case.record_family_coverage",
        "evidence_ref": "sha256:" + ("1" * 64),
        "runtime_event_ref": "event://policy-design-case/intent/1",
    }
    return {
        "schema_version": "policyos.policy_design_case.record_registry.validation.v1",
        "status": "pass",
        "summary": {"record_family_count": 1, "required_family_count": 1, "issue_count": 0},
        "record_families": [row],
        "runtime_record_family_coverage": {
            "schema_version": "policyos.runtime.policy_design_case.record_family_coverage.v1",
            "status": "pass",
            "summary": {
                "record_family_count": 1,
                "runtime_record_count": 1,
                "issue_count": 0,
                "required_family_count": 1,
            },
            "record_families": [runtime_coverage_row],
            "records": [runtime_record],
            "issues": [],
        },
        "issues": [],
    }


def _pass1b_payload() -> dict[str, object]:
    return {
        "schema_version": "policyos.policy_design_case.pass1b_hardening.v1",
        "status": "pass",
        "summary": {"pdd_count": 1, "implemented_pdd_count": 1, "issue_count": 0},
        "groups": {
            "group": {
                "owner": "team-quality-closeout",
                "implemented_evidence_contract": "policy_design_case.intent.v1",
                "scorecard_gate": "policy_design_case.intent.present_or_blocked",
                "readiness_check": "policy_design_case.minimum_record_registry",
                "remaining_blocker": "none",
                "authority_boundary": "record_is_evidence_only",
                "pdd_closeout": {
                    "PDD-001": {
                        "owner": "team-quality-closeout",
                        "implemented_evidence_contract": "policy_design_case.intent.v1",
                        "scorecard_gate": "policy_design_case.intent.present_or_blocked",
                        "readiness_check": "policy_design_case.minimum_record_registry",
                        "closeout_gate": "policy_design_case.intent.closeout",
                        "remaining_blocker": "none",
                        "coverage_kind": "concrete_evidence_contract",
                        "authority_boundary": "record_is_evidence_only",
                    }
                },
            }
        },
        "issues": [],
    }
