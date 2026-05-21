#!/usr/bin/env python3
"""Validate Policy Design Case Wave 35F remediation integrity artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation import build_policy_design_case_wave35f_integrity as build

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

REQUIRED_ARTIFACTS = {
    "classification": "remediation_integrity_classification.json",
    "gap_ledger": "runtime_enforcement_gap_ledger.json",
    "human_surface_audit": "wave35e_human_surface_enforcement_audit.json",
    "authority_map": "wave35_runtime_evidence_authority_map.json",
    "integrity_report": "wave35f_disposition_integrity_report.json",
    "exit_fence": "wave35f_exit_fence.json",
}


def validate_wave35f_integrity(
    *,
    repo_root: Path = REPO_ROOT,
    wave35_dir: Path = build.WAVE35_DIR,
    wave35f_dir: Path = build.WAVE35F_DIR,
    wave35g_dir: Path = build.WAVE35G_DIR,
) -> list[str]:
    repo_root = repo_root.resolve()
    wave35_path = _resolve(repo_root, wave35_dir)
    wave35f_path = _resolve(repo_root, wave35f_dir)
    errors: list[str] = []

    payloads = _load_required_payloads(wave35f_path, errors)
    if errors:
        return errors

    disposition = _load_json(wave35_path / "pass2_disposition.json", errors)
    if not disposition:
        return errors

    classification = payloads["classification"]
    gap_ledger = payloads["gap_ledger"]
    human_surface_audit = payloads["human_surface_audit"]
    authority_map = payloads["authority_map"]
    integrity_report = payloads["integrity_report"]
    exit_fence = payloads["exit_fence"]
    wave35g_backfill = build._load_wave35g_backfill_coverage(
        repo_root=repo_root,
        wave35g_dir=wave35g_dir,
    )

    _validate_common_payloads(payloads, errors)
    _validate_authority_map(authority_map, repo_root, errors)
    _validate_classification(classification, disposition, errors)
    _validate_gap_ledger(classification, gap_ledger, wave35g_backfill, errors)
    _validate_human_surface_audit(human_surface_audit, errors)
    _validate_exit_fence(gap_ledger, exit_fence, errors)
    _validate_integrity_report(classification, gap_ledger, integrity_report, errors)
    return errors


def _load_required_payloads(
    wave35f_path: Path,
    errors: list[str],
) -> dict[str, Mapping[str, Any]]:
    payloads: dict[str, Mapping[str, Any]] = {}
    for key, filename in REQUIRED_ARTIFACTS.items():
        path = wave35f_path / filename
        payload = _load_json(path, errors)
        if payload:
            payloads[key] = payload
    return payloads


def _validate_common_payloads(
    payloads: Mapping[str, Mapping[str, Any]],
    errors: list[str],
) -> None:
    for key, payload in payloads.items():
        if payload.get("schema_version") != build.SCHEMA_VERSION:
            errors.append(f"{key}: schema_version drifted")
        if payload.get("wave") != "35F":
            errors.append(f"{key}: wave must be 35F")
        if payload.get("phase") != "35F.1":
            errors.append(f"{key}: phase must be 35F.1")
        if not payload.get("tool"):
            errors.append(f"{key}: missing tool")
        if not payload.get("generated_at"):
            errors.append(f"{key}: missing generated_at")


def _validate_authority_map(
    authority_map: Mapping[str, Any],
    repo_root: Path,
    errors: list[str],
) -> None:
    rows = _mapping_rows(authority_map, "artifacts")
    expected_paths = _actual_wave35_artifacts(repo_root)
    observed_paths = {str(row.get("artifact_path")) for row in rows}
    if observed_paths != expected_paths:
        errors.append(
            "authority map must cover every Wave 35A-35E artifact: "
            f"missing={sorted(expected_paths - observed_paths)} "
            f"extra={sorted(observed_paths - expected_paths)}"
        )

    allowed = set(build.ALLOWED_AUTHORITY_CLASSES)
    for row in rows:
        artifact_path = str(row.get("artifact_path") or "<unknown>")
        authority_class = str(row.get("evidence_authority_class") or "")
        if authority_class not in allowed:
            errors.append(
                f"{artifact_path}: unknown evidence authority class {authority_class!r}"
            )
        if authority_class in build.OVERLAY_AUTHORITY_CLASSES:
            if row.get("runtime_fact_produced") is True:
                errors.append(f"{artifact_path}: overlay cannot produce runtime facts")
            if row.get("remediation_overlay_only") is not True:
                errors.append(f"{artifact_path}: overlay must be marked overlay-only")
        if (
            authority_class in build.RUNTIME_OR_TEST_AUTHORITY_CLASSES
            and row.get("runtime_fact_produced") is not True
        ):
            errors.append(f"{artifact_path}: runtime/test class must produce facts")


def _validate_classification(
    classification: Mapping[str, Any],
    disposition: Mapping[str, Any],
    errors: list[str],
) -> None:
    rows = _mapping_rows(classification, "rows")
    if not rows:
        errors.append("classification: rows must not be empty")
        return

    coverage = build.expected_wave35f_coverage(disposition)
    observed_finding_ids = {
        str(row.get("finding_id"))
        for row in rows
        if row.get("row_type") == "finding_remediation"
    }
    expected_finding_ids = set(coverage["remediated_finding_ids"])
    if observed_finding_ids != expected_finding_ids:
        errors.append(
            "classification must cover every remediated finding exactly once or more: "
            f"missing={sorted(expected_finding_ids - observed_finding_ids)} "
            f"extra={sorted(observed_finding_ids - expected_finding_ids)}"
        )

    observed_artifacts = {str(row.get("artifact_path")) for row in rows}
    expected_artifacts = set(coverage["disposition_artifact_paths"])
    if not expected_artifacts <= observed_artifacts:
        errors.append(
            "classification missing disposition implementation artifacts: "
            f"{sorted(expected_artifacts - observed_artifacts)}"
        )

    allowed = set(build.ALLOWED_AUTHORITY_CLASSES)
    required_fields = (
        "row_id",
        "wave",
        "cluster_id",
        "pdd_id",
        "finding_id",
        "artifact_path",
        "evidence_authority_class",
        "source_refs",
        "reviewer_command",
        "counts_toward_deterministic_closeout",
    )
    for row in rows:
        row_id = str(row.get("row_id") or "<unknown>")
        for field in required_fields:
            if field not in row or row.get(field) in (None, "", []):
                errors.append(f"{row_id}: classification row missing {field}")
        authority_class = str(row.get("evidence_authority_class") or "")
        if authority_class not in allowed:
            errors.append(f"{row_id}: unknown evidence authority class {authority_class!r}")
        if (
            authority_class in build.OVERLAY_AUTHORITY_CLASSES
            and row.get("counts_toward_deterministic_closeout") is True
        ):
            errors.append(f"{row_id}: overlay/manual row cannot count toward closeout")


def _validate_gap_ledger(
    classification: Mapping[str, Any],
    gap_ledger: Mapping[str, Any],
    wave35g_backfill: Mapping[str, Any],
    errors: list[str],
) -> None:
    classified_rows = _mapping_rows(classification, "rows")
    gap_rows = _mapping_rows(gap_ledger, "rows")
    gap_by_classification = {
        str(row.get("classification_row_id")): row for row in gap_rows
    }
    expected_gap_row_ids = {
        str(row.get("row_id"))
        for row in classified_rows
        if row.get("closeout_critical")
        and row.get("evidence_authority_class") in build.OVERLAY_AUTHORITY_CLASSES
    }
    observed_gap_row_ids = set(gap_by_classification)
    missing_gaps = sorted(expected_gap_row_ids - observed_gap_row_ids)
    if missing_gaps:
        errors.append(f"gap ledger missing closeout-critical overlay rows: {missing_gaps}")

    required_fields = (
        "gap_id",
        "classification_row_id",
        "artifact_path",
        "missing_runtime_api_ui_enforcement",
        "affected_code_or_artifact_path",
        "owner",
        "required_test_or_trace",
        "accepted_boundary",
        "wave36_blocking_decision",
    )
    allowed_decisions = {
        "block_wave36_release",
        "exclude_from_wave36_closeout_evidence",
    }
    for row in gap_rows:
        gap_id = str(row.get("gap_id") or "<unknown>")
        for field in required_fields:
            if field not in row or row.get(field) in (None, "", []):
                errors.append(f"{gap_id}: gap row missing {field}")
        if row.get("classification_row_id") not in expected_gap_row_ids:
            errors.append(f"{gap_id}: gap row does not correspond to an overlay row")
        boundary = row.get("accepted_boundary")
        if not isinstance(boundary, Mapping):
            errors.append(f"{gap_id}: missing accepted boundary")
        elif boundary.get("blocks_wave36_closeout_authority") is not True:
            errors.append(
                f"{gap_id}: accepted boundary must block Wave 36 closeout authority"
            )
        if (
            row.get("wave36_blocking_decision") == "exclude_from_wave36_closeout_evidence"
            and row.get("finding_id")
            in build._mapping(wave35g_backfill.get("non_closeout_boundary_by_finding"))
            and build._mapping(boundary).get("blocks_wave36_release") is not False
        ):
            errors.append(
                f"{gap_id}: Wave 35G non-closeout boundary must stop blocking release"
            )
        if row.get("wave36_blocking_decision") not in allowed_decisions:
            errors.append(f"{gap_id}: unknown Wave 36 blocking decision")


def _validate_human_surface_audit(
    human_surface_audit: Mapping[str, Any],
    errors: list[str],
) -> None:
    rows = _mapping_rows(human_surface_audit, "rows")
    observed_surfaces = {str(row.get("claim_surface")) for row in rows}
    required_surfaces = set(build.HUMAN_SURFACE_BY_ARTIFACT.values())
    if not required_surfaces <= observed_surfaces:
        errors.append(
            "human surface audit missing required surfaces: "
            f"{sorted(required_surfaces - observed_surfaces)}"
        )
    for row in rows:
        row_id = f"{row.get('claim_surface')}:{row.get('claim_id')}"
        authority_class = str(row.get("evidence_authority_class") or "")
        if authority_class not in build.ALLOWED_AUTHORITY_CLASSES:
            errors.append(f"{row_id}: unknown evidence authority class {authority_class!r}")
        if authority_class not in {"runtime_emitted", "test_observed"}:
            if row.get("closeout_authority_decision") != "not_closeout_authority":
                errors.append(f"{row_id}: human-facing overlay must be excluded")
            if not row.get("caveat"):
                errors.append(f"{row_id}: not_closeout_authority row missing caveat")
        if (
            authority_class in {"runtime_emitted", "test_observed"}
            and row.get("runtime_or_test_observed") is not True
        ):
            errors.append(f"{row_id}: runtime/test human row must be observed")


def _validate_exit_fence(
    gap_ledger: Mapping[str, Any],
    exit_fence: Mapping[str, Any],
    errors: list[str],
) -> None:
    blocking_gap_ids = sorted(
        str(row.get("gap_id"))
        for row in _mapping_rows(gap_ledger, "rows")
        if row.get("wave36_blocking_decision") == "block_wave36_release"
    )
    decision = exit_fence.get("wave36_release_decision")
    if blocking_gap_ids and decision != "blocked":
        errors.append("exit fence must block Wave 36 when blocking gaps remain")
    if not blocking_gap_ids and decision != "allowed":
        errors.append("exit fence must allow Wave 36 when no blocking gaps remain")
    if sorted(_as_string_list(exit_fence.get("wave36_blocking_gap_ids"))) != blocking_gap_ids:
        errors.append("exit fence blocking gap ids do not match gap ledger")
    if exit_fence.get("status") != "pass":
        errors.append("exit fence status must be pass once the integrity gate is valid")


def _validate_integrity_report(
    classification: Mapping[str, Any],
    gap_ledger: Mapping[str, Any],
    integrity_report: Mapping[str, Any],
    errors: list[str],
) -> None:
    if integrity_report.get("command") != build.INTEGRITY_CHECK_COMMAND:
        errors.append("integrity report command does not match reviewer command")
    if integrity_report.get("exit_code") != 0:
        errors.append("integrity report exit_code must be 0")
    if not _as_list(integrity_report.get("output_hashes")):
        errors.append("integrity report missing output_hashes")

    observed_counts = Counter(
        str(row.get("evidence_authority_class"))
        for row in _mapping_rows(classification, "rows")
    )
    report_counts = {
        str(key): int(value)
        for key, value in _mapping(
            integrity_report.get("artifact_classification_counts")
        ).items()
    }
    if dict(sorted(observed_counts.items())) != dict(sorted(report_counts.items())):
        errors.append("integrity report classification counts drifted")

    blocking_count = sum(
        1
        for row in _mapping_rows(gap_ledger, "rows")
        if row.get("wave36_blocking_decision") == "block_wave36_release"
    )
    if integrity_report.get("unresolved_closeout_critical_overlay_count") != blocking_count:
        errors.append("integrity report unresolved overlay count drifted")


def _actual_wave35_artifacts(repo_root: Path) -> set[str]:
    paths: set[str] = set()
    for directory in build.WAVE35_REMEDIATION_DIRS.values():
        directory_path = _resolve(repo_root, directory)
        paths.update(
            path.relative_to(repo_root).as_posix()
            for path in directory_path.glob("*.json")
        )
    return paths


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


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (repo_root / path).resolve(strict=False)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_string_list(value: object) -> list[str]:
    return [str(item) for item in _as_list(value)]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave35-dir", type=Path, default=build.WAVE35_DIR)
    parser.add_argument("--wave35f-dir", type=Path, default=build.WAVE35F_DIR)
    parser.add_argument("--wave35g-dir", type=Path, default=build.WAVE35G_DIR)
    args = parser.parse_args(argv)

    try:
        errors = validate_wave35f_integrity(
            repo_root=args.repo_root,
            wave35_dir=args.wave35_dir,
            wave35f_dir=args.wave35f_dir,
            wave35g_dir=args.wave35g_dir,
        )
    except (OSError, ValueError) as exc:
        errors = [str(exc)]

    if errors:
        for error in errors:
            sys.stderr.write(f"wave35f-integrity: {error}\n")
        sys.stderr.write(f"wave35f-integrity: failed with {len(errors)} issue(s)\n")
        return 1
    sys.stdout.write("wave35f-integrity: pass\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
