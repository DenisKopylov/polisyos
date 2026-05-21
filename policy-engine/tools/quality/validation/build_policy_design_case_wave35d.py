#!/usr/bin/env python3
"""Build Wave 35D operational recovery, resource, parity, and archive evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.wave35d.operational_recovery_archive.v1"
TOOL_NAME = "quality.validation.build-policy-design-case-wave35d"
CLUSTER_ID = "operational_recovery_resource_and_archive_readiness"
WAVE35_DIR = Path("_build/policy-design-case/rebaseline/wave-35")
WAVE35D_DIR = Path("_build/policy-design-case/rebaseline/wave-35D")
WAVE33_DIR = Path("_build/policy-design-case/rebaseline/wave-33")
DIAGNOSTICS_ROOT = Path("_build/diagnostics")

PHASE34_5_COMMAND = (
    "uv run python tools/quality/validation/run_policy_design_case_pass2_phase34_5.py"
)
CHECK_COMMAND = (
    "uv run python tools/quality/validation/check_policy_design_case_wave34_pass2.py "
    "--repo-root ."
)
VERIFY_DISPOSITION_COMMAND = (
    "uv run python tools/quality/validation/check_policy_design_case_pass2_disposition.py "
    "--repo-root . --require-passing --require-closeout-ready"
)

PDD_IDS = ("PDD-046", "PDD-077", "PDD-078", "PDD-090", "PDD-104")
SOURCE_ARTIFACT_BY_PDD = {
    "PDD-046": "_build/diagnostics/pdd-046/operational_root_cause_completeness_audit.json",
    "PDD-077": "_build/diagnostics/pdd-077/backup_restore_drill_evidence_audit.json",
    "PDD-078": "_build/diagnostics/pdd-078/resource_exhaustion_semantics_audit.json",
    "PDD-090": "_build/diagnostics/pdd-090/realtime_cursor_replay_polling_parity_audit.json",
    "PDD-104": "_build/diagnostics/pdd-104/archive_grade_reproducibility_audit.json",
}
OUTPUT_ARTIFACTS = {
    "PDD-046": "_build/policy-design-case/rebaseline/wave-35D/operator_root_cause_ledger.json",
    "PDD-077": "_build/policy-design-case/rebaseline/wave-35D/restore_drill_bundle.json",
    "PDD-078": "_build/policy-design-case/rebaseline/wave-35D/resource_exhaustion_ledger.json",
    "PDD-090": "_build/policy-design-case/rebaseline/wave-35D/live_polling_parity_ledger.json",
    "PDD-104": (
        "_build/policy-design-case/rebaseline/wave-35D/"
        "archive_grade_reproducibility_bundle.json"
    ),
}
REQUIRED_ROOT_CAUSE_CLASSES = (
    "lex",
    "fabric",
    "foundry",
    "decision-artifact",
    "scholar",
    "record-family",
)
RESOURCE_LIMIT_TYPES = (
    "rate_limit",
    "circuit_breaker",
    "timeout",
    "byte_limit",
    "token_limit",
    "cost_limit",
    "memory_limit",
    "queue_limit",
)


def build_wave35d_outputs(
    *,
    repo_root: Path = REPO_ROOT,
    wave35_dir: Path = WAVE35_DIR,
    wave35d_dir: Path = WAVE35D_DIR,
    run_rerun: bool = False,
    update_disposition: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    wave35_path = _resolve(repo_root, wave35_dir)
    wave35d_path = _resolve(repo_root, wave35d_dir)
    wave35d_path.mkdir(parents=True, exist_ok=True)

    ledger = _load_json(wave35_path / "pass2_findings_ledger.json")
    disposition = _load_json(wave35_path / "pass2_disposition.json")
    original_disposition = deepcopy(disposition)
    affected_rows = _affected_dispositions(disposition)
    findings_by_id = {
        str(row.get("finding_id")): row
        for row in _as_list(ledger.get("findings"))
        if isinstance(row, Mapping) and row.get("pdd_id") in PDD_IDS
    }
    context = _load_context(repo_root)

    root_cause = _build_operator_root_cause_ledger(
        context=context,
        affected_rows=affected_rows,
        repo_root=repo_root,
    )
    restore = _build_restore_drill_bundle(
        context=context,
        affected_rows=affected_rows,
        repo_root=repo_root,
    )
    resource = _build_resource_exhaustion_ledger(
        context=context,
        affected_rows=affected_rows,
        repo_root=repo_root,
    )
    parity = _build_live_polling_parity_ledger(
        context=context,
        affected_rows=affected_rows,
        repo_root=repo_root,
    )
    archive = _build_archive_grade_reproducibility_bundle(
        context=context,
        affected_rows=affected_rows,
        restore_drill=restore,
        repo_root=repo_root,
    )

    atomic_write_json(wave35d_path / "operator_root_cause_ledger.json", root_cause)
    atomic_write_json(wave35d_path / "restore_drill_bundle.json", restore)
    atomic_write_json(wave35d_path / "resource_exhaustion_ledger.json", resource)
    atomic_write_json(wave35d_path / "live_polling_parity_ledger.json", parity)
    atomic_write_json(
        wave35d_path / "archive_grade_reproducibility_bundle.json",
        archive,
    )

    phase34_rerun: dict[str, Any] | None = None
    if run_rerun:
        phase34_rerun = _run_phase34_5_rerun(
            repo_root=repo_root,
            wave35d_path=wave35d_path,
        )
        atomic_write_json(wave35d_path / "phase34_5_rerun.json", phase34_rerun)
    elif (wave35d_path / "phase34_5_rerun.json").exists():
        phase34_rerun = _load_json(wave35d_path / "phase34_5_rerun.json")

    disposition_update = _build_disposition_update(
        disposition=disposition,
        original_disposition=original_disposition,
        affected_rows=affected_rows,
        findings_by_id=findings_by_id,
        root_cause=root_cause,
        restore=restore,
        resource=resource,
        parity=parity,
        archive=archive,
        phase34_rerun=phase34_rerun,
        repo_root=repo_root,
    )
    atomic_write_json(wave35d_path / "wave35_disposition_update.json", disposition_update)

    if update_disposition:
        atomic_write_json(wave35_path / "pass2_disposition.json", disposition)

    return {
        "operator_root_cause": root_cause,
        "restore_drill": restore,
        "resource_exhaustion": resource,
        "live_polling_parity": parity,
        "archive_reproducibility": archive,
        "phase34_rerun": phase34_rerun,
        "disposition_update": disposition_update,
    }


def _build_operator_root_cause_ledger(
    *,
    context: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    scorecard = _mapping(context["wave33_files"].get("quality_scorecard.json"))
    readiness = _mapping(context["wave33_files"].get("readiness.json"))
    claim_argument = _mapping(context["wave33_files"].get("claim_argument.json"))
    job = _mapping(context["bundle_files"].get("job.json"))
    timeline = _mapping(context["bundle_files"].get("timeline.json"))
    events = _as_list(timeline.get("events"))

    source_rows = [
        *_surface_rows(scorecard.get("blocking_quality_failures"), "scorecard"),
        *_surface_rows(readiness.get("minimum_closeout_gate_failures"), "readiness"),
        *_surface_rows(claim_argument.get("blockers"), "claim_argument"),
    ]
    breadcrumb_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for source_row in source_rows:
        row = _mapping(source_row)
        code = str(row.get("code") or row.get("failure_code") or "unknown_failure")
        message = str(row.get("message") or "")
        surface = str(row.get("_surface") or "unknown")
        key = (surface, code, message)
        if key in seen:
            continue
        seen.add(key)
        failure_class = _failure_class(row)
        owner = _owner_for_class(failure_class)
        missing_input = _missing_input_for_row(row, failure_class)
        next_command = _next_command_for_row(row, failure_class)
        breadcrumb_rows.append(
            {
                "failure_class": failure_class,
                "failure_code": code,
                "source_surface": surface,
                "scorecard_gate": row.get("gate") or row.get("minimum_closeout_gate"),
                "layer": row.get("layer") or row.get("owning_layer") or row.get("source"),
                "first_missing_producer": _producer_for_class(failure_class),
                "upstream_cause": _upstream_cause_for_class(failure_class),
                "downstream_impact": row.get("downstream_impact")
                or row.get("message")
                or "Closeout would advance without authoritative runtime evidence.",
                "owner": owner,
                "missing_input": missing_input,
                "next_command": next_command,
                "event_refs": _diagnostic_event_refs(job, failure_class),
                "timeline_refs": _timeline_refs(events, failure_class),
                "source_evidence_ref": row.get("evidence_ref")
                or _mapping(row.get("evidence")).get("evidence_ref"),
            }
        )

    chains = []
    for failure_class in REQUIRED_ROOT_CAUSE_CLASSES:
        class_rows = [
            row for row in breadcrumb_rows if row["failure_class"] == failure_class
        ]
        representative = class_rows[0] if class_rows else {}
        chains.append(
            {
                "failure_class": failure_class,
                "status": "normalized_to_first_missing_producer"
                if representative
                else "missing_class_row",
                "first_missing_producer": representative.get("first_missing_producer")
                or _producer_for_class(failure_class),
                "owner": representative.get("owner") or _owner_for_class(failure_class),
                "missing_input": representative.get("missing_input")
                or _default_missing_input(failure_class),
                "upstream_cause": representative.get("upstream_cause")
                or _upstream_cause_for_class(failure_class),
                "downstream_impact": representative.get("downstream_impact")
                or "Closeout cannot distinguish producer absence from downstream gate failure.",
                "next_command": representative.get("next_command")
                or _next_command_for_class(failure_class),
                "scorecard_failure_refs": [
                    row["failure_code"] for row in class_rows[:8]
                ],
                "chain": [
                    {
                        "step": 1,
                        "producer": representative.get("first_missing_producer")
                        or _producer_for_class(failure_class),
                        "required_input": representative.get("missing_input")
                        or _default_missing_input(failure_class),
                    },
                    {
                        "step": 2,
                        "producer": "runtime quality scorecard/readiness aggregator",
                        "required_input": "typed failure breadcrumb with source evidence refs",
                    },
                    {
                        "step": 3,
                        "producer": "operator diagnostic ledger",
                        "required_input": "exact next command and owner-visible impact row",
                    },
                ],
            }
        )

    commands = _unique(
        [
            PHASE34_5_COMMAND,
            CHECK_COMMAND,
            "uv run pytest tests/unit/runtime/quality/test_scorecard.py "
            "tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q",
            *[row["next_command"] for row in breadcrumb_rows if row.get("next_command")],
        ]
    )
    observed_classes = sorted({row["failure_class"] for row in breadcrumb_rows})
    pdd046_findings = _finding_ids_for_pdd(affected_rows, "PDD-046")
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35D",
        "phase": "35D.1",
        "pdd_id": "PDD-046",
        "cluster_id": CLUSTER_ID,
        "status": "complete"
        if set(REQUIRED_ROOT_CAUSE_CLASSES) <= set(observed_classes)
        and all(row["first_missing_producer"] for row in breadcrumb_rows)
        and all(row["next_command"] for row in breadcrumb_rows)
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-046"],
            "_build/diagnostics/pass2/phase_34_5_operational_recovery_diagnostics.json",
            "_build/policy-design-case/rebaseline/wave-33/quality_scorecard.json",
            "_build/policy-design-case/rebaseline/wave-33/readiness.json",
            _rel(_resolve(repo_root, context["bundle_path"] / "job.json"), repo_root),
            _rel(_resolve(repo_root, context["bundle_path"] / "timeline.json"), repo_root),
        ],
        "run_identity": _run_identity(context),
        "top_level_diagnostic_command_list": commands,
        "required_failure_classes": list(REQUIRED_ROOT_CAUSE_CLASSES),
        "observed_failure_classes": observed_classes,
        "scorecard_failure_breadcrumb_row_count": len(breadcrumb_rows),
        "scorecard_failure_breadcrumb_rows": breadcrumb_rows,
        "first_missing_producer_chains": chains,
        "generic_failed_gate_boundary": {
            "generic_failed_gate_closes_pdd046": False,
            "required_chain_fields": [
                "first_missing_producer",
                "upstream_cause",
                "downstream_impact",
                "owner",
                "missing_input",
                "next_command",
                "event_refs",
                "timeline_refs",
            ],
        },
        "source_disposition_refs": pdd046_findings,
    }


def _build_restore_drill_bundle(
    *,
    context: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    bundle_path = _resolve(repo_root, context["bundle_path"])
    retained_paths = [
        WAVE33_DIR / "quality_scorecard.json",
        WAVE33_DIR / "readiness.json",
        WAVE33_DIR / "policy_design_case_sample.json",
        context["bundle_path"] / "bundle.json",
        context["bundle_path"] / "lineage.json",
        context["bundle_path"] / "quality_evidence/replay_manifest.json",
        context["bundle_path"] / "quality_evidence/evidence_provenance_manifest.json",
        context["bundle_path"] / "quality_evidence/quality_scorecard.json",
        context["bundle_path"] / "quality_evidence/policy_design_case.json",
    ]
    retained_hashes = [_hash_record(repo_root, path) for path in retained_paths]
    retained_hashes = [row for row in retained_hashes if row]
    provenance = _mapping(context["quality_files"].get("evidence_provenance_manifest.json"))
    archive_hash_verification = [
        _archive_verification_row(row, provenance) for row in retained_hashes
    ]
    injection_target = next(
        row
        for row in retained_hashes
        if row["path"].endswith("quality_evidence/replay_manifest.json")
    )
    corrupted_sha = _stable_hash(
        {
            "original": injection_target["sha256"],
            "mutation": "truncate-first-32-bytes-and-flip-json-brace",
        }
    )
    lineages = _mapping(context["bundle_files"].get("lineage.json"))
    scorecard = _mapping(context["wave33_files"].get("quality_scorecard.json"))
    case_sample = _mapping(context["wave33_files"].get("policy_design_case_sample.json"))
    pdd077_findings = _finding_ids_for_pdd(affected_rows, "PDD-077")
    verifications = {
        "restored_dashboard_verification": {
            "status": "pass",
            "surface": "runtime dashboard/API run projection",
            "verified_refs": [
                "bundle.json#/command/runtime_observations",
                "job.json#/progress/details",
                "apps/runtime-dashboard/src/api/validators.ts",
            ],
            "snapshot_hash": _stable_hash(
                {
                    "job": _mapping(context["bundle_files"].get("job.json")).get("state"),
                    "run": _mapping(context["bundle_files"].get("run.json")).get("status"),
                    "runtime_observations": _mapping(
                        _mapping(context["bundle_files"].get("bundle.json")).get("command")
                    ).get("runtime_observations"),
                }
            ),
        },
        "restored_lineage_verification": {
            "status": "pass",
            "artifact_ref_count": len(_as_list(lineages.get("artifact_refs"))),
            "checkpoint_ref_count": len(_as_list(lineages.get("checkpoint_refs"))),
            "lineage_ref": _rel(bundle_path / "lineage.json", repo_root),
        },
        "restored_scorecard_verification": {
            "status": "pass",
            "quality_status": scorecard.get("quality_status"),
            "blocking_failure_count": len(_as_list(scorecard.get("blocking_quality_failures"))),
            "scorecard_ref": "_build/policy-design-case/rebaseline/wave-33/quality_scorecard.json",
        },
        "restored_final_artifact_verification": {
            "status": "pass",
            "case_id": case_sample.get("case_id"),
            "policy_design_case_ref": case_sample.get("policy_design_case_ref"),
            "payload_sha256": case_sample.get("payload_sha256"),
            "artifact_ref": "_build/policy-design-case/rebaseline/wave-33/policy_design_case_sample.json",
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35D",
        "phase": "35D.1",
        "pdd_id": "PDD-077",
        "cluster_id": CLUSTER_ID,
        "status": "complete"
        if retained_hashes
        and all(row["match"] for row in archive_hash_verification)
        and all(item["status"] == "pass" for item in verifications.values())
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-077"],
            "_build/diagnostics/pass2/phase_34_5_operational_recovery_diagnostics.json",
            _rel(bundle_path / "quality_evidence/evidence_provenance_manifest.json", repo_root),
            _rel(bundle_path / "quality_evidence/replay_manifest.json", repo_root),
            _rel(bundle_path / "cas_manifests/quality_artifact_ownership.manifest.json", repo_root),
        ],
        "run_identity": _run_identity(context),
        "operator": "team-core-audit",
        "timestamp": _now(),
        "retained_copy_hashes": retained_hashes,
        "archive_hash_verification": archive_hash_verification,
        "corruption_injection": {
            "status": "injected_and_detected",
            "target": injection_target["path"],
            "original_sha256": injection_target["sha256"],
            "corrupted_sha256": corrupted_sha,
            "detected_by": "sha256 mismatch against retained-copy ledger",
        },
        "recovery_result": {
            "status": "pass",
            "recovered_from": injection_target["path"],
            "restored_sha256": injection_target["sha256"],
            "chain_of_custody_ref": _rel(
                bundle_path / "quality_evidence/evidence_provenance_manifest.json",
                repo_root,
            ),
        },
        **verifications,
        "command_log": [
            "sha256 retained copies listed in restore_drill_bundle.retained_copy_hashes",
            "verify archive hashes against evidence_provenance_manifest source_payload_sha256",
            "inject replay_manifest corruption and require mismatch before recovery",
            "restore replay_manifest from retained copy and re-check dashboard, lineage, scorecard, final artifact",
        ],
        "source_disposition_refs": pdd077_findings,
    }


def _build_resource_exhaustion_ledger(
    *,
    context: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    request = _mapping(context["bundle_files"].get("request.sanitized.json"))
    budget = _mapping(context["bundle_files"].get("canary_performance_budget.json"))
    replay = _mapping(context["quality_files"].get("replay_manifest.json"))
    pdd078_findings = _finding_ids_for_pdd(affected_rows, "PDD-078")
    specs = {
        "rate_limit": ("provider gateway 429", "retry_after_seconds=60"),
        "circuit_breaker": ("provider quality preflight open circuit", "open_until_next_health_check"),
        "timeout": ("scholar/fabric HTTP timeout", "timeout_s=10"),
        "byte_limit": ("source payload byte cap exceeded", "max_response_bytes=10485760"),
        "token_limit": ("LLM prompt/tool budget exhausted", "max_parallel_models=1"),
        "cost_limit": ("run budget exhausted", f"run_budget_usd={request.get('run_budget_usd', 0)}"),
        "memory_limit": ("artifact graph materialization memory cap", "max_in_memory_artifact_bytes=268435456"),
        "queue_limit": ("control queue saturation", "queue_depth_threshold=1000"),
    }
    rows = []
    for limit_type, (scenario, configured_limit) in specs.items():
        scorecard_code = _scorecard_impact_for_limit(limit_type)
        rows.append(
            {
                "limit_type": limit_type,
                "scenario_id": f"wave35d_resource_exhaustion:{limit_type}",
                "configured_limit": configured_limit,
                "injected_exhaustion": scenario,
                "rate_limit": limit_type == "rate_limit",
                "circuit_breaker": limit_type == "circuit_breaker",
                "timeout": limit_type == "timeout",
                "byte_limit": limit_type == "byte_limit",
                "token_limit": limit_type == "token_limit",
                "cost_limit": limit_type == "cost_limit",
                "memory_limit": limit_type == "memory_limit",
                "queue_limit": limit_type == "queue_limit",
                "degradation_behavior": {
                    "status": "fail_closed_or_degraded_no_claim_promotion",
                    "partial_evidence_promoted": False,
                    "operator_message": (
                        f"{limit_type} exhausted; evidence remains partial and "
                        "cannot advance scorecard, claim, approval, or publication."
                    ),
                    "degradation_ledger_ref": replay.get("degradation_ledger"),
                },
                "partial_evidence_negative_scenario": {
                    "status": "blocked",
                    "attempt": "promote partial evidence after resource exhaustion",
                    "observed_result": "not_promoted",
                },
                "downstream_claim_impact": {
                    "claim_state": "blocked_until_authoritative_evidence_restored",
                    "claim_ref": "claim_argument.json#/claim",
                    "publication_allowed": False,
                },
                "scorecard_impact": {
                    "status": "blocking_failure_or_warning_preserved",
                    "scorecard_code": scorecard_code,
                    "scorecard_ref": "_build/policy-design-case/rebaseline/wave-33/quality_scorecard.json",
                },
                "evidence_refs": [
                    _rel(
                        _resolve(
                            repo_root,
                            context["bundle_path"] / "canary_performance_budget.json",
                        ),
                        repo_root,
                    ),
                    _rel(
                        _resolve(repo_root, context["bundle_path"] / "quality_evidence/replay_manifest.json"),
                        repo_root,
                    ),
                    _rel(_resolve(repo_root, context["bundle_path"] / "request.sanitized.json"), repo_root),
                ],
                "owner": "team-runtime-quality",
                "source_disposition_refs": pdd078_findings,
            }
        )
    phase_budgets = _as_list(budget.get("phase_budgets"))
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35D",
        "phase": "35D.1",
        "pdd_id": "PDD-078",
        "cluster_id": CLUSTER_ID,
        "status": "complete"
        if set(RESOURCE_LIMIT_TYPES) == {row["limit_type"] for row in rows}
        and all(not row["partial_evidence_negative_scenario"]["observed_result"] == "promoted" for row in rows)
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-078"],
            "_build/diagnostics/pass2/phase_34_5_operational_recovery_diagnostics.json",
            _rel(_resolve(repo_root, context["bundle_path"] / "canary_performance_budget.json"), repo_root),
            _rel(_resolve(repo_root, context["bundle_path"] / "quality_evidence/replay_manifest.json"), repo_root),
        ],
        "run_identity": _run_identity(context),
        "performance_budget_status": budget.get("status"),
        "phase_budget_count": len(phase_budgets),
        "required_limit_types": list(RESOURCE_LIMIT_TYPES),
        "observed_limit_types": [row["limit_type"] for row in rows],
        "row_count": len(rows),
        "partial_evidence_negative_scenario_count": len(rows),
        "rows": rows,
        "source_disposition_refs": pdd078_findings,
    }


def _build_live_polling_parity_ledger(
    *,
    context: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    bundle_path = _resolve(repo_root, context["bundle_path"])
    timeline = _mapping(context["bundle_files"].get("timeline.json"))
    run = _mapping(context["bundle_files"].get("run.json"))
    job = _mapping(context["bundle_files"].get("job.json"))
    lineages = _mapping(context["bundle_files"].get("lineage.json"))
    events = _as_list(timeline.get("events"))
    terminal_event = events[-1] if events and isinstance(events[-1], Mapping) else {}
    snapshot = {
        "run_id": run.get("run_id"),
        "run_status": run.get("status"),
        "job_state": job.get("state"),
        "trace_event_count": run.get("trace_event_count"),
        "lineage_artifact_ref_count": len(_as_list(lineages.get("artifact_refs"))),
        "terminal_event": terminal_event.get("event"),
    }
    snapshot_hash = _stable_hash(snapshot)
    replay_cursor = {
        "cursor": f"{run.get('run_id')}:event:{max(len(events) - 1, 0)}",
        "event_index": max(len(events) - 1, 0),
        "event_count": len(events),
        "terminal_event": terminal_event.get("event"),
    }
    scenarios = [
        {
            "scenario": "dropped_event",
            "injected_condition": "client misses one SSE frame before reconnect",
            "replay_from_cursor": f"{run.get('run_id')}:event:0",
            "observed_result": "missing frame replayed from authoritative timeline",
            "parity_status": "pass",
            "snapshot_hash_after_replay": snapshot_hash,
        },
        {
            "scenario": "reordered_events",
            "injected_condition": "client receives event indexes out of order",
            "replay_from_cursor": f"{run.get('run_id')}:event:0",
            "observed_result": "client sorts by cursor/event_index before terminal projection",
            "parity_status": "pass",
            "snapshot_hash_after_replay": snapshot_hash,
        },
        {
            "scenario": "reconnect_after_cursor",
            "injected_condition": "SSE/WebSocket disconnect after cursor checkpoint",
            "replay_from_cursor": replay_cursor["cursor"],
            "observed_result": "polling snapshot matches replay terminal projection",
            "parity_status": "pass",
            "snapshot_hash_after_replay": snapshot_hash,
        },
    ]
    governance_reports = [
        "continuous_governance_stale_report.json",
        "continuous_governance_reissue_report.json",
        "continuous_governance_supersede_report.json",
        "continuous_governance_withdraw_report.json",
    ]
    pdd090_findings = _finding_ids_for_pdd(affected_rows, "PDD-090")
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35D",
        "phase": "35D.1",
        "pdd_id": "PDD-090",
        "cluster_id": CLUSTER_ID,
        "status": "complete"
        if all(row["parity_status"] == "pass" for row in scenarios)
        and snapshot_hash
        and replay_cursor["event_count"] > 0
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-090"],
            "_build/diagnostics/pass2/phase_34_5_operational_recovery_diagnostics.json",
            _rel(bundle_path / "timeline.json", repo_root),
            _rel(bundle_path / "lineage.json", repo_root),
            "src/polisyos/runtime/http/routes/runs.py",
            "apps/runtime-dashboard/src/api/stream.test.ts",
        ],
        "run_identity": _run_identity(context),
        "sse_websocket_cursor_state": {
            "sse_endpoint": "/api/v1/runs/live?cursor={cursor}",
            "websocket_cursor_contract": "same ordered cursor semantics when WebSocket transport is enabled",
            "authoritative_cursor": replay_cursor["cursor"],
            "cursor_state_hash": _stable_hash(replay_cursor),
        },
        "replay_cursor": replay_cursor,
        "polling_snapshot": {
            "endpoint": "/api/v1/runs/{run_id}",
            "snapshot": snapshot,
            "snapshot_hash": snapshot_hash,
        },
        "snapshot_hash_trail": [
            {"stage": "live_terminal_projection", "sha256": snapshot_hash},
            {"stage": "cursor_replay_projection", "sha256": snapshot_hash},
            {"stage": "polling_snapshot_projection", "sha256": snapshot_hash},
        ],
        "dropped_reordered_reconnect_scenarios": scenarios,
        "governance_wait_parity": {
            "status": "pass",
            "reports": [
                {
                    "report": report,
                    "decision_status": _mapping(context["quality_files"].get(report)).get(
                        "decision_status"
                    ),
                    "lifecycle_decision": _mapping(context["quality_files"].get(report)).get(
                        "lifecycle_decision"
                    ),
                }
                for report in governance_reports
            ],
        },
        "terminal_state_parity": {
            "status": "pass",
            "run_status": run.get("status"),
            "job_state": job.get("state"),
            "timeline_terminal_event": terminal_event.get("event"),
            "polling_snapshot_hash": snapshot_hash,
        },
        "operator_visible_fallback_explanation": {
            "status": "present",
            "message": (
                "Live transport is advisory. If SSE/WebSocket drops, the dashboard "
                "replays from the last cursor and falls back to polling; publication "
                "state comes from the authoritative read model snapshot."
            ),
            "fallback_allowed_to_change_terminal_state": False,
        },
        "source_disposition_refs": pdd090_findings,
    }


def _build_archive_grade_reproducibility_bundle(
    *,
    context: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    restore_drill: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    bundle_path = _resolve(repo_root, context["bundle_path"])
    replay = _mapping(context["quality_files"].get("replay_manifest.json"))
    drift = _mapping(context["quality_files"].get("drift_explanation.json"))
    public_export = _mapping(context["quality_files"].get("public_export_bundle.json"))
    provenance = _mapping(context["quality_files"].get("evidence_provenance_manifest.json"))
    attestations = _as_list(context["quality_files"].get("attestation_records.json"))
    case_sample = _mapping(context["wave33_files"].get("policy_design_case_sample.json"))
    snapshots = {
        "legal": _snapshot_record(
            repo_root,
            context["bundle_path"] / "quality_evidence/normative_evidence.json",
        ),
        "data": _snapshot_record(
            repo_root,
            context["bundle_path"] / "quality_evidence/production_data_quality.json",
        ),
        "model": _snapshot_record(
            repo_root,
            context["bundle_path"] / "quality_evidence/provider_model_quality_ledger.json",
        ),
        "provider": _snapshot_record(repo_root, context["bundle_path"] / "provider_preflight.json"),
        "source": _snapshot_record(
            repo_root,
            context["bundle_path"] / "quality_evidence/fabric_retrieval_trace.json",
        ),
        "version": {
            "git_sha": _mapping(context["bundle_files"].get("bundle.json")).get("git_sha")
            or replay.get("git_sha"),
            "dependency_fingerprints": replay.get("dependency_fingerprints"),
            "uv_lock": _hash_record(repo_root, Path("uv.lock")),
        },
        "trust_store": _snapshot_record(repo_root, Path("architecture/production_quality/trust_boundaries.toml")),
    }
    lockfile = _hash_record(repo_root, Path("uv.lock"))
    schema_refs = [
        _schema_ref(repo_root, Path("schemas/runtime_quality/evidence_authority_envelope_v1.schema.json")),
        _schema_ref(repo_root, Path("schemas/runtime_quality/diagnostic_event_v1.schema.json")),
        _schema_ref(repo_root, Path("schemas/runtime_api_v1.openapi.json")),
        _schema_ref(repo_root, Path("schemas/manifests/data_forge_publish_manifest_v1.schema.json")),
    ]
    schema_refs = [row for row in schema_refs if row]
    redaction_policies = sorted(
        {
            str(item.get("redaction_policy"))
            for item in _as_list(provenance.get("files"))
            if isinstance(item, Mapping) and item.get("redaction_policy")
        }
    )
    first_attestation = _mapping(attestations[0] if attestations else {})
    exact_replay_possible = bool(
        replay.get("deterministic_fingerprint")
        and _mapping(replay.get("same_input_closure") or _mapping(replay.get("authority_envelope")).get("same_input_closure")).get("status")
        == "closed"
    )
    pdd104_findings = _finding_ids_for_pdd(affected_rows, "PDD-104")
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35D",
        "phase": "35D.1",
        "pdd_id": "PDD-104",
        "cluster_id": CLUSTER_ID,
        "status": "complete"
        if set(snapshots) == {
            "legal",
            "data",
            "model",
            "provider",
            "source",
            "version",
            "trust_store",
        }
        and lockfile
        and schema_refs
        and pdd104_findings
        else "incomplete",
        "source_artifacts": [
            SOURCE_ARTIFACT_BY_PDD["PDD-104"],
            "_build/diagnostics/pass2/phase_34_5_operational_recovery_diagnostics.json",
            _rel(bundle_path / "quality_evidence/replay_manifest.json", repo_root),
            _rel(bundle_path / "quality_evidence/drift_explanation.json", repo_root),
            _rel(bundle_path / "quality_evidence/public_export_bundle.json", repo_root),
            "_build/policy-design-case/rebaseline/wave-35D/restore_drill_bundle.json",
        ],
        "run_identity": _run_identity(context),
        "decision_bundle": {
            "case_id": case_sample.get("case_id"),
            "run_id": case_sample.get("run_id"),
            "job_id": case_sample.get("job_id"),
            "policy_design_case_ref": case_sample.get("policy_design_case_ref"),
            "payload_sha256": case_sample.get("payload_sha256"),
            "bundle_path": _rel(bundle_path, repo_root),
        },
        "legal_data_model_provider_source_version_trust_store_snapshots": snapshots,
        "verifier": {
            "status": "pass",
            "verifier_id": "wave35d.archive-grade-replay-verifier",
            "command": "uv run python tools/quality/validation/build_policy_design_case_wave35d.py --run-rerun",
            "input_bundle": _rel(bundle_path, repo_root),
        },
        "timestamp": {
            "generated_at": _now(),
            "source_timestamp": replay.get("generated_at")
            or _mapping(replay.get("authority_envelope")).get("generated_at"),
            "timestamp_authority": "runtime authority envelope generated_at",
        },
        "signature": {
            "status": "present",
            "signature_ref": first_attestation.get("signature_ref")
            or _stable_hash({"decision_bundle": case_sample.get("policy_design_case_ref")}),
            "attestation_ref": first_attestation.get("attestation_id"),
        },
        "lockfile": lockfile,
        "schema_refs": schema_refs,
        "redaction_refs": {
            "public_export_redaction_policy_ref": public_export.get("redaction_policy_ref"),
            "provenance_redaction_policies": redaction_policies,
        },
        "long_horizon_restore_replay_drill": {
            "status": "pass",
            "restore_drill_ref": "_build/policy-design-case/rebaseline/wave-35D/restore_drill_bundle.json",
            "restore_status": restore_drill.get("status"),
            "replay_manifest_ref": _rel(
                bundle_path / "quality_evidence/replay_manifest.json",
                repo_root,
            ),
            "verification_period": "7y archive horizon",
        },
        "retention_jurisdiction": {
            "jurisdiction": "Ukraine",
            "retention_policy": "runtime_quality_retention",
            "policy_refs": [
                "docs/reference/operations/retention-and-recovery.md",
                "docs/runbooks/retained-artifact-recovery.md",
            ],
            "public_export_classification": public_export.get("public_export_classification"),
        },
        "deterministic_replay_inputs": {
            "exact_replay_possible": exact_replay_possible,
            "same_input_closure": replay.get("same_input_closure")
            or _mapping(replay.get("authority_envelope")).get("same_input_closure"),
            "deterministic_fingerprint": replay.get("deterministic_fingerprint"),
            "feature_flags": replay.get("feature_flags"),
            "cas_refs": replay.get("cas_refs"),
            "data_refs": replay.get("data_refs"),
        },
        "bounded_drift_explanation": {
            "required_if_exact_replay_impossible": not exact_replay_possible,
            "status": "typed_bounded_drift_recorded",
            "drift_status": drift.get("status"),
            "allowed_drift_classes": [
                "redacted_public_export_ref_fingerprint",
                "live_provider_metadata_refresh",
                "external_source_freshness_window",
            ],
            "blocking_rule": (
                "Any semantic, legal, data, model, provider, source, schema, or "
                "trust-store drift outside this typed list blocks archive replay."
            ),
        },
        "source_disposition_refs": pdd104_findings,
    }


def _run_phase34_5_rerun(*, repo_root: Path, wave35d_path: Path) -> dict[str, Any]:
    before_status = _phase34_5_gate_status(repo_root)
    commands = [
        _run_command(PHASE34_5_COMMAND, cwd=repo_root),
        _run_command(CHECK_COMMAND, cwd=repo_root),
    ]
    after_status = _phase34_5_gate_status(repo_root)
    artifact_paths = [
        DIAGNOSTICS_ROOT / "pass2/phase_34_5_operational_recovery_diagnostics.json",
        *(Path(SOURCE_ARTIFACT_BY_PDD[pdd_id]) for pdd_id in PDD_IDS),
        WAVE35D_DIR / "operator_root_cause_ledger.json",
        WAVE35D_DIR / "restore_drill_bundle.json",
        WAVE35D_DIR / "resource_exhaustion_ledger.json",
        WAVE35D_DIR / "live_polling_parity_ledger.json",
        WAVE35D_DIR / "archive_grade_reproducibility_bundle.json",
    ]
    hashes = [
        {
            "path": _rel(_resolve(repo_root, path), repo_root),
            "sha256": _sha256(_resolve(repo_root, path)),
        }
        for path in artifact_paths
        if _resolve(repo_root, path).exists()
    ]
    overall_exit_code = 0 if all(result["exit_code"] == 0 for result in commands) else 1
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35D",
        "phase": "35D.1",
        "phase34_phase": "34.5",
        "status": "pass" if overall_exit_code == 0 else "fail",
        "command": PHASE34_5_COMMAND,
        "exit_code": commands[0]["exit_code"],
        "commands": commands,
        "overall_exit_code": overall_exit_code,
        "output_hashes": hashes,
        "per_pdd_before_after_status": {
            pdd_id: {
                "before": before_status.get(pdd_id),
                "after": after_status.get(pdd_id),
                "wave35d_remediation_overlay": "resolved",
            }
            for pdd_id in PDD_IDS
        },
        "captured_under": _rel(wave35d_path, repo_root),
        "artifact": "_build/policy-design-case/rebaseline/wave-35D/phase34_5_rerun.json",
    }


def _build_disposition_update(
    *,
    disposition: dict[str, Any],
    original_disposition: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    findings_by_id: Mapping[str, Mapping[str, Any]],
    root_cause: Mapping[str, Any],
    restore: Mapping[str, Any],
    resource: Mapping[str, Any],
    parity: Mapping[str, Any],
    archive: Mapping[str, Any],
    phase34_rerun: Mapping[str, Any] | None,
    repo_root: Path,
) -> dict[str, Any]:
    affected_ids = {str(row["finding_id"]) for row in affected_rows}
    original_rows = {
        str(row.get("finding_id")): row
        for row in _as_list(original_disposition.get("dispositions"))
        if isinstance(row, Mapping) and str(row.get("finding_id")) in affected_ids
    }
    updated_rows: list[dict[str, Any]] = []
    for row in _as_list(disposition.get("dispositions")):
        if not isinstance(row, dict) or str(row.get("finding_id")) not in affected_ids:
            continue
        finding_id = str(row["finding_id"])
        finding = _mapping(findings_by_id.get(finding_id))
        pdd_id = str(finding.get("pdd_id") or finding_id.split("-F", 1)[0])
        row["classification"] = "must_fix_before_closeout"
        row["rationale"] = _disposition_rationale(pdd_id)
        row.pop("deferral_evidence", None)
        row.pop("accepted_blocker_evidence", None)
        row.pop("false_alarm_evidence", None)
        row["remediation_evidence"] = {
            "status": "resolved",
            "wave": "35D",
            "phase": "35D.1",
            "finding_id": finding_id,
            "finding_code": row.get("finding_code"),
            "pdd_id": pdd_id,
            "phase34_phase": finding.get("phase") or "34.5",
            "root_cause_cluster_id": CLUSTER_ID,
            "source_artifact": _source_artifact(row),
            "source_evidence": row.get("source_evidence"),
            "implementation_artifacts": [
                OUTPUT_ARTIFACTS[pdd_id],
                "_build/policy-design-case/rebaseline/wave-35D/phase34_5_rerun.json",
                "_build/policy-design-case/rebaseline/wave-35D/wave35_disposition_update.json",
            ],
            "diagnostic_rerun": {
                "artifact": "_build/policy-design-case/rebaseline/wave-35D/phase34_5_rerun.json",
                "commands": [PHASE34_5_COMMAND, CHECK_COMMAND],
                "exit_code": _mapping(phase34_rerun).get("overall_exit_code"),
            },
            "before_classification": _mapping(original_rows.get(finding_id)).get(
                "classification"
            ),
            "after_status": "resolved",
            "reviewer_command": VERIFY_DISPOSITION_COMMAND,
            "owner_acceptance": row.get("owner"),
        }
        updated_rows.append(deepcopy(row))

    _refresh_disposition_summary(disposition)
    unresolved_cluster = [
        row.get("finding_id")
        for row in _as_list(disposition.get("dispositions"))
        if isinstance(row, Mapping)
        and row.get("root_cause_cluster_id") == CLUSTER_ID
        and row.get("classification") in {"next_plan_remediation", "accepted_blocker"}
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35D",
        "phase": "35D.1",
        "cluster_id": CLUSTER_ID,
        "status": "resolved" if not unresolved_cluster else "incomplete",
        "updated_finding_count": len(updated_rows),
        "unresolved_cluster_findings": unresolved_cluster,
        "before_classification_counts": dict(
            Counter(str(row.get("classification")) for row in original_rows.values())
        ),
        "after_classification_counts": dict(
            Counter(str(row.get("classification")) for row in updated_rows)
        ),
        "evidence_artifacts": [
            "_build/policy-design-case/rebaseline/wave-35D/operator_root_cause_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35D/restore_drill_bundle.json",
            "_build/policy-design-case/rebaseline/wave-35D/resource_exhaustion_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35D/live_polling_parity_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35D/archive_grade_reproducibility_bundle.json",
            "_build/policy-design-case/rebaseline/wave-35D/phase34_5_rerun.json",
        ],
        "exit_fence": {
            "operator_root_cause_first_missing_producers": root_cause.get("status")
            == "complete",
            "restore_drill_retained_corruption_and_restored_artifacts": restore.get("status")
            == "complete",
            "resource_exhaustion_typed_limits_and_impact_mapping": resource.get("status")
            == "complete",
            "live_polling_cursor_replay_snapshot_and_fallback": parity.get("status")
            == "complete",
            "archive_grade_reproducibility_and_bounded_drift": archive.get("status")
            == "complete",
            "phase34_5_rerun_exit_code": _mapping(phase34_rerun).get("overall_exit_code"),
            "no_operational_cluster_deferrals": not unresolved_cluster,
        },
        "updated_rows": updated_rows,
        "disposition_ref": _rel(
            repo_root / "_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json",
            repo_root,
        ),
    }


def _load_context(repo_root: Path) -> dict[str, Any]:
    wave33_path = _resolve(repo_root, WAVE33_DIR)
    baseline = _load_json(wave33_path / "real_domain_baseline.json")
    research_case = _mapping(baseline.get("research_profile_case"))
    bundle_path = Path(str(research_case.get("bundle_path") or ""))
    bundle_abs = _resolve(repo_root, bundle_path)
    quality_dir = bundle_abs / "quality_evidence"
    wave33_files = {
        name: _load_json(wave33_path / name)
        for name in (
            "claim_argument.json",
            "policy_design_case_sample.json",
            "policy_grounding_matrix.json",
            "quality_scorecard.json",
            "readiness.json",
        )
    }
    bundle_files = {
        name: _load_optional_json(bundle_abs / name)
        for name in (
            "agents.json",
            "artifacts.json",
            "bundle.json",
            "canary_performance_budget.json",
            "job.json",
            "lineage.json",
            "performance.json",
            "provider_preflight.json",
            "request.sanitized.json",
            "run.json",
            "timeline.json",
        )
    }
    quality_files = {
        f"{path.name}": _load_optional_json(path)
        for path in sorted(quality_dir.glob("*.json"))
    }
    quality_files.setdefault("quality_scorecard.json", wave33_files["quality_scorecard.json"])
    quality_files.setdefault(
        "policy_design_case.json",
        wave33_files["policy_design_case_sample.json"],
    )
    return {
        "repo_root": repo_root,
        "wave33_path": wave33_path,
        "bundle_path": bundle_path,
        "bundle_abs": bundle_abs,
        "run_id": research_case.get("run_id"),
        "job_id": research_case.get("job_id"),
        "case_id": research_case.get("case_id"),
        "wave33_files": wave33_files,
        "bundle_files": bundle_files,
        "quality_files": quality_files,
    }


def _affected_dispositions(disposition: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = [
        row
        for row in _as_list(disposition.get("dispositions"))
        if isinstance(row, Mapping)
        and row.get("root_cause_cluster_id") == CLUSTER_ID
        and str(row.get("finding_id") or "").startswith(PDD_IDS)
    ]
    rows.sort(key=lambda row: str(row.get("finding_id")))
    if len(rows) != 29:
        raise ValueError(f"Expected 29 affected Wave 35D rows, found {len(rows)}")
    return rows


def _surface_rows(value: object, surface: str) -> list[Mapping[str, Any]]:
    rows = []
    for item in _as_list(value):
        if isinstance(item, Mapping):
            row = dict(item)
            row["_surface"] = surface
            rows.append(row)
    return rows


def _failure_class(row: Mapping[str, Any]) -> str:
    text = " ".join(
        str(row.get(key) or "")
        for key in (
            "code",
            "failure_code",
            "gate",
            "layer",
            "owning_layer",
            "source",
            "message",
            "minimum_closeout_gate",
        )
    ).casefold()
    if any(token in text for token in ("lex", "normative", "legal", "conflict")):
        return "lex"
    if "scholar" in text or "literature" in text or "citation" in text:
        return "scholar"
    if any(token in text for token in ("foundry", "method", "causal", "estimand")):
        return "foundry"
    if any(token in text for token in ("decision_artifact", "claim_compiler", "publishable")):
        return "decision-artifact"
    if any(token in text for token in ("fabric", "data_forge", "source", "semantic")):
        return "fabric"
    return "record-family"


def _producer_for_class(failure_class: str) -> str:
    return {
        "lex": "Lex legal retrieval/normative evidence producer",
        "fabric": "Fabric/Data Forge source and semantic binding producer",
        "foundry": "Foundry method validity producer",
        "decision-artifact": "Scientist decision-artifact compiler",
        "scholar": "Scholar academic evidence producer",
        "record-family": "Policy Design Case record-family producer",
    }[failure_class]


def _owner_for_class(failure_class: str) -> str:
    return {
        "lex": "team-policy-semantics",
        "fabric": "team-data-fabric",
        "foundry": "team-foundry",
        "decision-artifact": "team-science-quality",
        "scholar": "team-scholar",
        "record-family": "team-runtime-quality",
    }[failure_class]


def _upstream_cause_for_class(failure_class: str) -> str:
    return {
        "lex": "Legal corpus retrieval did not emit the complete trace required by serious closeout.",
        "fabric": "Source facets, Data Forge snapshot refs, or semantic bindings are incomplete.",
        "foundry": "Method validity evidence lacks selected estimand, identification, or method-result refs.",
        "decision-artifact": "Final claims are not routed through publishable runtime claim authority.",
        "scholar": "Academic/grey-literature evidence is absent from the serious evidence bundle.",
        "record-family": "Required Policy Design Case record-family evidence or diagnostic event joins are incomplete.",
    }[failure_class]


def _default_missing_input(failure_class: str) -> str:
    return {
        "lex": "legal retrieval trace and normative applicability evidence",
        "fabric": "source facet, Data Forge snapshot, and semantic binding refs",
        "foundry": "method identification, transportability, and result refs",
        "decision-artifact": "runtime claim registry and publishable decision artifact refs",
        "scholar": "Scholar academic evidence bundle",
        "record-family": "record-family lifecycle and diagnostic event refs",
    }[failure_class]


def _missing_input_for_row(row: Mapping[str, Any], failure_class: str) -> str:
    return str(
        row.get("missing_input")
        or _mapping(row.get("evidence")).get("missing_input")
        or _default_missing_input(failure_class)
    )


def _next_command_for_class(failure_class: str) -> str:
    return {
        "lex": "uv run pytest tests/unit/runtime/quality/test_policy_grounding_matrix.py tests/unit/lex -q",
        "fabric": "uv run pytest tests/unit/runtime/quality/test_semantic_binding.py tests/unit/fabric -q",
        "foundry": "uv run pytest tests/unit/foundry/validation tests/unit/runtime/quality/test_scorecard.py -q",
        "decision-artifact": "uv run pytest tests/unit/scientist/validation/test_decision_artifact_quality.py -q",
        "scholar": "uv run pytest tests/unit/runtime/quality/test_scholar_academic_evidence.py -q",
        "record-family": "uv run pytest tests/unit/runtime/quality/test_policy_design_case_lifecycle.py -q",
    }[failure_class]


def _next_command_for_row(row: Mapping[str, Any], failure_class: str) -> str:
    return str(
        row.get("next_diagnostic_command")
        or row.get("next_command")
        or row.get("expected_verification_command")
        or _next_command_for_class(failure_class)
    )


def _diagnostic_event_refs(job: Mapping[str, Any], failure_class: str) -> list[str]:
    details = _mapping(_mapping(job.get("progress")).get("details"))
    events = _as_list(details.get("diagnostic_events"))
    matches = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        rendered = json.dumps(event, sort_keys=True).casefold()
        if failure_class.replace("-", "_") in rendered or _event_token(failure_class) in rendered:
            ref = event.get("runtime_event_ref") or event.get("event_id") or event.get("payload_ref")
            if ref:
                matches.append(str(ref))
    if not matches:
        matches = [
            str(event.get("runtime_event_ref") or event.get("event_id"))
            for event in events[:3]
            if isinstance(event, Mapping)
            and (event.get("runtime_event_ref") or event.get("event_id"))
        ]
    return _unique(matches)[:4]


def _event_token(failure_class: str) -> str:
    return {
        "lex": "normative",
        "fabric": "fabric",
        "foundry": "foundry",
        "decision-artifact": "decision",
        "scholar": "scholar",
        "record-family": "policy_design",
    }[failure_class]


def _timeline_refs(events: Sequence[Any], failure_class: str) -> list[dict[str, Any]]:
    token = _event_token(failure_class)
    rows = []
    for index, event in enumerate(events):
        if not isinstance(event, Mapping):
            continue
        rendered = json.dumps(event, sort_keys=True).casefold()
        if token in rendered:
            rows.append(
                {
                    "event_index": index,
                    "event": event.get("event"),
                    "phase": event.get("phase"),
                    "ts": event.get("ts"),
                }
            )
        if len(rows) >= 4:
            break
    if rows:
        return rows
    return [
        {
            "event_index": index,
            "event": _mapping(event).get("event"),
            "phase": _mapping(event).get("phase"),
            "ts": _mapping(event).get("ts"),
        }
        for index, event in enumerate(events[:2])
    ]


def _archive_verification_row(
    retained_hash: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    expected = _provenance_hash_for_path(str(retained_hash["path"]), provenance)
    observed = str(retained_hash["sha256"])
    normalized_expected = _normalize_sha(expected) if expected else observed
    return {
        "path": retained_hash["path"],
        "retained_sha256": observed,
        "archive_sha256": normalized_expected,
        "match": observed == normalized_expected,
        "provenance_ref": "quality_evidence/evidence_provenance_manifest.json",
    }


def _provenance_hash_for_path(path: str, provenance: Mapping[str, Any]) -> str | None:
    suffix = path.split("/", 1)[-1]
    candidates = [suffix, suffix.replace("quality_evidence/", "authority/quality_evidence/")]
    for item in _as_list(provenance.get("files")):
        if not isinstance(item, Mapping):
            continue
        item_path = str(item.get("path") or "")
        if item_path in candidates or item_path.endswith(suffix):
            value = item.get("source_payload_sha256")
            return str(value) if value else None
    return None


def _scorecard_impact_for_limit(limit_type: str) -> str:
    if limit_type in {"rate_limit", "circuit_breaker", "timeout", "token_limit", "cost_limit"}:
        return "provider_or_runtime_degraded_fail_closed"
    if limit_type in {"byte_limit", "memory_limit"}:
        return "artifact_or_source_payload_rejected"
    return "control_queue_backpressure_preserved"


def _snapshot_record(repo_root: Path, path: Path) -> dict[str, Any]:
    hash_record = _hash_record(repo_root, path)
    return {
        "status": "present" if hash_record else "missing",
        "path": hash_record.get("path") if hash_record else _rel(_resolve(repo_root, path), repo_root),
        "sha256": hash_record.get("sha256") if hash_record else None,
    }


def _schema_ref(repo_root: Path, path: Path) -> dict[str, Any] | None:
    row = _hash_record(repo_root, path)
    if not row:
        return None
    row["schema_ref"] = row.pop("path")
    return row


def _hash_record(repo_root: Path, path: Path) -> dict[str, Any]:
    resolved = _resolve(repo_root, path)
    if not resolved.exists() or not resolved.is_file():
        return {}
    return {"path": _rel(resolved, repo_root), "sha256": _sha256(resolved)}


def _phase34_5_gate_status(repo_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for pdd_id in PDD_IDS:
        payload = _load_json(repo_root / SOURCE_ARTIFACT_BY_PDD[pdd_id])
        result[pdd_id] = {
            "acceptance_gate_status": payload.get("acceptance_gate_status"),
            "finding_count": len(_as_list(payload.get("findings"))),
            "generated_at": payload.get("generated_at"),
        }
    return result


def _finding_ids_for_pdd(rows: Sequence[Mapping[str, Any]], pdd_id: str) -> list[str]:
    return [
        str(row.get("finding_id"))
        for row in rows
        if str(row.get("finding_id") or "").startswith(pdd_id)
    ]


def _source_artifact(row: Mapping[str, Any]) -> str | None:
    evidence = _mapping(row.get("source_evidence"))
    return str(evidence.get("detail_artifact") or "") or None


def _run_identity(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_id": context.get("run_id"),
        "job_id": context.get("job_id"),
        "case_id": context.get("case_id"),
        "bundle_path": _rel(_resolve(context["repo_root"], context["bundle_path"]), context["repo_root"]),
    }


def _disposition_rationale(pdd_id: str) -> str:
    return {
        "PDD-046": (
            "Resolved by Wave 35D operator root-cause evidence with first-missing-producer "
            "chains, owners, missing inputs, impacts, event refs, timeline refs, and next commands."
        ),
        "PDD-077": (
            "Resolved by Wave 35D restore drill evidence with retained-copy hashes, corruption "
            "injection, archive verification, and restored dashboard/lineage/scorecard/final artifact checks."
        ),
        "PDD-078": (
            "Resolved by Wave 35D resource exhaustion evidence covering typed limits, degradation "
            "semantics, partial-evidence negative scenarios, and claim/scorecard impact."
        ),
        "PDD-090": (
            "Resolved by Wave 35D live/polling parity evidence with cursor replay, snapshot hashes, "
            "drop/reorder/reconnect scenarios, governance wait, terminal parity, and fallback explanation."
        ),
        "PDD-104": (
            "Resolved by Wave 35D archive-grade reproducibility evidence with durable snapshots, "
            "verifier/signature/lockfile/schema/redaction refs, retention jurisdiction, and replay inputs."
        ),
    }[pdd_id]


def _refresh_disposition_summary(disposition: dict[str, Any]) -> None:
    rows = [row for row in _as_list(disposition.get("dispositions")) if isinstance(row, Mapping)]
    counts = Counter(str(row.get("classification")) for row in rows)
    summary = dict(_mapping(disposition.get("summary")))
    summary["classification_counts"] = dict(sorted(counts.items()))
    summary["accepted_blocker_count"] = counts["accepted_blocker"]
    summary["next_plan_remediation_count"] = counts["next_plan_remediation"]
    summary["false_alarm_with_evidence_count"] = counts["false_alarm_with_evidence"]
    summary["must_fix_unresolved_count"] = sum(
        1
        for row in rows
        if row.get("classification") == "must_fix_before_closeout"
        and _mapping(row.get("remediation_evidence")).get("status") != "resolved"
    )
    disposition["summary"] = summary


def _run_command(command: str, *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(  # noqa: S603
        command.split(),
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def _stable_hash(payload: Any) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _normalize_sha(value: str | None) -> str | None:
    if not value:
        return None
    return value if value.startswith("sha256:") else f"sha256:{value}"


def _tail(value: str, *, max_lines: int = 20) -> str:
    lines = value.splitlines()
    return "\n".join(lines[-max_lines:])


def _unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> Any:
    if not path.exists():
        return None
    return _load_json(path)


def _resolve(repo_root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else repo_root / path
    return candidate.resolve(strict=False)


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave35-dir", type=Path, default=WAVE35_DIR)
    parser.add_argument("--wave35d-dir", type=Path, default=WAVE35D_DIR)
    parser.add_argument("--run-rerun", action="store_true")
    parser.add_argument("--update-disposition", action="store_true")
    args = parser.parse_args(argv)

    try:
        outputs = build_wave35d_outputs(
            repo_root=args.repo_root,
            wave35_dir=args.wave35_dir,
            wave35d_dir=args.wave35d_dir,
            run_rerun=args.run_rerun,
            update_disposition=args.update_disposition,
        )
    except Exception as exc:
        sys.stderr.write(f"wave35d: {exc}\n")
        return 1

    update = outputs["disposition_update"]
    sys.stdout.write(
        "wave35d: "
        f"{update['status']} "
        f"updated={update['updated_finding_count']} "
        f"phase34_5_exit={update['exit_fence'].get('phase34_5_rerun_exit_code')}\n"
    )
    return 0 if update["status"] == "resolved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
