"""Net-MAV complexity governance for Policy Design Case controls.

This module turns W2.D self-FMEA and soft-gate telemetry into W10.E governance:
new blocking-frontier controls need expected marginal assurance value (Net-MAV)
and telemetry refs, while already-active controls are periodically reviewed for
retirement or merge when they stop affecting decisions.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

COMPLEXITY_GOVERNANCE_SCHEMA_VERSION = "policyos.runtime.quality.complexity_governance.v1"
COMPLEXITY_GOVERNANCE_CONTRACT_ID = "policyos.runtime.quality.complexity_governance"
COMPLEXITY_GOVERNANCE_CONTROL_ID = "complexity_governance"
COMPLEXITY_GOVERNANCE_REPORT_KEY = "complexity_governance"
COMPLEXITY_GOVERNANCE_FILENAME = "complexity_governance.json"
NET_MAV_FORMULA = (
    "decision_gain + falsification_value + authority_gain + auditability_gain "
    "- human_time_cost - latency_penalty - rerun_penalty - false_block_penalty"
)

_GAIN_COMPONENTS = (
    "decision_gain",
    "falsification_value",
    "authority_gain",
    "auditability_gain",
)
_PENALTY_COMPONENTS = (
    "human_time_cost",
    "latency_penalty",
    "rerun_penalty",
    "false_block_penalty",
)
_MAV_COMPONENTS = (*_GAIN_COMPONENTS, *_PENALTY_COMPONENTS)
_BLOCKING_FRONTIER_LABELS = frozenset(
    {
        "blocking",
        "blocking_frontier",
        "block",
        "closeout_block",
        "frontier_blocking",
    }
)
_ACTIVE_CONTROL_STATUSES = frozenset(
    {
        "active",
        "admitted",
        "blocking",
        "enabled",
        "implemented",
        "retained",
    }
)
_DEFAULT_MEASUREMENT_WINDOW_DAYS = 30


class ComplexityGovernanceError(ValueError):
    """Raised when a complexity governance input cannot be interpreted."""

    def __init__(self, code: str, message: str, *, field: str | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.field = field


def compute_net_mav(
    *,
    decision_gain: float,
    falsification_value: float,
    authority_gain: float,
    auditability_gain: float,
    human_time_cost: float,
    latency_penalty: float,
    rerun_penalty: float,
    false_block_penalty: float,
) -> float:
    """Compute expected net marginal assurance value for one control.

    Args:
        decision_gain: Expected chance the control changes a material decision.
        falsification_value: Expected value of catching false positives/claims.
        authority_gain: Expected authority-boundary improvement.
        auditability_gain: Expected audit/inspection improvement.
        human_time_cost: Reviewer/operator burden penalty.
        latency_penalty: Runtime latency penalty.
        rerun_penalty: Expected rerun/replay burden penalty.
        false_block_penalty: Expected penalty from false blocks.

    Returns:
        Net-MAV rounded to six decimal places.
    """

    values = {
        "decision_gain": decision_gain,
        "falsification_value": falsification_value,
        "authority_gain": authority_gain,
        "auditability_gain": auditability_gain,
        "human_time_cost": human_time_cost,
        "latency_penalty": latency_penalty,
        "rerun_penalty": rerun_penalty,
        "false_block_penalty": false_block_penalty,
    }
    normalized = {
        key: _required_finite_number(value, field=key) for key, value in values.items()
    }
    return _round_mav(
        sum(normalized[key] for key in _GAIN_COMPONENTS)
        - sum(normalized[key] for key in _PENALTY_COMPONENTS)
    )


def evaluate_blocking_frontier_control(
    control: Mapping[str, Any],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate whether a proposed control may enter the blocking frontier.

    A W10.E-admissible blocking control must declare expected Net-MAV and cite
    telemetry refs. Positive Net-MAV is required before the control can add
    blocking surface; non-positive value means the control remains advisory or
    must be redesigned.
    """

    now = _utc(generated_at)
    control_id = _control_id(control)
    owner = _clean_text(control.get("owner")) or "team-runtime-quality"
    expected_net_mav, components, mav_issue = _expected_net_mav(control)
    telemetry_refs = _telemetry_refs(control)

    issues: list[dict[str, Any]] = []
    if mav_issue is not None:
        issues.append(mav_issue)
    elif expected_net_mav is None:
        issues.append(
            _issue(
                "expected_net_mav_missing",
                "Blocking-frontier controls must declare expected Net-MAV.",
                field="expected_net_mav",
            )
        )
    elif expected_net_mav <= 0:
        issues.append(
            _issue(
                "expected_net_mav_non_positive",
                "Blocking-frontier controls must have positive expected Net-MAV.",
                field="expected_net_mav",
            )
        )
    if not telemetry_refs:
        issues.append(
            _issue(
                "telemetry_refs_missing",
                "Blocking-frontier controls must cite W2.D/runtime telemetry refs.",
                field="telemetry_refs",
            )
        )

    admitted = not issues
    decision: dict[str, Any] = {
        "control_id": control_id,
        "owner": owner,
        "frontier": "blocking",
        "status": "admitted" if admitted else "rejected",
        "can_enter_blocking_frontier": admitted,
        "expected_net_mav": expected_net_mav,
        "net_mav_formula": NET_MAV_FORMULA,
        "telemetry_refs": telemetry_refs,
        "issues": issues,
        "generated_at": now.isoformat(),
        "authority_boundary": _authority_boundary(),
    }
    if components is not None:
        decision["mav_components"] = components
    return decision


