"""Soft-gate lifecycle and self-FMEA telemetry for Policy Design Case runs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from polisyos.runtime.quality.prompt_tool_ledger import (
    PromptToolParserAuthorityLedger,
    prompt_tool_repair_machinery_failures,
)

if TYPE_CHECKING:
    from polisyos.core.contracts import BoundedLivenessResolution

SOFT_GATE_TELEMETRY_SCHEMA_VERSION = "policyos.runtime.soft_gate_telemetry.v1"
DEFAULT_SOFT_GATE_TTL_SECONDS = 72 * 60 * 60
DEFAULT_SOFT_GATE_ESCALATION_SECONDS = 24 * 60 * 60

DEFAULT_COMPLEXITY_BUDGET: dict[str, float] = {
    "max_gate_count": 200.0,
    "max_warning_count": 10.0,
    "max_tool_count": 20.0,
    "max_repair_decision_count": 10.0,
    "max_review_count": 50.0,
    "max_total_actual_cost_usd": 1_000.0,
    "max_elapsed_seconds": 24 * 60 * 60.0,
    "max_human_review_hours": 24.0,
}

_OWNER_BY_LAYER = {
    "llm_gateway": "team-runtime-ops",
    "llm_provider_quality": "team-runtime-ops",
    "nl_pipeline": "team-runtime-ops",
    "prompt_tool_parser_authority": "team-runtime-ops",
    "quality_scorecard": "team-quality-closeout",
    "runtime_diagnostics": "team-observability",
    "semantic_binding": "team-policy-semantics",
    "source_truth": "team-architecture-governance",
    "human_review_calibration": "team-quality-closeout",
    "policy_design_run_cost_proportionality": "team-runtime-quality",
}


def warning_lifecycle_summaries(
    gates: Sequence[Mapping[str, Any]],
    *,
    generated_at: datetime | None = None,
    ttl_seconds: int = DEFAULT_SOFT_GATE_TTL_SECONDS,
    escalation_after_seconds: int = DEFAULT_SOFT_GATE_ESCALATION_SECONDS,
) -> list[dict[str, Any]]:
    """Project warning gates into owner- and TTL-bound lifecycle records.

    Args:
        gates: Scorecard gate rows. Only rows with ``status == "warn"`` are
            projected.
        generated_at: Runtime timestamp used for age and expiry evaluation.
        ttl_seconds: Maximum warning lifetime before it expires.
        escalation_after_seconds: Age at which owner escalation is due.

    Returns:
        Warning summaries suitable for scorecard, audit, and API surfaces.
    """

    now = _utc(generated_at)
    ttl = max(1, int(ttl_seconds))
    escalate_after = max(1, int(escalation_after_seconds))
    return [
        _warning_lifecycle_summary(
            gate,
            generated_at=now,
            ttl_seconds=ttl,
            escalation_after_seconds=escalate_after,
        )
        for gate in gates
        if str(gate.get("status") or "").casefold() == "warn"
    ]


def build_soft_gate_telemetry_report(
    *,
    run_id: str | None,
    job_id: str | None,
    gates: Sequence[Mapping[str, Any]],
    prompt_tool_ledger: PromptToolParserAuthorityLedger | Mapping[str, Any] | None = None,
    human_review_calibration: Mapping[str, Any] | None = None,
    run_cost_ledgers: Sequence[Mapping[str, Any]] = (),
    bounded_liveness_resolutions: Sequence[BoundedLivenessResolution | Mapping[str, Any]] = (),
    complexity_budget: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build W2.D soft-gate, liveness, review, repair, and complexity telemetry.

    The report is derived from runtime telemetry that already exists: scorecard
    gates, prompt/tool repair decisions, bounded-liveness resolutions,
    human-review telemetry, and run-cost ledgers. It intentionally does not
    introduce human ceremony forms as a source of complexity truth.
    """

    now = _utc(generated_at)
    warnings = warning_lifecycle_summaries(gates, generated_at=now)
    ledger = _coerce_prompt_tool_ledger(prompt_tool_ledger)
    repair_fmea = _repair_decision_fmea(ledger)
    review_telemetry = _advisory_review_telemetry(human_review_calibration)
    liveness_hooks = _bounded_liveness_hooks(bounded_liveness_resolutions)
    complexity = _complexity_budget_telemetry(
        gates=gates,
        warning_lifecycle=warnings,
        prompt_tool_ledger=ledger,
        human_review_calibration=human_review_calibration,
        run_cost_ledgers=run_cost_ledgers,
        complexity_budget=complexity_budget,
    )
    expired_warning_count = sum(
        1 for warning in warnings if warning.get("lifecycle_status") == "expired"
    )
    return {
        "schema_version": SOFT_GATE_TELEMETRY_SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "run_id": _clean_text(run_id),
        "job_id": _clean_text(job_id),
        "status": (
            "warn"
            if expired_warning_count or complexity["status"] == "advisory_over_budget"
            else "pass"
        ),
        "pattern_refs": ["P04", "P09", "P13"],
        "warning_lifecycle": warnings,
        "bounded_liveness_hooks": liveness_hooks,
        "repair_decision_fmea": repair_fmea,
        "advisory_review_telemetry": review_telemetry,
        "complexity_budget_telemetry": complexity,
        "summary": {
            "warning_count": len(warnings),
            "expired_warning_count": expired_warning_count,
            "bounded_liveness_hook_count": len(liveness_hooks),
            "repair_decision_count": repair_fmea["summary"]["repair_decision_count"],
            "repair_fmea_annotation_count": repair_fmea["summary"][
                "repair_fmea_annotation_count"
            ],
            "complexity_budget_status": complexity["status"],
        },
        "authority_boundary": {
            "authoritative_for": [
                "soft_gate_lifecycle_tracking",
                "bounded_liveness_runtime_observability",
                "repair_decision_self_fmea",
                "complexity_budget_observability",
            ],
            "may_not_use_for": [
                "claim_support",
                "evidence_admissibility",
                "current_run_closeout_without_scorecard_gate",
            ],
        },
        "surface": "quality_scorecard.soft_gate_telemetry",
    }


