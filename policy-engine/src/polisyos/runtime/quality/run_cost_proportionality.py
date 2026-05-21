"""Run-cost proportionality ledger contracts for Policy Design Case closeout."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

RUN_COST_PROPORTIONALITY_LEDGER_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.run_cost_proportionality_ledger.v1"
)
RUN_COST_PROPORTIONALITY_LEDGER_CONTRACT_ID = (
    "policy_design_case.run_cost_proportionality_ledger.v1"
)

HIGH_COST_LOW_IMPACT_COST_USD = 100.0
HIGH_COST_LOW_IMPACT_ELAPSED_SECONDS = 2 * 60 * 60
HIGH_COST_LOW_IMPACT_REVIEW_HOURS = 2.0
_AUTHORITY_LABEL_KEYS = (
    "authority_level",
    "requested_authority_level",
    "authority_profile",
    "effective_execution_profile",
    "execution_profile",
    "profile",
    "validation_profile",
)
_PUBLIC_IMPACT_LABEL_KEYS = (
    "public_impact",
    "public_impact_class",
    "impact_level",
    "risk_level",
)


@dataclass(frozen=True)
class RunCostProportionalityError(ValueError):
    """Fail-closed run-cost proportionality contract violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def validate_run_cost_proportionality_ledger(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and normalize a run-cost proportionality case record."""

    if not isinstance(record, Mapping):
        raise RunCostProportionalityError(
            "policy_design_run_cost_ledger_invalid",
            "Run-cost proportionality ledger must be a mapping.",
        )

    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_run_cost_schema_version_missing",
    )
    if schema_version != RUN_COST_PROPORTIONALITY_LEDGER_SCHEMA_VERSION:
        raise RunCostProportionalityError(
            "policy_design_run_cost_schema_version_invalid",
            "Run-cost proportionality ledger must use the Wave 30 schema version.",
            "schema_version",
        )

    normalized["schema_version"] = RUN_COST_PROPORTIONALITY_LEDGER_SCHEMA_VERSION
    normalized["contract_id"] = (
        _text(record.get("contract_id")) or RUN_COST_PROPORTIONALITY_LEDGER_CONTRACT_ID
    )
    normalized["ledger_id"] = run_cost_ledger_record_id(record)
    normalized["run_id"] = _required_text(
        record.get("run_id"),
        "run_id",
        "policy_design_run_cost_run_id_missing",
    )
    if _text(record.get("job_id")):
        normalized["job_id"] = str(record["job_id"])

    authority_level = _required_normalized_label_from_values(
        (record.get("authority_level"), record.get("authority_profile")),
        keys=_AUTHORITY_LABEL_KEYS,
        field="authority_level",
        code="policy_design_run_cost_authority_level_missing",
    )
    public_impact = _required_normalized_label_from_values(
        (record.get("public_impact"), record.get("public_impact_class")),
        keys=_PUBLIC_IMPACT_LABEL_KEYS,
        field="public_impact",
        code="policy_design_run_cost_public_impact_missing",
    )
    normalized["authority_level"] = authority_level
    normalized["public_impact"] = public_impact

    total_actual_cost_usd = 0.0
    total_budget_usd = 0.0
    for field, code in _COMPONENT_FIELDS.items():
        component = _validate_cost_component(record.get(field), field=field, code=code)
        normalized[field] = component
        total_actual_cost_usd += _component_cost_usd(component)
        total_budget_usd += _component_budget_usd(component)

    explicit_total = _optional_float(record.get("total_actual_cost_usd"))
    if explicit_total is not None:
        total_actual_cost_usd = explicit_total
    explicit_budget = _optional_float(record.get("total_budget_usd"))
    if explicit_budget is not None:
        total_budget_usd = explicit_budget
    normalized["total_actual_cost_usd"] = total_actual_cost_usd
    normalized["total_budget_usd"] = total_budget_usd
    normalized["elapsed_seconds"] = _component_seconds(normalized["elapsed_time_budget"])
    normalized["human_review_hours"] = _component_hours(normalized["human_review_burden"])

    blockers = tuple(_valid_blockers_from_record(record))
    normalized["blockers"] = [dict(blocker) for blocker in blockers]
    normalized["evidence_depth_budget"] = _validate_evidence_depth_budget(
        record.get("evidence_depth_budget"),
        authority_level=authority_level,
        public_impact=public_impact,
        typed_blockers=blockers,
    )

    proportionality = _validate_optional_proportionality_evidence(
        record.get("proportionality_evidence")
        or record.get("proportionality_record")
        or record.get("proportionality"),
    )
    if proportionality is not None:
        normalized["proportionality_evidence"] = proportionality

    if (
        _is_low_impact(public_impact)
        and _high_cost_low_impact_threshold_exceeded(
            total_actual_cost_usd=total_actual_cost_usd,
            elapsed_seconds=normalized["elapsed_seconds"],
            human_review_hours=normalized["human_review_hours"],
        )
        and proportionality is None
        and not blockers
    ):
        raise RunCostProportionalityError(
            "policy_design_run_cost_high_cost_low_impact_without_proportionality",
            (
                "High-cost low-impact runs must preserve proportionality evidence "
                "or emit a typed run-cost blocker."
            ),
            "proportionality_evidence",
        )

    if (
        total_budget_usd > 0
        and total_actual_cost_usd > total_budget_usd * 1.1
        and not _has_accepted_budget_change(record)
        and not blockers
    ):
        raise RunCostProportionalityError(
            "policy_design_run_cost_budget_overrun_change_record_missing",
            "Spending beyond budget must cite an accepted runtime budget-change record.",
            "budget_change_records",
        )

    evidence_ref = _required_text(
        record.get("evidence_ref") or record.get("cas_ref"),
        "evidence_ref",
        "policy_design_run_cost_evidence_ref_missing",
    )
    if not _runtime_artifact_ref(evidence_ref):
        raise RunCostProportionalityError(
            "policy_design_run_cost_evidence_ref_invalid",
            "Run-cost ledger evidence_ref must be a runtime artifact ref.",
            "evidence_ref",
        )
    normalized["evidence_ref"] = evidence_ref

    runtime_event_ref = _required_text(
        record.get("runtime_event_ref"),
        "runtime_event_ref",
        "policy_design_run_cost_runtime_event_ref_missing",
    )
    if not _runtime_event_ref(runtime_event_ref):
        raise RunCostProportionalityError(
            "policy_design_run_cost_runtime_event_ref_invalid",
            "Run-cost ledger must cite a runtime event ref.",
            "runtime_event_ref",
        )
    normalized["runtime_event_ref"] = runtime_event_ref
    return normalized


def run_cost_ledger_record_id(record: Mapping[str, Any]) -> str:
    """Return the stable identity for a run-cost proportionality ledger."""

    return _required_text(
        record.get("ledger_id")
        or record.get("run_cost_ledger_id")
        or record.get("record_id")
        or record.get("id"),
        "ledger_id",
        "policy_design_run_cost_ledger_id_missing",
    )


def validate_run_cost_proportionality_blocker(
    blocker: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a typed blocker that stands in for a missing run-cost ledger."""

    if not isinstance(blocker, Mapping):
        raise RunCostProportionalityError(
            "policy_design_run_cost_blocker_invalid",
            "Run-cost proportionality blocker must be a mapping.",
            "blockers",
        )
    row = dict(blocker)
    if _normalized_label(row.get("status") or row.get("decision")) != "blocked":
        raise RunCostProportionalityError(
            "policy_design_run_cost_blocker_status_invalid",
            "Run-cost proportionality blockers must have blocked status.",
            "blockers.status",
        )
    row["code"] = _required_text(
        row.get("code"),
        "code",
        "policy_design_run_cost_blocker_code_missing",
    )
    row["message"] = _required_text(
        row.get("message") or row.get("downstream_impact"),
        "message",
        "policy_design_run_cost_blocker_message_missing",
    )
    evidence_ref = _required_text(
        row.get("evidence_ref") or row.get("cas_ref"),
        "evidence_ref",
        "policy_design_run_cost_blocker_evidence_ref_missing",
    )
    if not _runtime_artifact_ref(evidence_ref):
        raise RunCostProportionalityError(
            "policy_design_run_cost_blocker_evidence_ref_invalid",
            "Run-cost proportionality blockers must cite runtime artifact refs.",
            "blockers.evidence_ref",
        )
    row["evidence_ref"] = evidence_ref
    runtime_event_ref = _required_text(
        row.get("runtime_event_ref"),
        "runtime_event_ref",
        "policy_design_run_cost_blocker_runtime_event_ref_missing",
    )
    if not _runtime_event_ref(runtime_event_ref):
        raise RunCostProportionalityError(
            "policy_design_run_cost_blocker_runtime_event_ref_invalid",
            "Run-cost proportionality blockers must cite runtime event refs.",
            "blockers.runtime_event_ref",
        )
    row["runtime_event_ref"] = runtime_event_ref
    return row


def build_run_cost_proportionality_ledger_from_quality_context(
    *,
    quality_evidence: Mapping[str, Any],
    case: Mapping[str, Any] | None = None,
    job_payload: Mapping[str, Any] | None = None,
    run_payload: Mapping[str, Any] | None = None,
    canary_kind: str | None = None,
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
) -> dict[str, Any]:
    """Project Wave 30 run-cost ledger evidence from runtime quality context."""

    case_payload = case if isinstance(case, Mapping) else quality_evidence.get(
        "policy_design_case"
    )
    if not isinstance(case_payload, Mapping):
        raise RunCostProportionalityError(
            "policy_design_run_cost_case_missing",
            "Run-cost projection requires a Policy Design Case payload.",
            "policy_design_case",
        )

    refs = _runtime_refs_from_quality_context(
        quality_evidence=quality_evidence,
        case=case_payload,
        job_payload=job_payload,
        run_payload=run_payload,
    )
    run_id = _text(
        _nested_get(job_payload, "run_id")
        or _nested_get(run_payload, "run_id")
        or case_payload.get("run_id")
        or case_payload.get("case_run_id")
    )
    if run_id is None:
        raise RunCostProportionalityError(
            "policy_design_run_cost_source_run_id_missing",
            "Run-cost projection requires a runtime run_id.",
            "run_id",
        )
    job_id = _text(
        _nested_get(job_payload, "job_id")
        or _nested_get(run_payload, "job_id")
        or case_payload.get("job_id")
    )

    authority_level = _first_normalized_label_from_values(
        (
            case_payload.get("authority_level"),
            case_payload.get("authority_profile"),
            case_payload.get("effective_execution_profile"),
            case_payload.get("profile_metadata"),
            case_payload.get("profile"),
            canary_kind,
            "research",
        ),
        keys=_AUTHORITY_LABEL_KEYS,
    )
    public_impact = _first_normalized_label_from_values(
        (
            case_payload.get("public_impact"),
            case_payload.get("public_impact_class"),
            _nested_get(case_payload, "public_impact"),
            _default_public_impact(authority_level, canary_kind),
        ),
        keys=_PUBLIC_IMPACT_LABEL_KEYS,
    )

    performance_budget = _performance_budget_from_context(
        quality_evidence=quality_evidence,
        job_payload=job_payload,
        run_payload=run_payload,
    )
    performance_ref = _source_ref(
        refs,
        ("performance_budget_ref", "canary_performance_budget_ref", "quality_report_ref"),
        run_id=run_id,
        slug="performance-budget",
    )
    foundry_ref = _source_ref(
        refs,
        ("foundry_method_report_ref",),
        run_id=run_id,
        slug="foundry-method-report",
    )
    scientist_ref = _source_ref(
        refs,
        ("policy_design_case_ref", "quality_report_ref"),
        run_id=run_id,
        slug="scientist-budget",
    )
    doe_ref = _source_ref(
        refs,
        ("policy_design_case_ref", "fabric_retrieval_trace_ref"),
        run_id=run_id,
        slug="doe-search-budget",
    )
    provider_ref = _source_ref(
        refs,
        ("provider_model_quality_ledger_ref",),
        run_id=run_id,
        slug="provider-model-quality-ledger",
    )
    human_review_ref = _source_ref(
        refs,
        ("human_review_calibration_report_ref",),
        run_id=run_id,
        slug="human-review-calibration",
    )
    case_ref = _source_ref(
        refs,
        ("policy_design_case_ref", "quality_scorecard_ref", "quality_report_ref"),
        run_id=run_id,
        slug="policy-design-case",
    )

    synthesis = _best_synthesis_report(case_payload)
    synthesis_run_cost = _mapping(synthesis.get("run_cost_proportionality"))
    foundry_cost = _foundry_cost_usd(quality_evidence)
    provider_cost = _provider_cost_usd(
        quality_evidence=quality_evidence,
        job_payload=job_payload,
        run_payload=run_payload,
    )
    scientist_budget = _scientist_budget_component(
        case_payload,
        synthesis_run_cost=synthesis_run_cost,
        evidence_ref=scientist_ref,
    )
    doe_budget = _doe_search_budget_component(case_payload, evidence_ref=doe_ref)

    ledger: dict[str, Any] = {
        "schema_version": RUN_COST_PROPORTIONALITY_LEDGER_SCHEMA_VERSION,
        "contract_id": RUN_COST_PROPORTIONALITY_LEDGER_CONTRACT_ID,
        "ledger_id": f"run-cost-ledger-{run_id}",
        "run_id": run_id,
        "authority_level": authority_level,
        "public_impact": public_impact,
        "runtime_performance_budget": {
            "actual_cost_usd": _first_number(performance_budget, ("actual_cost_usd",))
            or 0.0,
            "budget_usd": _first_number(performance_budget, ("budget_usd",)) or 0.0,
            "actual_duration_ms": _performance_actual_ms(performance_budget),
            "budget_duration_ms": _performance_budget_ms(performance_budget),
            "evidence_ref": performance_ref,
        },
        "foundry_cost_model": {
            "actual_cost_usd": foundry_cost,
            "budget_usd": _report_budget_usd(
                quality_evidence.get("foundry_method_report")
            ),
            "evidence_ref": foundry_ref,
        },
        "scientist_budget": scientist_budget,
        "doe_search_budget": doe_budget,
        "provider_cost": {
            "actual_cost_usd": provider_cost,
            "budget_usd": _provider_budget_usd(
                quality_evidence=quality_evidence,
                job_payload=job_payload,
                run_payload=run_payload,
            ),
            "evidence_ref": provider_ref,
        },
        "elapsed_time_budget": {
            "actual_seconds": _elapsed_seconds(
                performance_budget=performance_budget,
                job_payload=job_payload,
                run_payload=run_payload,
            ),
            "budget_seconds": _performance_budget_ms(performance_budget) / 1000.0,
            "evidence_ref": performance_ref,
        },
        "human_review_burden": _human_review_burden_component(
            quality_evidence,
            evidence_ref=human_review_ref,
        ),
        "evidence_depth_budget": _evidence_depth_budget(
            case_payload,
            quality_evidence=quality_evidence,
            synthesis=synthesis,
            authority_level=authority_level,
            public_impact=public_impact,
            stopping_ref=_source_ref_from_mapping(synthesis_run_cost)
            or _source_ref_from_mapping(synthesis)
            or case_ref,
        ),
        "budget_change_records": list(_budget_change_records(case_payload)),
        "evidence_ref": evidence_ref
        if evidence_ref and _runtime_artifact_ref(evidence_ref)
        else case_ref,
        "runtime_event_ref": runtime_event_ref
        if runtime_event_ref and _runtime_event_ref(runtime_event_ref)
        else f"event://runtime/run-cost/{run_id}",
    }
    if job_id is not None:
        ledger["job_id"] = job_id

    proportionality = _proportionality_evidence_from_synthesis(
        synthesis_run_cost,
        fallback_ref=case_ref,
    )
    if proportionality is not None:
        ledger["proportionality_evidence"] = proportionality

    return validate_run_cost_proportionality_ledger(ledger)


_COMPONENT_FIELDS = {
    "runtime_performance_budget": "policy_design_run_cost_runtime_performance_budget_missing",
    "foundry_cost_model": "policy_design_run_cost_foundry_cost_model_missing",
    "scientist_budget": "policy_design_run_cost_scientist_budget_missing",
    "doe_search_budget": "policy_design_run_cost_doe_search_budget_missing",
    "provider_cost": "policy_design_run_cost_provider_cost_missing",
    "elapsed_time_budget": "policy_design_run_cost_elapsed_time_budget_missing",
    "human_review_burden": "policy_design_run_cost_human_review_burden_missing",
}

_STOPPING_DECISIONS = frozenset({"stop", "stopped", "saturated", "closeout", "complete"})
_LOW_IMPACT_LABELS = frozenset({"low", "minor", "internal", "private", "limited"})


def _runtime_refs_from_quality_context(
    *,
    quality_evidence: Mapping[str, Any],
    case: Mapping[str, Any],
    job_payload: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
) -> dict[str, str]:
    refs: dict[str, str] = {}

    def visit(value: object) -> None:
        if isinstance(value, Mapping):
            for raw_key, raw_value in value.items():
                key = str(raw_key)
                if key.endswith("_ref") and _runtime_artifact_ref(raw_value):
                    refs.setdefault(key, str(raw_value))
                visit(raw_value)
        elif isinstance(value, Sequence) and not isinstance(value, str):
            for item in value:
                visit(item)

    visit(job_payload or {})
    visit(run_payload or {})
    visit({"policy_design_case": case})
    visit(quality_evidence)
    return refs


def _source_ref(
    refs: Mapping[str, str],
    keys: Sequence[str],
    *,
    run_id: str,
    slug: str,
) -> str:
    for key in keys:
        value = refs.get(key)
        if _runtime_artifact_ref(value):
            return value
    return f"artifact://runtime-quality/run-cost/{_artifact_slug(run_id)}/{slug}"


def _source_ref_from_mapping(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    for key in (
        "cost_evidence_ref",
        "stopping_rule_result_ref",
        "evidence_ref",
        "cas_ref",
        "artifact_ref",
    ):
        ref = _text(value.get(key))
        if ref and _runtime_artifact_ref(ref):
            return ref
    return None


def _default_public_impact(authority_level: str, canary_kind: str | None) -> str:
    label = _normalized_label(canary_kind) or authority_level
    if label in {"production", "governed"}:
        return "high"
    if label == "research":
        return "medium"
    return "low"


def _performance_budget_from_context(
    *,
    quality_evidence: Mapping[str, Any],
    job_payload: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    for candidate in (
        _nested_get(job_payload, "canary_performance_budget"),
        _nested_get(run_payload, "canary_performance_budget"),
        quality_evidence.get("canary_performance_budget"),
        _nested_get(job_payload, "run_performance_summary"),
        _nested_get(run_payload, "run_performance_summary"),
        quality_evidence.get("run_performance_summary"),
    ):
        if isinstance(candidate, Mapping):
            return candidate
    return {}


def _performance_actual_ms(performance_budget: Mapping[str, Any]) -> float:
    rows = _rows(performance_budget.get("phase_budgets"))
    row_total = sum(
        _first_number(
            row,
            (
                "observed_duration_ms",
                "duration_ms",
                "elapsed_ms",
                "latency_ms",
                "actual_ms",
            ),
        )
        or 0.0
        for row in rows
    )
    if row_total:
        return row_total
    return _first_number(
        performance_budget,
        ("observed_duration_ms", "duration_ms", "elapsed_ms", "latency_ms", "actual_ms"),
    ) or 0.0


def _performance_budget_ms(performance_budget: Mapping[str, Any]) -> float:
    rows = _rows(performance_budget.get("phase_budgets"))
    row_total = sum((_first_number(row, ("budget_ms", "max_duration_ms")) or 0.0) for row in rows)
    if row_total:
        return row_total
    return _first_number(performance_budget, ("budget_ms", "max_duration_ms")) or 0.0


def _foundry_cost_usd(quality_evidence: Mapping[str, Any]) -> float:
    report = quality_evidence.get("foundry_method_report")
    if not isinstance(report, Mapping):
        return 0.0
    methods = _rows(report.get("selected_methods") or report.get("methods"))
    cost = sum(
        _sum_numeric_keys(
            method,
            (
                "actual_cost_usd",
                "cost_usd",
                "estimated_cost_usd",
                "compute_cost_usd",
            ),
        )
        for method in methods
    )
    if cost:
        return cost
    return _sum_numeric_keys(
        report.get("cost_model"),
        ("actual_cost_usd", "cost_usd", "estimated_cost_usd", "compute_cost_usd"),
    )


def _report_budget_usd(report: object) -> float:
    if not isinstance(report, Mapping):
        return 0.0
    return _sum_numeric_keys(
        report,
        ("budget_usd", "max_cost_usd", "reserved_budget_usd", "cost_budget_usd"),
    )


def _scientist_budget_component(
    case: Mapping[str, Any],
    *,
    synthesis_run_cost: Mapping[str, Any],
    evidence_ref: str,
) -> dict[str, Any]:
    budget = (
        _first_number(case, ("scientist_budget_usd", "scientist_max_cost_usd"))
        or _first_number(_nested_get(case, "scientist_budget"), ("budget_usd", "max_cost_usd"))
        or 0.0
    )
    actual = (
        _first_number(case, ("scientist_actual_cost_usd", "scientist_cost_usd"))
        or _first_number(_nested_get(case, "scientist_budget"), ("actual_cost_usd", "cost_usd"))
        or 0.0
    )
    return {
        "actual_cost_usd": actual,
        "budget_usd": budget,
        "observed_marginal_cost_usd": _first_number(
            synthesis_run_cost,
            ("marginal_cost_usd",),
        )
        or 0.0,
        "evidence_ref": evidence_ref,
    }


def _doe_search_budget_component(
    case: Mapping[str, Any],
    *,
    evidence_ref: str,
) -> dict[str, Any]:
    multiverse_rows = [
        *_rows(case.get("multiverse_specification_curves")),
        *_rows(case.get("specification_curves")),
        *_rows(case.get("search_budget_records")),
        *_rows(case.get("doe_search_budget_records")),
    ]
    return {
        "actual_cost_usd": _sum_numeric_keys(
            multiverse_rows,
            ("actual_cost_usd", "cost_usd", "estimated_cost_usd"),
        ),
        "budget_usd": _sum_numeric_keys(
            multiverse_rows,
            ("budget_usd", "max_cost_usd", "reserved_budget_usd"),
        ),
        "observed_search_record_count": len(multiverse_rows),
        "evidence_ref": evidence_ref,
    }


def _provider_cost_usd(
    *,
    quality_evidence: Mapping[str, Any],
    job_payload: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
) -> float:
    ledger_cost = _provider_ledger_cost_usd(quality_evidence.get("provider_model_quality_ledger"))
    if ledger_cost is not None:
        return ledger_cost
    return _sum_numeric_keys(
        _llm_model_variants(job_payload=job_payload, run_payload=run_payload),
        ("actual_cost_usd", "cost_usd", "estimated_cost_usd"),
    )


def _provider_budget_usd(
    *,
    quality_evidence: Mapping[str, Any],
    job_payload: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
) -> float:
    ledger = quality_evidence.get("provider_model_quality_ledger")
    budget = _sum_numeric_keys(
        ledger,
        ("budget_usd", "max_cost_usd", "reserved_budget_usd"),
    )
    if budget:
        return budget
    return _sum_numeric_keys(
        _llm_model_variants(job_payload=job_payload, run_payload=run_payload),
        ("budget_usd", "max_cost_usd", "reserved_budget_usd"),
    )


def _provider_ledger_cost_usd(ledger: object) -> float | None:
    if not isinstance(ledger, Mapping):
        return None
    entries = _rows(ledger.get("entries"))
    entry_cost = sum(
        _first_number(_mapping(entry.get("metrics")), ("cost_usd_total",))
        or _first_number(entry, ("actual_cost_usd", "cost_usd", "estimated_cost_usd"))
        or 0.0
        for entry in entries
    )
    if entry_cost:
        return entry_cost
    summary_cost = _first_number(_mapping(ledger.get("summary")), ("cost_usd_total",))
    if summary_cost is not None:
        return summary_cost
    observation_cost = _sum_numeric_keys(
        ledger.get("observations"),
        ("actual_cost_usd", "cost_usd", "estimated_cost_usd"),
    )
    return observation_cost if observation_cost else None


def _llm_model_variants(
    *,
    job_payload: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    variants: list[Mapping[str, Any]] = []
    for payload in (job_payload, run_payload):
        value = _nested_get(payload, "llm_model_variants")
        variants.extend(_rows(value))
    return variants


def _human_review_burden_component(
    quality_evidence: Mapping[str, Any],
    *,
    evidence_ref: str,
) -> dict[str, Any]:
    report = _mapping(quality_evidence.get("human_review_calibration"))
    burden = _mapping(report.get("reviewer_burden"))
    summary = _mapping(report.get("summary"))
    actual_hours = (
        _first_number(
            burden,
            (
                "actual_reviewer_hours",
                "reviewer_hours",
                "actual_hours",
                "human_review_hours",
            ),
        )
        or _first_number(summary, ("actual_reviewer_hours", "human_review_hours"))
        or 0.0
    )
    return {
        "actual_reviewer_hours": actual_hours,
        "budget_reviewer_hours": _first_number(
            burden,
            ("budget_reviewer_hours", "reviewer_hours_budget", "budget_hours"),
        )
        or 0.0,
        "review_count": _first_number(summary, ("review_count",)) or 0.0,
        "evidence_ref": evidence_ref,
    }


def _elapsed_seconds(
    *,
    performance_budget: Mapping[str, Any],
    job_payload: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
) -> float:
    actual_ms = _performance_actual_ms(performance_budget)
    if actual_ms:
        return actual_ms / 1000.0
    for payload in (job_payload, run_payload):
        started_at = _timestamp(
            _nested_get(payload, "started_at")
            or _nested_get(payload, "created_at")
            or _nested_get(payload, "submitted_at")
        )
        finished_at = _timestamp(
            _nested_get(payload, "finished_at")
            or _nested_get(payload, "completed_at")
            or _nested_get(payload, "updated_at")
        )
        if started_at is not None and finished_at is not None:
            return max(0.0, (finished_at - started_at).total_seconds())
    return 0.0


def _evidence_depth_budget(
    case: Mapping[str, Any],
    *,
    quality_evidence: Mapping[str, Any],
    synthesis: Mapping[str, Any],
    authority_level: str,
    public_impact: str,
    stopping_ref: str,
) -> dict[str, Any]:
    saturation = _mapping(synthesis.get("information_saturation"))
    observed_heterogeneity = (
        saturation.get("observed_heterogeneity")
        or synthesis.get("observed_heterogeneity")
        or case.get("observed_heterogeneity")
        or "moderate"
    )
    effective_count = _effective_independent_evidence_count(
        case,
        quality_evidence=quality_evidence,
        synthesis=synthesis,
    )
    required_count = _required_independent_count(
        authority_level=authority_level,
        public_impact=public_impact,
        observed_heterogeneity=observed_heterogeneity,
    )
    return {
        "authority_level": authority_level,
        "public_impact": public_impact,
        "observed_heterogeneity": observed_heterogeneity,
        "effective_independent_evidence_count": effective_count,
        "minimum_effective_independent_evidence_count": required_count,
        "stopping_rule": synthesis.get("stopping_rule")
        or saturation.get("stopping_rule")
        or "stop after runtime quality evidence budget is saturated",
        "stopping_decision": synthesis.get("stopping_decision")
        or saturation.get("stopping_decision")
        or "stop",
        "stopping_rule_result_ref": stopping_ref,
    }


def _effective_independent_evidence_count(
    case: Mapping[str, Any],
    *,
    quality_evidence: Mapping[str, Any],
    synthesis: Mapping[str, Any],
) -> int:
    explicit = _first_number(
        synthesis,
        (
            "effective_independent_evidence_count",
            "effective_independent_count",
        ),
    ) or _first_number(
        case,
        (
            "effective_independent_evidence_count",
            "effective_independent_count",
        ),
    )
    if explicit is not None:
        return int(explicit)
    evidence_lines = _rows(case.get("evidence_lines"))
    if evidence_lines:
        return len(
            {
                _text(line.get("source_ref") or line.get("evidence_ref") or line.get("line_id"))
                for line in evidence_lines
                if _text(line.get("source_ref") or line.get("evidence_ref") or line.get("line_id"))
            }
        )
    present_reports = [
        key
        for key in (
            "normative_evidence",
            "fabric_retrieval_trace",
            "foundry_method_report",
            "policy_grounding_matrix",
            "human_review_calibration",
            "provider_model_quality_ledger",
        )
        if isinstance(quality_evidence.get(key), Mapping)
    ]
    return len(present_reports)


def _proportionality_evidence_from_synthesis(
    synthesis_run_cost: Mapping[str, Any],
    *,
    fallback_ref: str,
) -> dict[str, Any] | None:
    if not synthesis_run_cost:
        return None
    rationale = _text(
        synthesis_run_cost.get("proportionality_rationale")
        or synthesis_run_cost.get("rationale")
    )
    if rationale is None:
        return None
    evidence_ref = _source_ref_from_mapping(synthesis_run_cost) or fallback_ref
    return {
        "status": synthesis_run_cost.get("status") or "proportional",
        "rationale": rationale,
        "evidence_ref": evidence_ref,
    }


def _best_synthesis_report(case: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("synthesis_reports", "evidence_synthesis_reports", "synthesis_report"):
        value = case.get(key)
        if isinstance(value, Mapping):
            return value
        for row in _rows(value):
            return row
    return {}


def _budget_change_records(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in ("budget_change_records", "budget_change_record", "budget_overrun_approvals"):
        value = case.get(key)
        if isinstance(value, Mapping):
            rows.append(value)
        else:
            rows.extend(_rows(value))
    return tuple(rows)


def _rows(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _nested_get(payload: object, key: str) -> object | None:
    if isinstance(payload, Mapping):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = _nested_get(value, key)
            if found is not None:
                return found
    elif isinstance(payload, Sequence) and not isinstance(payload, str):
        for value in payload:
            found = _nested_get(value, key)
            if found is not None:
                return found
    return None


def _first_number(mapping: object, keys: Sequence[str]) -> float | None:
    if not isinstance(mapping, Mapping):
        return None
    for key in keys:
        number = _coerce_number(mapping.get(key))
        if number is not None:
            return number
    return None


def _sum_numeric_keys(value: object, keys: Sequence[str]) -> float:
    total = 0.0
    if isinstance(value, Mapping):
        for raw_key, raw_value in value.items():
            if str(raw_key) in keys:
                total += _coerce_number(raw_value) or 0.0
            elif isinstance(raw_value, Mapping | Sequence) and not isinstance(raw_value, str):
                total += _sum_numeric_keys(raw_value, keys)
    elif isinstance(value, Sequence) and not isinstance(value, str):
        for item in value:
            total += _sum_numeric_keys(item, keys)
    return total


def _coerce_number(value: object) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = _text(value)
    if text is None:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _artifact_slug(value: object) -> str:
    text = _text(value) or "unknown"
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in text)


def _validate_cost_component(value: object, *, field: str, code: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise RunCostProportionalityError(
            code,
            f"Run-cost proportionality ledger must include non-empty {field}.",
            field,
        )
    row = dict(value)
    evidence_ref = _required_text(
        row.get("evidence_ref")
        or row.get("cas_ref")
        or row.get("source_ref")
        or row.get("report_ref"),
        "evidence_ref",
        f"{code}_ref_missing",
    )
    if not _runtime_artifact_ref(evidence_ref):
        raise RunCostProportionalityError(
            f"{code}_ref_invalid",
            f"Run-cost component {field} must cite a runtime artifact ref.",
            f"{field}.evidence_ref",
        )
    row["evidence_ref"] = evidence_ref
    return row


def _validate_evidence_depth_budget(
    value: object,
    *,
    authority_level: str,
    public_impact: str,
    typed_blockers: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise RunCostProportionalityError(
            "policy_design_run_cost_evidence_depth_budget_missing",
            "Run-cost ledger must include evidence_depth_budget.",
            "evidence_depth_budget",
        )
    row = dict(value)
    row_authority = _normalized_label(row.get("authority_level")) or authority_level
    row_impact = _normalized_label(row.get("public_impact")) or public_impact
    row["authority_level"] = row_authority
    row["public_impact"] = row_impact
    row["observed_heterogeneity"] = _heterogeneity_label(row.get("observed_heterogeneity"))
    effective_count = _required_int(
        row.get("effective_independent_evidence_count")
        or row.get("effective_independent_count"),
        "evidence_depth_budget.effective_independent_evidence_count",
        "policy_design_run_cost_evidence_depth_effective_count_missing",
    )
    declared_minimum = _optional_int(
        row.get("minimum_effective_independent_evidence_count")
        or row.get("minimum_effective_independent_count")
    )
    required_count = max(
        declared_minimum or 0,
        _required_independent_count(
            authority_level=row_authority,
            public_impact=row_impact,
            observed_heterogeneity=row.get("observed_heterogeneity"),
        ),
    )
    row["effective_independent_evidence_count"] = effective_count
    row["minimum_effective_independent_evidence_count"] = declared_minimum or required_count
    row["required_effective_independent_evidence_count"] = required_count
    row["stopping_rule"] = _required_text(
        row.get("stopping_rule") or row.get("stop_when") or row.get("stopping_rule_id"),
        "stopping_rule",
        "policy_design_run_cost_stopping_rule_missing",
    )
    stopping_decision = _normalized_label(
        _required_text(
            row.get("stopping_decision") or row.get("decision"),
            "stopping_decision",
            "policy_design_run_cost_stopping_decision_missing",
        )
    )
    row["stopping_decision"] = stopping_decision
    stopping_ref = _text(
        row.get("stopping_rule_result_ref")
        or row.get("stopping_evidence_ref")
        or row.get("evidence_ref")
    )
    if stopping_decision in _STOPPING_DECISIONS and not stopping_ref and not typed_blockers:
        raise RunCostProportionalityError(
            "policy_design_run_cost_stopping_rule_ref_missing",
            "Stopping decisions must cite a stopping-rule result ref.",
            "evidence_depth_budget.stopping_rule_result_ref",
        )
    if (
        stopping_decision in _STOPPING_DECISIONS
        and effective_count < required_count
        and not typed_blockers
    ):
        raise RunCostProportionalityError(
            "policy_design_run_cost_evidence_depth_under_budget",
            (
                "Stopped run has less effective independent evidence than the "
                "authority, public-impact, and heterogeneity budget requires."
            ),
            "evidence_depth_budget.effective_independent_evidence_count",
        )
    if stopping_ref:
        if not _runtime_artifact_ref(stopping_ref):
            raise RunCostProportionalityError(
                "policy_design_run_cost_stopping_rule_ref_invalid",
                "Stopping-rule result ref must be a runtime artifact ref.",
                "evidence_depth_budget.stopping_rule_result_ref",
            )
        row["stopping_rule_result_ref"] = stopping_ref
    return row


def _validate_optional_proportionality_evidence(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or not value:
        return None
    row = dict(value)
    status = _normalized_label(
        _required_text(
            row.get("status") or row.get("decision"),
            "status",
            "policy_design_run_cost_proportionality_status_missing",
        )
    )
    if status not in {"proportional", "accepted", "approved", "pass", "passed"}:
        raise RunCostProportionalityError(
            "policy_design_run_cost_proportionality_status_invalid",
            "Proportionality evidence must be proportional, accepted, approved, or pass.",
            "proportionality_evidence.status",
        )
    row["status"] = status
    row["rationale"] = _required_text(
        row.get("rationale") or row.get("proportionality_rationale"),
        "rationale",
        "policy_design_run_cost_proportionality_rationale_missing",
    )
    evidence_ref = _required_text(
        row.get("evidence_ref") or row.get("cas_ref"),
        "evidence_ref",
        "policy_design_run_cost_proportionality_evidence_ref_missing",
    )
    if not _runtime_artifact_ref(evidence_ref):
        raise RunCostProportionalityError(
            "policy_design_run_cost_proportionality_evidence_ref_invalid",
            "Proportionality evidence must cite a runtime artifact ref.",
            "proportionality_evidence.evidence_ref",
        )
    row["evidence_ref"] = evidence_ref
    return row


def _valid_blockers_from_record(record: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    blockers: list[Mapping[str, Any]] = []
    for key in (
        "blockers",
        "runtime_blockers",
        "run_cost_blockers",
        "evidence_depth_blockers",
        "run_cost_proportionality_blockers",
    ):
        value = record.get(key)
        if isinstance(value, Mapping):
            candidate_values: Iterable[object] = (value,)
        elif isinstance(value, Sequence) and not isinstance(value, str):
            candidate_values = value
        else:
            candidate_values = ()
        for candidate in candidate_values:
            if isinstance(candidate, Mapping):
                blockers.append(validate_run_cost_proportionality_blocker(candidate))
    return tuple(blockers)


def _has_accepted_budget_change(record: Mapping[str, Any]) -> bool:
    for key in ("budget_change_records", "budget_change_record", "budget_overrun_approvals"):
        value = record.get(key)
        if isinstance(value, Mapping):
            rows: Iterable[object] = (value,)
        elif isinstance(value, Sequence) and not isinstance(value, str):
            rows = value
        else:
            rows = ()
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            status = _normalized_label(row.get("status") or row.get("decision"))
            evidence_ref = _text(row.get("evidence_ref") or row.get("cas_ref"))
            runtime_event_ref = _text(row.get("runtime_event_ref"))
            if (
                status in {"accepted", "approved", "pass", "passed"}
                and _runtime_artifact_ref(evidence_ref)
                and _runtime_event_ref(runtime_event_ref)
            ):
                return True
    return False


def _required_independent_count(
    *,
    authority_level: str,
    public_impact: str,
    observed_heterogeneity: object,
) -> int:
    authority_min = {
        "exploratory": 1,
        "draft": 1,
        "research": 1,
        "governed": 2,
        "production": 3,
    }.get(authority_level, 2)
    impact_min = {
        "none": 1,
        "internal": 1,
        "low": 1,
        "minor": 1,
        "limited": 1,
        "medium": 2,
        "moderate": 2,
        "high": 3,
        "critical": 4,
        "severe": 4,
    }.get(public_impact, 2)
    return max(authority_min, impact_min) + _heterogeneity_bump(observed_heterogeneity)


def _heterogeneity_bump(value: object) -> int:
    if isinstance(value, Mapping):
        i_squared = _optional_float(value.get("i_squared"))
        if i_squared is not None:
            if i_squared >= 0.75:
                return 2
            if i_squared >= 0.5:
                return 1
        value = value.get("interpretation") or value.get("level") or value.get("status")
    label = _normalized_label(value)
    if label in {"severe", "very_high"}:
        return 2
    if label in {"high", "substantial"}:
        return 1
    return 0


def _heterogeneity_label(value: object) -> object:
    if isinstance(value, Mapping):
        return dict(value)
    return _normalized_label(value) or "not_reported"


def _is_low_impact(public_impact: str) -> bool:
    return public_impact in _LOW_IMPACT_LABELS


def _high_cost_low_impact_threshold_exceeded(
    *,
    total_actual_cost_usd: float,
    elapsed_seconds: float,
    human_review_hours: float,
) -> bool:
    return (
        total_actual_cost_usd >= HIGH_COST_LOW_IMPACT_COST_USD
        or elapsed_seconds >= HIGH_COST_LOW_IMPACT_ELAPSED_SECONDS
        or human_review_hours >= HIGH_COST_LOW_IMPACT_REVIEW_HOURS
    )


def _component_cost_usd(component: Mapping[str, Any]) -> float:
    return _first_numeric(
        component,
        ("actual_cost_usd", "actual_usd", "cost_usd", "spent_usd"),
    )


def _component_budget_usd(component: Mapping[str, Any]) -> float:
    return _first_numeric(
        component,
        ("budget_usd", "max_cost_usd", "reserved_budget_usd", "budgeted_usd"),
    )


def _component_seconds(component: Mapping[str, Any]) -> float:
    seconds = _first_numeric(component, ("actual_seconds", "elapsed_seconds", "seconds"))
    if seconds:
        return seconds
    milliseconds = _first_numeric(component, ("actual_ms", "elapsed_ms", "duration_ms"))
    return milliseconds / 1000.0 if milliseconds else 0.0


def _component_hours(component: Mapping[str, Any]) -> float:
    return _first_numeric(
        component,
        (
            "actual_reviewer_hours",
            "reviewer_hours",
            "actual_hours",
            "human_review_hours",
        ),
    )


def _first_numeric(mapping: Mapping[str, Any], keys: Sequence[str]) -> float:
    for key in keys:
        value = _optional_float(mapping.get(key))
        if value is not None:
            return value
    return 0.0


def _required_text(value: object, field: str, code: str) -> str:
    text = _text(value)
    if text is None:
        raise RunCostProportionalityError(
            code,
            f"Run-cost proportionality ledger must include {field}.",
            field,
        )
    return text


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalized_label(value: object) -> str:
    text = _text(value)
    return text.casefold().replace("-", "_") if text is not None else ""


def _first_normalized_label_from_values(
    values: Iterable[object],
    *,
    keys: Sequence[str],
) -> str:
    for value in values:
        label = _normalized_label_from_value(value, keys=keys)
        if label:
            return label
    return ""


def _required_normalized_label_from_values(
    values: Iterable[object],
    *,
    keys: Sequence[str],
    field: str,
    code: str,
) -> str:
    label = _first_normalized_label_from_values(values, keys=keys)
    if not label:
        raise RunCostProportionalityError(
            code,
            f"Run-cost proportionality ledger must include non-empty {field}.",
            field,
        )
    return label


def _normalized_label_from_value(value: object, *, keys: Sequence[str]) -> str:
    text = _label_text_from_value(value, keys=keys)
    return text.casefold().replace("-", "_") if text is not None else ""


def _label_text_from_value(value: object, *, keys: Sequence[str]) -> str | None:
    if isinstance(value, Mapping):
        for key in keys:
            if key in value:
                text = _label_text_from_value(value[key], keys=keys)
                if text:
                    return text
        return None
    return _text(value)


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RunCostProportionalityError(
            "policy_design_run_cost_number_invalid",
            "Run-cost numeric fields must be finite numbers.",
        ) from exc
    if not math.isfinite(number) or number < 0:
        raise RunCostProportionalityError(
            "policy_design_run_cost_number_invalid",
            "Run-cost numeric fields must be finite non-negative numbers.",
        )
    return number


def _required_int(value: object, field: str, code: str) -> int:
    number = _optional_float(value)
    if number is None or int(number) != number:
        raise RunCostProportionalityError(
            code,
            "Run-cost evidence-depth counts must be non-negative integers.",
            field,
        )
    return int(number)


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    number = _optional_float(value)
    if number is None or int(number) != number:
        raise RunCostProportionalityError(
            "policy_design_run_cost_integer_invalid",
            "Run-cost evidence-depth counts must be non-negative integers.",
        )
    return int(number)


def _runtime_artifact_ref(value: object) -> bool:
    text = _text(value)
    if text is None or text.startswith(("/", "./", "../", "~", "file://", "repo://")):
        return False
    if text.startswith("sha256:"):
        digest = text.removeprefix("sha256:")
        return len(digest) == 64 and all(char in "0123456789abcdefABCDEF" for char in digest)
    if text.startswith("cas://sha256/"):
        digest = text.removeprefix("cas://sha256/")
        return len(digest) == 64 and all(char in "0123456789abcdefABCDEF" for char in digest)
    return text.startswith("artifact://")


def _runtime_event_ref(value: object) -> bool:
    text = _text(value)
    if text is None:
        return False
    return _runtime_artifact_ref(text) or text.startswith("event://")


__all__ = [
    "HIGH_COST_LOW_IMPACT_COST_USD",
    "HIGH_COST_LOW_IMPACT_ELAPSED_SECONDS",
    "HIGH_COST_LOW_IMPACT_REVIEW_HOURS",
    "RUN_COST_PROPORTIONALITY_LEDGER_CONTRACT_ID",
    "RUN_COST_PROPORTIONALITY_LEDGER_SCHEMA_VERSION",
    "RunCostProportionalityError",
    "build_run_cost_proportionality_ledger_from_quality_context",
    "run_cost_ledger_record_id",
    "validate_run_cost_proportionality_blocker",
    "validate_run_cost_proportionality_ledger",
]
