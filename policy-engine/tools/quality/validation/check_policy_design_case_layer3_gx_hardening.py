#!/usr/bin/env python3
"""Validate Layer 3 GX hardening guardrails and expected-red diagnostics."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.layer3_gx_data_home import (
    CONCEPT_ALIAS_GRAPH_PATH,
    CONCEPT_ALIAS_SEED_ROWS_PATH,
    DEMAND_PULL_REQUEST_PATH,
    PINNED_REQUEST_PATH,
    SCOPE_SEED_ROWS_PATH,
    build_layer3_gx_data_home_artifacts,
    load_layer3_gx_data_home,
)
from polisyos.runtime.quality.layer3_status_reducers import (
    G1SourceGroundingClosureInputs,
    G2ForecastAdmissionInputs,
    G3ProofAuthorityInputs,
    G4PromotionStateInputs,
    G5ConversionOutcomeInputs,
    G7RegionClosureInputs,
    G8DomainVsSearchCeilingInputs,
    GLLegalAuthorityInputs,
    Layer3ReducerDecision,
    Layer3ReducerInputRef,
    reduce_g1_source_grounding_closure,
    reduce_g2_forecast_admission,
    reduce_g3_proof_authority,
    reduce_g4_promotion_state,
    reduce_g5_conversion_outcome,
    reduce_g7_region_closure,
    reduce_g8_domain_vs_search_ceiling,
    reduce_gl_legal_authority,
)
from tools.lib.fs import atomic_write_json

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
BASELINE_NOTE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_baseline_note.json"

RUNTIME_LITERAL_LINT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_runtime_literal_lint.json"
REDUCER_INTEGRITY_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_reducer_integrity_report.json"
POSITIVE_STATUS_PROVENANCE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gx_positive_status_provenance.json"
)
PRODUCER_REGISTRY_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_producer_registry.json"
PRODUCER_ROOT_CHAIN_REPORT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gx_producer_root_chain_report.json"
)
MEASUREMENT_REPLAY_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_measurement_replay_report.json"
PERSISTED_STATUS_RECOMPUTE_DRIFT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gx_persisted_status_recompute_drift.json"
)
STATUS_VOCABULARY_DELTA_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_status_vocabulary_delta.json"
CORRECTION_RETRACTION_LOG_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_correction_retraction_log.json"
INDEPENDENT_AUDIT_SAMPLE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_independent_audit_sample.json"
VALIDATION_AUTHORITY_BOUNDARY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gx_validation_authority_boundary.json"
)
EXPECTED_RED_CHECKS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_expected_red_checks.json"
HUMAN_APPROVAL_RECEIPTS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_human_approval_receipts.json"
VERTICAL_PINNED_ROUTE_REPORT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gx_vertical_pinned_route_report.json"
)
PROVISIONAL_PINNED_ROUTE_OUTCOME_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gx_provisional_pinned_route_outcome_report.json"
)
PROVISIONAL_BLOCKER_AUDIT_RECORD_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gx_provisional_blocker_audit_record.json"
)
FINAL_PINNED_ROUTE_OUTCOME_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gx_final_pinned_route_outcome_report.json"
)
FINAL_BLOCKER_AUDIT_RECORD_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gx_final_blocker_audit_record.json"
)
DATA_MUTATION_FREE_GROWTH_REPORT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gx_data_mutation_free_growth_test_report.json"
)
G4_G5_DEREFERENCE_WAIST_COURT_REPORT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gx_g4_g5_dereference_waist_court_report.json"
)
G8_READINESS_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g8_readiness_manifest.json"
G8_CROSS_METRIC_DIAGNOSIS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_cross_metric_diagnosis.json"
)
G8_DOMAIN_VS_SEARCH_CEILING_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_domain_vs_search_ceiling_gate.json"
)
G8_OPEN_QUESTION_ANSWER_LEDGER_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_open_question_answer_ledger.json"
)
G8_METRIC_GOVERNANCE_AUDIT_SURFACE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_metric_governance_audit_surface.json"
)
G8_CLOSEOUT_SIGNAL_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g8_closeout_signal_consumer_gate.json"
)
G1_SEARCH_RECALL_FRESHNESS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_search_recall_freshness.json"
)
G1_SUBSTRATE_SEARCH_LEDGERS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_substrate_search_ledgers.json"
)

GX_OUTPUT_PATHS: tuple[Path, ...] = (
    PINNED_REQUEST_PATH,
    CONCEPT_ALIAS_SEED_ROWS_PATH,
    CONCEPT_ALIAS_GRAPH_PATH,
    SCOPE_SEED_ROWS_PATH,
    DEMAND_PULL_REQUEST_PATH,
    RUNTIME_LITERAL_LINT_PATH,
    REDUCER_INTEGRITY_REPORT_PATH,
    POSITIVE_STATUS_PROVENANCE_PATH,
    PRODUCER_REGISTRY_PATH,
    PRODUCER_ROOT_CHAIN_REPORT_PATH,
    MEASUREMENT_REPLAY_REPORT_PATH,
    PERSISTED_STATUS_RECOMPUTE_DRIFT_PATH,
    STATUS_VOCABULARY_DELTA_PATH,
    CORRECTION_RETRACTION_LOG_PATH,
    INDEPENDENT_AUDIT_SAMPLE_PATH,
    VALIDATION_AUTHORITY_BOUNDARY_PATH,
    EXPECTED_RED_CHECKS_PATH,
    HUMAN_APPROVAL_RECEIPTS_PATH,
    VERTICAL_PINNED_ROUTE_REPORT_PATH,
    PROVISIONAL_PINNED_ROUTE_OUTCOME_PATH,
    PROVISIONAL_BLOCKER_AUDIT_RECORD_PATH,
    FINAL_PINNED_ROUTE_OUTCOME_PATH,
    FINAL_BLOCKER_AUDIT_RECORD_PATH,
    DATA_MUTATION_FREE_GROWTH_REPORT_PATH,
    G4_G5_DEREFERENCE_WAIST_COURT_REPORT_PATH,
)

DEFAULT_SCAN_ROOTS: tuple[Path, ...] = (
    Path("src/polisyos/core"),
    Path("src/polisyos/runtime"),
    Path("tools/quality/validation"),
    Path("tests/unit/runtime"),
    Path("tests/repo_quality"),
)
DEFAULT_ARTIFACT_GLOBS: tuple[str, ...] = (
    "architecture/policy_design_case/layer3_*.json",
    "architecture/policy_design_case/layer2_s14_*.json",
)

FORBIDDEN_DOMAIN_LITERALS: frozenset[str] = frozenset(
    {
        "firm_survival",
        "credit_access",
        "credit_program_enrollment",
        "ua-msme-affordable-loans-2022",
        "KNOWN_CONSTRUCTS",
        "REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS",
    }
)
POSITIVE_LITERAL_VALUES: frozenset[str] = frozenset(
    {
        "grounded_or_uncertain",
        "governed_promoted",
        "calibrated",
        "observable_calibrated",
        "grounded_limited",
        "grounded_abstention",
        "answered_currently_healthy",
        "currently_healthy",
        "pass",
    }
)
RUNTIME_POSITIVE_LITERAL_VALUES: frozenset[str] = POSITIVE_LITERAL_VALUES - {"pass"}
POSITIVE_STATUS_FIELDS: frozenset[str] = frozenset(
    {
        "status",
        "promotion_state",
        "conversion_outcome",
        "grounding_closure_outcome",
        "adapter_maturity",
        "forecast_tier",
        "search_recall_status",
        "index_freshness_status",
        "grounding_status",
    }
)
DIAGNOSTIC_POSITIVE_STATUS_FIELDS: frozenset[str] = frozenset(
    {"status", "search_recall_status", "index_freshness_status"}
)
AUTHORITY_POSITIVE_STATUS_FIELDS: frozenset[str] = (
    POSITIVE_STATUS_FIELDS - DIAGNOSTIC_POSITIVE_STATUS_FIELDS
)
PRODUCED_BY_REQUIRED_KEYS: frozenset[str] = frozenset(
    {"reducer_id", "reducer_version", "rule_version", "input_hashes", "output_hash"}
)
MEASUREMENT_REPLAY_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "measurement_id",
        "producer_ref",
        "producer_version",
        "corpus_ref",
        "corpus_path",
        "corpus_snapshot_hash",
        "query_or_probe",
        "execution_parameters",
        "expected_output_hash",
        "replay_command",
        "replay_environment",
    }
)
SHA256_RE = re.compile(r"sha256:([A-Za-z0-9._:-]*)")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
REPEATED64_RE = re.compile(r"^(.)\1{63}$")


@dataclass(frozen=True)
class PositiveStatus:
    """A positive persisted status found in a generated artifact."""

    artifact_path: str
    pointer: str
    field: str
    value: str
    record: Mapping[str, Any]


def validate_layer3_gx_hardening(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Build the Layer 3 GX hardening report and optionally persist sidecars."""

    root = Path(repo_root).resolve()
    artifact_paths = _default_artifact_paths(root)
    data_home_artifacts = build_layer3_gx_data_home_artifacts(root)
    data_home_artifacts_by_path = {
        PINNED_REQUEST_PATH: data_home_artifacts["layer3_gx_pinned_request"],
        CONCEPT_ALIAS_SEED_ROWS_PATH: data_home_artifacts["layer3_gx_concept_alias_seed_rows"],
        CONCEPT_ALIAS_GRAPH_PATH: data_home_artifacts["layer3_gx_concept_alias_graph"],
        SCOPE_SEED_ROWS_PATH: data_home_artifacts["layer3_gx_scope_seed_rows"],
        DEMAND_PULL_REQUEST_PATH: data_home_artifacts["layer3_gx_demand_pull_request"],
    }

    runtime_literal_lint = build_runtime_literal_lint(root)
    positive_status_provenance = build_positive_status_provenance(
        root,
        artifact_paths=artifact_paths,
    )
    producer_registry = build_producer_registry(
        root,
        artifact_paths=artifact_paths,
        extra_artifacts=data_home_artifacts_by_path,
    )
    producer_root_chain = build_producer_root_chain_report(
        root,
        artifact_paths=artifact_paths,
        producer_registry=producer_registry,
    )
    reducer_decision_report = build_layer3_gx_reducer_decision_report(root)
    reducer_integrity = build_reducer_integrity_report(
        positive_status_provenance,
        producer_root_chain=producer_root_chain,
        reducer_decision_report=reducer_decision_report,
    )
    measurement_replay = build_measurement_replay_report(
        root,
        producer_registry=producer_registry,
    )
    vertical_pinned_route = build_layer3_gx_vertical_pinned_route_report(root)
    provisional_blocker_audit_record = build_layer3_gx_provisional_blocker_audit_record(
        root,
        vertical_pinned_route=vertical_pinned_route,
    )
    provisional_pinned_route_outcome = build_layer3_gx_provisional_pinned_route_outcome_report(
        root,
        vertical_pinned_route=vertical_pinned_route,
        blocker_audit_record=provisional_blocker_audit_record,
    )
    final_blocker_audit_record = build_layer3_gx_final_blocker_audit_record(
        root,
        vertical_pinned_route=vertical_pinned_route,
        provisional_blocker_audit_record=provisional_blocker_audit_record,
    )
    final_pinned_route_outcome = build_layer3_gx_final_pinned_route_outcome_report(
        root,
        vertical_pinned_route=vertical_pinned_route,
        provisional_pinned_route_outcome=provisional_pinned_route_outcome,
        final_blocker_audit_record=final_blocker_audit_record,
    )
    data_mutation_free_growth = build_data_mutation_free_growth_test_report(root)
    g4_g5_waist_court = build_layer3_gx_g4_g5_dereference_waist_court_report(
        root,
        vertical_pinned_route=vertical_pinned_route,
    )
    recompute_drift = build_persisted_status_recompute_drift(
        root,
        artifact_paths=artifact_paths,
    )
    status_vocabulary_delta = build_status_vocabulary_delta()
    correction_retraction_log = build_correction_retraction_log(
        root,
        runtime_literal_lint=runtime_literal_lint,
    )
    independent_audit_sample = build_independent_audit_sample(positive_status_provenance)
    validation_authority_boundary = build_validation_authority_boundary(root)
    human_approval_receipts = build_human_approval_receipts(root)

    issues = _deduplicate_issues(
        [
            *runtime_literal_lint["issues"],
            *positive_status_provenance["issues"],
            *producer_registry["issues"],
            *producer_root_chain["issues"],
            *reducer_integrity["issues"],
            *measurement_replay["issues"],
            *recompute_drift["issues"],
            *correction_retraction_log["issues"],
            *_authority_boundary_issues(validation_authority_boundary),
            *human_approval_receipts["issues"],
            *data_mutation_free_growth["issues"],
        ]
    )
    expected_red_checks = build_expected_red_checks(
        issues,
        provisional_task12_complete=True,
        final_task12_complete=True,
    )
    expected_codes = {entry["code"] for entry in expected_red_checks["checks"]}
    issue_codes = {issue["code"] for issue in issues}
    status = "pass"
    if issues and issue_codes <= expected_codes:
        status = "expected_red"
    elif issues:
        status = "fail"

    artifacts = {
        "layer3_gx_baseline_note": _read_json(root / BASELINE_NOTE_PATH, default={}),
        **data_home_artifacts,
        "layer3_gx_runtime_literal_lint": runtime_literal_lint,
        "layer3_gx_reducer_integrity_report": reducer_integrity,
        "layer3_gx_positive_status_provenance": positive_status_provenance,
        "layer3_gx_producer_registry": producer_registry,
        "layer3_gx_producer_root_chain_report": producer_root_chain,
        "layer3_gx_measurement_replay_report": measurement_replay,
        "layer3_gx_vertical_pinned_route_report": vertical_pinned_route,
        "layer3_gx_provisional_pinned_route_outcome_report": (provisional_pinned_route_outcome),
        "layer3_gx_provisional_blocker_audit_record": (provisional_blocker_audit_record),
        "layer3_gx_final_pinned_route_outcome_report": final_pinned_route_outcome,
        "layer3_gx_final_blocker_audit_record": final_blocker_audit_record,
        "layer3_gx_data_mutation_free_growth_test_report": data_mutation_free_growth,
        "layer3_gx_g4_g5_dereference_waist_court_report": g4_g5_waist_court,
        "layer3_gx_persisted_status_recompute_drift": recompute_drift,
        "layer3_gx_status_vocabulary_delta": status_vocabulary_delta,
        "layer3_gx_correction_retraction_log": correction_retraction_log,
        "layer3_gx_independent_audit_sample": independent_audit_sample,
        "layer3_gx_validation_authority_boundary": validation_authority_boundary,
        "layer3_gx_expected_red_checks": expected_red_checks,
        "layer3_gx_human_approval_receipts": human_approval_receipts,
    }
    report = {
        "schema_version": "policyos.policy_design_case.layer3_gx_hardening.v1",
        "rule_version": "policyos.layer3.gx.hardening.v1",
        "status": status,
        "issues": issues,
        "summary": {
            "issue_count": len(issues),
            "expected_red_check_count": len(expected_red_checks["checks"]),
            "candidate_positive_status_count": positive_status_provenance[
                "candidate_positive_status_count"
            ],
            "positive_status_count": positive_status_provenance["positive_status_count"],
            "excluded_positive_status_count": positive_status_provenance[
                "excluded_candidate_count"
            ],
            "runtime_literal_issue_count": len(runtime_literal_lint["issues"]),
            "producer_count": producer_registry["producer_count"],
            "measurement_replay_status": measurement_replay["status"],
            "vertical_pinned_route_status": vertical_pinned_route["status"],
            "provisional_pinned_route_status": provisional_pinned_route_outcome["status"],
            "final_pinned_route_status": final_pinned_route_outcome["status"],
            "final_pinned_route_outcome": final_pinned_route_outcome["outcome_kind"],
            "final_g8_audit_status": final_blocker_audit_record["status"],
            "data_mutation_free_growth_status": data_mutation_free_growth["status"],
            "g4_g5_waist_court_status": g4_g5_waist_court["status"],
            "provisional_pinned_route_outcome": provisional_pinned_route_outcome[
                "g5_conversion_outcome"
            ],
            "legacy_green_slice_count": validation_authority_boundary["legacy_green_slice_count"],
        },
        "artifacts": artifacts,
        "written_artifact_paths": [],
        "write": write,
    }
    if write:
        report["written_artifact_paths"] = _write_artifacts(root, artifacts)
    return report


