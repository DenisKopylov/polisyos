#!/usr/bin/env python3
"""Validate Policy Design Case Wave 35H runtime-owned institutional provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation import build_policy_design_case_wave35g_institutional_provenance
from tools.quality.validation import build_policy_design_case_wave35h_provenance as build

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality import institutional_provenance as runtime_provenance  # noqa: E402

REQUIRED_ARTIFACTS = {
    "implementation": build.IMPLEMENTATION_OUTPUT,
    "contestability": build.CONTESTABILITY_OUTPUT,
    "ownership": build.OWNERSHIP_OUTPUT,
    "integrity_report": build.INTEGRITY_REPORT_OUTPUT,
    "exit_fence": build.EXIT_FENCE_OUTPUT,
}
INSTITUTIONAL_LEDGER_FILES = {
    build.IMPLEMENTATION_LEDGER,
    build.CONTESTABILITY_LEDGER,
}


def validate_wave35h_provenance(
    *,
    repo_root: Path = REPO_ROOT,
    wave35e_dir: Path = build.WAVE35E_DIR,
    wave35f_dir: Path = build.WAVE35F_DIR,
    wave35g_dir: Path = build.WAVE35G_DIR,
    wave35h_dir: Path = build.WAVE35H_DIR,
) -> list[str]:
    repo_root = repo_root.resolve()
    wave35e_path = _resolve(repo_root, wave35e_dir)
    wave35f_path = _resolve(repo_root, wave35f_dir)
    wave35g_path = _resolve(repo_root, wave35g_dir)
    wave35h_path = _resolve(repo_root, wave35h_dir)
    errors: list[str] = []

    payloads = _load_required_payloads(wave35h_path, errors)
    if errors:
        return errors

    implementation = payloads["implementation"]
    contestability = payloads["contestability"]
    ownership = payloads["ownership"]
    integrity_report = payloads["integrity_report"]
    exit_fence = payloads["exit_fence"]

    _validate_runtime_artifact(
        implementation,
        label="implementation",
        schema_version=build.IMPLEMENTATION_SCHEMA_VERSION,
        phase="35H.1",
        affected_findings=set(build.IMPLEMENTATION_FINDINGS),
        surface="implementation_feasibility",
        errors=errors,
    )
    _validate_runtime_artifact(
        contestability,
        label="contestability",
        schema_version=build.CONTESTABILITY_SCHEMA_VERSION,
        phase="35H.2",
        affected_findings=set(build.CONTESTABILITY_FINDINGS),
        surface="contestability_appeals",
        errors=errors,
    )
    _validate_ownership_ledger(ownership, errors)
    _validate_wave35e_ledgers(wave35e_path, errors)
    _validate_wave35g_boundary(wave35g_path, errors)
    _validate_wave35f_classification(wave35f_path, errors)
    _validate_integrity_report(repo_root, integrity_report, errors)
    _validate_exit_fence(exit_fence, errors)
    return errors


def _load_required_payloads(
    wave35h_path: Path,
    errors: list[str],
) -> dict[str, Mapping[str, Any]]:
    payloads: dict[str, Mapping[str, Any]] = {}
    for key, filename in REQUIRED_ARTIFACTS.items():
        payload = _load_json(wave35h_path / filename, errors)
        if payload:
            payloads[key] = payload
    return payloads


def _validate_runtime_artifact(
    payload: Mapping[str, Any],
    *,
    label: str,
    schema_version: str,
    phase: str,
    affected_findings: set[str],
    surface: str,
    errors: list[str],
) -> None:
    _validate_common(
        payload,
        schema_version=schema_version,
        phase=phase,
        label=label,
        errors=errors,
    )
    if payload.get("status") != "complete":
        errors.append(f"{label}: status must be complete")
    if payload.get("evidence_authority") != "runtime_emitted":
        errors.append(f"{label}: evidence_authority must be runtime_emitted")
    if set(_as_string_list(payload.get("affected_findings"))) != affected_findings:
        errors.append(f"{label}: affected findings drifted")
    records = _mapping_rows(payload, "records")
    if not records:
        errors.append(f"{label}: records must not be empty")
    for record in records:
        try:
            runtime_provenance.validate_runtime_owned_provenance(record, surface=surface)
        except runtime_provenance.InstitutionalProvenanceError as exc:
            errors.append(f"{label}:{record.get('record_id')}: {exc.code}: {exc.field}")
    evidence_rows = _mapping_rows(payload, "evidence_rows")
    if {str(row.get("finding_id")) for row in evidence_rows} != affected_findings:
        errors.append(f"{label}: evidence_rows must cover affected findings")
    for row in evidence_rows:
        row_id = str(row.get("row_id") or "<unknown>")
        if row.get("evidence_authority") not in {"runtime_emitted", "runtime_derived"}:
            errors.append(f"{row_id}: evidence authority must be runtime-owned")
        if _mapping(row.get("command")).get("exit_code") != 0:
            errors.append(f"{row_id}: command exit_code must be 0")
        if not _as_string_list(row.get("source_refs")):
            errors.append(f"{row_id}: missing source_refs")
        if not _as_string_list(row.get("trace_refs")):
            errors.append(f"{row_id}: missing trace_refs")


def _validate_ownership_ledger(
    payload: Mapping[str, Any],
    errors: list[str],
) -> None:
    _validate_common(
        payload,
        schema_version=build.SCHEMA_VERSION,
        phase="35H.3",
        label="ownership",
        errors=errors,
    )
    if payload.get("status") != "pass":
        errors.append("ownership: status must be pass")
    summary = _mapping(payload.get("summary"))
    if summary.get("runtime_owned_provenance_count") != 6:
        errors.append("ownership: runtime_owned_provenance_count must be 6")
    if summary.get("not_closeout_authority_count") != 0:
        errors.append("ownership: not_closeout_authority_count must be 0")
    rows = _mapping_rows(payload, "rows")
    if {str(row.get("finding_id")) for row in rows} != set(build.AFFECTED_FINDINGS):
        errors.append("ownership: rows must cover all six Wave 35G findings")
    for row in rows:
        row_id = str(row.get("row_id") or "<unknown>")
        if row.get("runtime_owned_provenance_present") is not True:
            errors.append(f"{row_id}: missing runtime-owned provenance")
        if row.get("evidence_authority") not in {"runtime_emitted", "runtime_derived"}:
            errors.append(f"{row_id}: evidence authority must be runtime-owned")
        if row.get("counts_toward_final_publication") is not True:
            errors.append(f"{row_id}: must count toward final publication after Wave 35H")
        if row.get("counts_toward_deterministic_closeout") is not True:
            errors.append(f"{row_id}: must count toward deterministic closeout after Wave 35H")
        if _mapping(row.get("command")).get("exit_code") != 0:
            errors.append(f"{row_id}: command exit_code must be 0")
        provenance = _mapping(row.get("runtime_owned_provenance"))
        surface = str(row.get("surface") or "")
        try:
            runtime_provenance.validate_runtime_owned_provenance(provenance, surface=surface)
        except runtime_provenance.InstitutionalProvenanceError as exc:
            errors.append(f"{row_id}: {exc.code}: {exc.field}")


def _validate_wave35e_ledgers(wave35e_path: Path, errors: list[str]) -> None:
    implementation = _load_json(wave35e_path / build.IMPLEMENTATION_LEDGER, errors)
    contestability = _load_json(wave35e_path / build.CONTESTABILITY_LEDGER, errors)
    if not implementation or not contestability:
        return
    for label, payload, surface in (
        ("implementation", implementation, "implementation_feasibility"),
        ("contestability", contestability, "contestability_appeals"),
    ):
        runtime_evidence = _mapping(payload.get("runtime_enforcement_evidence"))
        if runtime_evidence.get("evidence_authority_class") != "runtime_emitted":
            errors.append(f"{label}: runtime_enforcement_evidence must be runtime_emitted")
        if runtime_evidence.get("manual_assertion_remaining_count") != 0:
            errors.append(f"{label}: manual assertions must be fully replaced")
        for index, row in enumerate(_mapping_rows(payload, "rows")):
            authority = row.get("evidence_authority_class")
            if authority == "manual_assertion":
                errors.append(f"{label}: row {index} remains manual_assertion")
            provenance = _mapping(row.get("runtime_owned_provenance"))
            if not provenance:
                errors.append(f"{label}: row {index} missing runtime_owned_provenance")
                continue
            try:
                runtime_provenance.validate_runtime_owned_provenance(
                    provenance,
                    surface=surface,
                )
            except runtime_provenance.InstitutionalProvenanceError as exc:
                errors.append(f"{label}: row {index}: {exc.code}: {exc.field}")


def _validate_wave35g_boundary(wave35g_path: Path, errors: list[str]) -> None:
    payload = _load_json(
        wave35g_path / build_policy_design_case_wave35g_institutional_provenance.OUTPUT_FILENAME,
        errors,
    )
    if not payload:
        return
    errors.extend(
        build_policy_design_case_wave35g_institutional_provenance
        .validate_institutional_provenance_boundary_ledger(payload)
    )
    summary = _mapping(payload.get("summary"))
    if summary.get("runtime_owned_provenance_count") != 6:
        errors.append("wave35g: runtime_owned_provenance_count must be 6")
    if summary.get("not_closeout_authority_count") != 0:
        errors.append("wave35g: not_closeout_authority_count must be 0")
    for row in _mapping_rows(payload, "rows"):
        row_id = str(row.get("row_id") or "<unknown>")
        if row.get("enforceable_boundary") not in (None, {}):
            errors.append(f"{row_id}: runtime-owned row must not keep non-closeout boundary")
        if row.get("runtime_owned_provenance_present") is not True:
            errors.append(f"{row_id}: missing runtime-owned provenance")


def _validate_wave35f_classification(wave35f_path: Path, errors: list[str]) -> None:
    payload = _load_json(
        wave35f_path / "remediation_integrity_classification.json",
        errors,
    )
    if not payload:
        return
    for row in _mapping_rows(payload, "rows"):
        finding_id = str(row.get("finding_id") or "")
        if not finding_id.startswith(("PDD-097", "PDD-099")):
            continue
        if Path(str(row.get("artifact_path") or "")).name not in INSTITUTIONAL_LEDGER_FILES:
            continue
        authority = str(row.get("evidence_authority_class") or "")
        if authority not in {"runtime_emitted", "runtime_derived"}:
            errors.append(
                f"{row.get('row_id')}: institutional ledger row must classify as "
                f"runtime-owned, not {authority!r}"
            )


def _validate_integrity_report(
    repo_root: Path,
    payload: Mapping[str, Any],
    errors: list[str],
) -> None:
    _validate_common(
        payload,
        schema_version=build.SCHEMA_VERSION,
        phase="35H.3",
        label="integrity_report",
        errors=errors,
    )
    if payload.get("command") != build.WAVE35H_CHECK_COMMAND:
        errors.append("integrity_report: command drifted")
    if payload.get("exit_code") != 0:
        errors.append("integrity_report: exit_code must be 0")
    if not _as_list(payload.get("before_hashes")) or not _as_list(payload.get("after_hashes")):
        errors.append("integrity_report: missing before/after hashes")
    before_counts = _mapping(payload.get("before_evidence_authority_counts"))
    after_counts = _mapping(payload.get("after_evidence_authority_counts"))
    if not before_counts or not after_counts:
        errors.append("integrity_report: missing before/after authority counts")
    for row in _as_list(payload.get("output_hashes")):
        if not isinstance(row, Mapping):
            errors.append("integrity_report: output hash row must be an object")
            continue
        rel_path = str(row.get("path") or "")
        if not rel_path:
            errors.append("integrity_report: output hash row missing path")
            continue
        path = _resolve(repo_root, Path(rel_path))
        if not path.exists() or not path.is_file():
            errors.append(f"integrity_report: hashed artifact missing: {rel_path}")
            continue
        expected = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if row.get("sha256") != expected:
            errors.append(f"integrity_report: hash drifted for {rel_path}")


def _validate_exit_fence(payload: Mapping[str, Any], errors: list[str]) -> None:
    _validate_common(
        payload,
        schema_version=build.SCHEMA_VERSION,
        phase="35H.3",
        label="exit_fence",
        errors=errors,
    )
    if payload.get("status") != "pass":
        errors.append("exit_fence: status must be pass")
    if payload.get("wave40_authority_decision") != "allowed":
        errors.append("exit_fence: wave40_authority_decision must be allowed")
    if payload.get("runtime_owned_provenance_count") != 6:
        errors.append("exit_fence: runtime_owned_provenance_count must be 6")
    if payload.get("not_closeout_authority_count") != 0:
        errors.append("exit_fence: not_closeout_authority_count must be 0")


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
    if payload.get("wave") != "35H":
        errors.append(f"{label}: wave must be 35H")
    if payload.get("phase") != phase:
        errors.append(f"{label}: phase must be {phase}")
    if not payload.get("tool"):
        errors.append(f"{label}: missing tool")
    if not payload.get("generated_at"):
        errors.append(f"{label}: missing generated_at")


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
    parser.add_argument("--wave35e-dir", type=Path, default=build.WAVE35E_DIR)
    parser.add_argument("--wave35f-dir", type=Path, default=build.WAVE35F_DIR)
    parser.add_argument("--wave35g-dir", type=Path, default=build.WAVE35G_DIR)
    parser.add_argument("--wave35h-dir", type=Path, default=build.WAVE35H_DIR)
    args = parser.parse_args(argv)

    try:
        errors = validate_wave35h_provenance(
            repo_root=args.repo_root,
            wave35e_dir=args.wave35e_dir,
            wave35f_dir=args.wave35f_dir,
            wave35g_dir=args.wave35g_dir,
            wave35h_dir=args.wave35h_dir,
        )
    except (OSError, ValueError) as exc:
        errors = [str(exc)]

    if errors:
        for error in errors:
            sys.stderr.write(f"wave35h-provenance: {error}\n")
        sys.stderr.write(f"wave35h-provenance: failed with {len(errors)} issue(s)\n")
        return 1
    sys.stdout.write("wave35h-provenance: pass\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
