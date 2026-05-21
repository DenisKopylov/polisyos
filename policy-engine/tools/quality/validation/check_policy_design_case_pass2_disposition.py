#!/usr/bin/env python3
"""Validate Policy Design Case Wave 35 Pass 2 disposition artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation import build_policy_design_case_pass2_disposition as build

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

DEFAULT_PLAN_PATH = Path(
    "docs/plans/archive/2026-05-19-policyos-policy-design-case-implementation-plan.md"
)
DEFAULT_DECISION_LOG = Path(
    "docs/system-design-decisions/policy-design-case-decision-log.md"
)

REQUIRED_DISPOSITION_FIELDS = (
    "classification",
    "rationale",
    "owner",
    "affected_subsystem",
    "closeout_impact",
    "verification_command",
    "source_evidence",
)

COMMON_REMEDIATION_MARKERS = (
    "Common Remediation Completion Contract For Waves 35A-35E",
    "Disposition update rule",
    "Historical evidence rule",
    "Closeout-ready validator rule",
    "--require-closeout-ready",
)

REMEDIATION_WAVE_MARKERS: dict[str, tuple[str, ...]] = {
    "Wave 35A": (
        "Cluster: `runtime_scenario_variant_coverage`.",
        "Wave 35 finding count: 31.",
        "scenario_variant_inventory.json",
        "cross_domain_runtime_bundles.json",
        "metamorphic_runtime_variants.json",
        "language_equivalence_runtime_pairs.json",
        "hardcoded_language_path_audit.json",
        "phase34_1_rerun.json",
        "build_policy_design_case_pass2_diagnostics.py --phase 34.1",
        "No `runtime_scenario_variant_coverage` disposition remains",
    ),
    "Wave 35B": (
        "Cluster: `adversarial_fail_closed_and_strategic_gates`.",
        "Wave 35 finding count: 12.",
        "adversarial_scenario_matrix.json",
        "cache_index_poisoning_controls.json",
        "cross_component_error_taxonomy.json",
        "strategic_behavior_gate_ledger.json",
        "phase34_2_rerun.json",
        "build_policy_design_case_pass2_diagnostics.py --phase 34.2",
        "No `adversarial_fail_closed_and_strategic_gates` disposition remains",
    ),
    "Wave 35C": (
        "`claim_authority_and_extraction_measurement_binding` and",
        "`semantic_validity_monitoring_and_model_readiness`.",
        "Wave 35 finding count: 22.",
        "claim_authority_binding_ledger.json",
        "extraction_authority_ledger.json",
        "measurement_construct_validity_ledger.json",
        "semantic_validity_model_readiness_ledger.json",
        "phase34_3_rerun.json",
        "phase34_4_rerun.json",
        "run_policy_design_case_pass2_phase34_3.py",
        "run_policy_design_case_pass2_phase34_4.py",
        "No Wave 35C cluster disposition remains",
    ),
    "Wave 35D": (
        "Cluster: `operational_recovery_resource_and_archive_readiness`.",
        "Wave 35 finding count: 29.",
        "operator_root_cause_ledger.json",
        "restore_drill_bundle.json",
        "resource_exhaustion_ledger.json",
        "live_polling_parity_ledger.json",
        "archive_grade_reproducibility_bundle.json",
        "phase34_5_rerun.json",
        "run_policy_design_case_pass2_phase34_5.py",
        "No `operational_recovery_resource_and_archive_readiness` disposition remains",
    ),
    "Wave 35E": (
        "Cluster: `human_facing_legitimacy_memory_and_trust_controls`.",
        "Wave 35 finding count: 19.",
        "projection_operator_truthfulness_matrix.json",
        "memory_authority_ledger.json",
        "implementation_feasibility_ledger.json",
        "contestability_appeals_ledger.json",
        "trust_framing_ui_negative_tests.json",
        "phase34_6_rerun.json",
        "run_policy_design_case_pass2_phase34_6.py",
        "No `human_facing_legitimacy_memory_and_trust_controls` disposition remains",
    ),
    "Wave 35F": (
        "Remediation Integrity And Runtime Enforcement Gate",
        "remediation_integrity_classification.json",
        "runtime_enforcement_gap_ledger.json",
        "wave35e_human_surface_enforcement_audit.json",
        "wave35_runtime_evidence_authority_map.json",
        "wave35f_disposition_integrity_report.json",
        "wave35f_exit_fence.json",
        "check_policy_design_case_wave35f_integrity.py",
        "synthetic_remediation_overlay",
        "manual_assertion",
        "wave36_release_decision=allowed",
    ),
}


def validate_pass2_disposition(
    *,
    repo_root: Path = REPO_ROOT,
    diagnostics_root: Path = build.DEFAULT_DIAGNOSTICS_ROOT,
    output_dir: Path = build.DEFAULT_OUTPUT_DIR,
    plan_path: Path = DEFAULT_PLAN_PATH,
    decision_log_path: Path = DEFAULT_DECISION_LOG,
    require_passing: bool = False,
    require_closeout_ready: bool = False,
) -> list[str]:
    repo_root = repo_root.resolve()
    output_path = _resolve(repo_root, output_dir)
    expected_ledger = build.build_findings_ledger_payload(
        repo_root=repo_root,
        diagnostics_root=diagnostics_root,
    )
    ledger = _load_json(output_path / "pass2_findings_ledger.json")
    clusters = _load_json(output_path / "pass2_root_cause_clusters.json")
    disposition = _load_json(output_path / "pass2_disposition.json")

    errors: list[str] = []
    _validate_ledger(ledger, expected_ledger, errors)
    _validate_clusters(clusters, ledger, errors)
    _validate_disposition(disposition, ledger, clusters, errors)
    _validate_plan_entry_criteria(
        _read_text(_resolve(repo_root, plan_path)),
        errors,
    )
    _validate_decision_log(
        _read_text(_resolve(repo_root, decision_log_path)),
        disposition,
        errors,
    )
    if require_closeout_ready:
        _validate_closeout_ready(disposition, errors)
    if require_passing and disposition.get("status") != "pass":
        errors.append("pass2_disposition.json status must be pass under --require-passing")
    return errors


def _validate_ledger(
    ledger: Mapping[str, Any],
    expected_ledger: Mapping[str, Any],
    errors: list[str],
) -> None:
    if ledger.get("schema_version") != build.SCHEMA_VERSION:
        errors.append("findings ledger schema_version drifted")
    expected_details = {
        str(row.get("pdd_id"))
        for row in _as_list(expected_ledger.get("pdd_detail_artifacts"))
        if isinstance(row, Mapping)
    }
    observed_details = {
        str(row.get("pdd_id"))
        for row in _as_list(ledger.get("pdd_detail_artifacts"))
        if isinstance(row, Mapping)
    }
    if observed_details != expected_details:
        errors.append(
            "findings ledger does not represent every Wave 34 detail artifact: "
            f"missing={sorted(expected_details - observed_details)} "
            f"extra={sorted(observed_details - expected_details)}"
        )

    expected_phase_count = int(
        expected_ledger.get("summary", {}).get("phase_index_count") or 0
    )
    observed_phase_count = len(_as_list(ledger.get("phase_indexes")))
    if observed_phase_count != expected_phase_count:
        errors.append(
            f"findings ledger phase index count mismatch: {observed_phase_count} "
            f"!= {expected_phase_count}"
        )

    expected_ids = _finding_ids(expected_ledger)
    observed_ids = _finding_ids(ledger)
    if observed_ids != expected_ids:
        errors.append(
            "findings ledger finding ids do not match current Wave 34 artifacts: "
            f"missing={sorted(expected_ids - observed_ids)} "
            f"extra={sorted(observed_ids - expected_ids)}"
        )

    for row in _as_list(ledger.get("findings")):
        if not isinstance(row, Mapping):
            errors.append("findings ledger contains a non-object finding row")
            continue
        for field in (
            "finding_id",
            "finding_code",
            "severity",
            "pdd_id",
            "phase",
            "source_artifact",
            "phase_index_artifact",
            "source_evidence",
            "recommended_gate",
        ):
            if not _present(row.get(field)):
                errors.append(f"{row.get('finding_id', '<unknown>')}: missing {field}")


def _validate_clusters(
    clusters: Mapping[str, Any],
    ledger: Mapping[str, Any],
    errors: list[str],
) -> None:
    if clusters.get("schema_version") != build.SCHEMA_VERSION:
        errors.append("root-cause clusters schema_version drifted")
    finding_ids = _finding_ids(ledger)
    covered: list[str] = []
    for cluster in _as_list(clusters.get("clusters")):
        if not isinstance(cluster, Mapping):
            errors.append("root-cause clusters contains a non-object cluster")
            continue
        cluster_id = str(cluster.get("cluster_id") or "")
        for field in (
            "owner",
            "affected_subsystem",
            "root_capability_gap",
            "shared_remediation_surface",
            "target_plan_wave",
            "verification_command",
            "revisit_trigger",
            "finding_ids",
        ):
            if not _present(cluster.get(field)):
                errors.append(f"{cluster_id}: missing cluster field {field}")
        covered.extend(str(item) for item in _as_list(cluster.get("finding_ids")))
    covered_counts = Counter(covered)
    duplicate_ids = sorted(
        finding_id for finding_id, count in covered_counts.items() if count != 1
    )
    if set(covered) != finding_ids or duplicate_ids:
        errors.append(
            "root-cause clusters must cover every finding exactly once: "
            f"missing={sorted(finding_ids - set(covered))} "
            f"extra={sorted(set(covered) - finding_ids)} duplicates={duplicate_ids}"
        )


def _validate_disposition(
    disposition: Mapping[str, Any],
    ledger: Mapping[str, Any],
    clusters: Mapping[str, Any],
    errors: list[str],
) -> None:
    if disposition.get("schema_version") != build.SCHEMA_VERSION:
        errors.append("disposition schema_version drifted")
    finding_ids = _finding_ids(ledger)
    disposition_rows = [
        row for row in _as_list(disposition.get("dispositions")) if isinstance(row, Mapping)
    ]
    disposition_ids = [
        str(row.get("finding_id"))
        for row in disposition_rows
        if _present(row.get("finding_id"))
    ]
    disposition_counts = Counter(disposition_ids)
    duplicate_ids = sorted(
        finding_id for finding_id, count in disposition_counts.items() if count != 1
    )
    if set(disposition_ids) != finding_ids or duplicate_ids:
        errors.append(
            "every Wave 34 finding must have exactly one disposition: "
            f"missing={sorted(finding_ids - set(disposition_ids))} "
            f"extra={sorted(set(disposition_ids) - finding_ids)} "
            f"duplicates={duplicate_ids}"
        )

    cluster_ids = {
        str(cluster.get("cluster_id"))
        for cluster in _as_list(clusters.get("clusters"))
        if isinstance(cluster, Mapping)
    }
    unresolved_must_fix: list[str] = []
    for row in disposition_rows:
        finding_id = str(row.get("finding_id") or "<unknown>")
        classification = str(row.get("classification") or "")
        if classification not in build.ALLOWED_CLASSIFICATIONS:
            errors.append(f"{finding_id}: invalid classification {classification!r}")
        for field in REQUIRED_DISPOSITION_FIELDS:
            if not _present(row.get(field)):
                errors.append(f"{finding_id}: disposition missing {field}")
        cluster_id = str(row.get("root_cause_cluster_id") or "")
        if cluster_id not in cluster_ids:
            errors.append(f"{finding_id}: unknown root_cause_cluster_id {cluster_id!r}")
        if classification == "must_fix_before_closeout":
            evidence = row.get("remediation_evidence")
            if not isinstance(evidence, Mapping) or evidence.get("status") != "resolved":
                unresolved_must_fix.append(finding_id)
        elif classification == "accepted_blocker":
            _validate_deferral_fields(row, "accepted_blocker_evidence", finding_id, errors)
        elif classification == "next_plan_remediation":
            _validate_deferral_fields(row, "deferral_evidence", finding_id, errors)
        elif classification == "false_alarm_with_evidence":
            if not _present(row.get("false_alarm_evidence")):
                errors.append(f"{finding_id}: missing false_alarm_evidence")
    if unresolved_must_fix:
        errors.append(
            "must_fix_before_closeout findings remain unresolved: "
            + ", ".join(unresolved_must_fix)
        )

    expected_zero_pdds = {
        str(row.get("pdd_id"))
        for row in _as_list(ledger.get("pdd_detail_artifacts"))
        if isinstance(row, Mapping) and int(row.get("finding_count") or 0) == 0
    }
    artifact_rows = [
        row
        for row in _as_list(disposition.get("artifact_dispositions"))
        if isinstance(row, Mapping)
    ]
    observed_zero_pdds = {str(row.get("pdd_id")) for row in artifact_rows}
    if observed_zero_pdds != expected_zero_pdds:
        errors.append(
            "zero-finding Wave 34 detail artifacts need artifact dispositions: "
            f"missing={sorted(expected_zero_pdds - observed_zero_pdds)} "
            f"extra={sorted(observed_zero_pdds - expected_zero_pdds)}"
        )
    for row in artifact_rows:
        pdd_id = str(row.get("pdd_id") or "<unknown>")
        for field in REQUIRED_DISPOSITION_FIELDS:
            if not _present(row.get(field)):
                errors.append(f"{pdd_id}: artifact disposition missing {field}")
        if row.get("classification") != "false_alarm_with_evidence":
            errors.append(f"{pdd_id}: zero-finding artifact must be false_alarm_with_evidence")
        if not _present(row.get("false_alarm_evidence")):
            errors.append(f"{pdd_id}: artifact disposition missing false_alarm_evidence")


def _validate_deferral_fields(
    row: Mapping[str, Any],
    evidence_field: str,
    finding_id: str,
    errors: list[str],
) -> None:
    if not _present(row.get(evidence_field)):
        errors.append(f"{finding_id}: missing {evidence_field}")
    target = str(row.get("target_plan_wave") or "")
    if not target.startswith("Wave 35"):
        errors.append(f"{finding_id}: target_plan_wave must occur before Wave 36")
    if not _present(row.get("revisit_trigger")):
        errors.append(f"{finding_id}: missing revisit_trigger")


def _validate_plan_entry_criteria(plan_text: str, errors: list[str]) -> None:
    for marker in COMMON_REMEDIATION_MARKERS:
        if marker not in plan_text:
            errors.append(f"Wave 35A-35E remediation contract missing marker: {marker}")

    for wave_id, markers in REMEDIATION_WAVE_MARKERS.items():
        section = _section(plan_text, f"## {wave_id}", f"## {_next_wave_id(wave_id)}")
        if not section:
            errors.append(f"{wave_id}: missing remediation wave section")
            continue
        if section.count(f"### Phase {wave_id.removeprefix('Wave ')}.1") != 1:
            errors.append(f"{wave_id}: must have exactly one phase")
        for marker in markers:
            if marker not in section:
                errors.append(f"{wave_id}: remediation wave spec missing marker: {marker}")

    wave36 = _section(plan_text, "## Wave 36", "## Wave 37")
    required_markers = (
        "Wave 36 Entry Criteria",
        "Wave 35A",
        "Wave 35E",
        "Wave 35F",
        "Wave 35G",
        "_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json",
        "_build/policy-design-case/rebaseline/wave-35F/wave35f_exit_fence.json",
        "_build/policy-design-case/rebaseline/wave-35G/wave35g_exit_fence.json",
        "check_policy_design_case_pass2_disposition.py --repo-root . --require-passing",
        "--require-closeout-ready",
        "check_policy_design_case_wave35f_integrity.py --repo-root .",
        "check_policy_design_case_wave35g_backfill.py --repo-root .",
    )
    for marker in required_markers:
        if marker not in wave36:
            errors.append(f"Wave 36 entry criteria missing marker: {marker}")


def _validate_decision_log(
    decision_log_text: str,
    disposition: Mapping[str, Any],
    errors: list[str],
) -> None:
    rows = [
        row for row in _as_list(disposition.get("dispositions")) if isinstance(row, Mapping)
    ]
    needed_clusters = {
        str(row.get("root_cause_cluster_id"))
        for row in rows
        if row.get("classification") in {"accepted_blocker", "next_plan_remediation"}
    }
    inserted = {
        cluster_id: str(wave.get("wave"))
        for wave in _as_list(
            disposition.get("plan_wave_impact", {}).get("inserted_remediation_waves")
        )
        if isinstance(wave, Mapping)
        for cluster_id in _as_list(wave.get("cluster_ids"))
    }
    for cluster_id in sorted(needed_clusters):
        target_wave = inserted.get(cluster_id, "")
        if cluster_id not in decision_log_text:
            errors.append(f"decision log missing Wave 35 cluster entry for {cluster_id}")
        if target_wave and target_wave not in decision_log_text:
            errors.append(f"decision log missing target wave {target_wave} for {cluster_id}")


def _validate_closeout_ready(
    disposition: Mapping[str, Any],
    errors: list[str],
) -> None:
    unresolved = [
        str(row.get("finding_id"))
        for row in _as_list(disposition.get("dispositions"))
        if isinstance(row, Mapping)
        and row.get("classification") in {"accepted_blocker", "next_plan_remediation"}
    ]
    if unresolved:
        errors.append(
            "--require-closeout-ready forbids unresolved accepted blockers or "
            f"next-plan remediations: count={len(unresolved)}"
        )


def _next_wave_id(wave_id: str) -> str:
    order = ("Wave 35A", "Wave 35B", "Wave 35C", "Wave 35D", "Wave 35E", "Wave 35F")
    try:
        return order[order.index(wave_id) + 1]
    except (ValueError, IndexError):
        return "Wave 36"


def _finding_ids(payload: Mapping[str, Any]) -> set[str]:
    return {
        str(row.get("finding_id"))
        for row in _as_list(payload.get("findings"))
        if isinstance(row, Mapping) and _present(row.get("finding_id"))
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return payload


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _section(source: str, start_marker: str, end_marker: str) -> str:
    start = source.find(start_marker)
    if start < 0:
        return ""
    end = source.find(end_marker, start + len(start_marker))
    return source[start:] if end < 0 else source[start:end]


def _resolve(repo_root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else repo_root / path
    return candidate.resolve(strict=False)


def _present(value: object) -> bool:
    return value not in (None, "", [], {})


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--diagnostics-root",
        type=Path,
        default=build.DEFAULT_DIAGNOSTICS_ROOT,
    )
    parser.add_argument("--output-dir", type=Path, default=build.DEFAULT_OUTPUT_DIR)
    parser.add_argument("--plan-path", type=Path, default=DEFAULT_PLAN_PATH)
    parser.add_argument("--decision-log", type=Path, default=DEFAULT_DECISION_LOG)
    parser.add_argument("--require-passing", action="store_true")
    parser.add_argument("--require-closeout-ready", action="store_true")
    args = parser.parse_args(argv)

    try:
        errors = validate_pass2_disposition(
            repo_root=args.repo_root,
            diagnostics_root=args.diagnostics_root,
            output_dir=args.output_dir,
            plan_path=args.plan_path,
            decision_log_path=args.decision_log,
            require_passing=args.require_passing,
            require_closeout_ready=args.require_closeout_ready,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        errors = [str(exc)]

    if errors:
        for error in errors:
            sys.stderr.write(f"pass2-disposition: {error}\n")
        sys.stderr.write(f"pass2-disposition: failed with {len(errors)} issue(s)\n")
        return 1
    sys.stdout.write("pass2-disposition: pass\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
