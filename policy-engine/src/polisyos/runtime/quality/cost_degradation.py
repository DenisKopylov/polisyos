"""Governed run-cost and degradation telemetry for Policy Design Case runs."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

COST_DEGRADATION_TELEMETRY_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.cost_degradation_telemetry.v1"
)
COST_DEGRADATION_TELEMETRY_CONTRACT_ID = (
    "policy_design_case.cost_degradation_telemetry.v1"
)
COST_DEGRADATION_TELEMETRY_REPORT_KEY = "cost_degradation_telemetry"
COST_DEGRADATION_TELEMETRY_FILENAME = "cost_degradation_telemetry.json"

_VALID_METRIC_TYPES = frozenset(
    {
        "provider_call",
        "tokens",
        "provider_cost",
        "search",
        "compute",
        "retry",
        "wall_clock",
        "acquisition",
        "degradation_state",
    }
)
_ATTENTION_STATUSES = frozenset({"warning", "limited", "over_budget", "degraded", "blocked"})
_CLOSEOUT_EFFECTS = frozenset({"observe_only", "warning", "limitation", "blocking"})
_COST_OBSERVATION_TYPES = _VALID_METRIC_TYPES - {"degradation_state"}
_NO_EVIDENCE_QUALITY_EFFECT = frozenset({"", "none", "diagnostic_only"})
_DEFAULT_WARNING_TTL_SECONDS = 7 * 24 * 60 * 60


class CostDegradationTelemetryError(ValueError):
    """Raised when cost/degradation telemetry would violate W2.C governance."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        field: str | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.field = field


