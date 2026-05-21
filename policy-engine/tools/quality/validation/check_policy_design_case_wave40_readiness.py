#!/usr/bin/env python3
"""Validate Policy Design Case Wave 40 readiness closeout artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation import build_policy_design_case_wave40_readiness as build

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)


def validate_wave40_readiness(
    *,
    repo_root: Path = REPO_ROOT,
    wave40_dir: Path = build.WAVE40_DIR,
) -> list[str]:
    repo_root = repo_root.resolve()
    wave40_path = _resolve(repo_root, wave40_dir)
    errors: list[str] = []

    closeout = _load_json(wave40_path / build.CLOSEOUT_OUTPUT, errors)
    exit_fence = _load_json(wave40_path / build.EXIT_FENCE_OUTPUT, errors)
    for filename in (
        build.READINESS_OUTPUT,
        build.BUNDLE_INSPECTION_OUTPUT,
        build.COVERAGE_OUTPUT,
        build.DRIFT_OUTPUT,
        build.STATIC_INVENTORY_OUTPUT,
        build.SDD_MAPPING_OUTPUT,
        build.PASS1B_OUTPUT,
    ):
        _load_json(wave40_path / filename, errors)
    if errors:
        return errors

    _validate_common(closeout, label="closeout", errors=errors)
    _validate_common(exit_fence, label="exit_fence", errors=errors)
    _validate_entry_criteria(closeout, errors)
    _validate_readiness(_mapping(closeout.get("readiness_aggregator")), errors)
    _validate_bundle_inspection(_mapping(closeout.get("bundle_inspection")), errors)
    _validate_coverage(_mapping(closeout.get("coverage")), errors)
    _validate_anti_drift(_mapping(closeout.get("anti_drift")), errors)
    _validate_static_inventory(_mapping(closeout.get("static_inventory")), errors)
    _validate_sdd_mapping(_mapping(closeout.get("sdd_record_family_mapping")), errors)
    _validate_pass1b(_mapping(closeout.get("pass1b_closeout")), errors)
    _validate_exit_fence(closeout=closeout, exit_fence=exit_fence, errors=errors)
    return errors


def _validate_common(
    payload: Mapping[str, Any],
    *,
    label: str,
    errors: list[str],
) -> None:
    if payload.get("schema_version") != build.SCHEMA_VERSION:
        errors.append(f"{label}: schema_version drifted")
    if payload.get("wave") != "40":
        errors.append(f"{label}: wave must be 40")
    if payload.get("phase") != "40.1":
        errors.append(f"{label}: phase must be 40.1")
    if not payload.get("tool"):
        errors.append(f"{label}: missing tool")
    if not payload.get("generated_at"):
        errors.append(f"{label}: missing generated_at")


def _validate_entry_criteria(closeout: Mapping[str, Any], errors: list[str]) -> None:
    rows = _mapping_rows(closeout, "entry_criteria")
    expected = {
        "wave35h_exit_fence_allows_wave40",
        "wave35h_provenance_validator",
        "institutional_ledgers_runtime_owned",
    }
    observed = {str(row.get("id")) for row in rows}
    missing = expected - observed
    if missing:
        errors.append(f"entry_criteria: missing Wave 40 entry checks: {sorted(missing)}")
    for row in rows:
        check_id = str(row.get("id") or "<unknown>")
        if row.get("status") != "pass":
            errors.append(f"{check_id}: entry criterion must pass")
        if row.get("errors"):
            errors.append(f"{check_id}: entry criterion has errors")
    institutional = next(
        (row for row in rows if row.get("id") == "institutional_ledgers_runtime_owned"),
        {},
    )
    summary = _mapping(_mapping(institutional).get("summary"))
    if _int(summary.get("manual_assertion_count")) != 0:
        errors.append("institutional ledgers: manual_assertion rows remain")
    if _int(summary.get("not_closeout_authority_count")) != 0:
        errors.append("institutional ledgers: not_closeout_authority rows remain")


def _validate_readiness(payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("status") != "pass":
        errors.append("readiness aggregator: status must be pass")
    if payload.get("passes_all") is not True:
        errors.append("readiness aggregator: passes_all must be true")
    if _int(payload.get("minimum_closeout_gate_failure_count")) != 0:
        errors.append("readiness aggregator: serious closeout failures must be zero")
    if _int(payload.get("component_failure_count")) != 0:
        errors.append("readiness aggregator: component failures must be zero")
    if payload.get("minimum_closeout_gate_failures"):
        errors.append("readiness aggregator: minimum_closeout_gate_failures must be empty")


def _validate_bundle_inspection(payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("status") != "pass":
        errors.append("bundle inspection: status must be pass")
    if _int(payload.get("selected_serious_count")) <= 0:
        errors.append("bundle inspection: must inspect at least one serious bundle")
    if _int(payload.get("closeout_ready_count")) != _int(payload.get("selected_serious_count")):
        errors.append("bundle inspection: every selected serious bundle must be closeout-ready")
    if _int(payload.get("fail_count")) != 0:
        errors.append("bundle inspection: fail_count must be zero")
    if payload.get("findings"):
        errors.append("bundle inspection: findings must be empty for Wave 40")


def _validate_coverage(payload: Mapping[str, Any], errors: list[str]) -> None:
    summary = _mapping(payload.get("summary"))
    if payload.get("status") != "pass":
        errors.append("coverage: Wave 40 coverage section must pass")
    if payload.get("mode") != "final_targets":
        errors.append("coverage: mode must be final_targets")
    if summary.get("status") != "pass":
        errors.append("coverage: summary status must be pass")
    if _int(summary.get("target_failure_count")) != 0:
        errors.append("coverage: target_failure_count must be zero")
    if payload.get("target_failures"):
        errors.append("coverage: target_failures must be empty")


def _validate_anti_drift(payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("status") != "pass":
        errors.append("anti-drift: status must be pass")
    for key in (
        "reuse_violation_count",
        "parallel_case_authority_violation_count",
        "profile_taxonomy_violation_count",
        "anti_drift_non_goal_violation_count",
    ):
        if _int(payload.get(key)) != 0:
            errors.append(f"anti-drift: {key} must be zero")
    if payload.get("violations"):
        errors.append("anti-drift: violations must be empty")


def _validate_static_inventory(payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("status") != "pass":
        errors.append("static inventory: status must be pass")
    if payload.get("producer_map_only") is not True:
        errors.append("static inventory: must remain a producer map")
    if payload.get("counts_toward_runtime_closeout") is not False:
        errors.append("static inventory: cannot count toward runtime closeout")
    if payload.get("counts_toward_final_publication") is not False:
        errors.append("static inventory: cannot count toward final publication")
    if not payload.get("readiness_aggregator_contract"):
        errors.append("static inventory: missing readiness aggregator contract")
    counts = _mapping(payload.get("blocking_status_counts"))
    for status in build.BLOCKING_INVENTORY_STATUSES:
        if _int(counts.get(status)) != 0:
            errors.append(f"static inventory: blocking status {status} must be zero")


def _validate_sdd_mapping(payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("status") != "pass":
        errors.append("SDD record-family mapping: status must be pass")
    coverage = _mapping(payload.get("runtime_record_family_coverage"))
    if coverage.get("status") != "pass":
        errors.append("SDD record-family mapping: runtime record-family coverage must pass")
    if _int(coverage.get("runtime_record_count")) <= 0:
        errors.append("SDD record-family mapping: runtime record-family coverage is empty")
    rows = _mapping_rows(payload, "rows")
    if not rows:
        errors.append("SDD record-family mapping: rows must not be empty")
    for row in rows:
        family_id = str(row.get("family_id") or "<unknown>")
        if row.get("status") != "pass":
            errors.append(f"SDD {family_id}: row must pass")
        if row.get("errors"):
            errors.append(f"SDD {family_id}: row has errors")
        for field in build.SDD_REQUIRED_FIELDS:
            if not str(row.get(field) or "").strip():
                errors.append(f"SDD {family_id}: missing {field}")
        if row.get("evidence_mapping") not in {
            "runtime_evidence",
            "typed_out_of_scope_authority_policy",
        }:
            errors.append(f"SDD {family_id}: evidence_mapping is invalid")
        if row.get("evidence_mapping") == "runtime_evidence" and _int(
            row.get("runtime_record_count")
        ) <= 0:
            errors.append(f"SDD {family_id}: missing runtime record-family coverage")


def _validate_pass1b(payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("status") != "pass":
        errors.append("Pass 1B closeout: status must be pass")
    rows = _mapping_rows(payload, "pdd_rows")
    if not rows:
        errors.append("Pass 1B closeout: pdd_rows must not be empty")
    for row in rows:
        label = f"Pass 1B {row.get('group_id')}:{row.get('pdd_id')}"
        if row.get("status") != "pass":
            errors.append(f"{label}: row must pass")
        if row.get("errors"):
            errors.append(f"{label}: row has errors")
        for field in build.PASS1B_REQUIRED_FIELDS:
            if not str(row.get(field) or "").strip():
                errors.append(f"{label}: missing {field}")
        if row.get("coverage_kind") != "concrete_evidence_contract":
            errors.append(f"{label}: coverage_kind must be concrete_evidence_contract")
        if row.get("authority_boundary") != "record_is_evidence_only":
            errors.append(f"{label}: authority_boundary must be record_is_evidence_only")


def _validate_exit_fence(
    *,
    closeout: Mapping[str, Any],
    exit_fence: Mapping[str, Any],
    errors: list[str],
) -> None:
    expected_status = (
        "pass"
        if all(row.get("status") == "pass" for row in _mapping_rows(closeout, "entry_criteria"))
        and _mapping(closeout.get("readiness_aggregator")).get("status") == "pass"
        and _mapping(closeout.get("bundle_inspection")).get("status") == "pass"
        and _mapping(closeout.get("coverage")).get("status") == "pass"
        and _mapping(closeout.get("anti_drift")).get("status") == "pass"
        and _mapping(closeout.get("static_inventory")).get("producer_map_only") is True
        and _mapping(closeout.get("static_inventory")).get("counts_toward_runtime_closeout")
        is False
        and _mapping(closeout.get("sdd_record_family_mapping")).get("status") == "pass"
        and _mapping(closeout.get("pass1b_closeout")).get("status") == "pass"
        else "fail"
    )
    if closeout.get("status") != expected_status:
        errors.append("closeout: status does not match Wave 40 inputs")
    if exit_fence.get("status") != expected_status:
        errors.append("exit_fence: status does not match Wave 40 inputs")
    if exit_fence.get("readiness_serious_failure_count") != _mapping(
        closeout.get("readiness_aggregator")
    ).get("minimum_closeout_gate_failure_count"):
        errors.append("exit_fence: readiness_serious_failure_count drifted")
    if exit_fence.get("policy_design_case_coverage_targets_met") is not (
        _mapping(closeout.get("coverage")).get("status") == "pass"
    ):
        errors.append("exit_fence: coverage target decision drifted")
    if exit_fence.get("anti_drift_non_goal_violations") != _mapping(
        closeout.get("anti_drift")
    ).get("anti_drift_non_goal_violation_count"):
        errors.append("exit_fence: anti-drift non-goal count drifted")
    if exit_fence.get("static_inventory_is_producer_map_only") is not (
        _mapping(closeout.get("static_inventory")).get("producer_map_only") is True
        and _mapping(closeout.get("static_inventory")).get("counts_toward_runtime_closeout")
        is False
    ):
        errors.append("exit_fence: static inventory authority decision drifted")
    if expected_status == "pass" and exit_fence.get("final_publication_decision") != "allowed":
        errors.append("exit_fence: final publication decision must be allowed when pass")
    if expected_status != "pass" and exit_fence.get("final_publication_decision") != "blocked":
        errors.append("exit_fence: final publication decision must be blocked when fail")


def _load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing artifact: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{path}: JSON artifact must contain an object")
        return {}
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave40-dir", type=Path, default=build.WAVE40_DIR)
    args = parser.parse_args(argv)

    try:
        errors = validate_wave40_readiness(
            repo_root=args.repo_root,
            wave40_dir=args.wave40_dir,
        )
    except (OSError, ValueError) as exc:
        errors = [str(exc)]

    if errors:
        for error in errors:
            sys.stderr.write(f"wave40-readiness: {error}\n")
        sys.stderr.write(f"wave40-readiness: failed with {len(errors)} issue(s)\n")
        return 1
    sys.stdout.write("wave40-readiness: pass\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
