"""Diagnostic SLO reports, error budgets, and fitness-control coverage."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

SCHEMA_VERSION = "policyos.runtime.diagnostic_slos.v1"
DEFAULT_OWNER = "team-assurance"
DEFAULT_EVIDENCE_REF = "quality_evidence/diagnostic_slo_report.json"
DEFAULT_NEXT_DIAGNOSTIC_COMMAND = (
    "uv run python tools/quality/validation/check_honest_diagnostics_proof_harness.py "
    "--repo-root . --require-passing"
)
DEFAULT_FITNESS_REGISTRY_PATH = (
    Path(__file__).resolve().parents[4]
    / "architecture"
    / "production_quality"
    / "diagnostic_fitness_functions.toml"
)
SERIOUS_CANARY_KINDS = frozenset({"governed", "production", "research"})
ALLOWED_FITNESS_TYPES = frozenset(
    {
        "positive_control",
        "negative_control",
        "mutation_control",
        "metamorphic_control",
    }
)

Comparator = Literal["at_least", "at_most"]


DIAGNOSTIC_SLO_METRIC_IDS = (
    "complete_authority_graph_rate",
    "evidence_completeness",
    "required_runtime_ref_verification_rate",
    "trace_continuity",
    "provenance_coverage",
    "fallback_ledger_coverage",
    "schema_compatibility_coverage",
    "semantic_binding_coverage",
    "blocker_precision",
    "blocker_recall",
    "detection_time",
    "stale_evidence_rate",
    "false_pass_rate_from_negative_controls",
    "false_block_rate_from_positive_controls",
    "redaction_coverage",
    "operator_time_to_root_cause",
)


@dataclass(frozen=True)
class DiagnosticSLOTarget:
    """One diagnostic SLO threshold."""

    metric_id: str
    description: str
    comparator: Comparator
    threshold: float
    stale_after_seconds: int = 86_400

    def passing_value(self) -> float:
        if self.comparator == "at_least":
            return self.threshold
        return 0.0


_TARGETS = (
    DiagnosticSLOTarget(
        "complete_authority_graph_rate",
        "Share of required authority graph refs present and linked.",
        "at_least",
        1.0,
    ),
    DiagnosticSLOTarget(
        "evidence_completeness",
        "Share of required diagnostic evidence reports present.",
        "at_least",
        1.0,
    ),
    DiagnosticSLOTarget(
        "required_runtime_ref_verification_rate",
        "Share of required runtime refs verified from runtime-owned surfaces.",
        "at_least",
        1.0,
    ),
    DiagnosticSLOTarget(
        "trace_continuity",
        "Share of required refs covered by unsampled diagnostic trace events.",
        "at_least",
        1.0,
    ),
    DiagnosticSLOTarget(
        "provenance_coverage",
        "Share of bundle files covered by provenance metadata.",
        "at_least",
        1.0,
    ),
    DiagnosticSLOTarget(
        "fallback_ledger_coverage",
        "Share of fallback or degradation uses covered by ledger records.",
        "at_least",
        1.0,
    ),
    DiagnosticSLOTarget(
        "schema_compatibility_coverage",
        "Share of closeout reports with scorecard-readable schema compatibility.",
        "at_least",
        1.0,
    ),
    DiagnosticSLOTarget(
        "semantic_binding_coverage",
        "Share of data-backed claims covered by semantic binding evidence.",
        "at_least",
        1.0,
    ),
    DiagnosticSLOTarget(
        "blocker_precision",
        "Share of emitted blockers that correspond to true closeout defects.",
        "at_least",
        0.95,
    ),
    DiagnosticSLOTarget(
        "blocker_recall",
        "Share of known defects caught by typed closeout blockers.",
        "at_least",
        0.95,
    ),
    DiagnosticSLOTarget(
        "detection_time",
        "Seconds between diagnostic defect introduction and typed detection.",
        "at_most",
        300.0,
    ),
    DiagnosticSLOTarget(
        "stale_evidence_rate",
        "Share of diagnostic evidence older than the allowed freshness window.",
        "at_most",
        0.0,
    ),
    DiagnosticSLOTarget(
        "false_pass_rate_from_negative_controls",
        "Share of negative controls that incorrectly passed.",
        "at_most",
        0.0,
    ),
    DiagnosticSLOTarget(
        "false_block_rate_from_positive_controls",
        "Share of positive controls that incorrectly blocked.",
        "at_most",
        0.0,
    ),
    DiagnosticSLOTarget(
        "redaction_coverage",
        "Share of diagnostic/public views covered by redaction policy.",
        "at_least",
        1.0,
    ),
    DiagnosticSLOTarget(
        "operator_time_to_root_cause",
        "Seconds from blocker surfacing to a next diagnostic command and owner.",
        "at_most",
        900.0,
    ),
)


def default_diagnostic_slo_targets() -> tuple[DiagnosticSLOTarget, ...]:
    """Return the Phase 4.4 diagnostic SLO target set."""

    return _TARGETS


def pass_observations_for_all_diagnostic_slos(
    *,
    observed_at: datetime | None = None,
    evidence_ref: str = DEFAULT_EVIDENCE_REF,
) -> dict[str, dict[str, Any]]:
    """Build explicit pass observations for tests and deterministic fixtures."""

    at = _utc(observed_at)
    return {
        target.metric_id: {
            "value": target.passing_value(),
            "observed_at": at.isoformat(),
            "evidence_ref": evidence_ref,
        }
        for target in _TARGETS
    }


def build_diagnostic_slo_report(
    *,
    observations: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
    run_id: str | None = None,
    canary_kind: str | None = None,
    owner: str = DEFAULT_OWNER,
    observed_self_deception_failures: Sequence[str] = (),
    fitness_registry_payload: Mapping[str, Any] | None = None,
    fitness_registry_path: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate diagnostic SLO evidence and closeout error-budget policy."""

    generated_at = _utc(now)
    indexed_observations = _observation_index(observations)
    metrics = [
        _metric_result(target, indexed_observations.get(target.metric_id), now=generated_at)
        for target in _TARGETS
    ]
    blockers = [_blocker_for_metric(metric) for metric in metrics if metric["status"] != "pass"]
    blockers = [blocker for blocker in blockers if blocker is not None]

    fitness_payload = fitness_registry_payload
    if fitness_payload is None and observed_self_deception_failures:
        fitness_payload = _load_fitness_registry(fitness_registry_path)
    fitness_summary = _fitness_registry_summary(
        observed_self_deception_failures=observed_self_deception_failures,
        registry_payload=fitness_payload,
    )
    for failure_code in fitness_summary["missing_active_controls"]:
        blockers.append(
            {
                "code": "diagnostic_fitness_control_missing",
                "metric_id": "diagnostic_fitness_registry",
                "message": (
                    "Observed self-deception failure lacks an active positive, "
                    f"negative, mutation, or metamorphic control: {failure_code}."
                ),
                "evidence_ref": _fitness_registry_ref(fitness_registry_path),
                "next_action": (
                    "Add or unretire a diagnostic fitness function, or retire the "
                    "failure mode through an ADR."
                ),
            }
        )

    error_budget_policy = _error_budget_policy(blockers)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "run_id": _text_or_none(run_id),
        "canary_kind": _text_or_none(canary_kind),
        "owner": _required_text(owner, DEFAULT_OWNER),
        "status": "fail" if blockers else "pass",
        "readiness_decision": error_budget_policy["decision"],
        "metrics": metrics,
        "blockers": blockers,
        "error_budget_policy": error_budget_policy,
        "fitness_registry": fitness_summary,
        "next_diagnostic_command": DEFAULT_NEXT_DIAGNOSTIC_COMMAND,
    }