def _warning_lifecycle_summary(
    gate: Mapping[str, Any],
    *,
    generated_at: datetime,
    ttl_seconds: int,
    escalation_after_seconds: int,
) -> dict[str, Any]:
    layer = _clean_text(gate.get("layer")) or "quality_scorecard"
    first_observed = _datetime_from(
        gate.get("first_observed_at")
        or gate.get("observed_at")
        or gate.get("generated_at"),
        default=generated_at,
    )
    age_seconds = max(0, int((generated_at - first_observed).total_seconds()))
    lifecycle_status = "active"
    if age_seconds >= ttl_seconds:
        lifecycle_status = "expired"
    elif age_seconds >= escalation_after_seconds:
        lifecycle_status = "escalation_due"

    ttl_expires_at = first_observed + timedelta(seconds=ttl_seconds)
    escalates_at = first_observed + timedelta(seconds=escalation_after_seconds)
    return {
        "gate": str(gate.get("name") or "quality_warning"),
        "code": _clean_text(gate.get("code")) or str(gate.get("name") or "quality_warning"),
        "layer": layer,
        "phase": _clean_text(gate.get("phase")),
        "message": _clean_text(gate.get("message")) or "Quality warning.",
        "evidence_ref": _clean_text(gate.get("evidence_ref")),
        "next_action": _clean_text(gate.get("next_action")),
        "owner": _warning_owner(gate, layer=layer),
        "first_observed_at": first_observed.isoformat(),
        "age_seconds": age_seconds,
        "ttl_seconds": ttl_seconds,
        "escalation_after_seconds": escalation_after_seconds,
        "escalates_at": escalates_at.isoformat(),
        "ttl_expires_at": ttl_expires_at.isoformat(),
        "lifecycle_status": lifecycle_status,
        "accepted_deficit_policy": "owner_review_required",
        "closeout_effect": _closeout_effect_for_lifecycle(lifecycle_status),
        "publication_effect": "publication_requires_resolution_or_accepted_deficit",
    }


