#!/usr/bin/env python3
"""Build Policy Design Case Wave 40 readiness and bundle-inspection closeout."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.ci import check_policyos_production_quality_best_in_class as gate
from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation import build_policy_design_case_coverage as coverage
from tools.quality.validation import check_policy_design_case_drift as drift
from tools.quality.validation import check_policy_design_case_pass1b_hardening as pass1b
from tools.quality.validation import (
    check_policy_design_case_wave35h_provenance,
    inspect_evidence_bundles,
)
from tools.quality.validation import production_quality_evidence_inventory as inventory

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.policy_design_case import (  # noqa: E402
    build_policy_design_case_record_registry_report,
)

SCHEMA_VERSION = "policyos.policy_design_case.wave40.readiness_bundle_inspection.v1"
TOOL_NAME = "quality.validation.build-policy-design-case-wave40-readiness"
WAVE35E_DIR = Path("_build/policy-design-case/rebaseline/wave-35E")
WAVE35H_DIR = Path("_build/policy-design-case/rebaseline/wave-35H")
WAVE36_DIR = Path("_build/policy-design-case/rebaseline/wave-36")
WAVE40_DIR = Path("_build/policy-design-case/rebaseline/wave-40")
DEFAULT_MATRIX_RUN_JSON = WAVE36_DIR / "deterministic_canary_matrix.json"

READINESS_OUTPUT = "readiness_aggregator.json"
BUNDLE_INSPECTION_OUTPUT = "bundle_inspection.json"
COVERAGE_OUTPUT = "coverage.json"
DRIFT_OUTPUT = "policy_design_case_drift.json"
STATIC_INVENTORY_OUTPUT = "static_inventory_producer_map.json"
SDD_MAPPING_OUTPUT = "sdd_record_family_mapping.json"
PASS1B_OUTPUT = "pass1b_closeout_mapping.json"
CLOSEOUT_OUTPUT = "wave40_readiness_bundle_inspection.json"
EXIT_FENCE_OUTPUT = "wave40_exit_fence.json"

RUNTIME_OWNED_AUTHORITIES = {"runtime_emitted", "runtime_derived"}
BLOCKING_INVENTORY_STATUSES = ("manual_input", "fixture_input", "missing")
PASS1B_REQUIRED_FIELDS = (
    "owner",
    "implemented_evidence_contract",
    "scorecard_gate",
    "readiness_check",
    "closeout_gate",
    "remaining_blocker",
    "coverage_kind",
    "authority_boundary",
)
SDD_REQUIRED_FIELDS = (
    "family_id",
    "producer_owner",
    "schema_name",
    "scorecard_gate",
    "readiness_check",
    "enforcement_function",
    "next_diagnostic_command",
    "maturity_floor",
)


def build_wave40_readiness_outputs(
    *,
    repo_root: Path = REPO_ROOT,
    wave35e_dir: Path = WAVE35E_DIR,
    wave35h_dir: Path = WAVE35H_DIR,
    wave40_dir: Path = WAVE40_DIR,
    matrix_run_json: Path = DEFAULT_MATRIX_RUN_JSON,
) -> dict[str, Any]:
    """Build all Wave 40 closeout artifacts."""

    repo_root = repo_root.resolve()
    wave35e_path = _resolve(repo_root, wave35e_dir)
    wave35h_path = _resolve(repo_root, wave35h_dir)
    wave40_path = _resolve(repo_root, wave40_dir)
    matrix_path = _resolve(repo_root, matrix_run_json)
    wave40_path.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now()
    entry_criteria = _entry_criteria(
        repo_root=repo_root,
        wave35e_path=wave35e_path,
        wave35h_path=wave35h_path,
        generated_at=generated_at,
    )
    readiness_payload = gate.build_readiness_payload(
        repo_root=repo_root,
        matrix_run_json=matrix_path,
        require_runtime_closeout_evidence=True,
    )
    bundle_payload = inspect_evidence_bundles.build_evidence_bundle_inspection_report(
        repo_root=repo_root,
        matrix_run_path=matrix_path,
    )
    coverage_payload = coverage.build_coverage_payload(
        repo_root=repo_root,
        require_targets=True,
    )
    drift_payload = drift.build_policy_design_case_drift_payload(repo_root=repo_root)
    inventory_payload = inventory.build_inventory(repo_root)
    registry_payload = build_policy_design_case_record_registry_report()
    pass1b_payload = pass1b.build_pass1b_hardening_payload(
        repo_root=repo_root,
        output_path=wave40_path / PASS1B_OUTPUT,
    )

    atomic_write_json(wave40_path / READINESS_OUTPUT, readiness_payload)
    atomic_write_json(wave40_path / BUNDLE_INSPECTION_OUTPUT, bundle_payload)
    atomic_write_json(wave40_path / COVERAGE_OUTPUT, coverage_payload)
    atomic_write_json(wave40_path / DRIFT_OUTPUT, drift_payload)
    atomic_write_json(wave40_path / STATIC_INVENTORY_OUTPUT, inventory_payload)
    atomic_write_json(wave40_path / SDD_MAPPING_OUTPUT, registry_payload)
    atomic_write_json(wave40_path / PASS1B_OUTPUT, pass1b_payload)

    readiness = _readiness_section(
        readiness_payload,
        matrix_path=matrix_path,
        wave40_path=wave40_path,
        repo_root=repo_root,
    )
    bundle_inspection = _bundle_inspection_section(
        bundle_payload,
        matrix_path=matrix_path,
        wave40_path=wave40_path,
        repo_root=repo_root,
    )
    final_coverage = _coverage_section(
        coverage_payload,
        wave40_path=wave40_path,
        repo_root=repo_root,
    )
    anti_drift = _anti_drift_section(
        drift_payload,
        wave40_path=wave40_path,
        repo_root=repo_root,
    )
    static_inventory = _static_inventory_section(
        inventory_payload,
        wave40_path=wave40_path,
        repo_root=repo_root,
    )
    sdd_mapping = _sdd_record_family_mapping(
        registry_payload,
        wave40_path=wave40_path,
        repo_root=repo_root,
    )
    pass1b_closeout = _pass1b_closeout_mapping(
        pass1b_payload,
        wave40_path=wave40_path,
        repo_root=repo_root,
    )
    exit_fence = _build_exit_fence(
        generated_at=generated_at,
        entry_criteria=entry_criteria,
        readiness=readiness,
        bundle_inspection=bundle_inspection,
        final_coverage=final_coverage,
        anti_drift=anti_drift,
        static_inventory=static_inventory,
        sdd_mapping=sdd_mapping,
        pass1b_closeout=pass1b_closeout,
    )
    closeout = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "40",
        "phase": "40.1",
        "status": exit_fence["status"],
        "repo_root": str(repo_root),
        "purpose": (
            "prove final readiness and public bundle integrity after closeout commands "
            "have fresh evidence"
        ),
        "entry_criteria": entry_criteria,
        "readiness_aggregator": readiness,
        "bundle_inspection": bundle_inspection,
        "coverage": final_coverage,
        "anti_drift": anti_drift,
        "static_inventory": static_inventory,
        "sdd_record_family_mapping": sdd_mapping,
        "pass1b_closeout": pass1b_closeout,
        "exit_fence_ref": _rel_path(wave40_path / EXIT_FENCE_OUTPUT, repo_root),
        "verification": {
            "acceptance_commands": [
                (
                    "uv run pytest "
                    "tests/repo_quality/tools/test_policy_design_case_wave40.py -q"
                ),
                (
                    "uv run python tools/quality/validation/"
                    "check_policy_design_case_wave40_readiness.py --repo-root ."
                ),
            ],
        },
    }
    exit_fence["closeout_artifact_ref"] = _rel_path(wave40_path / CLOSEOUT_OUTPUT, repo_root)
    atomic_write_json(wave40_path / CLOSEOUT_OUTPUT, closeout)
    atomic_write_json(wave40_path / EXIT_FENCE_OUTPUT, exit_fence)
    return {
        "closeout": closeout,
        "exit_fence": exit_fence,
        "readiness": readiness_payload,
        "bundle_inspection": bundle_payload,
        "coverage": coverage_payload,
        "anti_drift": drift_payload,
    }


def _entry_criteria(
    *,
    repo_root: Path,
    wave35e_path: Path,
    wave35h_path: Path,
    generated_at: str,
) -> list[dict[str, Any]]:
    rows = [
        _wave35h_exit_fence_entry(wave35h_path / "wave35h_exit_fence.json"),
        _validator_entry(
            check_id="wave35h_provenance_validator",
            command=(
                "uv run python tools/quality/validation/"
                "check_policy_design_case_wave35h_provenance.py --repo-root ."
            ),
            errors=check_policy_design_case_wave35h_provenance.validate_wave35h_provenance(
                repo_root=repo_root,
            ),
        ),
        _institutional_ledgers_entry(wave35e_path),
    ]
    for row in rows:
        row["checked_at"] = generated_at
    return rows


def _wave35h_exit_fence_entry(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    payload = _load_json(path)
    if payload.get("status") != "pass":
        errors.append("Wave 35H exit fence status must be pass")
    if payload.get("wave40_authority_decision") != "allowed":
        errors.append("Wave 35H must allow Wave 40 authority")
    return {
        "id": "wave35h_exit_fence_allows_wave40",
        "kind": "artifact_field",
        "artifact_path": str(path),
        "status": "pass" if not errors else "fail",
        "observed": {
            "status": payload.get("status"),
            "wave40_authority_decision": payload.get("wave40_authority_decision"),
            "runtime_owned_provenance_count": payload.get("runtime_owned_provenance_count"),
            "not_closeout_authority_count": payload.get("not_closeout_authority_count"),
        },
        "errors": errors,
    }


def _validator_entry(*, check_id: str, command: str, errors: Sequence[str]) -> dict[str, Any]:
    return {
        "id": check_id,
        "kind": "validator_command",
        "command": command,
        "status": "pass" if not errors else "fail",
        "errors": list(errors),
    }


def _institutional_ledgers_entry(wave35e_path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for filename, surface in (
        ("implementation_feasibility_ledger.json", "implementation_feasibility"),
        ("contestability_appeals_ledger.json", "contestability_appeals"),
    ):
        path = wave35e_path / filename
        payload = _load_json(path)
        runtime_evidence = _mapping(payload.get("runtime_enforcement_evidence"))
        manual_remaining = _int(runtime_evidence.get("manual_assertion_remaining_count"))
        if runtime_evidence.get("evidence_authority_class") not in RUNTIME_OWNED_AUTHORITIES:
            errors.append(f"{filename}: runtime enforcement evidence is not runtime-owned")
        if manual_remaining != 0:
            errors.append(f"{filename}: manual assertions remain")
        for index, row in enumerate(_mapping_rows(payload, "rows"), start=1):
            authority = str(
                row.get("evidence_authority_class")
                or row.get("evidence_authority")
                or ""
            )
            runtime_provenance = _mapping(row.get("runtime_owned_provenance"))
            row_status = "pass"
            row_errors: list[str] = []
            if authority in {"manual_assertion", "not_closeout_authority"}:
                row_status = "fail"
                row_errors.append(f"authority remains {authority}")
            if authority not in RUNTIME_OWNED_AUTHORITIES:
                row_status = "fail"
                row_errors.append(f"authority is not runtime-owned: {authority}")
            if not runtime_provenance:
                row_status = "fail"
                row_errors.append("missing runtime_owned_provenance")
            if row_errors:
                errors.extend(f"{filename}: row {index}: {error}" for error in row_errors)
            rows.append(
                {
                    "ledger": filename,
                    "surface": surface,
                    "row_index": index,
                    "status": row_status,
                    "evidence_authority": authority,
                    "runtime_owned_provenance_present": bool(runtime_provenance),
                    "errors": row_errors,
                }
            )
    return {
        "id": "institutional_ledgers_runtime_owned",
        "kind": "artifact_rows",
        "status": "pass" if not errors else "fail",
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "runtime_owned_row_count": sum(1 for row in rows if row["status"] == "pass"),
            "manual_assertion_count": sum(
                1 for row in rows if row["evidence_authority"] == "manual_assertion"
            ),
            "not_closeout_authority_count": sum(
                1 for row in rows if row["evidence_authority"] == "not_closeout_authority"
            ),
        },
        "errors": errors,
    }


def _readiness_section(
    payload: Mapping[str, Any],
    *,
    matrix_path: Path,
    wave40_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    minimum_failures = _as_list(payload.get("minimum_closeout_gate_failures"))
    component_failures = _as_list(payload.get("component_failures"))
    status = (
        "pass"
        if payload.get("status") == "pass"
        and payload.get("passes_all") is True
        and not minimum_failures
        and not component_failures
        else "fail"
    )
    return {
        "status": status,
        "command": (
            "uv run python tools/ci/check_policyos_production_quality_best_in_class.py "
            "--repo-root . "
            f"--matrix-run-json {_rel_path(matrix_path, repo_root)} "
            f"--output {_rel_path(wave40_path / READINESS_OUTPUT, repo_root)} "
            "--output-format json --require-passing"
        ),
        "result_path": _rel_path(wave40_path / READINESS_OUTPUT, repo_root),
        "matrix_run_json": _rel_path(matrix_path, repo_root),
        "aggregator_status": payload.get("status"),
        "passes_required": payload.get("passes_required") is True,
        "passes_all": payload.get("passes_all") is True,
        "minimum_closeout_gate_failure_count": len(minimum_failures),
        "component_failure_count": len(component_failures),
        "minimum_closeout_gate_failures": minimum_failures,
        "component_failures": component_failures,
    }


def _bundle_inspection_section(
    payload: Mapping[str, Any],
    *,
    matrix_path: Path,
    wave40_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    summary = _mapping(payload.get("summary"))
    findings = _as_list(payload.get("findings"))
    fail_count = _int(summary.get("fail_count"))
    warn_count = _int(summary.get("warn_count"))
    selected = _int(summary.get("selected_serious_count"))
    ready = _int(summary.get("closeout_ready_count"))
    return {
        "status": "pass"
        if (
            payload.get("status") == "pass"
            and fail_count == 0
            and selected > 0
            and ready == selected
        )
        else "fail",
        "command": (
            "uv run python tools/quality/validation/inspect_evidence_bundles.py "
            "--repo-root . "
            f"--matrix-run-json {_rel_path(matrix_path, repo_root)} "
            f"--json-output {_rel_path(wave40_path / BUNDLE_INSPECTION_OUTPUT, repo_root)} "
            "--require-passing"
        ),
        "result_path": _rel_path(wave40_path / BUNDLE_INSPECTION_OUTPUT, repo_root),
        "matrix_run_json": _rel_path(matrix_path, repo_root),
        "summary": dict(summary),
        "selected_serious_count": selected,
        "closeout_ready_count": ready,
        "finding_count": len(findings),
        "fail_count": fail_count,
        "warn_count": warn_count,
        "findings": findings,
        "bundle_inspections": _as_list(payload.get("bundle_inspections")),
    }


def _coverage_section(
    payload: Mapping[str, Any],
    *,
    wave40_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    summary = _mapping(payload.get("summary"))
    target_failures = _as_list(summary.get("target_failures"))
    return {
        "status": "pass"
        if payload.get("mode") == "final_targets"
        and summary.get("status") == "pass"
        and _int(summary.get("target_failure_count")) == 0
        and not target_failures
        else "fail",
        "command": (
            "uv run python tools/quality/validation/build_policy_design_case_coverage.py "
            "--repo-root . "
            f"--output-dir {_rel_path(wave40_path, repo_root)} "
            "--require-targets"
        ),
        "result_path": _rel_path(wave40_path / COVERAGE_OUTPUT, repo_root),
        "mode": payload.get("mode"),
        "summary": dict(summary),
        "target_failures": target_failures,
    }


def _anti_drift_section(
    payload: Mapping[str, Any],
    *,
    wave40_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    violations = _as_list(payload.get("violations"))
    non_goal_violations = len(violations)
    return {
        "status": "pass"
        if payload.get("status") == "pass"
        and _int(payload.get("reuse_violation_count")) == 0
        and _int(payload.get("parallel_case_authority_violation_count")) == 0
        and _int(payload.get("profile_taxonomy_violation_count")) == 0
        and non_goal_violations == 0
        else "fail",
        "command": (
            "uv run python tools/quality/validation/check_policy_design_case_drift.py "
            "--repo-root . "
            f"--json-output {_rel_path(wave40_path / DRIFT_OUTPUT, repo_root)}"
        ),
        "result_path": _rel_path(wave40_path / DRIFT_OUTPUT, repo_root),
        "reuse_violation_count": _int(payload.get("reuse_violation_count")),
        "parallel_case_authority_violation_count": _int(
            payload.get("parallel_case_authority_violation_count")
        ),
        "profile_taxonomy_violation_count": _int(payload.get("profile_taxonomy_violation_count")),
        "anti_drift_non_goal_violation_count": non_goal_violations,
        "violations": violations,
        "capability_count": _int(
            _mapping(payload.get("capability_map")).get("target_capability_count")
        ),
    }


def _static_inventory_section(
    payload: Mapping[str, Any],
    *,
    wave40_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    summary = _mapping(payload.get("summary"))
    report_counts = _mapping(summary.get("quality_report_status_counts"))
    ref_counts = _mapping(summary.get("required_ref_status_counts"))
    blocking_counts = {
        status: _int(report_counts.get(status)) + _int(ref_counts.get(status))
        for status in BLOCKING_INVENTORY_STATUSES
    }
    producer_map_only = (
        payload.get("mode") == "read_only_inventory"
        and bool(payload.get("readiness_aggregator_contract"))
        and all(count == 0 for count in blocking_counts.values())
    )
    return {
        "status": "pass" if producer_map_only else "fail",
        "result_path": _rel_path(wave40_path / STATIC_INVENTORY_OUTPUT, repo_root),
        "mode": payload.get("mode"),
        "schema_version": payload.get("schema_version"),
        "summary": dict(summary),
        "readiness_aggregator_contract": dict(
            _mapping(payload.get("readiness_aggregator_contract"))
        ),
        "blocking_status_counts": blocking_counts,
        "producer_map_only": producer_map_only,
        "counts_toward_runtime_closeout": False,
        "counts_toward_final_publication": False,
        "authority_policy": (
            "Static inventory identifies producers and required refs only; it never "
            "counts as runtime evidence."
        ),
    }


def _sdd_record_family_mapping(
    payload: Mapping[str, Any],
    *,
    wave40_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    runtime_coverage_payload = _mapping(
        payload.get("runtime_record_family_coverage")
        or payload.get("record_family_coverage")
    )
    runtime_coverage_summary = _mapping(runtime_coverage_payload.get("summary"))
    runtime_coverage_rows = {
        str(row.get("family_id")): row
        for row in _mapping_rows(runtime_coverage_payload, "record_families")
        if str(row.get("family_id") or "").strip()
    }
    runtime_coverage_issues = _as_list(runtime_coverage_payload.get("issues"))
    runtime_coverage_status = "pass"
    if not runtime_coverage_payload:
        runtime_coverage_status = "fail"
        issues.append("runtime record-family coverage missing")
    elif runtime_coverage_payload.get("status") != "pass":
        runtime_coverage_status = "fail"
        issues.append("runtime record-family coverage must pass")
    elif runtime_coverage_issues:
        runtime_coverage_status = "fail"
        issues.append("runtime record-family coverage has issues")

    for index, row in enumerate(_mapping_rows(payload, "record_families"), start=1):
        family_id = str(row.get("family_id") or f"record_families[{index}]")
        row_errors = [
            f"missing {field}"
            for field in SDD_REQUIRED_FIELDS
            if not str(row.get(field) or "").strip()
        ]
        evidence = _mapping(row.get("applicability_evidence"))
        if not evidence:
            row_errors.append("missing applicability_evidence")
        maturity = str(row.get("maturity_floor") or "")
        authority_policy = (
            "runtime_evidence"
            if row.get("applicability") in {"required", "profile_scoped", None}
            else "typed_out_of_scope_authority_policy"
        )
        if maturity != "stub_or_typed_blocker" and authority_policy != (
            "typed_out_of_scope_authority_policy"
        ):
            row_errors.append("maturity_floor is not a typed blocker policy")
        runtime_coverage_row = _mapping(runtime_coverage_rows.get(family_id))
        runtime_record_count = _int(runtime_coverage_row.get("runtime_record_count"))
        if not runtime_coverage_row:
            row_errors.append("missing runtime record-family coverage")
        elif runtime_coverage_row.get("status") != "pass":
            row_errors.append("runtime record-family coverage row must pass")
        elif authority_policy == "runtime_evidence" and runtime_record_count <= 0:
            row_errors.append("runtime record-family coverage has no concrete records")
        if row_errors:
            issues.extend(f"{family_id}: {error}" for error in row_errors)
        rows.append(
            {
                "family_id": family_id,
                "status": "pass" if not row_errors else "fail",
                "producer_owner": row.get("producer_owner"),
                "schema_name": row.get("schema_name"),
                "scorecard_gate": row.get("scorecard_gate"),
                "readiness_check": row.get("readiness_check"),
                "enforcement_function": row.get("enforcement_function"),
                "next_diagnostic_command": row.get("next_diagnostic_command"),
                "maturity_floor": row.get("maturity_floor"),
                "evidence_mapping": authority_policy,
                "runtime_record_count": runtime_record_count,
                "runtime_record_family_coverage_status": runtime_coverage_row.get(
                    "status"
                ),
                "errors": row_errors,
            }
        )
    status = (
        "pass"
        if payload.get("status") == "pass"
        and runtime_coverage_status == "pass"
        and rows
        and not issues
        else "fail"
    )
    return {
        "status": status,
        "result_path": _rel_path(wave40_path / SDD_MAPPING_OUTPUT, repo_root),
        "summary": dict(_mapping(payload.get("summary"))),
        "runtime_record_family_coverage": {
            "status": runtime_coverage_status,
            "summary": dict(runtime_coverage_summary),
            "record_family_count": _int(
                runtime_coverage_summary.get("record_family_count")
            ),
            "runtime_record_count": _int(
                runtime_coverage_summary.get("runtime_record_count")
            ),
            "issue_count": _int(runtime_coverage_summary.get("issue_count"))
            or len(runtime_coverage_issues),
            "issues": runtime_coverage_issues,
        },
        "row_count": len(rows),
        "rows": rows,
        "issues": issues,
    }


def _pass1b_closeout_mapping(
    payload: Mapping[str, Any],
    *,
    wave40_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    pdd_rows: list[dict[str, Any]] = []
    issues: list[str] = []
    groups = _mapping(payload.get("groups"))
    for group_id, group_value in sorted(groups.items()):
        group = _mapping(group_value)
        for pdd_id, row_value in sorted(_mapping(group.get("pdd_closeout")).items()):
            row = _mapping(row_value)
            row_errors = [
                f"missing {field}"
                for field in PASS1B_REQUIRED_FIELDS
                if not str(row.get(field) or "").strip()
            ]
            if row.get("coverage_kind") != "concrete_evidence_contract":
                row_errors.append("coverage_kind must be concrete_evidence_contract")
            if row.get("authority_boundary") != "record_is_evidence_only":
                row_errors.append("authority_boundary must be record_is_evidence_only")
            if row_errors:
                issues.extend(
                    f"Pass 1B {group_id}:{pdd_id}: {error}" for error in row_errors
                )
            pdd_rows.append(
                {
                    "group_id": str(group_id),
                    "pdd_id": str(pdd_id),
                    "status": "pass" if not row_errors else "fail",
                    "owner": row.get("owner"),
                    "implemented_evidence_contract": row.get(
                        "implemented_evidence_contract"
                    ),
                    "scorecard_gate": row.get("scorecard_gate"),
                    "readiness_check": row.get("readiness_check"),
                    "closeout_gate": row.get("closeout_gate"),
                    "remaining_blocker": row.get("remaining_blocker"),
                    "coverage_kind": row.get("coverage_kind"),
                    "authority_boundary": row.get("authority_boundary"),
                    "errors": row_errors,
                }
            )
    status = "pass" if payload.get("status") == "pass" and pdd_rows and not issues else "fail"
    return {
        "status": status,
        "result_path": _rel_path(wave40_path / PASS1B_OUTPUT, repo_root),
        "summary": dict(_mapping(payload.get("summary"))),
        "pdd_rows": pdd_rows,
        "issues": issues,
    }


def _build_exit_fence(
    *,
    generated_at: str,
    entry_criteria: Sequence[Mapping[str, Any]],
    readiness: Mapping[str, Any],
    bundle_inspection: Mapping[str, Any],
    final_coverage: Mapping[str, Any],
    anti_drift: Mapping[str, Any],
    static_inventory: Mapping[str, Any],
    sdd_mapping: Mapping[str, Any],
    pass1b_closeout: Mapping[str, Any],
) -> dict[str, Any]:
    entry_passed = all(row.get("status") == "pass" for row in entry_criteria)
    readiness_passed = readiness.get("status") == "pass"
    bundle_passed = bundle_inspection.get("status") == "pass"
    coverage_passed = final_coverage.get("status") == "pass"
    anti_drift_passed = anti_drift.get("status") == "pass"
    static_inventory_ok = (
        static_inventory.get("status") == "pass"
        and static_inventory.get("producer_map_only") is True
        and static_inventory.get("counts_toward_runtime_closeout") is False
    )
    sdd_passed = sdd_mapping.get("status") == "pass"
    pass1b_passed = pass1b_closeout.get("status") == "pass"
    institutional_ok = entry_passed
    status = (
        "pass"
        if entry_passed
        and readiness_passed
        and bundle_passed
        and coverage_passed
        and anti_drift_passed
        and static_inventory_ok
        and sdd_passed
        and pass1b_passed
        else "fail"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "40",
        "phase": "40.1",
        "status": status,
        "entry_criteria_passed": entry_passed,
        "readiness_aggregator_passed": readiness_passed,
        "readiness_serious_failure_count": _int(
            readiness.get("minimum_closeout_gate_failure_count")
        ),
        "bundle_inspection_passed": bundle_passed,
        "bundle_inspection_selected_serious_count": _int(
            bundle_inspection.get("selected_serious_count")
        ),
        "policy_design_case_coverage_targets_met": coverage_passed,
        "anti_drift_audit_passed": anti_drift_passed,
        "anti_drift_non_goal_violations": _int(
            anti_drift.get("anti_drift_non_goal_violation_count")
        ),
        "implementation_feasibility_and_contestability_runtime_owned": institutional_ok,
        "institutional_runtime_owned_provenance": institutional_ok,
        "static_inventory_is_producer_map_only": static_inventory_ok,
        "sdd_record_family_mapping_passed": sdd_passed,
        "pass1b_closeout_mapping_passed": pass1b_passed,
        "final_publication_decision": "allowed" if status == "pass" else "blocked",
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return payload


def _mapping_rows(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    return [row for row in _as_list(payload.get(key)) if isinstance(row, Mapping)]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (repo_root / path).resolve(strict=False)


def _rel_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave35e-dir", type=Path, default=WAVE35E_DIR)
    parser.add_argument("--wave35h-dir", type=Path, default=WAVE35H_DIR)
    parser.add_argument("--wave40-dir", type=Path, default=WAVE40_DIR)
    parser.add_argument("--matrix-run-json", type=Path, default=DEFAULT_MATRIX_RUN_JSON)
    args = parser.parse_args(argv)

    try:
        outputs = build_wave40_readiness_outputs(
            repo_root=args.repo_root,
            wave35e_dir=args.wave35e_dir,
            wave35h_dir=args.wave35h_dir,
            wave40_dir=args.wave40_dir,
            matrix_run_json=args.matrix_run_json,
        )
    except Exception as exc:
        sys.stderr.write(f"wave40-readiness-build: {exc}\n")
        return 1
    exit_fence = outputs["exit_fence"]
    sys.stdout.write(
        "wave40-readiness-build: "
        f"status={exit_fence['status']} "
        f"serious_failures={exit_fence['readiness_serious_failure_count']} "
        f"coverage_targets={exit_fence['policy_design_case_coverage_targets_met']} "
        f"final_publication={exit_fence['final_publication_decision']}\n"
    )
    return 0 if exit_fence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
