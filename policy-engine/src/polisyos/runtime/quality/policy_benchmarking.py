"""Best-in-class benchmarking records for Policy Design Case closeout."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

POLICY_BENCHMARKING_RECORD_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.best_in_class_benchmarking.v1"
)
POLICY_BENCHMARKING_RECORD_CONTRACT_ID = (
    "policy_design_case.best_in_class_benchmarking.v1"
)
POLICY_BENCHMARKING_RECORD_FAMILY = "best_in_class_benchmarking.v1"

REQUIRED_POLICY_BENCHMARK_METRICS = (
    "external_audit_pass_rate",
    "human_team_benchmark",
    "reversal_rate",
    "retraction_rate",
    "calibration_error",
    "claim_substantiation_rate",
    "triangulation_coverage",
    "operator_time_to_root_cause_seconds",
)

_PASSING_STATUSES = frozenset({"pass", "passed", "ok", "accepted", "verified"})
_LOWER_IS_BETTER_METRICS = frozenset(
    {
        "reversal_rate",
        "retraction_rate",
        "calibration_error",
        "operator_time_to_root_cause_seconds",
    }
)
_DIRECTIONS = frozenset(
    {
        "higher_is_better",
        "lower_is_better",
        "within_tolerance",
    }
)
_BEST_IN_CLASS_TEXT_MARKERS = (
    "best in class",
    "best-in-class",
    "frontier quality",
    "state of the art",
    "state-of-the-art",
)


@dataclass(frozen=True)
class PolicyBenchmarkingError(ValueError):
    """Fail-closed best-in-class benchmarking contract violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class PolicyBenchmarkingIssue:
    """Scorecard-readable best-in-class benchmarking validation issue."""

    code: str
    message: str
    field: str
    evidence_ref: str | None = None
    affected_claim: str | None = None
    next_action: str = (
        "Emit the Wave 31 best-in-class benchmarking record with external audit, "
        "human-team, reversal/retraction, calibration, claim substantiation, "
        "triangulation, operator root-cause, run-cost, and proportionality evidence."
    )

    def as_gate_fields(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "evidence_ref": self.evidence_ref,
            "affected_claim": self.affected_claim,
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class PolicyBenchmarkingValidationResult:
    """Validation result for best-in-class case records."""

    status: str
    benchmark_claim_ids: tuple[str, ...]
    records: tuple[dict[str, Any], ...]
    issues: tuple[PolicyBenchmarkingIssue, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": {
                "benchmark_claim_count": len(self.benchmark_claim_ids),
                "record_count": len(self.records),
                "issue_count": len(self.issues),
                "required_metrics": list(REQUIRED_POLICY_BENCHMARK_METRICS),
            },
            "benchmark_claim_ids": list(self.benchmark_claim_ids),
            "records": list(self.records),
            "issues": [issue.as_gate_fields() for issue in self.issues],
        }


def best_in_class_benchmarking_record_id(record: Mapping[str, Any]) -> str:
    """Return the stable identity for a best-in-class benchmarking record."""

    return _required_text(
        record.get("record_id") or record.get("benchmarking_record_id") or record.get("id"),
        "record_id",
        "policy_design_best_in_class_benchmark_record_id_missing",
    )