def _warning_owner(gate: Mapping[str, Any], *, layer: str) -> str:
    owner = _clean_text(gate.get("owner") or gate.get("responsible_owner"))
    if owner is not None:
        return owner
    return _OWNER_BY_LAYER.get(layer, "team-runtime-quality")


def _closeout_effect_for_lifecycle(lifecycle_status: str) -> str:
    if lifecycle_status == "expired":
        return "expired_warning_blocks_serious_closeout"
    if lifecycle_status == "escalation_due":
        return "owner_escalation_required"
    return "advisory_until_ttl_or_serious_closeout"


def _bounded_liveness_hooks(
    resolutions: Sequence[BoundedLivenessResolution | Mapping[str, Any]],
) -> list[dict[str, Any]]:
    hooks: list[dict[str, Any]] = []
    for resolution in resolutions:
        payload = _model_or_mapping(resolution)
        if not payload:
            continue
        hook = {
            "producer_key": _clean_text(payload.get("producer_key")),
            "deadline_s": _number(payload.get("deadline_s")),
            "retry_ceiling": _int_or_none(payload.get("retry_ceiling")),
            "escalation": _clean_text(payload.get("escalation")) or "runtime_escalation",
            "config_id": _clean_text(payload.get("config_id")),
            "config_version": _clean_text(payload.get("config_version")),
            "owner": _clean_text(payload.get("owner")) or "team-runtime-quality",
            "feature_flag": _clean_text(payload.get("feature_flag")),
            "status": "armed",
            "notes": _text_list(payload.get("notes")),
        }
        if hook["producer_key"] and hook["deadline_s"] is not None:
            hooks.append(hook)
    return hooks


def _coerce_prompt_tool_ledger(
    value: PromptToolParserAuthorityLedger | Mapping[str, Any] | None,
) -> PromptToolParserAuthorityLedger | None:
    if value is None:
        return None
    if isinstance(value, PromptToolParserAuthorityLedger):
        return value
    if isinstance(value, Mapping):
        try:
            return PromptToolParserAuthorityLedger.model_validate(value)
        except Exception:
            return None
    return None