def build_runtime_literal_lint(
    repo_root: Path,
    *,
    scan_roots: Sequence[Path] = DEFAULT_SCAN_ROOTS,
) -> dict[str, Any]:
    """Run AST-based literal and digest lint over GX runtime surfaces."""

    root = Path(repo_root).resolve()
    issues: list[dict[str, Any]] = []
    scanned_files = 0
    parse_errors: list[dict[str, Any]] = []
    for file_path in _iter_python_files(root, scan_roots):
        scanned_files += 1
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            parse_errors.append(
                _issue(
                    "layer3_gx_runtime_literal_parse_error",
                    _relative(root, file_path),
                    f"Could not parse file for GX literal lint: {exc}",
                )
            )
            continue
        _attach_parent_links(tree)
        lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                issues.extend(_literal_issues(root, file_path, node, lines))
            issues.extend(_identifier_issues(root, file_path, node))
            if isinstance(node, ast.FunctionDef):
                issues.extend(_input_discard_issues(root, file_path, node))
            if isinstance(node, ast.AsyncFunctionDef):
                issues.extend(_input_discard_issues(root, file_path, node))
    normalized = _deduplicate_issues([*issues, *parse_errors])
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_runtime_literal_lint.v1",
        "status": "fail" if normalized else "pass",
        "scan_roots": [path.as_posix() for path in scan_roots],
        "scanned_file_count": scanned_files,
        "issues": normalized,
    }


def build_positive_status_provenance(
    repo_root: Path,
    *,
    artifact_paths: Sequence[Path] | None = None,
) -> dict[str, Any]:
    """Inventory positive persisted statuses and require reducer provenance."""

    root = Path(repo_root).resolve()
    candidates = _find_positive_status_candidates(root, artifact_paths=artifact_paths)
    positives = _production_positive_statuses(candidates)
    excluded_candidates = [
        _positive_status_classification_record(status)
        for status in candidates
        if not _is_production_positive_status(status)
    ]
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for status in positives:
        produced_by = status.record.get("produced_by")
        missing = _missing_produced_by_keys(produced_by)
        record = {
            "artifact_path": status.artifact_path,
            "json_pointer": status.pointer,
            "field": status.field,
            "value": status.value,
            "producer_ref": status.record.get("producer_ref"),
            "classification": "production_positive_status",
            "produced_by_present": isinstance(produced_by, Mapping),
            "missing_produced_by_keys": sorted(missing),
        }
        records.append(record)
        if missing:
            issues.append(
                _issue(
                    "layer3_gx_reducer_provenance_missing",
                    f"{status.artifact_path}{status.pointer}",
                    "Positive persisted Layer 3 status lacks complete reducer provenance.",
                    field=status.field,
                    value=status.value,
                    missing_produced_by_keys=sorted(missing),
                )
            )
    normalized = _deduplicate_issues(issues)
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_positive_status_provenance.v1",
        "status": "fail" if normalized else "pass",
        "candidate_positive_status_count": len(candidates),
        "positive_status_count": len(positives),
        "excluded_candidate_count": len(excluded_candidates),
        "excluded_candidate_records": excluded_candidates,
        "records": records,
        "issues": normalized,
    }


def build_persisted_status_recompute_drift(
    repo_root: Path,
    *,
    artifact_paths: Sequence[Path] | None = None,
) -> dict[str, Any]:
    """Recompute available positive-status output hashes and report drift."""

    root = Path(repo_root).resolve()
    positives = _find_positive_statuses(root, artifact_paths=artifact_paths)
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for status in positives:
        produced_by = status.record.get("produced_by")
        if _missing_produced_by_keys(produced_by):
            issues.append(
                _issue(
                    "layer3_gx_recompute_provenance_missing",
                    f"{status.artifact_path}{status.pointer}",
                    "Positive status cannot be recomputed without complete reducer provenance.",
                    field=status.field,
                    value=status.value,
                )
            )
            continue
        assert isinstance(produced_by, Mapping)
        expected = str(produced_by["output_hash"])
        recomputed = _hash_payload(_record_without_output_hash(status.record))
        drifted = expected != recomputed
        records.append(
            {
                "artifact_path": status.artifact_path,
                "json_pointer": status.pointer,
                "field": status.field,
                "value": status.value,
                "persisted_output_hash": expected,
                "recomputed_output_hash": recomputed,
                "drifted": drifted,
            }
        )
        if drifted:
            issues.append(
                _issue(
                    "layer3_gx_recompute_output_hash_mismatch",
                    f"{status.artifact_path}{status.pointer}",
                    "Persisted positive status output hash differs from recomputed payload hash.",
                    persisted_output_hash=expected,
                    recomputed_output_hash=recomputed,
                )
            )
    normalized = _deduplicate_issues(issues)
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_persisted_status_recompute_drift.v1",
        "status": "fail" if normalized else "pass",
        "records": records,
        "issues": normalized,
    }


