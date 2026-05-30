"""Authority-aware run-cost enforcement gates for Policy Design Case runs."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from polisyos.runtime.quality.cost_degradation import (
    COST_DEGRADATION_TELEMETRY_REPORT_KEY,
    CostDegradationTelemetryError,
    build_cost_degradation_telemetry_from_quality_context,
    validate_cost_degradation_telemetry,
)

RUN_COST_GATE_SCHEMA_VERSION = "policyos.runtime.policy_design_case.run_cost_gate.v1"
RUN_COST_GATE_CONTRACT_ID = "policy_design_case.run_cost_gate.v1"
RUN_COST_GATE_REPORT_KEY = "run_cost_gate"
RUN_COST_GATE_FILENAME = "run_cost_gate.json"

_DEFAULT_OWNER = "team-runtime-quality"
_DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60
_PRODUCTION_AUTHORITY_LEVELS = frozenset(
    {"production", "governed", "publication", "publishable", "public", "release"}
)
_RESEARCH_AUTHORITY_LEVELS = frozenset(
    {"research", "exploratory", "experiment", "evaluation", "dev", "development", "test"}
)
_DIMENSION_ALIASES = {
    "provider_api_call": "provider_api_calls",
    "provider_api_calls": "provider_api_calls",
    "provider_call": "provider_api_calls",
    "provider_calls": "provider_api_calls",
    "api_calls": "provider_api_calls",
    "token": "tokens",
    "tokens": "tokens",
    "compute_dollar": "compute_dollars",
    "compute_dollars": "compute_dollars",
    "compute_usd": "compute_dollars",
    "provider_cost": "compute_dollars",
    "dollars": "compute_dollars",
    "search": "embedding_searches",
    "searches": "embedding_searches",
    "embedding": "embedding_searches",
    "embeddings": "embedding_searches",
    "embedding_search": "embedding_searches",
    "embedding_searches": "embedding_searches",
    "wall_clock": "wall_clock_seconds",
    "wall_clock_second": "wall_clock_seconds",
    "wall_clock_seconds": "wall_clock_seconds",
    "elapsed_seconds": "wall_clock_seconds",
    "retry": "retries",
    "retries": "retries",
    "retry_count": "retries",
    "acquisition": "acquisition_dollars",
    "acquisition_dollar": "acquisition_dollars",
    "acquisition_dollars": "acquisition_dollars",
    "acquisition_usd": "acquisition_dollars",
}
_DIMENSION_UNITS = {
    "provider_api_calls": "call",
    "tokens": "token",
    "compute_dollars": "usd",
    "embedding_searches": "query",
    "wall_clock_seconds": "second",
    "retries": "retry",
    "acquisition_dollars": "usd",
}


class RunCostGateError(ValueError):
    """Raised when a W10.D run-cost gate artifact violates authority semantics."""

    def __init__(self, code: str, message: str, *, field: str | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.field = field


def build_run_cost_gate_report(
    *,
    quality_evidence: Mapping[str, Any],
    job_payload: Mapping[str, Any] | None = None,
    run_payload: Mapping[str, Any] | None = None,
    canary_kind: str | None = None,
    budget_policy: Mapping[str, Any] | None = None,
    authority_level: str | None = None,
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the W10.D authority-aware cost enforcement artifact.

    Args:
        quality_evidence: Runtime quality evidence that may already contain
            W2.C `cost_degradation_telemetry`.
        job_payload: Optional runtime job payload with retry and timing inputs.
        run_payload: Optional runtime run payload.
        canary_kind: Runtime authority lane, such as `production` or `research`.
        budget_policy: Governed run-cost policy. Hard blockers are emitted only
            when an exceeded limit has an authority-policy ref and the effective
            authority level is production-like.
        authority_level: Optional explicit authority override.
        evidence_ref: Optional artifact ref for the gate report.
        runtime_event_ref: Optional runtime event ref for the gate report.
        now: Generation timestamp.

    Returns:
        A normalized run-cost enforcement report with typed blockers or
        limitations.
    """

    policy = _budget_policy(
        explicit_policy=budget_policy,
        quality_evidence=quality_evidence,
        job_payload=job_payload,
        run_payload=run_payload,
    )
    telemetry = _telemetry(
        quality_evidence=quality_evidence,
        job_payload=job_payload,
        run_payload=run_payload,
        canary_kind=canary_kind,
    )
    run_id = _run_id(
        telemetry=telemetry,
        quality_evidence=quality_evidence,
        job_payload=job_payload,
        run_payload=run_payload,
    )
    effective_authority = _effective_authority_level(
        explicit=authority_level,
        policy=policy,
        telemetry=telemetry,
        quality_evidence=quality_evidence,
        canary_kind=canary_kind,
    )
    observations = _dimension_observations(telemetry)
    gate_rows = [
        _evaluate_limit(
            limit=limit,
            observations=observations,
            run_id=run_id,
            authority_level=effective_authority,
            policy=policy,
        )
        for limit in _policy_limits(policy)
    ]
    gate_rows = [row for row in gate_rows if row is not None]

    blockers = [
        _typed_blocker(row, run_id=run_id)
        for row in gate_rows
        if row["status"] == "blocked"
    ]
    limitations = [
        _typed_limitation(row, run_id=run_id)
        for row in gate_rows
        if row["status"] == "limited"
    ]
    warnings = [
        _typed_warning(row, run_id=run_id)
        for row in gate_rows
        if row["status"] == "warning"
    ]
    issues = [
        *[_issue_from_item(item, severity="fail") for item in blockers],
        *[_issue_from_item(item, severity="limitation") for item in limitations],
        *[_issue_from_item(item, severity="warning") for item in warnings],
    ]
    deficit_crosswalk = [
        *[_deficit_from_item(item, closeout_effect="closeout_blocked") for item in blockers],
        *[
            _deficit_from_item(item, closeout_effect="publish_with_limitation")
            for item in limitations
        ],
    ]
    summary = _summary(gate_rows, observations)
    status = _report_status(blockers=blockers, limitations=limitations, warnings=warnings)
    report = {
        "schema_version": RUN_COST_GATE_SCHEMA_VERSION,
        "contract_id": RUN_COST_GATE_CONTRACT_ID,
        "gate_id": f"run-cost-gate-{_slug(run_id)}",
        "run_id": run_id,
        "job_id": _text(
            _nested_get(job_payload, "job_id") or _nested_get(run_payload, "job_id")
        ),
        "authority_level": effective_authority,
        "generated_at": _utc(now).isoformat(),
        "status": status,
        "closeout_effect": _report_closeout_effect(
            blockers=blockers,
            limitations=limitations,
        ),
        "budget_policy_ref": _policy_ref(policy),
        "telemetry_ref": _text(telemetry.get("evidence_ref")),
        "evidence_ref": _runtime_ref(evidence_ref)
        or f"artifact://runtime-quality/run-cost-gate/{_slug(run_id)}/report",
        "runtime_event_ref": runtime_event_ref
        if _runtime_event_ref(runtime_event_ref)
        else f"event://runtime/run-cost-gate/{_slug(run_id)}",
        "authority_envelope": _authority_envelope(run_id=run_id),
        "governance": {
            "posture": "authority_level_enforcement",
            "hard_block_requires_authority_policy_ref": True,
            "research_authority_effect": "limitation_only",
            "patterns": ["P01", "P02", "P05", "P09", "P13"],
        },
        "observations": [dict(value) for value in observations.values()],
        "gates": gate_rows,
        "blockers": blockers,
        "limitations": limitations,
        "warnings": warnings,
        "issues": issues,
        "deficit_crosswalk": deficit_crosswalk,
        "summary": summary,
    }
    if report["job_id"] is None:
        report.pop("job_id")
    return validate_run_cost_gate_report(report)


