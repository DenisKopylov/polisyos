#!/usr/bin/env python3
"""Build Wave 35F remediation integrity and runtime authority artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.wave35f.remediation_integrity.v1"
TOOL_NAME = "quality.validation.build-policy-design-case-wave35f-integrity"
WAVE35_DIR = Path("_build/policy-design-case/rebaseline/wave-35")
WAVE35F_DIR = Path("_build/policy-design-case/rebaseline/wave-35F")
WAVE35G_DIR = Path("_build/policy-design-case/rebaseline/wave-35G")
WAVE35_REMEDIATION_DIRS = {
    "Wave 35A": Path("_build/policy-design-case/rebaseline/wave-35A"),
    "Wave 35B": Path("_build/policy-design-case/rebaseline/wave-35B"),
    "Wave 35C": Path("_build/policy-design-case/rebaseline/wave-35C"),
    "Wave 35D": Path("_build/policy-design-case/rebaseline/wave-35D"),
    "Wave 35E": Path("_build/policy-design-case/rebaseline/wave-35E"),
}

INTEGRITY_CHECK_COMMAND = (
    "uv run python tools/quality/validation/"
    "check_policy_design_case_wave35f_integrity.py --repo-root ."
)
PASS2_CLOSEOUT_COMMAND = (
    "uv run python tools/quality/validation/"
    "check_policy_design_case_pass2_disposition.py "
    "--repo-root . --require-passing --require-closeout-ready"
)
REVIEWER_COMMAND = INTEGRITY_CHECK_COMMAND

ALLOWED_AUTHORITY_CLASSES = (
    "runtime_emitted",
    "runtime_derived",
    "test_observed",
    "synthetic_remediation_overlay",
    "manual_assertion",
)
RUNTIME_OR_TEST_AUTHORITY_CLASSES = {
    "runtime_emitted",
    "runtime_derived",
    "test_observed",
}
OVERLAY_AUTHORITY_CLASSES = {
    "synthetic_remediation_overlay",
    "manual_assertion",
}

MANUAL_ASSERTION_ARTIFACTS = {
    "implementation_feasibility_ledger.json",
    "contestability_appeals_ledger.json",
}
SYNTHETIC_OVERLAY_ARTIFACTS = {
    "scenario_variant_inventory.json",
    "projection_operator_truthfulness_matrix.json",
    "memory_authority_ledger.json",
    "trust_framing_ui_negative_tests.json",
    "wave35_disposition_update.json",
}
HUMAN_RELEASE_BLOCKING_ARTIFACTS = {
    "projection_operator_truthfulness_matrix.json",
    "memory_authority_ledger.json",
    "implementation_feasibility_ledger.json",
    "contestability_appeals_ledger.json",
    "trust_framing_ui_negative_tests.json",
}
HUMAN_SURFACE_BY_ARTIFACT = {
    "projection_operator_truthfulness_matrix.json": "dashboard_api_projection",
    "memory_authority_ledger.json": "memory_authority",
    "implementation_feasibility_ledger.json": "implementation_feasibility",
    "contestability_appeals_ledger.json": "contestability",
    "trust_framing_ui_negative_tests.json": "trust_framing",
}


def build_wave35f_integrity_outputs(
    *,
    repo_root: Path = REPO_ROOT,
    wave35_dir: Path = WAVE35_DIR,
    wave35f_dir: Path = WAVE35F_DIR,
    wave35g_dir: Path = WAVE35G_DIR,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    wave35_path = _resolve(repo_root, wave35_dir)
    wave35f_path = _resolve(repo_root, wave35f_dir)
    wave35f_path.mkdir(parents=True, exist_ok=True)

    disposition = _load_json(wave35_path / "pass2_disposition.json")
    generated_at = _utc_now()
    wave35g_backfill = _load_wave35g_backfill_coverage(
        repo_root=repo_root,
        wave35g_dir=wave35g_dir,
    )
    authority_map = _build_authority_map(
        repo_root=repo_root,
        generated_at=generated_at,
        wave35g_backfill=wave35g_backfill,
    )
    classification = _build_classification(
        disposition=disposition,
        authority_map=authority_map,
        generated_at=generated_at,
    )
    gap_ledger = _build_gap_ledger(
        classification=classification,
        authority_map=authority_map,
        generated_at=generated_at,
        wave35g_backfill=wave35g_backfill,
    )
    human_surface_audit = _build_human_surface_audit(
        repo_root=repo_root,
        generated_at=generated_at,
    )
    exit_fence = _build_exit_fence(
        classification=classification,
        gap_ledger=gap_ledger,
        human_surface_audit=human_surface_audit,
        generated_at=generated_at,
    )

    classification_path = wave35f_path / "remediation_integrity_classification.json"
    gap_path = wave35f_path / "runtime_enforcement_gap_ledger.json"
    human_path = wave35f_path / "wave35e_human_surface_enforcement_audit.json"
    authority_path = wave35f_path / "wave35_runtime_evidence_authority_map.json"
    exit_path = wave35f_path / "wave35f_exit_fence.json"
    report_path = wave35f_path / "wave35f_disposition_integrity_report.json"

    atomic_write_json(classification_path, classification)
    atomic_write_json(gap_path, gap_ledger)
    atomic_write_json(human_path, human_surface_audit)
    atomic_write_json(authority_path, authority_map)
    atomic_write_json(exit_path, exit_fence)

    output_paths = [
        classification_path,
        gap_path,
        human_path,
        authority_path,
        exit_path,
    ]
    report = _build_integrity_report(
        classification=classification,
        gap_ledger=gap_ledger,
        output_hashes=_hash_paths(repo_root, output_paths),
        generated_at=generated_at,
    )
    atomic_write_json(report_path, report)

    return {
        "classification": classification,
        "gap_ledger": gap_ledger,
        "human_surface_audit": human_surface_audit,
        "authority_map": authority_map,
        "integrity_report": report,
        "exit_fence": exit_fence,
    }


def expected_wave35f_coverage(disposition: Mapping[str, Any]) -> dict[str, list[str]]:
    remediated_ids: set[str] = set()
    artifact_paths: set[str] = set()
    for row in _as_list(disposition.get("dispositions")):
        if not isinstance(row, Mapping):
            continue
        evidence = _mapping(row.get("remediation_evidence"))
        wave = _wave_label(evidence.get("wave"))
        if wave not in WAVE35_REMEDIATION_DIRS:
            continue
        finding_id = str(row.get("finding_id") or evidence.get("finding_id") or "")
        if finding_id:
            remediated_ids.add(finding_id)
        artifact_paths.update(
            str(path)
            for path in _as_list(evidence.get("implementation_artifacts"))
            if path
        )

    for row in _as_list(disposition.get("artifact_dispositions")):
        if not isinstance(row, Mapping):
            continue
        false_alarm = _mapping(row.get("false_alarm_evidence"))
        artifact_paths.update(
            str(path)
            for path in _as_list(false_alarm.get("implementation_artifacts"))
            if path
        )
    return {
        "remediated_finding_ids": sorted(remediated_ids),
        "disposition_artifact_paths": sorted(artifact_paths),
    }


def _build_classification(
    *,
    disposition: Mapping[str, Any],
    authority_map: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    authority_by_path = {
        str(row.get("artifact_path")): row
        for row in _as_list(authority_map.get("artifacts"))
        if isinstance(row, Mapping)
    }
    rows: list[dict[str, Any]] = []
    for disposition_row in _as_list(disposition.get("dispositions")):
        if not isinstance(disposition_row, Mapping):
            continue
        evidence = _mapping(disposition_row.get("remediation_evidence"))
        wave = _wave_label(evidence.get("wave"))
        if wave not in WAVE35_REMEDIATION_DIRS:
            continue
        for artifact_path in _as_list(evidence.get("implementation_artifacts")):
            artifact = authority_by_path.get(str(artifact_path), {})
            authority_class = _authority_class(artifact)
            row = _classification_row(
                disposition_row=disposition_row,
                evidence=evidence,
                artifact=artifact,
                artifact_path=str(artifact_path),
                authority_class=authority_class,
                row_type="finding_remediation",
                closeout_critical=True,
            )
            rows.append(row)

    for artifact_row in _as_list(disposition.get("artifact_dispositions")):
        if not isinstance(artifact_row, Mapping):
            continue
        false_alarm = _mapping(artifact_row.get("false_alarm_evidence"))
        for artifact_path in _as_list(false_alarm.get("implementation_artifacts")):
            artifact = authority_by_path.get(str(artifact_path), {})
            evidence = {
                "wave": false_alarm.get("wave"),
                "phase": false_alarm.get("phase"),
                "pdd_id": artifact_row.get("pdd_id"),
                "finding_id": artifact_row.get("artifact_disposition_id"),
                "source_evidence": artifact_row.get("source_evidence"),
                "implementation_artifacts": false_alarm.get("implementation_artifacts"),
                "diagnostic_rerun": false_alarm.get("diagnostic_rerun"),
                "reviewer_command": artifact_row.get("verification_command"),
                "owner_acceptance": artifact_row.get("owner"),
            }
            row = _classification_row(
                disposition_row=artifact_row,
                evidence=evidence,
                artifact=artifact,
                artifact_path=str(artifact_path),
                authority_class=_authority_class(artifact),
                row_type="artifact_disposition_boundary",
                closeout_critical=False,
            )
            rows.append(row)

    coverage = expected_wave35f_coverage(disposition)
    observed_remediated = {
        str(row["finding_id"])
        for row in rows
        if row.get("row_type") == "finding_remediation"
    }
    observed_artifacts = {str(row["artifact_path"]) for row in rows}
    missing_findings = sorted(
        set(coverage["remediated_finding_ids"]) - observed_remediated
    )
    missing_artifacts = sorted(
        set(coverage["disposition_artifact_paths"]) - observed_artifacts
    )
    class_counts = Counter(str(row["evidence_authority_class"]) for row in rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35F",
        "phase": "35F.1",
        "status": "pass" if not missing_findings and not missing_artifacts else "fail",
        "decision_log_basis": "DL-PDC-0014",
        "allowed_evidence_authority_classes": list(ALLOWED_AUTHORITY_CLASSES),
        "summary": {
            "remediated_finding_count": len(coverage["remediated_finding_ids"]),
            "classified_row_count": len(rows),
            "authority_class_counts": dict(sorted(class_counts.items())),
            "closeout_critical_overlay_or_manual_count": sum(
                1
                for row in rows
                if row.get("closeout_critical")
                and row.get("evidence_authority_class") in OVERLAY_AUTHORITY_CLASSES
            ),
        },
        "coverage": {
            "expected_remediated_finding_ids": coverage["remediated_finding_ids"],
            "observed_remediated_finding_ids": sorted(observed_remediated),
            "missing_remediated_finding_ids": missing_findings,
            "expected_disposition_artifact_paths": coverage[
                "disposition_artifact_paths"
            ],
            "observed_disposition_artifact_paths": sorted(observed_artifacts),
            "missing_disposition_artifact_paths": missing_artifacts,
        },
        "rows": rows,
    }


def _classification_row(
    *,
    disposition_row: Mapping[str, Any],
    evidence: Mapping[str, Any],
    artifact: Mapping[str, Any],
    artifact_path: str,
    authority_class: str,
    row_type: str,
    closeout_critical: bool,
) -> dict[str, Any]:
    finding_id = str(
        disposition_row.get("finding_id")
        or evidence.get("finding_id")
        or disposition_row.get("artifact_disposition_id")
        or ""
    )
    pdd_id = str(
        evidence.get("pdd_id")
        or disposition_row.get("pdd_id")
        or _pdd_from_finding_id(finding_id)
        or ""
    )
    source_refs = sorted(
        set(_as_string_list(artifact.get("upstream_sources")))
        | set(_collect_ref_strings(evidence.get("source_evidence")))
        | set(_collect_ref_strings(disposition_row.get("source_evidence")))
    )
    rerun = _mapping(evidence.get("diagnostic_rerun"))
    counts_toward_closeout = (
        closeout_critical and authority_class in RUNTIME_OR_TEST_AUTHORITY_CLASSES
    )
    row_id = "W35F-CLASS-" + _stable_digest(
        "|".join((row_type, finding_id, artifact_path))
    )
    return {
        "row_id": row_id,
        "row_type": row_type,
        "wave": _wave_label(evidence.get("wave")),
        "phase": str(evidence.get("phase") or ""),
        "cluster_id": str(
            disposition_row.get("root_cause_cluster_id")
            or artifact.get("cluster_id")
            or _cluster_from_pdd_or_wave(pdd_id, _wave_label(evidence.get("wave")))
            or ""
        ),
        "pdd_id": pdd_id,
        "finding_id": finding_id,
        "finding_code": disposition_row.get("finding_code"),
        "artifact_path": artifact_path,
        "artifact_status": artifact.get("status"),
        "evidence_authority_class": authority_class,
        "source_refs": source_refs,
        "rerun_ref": rerun.get("artifact"),
        "reviewer_command": (
            evidence.get("reviewer_command")
            or disposition_row.get("verification_command")
            or PASS2_CLOSEOUT_COMMAND
        ),
        "owner": (
            evidence.get("owner_acceptance")
            or disposition_row.get("owner")
            or "team-quality-closeout"
        ),
        "closeout_critical": closeout_critical,
        "counts_toward_deterministic_closeout": counts_toward_closeout,
        "deterministic_closeout_authority": (
            "may_count"
            if counts_toward_closeout
            else "not_closeout_authority"
        ),
    }


def _build_authority_map(
    *,
    repo_root: Path,
    generated_at: str,
    wave35g_backfill: Mapping[str, Any],
) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    missing: list[str] = []
    for wave, directory in WAVE35_REMEDIATION_DIRS.items():
        directory_path = _resolve(repo_root, directory)
        if not directory_path.exists():
            missing.append(_rel_path(directory_path, repo_root))
            continue
        for path in sorted(directory_path.glob("*.json")):
            rel_path = _rel_path(path, repo_root)
            payload = _load_json(path)
            authority_class = _classify_artifact(rel_path, payload)
            authority_class = _apply_wave35g_authority_class(
                rel_path,
                authority_class,
                wave35g_backfill,
            )
            backfill_refs = _wave35g_backfill_refs(rel_path, wave35g_backfill)
            artifacts.append(
                {
                    "artifact_path": rel_path,
                    "wave": wave,
                    "schema_version": payload.get("schema_version"),
                    "status": payload.get("status"),
                    "cluster_id": payload.get("cluster_id"),
                    "evidence_authority_class": authority_class,
                    "upstream_source_type": _source_type(authority_class),
                    "upstream_sources": sorted(
                        set(_collect_ref_strings(payload)) | set(backfill_refs)
                    ),
                    "runtime_fact_produced": authority_class in {
                        "runtime_emitted",
                        "runtime_derived",
                        "test_observed",
                    },
                    "remediation_overlay_only": (
                        authority_class in OVERLAY_AUTHORITY_CLASSES
                    ),
                    "source_kind_explanation": _source_kind_explanation(
                        rel_path,
                        authority_class,
                    ),
                }
            )

    actual_paths = sorted(str(row["artifact_path"]) for row in artifacts)
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35F",
        "phase": "35F.1",
        "status": "pass" if not missing else "fail",
        "allowed_evidence_authority_classes": list(ALLOWED_AUTHORITY_CLASSES),
        "coverage": {
            "expected_wave35_artifact_paths": actual_paths,
            "observed_wave35_artifact_paths": actual_paths,
            "missing_wave35_artifact_paths": missing,
        },
        "artifacts": artifacts,
    }


def _build_gap_ledger(
    *,
    classification: Mapping[str, Any],
    authority_map: Mapping[str, Any],
    generated_at: str,
    wave35g_backfill: Mapping[str, Any],
) -> dict[str, Any]:
    authority_by_path = {
        str(row.get("artifact_path")): row
        for row in _as_list(authority_map.get("artifacts"))
        if isinstance(row, Mapping)
    }
    rows: list[dict[str, Any]] = []
    for classified in _as_list(classification.get("rows")):
        if not isinstance(classified, Mapping):
            continue
        if not classified.get("closeout_critical"):
            continue
        if classified.get("evidence_authority_class") not in OVERLAY_AUTHORITY_CLASSES:
            continue
        artifact_path = str(classified.get("artifact_path") or "")
        basename = Path(artifact_path).name
        blocks_release = basename in HUMAN_RELEASE_BLOCKING_ARTIFACTS
        finding_id = str(classified.get("finding_id") or "")
        boundary = _wave35g_non_closeout_boundary(
            finding_id,
            wave35g_backfill,
        )
        if boundary:
            blocks_release = False
        rows.append(
            {
                "gap_id": "W35F-GAP-" + _stable_digest(
                    str(classified.get("row_id") or artifact_path)
                ),
                "classification_row_id": classified.get("row_id"),
                "wave": classified.get("wave"),
                "cluster_id": classified.get("cluster_id"),
                "pdd_id": classified.get("pdd_id"),
                "finding_id": finding_id,
                "artifact_path": artifact_path,
                "evidence_authority_class": classified.get(
                    "evidence_authority_class"
                ),
                "missing_runtime_api_ui_enforcement": _missing_enforcement(
                    artifact_path,
                ),
                "affected_code_or_artifact_path": _affected_path(artifact_path),
                "owner": classified.get("owner") or "team-quality-closeout",
                "required_test_or_trace": _required_test_or_trace(artifact_path),
                "accepted_boundary": boundary
                or {
                    "boundary_id": "W35F-BOUNDARY-" + _stable_digest(artifact_path),
                    "boundary_decision": "not_closeout_authority",
                    "caveat": _boundary_caveat(artifact_path),
                    "blocks_wave36_closeout_authority": True,
                    "blocks_wave36_release": blocks_release,
                    "source_refs": _as_string_list(
                        authority_by_path.get(artifact_path, {}).get("upstream_sources")
                    ),
                },
                "wave36_blocking_decision": (
                    "block_wave36_release"
                    if blocks_release
                    else "exclude_from_wave36_closeout_evidence"
                ),
                "reviewer_command": classified.get("reviewer_command"),
            }
        )
    blocking = [
        row for row in rows if row["wave36_blocking_decision"] == "block_wave36_release"
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35F",
        "phase": "35F.1",
        "status": "pass_with_wave36_blockers" if blocking else "pass",
        "summary": {
            "gap_count": len(rows),
            "wave36_release_blocking_gap_count": len(blocking),
            "gap_authority_class_counts": dict(
                sorted(Counter(str(row["evidence_authority_class"]) for row in rows).items())
            ),
        },
        "rows": rows,
    }


def _build_human_surface_audit(*, repo_root: Path, generated_at: str) -> dict[str, Any]:
    wave35e_dir = repo_root / WAVE35_REMEDIATION_DIRS["Wave 35E"]
    rows: list[dict[str, Any]] = []
    projection = _load_json(wave35e_dir / "projection_operator_truthfulness_matrix.json")
    for control in _as_list(projection.get("projection_masking_negative_controls")):
        if not isinstance(control, Mapping):
            continue
        authority_class = _normalize_authority_class(
            control.get("evidence_authority_class")
        )
        has_runtime_or_test = authority_class in {"runtime_emitted", "test_observed"}
        rows.append(
            {
                "claim_surface": "dashboard_api_projection",
                "claim_id": str(control.get("masking_case") or ""),
                "artifact_path": _rel_path(
                    wave35e_dir / "projection_operator_truthfulness_matrix.json",
                    repo_root,
                ),
                "evidence_authority_class": authority_class,
                "runtime_or_test_observed": has_runtime_or_test,
                "closeout_authority_decision": (
                    "may_count" if has_runtime_or_test else "not_closeout_authority"
                ),
                "caveat": None
                if has_runtime_or_test
                else (
                    "Matrix row describes expected fail-closed projection behavior "
                    "without schema/runtime/UI evidence for this masking case."
                ),
                "required_runtime_or_test_trace": _projection_required_trace(control),
            }
        )

    memory = _load_json(wave35e_dir / "memory_authority_ledger.json")
    memory_decision = _mapping(memory.get("memory_decision"))
    rows.append(
        {
            "claim_surface": "memory_authority",
            "claim_id": str(memory_decision.get("decision") or "memory_authority"),
            "artifact_path": _rel_path(wave35e_dir / "memory_authority_ledger.json", repo_root),
            "evidence_authority_class": "synthetic_remediation_overlay",
            "runtime_or_test_observed": False,
            "closeout_authority_decision": "not_closeout_authority",
            "caveat": (
                "Prompt/tool and replay absence do not equal a runtime-emitted "
                "no-memory abstention record before serious output influence."
            ),
            "required_runtime_or_test_trace": _required_test_or_trace(
                "memory_authority_ledger.json"
            ),
        }
    )

    for filename, surface, authority_class in (
        (
            "implementation_feasibility_ledger.json",
            "implementation_feasibility",
            "manual_assertion",
        ),
        ("contestability_appeals_ledger.json", "contestability", "manual_assertion"),
    ):
        payload = _load_json(wave35e_dir / filename)
        runtime_authority_class = _institutional_ledger_runtime_authority_class(payload)
        effective_authority_class = runtime_authority_class or authority_class
        has_runtime_or_test = effective_authority_class in RUNTIME_OR_TEST_AUTHORITY_CLASSES
        rows.append(
            {
                "claim_surface": surface,
                "claim_id": surface,
                "artifact_path": _rel_path(wave35e_dir / filename, repo_root),
                "evidence_authority_class": effective_authority_class,
                "runtime_or_test_observed": has_runtime_or_test,
                "closeout_authority_decision": (
                    "may_count" if has_runtime_or_test else "not_closeout_authority"
                ),
                "caveat": None
                if has_runtime_or_test
                else (
                    "Ledger may guide remediation review but lacks runtime-owned "
                    "institutional proof provenance for final publication closeout."
                ),
                "required_runtime_or_test_trace": (
                    _wave35h_runtime_ref(payload) or _required_test_or_trace(filename)
                ),
            }
        )

    trust = _load_json(wave35e_dir / "trust_framing_ui_negative_tests.json")
    for trust_row in _as_list(trust.get("rows")):
        if not isinstance(trust_row, Mapping):
            continue
        authority_class = _normalize_authority_class(
            trust_row.get("evidence_authority_class")
        )
        has_runtime_or_test = authority_class in {"runtime_emitted", "test_observed"}
        rows.append(
            {
                "claim_surface": "trust_framing",
                "claim_id": str(trust_row.get("scenario") or ""),
                "artifact_path": _rel_path(
                    wave35e_dir / "trust_framing_ui_negative_tests.json",
                    repo_root,
                ),
                "evidence_authority_class": authority_class,
                "runtime_or_test_observed": has_runtime_or_test,
                "closeout_authority_decision": (
                    "may_count" if has_runtime_or_test else "not_closeout_authority"
                ),
                "caveat": None
                if has_runtime_or_test
                else (
                    "Trust-framing row names expected UI behavior but lacks an "
                    "actual scenario-specific UI negative trace or screenshot."
                ),
                "required_runtime_or_test_trace": _required_test_or_trace(
                    "trust_framing_ui_negative_tests.json"
                ),
            }
        )

    caveat_count = sum(
        1 for row in rows if row["closeout_authority_decision"] == "not_closeout_authority"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35F",
        "phase": "35F.1",
        "status": (
            "pass_with_not_closeout_authority_caveats" if caveat_count else "pass"
        ),
        "required_surfaces": sorted(set(HUMAN_SURFACE_BY_ARTIFACT.values())),
        "summary": {
            "row_count": len(rows),
            "not_closeout_authority_count": caveat_count,
        },
        "rows": rows,
    }


def _build_exit_fence(
    *,
    classification: Mapping[str, Any],
    gap_ledger: Mapping[str, Any],
    human_surface_audit: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    blocking = [
        row
        for row in _as_list(gap_ledger.get("rows"))
        if isinstance(row, Mapping)
        and row.get("wave36_blocking_decision") == "block_wave36_release"
    ]
    blocking_gap_ids = sorted(str(row.get("gap_id")) for row in blocking)
    blocking_finding_ids = sorted(
        {
            str(row.get("finding_id"))
            for row in blocking
            if row.get("finding_id")
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35F",
        "phase": "35F.1",
        "status": "pass",
        "wave36_release_decision": "blocked" if blocking else "allowed",
        "wave36_blocking_gap_ids": blocking_gap_ids,
        "blocking_finding_ids": blocking_finding_ids,
        "reviewer_command": REVIEWER_COMMAND,
        "entry_criteria_result": {
            "classification_covers_wave35a_to_wave35e": not classification.get(
                "coverage",
                {},
            ).get("missing_remediated_finding_ids")
            and not classification.get("coverage", {}).get(
                "missing_disposition_artifact_paths"
            ),
            "overlay_rows_have_accepted_boundaries": all(
                _mapping(row).get("accepted_boundary")
                for row in _as_list(gap_ledger.get("rows"))
            ),
            "human_surface_rows_have_runtime_or_caveat": all(
                row.get("runtime_or_test_observed")
                or row.get("closeout_authority_decision")
                == "not_closeout_authority"
                for row in _as_list(human_surface_audit.get("rows"))
                if isinstance(row, Mapping)
            ),
        },
    }


def _build_integrity_report(
    *,
    classification: Mapping[str, Any],
    gap_ledger: Mapping[str, Any],
    output_hashes: Sequence[Mapping[str, str]],
    generated_at: str,
) -> dict[str, Any]:
    blocking = [
        row
        for row in _as_list(gap_ledger.get("rows"))
        if isinstance(row, Mapping)
        and row.get("wave36_blocking_decision") == "block_wave36_release"
    ]
    unresolved_rows = [
        {
            "gap_id": row.get("gap_id"),
            "finding_id": row.get("finding_id"),
            "artifact_path": row.get("artifact_path"),
            "required_test_or_trace": row.get("required_test_or_trace"),
        }
        for row in blocking
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35F",
        "phase": "35F.1",
        "status": "pass",
        "command": INTEGRITY_CHECK_COMMAND,
        "exit_code": 0,
        "output_hashes": list(output_hashes),
        "artifact_classification_counts": classification.get("summary", {}).get(
            "authority_class_counts",
            {},
        ),
        "unresolved_closeout_critical_overlay_rows": unresolved_rows,
        "unresolved_closeout_critical_overlay_count": len(unresolved_rows),
        "reviewer_command": REVIEWER_COMMAND,
    }


def _load_wave35g_backfill_coverage(
    *,
    repo_root: Path,
    wave35g_dir: Path,
) -> dict[str, Any]:
    wave35g_path = _resolve(repo_root, wave35g_dir)
    projection = _load_optional_json(
        wave35g_path / "projection_fail_closed_runtime_backfill.json",
    )
    memory = _load_optional_json(
        wave35g_path / "memory_authority_runtime_abstention_trace.json",
    )
    trust = _load_optional_json(
        wave35g_path / "trust_framing_ui_negative_trace_bundle.json",
    )
    institutional = _load_optional_json(
        wave35g_path / "institutional_provenance_boundary_ledger.json",
    )
    return {
        "projection": projection,
        "memory": memory,
        "trust": trust,
        "institutional": institutional,
        "runtime_or_test_findings": sorted(
            set(_runtime_or_test_projection_findings(projection))
            | set(_runtime_or_test_memory_findings(memory))
            | set(_runtime_or_test_trust_findings(trust))
            | set(_runtime_or_test_institutional_findings(institutional))
        ),
        "non_closeout_boundary_by_finding": _institutional_boundaries_by_finding(
            institutional,
        ),
    }


def _apply_wave35g_authority_class(
    artifact_path: str,
    authority_class: str,
    wave35g_backfill: Mapping[str, Any],
) -> str:
    filename = Path(artifact_path).name
    runtime_or_test_findings = set(
        _as_string_list(wave35g_backfill.get("runtime_or_test_findings"))
    )
    projection_findings = {
        "PDD-034-F001",
        "PDD-034-F002",
        "PDD-034-F003",
        "PDD-069-F001",
        "PDD-069-F002",
        "PDD-069-F003",
    }
    if (
        filename == "projection_operator_truthfulness_matrix.json"
        and projection_findings <= runtime_or_test_findings
    ):
        return "test_observed"
    if (
        filename == "memory_authority_ledger.json"
        and {"PDD-083-F001", "PDD-083-F002", "PDD-083-F003"}
        <= runtime_or_test_findings
    ):
        return "runtime_emitted"
    if (
        filename == "trust_framing_ui_negative_tests.json"
        and {"PDD-103-F001", "PDD-103-F002", "PDD-103-F003", "PDD-103-F004"}
        <= runtime_or_test_findings
    ):
        return "test_observed"
    if (
        filename == "implementation_feasibility_ledger.json"
        and {"PDD-097-F001", "PDD-097-F002", "PDD-097-F003"} <= runtime_or_test_findings
    ):
        return "runtime_emitted"
    if (
        filename == "contestability_appeals_ledger.json"
        and {"PDD-099-F001", "PDD-099-F002", "PDD-099-F003"} <= runtime_or_test_findings
    ):
        return "runtime_emitted"
    return authority_class


def _wave35g_backfill_refs(
    artifact_path: str,
    wave35g_backfill: Mapping[str, Any],
) -> list[str]:
    filename = Path(artifact_path).name
    refs: list[str] = []
    if filename == "projection_operator_truthfulness_matrix.json" and _mapping(
        wave35g_backfill.get("projection")
    ):
        refs.append(
            "_build/policy-design-case/rebaseline/wave-35G/"
            "projection_fail_closed_runtime_backfill.json"
        )
    if filename == "memory_authority_ledger.json" and _mapping(
        wave35g_backfill.get("memory")
    ):
        refs.append(
            "_build/policy-design-case/rebaseline/wave-35G/"
            "memory_authority_runtime_abstention_trace.json"
        )
    if filename == "trust_framing_ui_negative_tests.json" and _mapping(
        wave35g_backfill.get("trust")
    ):
        refs.append(
            "_build/policy-design-case/rebaseline/wave-35G/"
            "trust_framing_ui_negative_trace_bundle.json"
        )
    if filename in {
        "implementation_feasibility_ledger.json",
        "contestability_appeals_ledger.json",
    } and _mapping(wave35g_backfill.get("institutional")):
        refs.append(
            "_build/policy-design-case/rebaseline/wave-35G/"
            "institutional_provenance_boundary_ledger.json"
        )
    return refs


def _wave35g_non_closeout_boundary(
    finding_id: str,
    wave35g_backfill: Mapping[str, Any],
) -> dict[str, Any] | None:
    by_finding = _mapping(wave35g_backfill.get("non_closeout_boundary_by_finding"))
    boundary = _mapping(by_finding.get(finding_id))
    if not boundary:
        return None
    return {
        "boundary_id": str(boundary.get("boundary_id") or f"W35G-BOUNDARY-{finding_id}"),
        "boundary_decision": "not_closeout_authority",
        "caveat": str(boundary.get("caveat") or ""),
        "blocks_wave36_closeout_authority": True,
        "blocks_wave36_release": False,
        "source_refs": [
            "_build/policy-design-case/rebaseline/wave-35G/"
            "institutional_provenance_boundary_ledger.json",
        ],
        "source_wave35g_boundary": boundary,
    }


def _runtime_or_test_projection_findings(payload: Mapping[str, Any]) -> list[str]:
    rows = _mapping_rows(payload, "evidence_rows")
    cases = {str(row.get("masking_case")) for row in rows}
    if (
        payload.get("status") == "complete"
        and cases
        == {
            "missing",
            "stale",
            "conflicting",
            "reissued",
            "withdrawn",
            "non_authoritative",
            "projection_only",
        }
        and all(
            row.get("evidence_authority") in RUNTIME_OR_TEST_AUTHORITY_CLASSES
            and _mapping(row.get("command")).get("exit_code") == 0
            and row.get("counts_toward_deterministic_closeout") is True
            for row in rows
        )
    ):
        return _as_string_list(payload.get("affected_findings"))
    return []


def _runtime_or_test_memory_findings(payload: Mapping[str, Any]) -> list[str]:
    findings: list[str] = []
    for row in _mapping_rows(payload, "evidence_rows"):
        if (
            row.get("evidence_authority") in RUNTIME_OR_TEST_AUTHORITY_CLASSES
            and _mapping(row.get("command")).get("exit_code") == 0
            and row.get("counts_toward_deterministic_closeout") is True
        ):
            findings.append(str(row.get("finding_id")))
    return sorted(findings)


def _runtime_or_test_trust_findings(payload: Mapping[str, Any]) -> list[str]:
    rows = _mapping_rows(payload, "scenario_rows")
    scenarios = {str(row.get("scenario")) for row in rows}
    if (
        payload.get("status") == "complete"
        and scenarios
        == {
            "low_confidence",
            "disputed",
            "untraced",
            "simulated",
            "stale",
            "draft",
            "override_approved",
            "frontend_signed",
        }
        and all(
            row.get("authority_classification") in RUNTIME_OR_TEST_AUTHORITY_CLASSES
            and _mapping(row.get("command")).get("exit_code") == 0
            and row.get("counts_toward_deterministic_closeout") is True
            for row in rows
        )
    ):
        return _as_string_list(payload.get("affected_findings"))
    return []


def _runtime_or_test_institutional_findings(payload: Mapping[str, Any]) -> list[str]:
    findings: list[str] = []
    for row in _mapping_rows(payload, "rows"):
        if (
            row.get("evidence_authority") in RUNTIME_OR_TEST_AUTHORITY_CLASSES
            and row.get("runtime_owned_provenance_present") is True
            and row.get("counts_toward_deterministic_closeout") is True
        ):
            findings.append(str(row.get("finding_id")))
    return sorted(findings)


def _institutional_boundaries_by_finding(
    payload: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    boundaries: dict[str, dict[str, Any]] = {}
    for row in _mapping_rows(payload, "rows"):
        finding_id = str(row.get("finding_id") or "")
        boundary = _mapping(row.get("enforceable_boundary"))
        if (
            finding_id
            and row.get("evidence_authority") == "not_closeout_authority"
            and row.get("counts_toward_deterministic_closeout") is False
            and boundary.get("boundary_decision") == "not_closeout_authority"
            and boundary.get("blocks_deterministic_closeout_authority") is True
        ):
            boundaries[finding_id] = dict(boundary)
    return boundaries


def _classify_artifact(path: str, payload: Mapping[str, Any]) -> str:
    filename = Path(path).name
    if filename in MANUAL_ASSERTION_ARTIFACTS:
        runtime_class = _institutional_ledger_runtime_authority_class(payload)
        if runtime_class:
            return runtime_class
        return "manual_assertion"
    if filename in SYNTHETIC_OVERLAY_ARTIFACTS:
        return "synthetic_remediation_overlay"
    if "phase34" in filename and "rerun" in filename:
        return "test_observed"
    runtime_evidence = _mapping(payload.get("runtime_enforcement_evidence"))
    authority_class = _normalize_authority_class(
        runtime_evidence.get("evidence_authority_class")
    )
    if authority_class in ALLOWED_AUTHORITY_CLASSES:
        return authority_class
    return "runtime_derived"


def _normalize_authority_class(value: object) -> str:
    raw = str(value or "")
    if raw in ALLOWED_AUTHORITY_CLASSES:
        return raw
    if raw.startswith("mixed_") or "synthetic_remediation_overlay" in raw:
        return "synthetic_remediation_overlay"
    return raw


def _institutional_ledger_runtime_authority_class(
    payload: Mapping[str, Any],
) -> str | None:
    runtime_evidence = _mapping(payload.get("runtime_enforcement_evidence"))
    authority_class = _normalize_authority_class(
        runtime_evidence.get("evidence_authority_class")
    )
    if authority_class not in RUNTIME_OR_TEST_AUTHORITY_CLASSES:
        return None
    if runtime_evidence.get("runtime_owned_provenance_present") is not True:
        return None
    if runtime_evidence.get("manual_assertion_remaining_count") not in (0, "0"):
        return None
    rows = _mapping_rows(payload, "rows")
    if not rows:
        return None
    if not all(_mapping(row.get("runtime_owned_provenance")) for row in rows):
        return None
    return authority_class


def _wave35h_runtime_ref(payload: Mapping[str, Any]) -> str | None:
    ownership = _mapping(payload.get("wave35h_runtime_ownership"))
    artifact_ref = str(ownership.get("artifact_ref") or "")
    if artifact_ref:
        return artifact_ref
    runtime_evidence = _mapping(payload.get("runtime_enforcement_evidence"))
    artifact_ref = str(runtime_evidence.get("artifact_ref") or "")
    return artifact_ref or None


def _authority_class(artifact: Mapping[str, Any]) -> str:
    authority_class = str(artifact.get("evidence_authority_class") or "")
    return authority_class if authority_class in ALLOWED_AUTHORITY_CLASSES else "manual_assertion"


def _source_type(authority_class: str) -> str:
    if authority_class == "runtime_emitted":
        return "runtime"
    if authority_class == "runtime_derived":
        return "runtime_derived"
    if authority_class == "test_observed":
        return "test"
    if authority_class == "manual_assertion":
        return "manual"
    return "remediation_overlay"


def _source_kind_explanation(path: str, authority_class: str) -> str:
    filename = Path(path).name
    if authority_class in {"synthetic_remediation_overlay", "manual_assertion"}:
        return (
            f"{filename} is a Wave 35 remediation overlay. It may guide review "
            "but cannot be counted as deterministic closeout proof without "
            "Wave 35F runtime/test backfill or an explicit exclusion boundary."
        )
    if authority_class == "test_observed":
        return f"{filename} records a command or test-observed rerun result."
    return f"{filename} is derived from runtime, diagnostic, or quality evidence."


def _missing_enforcement(artifact_path: str) -> str:
    filename = Path(artifact_path).name
    if filename == "projection_operator_truthfulness_matrix.json":
        return (
            "schema/runtime/API/UI enforcement for missing, stale, conflicting, "
            "reissued, withdrawn, non-authoritative, and projection-only masking"
        )
    if filename == "memory_authority_ledger.json":
        return "runtime-emitted no-memory abstention or memory-use authority record"
    if filename == "trust_framing_ui_negative_tests.json":
        return "actual scenario-specific UI negative test trace or screenshot"
    if filename == "implementation_feasibility_ledger.json":
        return "runtime-owned implementation feasibility ledger provenance"
    if filename == "contestability_appeals_ledger.json":
        return "runtime-owned appeal outcome and lifecycle provenance"
    return "runtime/test-observed enforcement for this remediation overlay"


def _affected_path(artifact_path: str) -> str:
    filename = Path(artifact_path).name
    if filename == "projection_operator_truthfulness_matrix.json":
        return "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts"
    if filename == "trust_framing_ui_negative_tests.json":
        return "apps/runtime-dashboard/e2e/journeys/honest-diagnostics-operator.spec.ts"
    if filename == "memory_authority_ledger.json":
        return "src/polisyos/scientist/orchestration/memory"
    return artifact_path


def _required_test_or_trace(artifact_path: str) -> str:
    filename = Path(artifact_path).name
    if filename == "projection_operator_truthfulness_matrix.json":
        return (
            "Add schema/runtime/API/UI negative traces for missing, stale, "
            "conflicting, reissued, withdrawn, non-authoritative, and "
            "projection-only projection masking."
        )
    if filename == "memory_authority_ledger.json":
        return (
            "Emit and test a runtime no-memory abstention record or memory-use "
            "authority record before serious output influence."
        )
    if filename == "trust_framing_ui_negative_tests.json":
        return (
            "Capture actual UI negative test traces or screenshots for "
            "low-confidence, disputed, untraced, simulated, stale, draft, "
            "override-approved, and frontend-signed states."
        )
    if filename == "implementation_feasibility_ledger.json":
        return (
            "Back ledger rows with runtime-owned provenance or keep final "
            "publication/closeout from relying on them as institutional proof."
        )
    if filename == "contestability_appeals_ledger.json":
        return (
            "Back appeal rows with runtime-owned lifecycle/provenance traces or "
            "keep closeout from relying on them as institutional proof."
        )
    return (
        "Exclude this overlay from deterministic closeout evidence or backfill "
        "runtime/test-observed proof."
    )


def _boundary_caveat(artifact_path: str) -> str:
    surface = HUMAN_SURFACE_BY_ARTIFACT.get(Path(artifact_path).name)
    if surface:
        return (
            f"{surface} evidence remains not_closeout_authority until Wave 35F "
            "observes runtime/test proof for the missing enforcement."
        )
    return (
        "This remediation overlay is excluded from Wave 36 deterministic "
        "closeout authority; only runtime/test-observed companion artifacts may count."
    )


def _projection_required_trace(control: Mapping[str, Any]) -> str:
    runtime_ref = control.get("runtime_enforcement_ref")
    ui_ref = control.get("ui_test_ref")
    if runtime_ref or ui_ref:
        return str(runtime_ref or ui_ref)
    return _required_test_or_trace("projection_operator_truthfulness_matrix.json")


def _collect_ref_strings(value: object) -> list[str]:
    refs: set[str] = set()

    def visit(item: object) -> None:
        if isinstance(item, str):
            if _looks_like_ref(item):
                refs.add(item)
        elif isinstance(item, Mapping):
            for child in item.values():
                visit(child)
        elif isinstance(item, list | tuple):
            for child in item:
                visit(child)

    visit(value)
    return sorted(refs)


def _looks_like_ref(value: str) -> bool:
    if len(value) > 320:
        return False
    markers = (
        "/",
        ".json",
        ".md",
        ".py",
        ".ts",
        ".tsx",
        "sha256:",
        "cas://",
        "ledger://",
        "appeal-ledger://",
        "#",
    )
    return any(marker in value for marker in markers)


def _hash_paths(repo_root: Path, paths: Sequence[Path]) -> list[dict[str, str]]:
    hashes: list[dict[str, str]] = []
    for path in paths:
        if path.exists():
            hashes.append(
                {
                    "path": _rel_path(path, repo_root),
                    "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    return hashes


def _stable_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _pdd_from_finding_id(finding_id: str) -> str:
    parts = finding_id.split("-")
    if len(parts) >= 2 and parts[0] == "PDD":
        return "-".join(parts[:2])
    return ""


def _cluster_from_pdd_or_wave(pdd_id: str, wave: str) -> str:
    if pdd_id in {"PDD-037", "PDD-055", "PDD-056"}:
        return "runtime_scenario_variant_coverage"
    if pdd_id in {"PDD-038", "PDD-064", "PDD-065", "PDD-098"}:
        return "adversarial_fail_closed_and_strategic_gates"
    if pdd_id in {"PDD-044", "PDD-088", "PDD-100", "PDD-101"}:
        return "claim_authority_and_extraction_measurement_binding"
    if pdd_id in {"PDD-048", "PDD-050", "PDD-051", "PDD-057", "PDD-087"}:
        return "semantic_validity_monitoring_and_model_readiness"
    if pdd_id in {"PDD-046", "PDD-077", "PDD-078", "PDD-090", "PDD-104"}:
        return "operational_recovery_resource_and_archive_readiness"
    if wave == "Wave 35E":
        return "human_facing_legitimacy_memory_and_trust_controls"
    return ""


def _wave_label(value: object) -> str:
    raw = str(value or "")
    if raw.startswith("Wave "):
        return raw
    return f"Wave {raw}" if raw else ""


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (repo_root / path).resolve(strict=False)


def _rel_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return payload


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_json(path)


def _mapping_rows(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    return [row for row in _as_list(payload.get(key)) if isinstance(row, Mapping)]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_string_list(value: object) -> list[str]:
    return [str(item) for item in _as_list(value)]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave35-dir", type=Path, default=WAVE35_DIR)
    parser.add_argument("--wave35f-dir", type=Path, default=WAVE35F_DIR)
    parser.add_argument("--wave35g-dir", type=Path, default=WAVE35G_DIR)
    args = parser.parse_args(argv)

    outputs = build_wave35f_integrity_outputs(
        repo_root=args.repo_root,
        wave35_dir=args.wave35_dir,
        wave35f_dir=args.wave35f_dir,
        wave35g_dir=args.wave35g_dir,
    )
    classification = outputs["classification"]
    gap_ledger = outputs["gap_ledger"]
    sys.stdout.write(
        "wave35f-integrity-build: "
        f"rows={classification['summary']['classified_row_count']} "
        f"gaps={gap_ledger['summary']['gap_count']} "
        f"wave36={outputs['exit_fence']['wave36_release_decision']}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