def build_producer_registry(
    repo_root: Path,
    *,
    artifact_paths: Sequence[Path] | None = None,
    extra_artifacts: Mapping[Path, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a conservative producer registry from persisted producer refs."""

    root = Path(repo_root).resolve()
    producers: dict[str, dict[str, Any]] = {}
    existing = _read_json(root / PRODUCER_REGISTRY_PATH, default={})
    for row in _as_list(existing.get("producers")):
        if not isinstance(row, Mapping):
            continue
        producer_ref = str(row.get("producer_ref") or "")
        if producer_ref:
            producers[producer_ref] = dict(row)
    for path in artifact_paths or _default_artifact_paths(root):
        payload = _read_json(root / path, default=None)
        if payload is None:
            continue
        _collect_producers_from_payload(producers, path, payload)
    for path, payload in (extra_artifacts or {}).items():
        _collect_producers_from_payload(producers, path, payload)
    _collect_g1_measurement_producers(root, producers)
    issues = (
        [
            _issue(
                "layer3_gx_producer_registry_empty",
                PRODUCER_REGISTRY_PATH.as_posix(),
                "GX producer registry has no producer records.",
            )
        ]
        if not producers
        else []
    )
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_producer_registry.v1",
        "status": "fail" if issues else "pass",
        "producer_count": len(producers),
        "producers": sorted(producers.values(), key=lambda row: str(row["producer_ref"])),
        "issues": issues,
    }


def _collect_producers_from_payload(
    producers: dict[str, dict[str, Any]],
    path: Path,
    payload: Mapping[str, Any],
) -> None:
    for item, pointer in _walk_json(payload):
        if not isinstance(item, Mapping):
            continue
        producer_ref = str(item.get("producer_ref") or "")
        if not producer_ref:
            continue
        producers.setdefault(
            producer_ref,
            {
                "producer_ref": producer_ref,
                "producer_type": _infer_producer_type(producer_ref, item, path),
                "root_refs": _string_list(item.get("producer_root_refs"))
                or _string_list(item.get("root_refs")),
                "first_seen_path": path.as_posix(),
                "first_seen_pointer": pointer,
            },
        )


def _collect_g1_measurement_producers(
    repo_root: Path,
    producers: dict[str, dict[str, Any]],
) -> None:
    recall_path = G1_SEARCH_RECALL_FRESHNESS_PATH
    recall_payload = _as_mapping(_read_json(repo_root / recall_path, default={}))
    search_health = _as_mapping(recall_payload.get("search_recall_freshness"))
    recall_row = _g1_search_recall_measurement_row(repo_root, recall_path, search_health)
    if recall_row is not None:
        producers[str(recall_row["producer_ref"])] = recall_row

    ledgers_path = G1_SUBSTRATE_SEARCH_LEDGERS_PATH
    ledgers_payload = _as_mapping(_read_json(repo_root / ledgers_path, default={}))
    ledgers = [
        row for row in _as_list(ledgers_payload.get("search_ledgers")) if isinstance(row, Mapping)
    ]
    ledgers_row = _g1_search_ledgers_measurement_row(repo_root, ledgers_path, ledgers)
    if ledgers_row is not None:
        producers[str(ledgers_row["producer_ref"])] = ledgers_row


def _g1_search_recall_measurement_row(
    repo_root: Path,
    path: Path,
    search_health: Mapping[str, Any],
) -> dict[str, Any] | None:
    if not search_health:
        return None
    required = (
        search_health.get("corpus_ref"),
        search_health.get("canonical_corpus_path"),
        search_health.get("corpus_snapshot_hash"),
        search_health.get("replay_command"),
        search_health.get("replay_expected_output_hash"),
    )
    if any(value in (None, "", [], {}) for value in required):
        return None
    query_or_probe = {
        "measurement_provenance": search_health.get("measurement_provenance"),
        "query_trace_refs": _string_list(search_health.get("query_trace_refs")),
        "query_expansion_trace_refs": _string_list(
            search_health.get("query_expansion_trace_refs")
        ),
        "resolved_corpus_row_refs": _string_list(
            search_health.get("resolved_corpus_row_refs")
        ),
    }
    if not any(query_or_probe.values()):
        return None
    return {
        "producer_ref": "measurement://layer3-g1/l1-dcat-search-recall",
        "producer_type": "measurement",
        "measurement_id": "layer3-g1-l1-dcat-search-recall",
        "producer_version": _first_text(
            search_health.get("rule_version"),
            "policyos.layer3.g1.substrate_grounding_search.v1",
        ),
        "corpus_ref": str(search_health["corpus_ref"]),
        "corpus_path": str(search_health["canonical_corpus_path"]),
        "corpus_snapshot_hash": str(search_health["corpus_snapshot_hash"]),
        "query_or_probe": query_or_probe,
        "execution_parameters": {
            "artifact_ref": f"repo://{path.as_posix()}#search_recall_freshness",
            "artifact_hash": _hash_file(repo_root / path),
            "corpus_kind": _first_text(search_health.get("corpus_kind")),
            "search_recall_status": _first_text(search_health.get("search_recall_status")),
            "index_freshness_status": _first_text(
                search_health.get("index_freshness_status")
            ),
        },
        "expected_output_hash": str(search_health["replay_expected_output_hash"]),
        "replay_command": str(search_health["replay_command"]),
        "replay_environment": {
            "cwd": ".",
            "runner": "uv",
            "network_required": False,
            "writes_artifacts": True,
        },
        "root_refs": _dedupe_strings(
            (
                f"repo://{path.as_posix()}",
                search_health.get("corpus_ref"),
                search_health.get("corpus_snapshot_hash"),
            )
        ),
        "first_seen_path": path.as_posix(),
        "first_seen_pointer": "$.search_recall_freshness",
    }


def _g1_search_ledgers_measurement_row(
    repo_root: Path,
    path: Path,
    ledgers: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    if not ledgers:
        return None
    replayable_ledgers = [
        ledger
        for ledger in ledgers
        if all(
            ledger.get(key)
            for key in (
                "corpus_ref",
                "corpus_path",
                "corpus_snapshot_hash",
                "query_text",
                "query_hash",
                "replay_command",
                "replay_expected_output_hash",
            )
        )
    ]
    if not replayable_ledgers:
        return None
    first = replayable_ledgers[0]
    query_or_probe = [
        {
            "ledger_id": ledger.get("ledger_id"),
            "query_text": ledger.get("query_text"),
            "query_hash": ledger.get("query_hash"),
            "replay_key": ledger.get("replay_key"),
        }
        for ledger in replayable_ledgers
    ]
    return {
        "producer_ref": "measurement://layer3-g1/l1-dcat-search-ledgers",
        "producer_type": "measurement",
        "measurement_id": "layer3-g1-l1-dcat-search-ledgers",
        "producer_version": "policyos.layer3.g1.substrate_grounding_search.v1",
        "corpus_ref": str(first["corpus_ref"]),
        "corpus_path": str(first["corpus_path"]),
        "corpus_snapshot_hash": str(first["corpus_snapshot_hash"]),
        "query_or_probe": query_or_probe,
        "execution_parameters": {
            "artifact_ref": f"repo://{path.as_posix()}#search_ledgers",
            "artifact_hash": _hash_file(repo_root / path),
            "ledger_count": len(ledgers),
            "replayable_ledger_count": len(replayable_ledgers),
            "ledger_expected_output_hashes": [
                str(ledger["replay_expected_output_hash"]) for ledger in replayable_ledgers
            ],
        },
        "expected_output_hash": _hash_file(repo_root / path),
        "replay_command": str(first["replay_command"]),
        "replay_environment": {
            "cwd": ".",
            "runner": "uv",
            "network_required": False,
            "writes_artifacts": True,
        },
        "root_refs": _dedupe_strings(
            [
                f"repo://{path.as_posix()}",
                *(ledger.get("corpus_ref") for ledger in replayable_ledgers),
                *(ledger.get("corpus_snapshot_hash") for ledger in replayable_ledgers),
            ]
        ),
        "first_seen_path": path.as_posix(),
        "first_seen_pointer": "$.search_ledgers",
    }


def build_producer_root_chain_report(
    repo_root: Path,
    *,
    artifact_paths: Sequence[Path] | None = None,
    producer_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate positive-status producer chains terminate in valid roots."""

    root = Path(repo_root).resolve()
    registry_payload = (
        dict(producer_registry)
        if producer_registry is not None
        else build_producer_registry(root, artifact_paths=artifact_paths)
    )
    registry = {
        str(row.get("producer_ref")): row
        for row in _as_list(registry_payload.get("producers"))
        if isinstance(row, Mapping) and row.get("producer_ref")
    }
    positives = _find_positive_statuses(root, artifact_paths=artifact_paths)
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for status in positives:
        producer_ref = str(status.record.get("producer_ref") or "")
        producer = registry.get(producer_ref)
        producer_type = str((producer or {}).get("producer_type") or "untyped")
        valid = producer_type in {"measurement", "external_request"}
        record = {
            "artifact_path": status.artifact_path,
            "json_pointer": status.pointer,
            "field": status.field,
            "value": status.value,
            "producer_ref": producer_ref,
            "producer_type": producer_type,
            "classification": "production_positive_status",
            "valid_root_chain": valid,
        }
        records.append(record)
        if not valid:
            issues.append(
                _issue(
                    "layer3_gx_producer_root_invalid",
                    f"{status.artifact_path}{status.pointer}",
                    "Positive production status does not terminate in a valid measurement or external_request root.",
                    producer_ref=producer_ref,
                    producer_type=producer_type,
                )
            )
    normalized = _deduplicate_issues(issues)
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_producer_root_chain_report.v1",
        "status": "fail" if normalized else "pass",
        "records": records,
        "issues": normalized,
    }


def build_measurement_replay_report(
    repo_root: Path,
    *,
    producer_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate machine-replay contracts for measurement producer roots."""

    root = Path(repo_root).resolve()
    registry_payload = (
        dict(producer_registry) if producer_registry is not None else build_producer_registry(root)
    )
    measurements = [
        row
        for row in _as_list(registry_payload.get("producers"))
        if isinstance(row, Mapping) and row.get("producer_type") == "measurement"
    ]
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for producer in measurements:
        missing = sorted(key for key in MEASUREMENT_REPLAY_REQUIRED_KEYS if not producer.get(key))
        records.append(
            {
                "producer_ref": producer.get("producer_ref"),
                "missing_replay_keys": missing,
                "replayable": not missing,
            }
        )
        if missing:
            issues.append(
                _issue(
                    "layer3_gx_measurement_replay_contract_missing",
                    str(producer.get("producer_ref") or "$.producers[]"),
                    "Measurement root lacks the executable replay contract required by GX.",
                    missing_replay_keys=missing,
                )
            )
    if not measurements:
        issues.append(
            _issue(
                "layer3_gx_measurement_replay_not_measured",
                PRODUCER_REGISTRY_PATH.as_posix(),
                "No measurement roots are available for GX replay.",
            )
        )
    normalized = _deduplicate_issues(issues)
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_measurement_replay_report.v1",
        "status": "fail" if normalized else "pass",
        "measurement_root_count": len(measurements),
        "records": records,
        "issues": normalized,
    }


def build_layer3_gx_reducer_decision_report(repo_root: Path) -> dict[str, Any]:
    """Recompute Task 4 reducer decisions from persisted lower-level artifacts."""

    root = Path(repo_root).resolve()
    decisions = _build_required_reducer_decisions(root)
    records = [decision.model_dump(mode="json") for decision in decisions]
    issues = _reducer_manifest_override_issues(root, decisions)
    normalized = _deduplicate_issues(issues)
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_reducer_decision_report.v1",
        "rule_version": "policyos.layer3.gx.reducer_only_status.v1",
        "status": "fail" if normalized else "pass",
        "required_reducer_ids": [
            "reduce_g1_source_grounding_closure",
            "reduce_g2_forecast_admission",
            "reduce_g3_proof_authority",
            "reduce_gl_legal_authority",
            "reduce_g4_promotion_state",
            "reduce_g5_conversion_outcome",
            "reduce_g7_region_closure",
            "reduce_g8_domain_vs_search_ceiling",
        ],
        "decisions": records,
        "issues": normalized,
    }


def build_data_mutation_free_growth_test_report(repo_root: Path) -> dict[str, Any]:
    """Report Task 6 data-mutation free-growth test coverage."""

    root = Path(repo_root).resolve()
    coverage_rows = [
        _data_mutation_coverage_row(
            root,
            requirement_id="g1_dcat_metric_binding_insertion",
            test_refs=(
                "tests/unit/runtime/quality/test_layer3_g1_substrate_grounding.py::"
                "test_task6_g1_temp_dcat_metric_insertion_changes_candidates_without_authority",
            ),
            corpus_kind="temp_store",
            production_readiness_status="bounded_surrogate",
        ),
        _data_mutation_coverage_row(
            root,
            requirement_id="g2_skg_edge_no_calibration",
            test_refs=(
                "tests/unit/runtime/quality/test_layer3_g2_causal_forecast.py::"
                "test_task6_g2_temp_skg_edge_insertion_is_replayable_but_not_admitted_"
                "without_calibration",
            ),
            corpus_kind="temp_store",
        ),
        _data_mutation_coverage_row(
            root,
            requirement_id="g2_skg_edge_governed_calibration_admission",
            test_refs=(
                "tests/unit/runtime/quality/test_layer3_g2_causal_forecast.py::"
                "test_task6_g2_temp_skg_edge_plus_governed_calibration_changes_reducer_"
                "admission",
            ),
            corpus_kind="temp_store",
        ),
        _data_mutation_coverage_row(
            root,
            requirement_id="g3_ir_proof_candidate_no_certificate",
            test_refs=(
                "tests/unit/runtime/quality/test_layer3_g3_analytics_search.py::"
                "test_task6_g3_ir_proof_candidate_insertion_is_replayable_but_not_"
                "certificate_authority",
            ),
            corpus_kind="temp_store",
        ),
        _data_mutation_coverage_row(
            root,
            requirement_id="gl_legal_threshold_temporal_reissue_gate",
            test_refs=(
                "tests/unit/runtime/quality/test_layer3_gl_legal_mandate_search.py::"
                "test_task6_gl_temp_legal_threshold_insertion_is_replayable_with_"
                "temporal_reissue_gate",
            ),
            corpus_kind="temp_store",
        ),
        _data_mutation_coverage_row(
            root,
            requirement_id="g4_governed_upstream_artifact_promotion",
            test_refs=(
                "tests/unit/runtime/quality/test_layer3_g4_promotion_gate.py::"
                "test_task6_g4_governed_upstream_artifact_insertion_promotes_after_"
                "admission",
            ),
            corpus_kind="temp_repo",
        ),
        _data_mutation_coverage_row(
            root,
            requirement_id="g5_conversion_reducer_inputs_only",
            test_refs=(
                "tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py::"
                "test_task6_g5_conversion_changes_only_from_governed_reducer_inputs",
            ),
            corpus_kind="temp_repo",
        ),
        _data_mutation_coverage_row(
            root,
            requirement_id="g8_case_specific_search_health_diagnostic_data",
            test_refs=(
                "tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::"
                "test_task6_g8_pinned_case_search_health_changes_with_case_diagnostic_"
                "data",
            ),
            corpus_kind="temp_repo",
        ),
        _data_mutation_coverage_row(
            root,
            requirement_id="canonical_corpus_pinned_request_search_health",
            test_refs=(
                "tests/unit/runtime/quality/test_layer3_g1_substrate_grounding.py::"
                "test_substrate_search_adapter_builds_replayable_ledger_for_pinned_"
                "ukraine_construct",
            ),
            corpus_kind="canonical",
            requires_corpus_snapshot_hash=True,
        ),
        _data_mutation_coverage_row(
            root,
            requirement_id="g1_canonical_overlay_injection",
            test_refs=(
                "tests/unit/runtime/quality/test_layer3_g1_substrate_grounding.py::"
                "test_task6_g1_canonical_overlay_seed_is_recall_only_not_grounding",
            ),
            corpus_kind="canonical_with_isolated_overlay",
            production_readiness_status="bounded_surrogate",
        ),
    ]
    required_ids = tuple(row["requirement_id"] for row in coverage_rows)
    issues = [
        _issue(
            "layer3_gx_data_mutation_free_growth_test_missing",
            f"{DATA_MUTATION_FREE_GROWTH_REPORT_PATH.as_posix()}#{row['requirement_id']}",
            "Task 6 data-mutation free-growth coverage row has no resolvable test ref.",
            missing_test_refs=row["missing_test_refs"],
        )
        for row in coverage_rows
        if row["missing_test_refs"]
    ]
    missing_ids = [row["requirement_id"] for row in coverage_rows if row["missing_test_refs"]]
    normalized = _deduplicate_issues(issues)
    return {
        "schema_version": (
            "policyos.policy_design_case.layer3_gx_data_mutation_free_growth_test_report.v1"
        ),
        "rule_version": "policyos.layer3.gx.data_mutation_free_growth_tests.v1",
        "status": "fail" if normalized else "pass",
        "required_requirement_ids": list(required_ids),
        "missing_requirement_ids": missing_ids,
        "coverage_rows": coverage_rows,
        "authoritative_for": [],
        "may_not_use_for": [
            "claim_authority",
            "production_authority",
            "admission_authority",
            "promotion_authority",
            "conversion_authority",
        ],
        "issues": normalized,
    }


def build_layer3_gx_vertical_pinned_route_report(repo_root: Path) -> dict[str, Any]:
    """Run the minimal pinned G1 -> G4 -> G5 route through reducers."""

    root = Path(repo_root).resolve()
    data_home = load_layer3_gx_data_home(root)
    case_id = (
        data_home.pinned_request.case_id
        if data_home.pinned_request is not None
        else "missing-pinned-case"
    )
    g1_manifest_path = POLICY_DESIGN_CASE_DIR / "layer3_g1_readiness_manifest.json"
    g1_contracts_path = POLICY_DESIGN_CASE_DIR / "layer3_g1_grounded_source_contracts.json"
    g1_recall_path = POLICY_DESIGN_CASE_DIR / "layer3_g1_search_recall_freshness.json"
    g1_ledgers_path = POLICY_DESIGN_CASE_DIR / "layer3_g1_substrate_search_ledgers.json"

    g1_manifest = _as_mapping(_read_json(root / g1_manifest_path, default={}))
    g1_counts = _as_mapping(g1_manifest.get("counts"))
    g1_contracts = _as_mapping(_read_json(root / g1_contracts_path, default={}))
    g1_contract_payload = _as_mapping(g1_contracts.get("grounded_source_contracts") or g1_contracts)
    g1_bindings = _as_list(g1_contract_payload.get("bindings"))
    g1_recall_payload = _as_mapping(_read_json(root / g1_recall_path, default={}))
    g1_search_health = _as_mapping(g1_recall_payload.get("search_recall_freshness"))
    g1_ledgers_payload = _as_mapping(_read_json(root / g1_ledgers_path, default={}))
    g1_ledgers = _as_list(g1_ledgers_payload.get("search_ledgers"))
    g1_measurement_refs = (
        _vertical_artifact_input_ref(
            root,
            g1_recall_path,
            producer_ref="measurement://layer3-g1/l1-dcat-search-recall",
            producer_type="measurement",
            producer_root_refs=(
                _first_text(g1_search_health.get("corpus_ref")),
                _first_text(g1_search_health.get("corpus_snapshot_hash")),
            ),
        ),
        _vertical_artifact_input_ref(
            root,
            g1_ledgers_path,
            producer_ref="measurement://layer3-g1/l1-dcat-search-ledgers",
            producer_type="measurement",
            producer_root_refs=(
                _first_text(g1_search_health.get("corpus_ref")),
                _first_text(g1_search_health.get("corpus_snapshot_hash")),
            ),
        ),
        _vertical_artifact_input_ref(
            root,
            g1_contracts_path,
            producer_ref="measurement://layer3-g1/source-contract-materialization",
            producer_type="measurement",
            producer_root_refs=(
                _first_text(g1_search_health.get("corpus_ref")),
                _first_text(g1_search_health.get("corpus_snapshot_hash")),
            ),
        ),
    )
    g1_decision = reduce_g1_source_grounding_closure(
        G1SourceGroundingClosureInputs(
            canonical_store=_first_text(g1_search_health.get("corpus_kind")) == "canonical",
            binding_count=len(g1_bindings),
            binding_statuses=tuple(
                str(_as_mapping(binding).get("grounding_status") or "grounded")
                for binding in g1_bindings
                if isinstance(binding, Mapping)
            ),
            measured_no_hit=not g1_bindings and bool(g1_ledgers),
            search_recall_status=_first_text(
                g1_search_health.get("search_recall_status"),
                g1_counts.get("g1_search_recall_status"),
                "not_measured",
            ),
            index_freshness_status=_first_text(
                g1_search_health.get("index_freshness_status"),
                g1_counts.get("g1_index_freshness_status"),
                "not_measured",
            ),
            overlay_injection_status=(
                "pass"
                if int(g1_counts.get("resolver_binding_consumed_count") or 0) > 0
                else "not_measured"
            ),
            abstention_vocabulary_approved=_gx_abstention_candidate_approved(root),
            input_refs=g1_measurement_refs,
        )
    )

    pinned_request_ref = _vertical_artifact_input_ref(
        root,
        PINNED_REQUEST_PATH,
        producer_ref=(
            data_home.pinned_request.producer_ref
            if data_home.pinned_request is not None
            else "external-request://layer3-gx/pinned-request/missing"
        ),
        producer_type="external_request",
        producer_root_refs=(
            data_home.pinned_request.producer_ref
            if data_home.pinned_request is not None
            else "external-request://layer3-gx/pinned-request/missing"
        ),
        supply_side=False,
    )
    g4_request = (
        data_home.pinned_request.g4_promotion_requests[0]
        if data_home.pinned_request is not None and data_home.pinned_request.g4_promotion_requests
        else {}
    )
    g4_blockers = [
        *g1_decision.blocker_refs,
        *(("layer3_g4_missing_g1_grounded_source_contract",) if not g1_bindings else ()),
    ]
    source_design_record = _as_mapping(g4_request.get("source_design_record"))
    if source_design_record.get("payload_status") in {"unresolved", "ref_only"}:
        g4_blockers.append("layer3_g4_source_design_record_unresolved")
    g4_decision = reduce_g4_promotion_state(
        G4PromotionStateInputs(
            dependency_statuses=(g1_decision.readiness_status,),
            blocker_refs=tuple(g4_blockers),
            input_refs=(
                pinned_request_ref,
                *g1_measurement_refs,
            ),
        )
    )

    demand_request_ref = _vertical_artifact_input_ref(
        root,
        DEMAND_PULL_REQUEST_PATH,
        producer_ref=(
            data_home.demand_pull_request.producer_ref
            if data_home.demand_pull_request is not None
            else "external-request://layer3-gx/demand-pull/missing"
        ),
        producer_type="external_request",
        producer_root_refs=(
            data_home.demand_pull_request.producer_ref
            if data_home.demand_pull_request is not None
            else "external-request://layer3-gx/demand-pull/missing"
        ),
        supply_side=False,
    )
    demand_pull_status = (
        "pass"
        if data_home.demand_pull_request is not None and data_home.demand_pull_request.demand_refs
        else "missing"
    )
    g5_decision = reduce_g5_conversion_outcome(
        G5ConversionOutcomeInputs(
            requested_conversion_outcome="grounded_abstention",
            g4_promotion_state=g4_decision.status,
            g1_grounding_closure=g1_decision.status,
            demand_pull_status=demand_pull_status,
            cross_slice_status="pass" if g4_decision.status == "governed_promoted" else "fail",
            grounded_evidence_ref_count=len(g1_bindings),
            input_refs=(
                demand_request_ref,
                _vertical_reducer_decision_input_ref(g1_decision),
                _vertical_reducer_decision_input_ref(g4_decision),
                *g1_measurement_refs,
            ),
        )
    )
    decisions = (g1_decision, g4_decision, g5_decision)
    next_blockers = tuple(
        dict.fromkeys(
            blocker
            for decision in (g5_decision, g4_decision, g1_decision)
            for blocker in decision.blocker_refs
        )
    )
    status = (
        "pass" if g5_decision.status in {"grounded_limited", "grounded_abstention"} else "blocked"
    )
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_vertical_pinned_route.v1",
        "rule_version": "policyos.layer3.gx.vertical_pinned_route.v1",
        "status": status,
        "case_id": case_id,
        "request_ref": (
            data_home.pinned_request.request_ref if data_home.pinned_request is not None else ""
        ),
        "data_home_status": data_home.status,
        "g1_search_measurement_status": (
            "pass"
            if g1_decision.issue_codes
            and "layer3_gx_inline_input_forbidden" not in g1_decision.issue_codes
            and _first_text(g1_search_health.get("search_recall_status")) == "pass"
            and _first_text(g1_search_health.get("index_freshness_status")) == "pass"
            else "blocked"
        ),
        "g1_grounding_closure": g1_decision.status,
        "g4_promotion_state": g4_decision.status,
        "final_outcome": g5_decision.status,
        "route_replay_key": f"layer3-gx-vertical-pinned-route:{case_id}:v1",
        "route_steps": [
            "layer3_gx_pinned_request",
            "g1_canonical_dcat_search_ledger",
            "g1_measured_recall_freshness",
            "g4_reducer_promotion_state",
            "layer3_gx_demand_pull_request",
            "g5_reducer_conversion_outcome",
        ],
        "decisions": [decision.model_dump(mode="json") for decision in decisions],
        "next_blocker_refs": list(next_blockers),
        "issue_codes": list(
            dict.fromkeys(issue for decision in decisions for issue in decision.issue_codes)
        ),
        "may_not_use_for": [
            "production_authority",
            "production_claim_authority",
            "rollout_authority",
            "publication_authority",
            "runtime_closeout_authority",
            "useful_design_credit",
            "domain_ceiling_authority_without_gate",
        ],
    }


def build_layer3_gx_g4_g5_dereference_waist_court_report(
    repo_root: Path,
    *,
    vertical_pinned_route: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Expose GX Task 9 G4/G5 waist-court dereference diagnostics."""

    root = Path(repo_root).resolve()
    data_home = load_layer3_gx_data_home(root)
    route = _as_mapping(vertical_pinned_route or build_layer3_gx_vertical_pinned_route_report(root))
    decisions = {
        _first_text(row.get("reducer_id")): _as_mapping(row)
        for row in _as_list(route.get("decisions"))
        if isinstance(row, Mapping)
    }
    g4_decision = decisions.get("reduce_g4_promotion_state", {})
    g5_decision = decisions.get("reduce_g5_conversion_outcome", {})
    g4_input_refs = _string_list(g4_decision.get("input_refs"))
    g5_input_refs = _string_list(g5_decision.get("input_refs"))
    demand = data_home.demand_pull_request
    demand_metadata_complete = bool(
        demand
        and demand.producer_ref
        and demand.source
        and demand.timestamp
        and demand.request_source_ref
        and demand.replay_key
        and demand.consumer_path
    )
    issue_codes = ["layer3_gx_task9_multi_family_pending"]
    if not g4_input_refs:
        issue_codes.append("layer3_gx_task9_g4_input_refs_missing")
    if not g5_input_refs:
        issue_codes.append("layer3_gx_task9_g5_input_refs_missing")
    if not demand_metadata_complete:
        issue_codes.append("layer3_gx_task9_demand_pull_artifact_metadata_missing")
    report = {
        "schema_version": (
            "policyos.policy_design_case.layer3_gx_g4_g5_dereference_waist_court.v1"
        ),
        "rule_version": "policyos.layer3.gx.g4_g5_waist_court.v1",
        "task_id": "GX Task 9",
        "status": "partial",
        "scope": "gx_vertical_pinned_route_only",
        "case_id": route.get("case_id") or "",
        "request_ref": route.get("request_ref") or "",
        "scientist_policy_design_bundle_location": "GY",
        "g4": {
            "reducer_id": "reduce_g4_promotion_state",
            "status": g4_decision.get("status") or "promotion_blocked",
            "readiness_status": g4_decision.get("readiness_status") or "fail",
            "input_ref_status": "pass" if g4_input_refs else "blocked",
            "input_refs": g4_input_refs,
            "blocker_refs": _string_list(g4_decision.get("blocker_refs")),
            "issue_codes": _string_list(g4_decision.get("issue_codes")),
            "can_synthesize_source_contracts": False,
            "can_synthesize_design_records": False,
        },
        "g5": {
            "reducer_id": "reduce_g5_conversion_outcome",
            "status": g5_decision.get("status") or "unchanged_blocker",
            "readiness_status": g5_decision.get("readiness_status") or "fail",
            "input_ref_status": "pass" if g5_input_refs else "blocked",
            "input_refs": g5_input_refs,
            "blocker_refs": _string_list(g5_decision.get("blocker_refs")),
            "issue_codes": _string_list(g5_decision.get("issue_codes")),
            "demand_pull_artifact_metadata_status": (
                "pass" if demand_metadata_complete else "blocked"
            ),
            "demand_pull_artifact_ref": f"repo://{DEMAND_PULL_REQUEST_PATH.as_posix()}",
            "bare_s3_demand_pull_ref_policy": "blocked_until_produced_artifact",
            "can_synthesize_evidence_rows": False,
            "can_synthesize_promotion_facts": False,
        },
        "authority_posture": "diagnostic_only",
        "authoritative_for": ["gx_task9_g4_g5_waist_court_diagnostics"],
        "may_not_use_for": [
            "claim_authority",
            "production_authority",
            "promotion_authority",
            "conversion_authority",
            "useful_design_credit",
            "publication_authority",
            "runtime_closeout_authority",
        ],
        "issue_codes": list(dict.fromkeys(issue_codes)),
    }
    report["report_hash"] = _hash_payload(report)
    return report


def build_layer3_gx_provisional_blocker_audit_record(
    repo_root: Path,
    *,
    vertical_pinned_route: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the provisional Task 12 blocker-specific audit record."""

    root = Path(repo_root).resolve()
    route = _as_mapping(vertical_pinned_route or build_layer3_gx_vertical_pinned_route_report(root))
    next_blockers = _string_list(route.get("next_blocker_refs"))
    cited_artifact_refs = [
        f"repo://{VERTICAL_PINNED_ROUTE_REPORT_PATH.as_posix()}",
        "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json",
        "repo://architecture/policy_design_case/layer3_g1_substrate_search_ledgers.json",
        "repo://architecture/policy_design_case/layer3_g1_grounded_source_contracts.json",
        f"repo://{PINNED_REQUEST_PATH.as_posix()}",
        f"repo://{DEMAND_PULL_REQUEST_PATH.as_posix()}",
    ]
    blocker_specific_search_status = (
        "measured_no_hit"
        if route.get("g1_search_measurement_status") == "pass"
        and route.get("g1_grounding_closure") == "typed_blocker"
        else "not_measured"
    )
    record = {
        "schema_version": ("policyos.policy_design_case.layer3_gx_provisional_blocker_audit.v1"),
        "rule_version": "policyos.layer3.gx.provisional_task12.v1",
        "audit_phase": "provisional_task12",
        "status": route.get("status") or "blocked",
        "answer_status": (
            "blocked_not_currently_publishable"
            if route.get("status") == "blocked"
            else "candidate_requires_final_g8_audit"
        ),
        "case_id": route.get("case_id") or "",
        "request_ref": route.get("request_ref") or "",
        "route_replay_key": route.get("route_replay_key") or "",
        "g8_open_question_surface_status": "not_required_until_task11",
        "blocker_specific_search_status": blocker_specific_search_status,
        "g1_search_measurement_status": route.get("g1_search_measurement_status") or "blocked",
        "g1_grounding_closure": route.get("g1_grounding_closure") or "typed_blocker",
        "g4_promotion_state": route.get("g4_promotion_state") or "promotion_blocked",
        "g5_conversion_outcome": route.get("final_outcome") or "unchanged_blocker",
        "next_blocker_refs": next_blockers,
        "cited_artifact_refs": cited_artifact_refs,
        "audit_basis": {
            "canonical_search_measured": route.get("g1_search_measurement_status") == "pass",
            "source_contract_materialized": route.get("g1_grounding_closure")
            in {"grounded_or_uncertain", "grounded_abstention_candidate"},
            "promotion_allowed": route.get("g4_promotion_state") == "governed_promoted",
            "conversion_allowed": route.get("final_outcome")
            in {"grounded_limited", "grounded_abstention"},
        },
        "may_not_use_for": [
            "production_authority",
            "production_claim_authority",
            "rollout_authority",
            "publication_authority",
            "runtime_closeout_authority",
            "useful_design_credit",
            "domain_ceiling_authority_without_gate",
        ],
    }
    record["audit_record_hash"] = _hash_payload(record)
    return record


def build_layer3_gx_provisional_pinned_route_outcome_report(
    repo_root: Path,
    *,
    vertical_pinned_route: Mapping[str, Any] | None = None,
    blocker_audit_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist the provisional Task 12 pinned-route reducer outcome."""

    root = Path(repo_root).resolve()
    route = _as_mapping(vertical_pinned_route or build_layer3_gx_vertical_pinned_route_report(root))
    audit = _as_mapping(
        blocker_audit_record
        or build_layer3_gx_provisional_blocker_audit_record(
            root,
            vertical_pinned_route=route,
        )
    )
    reducer_calls = []
    for decision in _as_list(route.get("decisions")):
        row = _as_mapping(decision)
        produced_by = _as_mapping(row.get("produced_by"))
        reducer_calls.append(
            {
                "reducer_id": row.get("reducer_id") or "",
                "status_field": row.get("status_field") or "",
                "status": row.get("status") or "",
                "readiness_status": row.get("readiness_status") or "",
                "rule_version": row.get("rule_version") or "",
                "input_refs": _string_list(row.get("input_refs")),
                "input_hashes": dict(_as_mapping(row.get("input_hashes"))),
                "output_hash": produced_by.get("output_hash") or "",
                "persisted_status_ref": (
                    f"repo://{VERTICAL_PINNED_ROUTE_REPORT_PATH.as_posix()}"
                    f"#decisions/{len(reducer_calls)}"
                ),
            }
        )
    g5_outcome = _first_text(route.get("final_outcome"), "unchanged_blocker")
    outcome_kind = (
        g5_outcome
        if g5_outcome
        in {"grounded_limited", "grounded_abstention", "search_ceiling_repair_required"}
        else "typed_blocker"
    )
    report = {
        "schema_version": (
            "policyos.policy_design_case.layer3_gx_provisional_pinned_route_outcome.v1"
        ),
        "rule_version": "policyos.layer3.gx.provisional_task12.v1",
        "run_phase": "provisional_task12",
        "status": route.get("status") or "blocked",
        "outcome_kind": outcome_kind,
        "outcome_source": "reduce_g5_conversion_outcome",
        "case_id": route.get("case_id") or "",
        "request_ref": route.get("request_ref") or "",
        "route_replay_key": route.get("route_replay_key") or "",
        "data_home_status": route.get("data_home_status") or "blocked",
        "g1_search_measurement_status": route.get("g1_search_measurement_status") or "blocked",
        "g1_grounding_closure": route.get("g1_grounding_closure") or "typed_blocker",
        "g4_promotion_state": route.get("g4_promotion_state") or "promotion_blocked",
        "g5_conversion_outcome": g5_outcome,
        "useful_design_credit": False,
        "reducer_calls": reducer_calls,
        "persisted_artifact_refs": [
            f"repo://{VERTICAL_PINNED_ROUTE_REPORT_PATH.as_posix()}",
            f"repo://{PROVISIONAL_BLOCKER_AUDIT_RECORD_PATH.as_posix()}",
            f"repo://{PINNED_REQUEST_PATH.as_posix()}",
            f"repo://{DEMAND_PULL_REQUEST_PATH.as_posix()}",
            "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json",
            "repo://architecture/policy_design_case/layer3_g1_substrate_search_ledgers.json",
            "repo://architecture/policy_design_case/layer3_g1_grounded_source_contracts.json",
        ],
        "blocker_audit_ref": (f"repo://{PROVISIONAL_BLOCKER_AUDIT_RECORD_PATH.as_posix()}"),
        "blocker_audit_hash": audit.get("audit_record_hash") or "",
        "next_missing_refs": _string_list(route.get("next_blocker_refs")),
        "issue_codes": _string_list(route.get("issue_codes")),
        "may_not_use_for": _string_list(route.get("may_not_use_for")),
    }
    report["provisional_run_hash"] = _hash_payload(report)
    return report


def build_layer3_gx_final_blocker_audit_record(
    repo_root: Path,
    *,
    vertical_pinned_route: Mapping[str, Any] | None = None,
    provisional_blocker_audit_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the final Task 12 blocker audit after the Task 11 G8 surface."""

    root = Path(repo_root).resolve()
    route = _as_mapping(vertical_pinned_route or build_layer3_gx_vertical_pinned_route_report(root))
    provisional_audit = _as_mapping(
        provisional_blocker_audit_record
        or build_layer3_gx_provisional_blocker_audit_record(
            root,
            vertical_pinned_route=route,
        )
    )
    g8_artifacts = _gx_final_task12_g8_artifacts(root)
    readiness = g8_artifacts["readiness_manifest"]
    domain_gate = g8_artifacts["domain_vs_search_ceiling_gate"]
    open_question_ledger = g8_artifacts["open_question_answer_ledger"]
    audit_surface = g8_artifacts["metric_governance_audit_surface"]
    closeout_gate = g8_artifacts["closeout_signal_consumer_gate"]
    classification = _gx_final_task12_search_health_classification(g8_artifacts)
    preconditions = _as_mapping(domain_gate.get("domain_ceiling_precondition_statuses"))
    search_answer = _gx_open_question_answer(open_question_ledger, "8.4-search-recall-freshness")
    g8_issue_codes = _gx_final_task12_g8_issue_codes(g8_artifacts)
    route_issue_codes = _string_list(route.get("issue_codes"))
    issue_codes = _dedupe_strings(
        (
            *route_issue_codes,
            *g8_issue_codes,
            *_string_list(classification.get("issue_codes")),
            *_string_list(search_answer.get("issue_codes")),
        )
    )
    next_blockers = _dedupe_strings(
        (
            *_string_list(route.get("next_blocker_refs")),
            *issue_codes,
            "layer3_g8_blocker_specific_search_diagnostic_missing"
            if _first_text(classification.get("current_blocker_status"), "unmeasured") != "pass"
            else "",
        )
    )
    domain_status = _first_text(
        domain_gate.get("status"),
        audit_surface.get("domain_vs_search_ceiling_status"),
        "search_ceiling_repair_required",
    )
    open_question_status = _first_text(open_question_ledger.get("status"), "blocked")
    status = (
        "pass"
        if route.get("status") == "pass"
        and domain_status == "domain_ceiling_supported"
        and open_question_status == "pass"
        else "blocked"
    )
    record = {
        "schema_version": "policyos.policy_design_case.layer3_gx_final_blocker_audit.v1",
        "rule_version": "policyos.layer3.gx.final_task12.v1",
        "audit_phase": "final_task12",
        "status": status,
        "answer_status": (
            "candidate_requires_replay"
            if status == "pass"
            else "blocked_not_currently_publishable"
        ),
        "case_id": route.get("case_id") or "",
        "request_ref": route.get("request_ref") or "",
        "route_replay_key": route.get("route_replay_key") or "",
        "provisional_audit_ref": f"repo://{PROVISIONAL_BLOCKER_AUDIT_RECORD_PATH.as_posix()}",
        "provisional_g8_open_question_surface_status": (
            provisional_audit.get("g8_open_question_surface_status") or ""
        ),
        "g8_open_question_surface_status": open_question_status,
        "blocker_specific_search_status": _first_text(
            classification.get("current_blocker_status"),
            "unmeasured",
        ),
        "g8_domain_vs_search_ceiling_status": domain_status,
        "g8_domain_ceiling_claim_allowed": bool(domain_gate.get("domain_ceiling_claim_allowed")),
        "g8_readiness_status": readiness.get("status") or "fail",
        "g8_metric_governance_audit_surface_status": audit_surface.get("status") or "blocked",
        "g8_closeout_signal_consumer_status": closeout_gate.get("status") or "blocked",
        "g8_search_health_classification": dict(classification),
        "g8_domain_ceiling_precondition_statuses": dict(preconditions),
        "g8_search_recall_freshness_answer": dict(search_answer),
        "g1_search_measurement_status": route.get("g1_search_measurement_status") or "blocked",
        "g1_grounding_closure": route.get("g1_grounding_closure") or "typed_blocker",
        "g4_promotion_state": route.get("g4_promotion_state") or "promotion_blocked",
        "g5_conversion_outcome": route.get("final_outcome") or "unchanged_blocker",
        "next_blocker_refs": next_blockers,
        "issue_codes": issue_codes,
        "cited_artifact_refs": _dedupe_strings(
            (
                f"repo://{VERTICAL_PINNED_ROUTE_REPORT_PATH.as_posix()}",
                f"repo://{PROVISIONAL_BLOCKER_AUDIT_RECORD_PATH.as_posix()}",
                *_gx_final_task12_g8_artifact_refs(),
                f"repo://{PINNED_REQUEST_PATH.as_posix()}",
                f"repo://{DEMAND_PULL_REQUEST_PATH.as_posix()}",
            )
        ),
        "g8_required_audit_refs": _gx_final_task12_required_audit_refs(),
        "audit_basis": {
            "task11_g8_surface_consumed": True,
            "blocker_specific_search_measured": (
                _first_text(classification.get("current_blocker_status")) == "pass"
                and _first_text(classification.get("freshness_status")) == "pass"
            ),
            "domain_ceiling_claim_allowed": bool(domain_gate.get("domain_ceiling_claim_allowed")),
            "closeout_consumer_gate_status": closeout_gate.get("status") or "blocked",
            "g8_is_audit_evidence_only": True,
            "can_use_g8_for_closeout_authority": False,
        },
        "authoritative_for": [
            "gx_final_task12_blocker_specific_audit",
            "gx_final_task12_replay_diagnostic",
        ],
        "may_not_use_for": _gx_task12_may_not_use_for(
            route,
            readiness,
            audit_surface,
            closeout_gate,
        ),
    }
    record["audit_record_hash"] = _hash_payload(record)
    return record


def build_layer3_gx_final_pinned_route_outcome_report(
    repo_root: Path,
    *,
    vertical_pinned_route: Mapping[str, Any] | None = None,
    provisional_pinned_route_outcome: Mapping[str, Any] | None = None,
    final_blocker_audit_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist the final Task 12 pinned-route outcome after G8 audit consumption."""

    root = Path(repo_root).resolve()
    route = _as_mapping(vertical_pinned_route or build_layer3_gx_vertical_pinned_route_report(root))
    provisional = _as_mapping(
        provisional_pinned_route_outcome
        or build_layer3_gx_provisional_pinned_route_outcome_report(
            root,
            vertical_pinned_route=route,
        )
    )
    audit = _as_mapping(
        final_blocker_audit_record
        or build_layer3_gx_final_blocker_audit_record(
            root,
            vertical_pinned_route=route,
        )
    )
    g8_artifacts = _gx_final_task12_g8_artifacts(root)
    domain_gate = g8_artifacts["domain_vs_search_ceiling_gate"]
    open_question_ledger = g8_artifacts["open_question_answer_ledger"]
    audit_surface = g8_artifacts["metric_governance_audit_surface"]
    closeout_gate = g8_artifacts["closeout_signal_consumer_gate"]
    classification = _gx_final_task12_search_health_classification(g8_artifacts)
    g8_decision = _gx_final_task12_g8_reducer_decision(
        root,
        route=route,
        classification=classification,
    )
    reducer_calls = [
        _gx_reducer_call_row(
            _as_mapping(decision),
            (
                f"repo://{VERTICAL_PINNED_ROUTE_REPORT_PATH.as_posix()}"
                f"#decisions/{index}"
            ),
        )
        for index, decision in enumerate(_as_list(route.get("decisions")))
        if isinstance(decision, Mapping)
    ]
    reducer_calls.append(
        _gx_reducer_call_row(
            g8_decision.model_dump(mode="json"),
            f"repo://{FINAL_PINNED_ROUTE_OUTCOME_PATH.as_posix()}#g8_domain_vs_search_ceiling",
        )
    )
    g5_outcome = _first_text(route.get("final_outcome"), "unchanged_blocker")
    if g8_decision.status == "search_ceiling_repair_required":
        outcome_kind = "search_ceiling_repair_required"
    elif g5_outcome in {"grounded_limited", "grounded_abstention"}:
        outcome_kind = g5_outcome
    else:
        outcome_kind = "typed_blocker"
    status = (
        "pass"
        if outcome_kind in {"grounded_limited", "grounded_abstention"}
        and g8_decision.readiness_status == "pass"
        else "blocked"
    )
    issue_codes = _dedupe_strings(
        (
            *_string_list(route.get("issue_codes")),
            *_string_list(audit.get("issue_codes")),
            *_string_list(g8_decision.issue_codes),
            *_gx_final_task12_g8_issue_codes(g8_artifacts),
        )
    )
    next_missing_refs = _dedupe_strings(
        (
            *_string_list(route.get("next_blocker_refs")),
            *_string_list(audit.get("next_blocker_refs")),
            *_string_list(g8_decision.blocker_refs),
            *issue_codes,
        )
    )
    report = {
        "schema_version": "policyos.policy_design_case.layer3_gx_final_pinned_route_outcome.v1",
        "rule_version": "policyos.layer3.gx.final_task12.v1",
        "run_phase": "final_task12",
        "status": status,
        "outcome_kind": outcome_kind,
        "outcome_source": "reduce_g5_conversion_outcome+reduce_g8_domain_vs_search_ceiling",
        "case_id": route.get("case_id") or "",
        "request_ref": route.get("request_ref") or "",
        "route_replay_key": route.get("route_replay_key") or "",
        "data_home_status": route.get("data_home_status") or "blocked",
        "g1_search_measurement_status": route.get("g1_search_measurement_status") or "blocked",
        "g1_grounding_closure": route.get("g1_grounding_closure") or "typed_blocker",
        "g4_promotion_state": route.get("g4_promotion_state") or "promotion_blocked",
        "g5_conversion_outcome": g5_outcome,
        "g8_domain_vs_search_ceiling_status": g8_decision.status,
        "g8_open_question_answer_status": open_question_ledger.get("status") or "blocked",
        "g8_metric_governance_audit_surface_status": audit_surface.get("status") or "blocked",
        "g8_closeout_signal_consumer_status": closeout_gate.get("status") or "blocked",
        "g8_search_health_classification": dict(classification),
        "g8_domain_ceiling_precondition_statuses": dict(
            _as_mapping(domain_gate.get("domain_ceiling_precondition_statuses"))
        ),
        "useful_design_credit": False,
        "reducer_calls": reducer_calls,
        "persisted_artifact_refs": _dedupe_strings(
            (
                f"repo://{VERTICAL_PINNED_ROUTE_REPORT_PATH.as_posix()}",
                f"repo://{PROVISIONAL_PINNED_ROUTE_OUTCOME_PATH.as_posix()}",
                f"repo://{FINAL_BLOCKER_AUDIT_RECORD_PATH.as_posix()}",
                f"repo://{PINNED_REQUEST_PATH.as_posix()}",
                f"repo://{DEMAND_PULL_REQUEST_PATH.as_posix()}",
                "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json",
                "repo://architecture/policy_design_case/layer3_g1_substrate_search_ledgers.json",
                "repo://architecture/policy_design_case/layer3_g1_grounded_source_contracts.json",
                *_gx_final_task12_g8_artifact_refs(),
            )
        ),
        "g8_required_audit_refs": _gx_final_task12_required_audit_refs(),
        "g8_audit_ref": f"repo://{FINAL_BLOCKER_AUDIT_RECORD_PATH.as_posix()}",
        "g8_audit_hash": audit.get("audit_record_hash") or "",
        "provisional_run_ref": f"repo://{PROVISIONAL_PINNED_ROUTE_OUTCOME_PATH.as_posix()}",
        "next_missing_refs": next_missing_refs,
        "issue_codes": issue_codes,
        "authoritative_for": [
            "gx_final_task12_pinned_route_replay",
            "gx_final_task12_reducer_outcome_audit",
        ],
        "may_not_use_for": _gx_task12_may_not_use_for(
            route,
            g8_artifacts["readiness_manifest"],
            audit_surface,
            closeout_gate,
        ),
        "final_run_hash_basis": "report_without_final_run_hash",
        "provisional_comparison": _gx_final_task12_provisional_comparison(
            root,
            provisional=provisional,
            audit=audit,
            outcome_kind=outcome_kind,
            g8_decision=g8_decision,
        ),
    }
    report_without_hash = json.loads(_json_dumps(report))
    final_run_hash = _hash_payload(report_without_hash)
    report["final_run_hash"] = final_run_hash
    report["provisional_comparison"]["final_run_hash"] = final_run_hash
    return report


def build_reducer_integrity_report(
    positive_status_provenance: Mapping[str, Any],
    *,
    producer_root_chain: Mapping[str, Any] | None = None,
    reducer_decision_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize reducer provenance integrity for positive statuses."""

    issues = []
    missing = [
        record
        for record in _as_list(positive_status_provenance.get("records"))
        if isinstance(record, Mapping) and record.get("missing_produced_by_keys")
    ]
    if missing:
        issues.append(
            _issue(
                "layer3_gx_reducer_provenance_missing",
                POSITIVE_STATUS_PROVENANCE_PATH.as_posix(),
                "One or more positive statuses lack reducer provenance.",
                missing_record_count=len(missing),
            )
        )
    invalid_root_records = [
        record
        for record in _as_list((producer_root_chain or {}).get("records"))
        if isinstance(record, Mapping) and record.get("valid_root_chain") is False
    ]
    if invalid_root_records:
        issues.append(
            _issue(
                "layer3_gx_reducer_producer_root_chain_invalid",
                PRODUCER_ROOT_CHAIN_REPORT_PATH.as_posix(),
                "Reducer provenance is insufficient when producer-root validation fails.",
                invalid_record_count=len(invalid_root_records),
            )
        )
    reducer_decisions = _as_list((reducer_decision_report or {}).get("decisions"))
    manifest_override_issues = _as_list((reducer_decision_report or {}).get("issues"))
    issues.extend(issue for issue in manifest_override_issues if isinstance(issue, Mapping))
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_reducer_integrity_report.v1",
        "status": "fail" if issues else "pass",
        "positive_status_count": int(positive_status_provenance.get("positive_status_count") or 0),
        "positive_status_records": _as_list(positive_status_provenance.get("records")),
        "missing_reducer_provenance_count": len(missing),
        "producer_root_invalid_count": len(invalid_root_records),
        "required_reducer_ids": list(
            (reducer_decision_report or {}).get(
                "required_reducer_ids",
                [
                    "reduce_g1_source_grounding_closure",
                    "reduce_g2_forecast_admission",
                    "reduce_g3_proof_authority",
                    "reduce_gl_legal_authority",
                    "reduce_g4_promotion_state",
                    "reduce_g5_conversion_outcome",
                    "reduce_g7_region_closure",
                    "reduce_g8_domain_vs_search_ceiling",
                ],
            )
        ),
        "reducer_decisions": reducer_decisions,
        "manifest_override_count": len(manifest_override_issues),
        "issues": issues,
    }


def build_status_vocabulary_delta() -> dict[str, Any]:
    """Return the GX status and issue-code vocabulary delta."""

    statuses = [
        {
            "status_id": "not_measured",
            "owner": "layer3-gx-runtime-hardening",
            "allowed_producers": ["measurement", "derivation"],
            "allowed_consumers": ["GX validator", "readiness manifests", "audit surfaces"],
            "composition": {
                "readiness_status": "blocked",
                "useful_design_credit": False,
                "grounding_disposition": "blocked_not_measured",
            },
        },
        {
            "status_id": "search_ceiling_repair_required",
            "owner": "layer3-gx-runtime-hardening",
            "allowed_producers": ["measurement", "derivation"],
            "allowed_consumers": ["GX validator", "G8 auditor", "readiness manifests"],
            "composition": {
                "readiness_status": "blocked",
                "useful_design_credit": False,
                "grounding_disposition": "search_ceiling_unknown",
            },
        },
        {
            "status_id": "blocked_legacy_fallback",
            "owner": "layer3-gx-runtime-hardening",
            "allowed_producers": ["GX validator"],
            "allowed_consumers": ["readiness manifests", "audit surfaces"],
            "composition": {
                "readiness_status": "fail",
                "useful_design_credit": False,
                "promotion_state": "blocked",
            },
        },
        {
            "status_id": "bounded_surrogate",
            "owner": "layer3-gx-runtime-hardening",
            "allowed_producers": ["measurement", "derivation"],
            "allowed_consumers": ["search health", "readiness manifests"],
            "composition": {
                "readiness_status": "limited",
                "useful_design_credit": False,
                "grounding_disposition": "limited_surrogate_only",
            },
        },
        {
            "status_id": "grounded_abstention_candidate",
            "owner": "layer3-gx-runtime-hardening",
            "allowed_producers": ["reducer"],
            "allowed_consumers": ["G5 reducer only after approval"],
            "composition": {
                "readiness_status": "review_required",
                "useful_design_credit": False,
                "approval_required": "deniskopylov",
            },
        },
    ]
    issue_codes = [
        "layer3_gx_reducer_provenance_missing",
        "layer3_gx_inline_input_forbidden",
        "layer3_gx_producer_root_invalid",
        "layer3_gx_correction_required",
        "layer3_gx_alias_unverified",
        "layer3_gx_runtime_literal_forbidden",
        "layer3_gx_placeholder_digest_forbidden",
        "layer3_gx_malformed_sha256_forbidden",
    ]
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_status_vocabulary_delta.v1",
        "status": "blocked_pending_human_approval",
        "principal": "deniskopylov",
        "statuses": statuses,
        "issue_codes": [
            {"code": code, "owner": "layer3-gx-runtime-hardening"} for code in issue_codes
        ],
        "issues": [
            _issue(
                "layer3_gx_human_approval_required",
                STATUS_VOCABULARY_DELTA_PATH.as_posix(),
                "grounded_abstention_candidate remains blocked until highest-governance approval exists.",
            )
        ],
    }


def build_correction_retraction_log(
    repo_root: Path,
    *,
    runtime_literal_lint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Record known published-artifact correction requirements."""

    root = Path(repo_root).resolve()
    hardcode_delta = root / POLICY_DESIGN_CASE_DIR / "layer3_g1_hardcode_strangle_delta.json"
    runtime_lint = runtime_literal_lint or _read_json(
        root / RUNTIME_LITERAL_LINT_PATH,
        default={},
    )
    issues: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    if hardcode_delta.exists():
        hardcode_payload = _read_json(hardcode_delta, default={})
        hardcode_record = hardcode_payload
        if isinstance(hardcode_payload, Mapping) and isinstance(
            hardcode_payload.get("hardcode_strangle_delta"),
            Mapping,
        ):
            hardcode_record = hardcode_payload["hardcode_strangle_delta"]
        hardcode_status = (
            str(hardcode_record.get("fallback_deletion_status") or "unknown")
            if isinstance(hardcode_record, Mapping)
            else "unknown"
        )
        hardcode_issue_codes = (
            _string_list(hardcode_record.get("issue_codes"))
            if isinstance(hardcode_record, Mapping)
            else []
        )
        literal_status = str(runtime_lint.get("status") or "unknown")
        recomputed_clean = (
            hardcode_status == "deleted_or_disabled_no_fallback"
            and not hardcode_issue_codes
            and literal_status == "pass"
        )
        replacement_status = "recomputed_clean" if recomputed_clean else "correction_required"
        records.append(
            {
                "artifact_ref": hardcode_delta.relative_to(root).as_posix(),
                "corrected_false_artifact_ref": (
                    f"{hardcode_delta.relative_to(root).as_posix()}#fallback_deletion_status"
                ),
                "false_or_contested_claim": "prior hardcode deletion/disablement claims cannot close while runtime literal scan remains red",
                "replacement_status": replacement_status,
                "recomputed_replacement_status": hardcode_status,
                "runtime_literal_lint_status": literal_status,
                "owner": "layer3-gx-runtime-hardening",
                "closeout_condition": "recompute hardcode/literal report under GX validator after Task 1 removes or data-owns legacy literals",
            }
        )
        if not recomputed_clean:
            issues.append(
                _issue(
                    "layer3_gx_correction_required",
                    hardcode_delta.relative_to(root).as_posix(),
                    "Published G1 hardcode strangle claims require explicit GX correction/retraction until recomputed clean.",
                    replacement_status=replacement_status,
                    recomputed_replacement_status=hardcode_status,
                    runtime_literal_lint_status=literal_status,
                )
            )
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_correction_retraction_log.v1",
        "status": "fail" if issues else "pass",
        "records": records,
        "issues": issues,
    }


def build_independent_audit_sample(
    positive_status_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the Task 0 independent audit sample placeholder."""

    positives = [
        record
        for record in _as_list(positive_status_provenance.get("records"))
        if isinstance(record, Mapping)
    ][:5]
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_independent_audit_sample.v1",
        "status": "blocked_pending_manual_audit",
        "principal": "deniskopylov",
        "sample_size": len(positives),
        "sample_records": positives,
        "manual_audit_required": True,
        "issues": [
            _issue(
                "layer3_gx_human_approval_required",
                INDEPENDENT_AUDIT_SAMPLE_PATH.as_posix(),
                "Independent audit sample requires principal approval before GX closeout.",
            )
        ],
    }


def build_validation_authority_boundary(repo_root: Path) -> dict[str, Any]:
    """Emit the boundary between legacy slice validators and GX authority."""

    baseline = _read_json(Path(repo_root).resolve() / BASELINE_NOTE_PATH, default={})
    by_slice = {
        str(row.get("slice_id")): row
        for row in _as_list(baseline.get("readiness_cli_baseline"))
        if isinstance(row, Mapping)
    }
    slices: list[dict[str, Any]] = []
    for slice_id in ("G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "GL"):
        row = by_slice.get(slice_id, {})
        old_status = str(row.get("status") or "not_recorded")
        summary = (
            row.get("important_summary")
            if isinstance(row.get("important_summary"), Mapping)
            else {}
        )
        legacy_green = old_status == "pass"
        legacy_diagnostic_codes: list[str] = []
        gx_state = "legacy_validator_no_gx_authority"
        if old_status == "fail":
            gx_state = "blocked_by_gx_migration"
            legacy_diagnostic_codes.append("layer3_gx_legacy_red_blocks_closeout")
        if legacy_green:
            legacy_diagnostic_codes.extend(
                [
                    "layer3_gx_legacy_green_not_authoritative",
                    f"layer3_gx_{slice_id.lower()}_legacy_green_not_authoritative",
                ]
            )
        if slice_id == "G5" and (
            summary.get("g5_dependency_readiness_status") == "fail"
            or summary.get("g5_conversion_outcome") == "unchanged_blocker"
        ):
            legacy_diagnostic_codes.append("layer3_gx_g5_legacy_green_not_authoritative")
        legacy_diagnostic_codes = sorted(set(legacy_diagnostic_codes))
        slices.append(
            {
                "slice_id": slice_id,
                "gx_migration_state": gx_state,
                "old_validator_status": old_status,
                "gx_validator_status": "expected_red",
                "readiness_authority": "legacy_diagnostic_only"
                if legacy_green
                else "no_gx_authority",
                "may_count_for_gx_closeout": False,
                "superseded_by": "tools/quality/validation/check_policy_design_case_layer3_gx_hardening.py",
                "issue_codes": [],
                "legacy_diagnostic_codes": legacy_diagnostic_codes,
                "expected_red_eligible": False,
            }
        )
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_validation_authority_boundary.v1",
        "status": "authority_boundary_enforced",
        "slices": slices,
        "legacy_green_slice_count": sum(
            1 for row in slices if row["old_validator_status"] == "pass"
        ),
        "legacy_diagnostic_count": sum(
            len(row["legacy_diagnostic_codes"]) for row in slices
        ),
        "issues": _authority_boundary_issues({"slices": slices}),
    }


def build_expected_red_checks(
    issues: Sequence[Mapping[str, Any]],
    *,
    provisional_task12_complete: bool = False,
    final_task12_complete: bool = False,
) -> dict[str, Any]:
    """Name every current GX red check against the current GX milestone."""

    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for issue in issues:
        grouped[str(issue.get("code") or "unknown")].append(issue)
    checks = [
        {
            "code": code,
            "status": "expected_red",
            "first_path": str(items[0].get("path") or "$"),
            "instance_count": len(items),
            "covered_issue_fingerprints": [_issue_fingerprint(issue) for issue in items],
            "owner": "layer3-gx-runtime-hardening",
            "removal_condition": _removal_condition(code),
        }
        for code, items in sorted(grouped.items())
    ]
    covered_issue_fingerprints = sorted(
        {fingerprint for check in checks for fingerprint in check["covered_issue_fingerprints"]}
    )
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_expected_red_checks.v1",
        "status": (
            "active_post_final_task12"
            if checks and final_task12_complete
            else "active_post_provisional_task12"
            if checks and provisional_task12_complete
            else "active_pre_provisional_task12"
            if checks
            else "empty"
        ),
        "provisional_task12_complete": provisional_task12_complete,
        "final_task12_complete": final_task12_complete,
        "checks": checks,
        "covered_issue_fingerprints": covered_issue_fingerprints,
        "issues": [],
    }


def build_human_approval_receipts(repo_root: Path) -> dict[str, Any]:
    """Load human approval receipts and flag missing approval for Task 0 exceptions."""

    payload = _read_json(Path(repo_root).resolve() / HUMAN_APPROVAL_RECEIPTS_PATH, default={})
    receipts = _as_list(payload.get("receipts")) if isinstance(payload, Mapping) else []
    issues = []
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            continue
        if receipt.get("principal") != "deniskopylov" or not receipt.get("decision"):
            issues.append(
                _issue(
                    "layer3_gx_human_approval_invalid",
                    HUMAN_APPROVAL_RECEIPTS_PATH.as_posix(),
                    "Human approval receipt must name deniskopylov and a concrete decision.",
                )
            )
    return {
        "schema_version": "policyos.policy_design_case.layer3_gx_human_approval_receipts.v1",
        "status": "pass" if not issues else "fail",
        "principal": "deniskopylov",
        "receipts": receipts,
        "issues": issues,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the GX hardening validator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = validate_layer3_gx_hardening(args.repo_root, write=args.write)
    rendered = _json_dumps(report) if args.output_format == "json" else _render_text(report)
    if args.output is not None:
        output_path = _resolve_path(args.repo_root, args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0 if report["status"] == "pass" else 1


def _literal_issues(
    repo_root: Path,
    file_path: Path,
    node: ast.Constant,
    lines: Sequence[str],
) -> list[dict[str, Any]]:
    value = str(node.value)
    rel_path = _relative(repo_root, file_path)
    if _is_test_path(rel_path):
        return []
    issues = _digest_issues(rel_path, node, value)
    if _is_task4_reducer_status_module(rel_path):
        return issues
    if _is_lint_configuration_literal(node) or _is_typing_literal_context(node):
        return issues
    domain_matches = sorted(literal for literal in FORBIDDEN_DOMAIN_LITERALS if literal in value)
    positive_matches = sorted(
        literal for literal in RUNTIME_POSITIVE_LITERAL_VALUES if literal in value
    )
    if positive_matches and not _is_positive_status_literal(node):
        positive_matches = []
    matched = [*domain_matches, *positive_matches]
    if not matched:
        return issues
    line_text = lines[node.lineno - 1] if 0 < node.lineno <= len(lines) else ""
    if "Literal[" in line_text or "typing.Literal" in line_text:
        return issues
    for literal in matched:
        issues.append(
            _issue(
                "layer3_gx_runtime_literal_forbidden",
                rel_path,
                "Runtime/core/validator code contains a GX-forbidden domain or positive-status literal.",
                literal=literal,
                line=node.lineno,
            )
        )
    return issues


def _identifier_issues(
    repo_root: Path,
    file_path: Path,
    node: ast.AST,
) -> list[dict[str, Any]]:
    rel_path = _relative(repo_root, file_path)
    if _is_test_path(rel_path):
        return []
    identifier = _identifier_name(node)
    if not identifier:
        return []
    domain_matches = sorted(
        literal for literal in FORBIDDEN_DOMAIN_LITERALS if literal in identifier
    )
    if not domain_matches:
        return []
    return [
        _issue(
            "layer3_gx_runtime_literal_forbidden",
            rel_path,
            "Runtime/core/validator code contains a GX-forbidden domain identifier.",
            literal=literal,
            identifier=identifier,
            line=int(getattr(node, "lineno", 0) or 0),
        )
        for literal in domain_matches
    ]


def _identifier_name(node: ast.AST) -> str:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return node.name
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.arg):
        return node.arg
    return ""


def _attach_parent_links(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._gx_parent = parent  # type: ignore[attr-defined]


def _is_positive_status_literal(node: ast.Constant) -> bool:
    parent = getattr(node, "_gx_parent", None)
    if isinstance(parent, ast.Dict):
        for key, value in zip(parent.keys, parent.values, strict=False):
            if value is node and _constant_text(key) in POSITIVE_STATUS_FIELDS:
                return True
    if isinstance(parent, ast.keyword):
        return bool(parent.arg and parent.arg in POSITIVE_STATUS_FIELDS)
    if isinstance(parent, ast.Assign):
        return any(_target_name(target) in POSITIVE_STATUS_FIELDS for target in parent.targets)
    if isinstance(parent, ast.AnnAssign):
        return _target_name(parent.target) in POSITIVE_STATUS_FIELDS
    return False


def _is_task4_reducer_status_module(rel_path: str) -> bool:
    return rel_path == "src/polisyos/runtime/quality/layer3_status_reducers.py"


def _is_lint_configuration_literal(node: ast.Constant) -> bool:
    config_names = {
        "FORBIDDEN_DOMAIN_LITERALS",
        "POSITIVE_LITERAL_VALUES",
        "RUNTIME_POSITIVE_LITERAL_VALUES",
        "POSITIVE_STATUS_FIELDS",
    }
    current: ast.AST | None = node
    while current is not None:
        parent = getattr(current, "_gx_parent", None)
        if isinstance(parent, ast.Assign):
            return any(_target_name(target) in config_names for target in parent.targets)
        if isinstance(parent, ast.AnnAssign):
            return _target_name(parent.target) in config_names
        current = parent
    return False


def _is_typing_literal_context(node: ast.Constant) -> bool:
    current: ast.AST | None = node
    while current is not None:
        parent = getattr(current, "_gx_parent", None)
        if isinstance(parent, ast.AnnAssign):
            return _contains_literal_annotation(parent.annotation)
        current = parent
    return False


def _contains_literal_annotation(node: ast.AST) -> bool:
    if isinstance(node, ast.Subscript):
        value = node.value
        if isinstance(value, ast.Name) and value.id == "Literal":
            return True
        if isinstance(value, ast.Attribute) and value.attr == "Literal":
            return True
    return any(_contains_literal_annotation(child) for child in ast.iter_child_nodes(node))


def _constant_text(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _target_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _digest_issues(rel_path: str, node: ast.Constant, value: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for match in SHA256_RE.finditer(value):
        digest = match.group(1)
        if not digest:
            continue
        if REPEATED64_RE.fullmatch(digest):
            issues.append(
                _issue(
                    "layer3_gx_placeholder_digest_forbidden",
                    rel_path,
                    "Repeated-character sha256 digest is forbidden outside negative fixtures.",
                    digest=f"sha256:{digest}",
                    line=node.lineno,
                )
            )
        elif not HEX64_RE.fullmatch(digest):
            issues.append(
                _issue(
                    "layer3_gx_malformed_sha256_forbidden",
                    rel_path,
                    "Malformed or incomplete sha256 digest is forbidden in GX authority paths.",
                    digest=f"sha256:{digest}",
                    line=node.lineno,
                )
            )
    return issues


def _input_discard_issues(repo_root: Path, file_path: Path, node: ast.AST) -> list[dict[str, Any]]:
    rel_path = _relative(repo_root, file_path)
    if _is_test_path(rel_path):
        return []
    discards_repo_root = any(
        isinstance(child, ast.Delete)
        and any(
            isinstance(target, ast.Name) and target.id == "repo_root" for target in child.targets
        )
        for child in ast.walk(node)
    )
    if not discards_repo_root:
        return []
    returns_status = any(
        isinstance(child, ast.Constant)
        and isinstance(child.value, str)
        and child.value in POSITIVE_STATUS_FIELDS
        for child in ast.walk(node)
    )
    if not returns_status:
        return []
    line = getattr(node, "lineno", 1)
    return [
        _issue(
            "layer3_gx_inline_input_forbidden",
            f"{rel_path}:{line}",
            "Builder discards repo_root and returns status-bearing payloads.",
        )
    ]


def _build_required_reducer_decisions(repo_root: Path) -> list[Layer3ReducerDecision]:
    g1_manifest_path = POLICY_DESIGN_CASE_DIR / "layer3_g1_readiness_manifest.json"
    g1_contracts_path = POLICY_DESIGN_CASE_DIR / "layer3_g1_grounded_source_contracts.json"
    g1_recall_path = POLICY_DESIGN_CASE_DIR / "layer3_g1_search_recall_freshness.json"
    g1_manifest = _as_mapping(_read_json(repo_root / g1_manifest_path, default={}))
    g1_counts = _as_mapping(g1_manifest.get("counts"))
    g1_contracts = _as_mapping(_read_json(repo_root / g1_contracts_path, default={}))
    g1_contract_payload = _as_mapping(g1_contracts.get("grounded_source_contracts") or g1_contracts)
    g1_bindings = _as_list(g1_contract_payload.get("bindings"))

    g2_manifest_path = POLICY_DESIGN_CASE_DIR / "layer3_g2_readiness_manifest.json"
    g2_manifest = _as_mapping(_read_json(repo_root / g2_manifest_path, default={}))
    g2_summary = _as_mapping(g2_manifest.get("summary"))

    g3_manifest_path = POLICY_DESIGN_CASE_DIR / "layer3_g3_readiness_manifest.json"
    g3_manifest = _as_mapping(_read_json(repo_root / g3_manifest_path, default={}))
    g3_summary = _as_mapping(g3_manifest.get("summary"))

    gl_manifest_path = POLICY_DESIGN_CASE_DIR / "layer3_gl_readiness_manifest.json"
    gl_manifest = _as_mapping(_read_json(repo_root / gl_manifest_path, default={}))
    gl_summary = _as_mapping(gl_manifest.get("summary"))

    g4_manifest_path = POLICY_DESIGN_CASE_DIR / "layer3_g4_readiness_manifest.json"
    g4_weakest_path = POLICY_DESIGN_CASE_DIR / "layer3_g4_weakest_boundary_composition.json"
    g4_manifest = _as_mapping(_read_json(repo_root / g4_manifest_path, default={}))
    g4_summary = _as_mapping(g4_manifest.get("summary"))
    g4_weakest = _as_mapping(_read_json(repo_root / g4_weakest_path, default={}))

    g5_manifest_path = POLICY_DESIGN_CASE_DIR / "layer3_g5_readiness_manifest.json"
    g5_records_path = POLICY_DESIGN_CASE_DIR / "layer3_g5_conversion_records.json"
    g5_manifest = _as_mapping(_read_json(repo_root / g5_manifest_path, default={}))
    g5_summary = _as_mapping(g5_manifest.get("summary"))

    g7_manifest_path = POLICY_DESIGN_CASE_DIR / "layer3_g7_readiness_manifest.json"
    g7_manifest = _as_mapping(_read_json(repo_root / g7_manifest_path, default={}))
    g7_summary = _as_mapping(g7_manifest.get("summary"))
    gx_boundary = _as_mapping(
        _read_json(repo_root / VALIDATION_AUTHORITY_BOUNDARY_PATH, default={})
    )

    g8_manifest_path = POLICY_DESIGN_CASE_DIR / "layer3_g8_readiness_manifest.json"

    g5_outcome = _first_text(
        g5_manifest.get("g5_conversion_outcome"),
        g5_summary.get("g5_conversion_outcome"),
    )
    g7_closure = _first_text(
        g7_manifest.get("g7_region_value_closure_status"),
        g7_summary.get("g7_region_value_closure_status"),
        g7_manifest.get("region_grounding_status"),
    )
    return [
        reduce_g1_source_grounding_closure(
            G1SourceGroundingClosureInputs(
                canonical_store=g1_counts.get("g1_l1_l5_l6_index_coverage_status") == "pass",
                binding_count=len(g1_bindings),
                binding_statuses=tuple(
                    str(_as_mapping(binding).get("grounding_status") or "grounded")
                    for binding in g1_bindings
                    if isinstance(binding, Mapping)
                ),
                measured_no_hit=(
                    not g1_bindings
                    and int(g1_counts.get("g1_substrate_search_ledger_count") or 0) > 0
                ),
                search_recall_status=_first_text(
                    g1_counts.get("g1_search_recall_status"),
                    "not_measured",
                ),
                index_freshness_status=_first_text(
                    g1_counts.get("g1_index_freshness_status"),
                    "not_measured",
                ),
                overlay_injection_status=(
                    "pass"
                    if int(g1_counts.get("resolver_binding_consumed_count") or 0) > 0
                    else "not_measured"
                ),
                abstention_vocabulary_approved=_gx_abstention_candidate_approved(repo_root),
                input_refs=(
                    _artifact_input_ref(repo_root, g1_manifest_path),
                    _artifact_input_ref(repo_root, g1_contracts_path),
                    _artifact_input_ref(repo_root, g1_recall_path),
                ),
            )
        ),
        reduce_g2_forecast_admission(
            G2ForecastAdmissionInputs(
                method_binding_status=_count_status(
                    g2_summary.get("g2_method_requirement_binding_count"),
                ),
                calibration_status=_first_text(
                    g2_summary.get("g2_conformance_status"),
                    g2_manifest.get("status"),
                    "missing",
                ),
                skg_edge_type=_first_text(g2_summary.get("g2_skg_edge_type"), "missing"),
                input_refs=(_artifact_input_ref(repo_root, g2_manifest_path),),
            )
        ),
        reduce_g3_proof_authority(
            G3ProofAuthorityInputs(
                proof_candidate_status=(
                    "proof_authority"
                    if int(g3_summary.get("g3_closure_count") or 0) > 0
                    else _first_text(g3_summary.get("g3_proof_status"), "candidate")
                ),
                certificate_status=_first_text(
                    g3_summary.get("g3_certificate_resolution_status"),
                    g3_manifest.get("status"),
                    "missing",
                ),
                input_refs=(_artifact_input_ref(repo_root, g3_manifest_path),),
            )
        ),
        reduce_gl_legal_authority(
            GLLegalAuthorityInputs(
                legal_basis_status=_first_text(
                    gl_summary.get("gl_requirement_artifact_status"),
                    gl_manifest.get("status"),
                    "missing",
                ),
                applicability_status=_first_text(
                    gl_summary.get("gl_applicability_status"),
                    gl_manifest.get("gl_applicability_status"),
                    "missing",
                ),
                mandate_status=_first_text(
                    gl_summary.get("gl_mandate_compatibility_status"),
                    gl_manifest.get("mandate_status"),
                    "missing",
                ),
                input_refs=(_artifact_input_ref(repo_root, gl_manifest_path),),
            )
        ),
        reduce_g4_promotion_state(
            G4PromotionStateInputs(
                dependency_statuses=tuple(
                    status
                    for status in (
                        _first_text(g4_summary.get("g4_dependency_readiness_status")),
                        _first_text(g4_manifest.get("status")),
                    )
                    if status
                ),
                blocker_refs=(
                    *_string_list(g4_weakest.get("blocker_refs")),
                    *_string_list(g4_weakest.get("issue_codes")),
                ),
                limitation_refs=tuple(_string_list(g4_weakest.get("limitation_refs"))),
                input_refs=(
                    _artifact_input_ref(repo_root, g4_manifest_path),
                    _artifact_input_ref(repo_root, g4_weakest_path),
                ),
            )
        ),
        reduce_g5_conversion_outcome(
            G5ConversionOutcomeInputs(
                requested_conversion_outcome=_gx_requested_g5_outcome(g5_outcome),
                g4_promotion_state=(
                    "governed_promoted"
                    if int(g5_summary.get("g5_governed_promotion_input_count") or 0) > 0
                    else "promotion_blocked"
                ),
                g1_grounding_closure=_first_text(
                    g5_summary.get("g5_g1_grounding_status"),
                    "typed_blocker",
                ),
                demand_pull_status=_first_text(
                    g5_summary.get("g5_demand_pull_attempt_status"),
                    "missing",
                ),
                cross_slice_status=(
                    "pass"
                    if (
                        g5_summary.get("g5_dependency_readiness_status") == "pass"
                        and g5_summary.get("g5_upstream_scope_join_status") == "pass"
                        and g5_summary.get("g5_g4_handoff_resolution_status") == "pass"
                    )
                    else "fail"
                ),
                grounded_evidence_ref_count=int(
                    g5_summary.get("g5_grounded_evidence_ref_count") or 0
                ),
                input_refs=(
                    _artifact_input_ref(repo_root, g5_manifest_path),
                    _artifact_input_ref(repo_root, g5_records_path),
                ),
            )
        ),
        reduce_g7_region_closure(
            G7RegionClosureInputs(
                gx_migration_state=_gx_slice_migration_state(gx_boundary, "G7"),
                g5_conversion_outcome=_gx_reducer_g5_status(g5_outcome),
                regional_breadth_status=_first_text(
                    g7_summary.get("g7_region_breadth_status"),
                    g7_manifest.get("g7_region_breadth_status"),
                    "missing",
                ),
                input_refs=(_artifact_input_ref(repo_root, g7_manifest_path),),
            )
        ),
        reduce_g8_domain_vs_search_ceiling(
            G8DomainVsSearchCeilingInputs(
                g5_conversion_outcome=_gx_reducer_g5_status(g5_outcome),
                g7_region_closure=_first_text(g7_closure, "blocked_by_gx_migration"),
                search_recall_status=_first_text(
                    g1_counts.get("g1_search_recall_status"),
                    "not_measured",
                ),
                index_freshness_status=_first_text(
                    g1_counts.get("g1_index_freshness_status"),
                    "not_measured",
                ),
                input_refs=(_artifact_input_ref(repo_root, g8_manifest_path),),
            )
        ),
    ]


def _reducer_manifest_override_issues(
    repo_root: Path,
    decisions: Sequence[Layer3ReducerDecision],
) -> list[dict[str, Any]]:
    decisions_by_id = {decision.reducer_id: decision for decision in decisions}
    checks = (
        (
            POLICY_DESIGN_CASE_DIR / "layer3_g1_readiness_manifest.json",
            "reduce_g1_source_grounding_closure",
            "grounding_closure_outcome",
        ),
        (
            POLICY_DESIGN_CASE_DIR / "layer3_g4_readiness_manifest.json",
            "reduce_g4_promotion_state",
            "promotion_state",
        ),
        (
            POLICY_DESIGN_CASE_DIR / "layer3_g5_readiness_manifest.json",
            "reduce_g5_conversion_outcome",
            "g5_conversion_outcome",
        ),
        (
            POLICY_DESIGN_CASE_DIR / "layer3_g7_readiness_manifest.json",
            "reduce_g7_region_closure",
            "g7_region_value_closure_status",
        ),
    )
    issues: list[dict[str, Any]] = []
    for relative_path, reducer_id, status_field in checks:
        payload = _as_mapping(_read_json(repo_root / relative_path, default={}))
        if not payload:
            continue
        decision = decisions_by_id[reducer_id]
        persisted_status = _first_text(
            payload.get(status_field),
            _as_mapping(payload.get("summary")).get(status_field),
            _as_mapping(payload.get("counts")).get(status_field),
        )
        if persisted_status and not _manifest_status_matches_reducer(
            reducer_id,
            persisted_status,
            decision.status,
        ):
            issues.append(
                _issue(
                    "layer3_gx_readiness_manifest_overrides_reducer_output",
                    f"{relative_path.as_posix()}#{status_field}",
                    "Readiness manifest status differs from the reducer-authored status.",
                    reducer_id=reducer_id,
                    persisted_status=persisted_status,
                    reducer_status=decision.status,
                )
            )
        if (
            _manifest_top_level_status_is_reducer_authority(reducer_id, payload)
            and payload.get("status") == "pass"
            and decision.readiness_status != "pass"
        ):
            issues.append(
                _issue(
                    "layer3_gx_readiness_manifest_overrides_reducer_output",
                    f"{relative_path.as_posix()}#status",
                    "Readiness manifest reports pass while the reducer remains blocked.",
                    reducer_id=reducer_id,
                    persisted_status="pass",
                    reducer_status=decision.status,
                    reducer_readiness_status=decision.readiness_status,
                )
            )
    return issues


def _manifest_status_matches_reducer(
    reducer_id: str,
    persisted_status: str,
    reducer_status: str,
) -> bool:
    if persisted_status == reducer_status:
        return True
    if reducer_id != "reduce_g7_region_closure":
        return False
    if persisted_status == "pass":
        return reducer_status == "region_closed"
    if persisted_status in {
        "blocked_by_current_g5_unchanged_blocker",
        "blocked_by_no_real_grounded_region_breadth",
        "blocked_by_bespoke_reuse",
        "blocked_by_s14_feed",
    }:
        return reducer_status in {"blocked_by_gx_migration", "region_blocked"}
    return False


def _manifest_top_level_status_is_reducer_authority(
    reducer_id: str,
    payload: Mapping[str, Any],
) -> bool:
    if reducer_id != "reduce_g7_region_closure":
        return True
    return (
        payload.get("status_authority_boundary")
        != "artifact_family_integrity_only_not_region_closure_authority"
    )


def _artifact_input_ref(
    repo_root: Path,
    relative_path: Path,
    *,
    supply_side: bool = True,
) -> Layer3ReducerInputRef:
    path = repo_root / relative_path
    if not path.exists():
        return Layer3ReducerInputRef(
            ref=f"repo://{relative_path.as_posix()}",
            exists=False,
            required=True,
            supply_side=supply_side,
        )
    payload = _read_json(path, default={})
    mapping = _as_mapping(payload)
    producer_ref = _first_text(_find_first_key(mapping, "producer_ref"))
    producer_type = _first_text(_find_first_key(mapping, "producer_type"))
    return Layer3ReducerInputRef(
        ref=f"repo://{relative_path.as_posix()}",
        exists=True,
        content_hash=_hash_file(path),
        producer_ref=producer_ref or None,
        producer_type=producer_type or None,
        producer_root_refs=tuple(_string_list(_find_first_key(mapping, "producer_root_refs"))),
        producer_root_status=_producer_root_status(producer_type),
        supply_side=supply_side,
    )


def _vertical_artifact_input_ref(
    repo_root: Path,
    relative_path: Path,
    *,
    producer_ref: str,
    producer_type: str,
    producer_root_refs: Sequence[str] = (),
    supply_side: bool = True,
) -> Layer3ReducerInputRef:
    path = repo_root / relative_path
    return Layer3ReducerInputRef(
        ref=f"repo://{relative_path.as_posix()}",
        exists=path.exists(),
        content_hash=_hash_file(path) if path.exists() else None,
        producer_ref=producer_ref,
        producer_type=producer_type,
        producer_root_refs=tuple(ref for ref in producer_root_refs if ref),
        producer_root_status=_producer_root_status(producer_type),
        supply_side=supply_side,
    )


def _vertical_reducer_decision_input_ref(
    decision: Layer3ReducerDecision,
) -> Layer3ReducerInputRef:
    output_hash = str(decision.produced_by.get("output_hash") or "")
    return Layer3ReducerInputRef(
        ref=f"reducer://layer3-gx/{decision.reducer_id}",
        exists=True,
        content_hash=output_hash,
        producer_ref=f"reducer://layer3-gx/{decision.reducer_id}",
        producer_type="derivation",
        producer_root_refs=decision.input_refs,
        producer_root_status="validated",
        supply_side=False,
    )


def _gx_reducer_call_row(
    decision_row: Mapping[str, Any],
    persisted_status_ref: str,
) -> dict[str, Any]:
    produced_by = _as_mapping(decision_row.get("produced_by"))
    return {
        "reducer_id": decision_row.get("reducer_id") or "",
        "status_field": decision_row.get("status_field") or "",
        "status": decision_row.get("status") or "",
        "readiness_status": decision_row.get("readiness_status") or "",
        "rule_version": decision_row.get("rule_version") or "",
        "input_refs": _string_list(decision_row.get("input_refs")),
        "input_hashes": dict(_as_mapping(decision_row.get("input_hashes"))),
        "output_hash": produced_by.get("output_hash") or "",
        "persisted_status_ref": persisted_status_ref,
    }


def _gx_final_task12_g8_artifacts(repo_root: Path) -> dict[str, Mapping[str, Any]]:
    return {
        "readiness_manifest": _as_mapping(
            _read_json(repo_root / G8_READINESS_MANIFEST_PATH, default={})
        ),
        "cross_metric_diagnosis": _as_mapping(
            _read_json(repo_root / G8_CROSS_METRIC_DIAGNOSIS_PATH, default={})
        ),
        "domain_vs_search_ceiling_gate": _as_mapping(
            _read_json(repo_root / G8_DOMAIN_VS_SEARCH_CEILING_GATE_PATH, default={})
        ),
        "open_question_answer_ledger": _as_mapping(
            _read_json(repo_root / G8_OPEN_QUESTION_ANSWER_LEDGER_PATH, default={})
        ),
        "metric_governance_audit_surface": _as_mapping(
            _read_json(repo_root / G8_METRIC_GOVERNANCE_AUDIT_SURFACE_PATH, default={})
        ),
        "closeout_signal_consumer_gate": _as_mapping(
            _read_json(repo_root / G8_CLOSEOUT_SIGNAL_CONSUMER_GATE_PATH, default={})
        ),
    }


def _gx_final_task12_search_health_classification(
    g8_artifacts: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    domain_gate = _as_mapping(g8_artifacts.get("domain_vs_search_ceiling_gate"))
    classification = _as_mapping(domain_gate.get("search_health_classification"))
    if classification:
        return classification
    cross_diagnosis = _as_mapping(g8_artifacts.get("cross_metric_diagnosis"))
    return _as_mapping(cross_diagnosis.get("search_health_classification"))


def _gx_open_question_answer(ledger: Mapping[str, Any], question_id: str) -> Mapping[str, Any]:
    for answer in _as_list(ledger.get("answers")):
        if isinstance(answer, Mapping) and answer.get("question_id") == question_id:
            return answer
    return {}


def _gx_final_task12_g8_issue_codes(
    g8_artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    codes: list[str] = []
    for payload in g8_artifacts.values():
        codes.extend(_string_list(payload.get("issue_codes")))
        classification = _as_mapping(payload.get("search_health_classification"))
        codes.extend(_string_list(classification.get("issue_codes")))
    return _dedupe_strings(codes)


def _gx_final_task12_g8_artifact_refs() -> list[str]:
    return [
        f"repo://{G8_READINESS_MANIFEST_PATH.as_posix()}",
        f"repo://{G8_CROSS_METRIC_DIAGNOSIS_PATH.as_posix()}",
        f"repo://{G8_DOMAIN_VS_SEARCH_CEILING_GATE_PATH.as_posix()}",
        f"repo://{G8_OPEN_QUESTION_ANSWER_LEDGER_PATH.as_posix()}",
        f"repo://{G8_METRIC_GOVERNANCE_AUDIT_SURFACE_PATH.as_posix()}",
        f"repo://{G8_CLOSEOUT_SIGNAL_CONSUMER_GATE_PATH.as_posix()}",
    ]


def _gx_final_task12_required_audit_refs() -> list[str]:
    return [
        f"repo://{G8_CROSS_METRIC_DIAGNOSIS_PATH.as_posix()}#search_health_classification",
        f"repo://{G8_DOMAIN_VS_SEARCH_CEILING_GATE_PATH.as_posix()}#search_health_classification",
        (
            f"repo://{G8_DOMAIN_VS_SEARCH_CEILING_GATE_PATH.as_posix()}"
            "#domain_ceiling_precondition_statuses"
        ),
        f"repo://{G8_OPEN_QUESTION_ANSWER_LEDGER_PATH.as_posix()}#8.4-search-recall-freshness",
        f"repo://{G8_METRIC_GOVERNANCE_AUDIT_SURFACE_PATH.as_posix()}",
        f"repo://{G8_CLOSEOUT_SIGNAL_CONSUMER_GATE_PATH.as_posix()}",
    ]


def _gx_final_task12_g8_input_refs(repo_root: Path) -> tuple[Layer3ReducerInputRef, ...]:
    root_refs = _gx_final_task12_required_audit_refs()
    return tuple(
        _vertical_artifact_input_ref(
            repo_root,
            path,
            producer_ref=producer_ref,
            producer_type="derivation",
            producer_root_refs=root_refs,
            supply_side=False,
        )
        for path, producer_ref in (
            (
                G8_DOMAIN_VS_SEARCH_CEILING_GATE_PATH,
                "runtime-quality://layer3-g8/domain-vs-search-ceiling-gate",
            ),
            (
                G8_OPEN_QUESTION_ANSWER_LEDGER_PATH,
                "runtime-quality://layer3-g8/open-question-answer-ledger",
            ),
            (
                G8_CROSS_METRIC_DIAGNOSIS_PATH,
                "runtime-quality://layer3-g8/cross-metric-diagnosis",
            ),
            (
                G8_METRIC_GOVERNANCE_AUDIT_SURFACE_PATH,
                "runtime-quality://layer3-g8/metric-governance-audit-surface",
            ),
            (
                G8_CLOSEOUT_SIGNAL_CONSUMER_GATE_PATH,
                "runtime-quality://layer3-g8/closeout-signal-consumer-gate",
            ),
            (
                G8_READINESS_MANIFEST_PATH,
                "runtime-quality://layer3-g8/readiness-manifest",
            ),
        )
    )


def _gx_final_task12_g8_reducer_decision(
    repo_root: Path,
    *,
    route: Mapping[str, Any],
    classification: Mapping[str, Any],
) -> Layer3ReducerDecision:
    return reduce_g8_domain_vs_search_ceiling(
        G8DomainVsSearchCeilingInputs(
            g5_conversion_outcome=_gx_reducer_g5_status(
                _first_text(route.get("final_outcome"), "unchanged_blocker")
            ),
            g7_region_closure=_first_text(
                classification.get("g7_region_closure"),
                "blocked_by_gx_migration",
            ),
            search_recall_status=_first_text(
                classification.get("current_blocker_status"),
                classification.get("pinned_request_status"),
                "not_measured",
            ),
            index_freshness_status=_first_text(
                classification.get("freshness_status"),
                "not_measured",
            ),
            input_refs=_gx_final_task12_g8_input_refs(repo_root),
        )
    )


def _gx_task12_may_not_use_for(*payloads: Mapping[str, Any]) -> list[str]:
    values: list[str] = [
        "production_authority",
        "production_claim_authority",
        "rollout_authority",
        "publication_authority",
        "approval_authority",
        "closeout_authority",
        "runtime_closeout_authority",
        "recommendation_authority",
        "universal_claim_authority",
        "domain_ceiling_authority_without_gate",
        "useful_design_credit",
    ]
    for payload in payloads:
        values.extend(_string_list(payload.get("may_not_use_for")))
    return _dedupe_strings(values)


def _gx_final_task12_provisional_comparison(
    repo_root: Path,
    *,
    provisional: Mapping[str, Any],
    audit: Mapping[str, Any],
    outcome_kind: str,
    g8_decision: Layer3ReducerDecision,
) -> dict[str, Any]:
    provisional_hash = _first_text(
        provisional.get("provisional_run_hash"),
        _hash_payload(provisional),
    )
    changed_statuses = []
    provisional_outcome = _first_text(provisional.get("outcome_kind"), "typed_blocker")
    if provisional_outcome != outcome_kind:
        changed_statuses.append(
            {
                "field": "outcome_kind",
                "provisional": provisional_outcome,
                "final": outcome_kind,
                "reason": "final_task12_adds_task11_g8_domain_vs_search_ceiling_gate",
            }
        )
    provisional_open_status = _first_text(
        audit.get("provisional_g8_open_question_surface_status"),
        "not_required_until_task11",
    )
    final_open_status = _first_text(audit.get("g8_open_question_surface_status"), "blocked")
    if provisional_open_status != final_open_status:
        changed_statuses.append(
            {
                "field": "g8_open_question_surface_status",
                "provisional": provisional_open_status,
                "final": final_open_status,
                "reason": "task11_g8_open_question_surface_is_now_required",
            }
        )
    changed_reducer_inputs = [
        {
            "reducer_id": "reduce_g8_domain_vs_search_ceiling",
            "change": "added_in_final_task12",
            "input_refs": list(g8_decision.input_refs),
            "input_hashes": dict(g8_decision.input_hashes),
            "reason": "final_task12_consumes_g8_audit_surface_after_task11_rollout",
        }
    ]
    changed_producer_roots = [
        {
            "producer_root_ref": artifact_ref,
            "change": "added_in_final_task12",
            "content_hash": _hash_file(
                repo_root / Path(artifact_ref.removeprefix("repo://").split("#", 1)[0])
            ),
        }
        for artifact_ref in _gx_final_task12_g8_artifact_refs()
        if (repo_root / Path(artifact_ref.removeprefix("repo://").split("#", 1)[0])).exists()
    ]
    return {
        "provisional_run_ref": f"repo://{PROVISIONAL_PINNED_ROUTE_OUTCOME_PATH.as_posix()}",
        "provisional_run_hash": provisional_hash,
        "final_run_hash": "",
        "changed_statuses": changed_statuses,
        "changed_reducer_inputs": changed_reducer_inputs,
        "changed_producer_roots": changed_producer_roots,
        "explanation": (
            "Final Task 12 keeps the provisional G5 reducer outcome, then adds the "
            "Task 11 G8 domain-vs-search ceiling reducer and audit-only evidence."
        ),
    }


def _producer_root_status(producer_type: str) -> str:
    if producer_type in {"derivation", "untyped", "test_fixture", "unverified"}:
        return producer_type if producer_type != "test_fixture" else "test_only"
    return "validated"


def _hash_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _find_first_key(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        if key in value:
            return value[key]
        for child in value.values():
            found = _find_first_key(child, key)
            if found not in (None, "", [], {}):
                return found
    if isinstance(value, list | tuple):
        for child in value:
            found = _find_first_key(child, key)
            if found not in (None, "", [], {}):
                return found
    return None


def _first_text(*values: Any) -> str:
    for value in values:
        if value not in (None, ""):
            return str(value)
    return ""


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _count_status(value: Any) -> str:
    try:
        return "pass" if int(value or 0) > 0 else "missing"
    except (TypeError, ValueError):
        return "missing"


def _gx_requested_g5_outcome(value: str) -> str:
    if "grounded_abstention" in value:
        return "grounded_abstention"
    if "grounded_limited" in value:
        return "grounded_limited"
    return "unchanged_blocker"


def _gx_reducer_g5_status(value: str) -> str:
    if "grounded_abstention" in value:
        return "grounded_abstention"
    if "grounded_limited" in value:
        return "grounded_limited"
    return "unchanged_blocker"


def _gx_slice_migration_state(boundary: Mapping[str, Any], slice_id: str) -> str:
    for row in _as_list(boundary.get("slices")):
        if isinstance(row, Mapping) and row.get("slice_id") == slice_id:
            return _first_text(row.get("gx_migration_state"), "blocked_by_gx_migration")
    return "blocked_by_gx_migration"


def _gx_abstention_candidate_approved(repo_root: Path) -> bool:
    payload = _as_mapping(_read_json(repo_root / STATUS_VOCABULARY_DELTA_PATH, default={}))
    if payload.get("status") != "approved":
        return False
    for row in _as_list(payload.get("statuses")):
        if isinstance(row, Mapping) and row.get("status_id") == "grounded_abstention_candidate":
            return True
    return False


def _find_positive_statuses(
    repo_root: Path,
    *,
    artifact_paths: Sequence[Path] | None = None,
) -> list[PositiveStatus]:
    return _production_positive_statuses(
        _find_positive_status_candidates(repo_root, artifact_paths=artifact_paths)
    )


def _find_positive_status_candidates(
    repo_root: Path,
    *,
    artifact_paths: Sequence[Path] | None = None,
) -> list[PositiveStatus]:
    root = Path(repo_root).resolve()
    positives: list[PositiveStatus] = []
    for path in artifact_paths or _default_artifact_paths(root):
        payload = _read_json(root / path, default=None)
        if payload is None:
            continue
        for item, pointer in _walk_json(payload):
            if not isinstance(item, Mapping):
                continue
            for key, value in item.items():
                if key in POSITIVE_STATUS_FIELDS and str(value) in POSITIVE_LITERAL_VALUES:
                    positives.append(
                        PositiveStatus(
                            artifact_path=path.as_posix(),
                            pointer=pointer,
                            field=str(key),
                            value=str(value),
                            record=item,
                        )
                    )
    return positives


def _production_positive_statuses(
    candidates: Sequence[PositiveStatus],
) -> list[PositiveStatus]:
    return [status for status in candidates if _is_production_positive_status(status)]


def _is_production_positive_status(status: PositiveStatus) -> bool:
    if _is_external_request_input_positive_status(status):
        return False
    if status.record.get("producer_ref") or isinstance(status.record.get("produced_by"), Mapping):
        return True
    return status.field in AUTHORITY_POSITIVE_STATUS_FIELDS


def _is_external_request_input_positive_status(status: PositiveStatus) -> bool:
    if status.field != "status" or status.value != "pass":
        return False
    if isinstance(status.record.get("produced_by"), Mapping):
        return False
    if str(status.record.get("producer_type") or "") != "external_request":
        return False
    purpose = str(status.record.get("authority_purpose") or "")
    may_not_use_for = set(_string_list(status.record.get("may_not_use_for")))
    return (
        purpose.endswith("_input_only")
        and "conversion_authority" in may_not_use_for
        and "production_authority" in may_not_use_for
    )


def _positive_status_classification_record(status: PositiveStatus) -> dict[str, Any]:
    reason = "generic_status_without_producer_or_reducer_provenance"
    classification = "diagnostic_positive_not_authority"
    if _is_external_request_input_positive_status(status):
        classification = "external_request_input_positive_not_reducer_output"
        reason = "external_request_input_only_status_without_reducer_authority"
    if status.field in {"search_recall_status", "index_freshness_status"}:
        reason = "search_health_status_without_producer_or_reducer_provenance"
    return {
        "artifact_path": status.artifact_path,
        "json_pointer": status.pointer,
        "field": status.field,
        "value": status.value,
        "producer_ref": status.record.get("producer_ref"),
        "classification": classification,
        "exclusion_reason": reason,
    }


def _default_artifact_paths(repo_root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for pattern in DEFAULT_ARTIFACT_GLOBS:
        paths.extend(
            path.relative_to(repo_root)
            for path in sorted(repo_root.glob(pattern))
            if path.is_file()
        )
    return tuple(paths)


def _missing_produced_by_keys(value: Any) -> set[str]:
    if not isinstance(value, Mapping):
        return set(PRODUCED_BY_REQUIRED_KEYS)
    return {
        key
        for key in PRODUCED_BY_REQUIRED_KEYS
        if key not in value or value.get(key) in (None, "", {}, [])
    }


def _record_without_output_hash(record: Mapping[str, Any]) -> dict[str, Any]:
    copied = json.loads(_json_dumps(record))
    produced_by = copied.get("produced_by")
    if isinstance(produced_by, dict):
        produced_by.pop("output_hash", None)
    return copied


def _hash_payload(payload: Any) -> str:
    encoded = _json_dumps(payload).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _iter_python_files(repo_root: Path, scan_roots: Sequence[Path]) -> Iterable[Path]:
    for scan_root in scan_roots:
        root = repo_root / scan_root
        if root.is_file() and root.suffix == ".py":
            yield root
        elif root.is_dir():
            yield from sorted(root.rglob("*.py"))


def _walk_json(value: Any, pointer: str = "$") -> Iterable[tuple[Any, str]]:
    yield value, pointer
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk_json(child, f"{pointer}/{_escape_pointer(str(key))}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_json(child, f"{pointer}/{index}")


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _read_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list | tuple):
        return [str(item) for item in value if item is not None]
    return []


def _dedupe_strings(values: Iterable[Any]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value not in (None, "")))


def _infer_producer_type(producer_ref: str, item: Mapping[str, Any], path: Path) -> str:
    explicit = item.get("producer_type")
    if explicit:
        return str(explicit)
    text = " ".join([producer_ref, path.as_posix()]).lower()
    if "measurement" in text or item.get("measurement_id"):
        return "measurement"
    if "request" in text or "demand" in text:
        return "external_request"
    if "fixture" in text or "/tests/" in text:
        return "test_fixture"
    return "derivation"


def _authority_boundary_issues(boundary: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for row in _as_list(boundary.get("slices")):
        if not isinstance(row, Mapping):
            continue
        for code in _string_list(row.get("issue_codes")):
            issues.append(
                _issue(
                    code,
                    f"{VALIDATION_AUTHORITY_BOUNDARY_PATH.as_posix()}#{row.get('slice_id')}",
                    "Legacy slice validator status has no GX closeout authority.",
                    slice_id=row.get("slice_id"),
                )
            )
    return _deduplicate_issues(issues)


def _data_mutation_coverage_row(
    repo_root: Path,
    *,
    requirement_id: str,
    test_refs: Sequence[str],
    corpus_kind: str,
    production_readiness_status: str = "test_only",
    requires_corpus_snapshot_hash: bool = False,
) -> dict[str, Any]:
    missing = [test_ref for test_ref in test_refs if not _test_ref_exists(repo_root, test_ref)]
    return {
        "requirement_id": requirement_id,
        "test_refs": list(test_refs),
        "missing_test_refs": missing,
        "coverage_status": "pass" if not missing else "missing",
        "corpus_kind": corpus_kind,
        "production_readiness_status": production_readiness_status,
        "requires_corpus_snapshot_hash": requires_corpus_snapshot_hash,
        "authority_boundary": {
            "can_create_source_contract": False,
            "can_create_admission": False,
            "can_create_promotion": False,
            "can_create_conversion": False,
        },
    }


def _test_ref_exists(repo_root: Path, test_ref: str) -> bool:
    path_text, _, node_id = test_ref.partition("::")
    path = repo_root / path_text
    if not path.exists():
        return False
    if not node_id:
        return True
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return f"def {node_id}" in source


def _write_artifacts(repo_root: Path, artifacts: Mapping[str, Any]) -> list[str]:
    mapping = {
        PINNED_REQUEST_PATH: artifacts["layer3_gx_pinned_request"],
        CONCEPT_ALIAS_SEED_ROWS_PATH: artifacts["layer3_gx_concept_alias_seed_rows"],
        CONCEPT_ALIAS_GRAPH_PATH: artifacts["layer3_gx_concept_alias_graph"],
        SCOPE_SEED_ROWS_PATH: artifacts["layer3_gx_scope_seed_rows"],
        DEMAND_PULL_REQUEST_PATH: artifacts["layer3_gx_demand_pull_request"],
        RUNTIME_LITERAL_LINT_PATH: artifacts["layer3_gx_runtime_literal_lint"],
        REDUCER_INTEGRITY_REPORT_PATH: artifacts["layer3_gx_reducer_integrity_report"],
        POSITIVE_STATUS_PROVENANCE_PATH: artifacts["layer3_gx_positive_status_provenance"],
        PRODUCER_REGISTRY_PATH: artifacts["layer3_gx_producer_registry"],
        PRODUCER_ROOT_CHAIN_REPORT_PATH: artifacts["layer3_gx_producer_root_chain_report"],
        MEASUREMENT_REPLAY_REPORT_PATH: artifacts["layer3_gx_measurement_replay_report"],
        VERTICAL_PINNED_ROUTE_REPORT_PATH: artifacts["layer3_gx_vertical_pinned_route_report"],
        PROVISIONAL_PINNED_ROUTE_OUTCOME_PATH: artifacts[
            "layer3_gx_provisional_pinned_route_outcome_report"
        ],
        PROVISIONAL_BLOCKER_AUDIT_RECORD_PATH: artifacts[
            "layer3_gx_provisional_blocker_audit_record"
        ],
        FINAL_PINNED_ROUTE_OUTCOME_PATH: artifacts[
            "layer3_gx_final_pinned_route_outcome_report"
        ],
        FINAL_BLOCKER_AUDIT_RECORD_PATH: artifacts["layer3_gx_final_blocker_audit_record"],
        DATA_MUTATION_FREE_GROWTH_REPORT_PATH: artifacts[
            "layer3_gx_data_mutation_free_growth_test_report"
        ],
        G4_G5_DEREFERENCE_WAIST_COURT_REPORT_PATH: artifacts[
            "layer3_gx_g4_g5_dereference_waist_court_report"
        ],
        PERSISTED_STATUS_RECOMPUTE_DRIFT_PATH: artifacts[
            "layer3_gx_persisted_status_recompute_drift"
        ],
        STATUS_VOCABULARY_DELTA_PATH: artifacts["layer3_gx_status_vocabulary_delta"],
        CORRECTION_RETRACTION_LOG_PATH: artifacts["layer3_gx_correction_retraction_log"],
        INDEPENDENT_AUDIT_SAMPLE_PATH: artifacts["layer3_gx_independent_audit_sample"],
        VALIDATION_AUTHORITY_BOUNDARY_PATH: artifacts["layer3_gx_validation_authority_boundary"],
        EXPECTED_RED_CHECKS_PATH: artifacts["layer3_gx_expected_red_checks"],
        HUMAN_APPROVAL_RECEIPTS_PATH: artifacts["layer3_gx_human_approval_receipts"],
    }
    written: list[str] = []
    for path, payload in mapping.items():
        atomic_write_json(repo_root / path, payload)
        written.append(path.as_posix())
    return written


def _issue(code: str, path: str, message: str, **extra: Any) -> dict[str, Any]:
    issue = {"code": code, "path": path, "message": message}
    issue.update(extra)
    return issue


def _issue_fingerprint(issue: Mapping[str, Any]) -> str:
    """Return a stable fingerprint for an expected-red issue instance."""

    payload = {
        "code": issue.get("code"),
        "path": issue.get("path"),
        "message": issue.get("message"),
        "literal": issue.get("literal"),
        "line": issue.get("line"),
        "pointer": issue.get("pointer"),
        "slice_id": issue.get("slice_id"),
        "producer_ref": issue.get("producer_ref"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _deduplicate_issues(issues: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for issue in issues:
        code = str(issue.get("code") or "")
        path = str(issue.get("path") or "")
        message = str(issue.get("message") or "")
        key = (code, path, message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(issue))
    return deduped


def _removal_condition(code: str) -> str:
    if code == "layer3_gx_runtime_literal_forbidden":
        return "Task 1 removes or data-owns runtime domain/positive literals and the AST lint has zero unapproved hits."
    if code == "layer3_gx_reducer_provenance_missing":
        return "Task 4 writes reducer provenance for every positive persisted status."
    if code == "layer3_gx_producer_root_invalid":
        return "Task 0/5 producer registry proves valid measurement or external_request roots."
    if code == "layer3_gx_measurement_replay_contract_missing":
        return "Measurement roots carry executable replay contracts and hash comparison passes."
    if "legacy_green" in code:
        return "Validation authority boundary marks the slice gx_hardened after the GX validator passes for that slice."
    return "Named GX producer/resolver/reducer/artifact is wired or the issue is explicitly superseded by a narrower diagnostic."


def _json_dumps(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _render_text(report: Mapping[str, Any]) -> str:
    lines = [
        f"Layer 3 GX hardening status: {report['status']}",
        f"issue_count: {report['summary']['issue_count']}",
        f"expected_red_check_count: {report['summary']['expected_red_check_count']}",
    ]
    for issue in report["issues"][:25]:
        lines.append(f"- {issue['code']} @ {issue['path']}: {issue['message']}")
    if len(report["issues"]) > 25:
        lines.append(f"- ... {len(report['issues']) - 25} more issues")
    return "\n".join(lines) + "\n"


def _resolve_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _is_test_path(path: str) -> bool:
    return path.startswith("tests/")


if __name__ == "__main__":
    raise SystemExit(main())