def build_diagnostic_slo_report_from_quality_context(
    *,
    quality_evidence: Mapping[str, Any],
    required_report_keys: Sequence[str],
    required_runtime_ref_keys: Sequence[str],
    runtime_refs: Mapping[str, Any],
    job_payload: Mapping[str, Any] | None = None,
    run_payload: Mapping[str, Any] | None = None,
    run_id: str | None = None,
    canary_kind: str | None = None,
    owner: str = DEFAULT_OWNER,
    evidence_bundle_path: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Derive SLO observations from scorecard inputs before bundle closeout."""

    observed_at = _utc(now)
    required_reports = tuple(dict.fromkeys(str(key) for key in required_report_keys))
    required_refs = tuple(dict.fromkeys(str(key) for key in required_runtime_ref_keys))
    refs_present = {
        ref_key for ref_key in required_refs if _text_or_none(runtime_refs.get(ref_key))
    }
    reports_present = {
        report_key
        for report_key in required_reports
        if isinstance(quality_evidence.get(report_key), Mapping)
    }
    diagnostic_events = _diagnostic_events(job_payload=job_payload, run_payload=run_payload)
    covered_trace_refs = _diagnostic_event_refs(diagnostic_events)
    fallback_used = _truthy_nested(
        {"job": job_payload or {}, "run": run_payload or {}, "evidence": quality_evidence},
        "fallback_used",
    )
    degradation_ref = _first_nested_text(
        {"job": job_payload or {}, "run": run_payload or {}, "evidence": quality_evidence},
        ("degradation_ledger_ref", "fallback_degradation_ref"),
    )
    schema_compatible_reports = {
        report_key
        for report_key in reports_present
        if _schema_compatible_report(quality_evidence.get(report_key))
    }
    semantic_required = _semantic_binding_required(quality_evidence)

    observations: dict[str, dict[str, Any]] = {
        "complete_authority_graph_rate": _observation(
            _ratio(len(refs_present), len(required_refs)),
            observed_at=observed_at,
            evidence_ref="runtime_quality_refs",
        ),
        "evidence_completeness": _observation(
            _ratio(len(reports_present), len(required_reports)),
            observed_at=observed_at,
            evidence_ref="quality_evidence",
        ),
        "required_runtime_ref_verification_rate": _observation(
            _ratio(len(refs_present), len(required_refs)),
            observed_at=observed_at,
            evidence_ref="runtime_quality_refs",
        ),
        "trace_continuity": _observation(
            _ratio(
                len({ref for ref in refs_present if ref in covered_trace_refs}),
                len(required_refs),
            ),
            observed_at=observed_at,
            evidence_ref="diagnostic_events",
        ),
        "provenance_coverage": _observation(
            1.0 if evidence_bundle_path else 0.0,
            observed_at=observed_at,
            evidence_ref="quality_evidence/evidence_provenance_manifest.json",
        ),
        "fallback_ledger_coverage": _observation(
            1.0 if not fallback_used or degradation_ref else 0.0,
            observed_at=observed_at,
            evidence_ref=degradation_ref or "degradation_ledger_ref",
        ),
        "schema_compatibility_coverage": _observation(
            _ratio(len(schema_compatible_reports), len(reports_present)),
            observed_at=observed_at,
            evidence_ref="schema_compatibility",
        ),
        "semantic_binding_coverage": _observation(
            1.0
            if not semantic_required
            or isinstance(quality_evidence.get("semantic_binding_ledger"), Mapping)
            else 0.0,
            observed_at=observed_at,
            evidence_ref="quality_evidence/semantic_binding_ledger.json",
        ),
    }
    observations.update(
        _derived_optional_observations(
            quality_evidence=quality_evidence,
            diagnostic_events=diagnostic_events,
            reports_present=reports_present,
            observed_at=observed_at,
        )
    )
    explicit_observations = quality_evidence.get("diagnostic_slo_observations")
    if isinstance(explicit_observations, Mapping):
        observations.update(
            {
                str(metric_id): dict(observation)
                for metric_id, observation in explicit_observations.items()
                if isinstance(observation, Mapping)
            }
        )
    return build_diagnostic_slo_report(
        observations=observations,
        run_id=run_id,
        canary_kind=canary_kind,
        owner=owner,
        now=observed_at,
    )


def diagnostic_slo_gates(
    report: Mapping[str, Any] | None,
    *,
    canary_kind: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return scorecard/readiness gates for diagnostic SLO evidence."""

    if canary_kind.casefold() not in SERIOUS_CANARY_KINDS:
        return []
    if not isinstance(report, Mapping):
        return [
            _gate(
                code="diagnostic_slo_evidence_missing",
                message="Diagnostic SLO evidence is missing for serious closeout.",
                evidence_ref=DEFAULT_EVIDENCE_REF,
                next_action="Persist diagnostic SLO report evidence before readiness closeout.",
            )
        ]

    blockers = [blocker for blocker in report.get("blockers", []) if isinstance(blocker, Mapping)]
    stale_blockers = _freshness_blockers(report, now=_utc(now))
    return [
        _gate(
            code=_required_text(blocker.get("code"), "diagnostic_slo_failed"),
            message=_required_text(blocker.get("message"), "Diagnostic SLO blocks closeout."),
            evidence_ref=_text_or_none(blocker.get("evidence_ref")) or DEFAULT_EVIDENCE_REF,
            next_action=_text_or_none(blocker.get("next_action"))
            or DEFAULT_NEXT_DIAGNOSTIC_COMMAND,
        )
        for blocker in [*blockers, *stale_blockers]
    ]


def _metric_result(
    target: DiagnosticSLOTarget,
    raw_observation: object,
    *,
    now: datetime,
) -> dict[str, Any]:
    observation = _normalize_observation(raw_observation)
    if observation is None:
        return _missing_metric(target, "Diagnostic SLO observation is missing.")
    value = _float_or_none(observation.get("value"))
    evidence_ref = _text_or_none(observation.get("evidence_ref"))
    observed_at = _datetime_or_none(observation.get("observed_at"))
    if value is None:
        return _missing_metric(target, "Diagnostic SLO observation value is missing.")
    if evidence_ref is None:
        return _missing_metric(target, "Diagnostic SLO observation evidence ref is missing.")
    if observed_at is None:
        return _missing_metric(target, "Diagnostic SLO observation timestamp is missing.")
    if bool(observation.get("stale")) or (
        now - observed_at
    ).total_seconds() > target.stale_after_seconds:
        return _metric_payload(
            target,
            value=value,
            observed_at=observed_at,
            evidence_ref=evidence_ref,
            status="stale",
            message="Diagnostic SLO evidence is stale.",
        )
    if not _passes_target(target, value):
        return _metric_payload(
            target,
            value=value,
            observed_at=observed_at,
            evidence_ref=evidence_ref,
            status="over_error_budget",
            message="Diagnostic SLO burned its error budget.",
        )
    return _metric_payload(
        target,
        value=value,
        observed_at=observed_at,
        evidence_ref=evidence_ref,
        status="pass",
        message="Diagnostic SLO is within budget.",
    )


def _metric_payload(
    target: DiagnosticSLOTarget,
    *,
    value: float | None,
    observed_at: datetime | None,
    evidence_ref: str | None,
    status: str,
    message: str,
) -> dict[str, Any]:
    error_budget_burn = _error_budget_burn(target, value)
    return {
        "metric_id": target.metric_id,
        "description": target.description,
        "objective": {
            "comparator": target.comparator,
            "threshold": target.threshold,
            "stale_after_seconds": target.stale_after_seconds,
        },
        "value": value,
        "status": status,
        "observed_at": observed_at.isoformat() if observed_at is not None else None,
        "evidence_ref": evidence_ref,
        "error_budget_burn": error_budget_burn,
        "remaining_error_budget": max(0.0, 1.0 - error_budget_burn),
        "message": message,
    }


def _missing_metric(target: DiagnosticSLOTarget, message: str) -> dict[str, Any]:
    return _metric_payload(
        target,
        value=None,
        observed_at=None,
        evidence_ref=None,
        status="missing",
        message=message,
    )


def _blocker_for_metric(metric: Mapping[str, Any]) -> dict[str, Any] | None:
    status = str(metric.get("status") or "")
    if status == "missing":
        code = "diagnostic_slo_evidence_missing"
    elif status == "stale":
        code = "diagnostic_slo_evidence_stale"
    elif status == "over_error_budget":
        code = "diagnostic_slo_error_budget_burned"
    else:
        return None
    metric_id = _required_text(metric.get("metric_id"), "diagnostic_slo")
    return {
        "code": code,
        "metric_id": metric_id,
        "message": f"{metric_id}: {_required_text(metric.get('message'), code)}",
        "evidence_ref": _text_or_none(metric.get("evidence_ref")) or DEFAULT_EVIDENCE_REF,
        "next_action": DEFAULT_NEXT_DIAGNOSTIC_COMMAND,
    }


def _error_budget_policy(blockers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    codes = {str(blocker.get("code") or "") for blocker in blockers}
    if "diagnostic_slo_error_budget_burned" in codes:
        decision = "quarantine_closeout"
        effect = "production closeout is quarantined or downgraded before approval"
    elif codes:
        decision = "block_closeout"
        effect = "production closeout is blocked until diagnostic evidence is fresh"
    else:
        decision = "pass"
        effect = "production closeout may proceed from diagnostic SLO policy"
    return {
        "policy": "diagnostic_error_budget_policy.v1",
        "decision": decision,
        "production_closeout_effect": effect,
        "blocking_codes": sorted(code for code in codes if code),
    }


def _fitness_registry_summary(
    *,
    observed_self_deception_failures: Sequence[str],
    registry_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    observed = sorted(
        {_required_text(code, "") for code in observed_self_deception_failures if code}
    )
    rows = []
    if isinstance(registry_payload, Mapping) and isinstance(
        registry_payload.get("fitness_functions"), list
    ):
        rows = [row for row in registry_payload["fitness_functions"] if isinstance(row, Mapping)]
    active_controls = {
        _required_text(row.get("failure_code"), "")
        for row in rows
        if _required_text(row.get("fitness_type"), "") in ALLOWED_FITNESS_TYPES
        and _text_or_none(row.get("retired_by_adr")) is None
        and _text_or_none(row.get("failure_code")) is not None
    }
    missing_active = sorted(set(observed) - active_controls)
    return {
        "observed_self_deception_failures": observed,
        "active_control_failure_codes": sorted(active_controls),
        "missing_active_controls": missing_active,
    }


def _freshness_blockers(report: Mapping[str, Any], *, now: datetime) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for metric in report.get("metrics", []):
        if not isinstance(metric, Mapping) or metric.get("status") != "pass":
            continue
        objective = metric.get("objective")
        stale_after = 86_400
        if isinstance(objective, Mapping):
            stale_after = int(objective.get("stale_after_seconds") or stale_after)
        observed_at = _datetime_or_none(metric.get("observed_at"))
        if observed_at is None:
            continue
        if (now - observed_at).total_seconds() <= stale_after:
            continue
        blockers.append(
            {
                "code": "diagnostic_slo_evidence_stale",
                "message": (
                    f"{_required_text(metric.get('metric_id'), 'diagnostic_slo')}: "
                    "Diagnostic SLO evidence is stale."
                ),
                "evidence_ref": _text_or_none(metric.get("evidence_ref"))
                or DEFAULT_EVIDENCE_REF,
                "next_action": DEFAULT_NEXT_DIAGNOSTIC_COMMAND,
            }
        )
    return blockers


def _gate(
    *,
    code: str,
    message: str,
    evidence_ref: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "name": "diagnostic_slo_readiness",
        "stage": "ops",
        "code": code,
        "status": "fail",
        "layer": "diagnostic_slos",
        "phase": "diagnostic_slo",
        "message": message,
        "evidence_ref": evidence_ref,
        "next_action": next_action,
        "blocking": True,
    }


def _observation(value: float, *, observed_at: datetime, evidence_ref: str) -> dict[str, Any]:
    return {
        "value": value,
        "observed_at": observed_at.isoformat(),
        "evidence_ref": evidence_ref,
    }


def _derived_optional_observations(
    *,
    quality_evidence: Mapping[str, Any],
    diagnostic_events: Sequence[Mapping[str, Any]],
    reports_present: set[str],
    observed_at: datetime,
) -> dict[str, dict[str, Any]]:
    observations: dict[str, dict[str, Any]] = {}
    control_results = _control_result_rows(quality_evidence)
    if control_results:
        observations.update(_control_metric_observations(control_results, observed_at))
    detection_seconds = _detection_time_seconds(diagnostic_events)
    if detection_seconds is not None:
        observations["detection_time"] = _observation(
            detection_seconds,
            observed_at=observed_at,
            evidence_ref="diagnostic_events",
        )
    stale_rate = _stale_evidence_rate(
        quality_evidence=quality_evidence,
        reports_present=reports_present,
        now=observed_at,
    )
    if stale_rate is not None:
        observations["stale_evidence_rate"] = _observation(
            stale_rate,
            observed_at=observed_at,
            evidence_ref="quality_evidence",
        )
    redaction_rate = _redaction_coverage_rate(quality_evidence)
    if redaction_rate is not None:
        observations["redaction_coverage"] = _observation(
            redaction_rate,
            observed_at=observed_at,
            evidence_ref="quality_evidence/public_export_bundle.json",
        )
    ttrc_seconds = _operator_ttrc_seconds(quality_evidence, diagnostic_events)
    if ttrc_seconds is not None:
        observations["operator_time_to_root_cause"] = _observation(
            ttrc_seconds,
            observed_at=observed_at,
            evidence_ref="diagnostic_events",
        )
    return observations


def _control_result_rows(quality_evidence: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "diagnostic_control_results",
        "fitness_control_results",
        "negative_control_results",
        "positive_control_results",
    ):
        value = quality_evidence.get(key)
        if isinstance(value, Mapping):
            candidates = value.get("results")
            if isinstance(candidates, list):
                rows.extend(item for item in candidates if isinstance(item, Mapping))
            else:
                rows.append(value)
        elif isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    return rows


def _control_metric_observations(
    rows: Sequence[Mapping[str, Any]],
    observed_at: datetime,
) -> dict[str, dict[str, Any]]:
    negative = [row for row in rows if _control_kind(row) == "negative"]
    positive = [row for row in rows if _control_kind(row) == "positive"]
    known_defects = [row for row in rows if _truthy(row.get("defect_present"))]
    emitted_blockers = [row for row in rows if _truthy(row.get("blocker_emitted"))]
    observations: dict[str, dict[str, Any]] = {}
    if emitted_blockers:
        true_blockers = [
            row
            for row in emitted_blockers
            if _truthy(row.get("defect_present")) or _truthy(row.get("expected_blocker"))
        ]
        observations["blocker_precision"] = _observation(
            _ratio(len(true_blockers), len(emitted_blockers)),
            observed_at=observed_at,
            evidence_ref="quality_evidence/diagnostic_control_results.json",
        )
    if known_defects:
        caught = [row for row in known_defects if _truthy(row.get("blocker_emitted"))]
        observations["blocker_recall"] = _observation(
            _ratio(len(caught), len(known_defects)),
            observed_at=observed_at,
            evidence_ref="quality_evidence/diagnostic_control_results.json",
        )
    if negative:
        false_passes = [row for row in negative if _observed_status(row) == "pass"]
        observations["false_pass_rate_from_negative_controls"] = _observation(
            _ratio(len(false_passes), len(negative)),
            observed_at=observed_at,
            evidence_ref="quality_evidence/diagnostic_control_results.json",
        )
    if positive:
        false_blocks = [
            row
            for row in positive
            if _observed_status(row) in {"fail", "blocked", "block", "quarantined"}
            or _truthy(row.get("blocker_emitted"))
        ]
        observations["false_block_rate_from_positive_controls"] = _observation(
            _ratio(len(false_blocks), len(positive)),
            observed_at=observed_at,
            evidence_ref="quality_evidence/diagnostic_control_results.json",
        )
    return observations


def _control_kind(row: Mapping[str, Any]) -> str:
    raw = str(row.get("control_type") or row.get("fitness_type") or row.get("kind") or "")
    normalized = raw.casefold()
    if "negative" in normalized:
        return "negative"
    if "positive" in normalized:
        return "positive"
    return ""


def _observed_status(row: Mapping[str, Any]) -> str:
    return str(
        row.get("observed_status")
        or row.get("status")
        or row.get("result_status")
        or ""
    ).casefold()


def _detection_time_seconds(events: Sequence[Mapping[str, Any]]) -> float | None:
    durations: list[float] = []
    for event in events:
        introduced = _datetime_or_none(
            event.get("defect_introduced_at") or event.get("introduced_at")
        )
        detected = _datetime_or_none(event.get("detected_at") or event.get("observed_at"))
        if introduced is not None and detected is not None:
            durations.append(max(0.0, (detected - introduced).total_seconds()))
    if not durations:
        return None
    return max(durations)


def _stale_evidence_rate(
    *,
    quality_evidence: Mapping[str, Any],
    reports_present: set[str],
    now: datetime,
) -> float | None:
    dated = 0
    stale = 0
    for key in reports_present:
        report = quality_evidence.get(key)
        if not isinstance(report, Mapping):
            continue
        observed_at = _datetime_or_none(
            report.get("observed_at") or report.get("generated_at") or report.get("created_at")
        )
        if observed_at is None:
            continue
        dated += 1
        if (now - observed_at).total_seconds() > 86_400:
            stale += 1
    if dated == 0:
        return None
    return _ratio(stale, dated)


def _redaction_coverage_rate(quality_evidence: Mapping[str, Any]) -> float | None:
    bundle = quality_evidence.get("public_export_bundle") or quality_evidence.get(
        "public_export"
    )
    if not isinstance(bundle, Mapping):
        return None
    summary = bundle.get("redaction_summary")
    limits = bundle.get("official_use_limits")
    if not isinstance(summary, Mapping) or not isinstance(limits, Mapping):
        return 0.0
    return 1.0 if bundle.get("authority_role") == "projection_only" else 0.0


def _operator_ttrc_seconds(
    quality_evidence: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
) -> float | None:
    explicit = _float_or_none(quality_evidence.get("operator_time_to_root_cause_seconds"))
    if explicit is not None:
        return explicit
    durations: list[float] = []
    for event in events:
        surfaced = _datetime_or_none(event.get("blocker_surfaced_at") or event.get("observed_at"))
        rooted = _datetime_or_none(event.get("root_cause_identified_at"))
        if surfaced is not None and rooted is not None:
            durations.append(max(0.0, (rooted - surfaced).total_seconds()))
    if not durations:
        return None
    return max(durations)


def _observation_index(
    observations: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    if observations is None:
        return {}
    if isinstance(observations, Mapping):
        return {str(key): value for key, value in observations.items()}
    indexed: dict[str, Any] = {}
    for row in observations:
        metric_id = _text_or_none(row.get("metric_id"))
        if metric_id is not None:
            indexed[metric_id] = row
    return indexed


def _normalize_observation(raw_observation: object) -> dict[str, Any] | None:
    if isinstance(raw_observation, Mapping):
        return dict(raw_observation)
    value = _float_or_none(raw_observation)
    if value is None:
        return None
    return {"value": value}


def _passes_target(target: DiagnosticSLOTarget, value: float) -> bool:
    if target.comparator == "at_least":
        return value >= target.threshold
    return value <= target.threshold


def _error_budget_burn(target: DiagnosticSLOTarget, value: float | None) -> float:
    if value is None:
        return 1.0
    if _passes_target(target, value):
        return 0.0
    if target.comparator == "at_least":
        if target.threshold == 0:
            return 1.0
        return min(1.0, (target.threshold - value) / abs(target.threshold))
    if target.threshold == 0:
        return 1.0
    return min(1.0, (value - target.threshold) / abs(target.threshold))


def _diagnostic_events(
    *,
    job_payload: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    values = _nested_find_all(
        {"job": job_payload or {}, "run": run_payload or {}},
        "diagnostic_events",
    )
    events: list[Mapping[str, Any]] = []
    for value in values:
        candidates = value if isinstance(value, list) else [value]
        events.extend(item for item in candidates if isinstance(item, Mapping))
    return events


def _diagnostic_event_refs(events: Sequence[Mapping[str, Any]]) -> set[str]:
    refs: set[str] = set()
    for event in events:
        for key in ("artifact_ref", "runtime_cas_ref"):
            value = _text_or_none(event.get(key))
            if value is not None:
                refs.add(value)
        artifact_refs = event.get("artifact_refs")
        if isinstance(artifact_refs, list):
            refs.update(_required_text(value, "") for value in artifact_refs if value)
    return refs


def _schema_compatible_report(report: object) -> bool:
    if not isinstance(report, Mapping):
        return False
    compatibility = report.get("schema_compatibility")
    if isinstance(compatibility, Mapping):
        decision = _required_text(compatibility.get("decision"), "").casefold()
        if decision in {"compatible", "reader_compatible", "legacy_supported"}:
            return True
    return _text_or_none(report.get("schema_version")) is not None or isinstance(
        report.get("schema"),
        Mapping,
    )


def _semantic_binding_required(quality_evidence: Mapping[str, Any]) -> bool:
    fabric = quality_evidence.get("fabric_retrieval_trace")
    grounding = quality_evidence.get("policy_grounding_matrix")
    if not isinstance(fabric, Mapping) or not isinstance(grounding, Mapping):
        return False
    candidates = fabric.get("candidate_sources")
    claims = grounding.get("claims")
    production_data_available = isinstance(candidates, list) and any(
        isinstance(row, Mapping)
        and (
            row.get("available_columns")
            or str(row.get("source_kind") or "").casefold() == "production_data"
        )
        for row in candidates
    )
    data_claims = isinstance(claims, list) and any(
        isinstance(row, Mapping) and bool(row.get("data_refs")) for row in claims
    )
    return production_data_available and data_claims


def _nested_find_all(payload: object, key: str) -> list[object]:
    found: list[object] = []
    if isinstance(payload, Mapping):
        if key in payload:
            found.append(payload[key])
        for value in payload.values():
            found.extend(_nested_find_all(value, key))
    elif isinstance(payload, list):
        for value in payload:
            found.extend(_nested_find_all(value, key))
    return found


def _truthy_nested(payload: object, key: str) -> bool:
    for value in _nested_find_all(payload, key):
        if isinstance(value, bool):
            return value
        if str(value).strip().casefold() in {"1", "true", "yes", "used"}:
            return True
    return False


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "pass", "present", "used"}


def _first_nested_text(payload: object, keys: Sequence[str]) -> str | None:
    for key in keys:
        for value in _nested_find_all(payload, key):
            text = _text_or_none(value)
            if text is not None:
                return text
    return None


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return round(numerator / denominator, 6)


def _load_fitness_registry(path: str | Path | None) -> Mapping[str, Any]:
    registry_path = Path(path) if path is not None else DEFAULT_FITNESS_REGISTRY_PATH
    try:
        with registry_path.open("rb") as stream:
            return tomllib.load(stream)
    except OSError:
        return {"fitness_functions": []}


def _fitness_registry_ref(path: str | Path | None) -> str:
    registry_path = Path(path) if path is not None else DEFAULT_FITNESS_REGISTRY_PATH
    try:
        return registry_path.resolve().relative_to(Path(__file__).resolve().parents[4]).as_posix()
    except ValueError:
        return registry_path.as_posix()


def _datetime_or_none(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _utc(value)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return _utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC, microsecond=0)
    return value.astimezone(UTC).replace(microsecond=0)


def _float_or_none(value: object) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _text_or_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _required_text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


__all__ = [
    "ALLOWED_FITNESS_TYPES",
    "DIAGNOSTIC_SLO_METRIC_IDS",
    "DiagnosticSLOTarget",
    "build_diagnostic_slo_report",
    "build_diagnostic_slo_report_from_quality_context",
    "default_diagnostic_slo_targets",
    "diagnostic_slo_gates",
    "pass_observations_for_all_diagnostic_slos",
]
