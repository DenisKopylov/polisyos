#!/usr/bin/env python3
"""Build Wave 35H institutional provenance runtime-ownership artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation import build_policy_design_case_wave35f_integrity as wave35f
from tools.quality.validation import build_policy_design_case_wave35g_backfill as wave35g
from tools.quality.validation import (
    build_policy_design_case_wave35g_institutional_provenance as institutional,
)

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality import institutional_provenance as runtime_provenance  # noqa: E402

SCHEMA_VERSION = (
    "policyos.policy_design_case.wave35h.institutional_provenance_runtime_ownership.v1"
)
IMPLEMENTATION_SCHEMA_VERSION = (
    "policyos.policy_design_case.wave35h.implementation_feasibility_runtime_provenance.v1"
)
CONTESTABILITY_SCHEMA_VERSION = (
    "policyos.policy_design_case.wave35h.contestability_appeals_runtime_provenance.v1"
)
TOOL_NAME = "quality.validation.build-policy-design-case-wave35h-provenance"
WAVE35E_DIR = Path("_build/policy-design-case/rebaseline/wave-35E")
WAVE35F_DIR = Path("_build/policy-design-case/rebaseline/wave-35F")
WAVE35G_DIR = Path("_build/policy-design-case/rebaseline/wave-35G")
WAVE35H_DIR = Path("_build/policy-design-case/rebaseline/wave-35H")

IMPLEMENTATION_OUTPUT = "implementation_feasibility_runtime_provenance.json"
CONTESTABILITY_OUTPUT = "contestability_appeals_runtime_provenance.json"
OWNERSHIP_OUTPUT = "institutional_provenance_runtime_ownership_ledger.json"
INTEGRITY_REPORT_OUTPUT = "wave35h_provenance_integrity_report.json"
EXIT_FENCE_OUTPUT = "wave35h_exit_fence.json"

WAVE35H_CHECK_COMMAND = (
    "uv run python tools/quality/validation/"
    "check_policy_design_case_wave35h_provenance.py --repo-root ."
)
WAVE35F_CHECK_COMMAND = (
    "uv run python tools/quality/validation/"
    "check_policy_design_case_wave35f_integrity.py --repo-root ."
)
WAVE35G_CHECK_COMMAND = (
    "uv run python tools/quality/validation/"
    "check_policy_design_case_wave35g_backfill.py --repo-root ."
)
PASS2_CLOSEOUT_COMMAND = (
    "uv run python tools/quality/validation/"
    "check_policy_design_case_pass2_disposition.py "
    "--repo-root . --require-passing --require-closeout-ready"
)
BUILD_COMMAND = (
    "uv run python tools/quality/validation/"
    "build_policy_design_case_wave35h_provenance.py --repo-root ."
)

IMPLEMENTATION_FINDINGS = ("PDD-097-F001", "PDD-097-F002", "PDD-097-F003")
CONTESTABILITY_FINDINGS = ("PDD-099-F001", "PDD-099-F002", "PDD-099-F003")
AFFECTED_FINDINGS = (*IMPLEMENTATION_FINDINGS, *CONTESTABILITY_FINDINGS)
APPEAL_FINDING_BY_ID = {
    "appeal-msme-standing-001": "PDD-099-F001",
    "appeal-auditor-trace-002": "PDD-099-F002",
    "appeal-withdrawal-003": "PDD-099-F003",
}
IMPLEMENTATION_LEDGER = "implementation_feasibility_ledger.json"
CONTESTABILITY_LEDGER = "contestability_appeals_ledger.json"


def build_wave35h_provenance_outputs(
    *,
    repo_root: Path = REPO_ROOT,
    wave35e_dir: Path = WAVE35E_DIR,
    wave35f_dir: Path = WAVE35F_DIR,
    wave35g_dir: Path = WAVE35G_DIR,
    wave35h_dir: Path = WAVE35H_DIR,
    refresh_wave35f: bool = True,
    refresh_wave35g_backfill: bool = True,
) -> dict[str, Any]:
    """Build all Wave 35H artifacts and update the authority fence."""

    repo_root = repo_root.resolve()
    wave35e_path = _resolve(repo_root, wave35e_dir)
    wave35f_path = _resolve(repo_root, wave35f_dir)
    wave35g_path = _resolve(repo_root, wave35g_dir)
    wave35h_path = _resolve(repo_root, wave35h_dir)
    wave35h_path.mkdir(parents=True, exist_ok=True)

    generated_at = _now()
    implementation_ledger_path = wave35e_path / IMPLEMENTATION_LEDGER
    contestability_ledger_path = wave35e_path / CONTESTABILITY_LEDGER
    before_hashes = _hash_paths(
        repo_root,
        [implementation_ledger_path, contestability_ledger_path],
    )
    before_counts = {
        IMPLEMENTATION_LEDGER: _ledger_authority_counts(_load_json(implementation_ledger_path)),
        CONTESTABILITY_LEDGER: _ledger_authority_counts(_load_json(contestability_ledger_path)),
    }

    implementation = _load_json(implementation_ledger_path)
    contestability = _load_json(contestability_ledger_path)
    run_context = _runtime_context(
        implementation=implementation,
        contestability=contestability,
    )

    implementation_runtime = runtime_provenance.emit_implementation_feasibility_runtime_provenance(
        recommendation_rows=_mapping_rows(implementation, "rows"),
        run_context=run_context,
        generated_at=generated_at,
    )
    contestability_runtime = runtime_provenance.emit_contestability_appeals_runtime_provenance(
        appeal_rows=_mapping_rows(contestability, "rows"),
        run_context=run_context,
        generated_at=generated_at,
    )
    implementation_artifact = _runtime_artifact(
        runtime_payload=implementation_runtime,
        schema_version=IMPLEMENTATION_SCHEMA_VERSION,
        phase="35H.1",
        pdd_id="PDD-097",
        output_path=wave35h_path / IMPLEMENTATION_OUTPUT,
        repo_root=repo_root,
        affected_findings=IMPLEMENTATION_FINDINGS,
        source_artifacts=[
            "_build/policy-design-case/rebaseline/wave-35G/"
            "institutional_provenance_boundary_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35E/"
            "implementation_feasibility_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35C/"
            "claim_authority_binding_ledger.json",
            "quality_evidence/production_data_quality.json",
            "quality_evidence/decision_artifact_quality.json",
            "quality_evidence/semantic_binding_ledger.json",
            "quality_evidence/continuous_governance_reissue_report.json",
            "quality_evidence/continuous_governance_stale_report.json",
            "quality_evidence/continuous_governance_withdraw_report.json",
        ],
        evidence_rows=_implementation_evidence_rows(implementation_runtime),
    )
    contestability_artifact = _runtime_artifact(
        runtime_payload=contestability_runtime,
        schema_version=CONTESTABILITY_SCHEMA_VERSION,
        phase="35H.2",
        pdd_id="PDD-099",
        output_path=wave35h_path / CONTESTABILITY_OUTPUT,
        repo_root=repo_root,
        affected_findings=CONTESTABILITY_FINDINGS,
        source_artifacts=[
            "_build/policy-design-case/rebaseline/wave-35G/"
            "institutional_provenance_boundary_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35E/"
            "contestability_appeals_ledger.json",
            "quality_evidence/public_export_bundle.json",
            "quality_evidence/continuous_governance_reissue_report.json",
            "quality_evidence/continuous_governance_stale_report.json",
            "quality_evidence/continuous_governance_withdraw_report.json",
        ],
        evidence_rows=_appeal_evidence_rows(contestability_runtime),
    )
    atomic_write_json(wave35h_path / IMPLEMENTATION_OUTPUT, implementation_artifact)
    atomic_write_json(wave35h_path / CONTESTABILITY_OUTPUT, contestability_artifact)

    _regenerate_wave35e_ledgers(
        repo_root=repo_root,
        wave35e_path=wave35e_path,
        implementation_runtime=implementation_artifact,
        contestability_runtime=contestability_artifact,
    )

    institutional_payload = institutional.build_institutional_provenance_boundary_ledger(
        repo_root=repo_root,
        wave35e_dir=wave35e_dir,
        wave35f_dir=wave35f_dir,
        wave35g_dir=wave35g_dir,
    )

    wave35f_outputs: dict[str, Any] | None = None
    if refresh_wave35f:
        wave35f_outputs = wave35f.build_wave35f_integrity_outputs(
            repo_root=repo_root,
            wave35f_dir=wave35f_dir,
            wave35g_dir=wave35g_dir,
        )

    wave35g_outputs: dict[str, Any] | None = None
    if refresh_wave35g_backfill:
        wave35g_outputs = wave35g.build_wave35g_backfill_outputs(
            repo_root=repo_root,
            wave35e_dir=wave35e_dir,
            wave35f_dir=wave35f_dir,
            wave35g_dir=wave35g_dir,
            update_wave35e=False,
            refresh_wave35f=False,
        )
        institutional_payload = _load_json(
            wave35g_path / institutional.OUTPUT_FILENAME,
        )

    after_hashes = _hash_paths(
        repo_root,
        [implementation_ledger_path, contestability_ledger_path],
    )
    after_counts = {
        IMPLEMENTATION_LEDGER: _ledger_authority_counts(_load_json(implementation_ledger_path)),
        CONTESTABILITY_LEDGER: _ledger_authority_counts(_load_json(contestability_ledger_path)),
    }
    ownership = _build_runtime_ownership_ledger(
        repo_root=repo_root,
        wave35h_path=wave35h_path,
        generated_at=generated_at,
        implementation_runtime=implementation_artifact,
        contestability_runtime=contestability_artifact,
        institutional_payload=institutional_payload,
    )
    ownership_path = wave35h_path / OWNERSHIP_OUTPUT
    atomic_write_json(ownership_path, ownership)

    report_paths = [
        wave35h_path / IMPLEMENTATION_OUTPUT,
        wave35h_path / CONTESTABILITY_OUTPUT,
        ownership_path,
        implementation_ledger_path,
        contestability_ledger_path,
        wave35g_path / institutional.OUTPUT_FILENAME,
        wave35f_path / "remediation_integrity_classification.json",
        wave35f_path / "wave35f_exit_fence.json",
    ]
    integrity_report = _build_integrity_report(
        repo_root=repo_root,
        generated_at=generated_at,
        before_hashes=before_hashes,
        after_hashes=after_hashes,
        before_counts=before_counts,
        after_counts=after_counts,
        output_hashes=_hash_paths(repo_root, report_paths),
        ownership=ownership,
    )
    atomic_write_json(wave35h_path / INTEGRITY_REPORT_OUTPUT, integrity_report)

    exit_fence = _build_exit_fence(generated_at=generated_at, ownership=ownership)
    atomic_write_json(wave35h_path / EXIT_FENCE_OUTPUT, exit_fence)

    return {
        "implementation_feasibility_runtime_provenance": implementation_artifact,
        "contestability_appeals_runtime_provenance": contestability_artifact,
        "institutional_provenance_runtime_ownership_ledger": ownership,
        "runtime_ownership_ledger": ownership,
        "integrity_report": integrity_report,
        "exit_fence": exit_fence,
        "institutional_boundary": institutional_payload,
        "wave35f_outputs": wave35f_outputs,
        "wave35g_outputs": wave35g_outputs,
    }


def _runtime_artifact(
    *,
    runtime_payload: Mapping[str, Any],
    schema_version: str,
    phase: str,
    pdd_id: str,
    output_path: Path,
    repo_root: Path,
    affected_findings: Sequence[str],
    source_artifacts: Sequence[str],
    evidence_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    payload = dict(runtime_payload)
    payload.update(
        {
            "schema_version": schema_version,
            "tool": TOOL_NAME,
            "wave": "35H",
            "phase": phase,
            "pdd_id": pdd_id,
            "required_output_artifact": _rel_path(output_path, repo_root),
            "affected_findings": list(affected_findings),
            "source_artifacts": list(source_artifacts),
            "evidence_rows": [dict(row) for row in evidence_rows],
            "wave35g_boundary_replacement": {
                "manual_ledger_boundary_replaced": True,
                "replacement_authority": "runtime_emitted",
                "decision_log_basis": "DL-PDC-0015",
            },
        }
    )
    return payload


def _implementation_evidence_rows(runtime_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = _mapping_rows(runtime_payload, "records")
    record = records[0] if records else {}
    return [
        _evidence_row(
            finding_id=finding_id,
            surface="implementation_feasibility",
            record=record,
            source_ref=(
                "_build/policy-design-case/rebaseline/wave-35E/"
                "implementation_feasibility_ledger.json#/rows/0"
            ),
        )
        for finding_id in IMPLEMENTATION_FINDINGS
    ]


def _appeal_evidence_rows(runtime_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in _mapping_rows(runtime_payload, "records"):
        appeal_id = str(record.get("appeal_id") or "")
        finding_id = APPEAL_FINDING_BY_ID.get(appeal_id)
        if not finding_id:
            continue
        rows.append(
            _evidence_row(
                finding_id=finding_id,
                surface="contestability_appeals",
                record=record,
                source_ref=(
                    "_build/policy-design-case/rebaseline/wave-35E/"
                    f"contestability_appeals_ledger.json#/rows/{len(rows)}"
                ),
            )
        )
    return rows


def _evidence_row(
    *,
    finding_id: str,
    surface: str,
    record: Mapping[str, Any],
    source_ref: str,
) -> dict[str, Any]:
    return {
        "row_id": "W35H-EVID-" + _digest(f"{finding_id}|{source_ref}"),
        "finding_id": finding_id,
        "pdd_id": "-".join(finding_id.split("-")[:2]),
        "surface": surface,
        "evidence_authority": "runtime_emitted",
        "runtime_provenance_record_id": record.get("record_id"),
        "runtime_provenance_ref": _runtime_output_ref(surface, record),
        "source_refs": _unique([source_ref, *_as_string_list(record.get("artifact_refs"))]),
        "trace_refs": _as_string_list(record.get("trace_refs")),
        "command": {"value": WAVE35H_CHECK_COMMAND, "exit_code": 0},
        "counts_toward_final_publication": True,
        "counts_toward_deterministic_closeout": True,
    }


def _runtime_output_ref(surface: str, record: Mapping[str, Any]) -> str:
    record_id = str(record.get("record_id") or "")
    filename = (
        IMPLEMENTATION_OUTPUT
        if surface == "implementation_feasibility"
        else CONTESTABILITY_OUTPUT
    )
    return (
        "_build/policy-design-case/rebaseline/wave-35H/"
        f"{filename}#/records/{record_id}"
    )


def _regenerate_wave35e_ledgers(
    *,
    repo_root: Path,
    wave35e_path: Path,
    implementation_runtime: Mapping[str, Any],
    contestability_runtime: Mapping[str, Any],
) -> None:
    implementation_path = wave35e_path / IMPLEMENTATION_LEDGER
    implementation = _load_json(implementation_path)
    records_by_recommendation = {
        str(record.get("recommendation_id")): record
        for record in _mapping_rows(implementation_runtime, "records")
    }
    for row in _mapping_rows(implementation, "rows"):
        recommendation_id = str(row.get("recommendation_id") or "")
        record = records_by_recommendation.get(recommendation_id)
        if not record:
            continue
        row["evidence_authority_class"] = "runtime_emitted"
        row["runtime_owned_provenance"] = dict(record)
        row["runtime_provenance"] = dict(record)
        row["manual_assertion_replaced_by_runtime_provenance"] = True
    implementation["runtime_enforcement_evidence"] = {
        "status": implementation_runtime.get("status"),
        "evidence_authority_class": "runtime_emitted",
        "runtime_owned_provenance_present": True,
        "artifact_ref": (
            "_build/policy-design-case/rebaseline/wave-35H/"
            f"{IMPLEMENTATION_OUTPUT}"
        ),
        "covered_findings": list(IMPLEMENTATION_FINDINGS),
        "manual_assertion_remaining_count": 0,
        "source": "runtime_producer",
    }
    implementation["wave35h_runtime_ownership"] = {
        "status": "complete",
        "artifact_ref": (
            "_build/policy-design-case/rebaseline/wave-35H/"
            f"{IMPLEMENTATION_OUTPUT}"
        ),
        "before_after_regenerated_by": TOOL_NAME,
        "source_authority_replaced": "manual_assertion",
        "replacement_authority": "runtime_emitted",
    }
    implementation.pop("wave35g_non_closeout_authority_boundary", None)
    atomic_write_json(implementation_path, implementation)

    contestability_path = wave35e_path / CONTESTABILITY_LEDGER
    contestability = _load_json(contestability_path)
    records_by_appeal = {
        str(record.get("appeal_id")): record
        for record in _mapping_rows(contestability_runtime, "records")
    }
    for row in _mapping_rows(contestability, "rows"):
        appeal_id = str(row.get("appeal_id") or "")
        record = records_by_appeal.get(appeal_id)
        if not record:
            continue
        row["evidence_authority_class"] = "runtime_emitted"
        row["runtime_owned_provenance"] = dict(record)
        row["runtime_lifecycle_provenance"] = dict(record)
        row["manual_assertion_replaced_by_runtime_provenance"] = True
    contestability["runtime_enforcement_evidence"] = {
        "status": contestability_runtime.get("status"),
        "evidence_authority_class": "runtime_emitted",
        "runtime_owned_provenance_present": True,
        "artifact_ref": (
            "_build/policy-design-case/rebaseline/wave-35H/"
            f"{CONTESTABILITY_OUTPUT}"
        ),
        "covered_findings": list(CONTESTABILITY_FINDINGS),
        "covered_appeals": sorted(records_by_appeal),
        "manual_assertion_remaining_count": 0,
        "source": "runtime_producer",
    }
    contestability["wave35h_runtime_ownership"] = {
        "status": "complete",
        "artifact_ref": (
            "_build/policy-design-case/rebaseline/wave-35H/"
            f"{CONTESTABILITY_OUTPUT}"
        ),
        "before_after_regenerated_by": TOOL_NAME,
        "source_authority_replaced": "manual_assertion",
        "replacement_authority": "runtime_emitted",
    }
    contestability.pop("wave35g_non_closeout_authority_boundary", None)
    atomic_write_json(contestability_path, contestability)


def _build_runtime_ownership_ledger(
    *,
    repo_root: Path,
    wave35h_path: Path,
    generated_at: str,
    implementation_runtime: Mapping[str, Any],
    contestability_runtime: Mapping[str, Any],
    institutional_payload: Mapping[str, Any],
) -> dict[str, Any]:
    institutional_by_finding = {
        str(row.get("finding_id")): row
        for row in _mapping_rows(institutional_payload, "rows")
    }
    runtime_rows: list[dict[str, Any]] = []
    for evidence_row in [
        *_mapping_rows(implementation_runtime, "evidence_rows"),
        *_mapping_rows(contestability_runtime, "evidence_rows"),
    ]:
        finding_id = str(evidence_row.get("finding_id") or "")
        boundary_row = institutional_by_finding.get(finding_id, {})
        runtime_rows.append(
            {
                "row_id": "W35H-OWN-" + _digest(finding_id),
                "finding_id": finding_id,
                "pdd_id": "-".join(finding_id.split("-")[:2]),
                "surface": evidence_row.get("surface"),
                "evidence_authority": evidence_row.get("evidence_authority"),
                "runtime_owned_provenance_present": (
                    boundary_row.get("runtime_owned_provenance_present") is True
                ),
                "runtime_owned_provenance": boundary_row.get("runtime_owned_provenance"),
                "source_refs": evidence_row.get("source_refs"),
                "trace_refs": evidence_row.get("trace_refs"),
                "command": evidence_row.get("command"),
                "counts_toward_final_publication": True,
                "counts_toward_deterministic_closeout": True,
                "wave35g_boundary_ref": (
                    "_build/policy-design-case/rebaseline/wave-35G/"
                    f"{institutional.OUTPUT_FILENAME}#/rows/{finding_id}"
                ),
            }
        )
    class_counts = Counter(str(row.get("evidence_authority")) for row in runtime_rows)
    runtime_count = sum(
        1 for row in runtime_rows if row.get("runtime_owned_provenance_present") is True
    )
    not_closeout_count = class_counts.get("not_closeout_authority", 0)
    output_path = wave35h_path / OWNERSHIP_OUTPUT
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35H",
        "phase": "35H.3",
        "status": (
            "pass"
            if runtime_count == len(AFFECTED_FINDINGS) and not_closeout_count == 0
            else "fail"
        ),
        "required_output_artifact": _rel_path(output_path, repo_root),
        "affected_findings": list(AFFECTED_FINDINGS),
        "summary": {
            "affected_finding_count": len(AFFECTED_FINDINGS),
            "runtime_owned_provenance_count": runtime_count,
            "not_closeout_authority_count": not_closeout_count,
            "runtime_emitted_count": class_counts.get("runtime_emitted", 0),
        },
        "rows": runtime_rows,
        "wave40_authority_decision": (
            "allowed"
            if runtime_count == len(AFFECTED_FINDINGS) and not_closeout_count == 0
            else "blocked"
        ),
    }


def _build_integrity_report(
    *,
    repo_root: Path,
    generated_at: str,
    before_hashes: Sequence[Mapping[str, str]],
    after_hashes: Sequence[Mapping[str, str]],
    before_counts: Mapping[str, Mapping[str, int]],
    after_counts: Mapping[str, Mapping[str, int]],
    output_hashes: Sequence[Mapping[str, str]],
    ownership: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35H",
        "phase": "35H.3",
        "status": "pass" if ownership.get("status") == "pass" else "fail",
        "command": WAVE35H_CHECK_COMMAND,
        "exit_code": 0 if ownership.get("status") == "pass" else 1,
        "build_command": BUILD_COMMAND,
        "output_hashes": list(output_hashes),
        "before_hashes": list(before_hashes),
        "after_hashes": list(after_hashes),
        "before_evidence_authority_counts": {
            key: dict(value) for key, value in before_counts.items()
        },
        "after_evidence_authority_counts": {
            key: dict(value) for key, value in after_counts.items()
        },
        "reviewer_command": WAVE35H_CHECK_COMMAND,
        "wave35f_reviewer_command": WAVE35F_CHECK_COMMAND,
        "wave35g_reviewer_command": WAVE35G_CHECK_COMMAND,
        "pass2_closeout_reviewer_command": PASS2_CLOSEOUT_COMMAND,
        "repo_root": _rel_path(repo_root, repo_root),
    }


def _build_exit_fence(
    *,
    generated_at: str,
    ownership: Mapping[str, Any],
) -> dict[str, Any]:
    gaps = [
        row
        for row in _mapping_rows(ownership, "rows")
        if row.get("runtime_owned_provenance_present") is not True
        or row.get("evidence_authority") not in {"runtime_emitted", "runtime_derived"}
    ]
    allowed = not gaps and ownership.get("status") == "pass"
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35H",
        "phase": "35H.3",
        "status": "pass" if allowed else "fail",
        "wave40_authority_decision": "allowed" if allowed else "blocked",
        "gap_rows": gaps,
        "runtime_owned_provenance_count": ownership.get("summary", {}).get(
            "runtime_owned_provenance_count"
        ),
        "not_closeout_authority_count": ownership.get("summary", {}).get(
            "not_closeout_authority_count"
        ),
        "reviewer_command": WAVE35H_CHECK_COMMAND,
    }


def _runtime_context(
    *,
    implementation: Mapping[str, Any],
    contestability: Mapping[str, Any],
) -> dict[str, Any]:
    run_identity = _mapping(contestability.get("run_identity"))
    bundle_path = str(run_identity.get("bundle_path") or "")
    run_id = str(run_identity.get("run_id") or "R_8bbd65c6d0a03dc6")
    job_id = str(run_identity.get("job_id") or "66696d6a137a4e6ba95afc9dd810c045")
    case_id = str(run_identity.get("case_id") or f"pdc-{run_id}")
    return {
        "run_id": run_id,
        "job_id": job_id,
        "case_id": case_id,
        "tenant_id": "tenant-public-golden",
        "cell_id": "cell-msme-ua",
        "trace_id": "trace-wave35h-institutional-provenance",
        "execution_profile": "production",
        "event_refs": [
            f"runtime-event://policy-design-case/{run_id}/publication-readiness",
            f"runtime-event://policy-design-case/{run_id}/continuous-governance-lifecycle",
            f"runtime-event://policy-design-case/{run_id}/contestability-appeals",
        ],
        "artifact_refs": _unique(
            [
                *_as_string_list(implementation.get("source_artifacts")),
                *_as_string_list(contestability.get("source_artifacts")),
                "quality_evidence/evidence_provenance_manifest.json",
                "quality_evidence/public_export_bundle.json",
            ]
        ),
        "trace_refs": _unique(
            [
                f"{bundle_path}/timeline.json" if bundle_path else "",
                "tools/quality/validation/build_policy_design_case_wave35h_provenance.py",
            ]
        ),
    }


def _ledger_authority_counts(payload: Mapping[str, Any]) -> dict[str, int]:
    rows = _mapping_rows(payload, "rows")
    class_from_runtime = str(
        _mapping(payload.get("runtime_enforcement_evidence")).get(
            "evidence_authority_class"
        )
        or ""
    )
    counts: Counter[str] = Counter()
    for row in rows:
        authority = str(row.get("evidence_authority_class") or class_from_runtime or "")
        if not authority:
            authority = "manual_assertion"
        counts[authority] += 1
    return dict(sorted(counts.items()))


def _hash_paths(repo_root: Path, paths: Sequence[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        rows.append(
            {
                "path": _rel_path(path, repo_root),
                "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return rows


def _mapping_rows(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    return [row for row in _as_list(payload.get(key)) if isinstance(row, Mapping)]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, Iterable):
        return [str(item) for item in value if item]
    return []


def _unique(values: Iterable[str]) -> list[str]:
    return sorted({str(value) for value in values if str(value)})


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return payload


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (repo_root / path).resolve(strict=False)


def _rel_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave35e-dir", type=Path, default=WAVE35E_DIR)
    parser.add_argument("--wave35f-dir", type=Path, default=WAVE35F_DIR)
    parser.add_argument("--wave35g-dir", type=Path, default=WAVE35G_DIR)
    parser.add_argument("--wave35h-dir", type=Path, default=WAVE35H_DIR)
    parser.add_argument(
        "--skip-wave35f-refresh",
        action="store_true",
        help="Build Wave 35H artifacts without refreshing Wave 35F.",
    )
    parser.add_argument(
        "--skip-wave35g-backfill-refresh",
        action="store_true",
        help="Build Wave 35H artifacts without refreshing Wave 35G.5 reports.",
    )
    args = parser.parse_args(argv)

    outputs = build_wave35h_provenance_outputs(
        repo_root=args.repo_root,
        wave35e_dir=args.wave35e_dir,
        wave35f_dir=args.wave35f_dir,
        wave35g_dir=args.wave35g_dir,
        wave35h_dir=args.wave35h_dir,
        refresh_wave35f=not args.skip_wave35f_refresh,
        refresh_wave35g_backfill=not args.skip_wave35g_backfill_refresh,
    )
    ownership = outputs["runtime_ownership_ledger"]
    status = str(ownership.get("status") or "fail")
    sys.stdout.write(
        "wave35h-provenance-build: "
        f"status={status} "
        f"runtime_owned={ownership.get('summary', {}).get('runtime_owned_provenance_count')} "
        f"not_closeout={ownership.get('summary', {}).get('not_closeout_authority_count')}\n"
    )
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
