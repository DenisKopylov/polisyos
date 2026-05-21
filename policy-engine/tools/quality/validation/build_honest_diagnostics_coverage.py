#!/usr/bin/env python3
"""Build the Honest Diagnostics substrate coverage dashboard."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.invariants import MINIMUM_CLOSEOUT_GATES  # noqa: E402

SCHEMA_VERSION = "policyos.honest_diagnostics_coverage.v1"
TOOL_NAME = "quality.validation.build-honest-diagnostics-coverage"
GENERATED_AT = "2026-05-15T00:00:00Z"
DEFAULT_REGISTRY = Path("architecture/production_quality/invariant_registry.toml")
DEFAULT_OUTPUT_DIR = Path("_build/honest-diagnostics/coverage")
DEFAULT_OPERATIONAL_CLOSEOUT_REPORT = Path(
    "_build/honest-diagnostics/rebaseline/wave-4/wave4_operational_closeout.json"
)

REQUIRED_INVARIANT_FIELDS = frozenset(
    {
        "invariant_id",
        "minimum_closeout_gate",
        "pql_id",
        "final_owner",
        "producer_owners",
        "runtime_event_names",
        "required_artifact_kinds",
        "required_ref_keys",
        "evidence_classes",
        "allowed_provenance_kinds",
        "required_schema_contracts",
        "scorecard_gate_names",
        "readiness_check",
        "approval_policy",
        "override_policy",
        "non_overridable_blockers",
        "dashboard_projection_policy",
        "public_artifact_policy",
        "conflict_policy",
        "failure_code",
        "diagnostic_owner",
        "dependencies",
        "consumers",
        "next_diagnostic_command",
        "negative_tests",
    }
)
REQUIRED_STRING_INVARIANT_FIELDS = frozenset(
    {
        "invariant_id",
        "minimum_closeout_gate",
        "pql_id",
        "final_owner",
        "readiness_check",
        "approval_policy",
        "override_policy",
        "dashboard_projection_policy",
        "public_artifact_policy",
        "conflict_policy",
        "failure_code",
        "diagnostic_owner",
        "next_diagnostic_command",
    }
)
REQUIRED_LIST_INVARIANT_FIELDS = frozenset(
    {
        "producer_owners",
        "runtime_event_names",
        "required_artifact_kinds",
        "required_ref_keys",
        "evidence_classes",
        "allowed_provenance_kinds",
        "required_schema_contracts",
        "scorecard_gate_names",
        "non_overridable_blockers",
        "consumers",
        "negative_tests",
    }
)
OPTIONAL_LIST_INVARIANT_FIELDS = frozenset({"dependencies"})

REQUIRED_METRIC_IDS = (
    "invariant_registry_complete_pct",
    "runtime_emitted_invariant_pct",
    "negative_control_coverage_pct",
    "authority_envelope_complete_pct",
    "payload_identity_verified_gate_pct",
    "fallback_ledger_coverage_pct",
    "authority_bearing_provenance_pct",
    "source_truth_conflict_gate_pct",
    "semantic_binding_gate_pct",
    "legacy_quarantine_classified_pct",
    "diagnostic_slo_metric_coverage_pct",
    "attestation_observed_material_coverage_pct",
    "public_redaction_projection_coverage_pct",
    "false_pass_rate_negative_controls",
    "replay_drift_gate_pct",
    "operator_ttrc_p50_minutes",
    "operator_ttrc_p90_minutes",
)

METRIC_DEFINITIONS: dict[str, dict[str, Any]] = {
    "invariant_registry_complete_pct": {
        "title": "Invariant registry completeness",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"wave0": ">= 10", "wave1": "100", "wave3": "100", "final": "100"},
    },
    "runtime_emitted_invariant_pct": {
        "title": "Runtime-emitted invariant coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": "baseline only",
            "wave3": ">= 85",
            "final": "100",
        },
    },
    "negative_control_coverage_pct": {
        "title": "Negative-control coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"wave0": ">= 25", "wave1": ">= 60", "wave3": "100", "final": "100"},
    },
    "authority_envelope_complete_pct": {
        "title": "Authority envelope completeness",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "fixture baseline",
            "wave1": "100 for contract tests",
            "wave3": ">= 90 runtime bundles",
            "final": "100",
        },
    },
    "payload_identity_verified_gate_pct": {
        "title": "Payload identity verified gate coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": "baseline only",
            "wave3": "100",
            "final": "100",
        },
    },
    "fallback_ledger_coverage_pct": {
        "title": "Fallback ledger coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": ">= 60 known paths",
            "wave3": ">= 90 known paths",
            "final": "100",
        },
    },
    "authority_bearing_provenance_pct": {
        "title": "Authority-bearing provenance coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": "100 for fixtures",
            "wave3": "100",
            "final": "100",
        },
    },
    "source_truth_conflict_gate_pct": {
        "title": "Source-truth conflict gate coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": ">= 80 field families",
            "wave3": "100",
            "final": "100",
        },
    },
    "semantic_binding_gate_pct": {
        "title": "Semantic binding gate coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": "baseline only",
            "wave3": ">= 60",
            "final": "100",
        },
    },
    "legacy_quarantine_classified_pct": {
        "title": "Legacy quarantine classification coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": ">= 90 known bundles",
            "wave3": "100",
            "final": "100",
        },
    },
    "diagnostic_slo_metric_coverage_pct": {
        "title": "Diagnostic SLO metric coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": "baseline only",
            "wave3": "baseline only",
            "wave4": "100",
            "final": "100",
        },
    },
    "attestation_observed_material_coverage_pct": {
        "title": "Attestation observed-material coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": "baseline only",
            "wave3": "baseline only",
            "wave4": "100",
            "final": "100",
        },
    },
    "public_redaction_projection_coverage_pct": {
        "title": "Public redaction projection coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": "baseline only",
            "wave3": "baseline only",
            "wave4": "100",
            "final": "100",
        },
    },
    "false_pass_rate_negative_controls": {
        "title": "False-pass rate for negative controls",
        "unit": "rate",
        "direction": "lower_is_better",
        "target": {"wave0": "0", "wave1": "0", "wave3": "0", "final": "0"},
    },
    "replay_drift_gate_pct": {
        "title": "Replay and drift gate coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": "baseline only",
            "wave3": "baseline only",
            "final": "100",
        },
    },
    "operator_ttrc_p50_minutes": {
        "title": "Operator time-to-root-cause p50",
        "unit": "minutes",
        "direction": "lower_is_better",
        "target": {
            "wave0": "measured",
            "wave1": "measured",
            "wave3": "<= 10",
            "final": "<= 5",
        },
    },
    "operator_ttrc_p90_minutes": {
        "title": "Operator time-to-root-cause p90",
        "unit": "minutes",
        "direction": "lower_is_better",
        "target": {
            "wave0": "measured",
            "wave1": "measured",
            "wave3": "<= 20",
            "final": "<= 10",
        },
    },
}


class CoverageDefinitionError(ValueError):
    """Raised when the dashboard metric contract is incomplete."""


class CoverageInputError(ValueError):
    """Raised when a coverage input file cannot be read as the expected contract."""


def build_coverage_payload(
    *,
    repo_root: Path = REPO_ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
    operational_closeout_report_path: Path | None = DEFAULT_OPERATIONAL_CLOSEOUT_REPORT,
    wave5_metamorphic_report_path: Path | None = None,
    wave5_resilience_report_path: Path | None = None,
    wave5_replay_report_path: Path | None = None,
    substrate_drift_report_path: Path | None = None,
    metric_definitions: Mapping[str, Mapping[str, Any]] = METRIC_DEFINITIONS,
    wave: str | None = None,
    require_targets: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    registry_file = _resolve(repo_root, registry_path)
    validate_metric_definitions(metric_definitions)
    invariants = _load_invariants(registry_file)
    closeout_report = _load_optional_closeout_report(
        _resolve(repo_root, operational_closeout_report_path)
        if operational_closeout_report_path is not None
        else None
    )
    wave5_metamorphic_report = _load_optional_json_report(
        _resolve(repo_root, wave5_metamorphic_report_path)
        if wave5_metamorphic_report_path is not None
        else None
    )
    wave5_resilience_report = _load_optional_json_report(
        _resolve(repo_root, wave5_resilience_report_path)
        if wave5_resilience_report_path is not None
        else None
    )
    wave5_replay_report = _load_optional_json_report(
        _resolve(repo_root, wave5_replay_report_path)
        if wave5_replay_report_path is not None
        else None
    )
    substrate_drift_report = _load_optional_json_report(
        _resolve(repo_root, substrate_drift_report_path)
        if substrate_drift_report_path is not None
        else None
    )
    metric_rows = _build_metric_rows(
        invariants,
        metric_definitions,
        closeout_report,
        wave5_metamorphic_report=wave5_metamorphic_report,
        wave5_resilience_report=wave5_resilience_report,
        wave5_replay_report=wave5_replay_report,
    )
    invalid_invariants = _invalid_invariants(invariants)
    missing_evidence = _missing_wave5_evidence(
        require_targets=require_targets,
        wave5_metamorphic_report=wave5_metamorphic_report,
        wave5_resilience_report=wave5_resilience_report,
        wave5_replay_report=wave5_replay_report,
        substrate_drift_report=substrate_drift_report,
    )
    target_violations = (
        _target_violations(metric_rows, wave=wave)
        if require_targets and wave is not None
        else []
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": GENERATED_AT,
        "repo_root": str(repo_root),
        "source": {
            "invariant_registry": _rel(registry_file, repo_root),
            "invariant_count": len(invariants),
            "operational_closeout_report": (
                _rel(
                    _resolve(repo_root, operational_closeout_report_path),
                    repo_root,
                )
                if operational_closeout_report_path is not None
                and _resolve(repo_root, operational_closeout_report_path).is_file()
                else None
            ),
            "wave5_metamorphic_report": (
                _rel(_resolve(repo_root, wave5_metamorphic_report_path), repo_root)
                if wave5_metamorphic_report_path is not None
                else None
            ),
            "wave5_resilience_report": (
                _rel(_resolve(repo_root, wave5_resilience_report_path), repo_root)
                if wave5_resilience_report_path is not None
                else None
            ),
            "wave5_replay_report": (
                _rel(_resolve(repo_root, wave5_replay_report_path), repo_root)
                if wave5_replay_report_path is not None
                else None
            ),
            "substrate_drift_report": (
                _rel(_resolve(repo_root, substrate_drift_report_path), repo_root)
                if substrate_drift_report_path is not None
                else None
            ),
        },
        "summary": {
            "status": (
                "pass"
                if not invalid_invariants and not target_violations and not missing_evidence
                else "fail"
            ),
            "metric_count": len(metric_rows),
            "required_metric_count": len(REQUIRED_METRIC_IDS),
            "invariant_count": len(invariants),
            "known_minimum_closeout_gate_count": len(MINIMUM_CLOSEOUT_GATES),
            "invalid_invariant_count": len(invalid_invariants),
            "target_violation_count": len(target_violations),
            "missing_evidence_count": len(missing_evidence),
            "wave": wave,
        },
        "metrics": metric_rows,
        "invalid_invariants": invalid_invariants,
        "missing_evidence": missing_evidence,
        "target_violations": target_violations,
    }


def validate_metric_definitions(
    metric_definitions: Mapping[str, Mapping[str, Any]],
) -> None:
    missing = [
        metric_id
        for metric_id in REQUIRED_METRIC_IDS
        if metric_id not in metric_definitions
    ]
    if missing:
        raise CoverageDefinitionError(
            "Missing Honest Diagnostics coverage metric definitions: "
            + ", ".join(missing)
        )
    invalid = [
        metric_id
        for metric_id in REQUIRED_METRIC_IDS
        if not _definition_is_complete(metric_definitions[metric_id])
    ]
    if invalid:
        raise CoverageDefinitionError(
            "Incomplete Honest Diagnostics coverage metric definitions: "
            + ", ".join(invalid)
        )


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_markdown(payload: Mapping[str, Any]) -> str:
    metrics = payload["metrics"]
    if not isinstance(metrics, Mapping):
        raise CoverageInputError("Coverage payload metrics must be a mapping.")
    source = payload["source"]
    summary = payload["summary"]
    lines = [
        "# Honest Diagnostics Coverage",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Invariant registry: `{source['invariant_registry']}`",
        f"- Invariants: {source['invariant_count']}",
        f"- Status: `{summary['status']}`",
        "",
        "## Metrics",
        "",
        (
            "| Metric | Value | Numerator | Denominator | Denominator Changed | "
            "Wave 0 | Wave 1 | Wave 3 | Wave 4 | Final |"
        ),
        "| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for metric_id in REQUIRED_METRIC_IDS:
        row = metrics[metric_id]
        definition = row["definition"]
        target = definition["target"]
        lines.append(
            "| "
            f"`{metric_id}` | {_render_value(row['value'])} | "
            f"{_render_value(row['numerator'])} | {_render_value(row['denominator'])} | "
            f"{str(row['denominator_changed']).lower()} | "
            f"{target['wave0']} | {target['wave1']} | {target['wave3']} | "
            f"{target.get('wave4', '')} | {target['final']} |"
        )

    invalid = payload.get("invalid_invariants")
    if invalid:
        lines.extend(["", "## Invalid Invariants", ""])
        for row in invalid:
            lines.append(f"- `{row['invariant_id']}` missing: {', '.join(row['missing_fields'])}")

    return "\n".join(lines) + "\n"


def _build_metric_rows(
    invariants: Sequence[Mapping[str, Any]],
    metric_definitions: Mapping[str, Mapping[str, Any]],
    closeout_report: Mapping[str, Any] | None = None,
    *,
    wave5_metamorphic_report: Mapping[str, Any] | None = None,
    wave5_resilience_report: Mapping[str, Any] | None = None,
    wave5_replay_report: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    denominator = len(MINIMUM_CLOSEOUT_GATES)
    known_gate_rows = {
        str(row.get("minimum_closeout_gate") or "").strip(): row for row in invariants
    }
    negative_test_count = sum(len(_list(row.get("negative_tests"))) for row in invariants)
    closeout_items = _closeout_item_statuses(closeout_report)
    diagnostic_slo_refs = (
        closeout_report.get("diagnostic_slo_refs")
        if isinstance(closeout_report, Mapping)
        else None
    )
    attestation_refs = (
        closeout_report.get("attestation_refs")
        if isinstance(closeout_report, Mapping)
        else None
    )
    wave5_controls = _wave5_negative_controls(wave5_metamorphic_report)
    wave5_false_passes = [
        control for control in wave5_controls if not _wave5_control_passed(control)
    ]
    wave5_semantic = _wave5_semantic_binding_metric(wave5_metamorphic_report)
    wave5_slo = _wave5_resilience_slo_metric(wave5_resilience_report)
    wave5_ttrc = _wave5_operator_ttrc(wave5_resilience_report)
    wave5_replay = _wave5_replay_metric(wave5_replay_report)
    rows = {
        "invariant_registry_complete_pct": _pct_metric(
            numerator=sum(
                1
                for gate in MINIMUM_CLOSEOUT_GATES
                if (row := known_gate_rows.get(gate)) is not None and not _missing_fields(row)
            ),
            denominator=denominator,
        ),
        "runtime_emitted_invariant_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _list(row.get("runtime_event_names"))),
            denominator=denominator,
        ),
        "negative_control_coverage_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _list(row.get("negative_tests"))),
            denominator=denominator,
        ),
        "authority_envelope_complete_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _has_authority_envelope_fields(row)),
            denominator=denominator,
        ),
        "payload_identity_verified_gate_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _has_payload_identity_gate(row)),
            denominator=denominator,
        ),
        "fallback_ledger_coverage_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _has_any_key(row, "fallback")),
            denominator=denominator,
        ),
        "authority_bearing_provenance_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _has_authority_bearing_provenance(row)),
            denominator=denominator,
        ),
        "source_truth_conflict_gate_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _has_source_truth_conflict_gate(row)),
            denominator=denominator,
        ),
        "semantic_binding_gate_pct": _pct_metric(
            numerator=wave5_semantic["numerator"]
            if wave5_semantic is not None
            else _wave4_item_numerator(
                    closeout_items,
                    "semantic_binding_claim_level",
                    fallback=sum(1 for row in invariants if _has_any_key(row, "semantic")),
                ),
            denominator=wave5_semantic["denominator"]
            if wave5_semantic is not None
            else _wave4_item_denominator(closeout_items, fallback=denominator),
        ),
        "legacy_quarantine_classified_pct": _pct_metric(
            numerator=_wave4_item_numerator(
                closeout_items,
                "legacy_quarantined_unless_compatible",
                fallback=sum(
                    1
                    for row in invariants
                    if _has_any_key(row, "legacy") or _has_any_key(row, "quarantine")
                ),
            ),
            denominator=_wave4_item_denominator(closeout_items, fallback=denominator),
        ),
        "diagnostic_slo_metric_coverage_pct": _pct_metric(
            numerator=wave5_slo["numerator"]
            if wave5_slo is not None
            else (
                len(diagnostic_slo_refs) if isinstance(diagnostic_slo_refs, Mapping) else 0
            ),
            denominator=wave5_slo["denominator"] if wave5_slo is not None else 16,
        ),
        "attestation_observed_material_coverage_pct": _pct_metric(
            numerator=(
                len(attestation_refs)
                if isinstance(attestation_refs, Mapping)
                else sum(1 for row in invariants if _has_any_key(row, "attestation"))
            ),
            denominator=(
                max(1, len(attestation_refs))
                if isinstance(attestation_refs, Mapping)
                else max(1, sum(1 for row in invariants if _has_any_key(row, "attestation")))
            ),
        ),
        "public_redaction_projection_coverage_pct": _pct_metric(
            numerator=_wave4_item_numerator(
                closeout_items,
                "public_exports_projection_only",
                fallback=sum(
                    1
                    for row in invariants
                    if _has_any_key(row, "public") or _has_any_key(row, "redaction")
                ),
            ),
            denominator=_wave4_item_denominator(
                closeout_items,
                fallback=max(
                    1,
                    sum(
                        1
                        for row in invariants
                        if _has_any_key(row, "public") or _has_any_key(row, "redaction")
                    ),
                ),
            ),
        ),
        "false_pass_rate_negative_controls": {
            "value": (
                0.0
                if wave5_controls and not wave5_false_passes
                else (
                    round(len(wave5_false_passes) / len(wave5_controls), 3)
                    if wave5_controls
                    else None
                )
            ),
            "numerator": len(wave5_false_passes) if wave5_controls else 0,
            "denominator": len(wave5_controls) if wave5_controls else 0,
            "denominator_changed": False,
        },
        "replay_drift_gate_pct": (
            _pct_metric(
                numerator=wave5_replay["numerator"],
                denominator=wave5_replay["denominator"],
            )
            if wave5_replay is not None
            else {
                "value": None,
                "numerator": 0,
                "denominator": 0,
                "denominator_changed": False,
            }
        ),
        "operator_ttrc_p50_minutes": {
            "value": wave5_ttrc.get("p50") if wave5_ttrc is not None else None,
            "numerator": wave5_ttrc.get("p50") if wave5_ttrc is not None else 0,
            "denominator": 1 if wave5_ttrc is not None else 0,
            "denominator_changed": False,
            "measurement_status": (
                "measured_from_wave5_resilience_report"
                if wave5_ttrc is not None
                else "missing_wave5_runtime_evidence"
            ),
        },
        "operator_ttrc_p90_minutes": {
            "value": wave5_ttrc.get("p90") if wave5_ttrc is not None else None,
            "numerator": wave5_ttrc.get("p90") if wave5_ttrc is not None else 0,
            "denominator": 1 if wave5_ttrc is not None else 0,
            "denominator_changed": False,
            "measurement_status": (
                "measured_from_wave5_resilience_report"
                if wave5_ttrc is not None
                else "missing_wave5_runtime_evidence"
            ),
        },
    }
    metric_rows = {
        metric_id: {
            "metric_id": metric_id,
            **rows[metric_id],
            "definition": dict(metric_definitions[metric_id]),
        }
        for metric_id in REQUIRED_METRIC_IDS
    }
    metric_rows["semantic_binding_gate_pct"]["measurement_status"] = (
        "measured_from_wave5_metamorphic_report"
        if wave5_semantic is not None
        else (
            "measured_from_wave4_closeout"
            if closeout_report is not None
            else "measured_from_registry_contract"
        )
    )
    metric_rows["diagnostic_slo_metric_coverage_pct"]["measurement_status"] = (
        "measured_from_wave5_resilience_report"
        if wave5_slo is not None
        else (
            "measured_from_wave4_closeout"
            if closeout_report is not None
            else "measured_from_registry_contract"
        )
    )
    for metric_id in (
        "legacy_quarantine_classified_pct",
        "attestation_observed_material_coverage_pct",
        "public_redaction_projection_coverage_pct",
    ):
        metric_rows[metric_id]["measurement_status"] = (
            "measured_from_wave4_closeout"
            if closeout_report is not None
            else "measured_from_registry_contract"
        )
    return metric_rows


def _pct_metric(*, numerator: int, denominator: int) -> dict[str, Any]:
    value = 0.0 if denominator <= 0 else round((numerator / denominator) * 100, 3)
    return {
        "value": value,
        "numerator": numerator,
        "denominator": denominator,
        "denominator_changed": False,
    }


def _load_invariants(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("rb") as stream:
            payload = tomllib.load(stream)
    except FileNotFoundError as exc:
        raise CoverageInputError(f"Invariant registry not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise CoverageInputError(f"Invariant registry is invalid TOML: {path}: {exc}") from exc

    invariants = payload.get("invariants")
    if not isinstance(invariants, list):
        raise CoverageInputError("Invariant registry must define [[invariants]] rows.")
    if not invariants:
        raise CoverageInputError("Invariant registry must contain at least one invariant.")
    if not all(isinstance(row, Mapping) for row in invariants):
        raise CoverageInputError("Every invariant registry row must be a TOML table.")
    return [dict(row) for row in invariants]


def _load_optional_closeout_report(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CoverageInputError(f"Wave 4 closeout report is invalid JSON: {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise CoverageInputError(f"Wave 4 closeout report must be a JSON object: {path}")
    if payload.get("schema_version") != "policyos.honest_diagnostics.wave4_closeout.v1":
        raise CoverageInputError(f"Wave 4 closeout report has unexpected schema: {path}")
    return dict(payload)


def _load_optional_json_report(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CoverageInputError(f"Wave 5 report is invalid JSON: {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise CoverageInputError(f"Wave 5 report must be a JSON object: {path}")
    return dict(payload)


def _missing_wave5_evidence(
    *,
    require_targets: bool,
    wave5_metamorphic_report: Mapping[str, Any] | None,
    wave5_resilience_report: Mapping[str, Any] | None,
    wave5_replay_report: Mapping[str, Any] | None,
    substrate_drift_report: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if not require_targets:
        return []
    required = (
        ("hds_wave5_metamorphic_report_missing", "wave5_metamorphic_report"),
        ("hds_wave5_resilience_report_missing", "wave5_resilience_report"),
        ("hds_wave5_replay_report_missing", "wave5_replay_report"),
        ("hds_substrate_drift_report_missing", "substrate_drift_report"),
    )
    reports = {
        "wave5_metamorphic_report": wave5_metamorphic_report,
        "wave5_resilience_report": wave5_resilience_report,
        "wave5_replay_report": wave5_replay_report,
        "substrate_drift_report": substrate_drift_report,
    }
    missing = [
        {
            "code": code,
            "missing_evidence_type": name,
            "message": f"{name} is required when --require-targets is used.",
        }
        for code, name in required
        if reports[name] is None
    ]
    if (
        substrate_drift_report is not None
        and str(substrate_drift_report.get("status") or "").casefold() != "pass"
    ):
        missing.append(
            {
                "code": "hds_substrate_drift_report_not_passing",
                "missing_evidence_type": "substrate_drift_report",
                "message": "substrate_drift_report must have status=pass when --require-targets is used.",
                "actual_status": str(substrate_drift_report.get("status") or "missing"),
            }
        )
    return missing


def _wave5_negative_controls(
    report: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    if not isinstance(report, Mapping):
        return []
    controls: list[Mapping[str, Any]] = []
    for scenario in report.get("scenario_reports") or []:
        if not isinstance(scenario, Mapping):
            continue
        controls.extend(_controls_from_container(scenario.get("negative_controls")))
        controls.extend(_controls_from_container(scenario.get("cross_domain")))
    controls.extend(_controls_from_container(report))
    return controls


def _controls_from_container(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        return []
    controls = value.get("controls")
    if not isinstance(controls, list):
        return []
    return [control for control in controls if isinstance(control, Mapping)]


def _wave5_control_passed(control: Mapping[str, Any]) -> bool:
    status = str(control.get("status") or "").strip().casefold()
    observed = str(control.get("observed_status") or "").strip().casefold()
    failure_codes = _list(control.get("failure_codes"))
    expected = _list(control.get("expected_failure_codes"))
    if status != "pass":
        return False
    if expected and not failure_codes:
        return False
    if expected and set(failure_codes) != set(expected):
        return False
    if expected and observed not in {"blocked", "fail", "failed"}:
        return False
    return True


def _wave5_semantic_binding_metric(
    report: Mapping[str, Any] | None,
) -> dict[str, int] | None:
    if not isinstance(report, Mapping):
        return None
    scenarios = [
        scenario
        for scenario in report.get("scenario_reports") or []
        if isinstance(scenario, Mapping)
    ]
    if not scenarios:
        return None
    numerator = 0
    for scenario in scenarios:
        semantic = scenario.get("semantic_binding_report")
        cross_domain = scenario.get("cross_domain")
        if isinstance(semantic, Mapping) and semantic.get("status") == "pass":
            numerator += 1
        elif isinstance(cross_domain, Mapping) and cross_domain.get("status") == "pass":
            numerator += 1
    return {"numerator": numerator, "denominator": len(scenarios)}


def _wave5_resilience_slo_metric(
    report: Mapping[str, Any] | None,
) -> dict[str, int] | None:
    if not isinstance(report, Mapping):
        return None
    required = {
        "trace_continuity",
        "event_loss",
        "payload_mismatch",
        "latency",
        "retry_amplification",
        "stale_evidence",
        "operator_root_cause_fields",
    }
    observed: set[str] = set()
    for scenario in report.get("scenarios") or []:
        if not isinstance(scenario, Mapping):
            continue
        evidence = scenario.get("runtime_owned_evidence")
        slo = scenario.get("diagnostic_slo_evidence")
        if not (
            isinstance(evidence, Mapping)
            and evidence.get("runtime_owned") is True
            and evidence.get("emission_mode") == "runtime_cas_event"
            and isinstance(slo, Mapping)
            and slo.get("runtime_owned") is True
            and slo.get("emission_mode") == "runtime_cas_event"
        ):
            continue
        for metric in slo.get("metrics") or []:
            if isinstance(metric, Mapping) and str(metric.get("evidence_ref") or "").startswith("sha256:"):
                observed.add(str(metric.get("metric_id") or ""))
    return {"numerator": len(required & observed), "denominator": len(required)}


def _wave5_operator_ttrc(report: Mapping[str, Any] | None) -> dict[str, float] | None:
    if not isinstance(report, Mapping):
        return None
    ttrc = report.get("operator_ttrc_minutes")
    if not isinstance(ttrc, Mapping):
        return None
    try:
        return {"p50": float(ttrc["p50"]), "p90": float(ttrc["p90"])}
    except (KeyError, TypeError, ValueError):
        return None


def _wave5_replay_metric(report: Mapping[str, Any] | None) -> dict[str, int] | None:
    if not isinstance(report, Mapping):
        return None
    cases = [case for case in report.get("cases") or [] if isinstance(case, Mapping)]
    if not cases:
        return None
    numerator = sum(1 for case in cases if str(case.get("status") or "") == "pass")
    return {"numerator": numerator, "denominator": len(cases)}


def _closeout_item_statuses(report: Mapping[str, Any] | None) -> dict[str, str]:
    if report is None:
        return {}
    rows = report.get("exit_fence_items")
    if not isinstance(rows, list):
        return {}
    statuses: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        item_id = str(row.get("item_id") or "").strip()
        status = str(row.get("status") or "").strip()
        if item_id and status:
            statuses[item_id] = status
    return statuses


def _wave4_item_numerator(
    closeout_items: Mapping[str, str],
    item_id: str,
    *,
    fallback: int,
) -> int:
    if not closeout_items:
        return fallback
    return 1 if closeout_items.get(item_id) == "pass" else 0


def _wave4_item_denominator(closeout_items: Mapping[str, str], *, fallback: int) -> int:
    return 1 if closeout_items else fallback


def _invalid_invariants(invariants: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, invariant in enumerate(invariants, start=1):
        missing = _missing_fields(invariant)
        if not missing:
            continue
        rows.append(
            {
                "invariant_id": _invariant_id(invariant, index),
                "missing_fields": missing,
            }
        )
    referenced_gates = {
        str(row.get("minimum_closeout_gate") or "").strip() for row in invariants
    }
    for gate in sorted(set(MINIMUM_CLOSEOUT_GATES) - referenced_gates):
        rows.append(
            {
                "invariant_id": gate,
                "missing_fields": ["minimum_closeout_gate_registry_row"],
            }
        )
    return rows


def _target_violations(
    metrics: Mapping[str, Mapping[str, Any]],
    *,
    wave: str,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    target_key = wave.replace("-", "")
    target_aliases = {wave, target_key}
    for metric_id, row in metrics.items():
        definition = row.get("definition")
        if not isinstance(definition, Mapping):
            continue
        target = definition.get("target")
        if not isinstance(target, Mapping):
            continue
        expression = None
        for key in target_aliases:
            if key in target:
                expression = str(target[key])
                break
        if expression is None:
            continue
        if not _target_satisfied(row, expression=expression):
            violations.append(
                {
                    "metric_id": metric_id,
                    "target": expression,
                    "value": row.get("value"),
                    "code": "hds_coverage_target_missed",
                }
            )
    return violations


def _target_satisfied(row: Mapping[str, Any], *, expression: str) -> bool:
    value = row.get("value")
    if value is None:
        return not re.search(r"\d", expression)
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return False
    normalized = expression.strip().casefold()
    if normalized.startswith(">="):
        return numeric_value >= float(re.search(r"\d+(?:\.\d+)?", normalized).group(0))
    if normalized.startswith("<="):
        return numeric_value <= float(re.search(r"\d+(?:\.\d+)?", normalized).group(0))
    match = re.search(r"\d+(?:\.\d+)?", normalized)
    if match is None:
        return True
    target_value = float(match.group(0))
    direction = str(row.get("definition", {}).get("direction") or "")
    if direction == "lower_is_better":
        return numeric_value <= target_value
    return numeric_value >= target_value


def _missing_fields(invariant: Mapping[str, Any]) -> list[str]:
    missing = set(REQUIRED_INVARIANT_FIELDS - set(invariant))
    invalid = {
        field
        for field in REQUIRED_STRING_INVARIANT_FIELDS
        if field in invariant and not _non_empty_string(invariant.get(field))
    }
    invalid.update(
        field
        for field in REQUIRED_LIST_INVARIANT_FIELDS
        if field in invariant and not _list(invariant.get(field))
    )
    invalid.update(
        field
        for field in OPTIONAL_LIST_INVARIANT_FIELDS
        if field in invariant and not isinstance(invariant.get(field), list)
    )
    return sorted(missing | invalid)


def _invariant_id(invariant: Mapping[str, Any], index: int) -> str:
    invariant_id = invariant.get("invariant_id")
    if isinstance(invariant_id, str) and invariant_id:
        return invariant_id
    return f"invariants[{index}]"


def _definition_is_complete(definition: Mapping[str, Any]) -> bool:
    target = definition.get("target")
    return (
        bool(definition.get("title"))
        and definition.get("unit") in {"percent", "rate", "minutes"}
        and definition.get("direction") in {"higher_is_better", "lower_is_better"}
        and isinstance(target, Mapping)
        and all(target.get(key) for key in ("wave0", "wave1", "wave3", "final"))
    )


def _has_authority_envelope_fields(invariant: Mapping[str, Any]) -> bool:
    return all(
        _list(invariant.get(key))
        for key in (
            "runtime_event_names",
            "required_artifact_kinds",
            "required_ref_keys",
            "allowed_provenance_kinds",
            "required_schema_contracts",
        )
    ) and bool(str(invariant.get("final_owner") or "").strip())


def _has_payload_identity_gate(invariant: Mapping[str, Any]) -> bool:
    blockers = set(_list(invariant.get("non_overridable_blockers")))
    return "authority_payload_mismatch" in blockers and bool(
        _list(invariant.get("required_ref_keys"))
    )


def _has_authority_bearing_provenance(invariant: Mapping[str, Any]) -> bool:
    evidence_classes = set(_list(invariant.get("evidence_classes")))
    provenance = set(_list(invariant.get("allowed_provenance_kinds")))
    return "authority_bearing" in evidence_classes and bool(
        provenance & {"runtime_emitted", "runtime_blocker"}
    )


def _has_source_truth_conflict_gate(invariant: Mapping[str, Any]) -> bool:
    return (
        invariant.get("conflict_policy") == "fail_closed"
        and invariant.get("dashboard_projection_policy") == "projection_only"
    )


def _has_any_key(invariant: Mapping[str, Any], needle: str) -> bool:
    return any(needle in key for key in invariant)


def _list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _render_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--wave", choices=("wave-0", "wave-1", "wave-3", "wave-4", "final"))
    parser.add_argument(
        "--operational-closeout-report",
        type=Path,
        default=DEFAULT_OPERATIONAL_CLOSEOUT_REPORT,
    )
    parser.add_argument("--wave5-metamorphic-report", type=Path)
    parser.add_argument("--wave5-resilience-report", type=Path)
    parser.add_argument("--wave5-replay-report", type=Path)
    parser.add_argument("--substrate-drift-report", type=Path)
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        help=(
            "Use the Wave 4 operational closeout report written inside this bundle "
            "when --operational-closeout-report is not set."
        ),
    )
    parser.add_argument("--require-targets", action="store_true")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if any invariant row is incomplete.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_dir = _resolve(repo_root, args.output_dir)
    json_output = (
        _resolve(repo_root, args.json_output)
        if args.json_output
        else output_dir / "coverage.json"
    )
    markdown_output = (
        _resolve(repo_root, args.markdown_output)
        if args.markdown_output
        else output_dir / "coverage.md"
    )

    try:
        payload = build_coverage_payload(
            repo_root=repo_root,
            registry_path=args.registry,
            operational_closeout_report_path=(
                args.operational_closeout_report
                if args.operational_closeout_report != DEFAULT_OPERATIONAL_CLOSEOUT_REPORT
                else (
                    args.bundle_dir / "quality_evidence" / "wave4_operational_closeout.json"
                    if args.bundle_dir is not None
                    else args.operational_closeout_report
                )
            ),
            wave5_metamorphic_report_path=args.wave5_metamorphic_report,
            wave5_resilience_report_path=args.wave5_resilience_report,
            wave5_replay_report_path=args.wave5_replay_report,
            substrate_drift_report_path=args.substrate_drift_report,
            wave=args.wave,
            require_targets=args.require_targets,
        )
    except (CoverageDefinitionError, CoverageInputError) as exc:
        sys.stderr.write(f"honest diagnostics coverage failed: {exc}\n")
        return 2

    atomic_write_text(json_output, dump_json(payload))
    atomic_write_text(markdown_output, render_markdown(payload))
    if (args.check or args.require_targets) and payload["summary"]["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
