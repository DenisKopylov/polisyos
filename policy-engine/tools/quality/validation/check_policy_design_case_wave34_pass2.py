#!/usr/bin/env python3
"""Validate Policy Design Case Wave 34 Pass 2 diagnostic closeout."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

EXPECTED_PHASES: dict[str, dict[str, Any]] = {
    "34.1": {
        "index": "phase34_1_cross_domain_metamorphic_diagnostics.json",
        "pdds": {
            "PDD-037": "cross_domain_generality_diagnostic_matrix",
            "PDD-055": "metamorphic_policy_diagnostic_suite",
            "PDD-056": "multilingual_transliteration_equivalence_audit",
        },
    },
    "34.2": {
        "index": "phase34_2_adversarial_fail_closed_diagnostics.json",
        "pdds": {
            "PDD-038": "adversarial_fail_closed_diagnostics",
            "PDD-064": "cache_index_snapshot_poisoning_audit",
            "PDD-065": "cross_component_error_semantics_audit",
            "PDD-098": "strategic_behavior_binding_audit",
        },
    },
    "34.3": {
        "index": "phase_34_3_claim_grounding_validity_index.json",
        "pdds": {
            "PDD-044": "final_artifact_section_grounding_audit",
            "PDD-048": "institutional_competence_authority_audit",
            "PDD-050": "external_validity_transferability_audit",
            "PDD-051": "uncertainty_propagation_chain_audit",
            "PDD-057": "final_decision_monitoring_claim_binding_audit",
            "PDD-087": "model_registry_readiness_binding_audit",
            "PDD-088": "berl_explanation_reliability_binding_audit",
        },
    },
    "34.4": {
        "index": "phase_34_4_extraction_measurement_diagnostics.json",
        "pdds": {
            "PDD-100": "document_extraction_authority_audit",
            "PDD-101": "survey_measurement_construct_validity_audit",
        },
    },
    "34.5": {
        "index": "phase_34_5_operational_recovery_diagnostics.json",
        "pdds": {
            "PDD-046": "operational_root_cause_completeness_audit",
            "PDD-077": "backup_restore_drill_evidence_audit",
            "PDD-078": "resource_exhaustion_semantics_audit",
            "PDD-090": "realtime_cursor_replay_polling_parity_audit",
            "PDD-104": "archive_grade_reproducibility_audit",
        },
    },
    "34.6": {
        "index": "phase_34_6_human_facing_legitimacy_memory_diagnostics.json",
        "pdds": {
            "PDD-034": "dashboard_api_projection_consistency_audit",
            "PDD-069": "dashboard_operator_truthfulness_audit",
            "PDD-083": "reusable_agent_memory_reflexion_applicability_audit",
            "PDD-097": "implementation_feasibility_beyond_final_text_audit",
            "PDD-099": "public_contestability_appeals_legitimacy_audit",
            "PDD-103": "human_overtrust_ui_persuasion_risk_audit",
        },
    },
}

REQUIRED_DETAIL_FIELDS: tuple[str, ...] = (
    "schema_version",
    "tool",
    "generated_at",
    "wave",
    "phase",
    "pdd_id",
    "title",
    "question",
    "diagnostic_status",
    "acceptance_gate_status",
    "verdict",
    "wave33",
    "source_artifacts",
    "findings",
    "recommended_gate",
    "backlog_summary",
)

SAME_WAVE_DEPENDENCY_MARKERS: tuple[str, ...] = (
    "_build/diagnostics/pass2/phase",
    "_build/diagnostics/pass2/phase34",
    "_build/diagnostics/pdd-",
)


def validate_wave34_pass2(
    *,
    repo_root: Path = REPO_ROOT,
    diagnostics_root: Path = Path("_build/diagnostics"),
) -> list[str]:
    repo_root = repo_root.resolve()
    diagnostics_root = _resolve(repo_root, diagnostics_root)
    errors: list[str] = []
    expected_count = sum(len(phase["pdds"]) for phase in EXPECTED_PHASES.values())
    seen: set[str] = set()

    for phase, spec in EXPECTED_PHASES.items():
        index_path = diagnostics_root / "pass2" / str(spec["index"])
        index_md_path = index_path.with_suffix(".md")
        index_payload = _load_json(index_path, errors)
        if not index_md_path.exists():
            errors.append(f"{phase}: missing phase markdown index: {index_md_path}")
        if index_payload:
            _validate_phase_index(index_payload, phase, spec, errors)

        for pdd_id, slug in spec["pdds"].items():
            seen.add(pdd_id)
            detail_json = diagnostics_root / pdd_id.lower() / f"{slug}.json"
            detail_md = diagnostics_root / pdd_id.lower() / f"{slug}.md"
            summary_md = diagnostics_root / pdd_id.lower() / "summary.md"
            fragment_md = (
                diagnostics_root / "pass2" / "backlog_fragments" / f"{pdd_id.lower()}.md"
            )
            for path, label in (
                (detail_json, "detail JSON"),
                (detail_md, "detail Markdown"),
                (summary_md, "summary Markdown"),
                (fragment_md, "backlog fragment"),
            ):
                if not path.exists():
                    errors.append(f"{pdd_id}: missing {label}: {path}")
            detail = _load_json(detail_json, errors)
            if detail:
                _validate_detail(detail, pdd_id, phase, errors)

    if len(seen) != expected_count:
        errors.append(
            f"expected {expected_count} PDD ids but validated {len(seen)} unique ids"
        )
    return errors


def _validate_phase_index(
    payload: Mapping[str, Any],
    phase: str,
    spec: Mapping[str, Any],
    errors: list[str],
) -> None:
    if payload.get("wave") != "34":
        errors.append(f"{phase}: phase index wave must be '34'")
    if payload.get("phase") != phase:
        errors.append(f"{phase}: phase index phase mismatch: {payload.get('phase')}")
    if payload.get("status") != "diagnosed":
        errors.append(f"{phase}: phase index status must be 'diagnosed'")
    if not payload.get("schema_version"):
        errors.append(f"{phase}: phase index missing schema_version")
    if not payload.get("tool"):
        errors.append(f"{phase}: phase index missing tool")
    members = payload.get("diagnostics") or payload.get("pdds") or {}
    if not isinstance(members, Mapping):
        errors.append(f"{phase}: phase index diagnostics/pdds must be an object")
        return
    for pdd_id in spec["pdds"]:
        if pdd_id not in members:
            errors.append(f"{phase}: phase index missing {pdd_id}")
    _validate_wave33(payload.get("wave33") or payload.get("observed_wave33_case"), phase, errors)


def _validate_detail(
    payload: Mapping[str, Any],
    pdd_id: str,
    phase: str,
    errors: list[str],
) -> None:
    for field in REQUIRED_DETAIL_FIELDS:
        if field not in payload or payload.get(field) in (None, ""):
            errors.append(f"{pdd_id}: missing required field {field}")
    if payload.get("wave") != "34":
        errors.append(f"{pdd_id}: wave must be '34', got {payload.get('wave')!r}")
    if payload.get("phase") != phase:
        errors.append(f"{pdd_id}: phase must be {phase}, got {payload.get('phase')!r}")
    if payload.get("pdd_id") != pdd_id:
        errors.append(f"{pdd_id}: pdd_id mismatch: {payload.get('pdd_id')!r}")
    if payload.get("diagnostic_status") != "diagnosed":
        errors.append(f"{pdd_id}: diagnostic_status must be diagnosed")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        errors.append(f"{pdd_id}: findings must be a list")
    elif not findings and not _allowed_empty_findings(payload, pdd_id):
        errors.append(f"{pdd_id}: findings must be non-empty")
    gate = str(payload.get("acceptance_gate_status") or "")
    if pdd_id == "PDD-088":
        if gate != "not_triggered_no_explanation_support_detected":
            errors.append(
                "PDD-088: not-triggered allowance requires "
                "not_triggered_no_explanation_support_detected"
            )
    elif gate.startswith("not_triggered"):
        errors.append(f"{pdd_id}: unexpected not_triggered gate")
    _validate_wave33(payload.get("wave33"), pdd_id, errors)
    source_artifacts = payload.get("source_artifacts")
    if not isinstance(source_artifacts, Mapping):
        errors.append(f"{pdd_id}: source_artifacts must be an object")
    elif not source_artifacts.get("real_domain_baseline"):
        errors.append(f"{pdd_id}: source_artifacts missing real_domain_baseline")
    _validate_no_same_wave_dependency(payload, pdd_id, errors)


def _validate_wave33(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, Mapping):
        errors.append(f"{label}: missing Wave 33 provenance object")
        return
    for field in ("run_id", "job_id", "bundle_path"):
        if not value.get(field):
            errors.append(f"{label}: wave33 missing {field}")


def _validate_no_same_wave_dependency(
    payload: Mapping[str, Any],
    pdd_id: str,
    errors: list[str],
) -> None:
    scanned = {
        "source_artifacts": payload.get("source_artifacts"),
        "wave33": payload.get("wave33"),
        "wave33_evidence": payload.get("wave33_evidence"),
        "wave_33_evidence": payload.get("wave_33_evidence"),
        "input_evidence": payload.get("input_evidence"),
    }
    for path, value in _walk_strings(scanned):
        text = value.replace("\\", "/")
        if any(marker in text for marker in SAME_WAVE_DEPENDENCY_MARKERS):
            errors.append(
                f"{pdd_id}: same-wave diagnostic dependency in {'.'.join(path)}: {value}"
            )


def _allowed_empty_findings(payload: Mapping[str, Any], pdd_id: str) -> bool:
    if pdd_id != "PDD-088":
        return False
    if payload.get("acceptance_gate_status") != "not_triggered_no_explanation_support_detected":
        return False
    evidence = payload.get("evidence")
    if not isinstance(evidence, Mapping):
        return False
    refs = evidence.get("berl_or_explanation_refs_detected")
    if isinstance(refs, list) and not refs:
        return True
    rendered = json.dumps(evidence, sort_keys=True)
    return "explanation" in rendered.lower() and "support" in rendered.lower()


def _walk_strings(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], str]]:
    strings: list[tuple[tuple[str, ...], str]] = []
    if isinstance(value, str):
        strings.append((path, value))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            strings.extend(_walk_strings(item, (*path, str(key))))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            strings.extend(_walk_strings(item, (*path, str(index))))
    return strings


def _load_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.exists():
        errors.append(f"missing JSON file: {path}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON {path}: {exc.msg}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"JSON file must contain an object: {path}")
        return None
    return payload


def _resolve(repo_root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else repo_root / path
    return candidate.resolve(strict=False)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--diagnostics-root",
        type=Path,
        default=Path("_build/diagnostics"),
    )
    args = parser.parse_args(argv)

    errors = validate_wave34_pass2(
        repo_root=args.repo_root,
        diagnostics_root=args.diagnostics_root,
    )
    if errors:
        for error in errors:
            sys.stderr.write(f"wave34-pass2: {error}\n")
        sys.stderr.write(f"wave34-pass2: failed with {len(errors)} issue(s)\n")
        return 1
    sys.stdout.write("wave34-pass2: pass\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