def validate_run_cost_gate_report(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a W10.D run-cost enforcement report."""

    if not isinstance(record, Mapping):
        raise RunCostGateError(
            "run_cost_gate_invalid",
            "Run-cost gate report must be a mapping.",
        )
    schema_version = _required_text(
        record.get("schema_version"),
        field="schema_version",
        code="run_cost_gate_schema_version_missing",
    )
    if schema_version != RUN_COST_GATE_SCHEMA_VERSION:
        raise RunCostGateError(
            "run_cost_gate_schema_version_invalid",
            "Run-cost gate report must use the W10.D schema version.",
            field="schema_version",
        )
    run_id = _required_text(
        record.get("run_id"),
        field="run_id",
        code="run_cost_gate_run_id_missing",
    )
    authority_level = _normalized_token(
        _required_text(
            record.get("authority_level"),
            field="authority_level",
            code="run_cost_gate_authority_level_missing",
        )
    )

    normalized = dict(record)
    normalized["schema_version"] = RUN_COST_GATE_SCHEMA_VERSION
    normalized["contract_id"] = _text(record.get("contract_id")) or RUN_COST_GATE_CONTRACT_ID
    normalized["gate_id"] = _text(record.get("gate_id")) or f"run-cost-gate-{_slug(run_id)}"
    normalized["run_id"] = run_id
    normalized["authority_level"] = authority_level
    normalized["evidence_ref"] = _runtime_ref(record.get("evidence_ref")) or (
        f"artifact://runtime-quality/run-cost-gate/{_slug(run_id)}/report"
    )
    event_ref = _text(record.get("runtime_event_ref"))
    normalized["runtime_event_ref"] = (
        event_ref
        if _runtime_event_ref(event_ref)
        else f"event://runtime/run-cost-gate/{_slug(run_id)}"
    )

    gate_rows = [
        _validate_gate_row(row, index=index, authority_level=authority_level)
        for index, row in enumerate(_rows(record.get("gates")))
    ]
    blockers = [
        _validate_blocker(row, index=index, authority_level=authority_level)
        for index, row in enumerate(_rows(record.get("blockers")))
    ]
    limitations = [
        _validate_attention_item(row, index=index)
        for index, row in enumerate(_rows(record.get("limitations")))
    ]
    warnings = [
        _validate_attention_item(row, index=index)
        for index, row in enumerate(_rows(record.get("warnings")))
    ]

    if authority_level in _RESEARCH_AUTHORITY_LEVELS and blockers:
        raise RunCostGateError(
            "run_cost_gate_research_blocker_invalid",
            "Research-authority run-cost gates may emit limitations, not blockers.",
            field="blockers",
        )

    status = _status(record.get("status"))
    expected_status = _report_status(
        blockers=blockers,
        limitations=limitations,
        warnings=warnings,
    )
    if status != expected_status:
        status = expected_status
    normalized["status"] = status
    normalized["closeout_effect"] = _report_closeout_effect(
        blockers=blockers,
        limitations=limitations,
    )
    normalized["gates"] = gate_rows
    normalized["blockers"] = blockers
    normalized["limitations"] = limitations
    normalized["warnings"] = warnings
    normalized["issues"] = [dict(row) for row in _rows(record.get("issues"))]
    normalized["deficit_crosswalk"] = [
        dict(row) for row in _rows(record.get("deficit_crosswalk"))
    ]
    normalized["summary"] = _validated_summary(
        record.get("summary"),
        gate_rows=gate_rows,
        blockers=blockers,
        limitations=limitations,
        warnings=warnings,
    )
    governance = dict(record.get("governance") or {})
    governance.setdefault("posture", "authority_level_enforcement")
    governance.setdefault("hard_block_requires_authority_policy_ref", True)
    governance.setdefault("research_authority_effect", "limitation_only")
    governance.setdefault("patterns", ["P01", "P02", "P05", "P09", "P13"])
    normalized["governance"] = governance
    if "authority_envelope" not in normalized:
        normalized["authority_envelope"] = _authority_envelope(run_id=run_id)
    return normalized


def cost_gate_scorecard_gates(
    *,
    quality_evidence: Mapping[str, Any],
    job_payload: Mapping[str, Any] | None = None,
    run_payload: Mapping[str, Any] | None = None,
    canary_kind: str | None = None,
) -> list[dict[str, Any]]:
    """Return scorecard-readable W10.D run-cost gates."""

    try:
        record = quality_evidence.get(RUN_COST_GATE_REPORT_KEY)
        if isinstance(record, Mapping):
            report = validate_run_cost_gate_report(record)
        else:
            report = build_run_cost_gate_report(
                quality_evidence=quality_evidence,
                job_payload=job_payload,
                run_payload=run_payload,
                canary_kind=canary_kind,
            )
    except (RunCostGateError, CostDegradationTelemetryError) as exc:
        return [
            _scorecard_gate(
                status="fail",
                blocking=True,
                code=getattr(exc, "code", "run_cost_gate_invalid"),
                message=str(exc),
                evidence_ref="quality_evidence/run_cost_gate.json",
                closeout_effect="blocking",
                missing_input=getattr(exc, "field", None) or RUN_COST_GATE_REPORT_KEY,
            )
        ]

    summary = dict(report["summary"])
    blocked_count = int(summary.get("blocked_count") or 0)
    limitation_count = int(summary.get("limitation_count") or 0)
    if blocked_count:
        return [
            _scorecard_gate(
                status="fail",
                blocking=True,
                code="run_cost_authority_budget_blocking",
                message="Production-authority run exceeded an authority-level run-cost budget.",
                evidence_ref=str(report["evidence_ref"]),
                closeout_effect="blocking",
                blocked_count=blocked_count,
                limitation_count=limitation_count,
            )
        ]
    if limitation_count:
        return [
            _scorecard_gate(
                status="warn",
                blocking=False,
                code="run_cost_budget_limitation",
                message="Run-cost budget breach is visible as an authority-scoped limitation.",
                evidence_ref=str(report["evidence_ref"]),
                closeout_effect="limitation",
                limitation_count=limitation_count,
            )
        ]
    return [
        _scorecard_gate(
            status="pass",
            blocking=False,
            code="run_cost_gate_observed",
            message="Run-cost enforcement gate evaluated without authority-level blockers.",
            evidence_ref=str(report["evidence_ref"]),
            closeout_effect="observe_only",
        )
    ]


def _budget_policy(
    *,
    explicit_policy: Mapping[str, Any] | None,
    quality_evidence: Mapping[str, Any],
    job_payload: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if isinstance(explicit_policy, Mapping):
        return explicit_policy
    for candidate in (
        quality_evidence.get("run_cost_budget_policy"),
        quality_evidence.get("cost_gate_policy"),
        _nested_get(quality_evidence.get("policy_design_case"), "run_cost_budget_policy"),
        _nested_get(job_payload, "run_cost_budget_policy"),
        _nested_get(run_payload, "run_cost_budget_policy"),
        _nested_get(job_payload, "cost_gate_policy"),
        _nested_get(run_payload, "cost_gate_policy"),
    ):
        if isinstance(candidate, Mapping):
            return candidate
    return {}


def _telemetry(
    *,
    quality_evidence: Mapping[str, Any],
    job_payload: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
    canary_kind: str | None,
) -> dict[str, Any]:
    record = quality_evidence.get(COST_DEGRADATION_TELEMETRY_REPORT_KEY)
    if isinstance(record, Mapping):
        return validate_cost_degradation_telemetry(record)
    return build_cost_degradation_telemetry_from_quality_context(
        quality_evidence=quality_evidence,
        job_payload=job_payload,
        run_payload=run_payload,
        canary_kind=canary_kind,
    )


def _run_id(
    *,
    telemetry: Mapping[str, Any],
    quality_evidence: Mapping[str, Any],
    job_payload: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
) -> str:
    return (
        _text(telemetry.get("run_id"))
        or _text(_nested_get(job_payload, "run_id"))
        or _text(_nested_get(run_payload, "run_id"))
        or _text(_nested_get(quality_evidence.get("policy_design_case"), "run_id"))
        or "unknown-run"
    )


def _effective_authority_level(
    *,
    explicit: str | None,
    policy: Mapping[str, Any],
    telemetry: Mapping[str, Any],
    quality_evidence: Mapping[str, Any],
    canary_kind: str | None,
) -> str:
    case = quality_evidence.get("policy_design_case")
    for value in (
        explicit,
        policy.get("authority_level"),
        _nested_get(case, "authority_level"),
        _nested_get(case, "requested_authority_level"),
        _nested_get(case, "effective_execution_profile"),
        telemetry.get("authority_profile"),
        canary_kind,
        "research",
    ):
        label = _normalized_token(value)
        if label:
            return label
    return "research"


def _dimension_observations(telemetry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    dimensions: dict[str, dict[str, Any]] = {
        dimension: {
            "dimension": dimension,
            "observed_value": 0.0,
            "unit": unit,
            "source_metric_ids": [],
            "source_evidence_refs": [],
        }
        for dimension, unit in _DIMENSION_UNITS.items()
    }
    for row in _rows(telemetry.get("observations")):
        metric_type = _normalized_token(row.get("metric_type"))
        unit = _normalized_token(row.get("unit"))
        value = _number(row.get("observed_value")) or 0.0
        target_dimensions = _dimensions_for_observation(metric_type=metric_type, unit=unit)
        for dimension in target_dimensions:
            aggregate = dimensions[dimension]
            aggregate["observed_value"] = round(float(aggregate["observed_value"]) + value, 6)
            metric_id = _text(row.get("metric_id"))
            if metric_id is not None:
                aggregate["source_metric_ids"].append(metric_id)
            evidence_ref = _runtime_ref(row.get("evidence_ref"))
            if evidence_ref is not None:
                aggregate["source_evidence_refs"].append(evidence_ref)
    return dimensions


def _dimensions_for_observation(*, metric_type: str, unit: str) -> tuple[str, ...]:
    if metric_type == "provider_call":
        return ("provider_api_calls",)
    if metric_type == "tokens":
        return ("tokens",)
    if metric_type == "provider_cost":
        return ("compute_dollars",)
    if metric_type == "compute" and unit == "usd":
        return ("compute_dollars",)
    if metric_type in {"search", "embedding", "embeddings", "embedding_search"}:
        return ("embedding_searches",)
    if metric_type == "wall_clock":
        return ("wall_clock_seconds",)
    if metric_type == "retry":
        return ("retries",)
    if metric_type == "acquisition" and unit == "usd":
        return ("acquisition_dollars",)
    return ()


def _policy_limits(policy: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw_limits = policy.get("limits")
    rows: list[Mapping[str, Any]] = []
    if isinstance(raw_limits, Mapping):
        rows.extend(
            {"dimension": key, "budget": value}
            for key, value in raw_limits.items()
            if not isinstance(value, Mapping)
        )
        rows.extend(
            {"dimension": key, **dict(value)}
            for key, value in raw_limits.items()
            if isinstance(value, Mapping)
        )
    elif isinstance(raw_limits, Sequence) and not isinstance(raw_limits, (str, bytes, bytearray)):
        rows.extend(item for item in raw_limits if isinstance(item, Mapping))
    for key in ("budgets", "budget_limits"):
        value = policy.get(key)
        if isinstance(value, Mapping):
            rows.extend(
                {"dimension": dimension, "budget": budget}
                for dimension, budget in value.items()
                if not isinstance(budget, Mapping)
            )
            rows.extend(
                {"dimension": dimension, **dict(budget)}
                for dimension, budget in value.items()
                if isinstance(budget, Mapping)
            )
    return tuple(rows)


def _evaluate_limit(
    *,
    limit: Mapping[str, Any],
    observations: Mapping[str, Mapping[str, Any]],
    run_id: str,
    authority_level: str,
    policy: Mapping[str, Any],
) -> dict[str, Any] | None:
    dimension = _dimension(limit.get("dimension") or limit.get("metric_type") or limit.get("name"))
    if dimension is None:
        return None
    budget_value = _number(
        limit.get("budget")
        or limit.get("budget_value")
        or limit.get("limit")
        or limit.get("max")
        or limit.get("ceiling")
    )
    if budget_value is None:
        return None
    observation = observations.get(dimension) or {}
    observed_value = _number(observation.get("observed_value")) or 0.0
    exceeded = observed_value > budget_value
    desired_effect = _closeout_effect(
        limit.get("closeout_effect") or policy.get("closeout_effect")
    )
    authority_policy_ref = _text(
        limit.get("authority_policy_ref") or policy.get("authority_policy_ref")
    )
    production_authority = authority_level in _PRODUCTION_AUTHORITY_LEVELS
    if not exceeded:
        status = "pass"
        closeout_effect = "observe_only"
    elif desired_effect == "warning":
        status = "warning"
        closeout_effect = "warning"
    elif desired_effect == "blocking" and production_authority and authority_policy_ref:
        status = "blocked"
        closeout_effect = "blocking"
    else:
        status = "limited"
        closeout_effect = "limitation"
    unit = _text(limit.get("unit")) or _DIMENSION_UNITS[dimension]
    return {
        "gate_id": f"{_slug(run_id)}.{dimension}",
        "dimension": dimension,
        "observed_value": observed_value,
        "budget_value": budget_value,
        "unit": unit,
        "status": status,
        "closeout_effect": closeout_effect,
        "over_by": round(max(0.0, observed_value - budget_value), 6),
        "over_ratio": round(observed_value / budget_value, 6) if budget_value else None,
        "authority_level": authority_level,
        "authority_policy_ref": authority_policy_ref,
        "owner": _text(limit.get("owner") or policy.get("owner")) or _DEFAULT_OWNER,
        "ttl_seconds": int(
            _number(limit.get("ttl_seconds") or policy.get("ttl_seconds"))
            or _DEFAULT_TTL_SECONDS
        ),
        "next_action": _text(limit.get("next_action") or policy.get("next_action"))
        or f"Review {dimension} budget before authority promotion.",
        "evidence_ref": _runtime_ref(limit.get("evidence_ref"))
        or _first_runtime_ref(observation.get("source_evidence_refs"))
        or _runtime_ref(policy.get("evidence_ref"))
        or f"artifact://runtime-quality/run-cost-gate/{_slug(run_id)}/{dimension}",
        "source_metric_ids": list(observation.get("source_metric_ids") or []),
    }


def _validate_gate_row(
    row: Mapping[str, Any],
    *,
    index: int,
    authority_level: str,
) -> dict[str, Any]:
    dimension = _dimension(
        _required_text(
            row.get("dimension"),
            field=f"gates[{index}].dimension",
            code="run_cost_gate_dimension_missing",
        )
    )
    if dimension is None:
        raise RunCostGateError(
            "run_cost_gate_dimension_invalid",
            "Run-cost gate dimension is not supported.",
            field=f"gates[{index}].dimension",
        )
    status = _status(row.get("status"))
    normalized = dict(row)
    normalized["dimension"] = dimension
    normalized["observed_value"] = _required_number(
        row.get("observed_value"),
        field=f"gates[{index}].observed_value",
        code="run_cost_gate_observed_value_missing",
    )
    normalized["budget_value"] = _required_number(
        row.get("budget_value"),
        field=f"gates[{index}].budget_value",
        code="run_cost_gate_budget_value_missing",
    )
    normalized["status"] = status
    normalized["closeout_effect"] = _closeout_effect(row.get("closeout_effect"))
    normalized["unit"] = _text(row.get("unit")) or _DIMENSION_UNITS[dimension]
    normalized["owner"] = _text(row.get("owner")) or _DEFAULT_OWNER
    normalized["ttl_seconds"] = int(_number(row.get("ttl_seconds")) or _DEFAULT_TTL_SECONDS)
    normalized["next_action"] = _text(row.get("next_action")) or (
        f"Review {dimension} budget before authority promotion."
    )
    normalized["evidence_ref"] = _runtime_ref(row.get("evidence_ref")) or (
        f"artifact://runtime-quality/run-cost-gate/unknown/{dimension}"
    )
    if status == "blocked":
        if authority_level not in _PRODUCTION_AUTHORITY_LEVELS:
            raise RunCostGateError(
                "run_cost_gate_nonproduction_blocker_invalid",
                "Only production-like authority levels may carry run-cost blockers.",
                field=f"gates[{index}].status",
            )
        if not _text(row.get("authority_policy_ref")):
            raise RunCostGateError(
                "run_cost_gate_blocking_policy_ref_missing",
                "Run-cost blockers require an authority-level policy ref.",
                field=f"gates[{index}].authority_policy_ref",
            )
    return normalized


def _validate_blocker(
    row: Mapping[str, Any],
    *,
    index: int,
    authority_level: str,
) -> dict[str, Any]:
    normalized = _validate_attention_item(row, index=index)
    if _status(normalized.get("status")) != "blocked":
        raise RunCostGateError(
            "run_cost_gate_blocker_status_invalid",
            "Run-cost blockers must use blocked status.",
            field=f"blockers[{index}].status",
        )
    if authority_level not in _PRODUCTION_AUTHORITY_LEVELS:
        raise RunCostGateError(
            "run_cost_gate_nonproduction_blocker_invalid",
            "Only production-like authority levels may carry run-cost blockers.",
            field=f"blockers[{index}]",
        )
    if not _text(normalized.get("authority_policy_ref")):
        raise RunCostGateError(
            "run_cost_gate_blocking_policy_ref_missing",
            "Run-cost blockers require an authority-level policy ref.",
            field=f"blockers[{index}].authority_policy_ref",
        )
    return normalized


def _validate_attention_item(row: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    normalized = dict(row)
    normalized["dimension"] = _required_text(
        row.get("dimension"),
        field=f"attention[{index}].dimension",
        code="run_cost_gate_attention_dimension_missing",
    )
    normalized["code"] = _required_text(
        row.get("code"),
        field=f"attention[{index}].code",
        code="run_cost_gate_attention_code_missing",
    )
    normalized["message"] = _required_text(
        row.get("message"),
        field=f"attention[{index}].message",
        code="run_cost_gate_attention_message_missing",
    )
    normalized["owner"] = _text(row.get("owner")) or _DEFAULT_OWNER
    normalized["ttl_seconds"] = int(_number(row.get("ttl_seconds")) or _DEFAULT_TTL_SECONDS)
    normalized["next_action"] = _text(row.get("next_action")) or "Review run-cost gate."
    normalized["evidence_ref"] = (
        _runtime_ref(row.get("evidence_ref")) or "quality_evidence/run_cost_gate.json"
    )
    return normalized


def _typed_blocker(row: Mapping[str, Any], *, run_id: str) -> dict[str, Any]:
    return _typed_attention_item(
        row,
        run_id=run_id,
        status="blocked",
        code="run_cost_budget_exceeded",
        message="Run-cost budget exceeded for production-authority closeout.",
    )


def _typed_limitation(row: Mapping[str, Any], *, run_id: str) -> dict[str, Any]:
    return _typed_attention_item(
        row,
        run_id=run_id,
        status="limited",
        code="run_cost_budget_limitation",
        message="Run-cost budget exceeded; authority effect is limited rather than blocking.",
    )


def _typed_warning(row: Mapping[str, Any], *, run_id: str) -> dict[str, Any]:
    return _typed_attention_item(
        row,
        run_id=run_id,
        status="warning",
        code="run_cost_budget_warning",
        message="Run-cost budget warning emitted by governed policy.",
    )


def _typed_attention_item(
    row: Mapping[str, Any],
    *,
    run_id: str,
    status: str,
    code: str,
    message: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "code": code,
        "message": message,
        "run_id": run_id,
        "dimension": row["dimension"],
        "observed_value": row["observed_value"],
        "budget_value": row["budget_value"],
        "unit": row["unit"],
        "over_by": row["over_by"],
        "over_ratio": row["over_ratio"],
        "authority_level": row["authority_level"],
        "authority_policy_ref": row.get("authority_policy_ref"),
        "owner": row["owner"],
        "ttl_seconds": row["ttl_seconds"],
        "next_action": row["next_action"],
        "evidence_ref": row["evidence_ref"],
        "runtime_event_ref": f"event://runtime/run-cost-gate/{_slug(run_id)}/{row['dimension']}",
        "source_metric_ids": list(row.get("source_metric_ids") or []),
    }


def _issue_from_item(item: Mapping[str, Any], *, severity: str) -> dict[str, Any]:
    return {
        "code": item["code"],
        "message": item["message"],
        "severity": severity,
        "dimension": item["dimension"],
        "owner": item["owner"],
        "next_action": item["next_action"],
        "evidence_ref": item["evidence_ref"],
    }


def _deficit_from_item(item: Mapping[str, Any], *, closeout_effect: str) -> dict[str, Any]:
    return {
        "deficit_id": f"run_cost_gate.{item['dimension']}",
        "deficit_type": "run_cost_budget",
        "status_axis": "cost_admissibility",
        "closeout_effect": closeout_effect,
        "dimension": item["dimension"],
        "owner": item["owner"],
        "ttl_seconds": item["ttl_seconds"],
        "next_action": item["next_action"],
        "evidence_ref": item["evidence_ref"],
    }


def _summary(
    gate_rows: Sequence[Mapping[str, Any]],
    observations: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "gate_count": len(gate_rows),
        "observed_dimension_count": sum(
            1 for value in observations.values() if float(value.get("observed_value") or 0.0) > 0
        ),
        "pass_count": sum(1 for row in gate_rows if row["status"] == "pass"),
        "warning_count": sum(1 for row in gate_rows if row["status"] == "warning"),
        "limitation_count": sum(1 for row in gate_rows if row["status"] == "limited"),
        "blocked_count": sum(1 for row in gate_rows if row["status"] == "blocked"),
        "over_budget_count": sum(1 for row in gate_rows if float(row.get("over_by") or 0.0) > 0),
    }


def _validated_summary(
    value: object,
    *,
    gate_rows: Sequence[Mapping[str, Any]],
    blockers: Sequence[Mapping[str, Any]],
    limitations: Sequence[Mapping[str, Any]],
    warnings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    summary = dict(value) if isinstance(value, Mapping) else {}
    summary["gate_count"] = len(gate_rows)
    summary["pass_count"] = sum(1 for row in gate_rows if row["status"] == "pass")
    summary["warning_count"] = len(warnings)
    summary["limitation_count"] = len(limitations)
    summary["blocked_count"] = len(blockers)
    summary["over_budget_count"] = sum(
        1 for row in gate_rows if float(row.get("over_by") or 0.0) > 0
    )
    summary.setdefault("observed_dimension_count", 0)
    return summary


def _report_status(
    *,
    blockers: Sequence[Mapping[str, Any]],
    limitations: Sequence[Mapping[str, Any]],
    warnings: Sequence[Mapping[str, Any]],
) -> str:
    if blockers:
        return "blocked"
    if limitations:
        return "limited"
    if warnings:
        return "warning"
    return "pass"


def _report_closeout_effect(
    *,
    blockers: Sequence[Mapping[str, Any]],
    limitations: Sequence[Mapping[str, Any]],
) -> str:
    if blockers:
        return "blocking"
    if limitations:
        return "limitation"
    return "observe_only"


def _scorecard_gate(
    *,
    status: str,
    blocking: bool,
    code: str,
    message: str,
    evidence_ref: str,
    closeout_effect: str,
    missing_input: str | None = None,
    blocked_count: int | None = None,
    limitation_count: int | None = None,
) -> dict[str, Any]:
    payload = {
        "name": "policy_design_w10d_run_cost_gate",
        "stage": "ops",
        "code": code,
        "status": status,
        "layer": "runtime_cost_enforcement",
        "phase": "policy_design_w10d_run_cost_gate",
        "message": message,
        "evidence_ref": evidence_ref,
        "next_action": (
            "Inspect quality_evidence/run_cost_gate.json and the governed "
            "authority-level run-cost policy before promotion."
        ),
        "blocking": blocking,
        "owner": _DEFAULT_OWNER,
        "closeout_effect": closeout_effect,
    }
    for key, value in (
        ("missing_input", missing_input),
        ("blocked_count", blocked_count),
        ("limitation_count", limitation_count),
    ):
        if value is not None:
            payload[key] = value
    return payload


def _authority_envelope(*, run_id: str) -> dict[str, Any]:
    return {
        "authoritative_for": ["run_cost_enforcement"],
        "may_not_use_for": [
            "claim_evidence",
            "domain_evidence",
            "evidence_quality_downgrade",
            "projection_authority",
        ],
        "run_id": run_id,
        "producer": "polisyos.runtime.quality.cost_gate",
    }


def _dimension(value: object) -> str | None:
    token = _normalized_token(value)
    return _DIMENSION_ALIASES.get(token)


def _policy_ref(policy: Mapping[str, Any]) -> str | None:
    return _text(policy.get("policy_ref") or policy.get("policy_id") or policy.get("config_ref"))


def _closeout_effect(value: object) -> str:
    token = _normalized_token(value)
    if token in {"block", "blocked", "blocking", "hard_block"}:
        return "blocking"
    if token in {"warn", "warning"}:
        return "warning"
    if token in {"limit", "limited", "limitation"}:
        return "limitation"
    return "limitation"


def _status(value: object) -> str:
    token = _normalized_token(value)
    if token in {"pass", "passed", "ok", "success", "succeeded"}:
        return "pass"
    if token in {"warn", "warning"}:
        return "warning"
    if token in {"limit", "limited", "limitation"}:
        return "limited"
    if token in {"block", "blocked", "blocking", "fail", "failed"}:
        return "blocked"
    return token or "pass"


def _rows(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def _required_text(value: object, *, field: str, code: str) -> str:
    text = _text(value)
    if text is None:
        raise RunCostGateError(code, f"Run-cost gate is missing {field}.", field=field)
    return text


def _required_number(value: object, *, field: str, code: str) -> float:
    number = _number(value)
    if number is None:
        raise RunCostGateError(code, f"Run-cost gate is missing numeric {field}.", field=field)
    return number


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _normalized_token(value: object) -> str:
    text = _text(value)
    if text is None:
        return ""
    return text.casefold().replace("-", "_").replace(" ", "_")


def _nested_get(payload: object, key: str) -> object | None:
    if isinstance(payload, Mapping):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = _nested_get(value, key)
            if found is not None:
                return found
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        for item in payload:
            found = _nested_get(item, key)
            if found is not None:
                return found
    return None


def _runtime_ref(value: object) -> str | None:
    text = _text(value)
    if text and text.startswith(("cas://", "sha256:", "artifact://", "quality_evidence/")):
        return text
    return None


def _runtime_event_ref(value: object) -> bool:
    text = _text(value)
    return bool(text and text.startswith("event://"))


def _first_runtime_ref(value: object) -> str | None:
    if isinstance(value, str):
        return _runtime_ref(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            ref = _runtime_ref(item)
            if ref is not None:
                return ref
    return None


def _slug(value: object) -> str:
    text = _text(value) or "unknown"
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in text)


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "RUN_COST_GATE_CONTRACT_ID",
    "RUN_COST_GATE_FILENAME",
    "RUN_COST_GATE_REPORT_KEY",
    "RUN_COST_GATE_SCHEMA_VERSION",
    "RunCostGateError",
    "build_run_cost_gate_report",
    "cost_gate_scorecard_gates",
    "validate_run_cost_gate_report",
]