def validate_policy_benchmarking_record(
    record: Mapping[str, Any],
    *,
    required_claim_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Validate one Wave 31 best-in-class benchmarking record."""

    if not isinstance(record, Mapping):
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmarking_record_invalid",
            "Best-in-class benchmarking record must be a mapping.",
            "best_in_class_benchmarking",
        )

    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_best_in_class_benchmark_schema_version_missing",
    )
    if schema_version != POLICY_BENCHMARKING_RECORD_SCHEMA_VERSION:
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_schema_version_invalid",
            "Best-in-class benchmarking record must use the Wave 31 schema version.",
            "schema_version",
        )

    normalized["schema_version"] = POLICY_BENCHMARKING_RECORD_SCHEMA_VERSION
    normalized["contract_id"] = (
        _text(record.get("contract_id")) or POLICY_BENCHMARKING_RECORD_CONTRACT_ID
    )
    record_family = _text(record.get("record_family")) or POLICY_BENCHMARKING_RECORD_FAMILY
    if record_family != POLICY_BENCHMARKING_RECORD_FAMILY:
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_record_family_invalid",
            "Best-in-class benchmarking record must bind to the benchmarking record family.",
            "record_family",
        )
    normalized["record_family"] = POLICY_BENCHMARKING_RECORD_FAMILY
    normalized["record_id"] = best_in_class_benchmarking_record_id(record)
    for field, code in (
        ("case_id", "policy_design_best_in_class_case_id_missing"),
        ("run_id", "policy_design_best_in_class_run_id_missing"),
        ("job_id", "policy_design_best_in_class_job_id_missing"),
        ("authority_level", "policy_design_best_in_class_authority_level_missing"),
        ("domain", "policy_design_best_in_class_domain_missing"),
    ):
        normalized[field] = _required_text(record.get(field), field, code)

    status = _normalized_label(record.get("status"))
    if status not in _PASSING_STATUSES:
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_status_not_pass",
            "Best-in-class benchmarking evidence must be passing for closeout.",
            "status",
        )
    normalized["status"] = status

    claim_ids = _text_values(record.get("benchmark_claim_ids") or record.get("claim_ids"))
    if not claim_ids:
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_claim_ids_missing",
            "Best-in-class benchmarking record must name the claim ids it falsifies.",
            "benchmark_claim_ids",
        )
    normalized["benchmark_claim_ids"] = list(claim_ids)
    missing_claim_ids = tuple(
        claim_id for claim_id in _text_values(required_claim_ids) if claim_id not in claim_ids
    )
    if missing_claim_ids:
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_claim_not_benchmarked",
            (
                "Best-in-class benchmarking record does not cover all best-in-class "
                f"claim ids: {', '.join(missing_claim_ids)}."
            ),
            "benchmark_claim_ids",
        )

    normalized["run_cost_ledger_refs"] = _required_runtime_refs(
        _first_present(
            record,
            (
                "run_cost_ledger_refs",
                "run_cost_proportionality_refs",
                "cost_evidence_refs",
            ),
        ),
        "run_cost_ledger_refs",
        missing_code="policy_design_best_in_class_run_cost_ref_missing",
        invalid_code="policy_design_best_in_class_run_cost_ref_invalid",
    )
    normalized["proportionality_evidence_refs"] = _required_runtime_refs(
        _first_present(
            record,
            (
                "proportionality_evidence_refs",
                "proportionality_refs",
                "evidence_depth_budget_refs",
            ),
        ),
        "proportionality_evidence_refs",
        missing_code="policy_design_best_in_class_proportionality_ref_missing",
        invalid_code="policy_design_best_in_class_proportionality_ref_invalid",
    )

    metrics = record.get("metrics")
    if not isinstance(metrics, Mapping):
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_metrics_missing",
            "Best-in-class benchmarking record must include a metrics mapping.",
            "metrics",
        )
    normalized_metrics: dict[str, dict[str, Any]] = {}
    for metric_id in REQUIRED_POLICY_BENCHMARK_METRICS:
        metric = metrics.get(metric_id) or record.get(metric_id)
        normalized_metrics[metric_id] = _validate_metric(metric, metric_id=metric_id)
    normalized["metrics"] = normalized_metrics

    evidence_ref = _required_text(
        record.get("evidence_ref") or record.get("cas_ref"),
        "evidence_ref",
        "policy_design_best_in_class_evidence_ref_missing",
    )
    if not _runtime_artifact_ref(evidence_ref):
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_evidence_ref_invalid",
            "Best-in-class benchmarking record evidence_ref must be a runtime artifact ref.",
            "evidence_ref",
        )
    normalized["evidence_ref"] = evidence_ref
    runtime_event_ref = _required_text(
        record.get("runtime_event_ref"),
        "runtime_event_ref",
        "policy_design_best_in_class_runtime_event_ref_missing",
    )
    if not _runtime_event_ref(runtime_event_ref):
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_runtime_event_ref_invalid",
            "Best-in-class benchmarking record must cite a runtime event ref.",
            "runtime_event_ref",
        )
    normalized["runtime_event_ref"] = runtime_event_ref
    return normalized


def validate_policy_design_best_in_class_benchmarking_records(
    case: Mapping[str, Any],
) -> PolicyBenchmarkingValidationResult:
    """Validate that best-in-class claims have falsifiable benchmark evidence."""

    if not isinstance(case, Mapping):
        issue = PolicyBenchmarkingIssue(
            code="policy_design_best_in_class_case_invalid",
            message="Policy Design Case benchmarking validation requires a mapping.",
            field="policy_design_case",
        )
        return PolicyBenchmarkingValidationResult("fail", (), (), (issue,))

    benchmark_claim_ids = _best_in_class_claim_ids(case)
    if not benchmark_claim_ids:
        return PolicyBenchmarkingValidationResult("pass", (), (), ())

    records = _benchmarking_rows(case)
    if not records:
        issue = PolicyBenchmarkingIssue(
            code="policy_design_best_in_class_benchmarking_record_missing",
            message=(
                "Best-in-class claims must be backed by Wave 31 benchmarking "
                "evidence, not narrative assertion."
            ),
            field="best_in_class_benchmarking_records",
        )
        return PolicyBenchmarkingValidationResult(
            "fail",
            benchmark_claim_ids,
            (),
            (issue,),
        )

    issues: list[PolicyBenchmarkingIssue] = []
    validated_records: list[dict[str, Any]] = []
    covered_claim_ids: set[str] = set()
    for record in records:
        try:
            validated = validate_policy_benchmarking_record(record)
        except PolicyBenchmarkingError as exc:
            issues.append(
                PolicyBenchmarkingIssue(
                    code=exc.code,
                    message=str(exc),
                    field=exc.field or "best_in_class_benchmarking_records",
                    evidence_ref=_text(record.get("evidence_ref") or record.get("cas_ref")),
                )
            )
            continue
        validated_records.append(validated)
        covered_claim_ids.update(_text_values(validated.get("benchmark_claim_ids")))

    for claim_id in benchmark_claim_ids:
        if claim_id in covered_claim_ids:
            continue
        issues.append(
            PolicyBenchmarkingIssue(
                code="policy_design_best_in_class_claim_not_benchmarked",
                message=(
                    f"Best-in-class claim {claim_id!r} is not covered by any "
                    "validated benchmarking record."
                ),
                field="benchmark_claim_ids",
                affected_claim=claim_id,
            )
        )

    return PolicyBenchmarkingValidationResult(
        "fail" if issues else "pass",
        benchmark_claim_ids,
        tuple(validated_records),
        tuple(issues),
    )


def _validate_metric(metric: object, *, metric_id: str) -> dict[str, Any]:
    if not isinstance(metric, Mapping):
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_metric_missing",
            f"Best-in-class benchmarking metric {metric_id!r} is required.",
            f"metrics.{metric_id}",
        )
    normalized = dict(metric)
    observed = _first_number(metric, ("observed_value", "value", "rate", "seconds"))
    if observed is None:
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_metric_observed_missing",
            f"Best-in-class benchmarking metric {metric_id!r} must include observed_value.",
            f"metrics.{metric_id}.observed_value",
        )
    target = _first_number(metric, ("target_value", "target", "threshold", "benchmark_value"))
    if target is None:
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_metric_target_missing",
            f"Best-in-class benchmarking metric {metric_id!r} must include target_value.",
            f"metrics.{metric_id}.target_value",
        )
    direction = _normalized_label(metric.get("direction")) or _default_direction(metric_id)
    if direction not in _DIRECTIONS:
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_direction_invalid",
            "Benchmarking metric direction must be explicit and supported.",
            f"metrics.{metric_id}.direction",
        )
    tolerance = _first_number(metric, ("tolerance", "target_tolerance")) or 0.0
    if not _target_satisfied(
        observed=observed,
        target=target,
        direction=direction,
        tolerance=tolerance,
    ):
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_target_not_met",
            f"Best-in-class metric {metric_id!r} does not meet its benchmark target.",
            f"metrics.{metric_id}",
        )
    sample_size = _first_int(
        metric,
        (
            "sample_size",
            "n",
            "case_count",
            "audit_count",
            "incident_count",
            "prediction_count",
        ),
    )
    if sample_size is None or sample_size <= 0:
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_sample_missing",
            f"Best-in-class metric {metric_id!r} must include positive sample_size.",
            f"metrics.{metric_id}.sample_size",
        )
    evidence_ref = _required_text(
        metric.get("evidence_ref") or metric.get("cas_ref"),
        "evidence_ref",
        "policy_design_best_in_class_benchmark_metric_evidence_ref_missing",
    )
    if not _runtime_artifact_ref(evidence_ref):
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_metric_evidence_ref_invalid",
            "Benchmarking metric evidence_ref must be a runtime artifact ref.",
            f"metrics.{metric_id}.evidence_ref",
        )
    runtime_event_ref = _required_text(
        metric.get("runtime_event_ref"),
        "runtime_event_ref",
        "policy_design_best_in_class_benchmark_metric_runtime_event_ref_missing",
    )
    if not _runtime_event_ref(runtime_event_ref):
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_metric_runtime_event_ref_invalid",
            "Benchmarking metric must cite a runtime event ref.",
            f"metrics.{metric_id}.runtime_event_ref",
        )

    normalized.update(
        {
            "metric_id": metric_id,
            "observed_value": observed,
            "target_value": target,
            "direction": direction,
            "sample_size": sample_size,
            "evidence_ref": evidence_ref,
            "runtime_event_ref": runtime_event_ref,
        }
    )
    if direction == "within_tolerance":
        normalized["tolerance"] = tolerance
    return normalized


def _best_in_class_claim_ids(case: Mapping[str, Any]) -> tuple[str, ...]:
    claim_ids: list[str] = []
    claims = case.get("final_major_claims") or case.get("major_claims") or ()
    if not isinstance(claims, list):
        return ()
    for index, claim in enumerate(claims, start=1):
        if not isinstance(claim, Mapping) or claim.get("major") is False:
            continue
        if not _claim_is_best_in_class(claim):
            continue
        claim_id = _text(claim.get("claim_id") or claim.get("id"))
        claim_ids.append(claim_id or f"<unnamed-best-in-class-claim-{index}>")
    return tuple(dict.fromkeys(claim_ids))


def _claim_is_best_in_class(claim: Mapping[str, Any]) -> bool:
    for key in (
        "best_in_class",
        "claims_best_in_class",
        "best_in_class_claim",
        "benchmarking_required",
    ):
        value = claim.get(key)
        if isinstance(value, bool) and value:
            return True
        if _normalized_label(value) in {"true", "yes", "required", "best_in_class"}:
            return True
    for key in ("claim_class", "quality_claim", "benchmark_claim", "claim_type"):
        labels = {_normalized_label(value) for value in _text_values(claim.get(key))}
        if labels & {"best_in_class", "frontier_quality", "state_of_the_art"}:
            return True
    text = " ".join(
        _text_values(
            [
                claim.get("text"),
                claim.get("claim"),
                claim.get("summary"),
                claim.get("title"),
            ]
        )
    ).casefold()
    return any(marker in text for marker in _BEST_IN_CLASS_TEXT_MARKERS)


def _benchmarking_rows(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "best_in_class_benchmarking_records",
        "best_in_class_benchmarking",
        "policy_benchmarking_records",
        "policy_benchmarking_record",
        "benchmarking_records",
    ):
        value = case.get(key)
        if isinstance(value, Mapping):
            rows.append(value)
        elif isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    nodes = case.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_type = _normalized_label(node.get("node_type"))
            node_family = _normalized_label(node.get("node_family"))
            if node_type == "best_in_class_benchmarking" or (
                node_family == "best_in_class_benchmarking"
            ):
                rows.append(node)
    return tuple(rows)


def _required_runtime_refs(
    value: object,
    field: str,
    *,
    missing_code: str,
    invalid_code: str,
) -> list[str]:
    refs = list(_text_values(value))
    if not refs:
        raise PolicyBenchmarkingError(
            missing_code,
            f"Best-in-class benchmarking record must include {field}.",
            field,
        )
    invalid = [ref for ref in refs if not _runtime_artifact_ref(ref)]
    if invalid:
        raise PolicyBenchmarkingError(
            invalid_code,
            f"Best-in-class benchmarking {field} must be runtime artifact refs.",
            field,
        )
    return refs


def _first_present(mapping: Mapping[str, Any], keys: Sequence[str]) -> object:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], ()):
            return value
    return None


def _target_satisfied(
    *,
    observed: float,
    target: float,
    direction: str,
    tolerance: float,
) -> bool:
    if direction == "higher_is_better":
        return observed >= target
    if direction == "lower_is_better":
        return observed <= target
    return abs(observed - target) <= tolerance


def _default_direction(metric_id: str) -> str:
    return "lower_is_better" if metric_id in _LOWER_IS_BETTER_METRICS else "higher_is_better"


def _first_number(mapping: Mapping[str, Any], keys: Sequence[str]) -> float | None:
    for key in keys:
        value = mapping.get(key)
        if value in (None, ""):
            continue
        return _number(value)
    return None


def _first_int(mapping: Mapping[str, Any], keys: Sequence[str]) -> int | None:
    number = _first_number(mapping, keys)
    if number is None or int(number) != number:
        return None
    return int(number)


def _number(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_number_invalid",
            "Benchmarking numeric fields must be finite numbers.",
        ) from exc
    if not math.isfinite(number) or number < 0:
        raise PolicyBenchmarkingError(
            "policy_design_best_in_class_benchmark_number_invalid",
            "Benchmarking numeric fields must be finite non-negative numbers.",
        )
    return number


def _required_text(value: object, field: str, code: str) -> str:
    text = _text(value)
    if text is None:
        raise PolicyBenchmarkingError(
            code,
            f"Best-in-class benchmarking record must include {field}.",
            field,
        )
    return text


def _text_values(value: object) -> tuple[str, ...]:
    values: list[str] = []
    if isinstance(value, str):
        text = _text(value)
        if text is not None:
            values.append(text)
    elif isinstance(value, Mapping):
        for key in ("claim_id", "id", "ref", "evidence_ref", "cas_ref"):
            text = _text(value.get(key))
            if text is not None:
                values.append(text)
    elif isinstance(value, Iterable):
        for item in value:
            values.extend(_text_values(item))
    return tuple(dict.fromkeys(values))


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalized_label(value: object) -> str:
    text = _text(value)
    return text.casefold().replace("-", "_").replace(" ", "_") if text is not None else ""


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
    "POLICY_BENCHMARKING_RECORD_CONTRACT_ID",
    "POLICY_BENCHMARKING_RECORD_FAMILY",
    "POLICY_BENCHMARKING_RECORD_SCHEMA_VERSION",
    "REQUIRED_POLICY_BENCHMARK_METRICS",
    "PolicyBenchmarkingError",
    "PolicyBenchmarkingIssue",
    "PolicyBenchmarkingValidationResult",
    "best_in_class_benchmarking_record_id",
    "validate_policy_benchmarking_record",
    "validate_policy_design_best_in_class_benchmarking_records",
]
