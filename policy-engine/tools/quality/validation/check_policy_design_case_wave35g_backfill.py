#!/usr/bin/env python3
"""Validate Policy Design Case Wave 35G backfill release-fence artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation import build_policy_design_case_wave35g_backfill as build

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

REQUIRED_ARTIFACTS = {
    "projection": build.PROJECTION_OUTPUT,
    "memory": build.memory_authority.OUTPUT_NAME,
    "trust": build.TRUST_OUTPUT,
    "institutional": build.institutional.OUTPUT_FILENAME,
    "phase34_rerun": build.PHASE34_RERUN_OUTPUT,
    "integrity_report": build.INTEGRITY_REPORT_OUTPUT,
    "exit_fence": build.EXIT_FENCE_OUTPUT,
}


def validate_wave35g_backfill(
    *,
    repo_root: Path = REPO_ROOT,
    wave35f_dir: Path = build.WAVE35F_DIR,
    wave35g_dir: Path = build.WAVE35G_DIR,
    require_wave35f_release_allowed: bool = True,
) -> list[str]:
    repo_root = repo_root.resolve()
    wave35f_path = _resolve(repo_root, wave35f_dir)
    wave35g_path = _resolve(repo_root, wave35g_dir)
    errors: list[str] = []
    payloads = _load_required_payloads(wave35g_path, errors)
    if errors:
        return errors

    gap_ledger = _load_json(
        wave35f_path / "runtime_enforcement_gap_ledger.json",
        errors,
    )
    wave35f_exit = _load_json(wave35f_path / "wave35f_exit_fence.json", errors)
    if errors:
        return errors

    projection = payloads["projection"]
    memory = payloads["memory"]
    trust = payloads["trust"]
    institutional_payload = payloads["institutional"]
    phase34_rerun = payloads["phase34_rerun"]
    integrity_report = payloads["integrity_report"]
    exit_fence = payloads["exit_fence"]

    _validate_projection(projection, errors)
    _validate_memory(memory, errors)
    _validate_trust(trust, repo_root, errors)
    _validate_institutional(institutional_payload, errors)
    _validate_phase34_rerun(phase34_rerun, errors)

    closure = build.build_blocker_closure(
        repo_root=repo_root,
        wave35f_gap_ledger=gap_ledger,
        projection=projection,
        memory=memory,
        trust=trust,
        institutional_payload=institutional_payload,
    )
    _validate_closure(closure, errors)
    _validate_integrity_report(
        repo_root=repo_root,
        wave35g_path=wave35g_path,
        trust=trust,
        closure=closure,
        integrity_report=integrity_report,
        errors=errors,
    )
    _validate_exit_fence(
        closure=closure,
        phase34_rerun=phase34_rerun,
        wave35f_exit=wave35f_exit,
        exit_fence=exit_fence,
        require_wave35f_release_allowed=require_wave35f_release_allowed,
        errors=errors,
    )
    if require_wave35f_release_allowed:
        _validate_wave35f_release_allowed(wave35f_exit, errors)
    return errors


def _load_required_payloads(
    wave35g_path: Path,
    errors: list[str],
) -> dict[str, Mapping[str, Any]]:
    payloads: dict[str, Mapping[str, Any]] = {}
    for key, filename in REQUIRED_ARTIFACTS.items():
        payload = _load_json(wave35g_path / filename, errors)
        if payload:
            payloads[key] = payload
    return payloads


def _validate_projection(payload: Mapping[str, Any], errors: list[str]) -> None:
    _validate_common(
        payload,
        schema_version=build.PROJECTION_SCHEMA_VERSION,
        phase="35G.1",
        label="projection",
        errors=errors,
    )
    if set(_as_string_list(payload.get("affected_findings"))) != set(build.PROJECTION_FINDINGS):
        errors.append("projection: affected_findings must cover PDD-034/PDD-069 blockers")
    rows = _mapping_rows(payload, "evidence_rows")
    if {str(row.get("masking_case")) for row in rows} != set(build.PROJECTION_MASKING_CASES):
        errors.append("projection: missing required masking-case runtime rows")
    if not build._projection_artifact_closes(payload):
        errors.append("projection: runtime/API/UI fail-closed evidence is incomplete")


def _validate_memory(payload: Mapping[str, Any], errors: list[str]) -> None:
    _validate_common(
        payload,
        schema_version=build.memory_authority.SCHEMA_VERSION,
        phase="35G.2",
        label="memory",
        errors=errors,
    )
    if set(_as_string_list(payload.get("affected_wave35f_blockers"))) != set(build.MEMORY_FINDINGS):
        errors.append("memory: affected_wave35f_blockers must cover PDD-083 blockers")
    observed = {str(row.get("finding_id")) for row in _mapping_rows(payload, "evidence_rows")}
    missing = set(build.MEMORY_FINDINGS) - observed
    for finding_id in sorted(missing):
        errors.append(f"{finding_id} lacks runtime/test evidence or non-closeout boundary")
    for row in _mapping_rows(payload, "evidence_rows"):
        if not build._runtime_or_test_evidence_row_closes(row):
            errors.append(
                f"{row.get('finding_id')}: memory evidence row is not runtime/test-closeable"
            )


def _validate_trust(
    payload: Mapping[str, Any],
    repo_root: Path,
    errors: list[str],
) -> None:
    _validate_common(
        payload,
        schema_version=build.TRUST_SCHEMA_VERSION,
        phase="35G.3",
        label="trust",
        errors=errors,
    )
    if set(_as_string_list(payload.get("affected_findings"))) != set(build.TRUST_FINDINGS):
        errors.append("trust: affected_findings must cover PDD-103 blockers")
    rows = _mapping_rows(payload, "scenario_rows")
    if {str(row.get("scenario")) for row in rows} != set(build.TRUST_SCENARIOS):
        errors.append("trust: missing required UI negative scenarios")
    if not build._trust_artifact_closes(payload):
        errors.append("trust: UI negative trace evidence is incomplete")
    for row in rows:
        scenario = str(row.get("scenario") or "<missing>")
        media_refs = build._generated_trust_trace_or_screenshot_refs([row])
        if not media_refs:
            errors.append(f"trust: missing generated UI trace or screenshot for {scenario}")
            continue
        screenshot_sha256 = row.get("screenshot_sha256")
        for ref in media_refs:
            path = _resolve(repo_root, Path(ref))
            if not path.exists() or not path.is_file():
                errors.append(
                    f"trust: generated UI trace or screenshot missing for {scenario}: {ref}"
                )
                continue
            if Path(ref).suffix == ".png":
                expected = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                if screenshot_sha256 != expected:
                    errors.append(f"trust: screenshot hash drifted for {scenario}: {ref}")


def _validate_institutional(
    payload: Mapping[str, Any],
    errors: list[str],
) -> None:
    _validate_common(
        payload,
        schema_version=build.institutional.SCHEMA_VERSION,
        phase="35G.4",
        label="institutional",
        errors=errors,
    )
    errors.extend(build.institutional.validate_institutional_provenance_boundary_ledger(payload))
    rows_by_finding = {str(row.get("finding_id")): row for row in _mapping_rows(payload, "rows")}
    for finding_id in build.INSTITUTIONAL_FINDINGS:
        row = rows_by_finding.get(finding_id, {})
        if not (
            build._institutional_row_has_runtime_authority(row)
            or build._institutional_boundary_closes(row)
        ):
            errors.append(f"{finding_id} lacks runtime/test evidence or non-closeout boundary")


def _validate_phase34_rerun(
    payload: Mapping[str, Any],
    errors: list[str],
) -> None:
    _validate_common(
        payload,
        schema_version=build.PHASE34_RERUN_SCHEMA_VERSION,
        phase="35G.5",
        label="phase34_rerun",
        errors=errors,
    )
    if payload.get("command") != build.PHASE34_6_COMMAND:
        errors.append("phase34_rerun: command drifted")
    if payload.get("exit_code") != 0:
        errors.append("phase34_rerun: exit_code must be 0")
    if payload.get("status") != "pass":
        errors.append("phase34_rerun: status must be pass")
    if not _as_list(payload.get("output_hashes")):
        errors.append("phase34_rerun: missing output_hashes")


def _validate_closure(closure: Mapping[str, Any], errors: list[str]) -> None:
    rows = _mapping_rows(closure, "blocker_closure_rows")
    observed = {str(row.get("finding_id")) for row in rows}
    expected = set(build.RELEASE_BLOCKER_IDS)
    if observed != expected:
        errors.append(
            "closure rows must cover exactly the 19 Wave 35F release blockers: "
            f"missing={sorted(expected - observed)} extra={sorted(observed - expected)}"
        )
    for row in rows:
        if row.get("closure_decision") == "remaining_blocker":
            errors.append(
                f"{row.get('finding_id')} lacks runtime/test evidence or non-closeout boundary"
            )
    counts = _mapping(closure.get("blocker_closure_counts"))
    if counts.get("required_release_blocker_count") != len(build.RELEASE_BLOCKER_IDS):
        errors.append("closure count must report 19 required release blockers")
    if counts.get("remaining_release_blocker_count") != len(
        _as_list(closure.get("remaining_blocker_rows"))
    ):
        errors.append("closure remaining count drifted")


def _validate_integrity_report(
    *,
    repo_root: Path,
    wave35g_path: Path,
    trust: Mapping[str, Any],
    closure: Mapping[str, Any],
    integrity_report: Mapping[str, Any],
    errors: list[str],
) -> None:
    _validate_common(
        integrity_report,
        schema_version=build.SCHEMA_VERSION,
        phase="35G.5",
        label="integrity_report",
        errors=errors,
    )
    if integrity_report.get("command") != build.BACKFILL_CHECK_COMMAND:
        errors.append("integrity_report: command drifted")
    if integrity_report.get("exit_code") != 0:
        errors.append("integrity_report: exit_code must be 0")
    if integrity_report.get("status") != "pass":
        errors.append("integrity_report: status must be pass")
    if integrity_report.get("blocker_closure_counts") != closure.get("blocker_closure_counts"):
        errors.append("integrity_report: blocker closure counts drifted")
    if _as_list(integrity_report.get("remaining_blocker_rows")):
        errors.append("integrity_report: remaining_blocker_rows must be empty")
    _validate_hashes(
        repo_root,
        wave35g_path,
        integrity_report,
        errors,
        required_rel_paths=build._generated_trust_trace_or_screenshot_refs(
            _mapping_rows(trust, "scenario_rows")
        ),
    )


def _validate_exit_fence(
    *,
    closure: Mapping[str, Any],
    phase34_rerun: Mapping[str, Any],
    wave35f_exit: Mapping[str, Any],
    exit_fence: Mapping[str, Any],
    require_wave35f_release_allowed: bool,
    errors: list[str],
) -> None:
    _validate_common(
        exit_fence,
        schema_version=build.SCHEMA_VERSION,
        phase="35G.5",
        label="exit_fence",
        errors=errors,
    )
    remaining = _as_list(closure.get("remaining_blocker_rows"))
    phase34_pass = phase34_rerun.get("status") == "pass" and phase34_rerun.get("exit_code") == 0
    wave35f_allowed = (
        wave35f_exit.get("status") == "pass"
        and wave35f_exit.get("wave36_release_decision") == "allowed"
    )
    should_allow = (
        not remaining and phase34_pass and (wave35f_allowed or not require_wave35f_release_allowed)
    )
    expected_decision = "allowed" if should_allow else "blocked"
    if exit_fence.get("wave36_release_decision") != expected_decision:
        errors.append("exit_fence: Wave 36 release decision drifted")
    if exit_fence.get("status") != ("pass" if should_allow else "fail"):
        errors.append("exit_fence: status does not match release decision")
    if set(_as_string_list(exit_fence.get("covered_release_blocker_ids"))) != set(
        build.RELEASE_BLOCKER_IDS
    ):
        errors.append("exit_fence: covered_release_blocker_ids must list all 19 blockers")


def _validate_wave35f_release_allowed(
    wave35f_exit: Mapping[str, Any],
    errors: list[str],
) -> None:
    if wave35f_exit.get("status") != "pass":
        errors.append("wave35f_exit_fence: status must be pass")
    if wave35f_exit.get("wave36_release_decision") != "allowed":
        errors.append("wave35f_exit_fence: wave36_release_decision must be allowed")


def _validate_common(
    payload: Mapping[str, Any],
    *,
    schema_version: str,
    phase: str,
    label: str,
    errors: list[str],
) -> None:
    if payload.get("schema_version") != schema_version:
        errors.append(f"{label}: schema_version drifted")
    if payload.get("wave") != "35G":
        errors.append(f"{label}: wave must be 35G")
    if payload.get("phase") != phase:
        errors.append(f"{label}: phase must be {phase}")
    if not payload.get("tool"):
        errors.append(f"{label}: missing tool")
    if not payload.get("generated_at"):
        errors.append(f"{label}: missing generated_at")


def _validate_hashes(
    repo_root: Path,
    wave35g_path: Path,
    integrity_report: Mapping[str, Any],
    errors: list[str],
    *,
    required_rel_paths: Sequence[str] = (),
) -> None:
    rows = _as_list(integrity_report.get("output_hashes"))
    if not rows:
        errors.append("integrity_report: missing output_hashes")
        return
    required_paths = {
        build.PROJECTION_OUTPUT,
        build.memory_authority.OUTPUT_NAME,
        build.TRUST_OUTPUT,
        build.institutional.OUTPUT_FILENAME,
        build.PHASE34_RERUN_OUTPUT,
        build.EXIT_FENCE_OUTPUT,
    }
    observed_names = {
        Path(str(row.get("path") or "")).name for row in rows if isinstance(row, Mapping)
    }
    observed_paths = {str(row.get("path") or "") for row in rows if isinstance(row, Mapping)}
    if not required_paths <= observed_names:
        errors.append(
            "integrity_report: output_hashes missing required artifacts: "
            f"{sorted(required_paths - observed_names)}"
        )
    missing_required_rel_paths = set(required_rel_paths) - observed_paths
    if missing_required_rel_paths:
        errors.append(
            "integrity_report: output_hashes missing generated trust traces: "
            f"{sorted(missing_required_rel_paths)}"
        )
    for row in rows:
        if not isinstance(row, Mapping):
            errors.append("integrity_report: output_hash row must be an object")
            continue
        rel_path = str(row.get("path") or "")
        if not rel_path:
            errors.append("integrity_report: output_hash row missing path")
            continue
        path = _resolve(repo_root, Path(rel_path))
        if not path.exists() and Path(rel_path).name in required_paths:
            path = wave35g_path / Path(rel_path).name
        if not path.exists():
            errors.append(f"integrity_report: hashed artifact missing: {rel_path}")
            continue
        expected = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if row.get("sha256") != expected:
            errors.append(f"integrity_report: hash drifted for {rel_path}")


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


def _as_string_list(value: object) -> list[str]:
    return [str(item) for item in _as_list(value) if item]


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (repo_root / path).resolve(strict=False)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave35f-dir", type=Path, default=build.WAVE35F_DIR)
    parser.add_argument("--wave35g-dir", type=Path, default=build.WAVE35G_DIR)
    parser.add_argument(
        "--skip-wave35f-release-check",
        action="store_true",
        help="Validate Wave 35G artifacts without requiring refreshed Wave 35F release.",
    )
    args = parser.parse_args(argv)

    try:
        errors = validate_wave35g_backfill(
            repo_root=args.repo_root,
            wave35f_dir=args.wave35f_dir,
            wave35g_dir=args.wave35g_dir,
            require_wave35f_release_allowed=not args.skip_wave35f_release_check,
        )
    except (OSError, ValueError) as exc:
        errors = [str(exc)]

    if errors:
        for error in errors:
            sys.stderr.write(f"wave35g-backfill: {error}\n")
        sys.stderr.write(f"wave35g-backfill: failed with {len(errors)} issue(s)\n")
        return 1
    sys.stdout.write("wave35g-backfill: pass\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