def build_cost_degradation_telemetry_from_quality_context(
    *,
    quality_evidence: Mapping[str, Any],
    case: Mapping[str, Any] | None = None,
    job_payload: Mapping[str, Any] | None = None,
    run_payload: Mapping[str, Any] | None = None,
    canary_kind: str | None = None,
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build W2.C advisory telemetry from existing runtime quality context.

    The builder is intentionally telemetry-first: cost, retry, acquisition, and
    degradation rows may expose warning or limitation effects, but they do not
    become closeout blockers unless a row cites an authority-level policy ref.
    """

    case_payload = _mapping(case) or _mapping(quality_evidence.get("policy_design_case"))
    run_id = (
        _text(_nested_get(job_payload, "run_id"))
        or _text(_nested_get(run_payload, "run_id"))
        or _text(case_payload.get("run_id"))
        or _text(case_payload.get("case_run_id"))
        or "unknown-run"
    )
    job_id = (
        _text(_nested_get(job_payload, "job_id"))
        or _text(_nested_get(run_payload, "job_id"))
        or _text(case_payload.get("job_id"))
    )
    source_ref = _runtime_ref(evidence_ref) or _source_ref(
        run_id=run_id,
        slug="cost-degradation-telemetry",
    )
    event_ref = (
        runtime_event_ref
        if _runtime_event_ref(runtime_event_ref)
        else f"event://runtime/cost-degradation/{_slug(run_id)}"
    )

    context = _BuildContext(
        quality_evidence=quality_evidence,
        case=case_payload,
        job_payload=job_payload or {},
        run_payload=run_payload or {},
        run_id=run_id,
        default_evidence_ref=source_ref,
    )
    observations = [
        *_provider_observations(context),
        *_search_observations(context),
        *_compute_observations(context),
        *_retry_observations(context),
        *_wall_clock_observations(context),
        *_acquisition_observations(context),
        *_degradation_observations(context),
    ]
    if not observations:
        observations.append(
            _observation(
                run_id=run_id,
                metric_type="wall_clock",
                producer="runtime.quality.cost_degradation",
                observed_value=0.0,
                unit="second",
                evidence_ref=source_ref,
                index=0,
            )
        )

    payload: dict[str, Any] = {
        "schema_version": COST_DEGRADATION_TELEMETRY_SCHEMA_VERSION,
        "contract_id": COST_DEGRADATION_TELEMETRY_CONTRACT_ID,
        "telemetry_id": f"cost-degradation-telemetry-{_slug(run_id)}",
        "run_id": run_id,
        "authority_profile": _normalized_token(canary_kind or "unknown"),
        "generated_at": _utc(now).isoformat(),
        "observations": observations,
        "evidence_ref": source_ref,
        "runtime_event_ref": event_ref,
        "governance": {
            "posture": "telemetry_first",
            "default_closeout_effect": "observe_only",
            "blocking_requires_authority_policy_ref": True,
            "patterns": ["P09", "P13"],
        },
    }
    if job_id is not None:
        payload["job_id"] = job_id
    return validate_cost_degradation_telemetry(payload)


def validate_cost_degradation_telemetry(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a W2.C cost/degradation telemetry record."""

    if not isinstance(record, Mapping):
        raise CostDegradationTelemetryError(
            "cost_degradation_telemetry_invalid",
            "Cost/degradation telemetry must be a mapping.",
        )
    schema_version = _required_text(
        record.get("schema_version"),
        field="schema_version",
        code="cost_degradation_schema_version_missing",
    )
    if schema_version != COST_DEGRADATION_TELEMETRY_SCHEMA_VERSION:
        raise CostDegradationTelemetryError(
            "cost_degradation_schema_version_invalid",
            "Cost/degradation telemetry must use the W2.C schema version.",
            field="schema_version",
        )
    run_id = _required_text(
        record.get("run_id"),
        field="run_id",
        code="cost_degradation_run_id_missing",
    )
    rows = _rows(record.get("observations"))
    if not rows:
        raise CostDegradationTelemetryError(
            "cost_degradation_observations_missing",
            "Cost/degradation telemetry must include at least one observation.",
            field="observations",
        )

    normalized_rows = [
        _validate_observation(row, index=index, run_id=run_id) for index, row in enumerate(rows)
    ]
    normalized: dict[str, Any] = dict(record)
    normalized["schema_version"] = COST_DEGRADATION_TELEMETRY_SCHEMA_VERSION
    normalized["contract_id"] = (
        _text(record.get("contract_id")) or COST_DEGRADATION_TELEMETRY_CONTRACT_ID
    )
    normalized["telemetry_id"] = _text(record.get("telemetry_id")) or (
        f"cost-degradation-telemetry-{_slug(run_id)}"
    )
    normalized["run_id"] = run_id
    normalized["observations"] = normalized_rows
    normalized["evidence_ref"] = _runtime_ref(record.get("evidence_ref")) or _source_ref(
        run_id=run_id,
        slug="cost-degradation-telemetry",
    )
    event_ref = _text(record.get("runtime_event_ref"))
    normalized["runtime_event_ref"] = (
        event_ref
        if _runtime_event_ref(event_ref)
        else f"event://runtime/cost-degradation/{_slug(run_id)}"
    )
    normalized["summary"] = _summary(normalized_rows)
    governance = dict(record.get("governance") or {})
    governance.setdefault("posture", "telemetry_first")
    governance.setdefault("default_closeout_effect", "observe_only")
    governance.setdefault("blocking_requires_authority_policy_ref", True)
    governance.setdefault("patterns", ["P09", "P13"])
    normalized["governance"] = governance
    return normalized


def cost_degradation_scorecard_gates(
    *,
    quality_evidence: Mapping[str, Any],
    job_payload: Mapping[str, Any] | None = None,
    run_payload: Mapping[str, Any] | None = None,
    canary_kind: str | None = None,
) -> list[dict[str, Any]]:
    """Return scorecard-readable gates for W2.C telemetry.

    Advisory warnings and limitations remain observable inside the telemetry
    artifact. The gate blocks only when the telemetry itself carries an
    authority-policy-backed blocking effect.
    """

    record = quality_evidence.get(COST_DEGRADATION_TELEMETRY_REPORT_KEY)
    try:
        if isinstance(record, Mapping):
            telemetry = validate_cost_degradation_telemetry(record)
        else:
            telemetry = build_cost_degradation_telemetry_from_quality_context(
                quality_evidence=quality_evidence,
                job_payload=job_payload,
                run_payload=run_payload,
                canary_kind=canary_kind,
            )
    except CostDegradationTelemetryError as exc:
        return [
            _gate(
                status="fail",
                blocking=True,
                code=exc.code,
                message=str(exc),
                evidence_ref="quality_evidence/cost_degradation_telemetry.json",
                closeout_effect="blocking",
                missing_input=exc.field or COST_DEGRADATION_TELEMETRY_REPORT_KEY,
            )
        ]

    summary = dict(telemetry["summary"])
    blocking = int(summary.get("blocking_count") or 0) > 0
    return [
        _gate(
            status="fail" if blocking else "pass",
            blocking=blocking,
            code=(
                "cost_degradation_authority_policy_blocking"
                if blocking
                else "cost_degradation_telemetry_observed"
            ),
            message=(
                "Cost/degradation telemetry contains an authority-policy-backed blocker."
                if blocking
                else "Cost/degradation telemetry is observable and advisory."
            ),
            evidence_ref=_text(telemetry.get("evidence_ref"))
            or "quality_evidence/cost_degradation_telemetry.json",
            closeout_effect="blocking" if blocking else "observe_only",
            warning_count=int(summary.get("warning_count") or 0),
            limitation_count=int(summary.get("limitation_count") or 0),
            blocking_count=int(summary.get("blocking_count") or 0),
        )
    ]


class _BuildContext:
    def __init__(
        self,
        *,
        quality_evidence: Mapping[str, Any],
        case: Mapping[str, Any],
        job_payload: Mapping[str, Any],
        run_payload: Mapping[str, Any],
        run_id: str,
        default_evidence_ref: str,
    ) -> None:
        self.quality_evidence = quality_evidence
        self.case = case
        self.job_payload = job_payload
        self.run_payload = run_payload
        self.run_id = run_id
        self.default_evidence_ref = default_evidence_ref


def _provider_observations(context: _BuildContext) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, entry in enumerate(_provider_entries(context)):
        metrics = _mapping(entry.get("metrics")) or _mapping(entry.get("usage")) or entry
        provider = _text(entry.get("provider") or entry.get("provider_id")) or "unknown_provider"
        model = _text(entry.get("model_id") or entry.get("model")) or "unknown_model"
        producer = f"provider.{_slug(provider)}.{_slug(model)}"
        evidence_ref = _source_ref_from_mapping(entry) or _source_ref_from_mapping(metrics)
        evidence_ref = evidence_ref or context.default_evidence_ref

        call_count = _first_number(
            metrics,
            ("provider_call_count", "call_count", "request_count", "requests"),
        )
        if call_count is None and (provider != "unknown_provider" or model != "unknown_model"):
            call_count = 1.0
        if call_count and call_count > 0:
            rows.append(
                _observation(
                    run_id=context.run_id,
                    metric_type="provider_call",
                    producer=producer,
                    observed_value=call_count,
                    unit="call",
                    evidence_ref=evidence_ref,
                    index=index,
                )
            )

        input_tokens = _first_number(metrics, ("input_tokens", "prompt_tokens"))
        output_tokens = _first_number(metrics, ("output_tokens", "completion_tokens"))
        token_total = _first_number(metrics, ("total_tokens", "tokens"))
        if token_total is None:
            token_total = (input_tokens or 0.0) + (output_tokens or 0.0)
        if token_total and token_total > 0:
            row = _observation(
                run_id=context.run_id,
                metric_type="tokens",
                producer=producer,
                observed_value=token_total,
                unit="token",
                evidence_ref=evidence_ref,
                index=index,
            )
            if input_tokens is not None:
                row["input_tokens"] = input_tokens
            if output_tokens is not None:
                row["output_tokens"] = output_tokens
            rows.append(row)

        cost_usd = _first_number(
            metrics,
            ("cost_usd_total", "total_cost_usd", "actual_cost_usd", "cost_usd"),
        ) or _first_number(entry, ("cost_usd", "actual_cost_usd"))
        if cost_usd and cost_usd > 0:
            rows.append(
                _observation(
                    run_id=context.run_id,
                    metric_type="provider_cost",
                    producer=producer,
                    observed_value=cost_usd,
                    unit="usd",
                    evidence_ref=evidence_ref,
                    index=index,
                )
            )
    return rows


def _search_observations(context: _BuildContext) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    search_records = [
        *_rows(context.case.get("search_budget_records")),
        *_rows(context.case.get("doe_search_budget_records")),
        *_rows(context.case.get("search_records")),
    ]
    for index, record in enumerate(search_records):
        count = (
            _first_number(record, ("query_count", "search_count", "request_count"))
            or float(len(_rows(record.get("queries"))))
            or 1.0
        )
        rows.append(
            _observation(
                run_id=context.run_id,
                metric_type="search",
                producer=_text(record.get("producer")) or "policy_design.search",
                observed_value=count,
                unit="query",
                evidence_ref=_source_ref_from_mapping(record) or context.default_evidence_ref,
                status=record.get("status"),
                index=index,
            )
        )
    return rows


def _compute_observations(context: _BuildContext) -> list[dict[str, Any]]:
    report = _mapping(context.quality_evidence.get("foundry_method_report"))
    rows: list[dict[str, Any]] = []
    if not report:
        return rows
    for index, method in enumerate(_rows(report.get("selected_methods") or report.get("methods"))):
        seconds = _first_number(
            method,
            ("compute_seconds", "runtime_seconds", "execution_seconds"),
        )
        cost = _first_number(
            method,
            ("compute_cost_usd", "estimated_cost_usd", "actual_cost_usd", "cost_usd"),
        )
        if seconds is None and cost is None:
            continue
        rows.append(
            _observation(
                run_id=context.run_id,
                metric_type="compute",
                producer=_text(method.get("method_id")) or "foundry.method",
                observed_value=seconds if seconds is not None else cost or 0.0,
                unit="second" if seconds is not None else "usd",
                evidence_ref=_source_ref_from_mapping(method)
                or _source_ref_from_mapping(report)
                or context.default_evidence_ref,
                index=index,
            )
        )
    return rows


def _retry_observations(context: _BuildContext) -> list[dict[str, Any]]:
    retry_stats = _mapping(_nested_get(context.job_payload, "retry_stats")) or _mapping(
        _nested_get(context.run_payload, "retry_stats")
    )
    if not retry_stats:
        return []
    retries = _first_number(retry_stats, ("retries", "retry_count", "retry_attempts"))
    attempts = _first_number(retry_stats, ("attempts", "attempt_count"))
    if retries is None and attempts is not None:
        retries = max(0.0, attempts - 1.0)
    if retries is None:
        return []
    return [
        _observation(
            run_id=context.run_id,
            metric_type="retry",
            producer=_text(retry_stats.get("producer")) or "runtime.retry",
            observed_value=retries,
            unit="retry",
            evidence_ref=_source_ref_from_mapping(retry_stats) or context.default_evidence_ref,
            index=0,
        )
    ]


def _wall_clock_observations(context: _BuildContext) -> list[dict[str, Any]]:
    submitted = _timestamp(
        context.job_payload.get("submitted_at")
        or context.job_payload.get("created_at")
        or context.job_payload.get("queued_at")
    )
    finished = _timestamp(
        context.job_payload.get("finished_at")
        or context.job_payload.get("completed_at")
        or context.job_payload.get("ended_at")
    )
    seconds = None
    if submitted is not None and finished is not None:
        seconds = max(0.0, (finished - submitted).total_seconds())
    performance = _mapping(
        _nested_get(context.job_payload, "canary_performance_budget")
    ) or _mapping(_nested_get(context.run_payload, "canary_performance_budget"))
    if seconds is None and performance:
        actual_ms = sum(
            _first_number(
                row,
                ("observed_duration_ms", "duration_ms", "elapsed_ms", "latency_ms"),
            )
            or 0.0
            for row in _rows(performance.get("phase_budgets"))
        )
        if actual_ms > 0:
            seconds = actual_ms / 1000.0
    if seconds is None:
        return []
    return [
        _observation(
            run_id=context.run_id,
            metric_type="wall_clock",
            producer="runtime.control",
            observed_value=seconds,
            unit="second",
            evidence_ref=_source_ref_from_mapping(performance) or context.default_evidence_ref,
            index=0,
        )
    ]


def _acquisition_observations(context: _BuildContext) -> list[dict[str, Any]]:
    records = [
        *_rows(context.case.get("acquisition_records")),
        *_rows(context.case.get("evidence_acquisition_records")),
        *_rows(context.case.get("acquisition_plans")),
    ]
    rows: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        status = _status(record.get("status") or record.get("decision"))
        value = _first_number(record, ("actual_cost_usd", "estimated_cost_usd", "cost_usd")) or 1.0
        rows.append(
            _observation(
                run_id=context.run_id,
                metric_type="acquisition",
                producer=_text(record.get("producer")) or "policy_design.acquisition",
                observed_value=value,
                unit="usd" if value != 1.0 else "record",
                evidence_ref=_source_ref_from_mapping(record) or context.default_evidence_ref,
                status=status,
                closeout_effect="limitation" if status == "limited" else None,
                owner=_text(record.get("owner")) or "team-policyos-runtime",
                ttl_seconds=_first_number(record, ("ttl_seconds",)) or _DEFAULT_WARNING_TTL_SECONDS,
                next_action=(
                    _text(record.get("next_action"))
                    or (
                        "Review acquisition limitation before promotion to a stronger "
                        "authority lane."
                    )
                ),
                index=index,
            )
        )
    return rows


def _degradation_observations(context: _BuildContext) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, record in enumerate(_iter_degradation_records(context.quality_evidence)):
        blocking_status = _normalized_token(record.get("blocking_status"))
        status = "blocked" if blocking_status in {"blocked", "blocking"} else "degraded"
        severity = _normalized_token(record.get("severity"))
        effect = "limitation" if severity in {"high", "critical"} else "warning"
        if status == "blocked":
            effect = "blocking"
        rows.append(
            _observation(
                run_id=context.run_id,
                metric_type="degradation_state",
                producer=_text(record.get("component")) or "runtime.degradation",
                observed_value=1.0,
                unit="state",
                evidence_ref=_source_ref_from_mapping(record)
                or _first_runtime_ref(_rows(record.get("provenance_refs")))
                or context.default_evidence_ref,
                status=status,
                closeout_effect=effect,
                owner=_text(record.get("owner")) or "team-runtime-quality",
                ttl_seconds=_first_number(record, ("ttl_seconds",)) or _DEFAULT_WARNING_TTL_SECONDS,
                next_action=(
                    _text(record.get("next_action") or record.get("next_diagnostic_command"))
                    or "Inspect degradation lifecycle before increasing authority."
                ),
                authority_policy_ref=_text(record.get("authority_policy_ref")),
                index=index,
            )
        )
    return rows


def _provider_entries(context: _BuildContext) -> list[Mapping[str, Any]]:
    entries: list[Mapping[str, Any]] = []
    ledger = _mapping(context.quality_evidence.get("provider_model_quality_ledger"))
    if ledger:
        entries.extend(_rows(ledger.get("entries") or ledger.get("providers")))
    for payload in (context.job_payload, context.run_payload, context.quality_evidence):
        entries.extend(_rows(_nested_get(payload, "llm_model_variants")))
    return entries


def _iter_degradation_records(payload: object) -> Iterable[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_text = str(key)
            if key_text in {"degradation_record", "degradation_ledger"} and isinstance(
                value,
                Mapping,
            ):
                yield value
                continue
            if key_text in {"degradation_records", "degradation_ledgers"}:
                yield from _rows(value)
                continue
            yield from _iter_degradation_records(value)
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        for item in payload:
            yield from _iter_degradation_records(item)


def _validate_observation(row: Mapping[str, Any], *, index: int, run_id: str) -> dict[str, Any]:
    metric_type = _normalized_token(
        _required_text(
            row.get("metric_type"),
            field=f"observations[{index}].metric_type",
            code="cost_degradation_metric_type_missing",
        )
    )
    if metric_type not in _VALID_METRIC_TYPES:
        raise CostDegradationTelemetryError(
            "cost_degradation_metric_type_invalid",
            f"Unsupported cost/degradation metric_type: {metric_type}.",
            field=f"observations[{index}].metric_type",
        )
    observed_value = _required_number(
        row.get("observed_value"),
        field=f"observations[{index}].observed_value",
        code="cost_degradation_observed_value_missing",
    )
    status = _status(row.get("status"))
    effect = _closeout_effect(row.get("closeout_effect"), status=status)
    evidence_quality_effect = _normalized_token(row.get("evidence_quality_effect") or "none")
    if evidence_quality_effect not in _NO_EVIDENCE_QUALITY_EFFECT:
        raise CostDegradationTelemetryError(
            "cost_degradation_evidence_quality_effect_invalid",
            "Cost/degradation telemetry may not silently downgrade evidence quality.",
            field=f"observations[{index}].evidence_quality_effect",
        )

    normalized = dict(row)
    normalized["metric_id"] = _text(row.get("metric_id")) or (
        f"{_slug(run_id)}.{metric_type}.{index}"
    )
    normalized["metric_type"] = metric_type
    normalized["producer"] = _required_text(
        row.get("producer"),
        field=f"observations[{index}].producer",
        code="cost_degradation_producer_missing",
    )
    normalized["observed_value"] = observed_value
    normalized["unit"] = _required_text(
        row.get("unit"),
        field=f"observations[{index}].unit",
        code="cost_degradation_unit_missing",
    )
    normalized["status"] = status
    normalized["closeout_effect"] = effect
    normalized["evidence_quality_effect"] = evidence_quality_effect or "none"
    normalized["evidence_ref"] = _runtime_ref(row.get("evidence_ref")) or _source_ref(
        run_id=run_id,
        slug=f"{metric_type}-{index}",
    )

    if effect in {"warning", "limitation", "blocking"} or status in _ATTENTION_STATUSES:
        normalized["owner"] = _required_text(
            row.get("owner"),
            field=f"observations[{index}].owner",
            code="cost_degradation_warning_owner_missing",
        )
        normalized["ttl_seconds"] = _required_number(
            row.get("ttl_seconds"),
            field=f"observations[{index}].ttl_seconds",
            code="cost_degradation_warning_ttl_missing",
        )
        normalized["next_action"] = _required_text(
            row.get("next_action"),
            field=f"observations[{index}].next_action",
            code="cost_degradation_warning_next_action_missing",
        )

    if effect == "blocking" or bool(row.get("may_block_closeout")):
        policy_ref = _text(row.get("authority_policy_ref"))
        if not policy_ref:
            raise CostDegradationTelemetryError(
                "cost_degradation_blocking_policy_ref_missing",
                (
                    "Cost/degradation telemetry can block only when an "
                    "authority-level policy ref is present."
                ),
                field=f"observations[{index}].authority_policy_ref",
            )
        normalized["authority_policy_ref"] = policy_ref
        normalized["may_block_closeout"] = True
    else:
        normalized["may_block_closeout"] = False
    if metric_type in _COST_OBSERVATION_TYPES:
        normalized["evidence_quality_effect"] = "none"
    return normalized


def _observation(
    *,
    run_id: str,
    metric_type: str,
    producer: str,
    observed_value: float,
    unit: str,
    evidence_ref: str,
    index: int,
    status: object = "pass",
    closeout_effect: str | None = None,
    owner: str | None = None,
    ttl_seconds: float | int | None = None,
    next_action: str | None = None,
    authority_policy_ref: str | None = None,
) -> dict[str, Any]:
    normalized_status = _status(status)
    effect = _closeout_effect(closeout_effect, status=normalized_status)
    row: dict[str, Any] = {
        "metric_id": f"{_slug(run_id)}.{metric_type}.{index}",
        "metric_type": metric_type,
        "producer": producer,
        "observed_value": float(observed_value),
        "unit": unit,
        "status": normalized_status,
        "closeout_effect": effect,
        "evidence_ref": evidence_ref,
        "evidence_quality_effect": "none",
    }
    if effect in {"warning", "limitation", "blocking"} or normalized_status in _ATTENTION_STATUSES:
        row["owner"] = owner or "team-runtime-quality"
        row["ttl_seconds"] = int(ttl_seconds or _DEFAULT_WARNING_TTL_SECONDS)
        row["next_action"] = next_action or "Review cost/degradation telemetry before promotion."
    if authority_policy_ref:
        row["authority_policy_ref"] = authority_policy_ref
    return row


def _summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "observation_count": len(rows),
        "provider_call_count": int(
            sum(row["observed_value"] for row in rows if row["metric_type"] == "provider_call")
        ),
        "token_count": int(
            sum(row["observed_value"] for row in rows if row["metric_type"] == "tokens")
        ),
        "total_cost_usd": round(
            sum(
                float(row["observed_value"])
                for row in rows
                if row["unit"] == "usd" or row["metric_type"] == "provider_cost"
            ),
            6,
        ),
        "search_query_count": int(
            sum(row["observed_value"] for row in rows if row["metric_type"] == "search")
        ),
        "compute_seconds": round(
            sum(
                float(row["observed_value"])
                for row in rows
                if row["metric_type"] == "compute" and row["unit"] == "second"
            ),
            6,
        ),
        "retry_count": int(
            sum(row["observed_value"] for row in rows if row["metric_type"] == "retry")
        ),
        "wall_clock_seconds": round(
            sum(
                float(row["observed_value"])
                for row in rows
                if row["metric_type"] == "wall_clock" and row["unit"] == "second"
            ),
            6,
        ),
        "acquisition_count": sum(1 for row in rows if row["metric_type"] == "acquisition"),
        "degradation_state_count": sum(
            1 for row in rows if row["metric_type"] == "degradation_state"
        ),
        "warning_count": sum(1 for row in rows if row["closeout_effect"] == "warning"),
        "limitation_count": sum(1 for row in rows if row["closeout_effect"] == "limitation"),
        "blocking_count": sum(1 for row in rows if row["closeout_effect"] == "blocking"),
        "posture": "telemetry_first",
    }


def _gate(
    *,
    status: str,
    blocking: bool,
    code: str,
    message: str,
    evidence_ref: str,
    closeout_effect: str,
    missing_input: str | None = None,
    warning_count: int | None = None,
    limitation_count: int | None = None,
    blocking_count: int | None = None,
) -> dict[str, Any]:
    gate = {
        "name": "policy_design_w2c_cost_degradation_telemetry",
        "stage": "ops",
        "code": code,
        "status": status,
        "layer": "runtime_cost_degradation",
        "phase": "policy_design_w2c_cost_degradation",
        "message": message,
        "evidence_ref": evidence_ref,
        "next_action": (
            "Inspect quality_evidence/cost_degradation_telemetry.json; promote "
            "blocking behavior only through authority-level policy."
        ),
        "blocking": blocking,
        "owner": "team-runtime-quality",
        "closeout_effect": closeout_effect,
    }
    for key, value in (
        ("missing_input", missing_input),
        ("warning_count", warning_count),
        ("limitation_count", limitation_count),
        ("blocking_count", blocking_count),
    ):
        if value is not None:
            gate[key] = value
    return gate


def _rows(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _required_text(value: object, *, field: str, code: str) -> str:
    text = _text(value)
    if text is None:
        raise CostDegradationTelemetryError(
            code,
            f"Cost/degradation telemetry is missing {field}.",
            field=field,
        )
    return text


def _required_number(value: object, *, field: str, code: str) -> float:
    number = _number(value)
    if number is None:
        raise CostDegradationTelemetryError(
            code,
            f"Cost/degradation telemetry is missing numeric {field}.",
            field=field,
        )
    return number


def _first_number(payload: object, keys: Sequence[str]) -> float | None:
    if not isinstance(payload, Mapping):
        return None
    for key in keys:
        number = _number(payload.get(key))
        if number is not None:
            return number
    return None


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


def _status(value: object) -> str:
    token = _normalized_token(value or "pass")
    if token in {"ok", "passed", "success", "succeeded"}:
        return "pass"
    if token in {"warn", "warning"}:
        return "warning"
    if token in {"limit", "limited", "partial"}:
        return "limited"
    if token in {"block", "blocked", "blocking", "fail", "failed"}:
        return "blocked"
    if token in {"degrade", "degraded", "degradation"}:
        return "degraded"
    if token in {"over_budget", "budget_exceeded"}:
        return "over_budget"
    return token or "pass"


def _closeout_effect(value: object, *, status: str) -> str:
    token = _normalized_token(value)
    if not token:
        if status == "blocked":
            return "blocking"
        if status in {"limited", "over_budget"}:
            return "limitation"
        if status in {"warning", "degraded"}:
            return "warning"
        return "observe_only"
    if token in {"none", "observe", "observed", "advisory", "diagnostic"}:
        return "observe_only"
    if token in {"warn", "warning"}:
        return "warning"
    if token in {"limit", "limited", "limitation"}:
        return "limitation"
    if token in {"block", "blocked", "blocking"}:
        return "blocking"
    if token not in _CLOSEOUT_EFFECTS:
        raise CostDegradationTelemetryError(
            "cost_degradation_closeout_effect_invalid",
            f"Unsupported cost/degradation closeout effect: {token}.",
            field="closeout_effect",
        )
    return token


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


def _source_ref_from_mapping(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    for key in (
        "evidence_ref",
        "cas_ref",
        "artifact_ref",
        "runtime_ref",
        "provider_model_quality_ledger_ref",
        "foundry_method_report_ref",
        "cost_evidence_ref",
    ):
        ref = _runtime_ref(value.get(key))
        if ref is not None:
            return ref
    return None


def _first_runtime_ref(values: Sequence[Mapping[str, Any]]) -> str | None:
    for value in values:
        ref = _runtime_ref(value)
        if ref is not None:
            return ref
    return None


def _runtime_ref(value: object) -> str | None:
    text = _text(value)
    if text and text.startswith(("cas://", "sha256:", "artifact://", "quality_evidence/")):
        return text
    return None


def _runtime_event_ref(value: object) -> bool:
    text = _text(value)
    return bool(text and text.startswith("event://"))


def _source_ref(*, run_id: str, slug: str) -> str:
    return f"artifact://runtime-quality/cost-degradation/{_slug(run_id)}/{_slug(slug)}"


def _timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _utc(value)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalized_token(value: object) -> str:
    return str(value or "").strip().replace("-", "_").casefold()


def _slug(value: object) -> str:
    token = _normalized_token(value)
    return "".join(char if char.isalnum() else "_" for char in token).strip("_") or "unknown"


__all__ = [
    "COST_DEGRADATION_TELEMETRY_CONTRACT_ID",
    "COST_DEGRADATION_TELEMETRY_FILENAME",
    "COST_DEGRADATION_TELEMETRY_REPORT_KEY",
    "COST_DEGRADATION_TELEMETRY_SCHEMA_VERSION",
    "CostDegradationTelemetryError",
    "build_cost_degradation_telemetry_from_quality_context",
    "cost_degradation_scorecard_gates",
    "validate_cost_degradation_telemetry",
]