def review_controls_for_pruning(
    controls: Sequence[Mapping[str, Any]],
    *,
    generated_at: datetime | None = None,
    measurement_window_started_at: datetime | str | None = None,
    measurement_window_days: int = _DEFAULT_MEASUREMENT_WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """Review active controls for retirement or merge after a measurement window.

    Controls that have no decision effect after the window are returned as
    `retire_candidate` or `merge_candidate`. The function deliberately reviews
    all supplied controls so audit surfaces can see retained controls too.
    """

    now = _utc(generated_at)
    window_days = max(1, int(measurement_window_days))
    default_started_at = _datetime_from(measurement_window_started_at, default=now)
    rows: list[dict[str, Any]] = []
    for control in controls:
        control_id = _control_id(control)
        owner = _clean_text(control.get("owner")) or "team-runtime-quality"
        started_at = _datetime_from(
            control.get("first_measured_at")
            or control.get("measurement_window_started_at")
            or default_started_at,
            default=default_started_at,
        )
        window_elapsed = now - started_at >= timedelta(days=window_days)
        effect_count = _decision_effect_count(control)
        merge_candidates = _text_list(
            control.get("merge_candidate_with")
            or control.get("overlaps_with")
            or control.get("duplicate_of")
        )
        telemetry_refs = _telemetry_refs(control)

        if not window_elapsed:
            recommendation = "observe_until_window_complete"
            reason = "measurement_window_open"
        elif effect_count > 0:
            recommendation = "retain"
            reason = "affected_decisions_observed"
        elif merge_candidates:
            recommendation = "merge_candidate"
            reason = "no_decision_effect_after_measurement_window"
        else:
            recommendation = "retire_candidate"
            reason = "no_decision_effect_after_measurement_window"

        rows.append(
            {
                "control_id": control_id,
                "owner": owner,
                "status": _clean_text(control.get("status")) or "active",
                "recommendation": recommendation,
                "reason": reason,
                "measurement_window_started_at": started_at.isoformat(),
                "measurement_window_days": window_days,
                "window_elapsed": window_elapsed,
                "decision_effect_count": effect_count,
                "merge_candidate_with": merge_candidates,
                "telemetry_refs": telemetry_refs,
                "next_action": _next_action_for_recommendation(recommendation),
            }
        )
    return rows


def build_complexity_governance_report(
    *,
    run_id: str | None,
    soft_gate_telemetry: Mapping[str, Any] | None,
    controls: Sequence[Mapping[str, Any]],
    generated_at: datetime | None = None,
    measurement_window_started_at: datetime | str | None = None,
    measurement_window_days: int = _DEFAULT_MEASUREMENT_WINDOW_DAYS,
) -> dict[str, Any]:
    """Build the W10.E governance report over W2.D self-FMEA telemetry.

    Args:
        run_id: Runtime run identifier.
        soft_gate_telemetry: W2.D `build_soft_gate_telemetry_report` payload.
        controls: Proposed or active controls to gate and/or review.
        generated_at: Report timestamp.
        measurement_window_started_at: Start of periodic prune-review window.
        measurement_window_days: Minimum window before retirement candidates emit.

    Returns:
        A report suitable for quality-scorecard, audit, or operator surfaces.
    """

    now = _utc(generated_at)
    telemetry = dict(soft_gate_telemetry or {})
    issues = _telemetry_issues(telemetry)
    gating_controls = [control for control in controls if _wants_blocking_frontier(control)]
    gating_decisions = [
        evaluate_blocking_frontier_control(control, generated_at=now)
        for control in gating_controls
    ]
    active_controls = [
        control for control in controls if _is_active_for_prune_review(control)
    ]
    prune_review = review_controls_for_pruning(
        active_controls,
        generated_at=now,
        measurement_window_started_at=measurement_window_started_at,
        measurement_window_days=measurement_window_days,
    )
    self_application = _self_application_review(
        telemetry,
        generated_at=now,
        measurement_window_started_at=measurement_window_started_at,
        measurement_window_days=measurement_window_days,
    )
    rejected_count = sum(
        1 for decision in gating_decisions if not decision["can_enter_blocking_frontier"]
    )
    admitted_count = len(gating_decisions) - rejected_count
    prune_candidate_count = sum(
        1
        for row in prune_review
        if row["recommendation"] in {"merge_candidate", "retire_candidate"}
    )

    status = "pass"
    if rejected_count:
        status = "blocking_frontier_rejected"
    elif prune_candidate_count or self_application["recommendation"] == "retire_candidate":
        status = "prune_review_due"
    if issues:
        status = "telemetry_issue"

    return {
        "schema_version": COMPLEXITY_GOVERNANCE_SCHEMA_VERSION,
        "contract_id": COMPLEXITY_GOVERNANCE_CONTRACT_ID,
        "run_id": _clean_text(run_id) or _clean_text(telemetry.get("run_id")),
        "generated_at": now.isoformat(),
        "input_source": "w2d_self_fmea_telemetry",
        "status": status,
        "pattern_refs": ["P09", "P13"],
        "net_mav_formula": NET_MAV_FORMULA,
        "telemetry_summary": _telemetry_summary(telemetry),
        "gating_decisions": gating_decisions,
        "prune_review": prune_review,
        "self_application": self_application,
        "issues": issues,
        "summary": {
            "blocking_frontier_control_count": len(gating_decisions),
            "blocking_frontier_admitted_count": admitted_count,
            "blocking_frontier_rejected_count": rejected_count,
            "prune_review_control_count": len(prune_review),
            "prune_or_merge_candidate_count": prune_candidate_count,
            "self_application_recommendation": self_application["recommendation"],
        },
        "authority_boundary": _authority_boundary(),
        "surface": "quality_scorecard.complexity_governance",
    }


def complexity_governance_scorecard_gates(
    quality_evidence: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return scorecard-readable W10.E complexity-governance gates.

    The consumer gate blocks growth of the blocking frontier when Net-MAV or
    telemetry refs are missing. Existing-run complexity review remains advisory:
    prune/merge candidates produce warnings, not current-run closeout blockers.
    """

    report = quality_evidence.get(COMPLEXITY_GOVERNANCE_REPORT_KEY)
    if not isinstance(report, Mapping):
        return []

    summary = dict(report.get("summary") or {})
    rejected_count = _int_or_none(summary.get("blocking_frontier_rejected_count")) or 0
    prune_candidate_count = _int_or_none(summary.get("prune_or_merge_candidate_count")) or 0
    status = _normalized_label(report.get("status"))
    evidence_ref = f"quality_evidence/{COMPLEXITY_GOVERNANCE_FILENAME}"

    if rejected_count or status == "blocking_frontier_rejected":
        return [
            _scorecard_gate(
                code="complexity_governance_blocking_frontier_rejected",
                status="fail",
                message=(
                    "Complexity governance rejected proposed blocking-frontier control "
                    "growth without positive Net-MAV and telemetry refs."
                ),
                evidence_ref=evidence_ref,
                next_action=(
                    "Add expected Net-MAV and telemetry refs, or keep the control "
                    "advisory until measured."
                ),
                blocking=True,
                closeout_effect="blocking_frontier_admission_blocked",
                current_run_closeout_effect="none",
                blocking_frontier_rejected_count=rejected_count,
                prune_or_merge_candidate_count=prune_candidate_count,
            )
        ]

    if status == "telemetry_issue":
        return [
            _scorecard_gate(
                code="complexity_governance_telemetry_missing",
                status="warn",
                message=(
                    "Complexity governance could not read W2.D self-FMEA telemetry; "
                    "new controls cannot graduate from this report."
                ),
                evidence_ref=evidence_ref,
                next_action="Emit W2.D complexity-budget telemetry before frontier admission.",
                blocking=False,
                closeout_effect="advisory_measurement_gap",
                current_run_closeout_effect="none",
                blocking_frontier_rejected_count=rejected_count,
                prune_or_merge_candidate_count=prune_candidate_count,
            )
        ]

    if prune_candidate_count or status == "prune_review_due":
        return [
            _scorecard_gate(
                code="complexity_governance_prune_review_due",
                status="warn",
                message=(
                    "Complexity governance found controls that should be reviewed for "
                    "retirement or merge after the measurement window."
                ),
                evidence_ref=evidence_ref,
                next_action="Review retire/merge candidates before adding new controls.",
                blocking=False,
                closeout_effect="advisory_prune_review",
                current_run_closeout_effect="none",
                blocking_frontier_rejected_count=rejected_count,
                prune_or_merge_candidate_count=prune_candidate_count,
            )
        ]

    return [
        _scorecard_gate(
            code="complexity_governance_observed",
            status="pass",
            message="Complexity governance evaluated without Net-MAV admission blockers.",
            evidence_ref=evidence_ref,
            next_action="Keep the control set under periodic Net-MAV review.",
            blocking=False,
            closeout_effect="observe_only",
            current_run_closeout_effect="none",
            blocking_frontier_rejected_count=rejected_count,
            prune_or_merge_candidate_count=prune_candidate_count,
        )
    ]


def _expected_net_mav(
    control: Mapping[str, Any],
) -> tuple[float | None, dict[str, float] | None, dict[str, Any] | None]:
    explicit = _number(
        _first_present(
            control,
            ("expected_net_mav", "net_mav", "expected_marginal_assurance_value"),
        )
    )
    components = _mav_components_from(control)
    if components is not None:
        return (
            compute_net_mav(**components),
            components,
            None,
        )
    if explicit is not None:
        return _round_mav(explicit), None, None

    component_keys_present = any(key in control for key in _MAV_COMPONENTS)
    if component_keys_present:
        return (
            None,
            None,
            _issue(
                "expected_net_mav_components_incomplete",
                "All Net-MAV gain and penalty components are required when components are used.",
                field="mav_components",
            ),
        )
    return None, None, None


def _first_present(control: Mapping[str, Any], keys: Sequence[str]) -> object | None:
    for key in keys:
        if key in control and control[key] is not None:
            return control[key]
    return None


def _mav_components_from(control: Mapping[str, Any]) -> dict[str, float] | None:
    row: dict[str, float] = {}
    for key in _MAV_COMPONENTS:
        value = _number(control.get(key))
        if value is None:
            return None
        row[key] = value
    return row


def _telemetry_issues(soft_gate_telemetry: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not soft_gate_telemetry:
        return [
            _issue(
                "w2d_self_fmea_telemetry_missing",
                "Complexity governance must read W2.D soft-gate telemetry.",
                field="soft_gate_telemetry",
            )
        ]
    complexity = soft_gate_telemetry.get("complexity_budget_telemetry")
    if not isinstance(complexity, Mapping):
        return [
            _issue(
                "complexity_budget_telemetry_missing",
                "W2.D soft-gate telemetry must include complexity_budget_telemetry.",
                field="soft_gate_telemetry.complexity_budget_telemetry",
            )
        ]
    return []


def _telemetry_summary(soft_gate_telemetry: Mapping[str, Any]) -> dict[str, Any]:
    complexity = soft_gate_telemetry.get("complexity_budget_telemetry")
    if not isinstance(complexity, Mapping):
        return {
            "complexity_budget_status": "missing",
            "measurement_count": 0,
            "w2d_prune_or_merge_decision_count": 0,
        }
    measurements = complexity.get("measurements")
    decisions = _mapping_rows(complexity.get("prune_or_merge_decisions"))
    return {
        "complexity_budget_status": _clean_text(complexity.get("status")) or "unknown",
        "measurement_count": len(measurements) if isinstance(measurements, Mapping) else 0,
        "w2d_prune_or_merge_decision_count": len(decisions),
        "authority_effect": _clean_text(complexity.get("authority_effect")),
    }


def _self_application_review(
    soft_gate_telemetry: Mapping[str, Any],
    *,
    generated_at: datetime,
    measurement_window_started_at: datetime | str | None,
    measurement_window_days: int,
) -> dict[str, Any]:
    started_at = _datetime_from(measurement_window_started_at, default=generated_at)
    window_days = max(1, int(measurement_window_days))
    window_elapsed = generated_at - started_at >= timedelta(days=window_days)
    complexity = soft_gate_telemetry.get("complexity_budget_telemetry")
    decisions = (
        _mapping_rows(complexity.get("prune_or_merge_decisions"))
        if isinstance(complexity, Mapping)
        else []
    )
    effect_count = len(decisions)
    if not window_elapsed:
        recommendation = "observe_until_window_complete"
        reason = "measurement_window_open"
    elif effect_count > 0:
        recommendation = "retain"
        reason = "prune_decisions_observed"
    else:
        recommendation = "retire_candidate"
        reason = "no_prune_decisions_after_measurement_window"
    return {
        "control_id": COMPLEXITY_GOVERNANCE_CONTROL_ID,
        "owner": "team-runtime-quality",
        "self_applies": True,
        "recommendation": recommendation,
        "reason": reason,
        "measurement_window_started_at": started_at.isoformat(),
        "measurement_window_days": window_days,
        "window_elapsed": window_elapsed,
        "decision_effect_count": effect_count,
        "prune_or_merge_decisions": [dict(row) for row in decisions],
        "next_action": _next_action_for_recommendation(recommendation),
    }


def _wants_blocking_frontier(control: Mapping[str, Any]) -> bool:
    if bool(control.get("enter_blocking_frontier")):
        return True
    for key in ("frontier", "frontier_effect", "target_frontier", "control_effect"):
        label = _normalized_label(control.get(key))
        if label in _BLOCKING_FRONTIER_LABELS:
            return True
    return False


def _is_active_for_prune_review(control: Mapping[str, Any]) -> bool:
    if any(key in control for key in ("first_measured_at", "measurement_window_started_at")):
        return True
    return _normalized_label(control.get("status")) in _ACTIVE_CONTROL_STATUSES


def _decision_effect_count(control: Mapping[str, Any]) -> int:
    for key in (
        "decision_effect_count",
        "decisions_affected_count",
        "decision_impact_count",
        "blocking_decision_count",
        "prune_decision_count",
    ):
        count = _int_or_none(control.get(key))
        if count is not None:
            return max(0, count)
    for key in ("decision_effects", "decision_impacts", "decision_observations"):
        rows = _mapping_rows(control.get(key))
        if rows:
            return len(rows)
    rows = _mapping_rows(control.get("prune_or_merge_decisions"))
    return len(rows)


def _control_id(control: Mapping[str, Any]) -> str:
    return (
        _clean_text(
            control.get("control_id")
            or control.get("id")
            or control.get("gate_id")
            or control.get("name")
        )
        or "unknown_control"
    )


def _authority_boundary() -> dict[str, list[str]]:
    return {
        "authoritative_for": [
            "blocking_frontier_admission",
            "complexity_prune_review",
            "complexity_governance_self_application",
        ],
        "may_not_use_for": [
            "claim_support",
            "domain_evidence",
            "producer_evidence",
            "publication_authority_without_closeout",
            "current_run_closeout_block_without_scorecard_gate",
        ],
    }


def _next_action_for_recommendation(recommendation: str) -> str:
    if recommendation == "merge_candidate":
        return "Merge duplicate or overlapping controls before adding new blocking gates."
    if recommendation == "retire_candidate":
        return "Retire the control or document why it remains authority-load-bearing."
    if recommendation == "retain":
        return "Keep the control under the next periodic Net-MAV review."
    return "Continue measurement until the review window closes."


def _issue(code: str, message: str, *, field: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "severity": "blocking",
        "message": message,
    }
    if field is not None:
        payload["field"] = field
    return payload


def _scorecard_gate(
    *,
    code: str,
    status: str,
    message: str,
    evidence_ref: str,
    next_action: str,
    blocking: bool,
    closeout_effect: str,
    current_run_closeout_effect: str,
    blocking_frontier_rejected_count: int,
    prune_or_merge_candidate_count: int,
) -> dict[str, Any]:
    return {
        "name": "policy_design_w10e_complexity_governance",
        "stage": "governance",
        "code": code,
        "status": status,
        "layer": "runtime_quality",
        "phase": "policy_design_w10e_complexity_governance",
        "message": message,
        "evidence_ref": evidence_ref,
        "next_action": next_action,
        "blocking": blocking,
        "owner": "team-runtime-quality",
        "closeout_effect": closeout_effect,
        "current_run_closeout_effect": current_run_closeout_effect,
        "blocking_frontier_rejected_count": blocking_frontier_rejected_count,
        "prune_or_merge_candidate_count": prune_or_merge_candidate_count,
    }


def _telemetry_refs(control: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for key in (
        "telemetry_refs",
        "runtime_telemetry_refs",
        "self_fmea_telemetry_refs",
        "evidence_refs",
    ):
        values.extend(_text_list(control.get(key)))
    evidence_ref = _clean_text(control.get("evidence_ref") or control.get("cas_ref"))
    if evidence_ref:
        values.append(evidence_ref)
    runtime_event_ref = _clean_text(control.get("runtime_event_ref"))
    if runtime_event_ref:
        values.append(runtime_event_ref)
    return list(dict.fromkeys(values))


def _text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = _clean_text(value)
        return [text] if text else []
    if isinstance(value, Mapping):
        ref = _clean_text(value.get("ref") or value.get("id") or value.get("control_id"))
        return [ref] if ref else []
    if isinstance(value, Sequence):
        rows: list[str] = []
        for item in value:
            rows.extend(_text_list(item))
        return rows
    return []


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [row for row in value if isinstance(row, Mapping)]
    return []


def _required_finite_number(value: object, *, field: str) -> float:
    number = _number(value)
    if number is None:
        raise ComplexityGovernanceError(
            "net_mav_component_invalid",
            "Net-MAV components must be finite numbers.",
            field=field,
        )
    return number


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


def _round_mav(value: float) -> float:
    return round(float(value), 6)


def _datetime_from(value: object, *, default: datetime) -> datetime:
    if isinstance(value, datetime):
        return _utc(value)
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                return _utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
            except ValueError:
                return default
    return default


def _utc(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(tz=UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalized_label(value: object) -> str:
    text = _clean_text(value)
    if text is None:
        return ""
    return text.casefold().replace("-", "_").replace(" ", "_")


__all__ = [
    "COMPLEXITY_GOVERNANCE_CONTRACT_ID",
    "COMPLEXITY_GOVERNANCE_CONTROL_ID",
    "COMPLEXITY_GOVERNANCE_FILENAME",
    "COMPLEXITY_GOVERNANCE_REPORT_KEY",
    "COMPLEXITY_GOVERNANCE_SCHEMA_VERSION",
    "NET_MAV_FORMULA",
    "ComplexityGovernanceError",
    "build_complexity_governance_report",
    "complexity_governance_scorecard_gates",
    "compute_net_mav",
    "evaluate_blocking_frontier_control",
    "review_controls_for_pruning",
]