def _repair_decision_fmea(
    ledger: PromptToolParserAuthorityLedger | None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if ledger is None:
        return {
            "summary": {
                "repair_decision_count": 0,
                "repair_fmea_annotation_count": 0,
                "repair_fmea_unannotated_count": 0,
                "repair_machinery_failure_count": 0,
                "max_risk_priority_number": None,
            },
            "decisions": rows,
            "machinery_failures": [],
        }

    machinery_failures = prompt_tool_repair_machinery_failures(ledger)
    for step in ledger.steps:
        for decision in step.repair_decisions:
            annotation = decision.fmea_annotation
            row = {
                "step_id": step.step_id,
                "decision": decision.decision,
                "status": decision.status,
                "repair_ref": decision.repair_ref,
                "annotation_status": "present" if annotation is not None else "missing",
            }
            if annotation is not None:
                row["fmea_annotation"] = annotation.model_dump(
                    mode="json",
                    exclude_none=True,
                )
            rows.append(row)

    annotated = [row for row in rows if row["annotation_status"] == "present"]
    unannotated_applied = [
        row
        for row in rows
        if row["annotation_status"] == "missing"
    ]
    rpn_values = [
        int(row["fmea_annotation"]["risk_priority_number"])
        for row in annotated
        if isinstance(row.get("fmea_annotation"), Mapping)
        and row["fmea_annotation"].get("risk_priority_number") is not None
    ]
    return {
        "summary": {
            "repair_decision_count": len(rows),
            "repair_fmea_annotation_count": len(annotated),
            "repair_fmea_unannotated_count": len(unannotated_applied),
            "repair_machinery_failure_count": len(machinery_failures),
            "max_risk_priority_number": max(rpn_values) if rpn_values else None,
        },
        "decisions": rows,
        "machinery_failures": machinery_failures,
    }


def _advisory_review_telemetry(
    human_review_calibration: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(human_review_calibration, Mapping):
        return {
            "schema_version": "policyos.human_review_effectiveness_telemetry.v1",
            "posture": "not_observed",
            "blocking_permitted": False,
            "authority_boundary": {
                "authoritative_for": ["review_effectiveness_measurement_absence"],
                "may_not_use_for": [
                    "current_run_closeout_block",
                    "publication_block",
                    "claim_support_downgrade",
                ],
            },
        }
    telemetry = human_review_calibration.get("review_effectiveness_telemetry")
    if isinstance(telemetry, Mapping):
        payload = dict(telemetry)
    else:
        payload = {
            "schema_version": "policyos.human_review_effectiveness_telemetry.v1",
            "posture": "advisory",
            "blocking_permitted": False,
            "measured_signals": {
                "review_count": _review_count(human_review_calibration),
            },
        }
    payload.setdefault("posture", "advisory")
    payload.setdefault("blocking_permitted", False)
    payload.setdefault(
        "authority_boundary",
        {
            "authoritative_for": [
                "review_effectiveness_measurement",
                "future_policy_calibration",
            ],
            "may_not_use_for": [
                "current_run_closeout_block",
                "publication_block",
                "claim_support_downgrade",
            ],
        },
    )
    return payload


def _complexity_budget_telemetry(
    *,
    gates: Sequence[Mapping[str, Any]],
    warning_lifecycle: Sequence[Mapping[str, Any]],
    prompt_tool_ledger: PromptToolParserAuthorityLedger | None,
    human_review_calibration: Mapping[str, Any] | None,
    run_cost_ledgers: Sequence[Mapping[str, Any]],
    complexity_budget: Mapping[str, Any] | None,
) -> dict[str, Any]:
    budget = {**DEFAULT_COMPLEXITY_BUDGET, **_numeric_budget(complexity_budget)}
    measurements = _complexity_measurements(
        gates=gates,
        warning_lifecycle=warning_lifecycle,
        prompt_tool_ledger=prompt_tool_ledger,
        human_review_calibration=human_review_calibration,
        run_cost_ledgers=run_cost_ledgers,
    )
    decisions = _prune_or_merge_decisions(measurements, budget)
    return {
        "input_source": "runtime_telemetry",
        "status": "advisory_over_budget" if decisions else "advisory_within_budget",
        "authority_effect": "advisory_complexity_budget",
        "measurements": measurements,
        "budget": budget,
        "prune_or_merge_decisions": decisions,
        "human_form_count": 0,
    }


def _complexity_measurements(
    *,
    gates: Sequence[Mapping[str, Any]],
    warning_lifecycle: Sequence[Mapping[str, Any]],
    prompt_tool_ledger: PromptToolParserAuthorityLedger | None,
    human_review_calibration: Mapping[str, Any] | None,
    run_cost_ledgers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    repair_decision_count = 0
    repair_annotation_count = 0
    tool_count = 0
    if prompt_tool_ledger is not None:
        repair_decision_count = sum(
            len(step.repair_decisions) for step in prompt_tool_ledger.steps
        )
        repair_annotation_count = sum(
            1
            for step in prompt_tool_ledger.steps
            for decision in step.repair_decisions
            if decision.fmea_annotation is not None
        )
        tool_count = len(
            {
                tool
                for step in prompt_tool_ledger.steps
                for tool in step.tool_allowlist
            }
        )

    cost = _sum_numbers(run_cost_ledgers, "total_actual_cost_usd")
    elapsed = _sum_numbers(run_cost_ledgers, "elapsed_seconds")
    review_hours = _sum_numbers(run_cost_ledgers, "human_review_hours")
    measurements = {
        "gate_count": len(gates),
        "warning_count": len(warning_lifecycle),
        "repair_decision_count": repair_decision_count,
        "repair_fmea_annotation_count": repair_annotation_count,
        "tool_count": tool_count,
        "review_count": _review_count(human_review_calibration),
        "total_actual_cost_usd": cost,
        "elapsed_seconds": elapsed,
        "human_review_hours": review_hours,
    }
    return measurements


def _prune_or_merge_decisions(
    measurements: Mapping[str, Any],
    budget: Mapping[str, float],
) -> list[dict[str, Any]]:
    decision_specs = (
        (
            "warning_count",
            "max_warning_count",
            "soft_gate_warning_prune_or_merge",
            "team-quality-closeout",
            "Merge duplicate warnings or resolve owner-accepted deficits before adding gates.",
        ),
        (
            "tool_count",
            "max_tool_count",
            "prompt_tool_allowlist_prune_or_merge",
            "team-runtime-ops",
            "Consolidate tool calls or remove unused allowlist entries.",
        ),
        (
            "gate_count",
            "max_gate_count",
            "quality_gate_prune_or_merge",
            "team-quality-closeout",
            "Consolidate overlapping quality gates before adding new controls.",
        ),
        (
            "repair_decision_count",
            "max_repair_decision_count",
            "repair_path_prune_or_merge",
            "team-runtime-ops",
            "Consolidate repeated repair paths and keep FMEA annotations current.",
        ),
        (
            "review_count",
            "max_review_count",
            "review_burden_prune_or_merge",
            "team-quality-closeout",
            "Reduce review burden through sampled or role-specific review policy.",
        ),
        (
            "total_actual_cost_usd",
            "max_total_actual_cost_usd",
            "cost_surface_prune_or_merge",
            "team-runtime-quality",
            "Review marginal-cost evidence before expanding runtime controls.",
        ),
        (
            "elapsed_seconds",
            "max_elapsed_seconds",
            "liveness_surface_prune_or_merge",
            "team-runtime-quality",
            "Use bounded-liveness hooks to reduce wall-clock control cost.",
        ),
        (
            "human_review_hours",
            "max_human_review_hours",
            "human_review_burden_prune_or_merge",
            "team-quality-closeout",
            "Review owner load and merge low-value manual review steps.",
        ),
    )
    decisions: list[dict[str, Any]] = []
    for measurement_key, budget_key, decision, owner, next_action in decision_specs:
        value = _number(measurements.get(measurement_key))
        limit = _number(budget.get(budget_key))
        if value is None or limit is None or value <= limit:
            continue
        decisions.append(
            {
                "decision": decision,
                "owner": owner,
                "measurement": measurement_key,
                "value": value,
                "budget": limit,
                "next_action": next_action,
            }
        )
    return decisions


def _review_count(report: Mapping[str, Any] | None) -> int:
    if not isinstance(report, Mapping):
        return 0
    summary = report.get("summary")
    if isinstance(summary, Mapping):
        count = _int_or_none(summary.get("review_count"))
        if count is not None:
            return count
    telemetry = report.get("review_effectiveness_telemetry")
    if isinstance(telemetry, Mapping):
        measured = telemetry.get("measured_signals")
        if isinstance(measured, Mapping):
            count = _int_or_none(measured.get("review_count"))
            if count is not None:
                return count
    return 0


def _numeric_budget(value: Mapping[str, Any] | None) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    budget: dict[str, float] = {}
    for key, raw_value in value.items():
        number = _number(raw_value)
        if number is not None:
            budget[str(key)] = number
    return budget


def _sum_numbers(rows: Iterable[Mapping[str, Any]], key: str) -> float:
    total = 0.0
    for row in rows:
        number = _number(row.get(key))
        if number is not None:
            total += number
    return round(total, 6)


def _model_or_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json", exclude_none=True)
        if isinstance(payload, Mapping):
            return dict(payload)
    return {}


def _datetime_from(value: object, *, default: datetime) -> datetime:
    if isinstance(value, datetime):
        return _utc(value)
    text = _clean_text(value)
    if text is None:
        return default
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return default
    return _utc(parsed)


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or any(char in text for char in "\r\n\t"):
        return None
    return text


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _text_list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    rows: list[str] = []
    for item in value:
        text = _clean_text(item)
        if text is not None:
            rows.append(text)
    return rows


__all__ = [
    "DEFAULT_SOFT_GATE_ESCALATION_SECONDS",
    "DEFAULT_SOFT_GATE_TTL_SECONDS",
    "SOFT_GATE_TELEMETRY_SCHEMA_VERSION",
    "build_soft_gate_telemetry_report",
    "warning_lifecycle_summaries",
]
