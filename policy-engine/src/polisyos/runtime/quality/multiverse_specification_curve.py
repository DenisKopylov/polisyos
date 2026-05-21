"""Multiverse specification-curve records for Policy Design Case synthesis."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from statistics import median
from typing import Any

MULTIVERSE_SPECIFICATION_CURVE_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.multiverse_specification_curve.v1"
)
MULTIVERSE_SPECIFICATION_CURVE_CONTRACT_ID = (
    "policy_design_case.multiverse_specification_curve.v1"
)

REQUIRED_MULTIVERSE_SOURCE_KINDS = (
    "scientist_doe",
    "scientist_discovery",
    "foundry_sensitivity",
    "backtesting",
)
_SOURCE_KIND_LABELS = {
    "scientist_doe": "Scientist DOE",
    "scientist_discovery": "Scientist discovery",
    "foundry_sensitivity": "Foundry sensitivity",
    "backtesting": "backtesting",
}
_DEFENSIBLE_DECISIONS = frozenset(
    {
        "accepted",
        "defensible",
        "included",
        "pass",
        "passed",
        "supported",
        "valid",
    }
)
_REJECTED_DECISIONS = frozenset(
    {
        "exclude",
        "excluded",
        "fail",
        "failed",
        "invalid",
        "reject",
        "rejected",
        "unsupported",
    }
)
_DRIVER_AXIS_ORDER = (
    "model_family",
    "method_family",
    "covariate_set",
    "sample",
    "functional_form",
    "sensitivity_axes",
    "backtest_scenario",
    "source_kind",
)


@dataclass
class MultiverseSpecificationCurveError(ValueError):
    """Fail-closed multiverse specification-curve contract violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def build_multiverse_specification_curve_record(
    *,
    curve_id: str,
    claim_id: str | None = None,
    claim_ids: Iterable[str] = (),
    portfolio_id: str,
    scientist_doe_outputs: Iterable[object] = (),
    scientist_discovery_outputs: Iterable[object] = (),
    foundry_sensitivity_outputs: Iterable[object] = (),
    backtesting_outputs: Iterable[object] = (),
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
    previous_wave_refs: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Project producer outputs into one multiverse specification-curve record."""

    curve_id = _required_text(
        curve_id,
        "curve_id",
        "policy_design_multiverse_curve_id_missing",
    )
    portfolio_id = _required_text(
        portfolio_id,
        "portfolio_id",
        "policy_design_multiverse_portfolio_id_missing",
    )
    claims = _claim_ids(claim_id=claim_id, claim_ids=claim_ids)
    records: list[dict[str, Any]] = []
    source_groups = (
        ("scientist_doe", scientist_doe_outputs),
        ("scientist_discovery", scientist_discovery_outputs),
        ("foundry_sensitivity", foundry_sensitivity_outputs),
        ("backtesting", backtesting_outputs),
    )
    for source_kind, outputs in source_groups:
        for output_index, output in enumerate(outputs):
            records.extend(
                _project_output(
                    output,
                    source_kind=source_kind,
                    output_index=output_index,
                    default_claim_ids=claims,
                    default_portfolio_id=portfolio_id,
                )
            )

    normalized_records = _sorted_records(records)
    payload: dict[str, Any] = {
        "schema_version": MULTIVERSE_SPECIFICATION_CURVE_SCHEMA_VERSION,
        "contract_id": MULTIVERSE_SPECIFICATION_CURVE_CONTRACT_ID,
        "curve_id": curve_id,
        "claim_ids": claims,
        "portfolio_id": portfolio_id,
        "source_kind_counts": _source_kind_counts(normalized_records),
        "specification_records": normalized_records,
        "defensible_specifications": _specification_summaries(
            normalized_records, decision="defensible"
        ),
        "rejected_specifications": _specification_summaries(
            normalized_records, decision="rejected"
        ),
        "result_distribution": _result_distribution(normalized_records),
        "drivers_of_divergence": _drivers_of_divergence(normalized_records),
        "claim_markers": _claim_markers(normalized_records, claims),
    }
    if previous_wave_refs is not None:
        payload["previous_wave_refs"] = _validate_previous_wave_refs(previous_wave_refs)
    if evidence_ref is not None:
        payload["evidence_ref"] = str(evidence_ref)
    if runtime_event_ref is not None:
        payload["runtime_event_ref"] = str(runtime_event_ref)
    return validate_multiverse_specification_curve_record(payload)


def validate_multiverse_specification_curve_record(
    record: Mapping[str, Any],
    *,
    portfolio_designs: Iterable[Mapping[str, Any]] = (),
    evidence_lines: Iterable[Mapping[str, Any]] = (),
    independence_maps: Iterable[Mapping[str, Any]] = (),
    major_claim_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Validate and normalize one multiverse specification-curve record."""

    if not isinstance(record, Mapping):
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_record_invalid",
            "Multiverse specification-curve record must be a mapping.",
        )

    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_multiverse_schema_version_missing",
    )
    if schema_version != MULTIVERSE_SPECIFICATION_CURVE_SCHEMA_VERSION:
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_schema_version_invalid",
            "Multiverse specification-curve record must use the runtime-quality schema.",
            "schema_version",
        )
    normalized["schema_version"] = MULTIVERSE_SPECIFICATION_CURVE_SCHEMA_VERSION
    normalized["contract_id"] = (
        _text(record.get("contract_id")) or MULTIVERSE_SPECIFICATION_CURVE_CONTRACT_ID
    )
    normalized["curve_id"] = _required_text(
        record.get("curve_id") or record.get("record_id"),
        "curve_id",
        "policy_design_multiverse_curve_id_missing",
    )
    normalized["portfolio_id"] = _required_text(
        record.get("portfolio_id") or record.get("portfolio_ref"),
        "portfolio_id",
        "policy_design_multiverse_portfolio_id_missing",
    )
    claims = _claim_ids(
        claim_id=_text(record.get("claim_id")),
        claim_ids=record.get("claim_ids") or (),
    )
    required_claims = set(_clean_texts(major_claim_ids))
    if required_claims and required_claims.isdisjoint(claims):
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_claim_ref_missing",
            "Multiverse specification curve does not bind the required major claim.",
            "claim_ids",
        )
    normalized["claim_ids"] = claims
    _validate_portfolio_binding(
        normalized,
        portfolio_designs=tuple(portfolio_designs),
    )

    for field in (
        "specification_records",
        "defensible_specifications",
        "rejected_specifications",
        "result_distribution",
        "drivers_of_divergence",
        "claim_markers",
    ):
        _require_surface(
            record.get(field),
            field,
            f"policy_design_multiverse_{field}_missing",
        )
    normalized["previous_wave_refs"] = _validate_previous_wave_refs(
        record.get("previous_wave_refs"),
        portfolio_designs=tuple(portfolio_designs),
        evidence_lines=tuple(evidence_lines),
        independence_maps=tuple(independence_maps),
    )

    evidence_ref = _required_text(
        record.get("evidence_ref") or record.get("cas_ref"),
        "evidence_ref",
        "policy_design_multiverse_evidence_ref_missing",
    )
    if not _runtime_artifact_ref(evidence_ref):
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_evidence_ref_invalid",
            "Multiverse specification-curve evidence_ref must be a runtime artifact ref.",
            "evidence_ref",
        )
    normalized["evidence_ref"] = evidence_ref
    runtime_event_ref = _required_text(
        record.get("runtime_event_ref"),
        "runtime_event_ref",
        "policy_design_multiverse_runtime_event_ref_missing",
    )
    if not _runtime_event_ref(runtime_event_ref):
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_runtime_event_ref_invalid",
            "Multiverse specification curve must cite a runtime event ref.",
            "runtime_event_ref",
        )
    normalized["runtime_event_ref"] = runtime_event_ref

    raw_records = record.get("specification_records")
    if not isinstance(raw_records, Sequence) or isinstance(raw_records, str):
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_specification_records_invalid",
            "specification_records must be a sequence.",
            "specification_records",
        )
    records = _sorted_records(
        _validate_specification_record(item, index=index)
        for index, item in enumerate(raw_records)
    )
    if not records:
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_specification_records_missing",
            "Multiverse specification curve must include at least one specification record.",
            "specification_records",
        )
    normalized["specification_records"] = records

    source_counts = _source_kind_counts(records)
    for source_kind in REQUIRED_MULTIVERSE_SOURCE_KINDS:
        if source_counts.get(source_kind, 0) <= 0:
            raise MultiverseSpecificationCurveError(
                "policy_design_multiverse_required_source_missing",
                (
                    "Multiverse specification curve must project "
                    f"{_SOURCE_KIND_LABELS[source_kind]} outputs."
                ),
                "source_kind_counts",
            )
    normalized["source_kind_counts"] = source_counts

    normalized["defensible_specifications"] = _validate_specification_summaries(
        record.get("defensible_specifications"),
        records=records,
        expected_decision="defensible",
    )
    normalized["rejected_specifications"] = _validate_specification_summaries(
        record.get("rejected_specifications"),
        records=records,
        expected_decision="rejected",
    )
    normalized["result_distribution"] = _validate_distribution(
        record.get("result_distribution"),
        records=records,
    )
    normalized["drivers_of_divergence"] = _validate_divergence_rows(
        record.get("drivers_of_divergence")
    )
    normalized["claim_markers"] = _validate_claim_markers(
        record.get("claim_markers"),
        records=records,
        claim_ids=claims,
    )
    return normalized


def _project_output(
    output: object,
    *,
    source_kind: str,
    output_index: int,
    default_claim_ids: list[str],
    default_portfolio_id: str,
) -> list[dict[str, Any]]:
    payload = _as_mapping(output)
    raw_specification_ids = payload.get("specification_ids")
    raw_estimates = payload.get("estimates")
    bundled = raw_specification_ids is not None or (
        isinstance(raw_estimates, Sequence) and not isinstance(raw_estimates, str)
    )
    if bundled:
        specification_ids = _sequence_or_none(raw_specification_ids)
        estimates = _float_sequence_or_none(raw_estimates)
        standard_errors = _float_sequence_or_none(
            payload.get("standard_errors")
            or payload.get("se")
            or payload.get("std_errors")
        )
        if specification_ids is None or estimates is None:
            raise MultiverseSpecificationCurveError(
                "policy_design_multiverse_bundled_output_invalid",
                "Bundled outputs must include specification_ids and estimates.",
                "specification_ids",
            )
        if standard_errors is None:
            standard_errors = [0.0 for _ in specification_ids]
        if not (
            len(specification_ids) == len(estimates) == len(standard_errors)
        ):
            raise MultiverseSpecificationCurveError(
                "policy_design_multiverse_bundled_output_shape_mismatch",
                "Bundled specification_ids, estimates, and standard_errors must align.",
                "specification_ids",
            )
        records = []
        for bundle_index, specification_id in enumerate(specification_ids):
            item = dict(payload)
            item["specification_id"] = specification_id
            item["estimate"] = estimates[bundle_index]
            item["standard_error"] = standard_errors[bundle_index]
            item["_bundle_index"] = bundle_index
            records.append(
                _record_from_payload(
                    item,
                    source_kind=source_kind,
                    output_index=output_index,
                    default_claim_ids=default_claim_ids,
                    default_portfolio_id=default_portfolio_id,
                )
            )
        return records
    return [
        _record_from_payload(
            payload,
            source_kind=source_kind,
            output_index=output_index,
            default_claim_ids=default_claim_ids,
            default_portfolio_id=default_portfolio_id,
        )
    ]


def _record_from_payload(
    payload: Mapping[str, Any],
    *,
    source_kind: str,
    output_index: int,
    default_claim_ids: list[str],
    default_portfolio_id: str,
) -> dict[str, Any]:
    estimate = _required_float(
        _first_present(
            payload,
            "estimate",
            "effect_estimate",
            "estimated_effect",
            "coefficient",
            "mean_estimate",
        ),
        "estimate",
        "policy_design_multiverse_estimate_missing",
    )
    standard_error = _float(
        _first_present(payload, "standard_error", "se", "stderr", "std_error"),
        default=0.0,
    )
    decision = _decision(payload)
    specification_id = _required_text(
        _first_present(
            payload,
            "specification_id",
            "spec_id",
            "hypothesis_id",
            "scenario_id",
            "experiment_id",
            "run_id",
        )
        or f"{source_kind}-{output_index + 1}",
        "specification_id",
        "policy_design_multiverse_specification_id_missing",
    )
    claims = _claim_ids(
        claim_id=_text(payload.get("claim_id")),
        claim_ids=payload.get("claim_ids") or default_claim_ids,
    )
    rejection_reason = _text(
        payload.get("rejection_reason")
        or payload.get("reject_reason")
        or payload.get("failure_reason")
    )
    record: dict[str, Any] = {
        "specification_id": specification_id,
        "claim_ids": claims,
        "portfolio_id": _text(payload.get("portfolio_id")) or default_portfolio_id,
        "source_kind": source_kind,
        "decision": decision,
        "estimate": estimate,
        "standard_error": standard_error,
        "sign": _sign(estimate),
        "significant": _significant(estimate, standard_error),
        "drivers": _drivers(payload, source_kind=source_kind),
    }
    source_record_id = _text(
        _first_present(payload, "source_record_id", "experiment_id", "hypothesis_id", "scenario_id")
    )
    if source_record_id is not None:
        record["source_record_id"] = source_record_id
    evidence_ref = _text(
        _first_present(payload, "evidence_ref", "cas_ref", "source_ref", "producer_ref")
    )
    if evidence_ref is not None:
        record["evidence_ref"] = evidence_ref
    if rejection_reason is not None:
        record["rejection_reason"] = rejection_reason
    metadata = payload.get("metadata")
    if isinstance(metadata, Mapping) and metadata:
        record["metadata"] = dict(metadata)
    return _validate_specification_record(record, index=output_index)


def _validate_specification_record(value: object, *, index: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_specification_record_invalid",
            "Every specification record must be a mapping.",
            f"specification_records[{index}]",
        )
    record = dict(value)
    specification_id = _required_text(
        record.get("specification_id") or record.get("spec_id"),
        "specification_id",
        "policy_design_multiverse_specification_id_missing",
    )
    source_kind = _required_text(
        record.get("source_kind") or record.get("producer_kind"),
        "source_kind",
        "policy_design_multiverse_source_kind_missing",
    )
    if source_kind not in REQUIRED_MULTIVERSE_SOURCE_KINDS:
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_source_kind_invalid",
            "Specification record source_kind is not a supported multiverse producer.",
            "source_kind",
        )
    estimate = _required_float(
        record.get("estimate"),
        "estimate",
        "policy_design_multiverse_estimate_missing",
    )
    standard_error = _float(record.get("standard_error"), default=0.0)
    if standard_error < 0.0:
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_standard_error_invalid",
            "standard_error must be non-negative.",
            "standard_error",
        )
    decision = _text(record.get("decision")) or "defensible"
    if decision not in {"defensible", "rejected"}:
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_decision_invalid",
            "Specification decision must be defensible or rejected.",
            "decision",
        )
    rejection_reason = _text(record.get("rejection_reason"))
    if decision == "rejected" and rejection_reason is None:
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_rejection_reason_missing",
            "Rejected specifications must record a rejection reason.",
            "rejection_reason",
        )
    claim_ids = _claim_ids(
        claim_id=_text(record.get("claim_id")),
        claim_ids=record.get("claim_ids") or (),
    )
    if not claim_ids:
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_claim_ref_missing",
            "Specification records must bind at least one claim.",
            "claim_ids",
        )
    normalized = {
        **record,
        "specification_id": specification_id,
        "claim_ids": claim_ids,
        "source_kind": source_kind,
        "decision": decision,
        "estimate": estimate,
        "standard_error": standard_error,
        "sign": _sign(estimate),
        "significant": bool(record.get("significant", _significant(estimate, standard_error))),
        "drivers": _normalize_drivers(record.get("drivers")),
    }
    if rejection_reason is not None:
        normalized["rejection_reason"] = rejection_reason
    return normalized


def _validate_specification_summaries(
    value: object,
    *,
    records: list[dict[str, Any]],
    expected_decision: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise MultiverseSpecificationCurveError(
            f"policy_design_multiverse_{expected_decision}_specifications_invalid",
            f"{expected_decision}_specifications must be a sequence.",
            f"{expected_decision}_specifications",
        )
    expected_ids = {
        str(record["specification_id"])
        for record in records
        if record["decision"] == expected_decision
    }
    seen_ids: set[str] = set()
    summaries: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise MultiverseSpecificationCurveError(
                f"policy_design_multiverse_{expected_decision}_summary_invalid",
                "Specification summaries must be mappings.",
                f"{expected_decision}_specifications[{index}]",
            )
        specification_id = _required_text(
            item.get("specification_id") or item.get("spec_id"),
            "specification_id",
            "policy_design_multiverse_specification_id_missing",
        )
        if specification_id not in expected_ids:
            raise MultiverseSpecificationCurveError(
                f"policy_design_multiverse_{expected_decision}_summary_mismatch",
                (
                    f"{expected_decision}_specifications must correspond to "
                    "specification_records decisions."
                ),
                f"{expected_decision}_specifications[{index}]",
            )
        summary = dict(item)
        summary["specification_id"] = specification_id
        seen_ids.add(specification_id)
        summaries.append(summary)
    if seen_ids != expected_ids:
        raise MultiverseSpecificationCurveError(
            f"policy_design_multiverse_{expected_decision}_summary_missing",
            (
                f"{expected_decision}_specifications must enumerate all "
                f"{expected_decision} specification records."
            ),
            f"{expected_decision}_specifications",
        )
    return sorted(summaries, key=lambda item: str(item["specification_id"]))


def _validate_distribution(
    value: object,
    *,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_result_distribution_invalid",
            "result_distribution must be a mapping.",
            "result_distribution",
        )
    actual = _result_distribution(records)
    declared = dict(value)
    for field in (
        "n_specifications",
        "defensible_count",
        "rejected_count",
        "sign_counts",
    ):
        if declared.get(field) != actual[field]:
            raise MultiverseSpecificationCurveError(
                "policy_design_multiverse_result_distribution_mismatch",
                "result_distribution must summarize all specification records.",
                f"result_distribution.{field}",
            )
    return {**declared, **actual}


def _validate_divergence_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_divergence_rows_invalid",
            "drivers_of_divergence must be a sequence.",
            "drivers_of_divergence",
        )
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise MultiverseSpecificationCurveError(
                "policy_design_multiverse_divergence_row_invalid",
                "Every divergence row must be a mapping.",
                f"drivers_of_divergence[{index}]",
            )
        axis = _required_text(
            item.get("axis"),
            "axis",
            "policy_design_multiverse_divergence_axis_missing",
        )
        row = dict(item)
        row["axis"] = axis
        rows.append(row)
    return rows


def _validate_claim_markers(
    value: object,
    *,
    records: list[dict[str, Any]],
    claim_ids: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_claim_markers_invalid",
            "claim_markers must be a sequence.",
            "claim_markers",
        )
    markers: list[dict[str, Any]] = []
    seen_claims: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise MultiverseSpecificationCurveError(
                "policy_design_multiverse_claim_marker_invalid",
                "Every claim marker must be a mapping.",
                f"claim_markers[{index}]",
            )
        claim_id = _required_text(
            item.get("claim_id"),
            "claim_id",
            "policy_design_multiverse_claim_marker_claim_missing",
        )
        marker = _required_text(
            item.get("marker"),
            "marker",
            "policy_design_multiverse_claim_marker_missing",
        )
        if marker not in {"fragile", "robust"}:
            raise MultiverseSpecificationCurveError(
                "policy_design_multiverse_claim_marker_invalid",
                "Claim marker must be fragile or robust.",
                f"claim_markers[{index}].marker",
            )
        if marker == "robust" and _rejected_specs_diverge(records, claim_id=claim_id):
            raise MultiverseSpecificationCurveError(
                "policy_design_multiverse_cherry_picked_agreement",
                (
                    "A claim cannot be marked robust when rejected specifications "
                    "diverge from the agreeing defensible specifications."
                ),
                f"claim_markers[{index}]",
            )
        row = dict(item)
        row["claim_id"] = claim_id
        row["marker"] = marker
        reason_codes = row.get("reason_codes")
        row["reason_codes"] = (
            [str(item) for item in reason_codes]
            if isinstance(reason_codes, Sequence) and not isinstance(reason_codes, str)
            else []
        )
        markers.append(row)
        seen_claims.add(claim_id)
    missing_claims = set(claim_ids) - seen_claims
    if missing_claims:
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_claim_marker_missing",
            "Every claim in the multiverse curve must have a fragile/robust marker.",
            "claim_markers",
        )
    return sorted(markers, key=lambda item: str(item["claim_id"]))


def _result_distribution(records: list[dict[str, Any]]) -> dict[str, Any]:
    estimates = [float(record["estimate"]) for record in records]
    signs = Counter(str(record["sign"]) for record in records)
    return {
        "n_specifications": len(records),
        "defensible_count": sum(1 for record in records if record["decision"] == "defensible"),
        "rejected_count": sum(1 for record in records if record["decision"] == "rejected"),
        "sign_counts": {
            "positive": signs.get("positive", 0),
            "negative": signs.get("negative", 0),
            "zero": signs.get("zero", 0),
        },
        "estimate_min": min(estimates),
        "estimate_max": max(estimates),
        "estimate_median": float(median(estimates)),
        "share_significant": (
            sum(1 for record in records if record.get("significant")) / max(len(records), 1)
        ),
    }


def _drivers_of_divergence(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_axis: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for record in records:
        drivers = dict(record.get("drivers") or {})
        drivers["source_kind"] = record["source_kind"]
        for axis, raw_value in drivers.items():
            for value in _driver_values(raw_value):
                by_axis[str(axis)][value].append(record)

    rows: list[dict[str, Any]] = []
    for axis, value_records in by_axis.items():
        if len(value_records) <= 1:
            continue
        sign_counts_by_value = {
            value: dict(Counter(str(record["sign"]) for record in axis_records))
            for value, axis_records in value_records.items()
        }
        axis_signs = {
            sign
            for counts in sign_counts_by_value.values()
            for sign, count in counts.items()
            if count > 0
        }
        rows.append(
            {
                "axis": axis,
                "values": sorted(value_records),
                "sign_counts_by_value": sign_counts_by_value,
                "divergence_signal": (
                    "mixed_signs" if len(axis_signs - {"zero"}) > 1 else "distribution_shift"
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            _DRIVER_AXIS_ORDER.index(str(row["axis"]))
            if row["axis"] in _DRIVER_AXIS_ORDER
            else len(_DRIVER_AXIS_ORDER),
            str(row["axis"]),
        ),
    )


def _claim_markers(records: list[dict[str, Any]], claim_ids: list[str]) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    for claim_id in claim_ids:
        claim_records = [
            record for record in records if claim_id in set(record.get("claim_ids") or [])
        ]
        defensible = [
            record for record in claim_records if record["decision"] == "defensible"
        ]
        defensible_signs = {
            str(record["sign"]) for record in defensible if record["sign"] != "zero"
        }
        reason_codes: list[str] = []
        marker = "robust"
        if len(defensible) < 2:
            marker = "fragile"
            reason_codes.append("insufficient_defensible_specifications")
        if len(defensible_signs) > 1:
            marker = "fragile"
            reason_codes.append("defensible_specifications_diverge")
        if _rejected_specs_diverge(records, claim_id=claim_id):
            marker = "fragile"
            reason_codes.append("rejected_specifications_diverge")
        if marker == "robust":
            reason_codes.append("defensible_specifications_agree")
        markers.append(
            {
                "claim_id": claim_id,
                "marker": marker,
                "reason_codes": sorted(dict.fromkeys(reason_codes)),
            }
        )
    return markers


def _rejected_specs_diverge(records: list[dict[str, Any]], *, claim_id: str) -> bool:
    defensible_signs = {
        str(record["sign"])
        for record in records
        if record["decision"] == "defensible"
        and claim_id in set(record.get("claim_ids") or [])
        and record["sign"] != "zero"
    }
    rejected_signs = {
        str(record["sign"])
        for record in records
        if record["decision"] == "rejected"
        and claim_id in set(record.get("claim_ids") or [])
        and record["sign"] != "zero"
    }
    if not defensible_signs or len(defensible_signs) > 1:
        return bool(rejected_signs)
    return bool(rejected_signs - defensible_signs)


def _source_kind_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(record["source_kind"]) for record in records)
    return {kind: counts[kind] for kind in sorted(counts)}


def _specification_summaries(
    records: list[dict[str, Any]],
    *,
    decision: str,
) -> list[dict[str, Any]]:
    summaries = [
        {
            "specification_id": record["specification_id"],
            "source_kind": record["source_kind"],
            "estimate": record["estimate"],
            "standard_error": record["standard_error"],
            **(
                {"rejection_reason": record["rejection_reason"]}
                if decision == "rejected" and record.get("rejection_reason")
                else {}
            ),
        }
        for record in records
        if record["decision"] == decision
    ]
    return sorted(summaries, key=lambda item: str(item["specification_id"]))


def _sorted_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [dict(record) for record in records],
        key=lambda record: (str(record["source_kind"]), str(record["specification_id"])),
    )


def _drivers(payload: Mapping[str, Any], *, source_kind: str) -> dict[str, Any]:
    drivers: dict[str, Any] = {}
    raw_drivers = payload.get("drivers")
    if isinstance(raw_drivers, Mapping):
        drivers.update(_normalize_drivers(raw_drivers))
    metadata = payload.get("metadata")
    if isinstance(metadata, Mapping):
        for key in _DRIVER_AXIS_ORDER:
            if key in metadata and key not in drivers:
                drivers[key] = metadata[key]
    for key in _DRIVER_AXIS_ORDER:
        if key in payload and key not in drivers:
            drivers[key] = payload[key]
    axes = payload.get("sensitivity_axes")
    if axes and "sensitivity_axes" not in drivers:
        drivers["sensitivity_axes"] = axes
    drivers.setdefault("source_family", source_kind)
    return _normalize_drivers(drivers)


def _normalize_drivers(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    drivers: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = _text(raw_key)
        if key is None:
            continue
        if isinstance(raw_value, Mapping):
            continue
        if isinstance(raw_value, Sequence) and not isinstance(raw_value, str):
            values = [str(item) for item in raw_value if _text(item) is not None]
            if values:
                drivers[key] = values
        else:
            text = _text(raw_value)
            if text is not None:
                drivers[key] = text
    return drivers


def _decision(payload: Mapping[str, Any]) -> str:
    raw = _text(
        _first_present(payload, "decision", "status", "verdict", "result_status")
    )
    if _text(payload.get("rejection_reason")) is not None:
        return "rejected"
    if raw is not None:
        lowered = raw.casefold()
        if lowered in _REJECTED_DECISIONS:
            return "rejected"
        if lowered in _DEFENSIBLE_DECISIONS:
            return "defensible"
    if payload.get("accepted") is False:
        return "rejected"
    return "defensible"


def _claim_ids(*, claim_id: str | None, claim_ids: object) -> list[str]:
    values: list[str] = []
    if claim_id is not None:
        values.append(claim_id)
    if isinstance(claim_ids, str):
        values.append(claim_ids)
    elif isinstance(claim_ids, Iterable):
        values.extend(str(item) for item in claim_ids if _text(item) is not None)
    return sorted(dict.fromkeys(value for value in values if _text(value) is not None))


def _clean_texts(values: Iterable[object]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = _text(value)
        if text is not None:
            cleaned.append(text)
    return sorted(dict.fromkeys(cleaned))


def _validate_portfolio_binding(
    record: Mapping[str, Any],
    *,
    portfolio_designs: Sequence[Mapping[str, Any]],
) -> None:
    if not portfolio_designs:
        return
    portfolio_id = _required_text(
        record.get("portfolio_id"),
        "portfolio_id",
        "policy_design_multiverse_portfolio_id_missing",
    )
    claim_ids = set(_text_values(record.get("claim_ids")))
    for design in portfolio_designs:
        if portfolio_id not in _row_refs(
            design,
            (
                "portfolio_id",
                "portfolio_design_id",
                "design_id",
                "record_id",
                "id",
                "cas_ref",
                "evidence_ref",
            ),
        ):
            continue
        design_claims = set(
            _text_values(
                design.get("claim_ids")
                or design.get("major_claim_ids")
                or design.get("claim_id")
                or design.get("major_claim_id")
            )
        )
        if not claim_ids or not design_claims or not claim_ids.isdisjoint(design_claims):
            return
    raise MultiverseSpecificationCurveError(
        "policy_design_multiverse_portfolio_binding_missing",
        "Multiverse specification curve must bind a predeclared portfolio design.",
        "portfolio_id",
    )


def _validate_previous_wave_refs(
    value: object,
    *,
    portfolio_designs: Sequence[Mapping[str, Any]] = (),
    evidence_lines: Sequence[Mapping[str, Any]] = (),
    independence_maps: Sequence[Mapping[str, Any]] = (),
) -> dict[str, list[str]]:
    if not isinstance(value, Mapping):
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_previous_wave_refs_missing",
            (
                "Multiverse specification curve must cite previous-wave portfolio, "
                "evidence-line, and independence-map refs."
            ),
            "previous_wave_refs",
        )
    normalized = {
        "portfolio_design_refs": _required_previous_refs(
            value,
            (
                "portfolio_design_refs",
                "portfolio_refs",
                "evidence_portfolio_refs",
            ),
            code="policy_design_multiverse_previous_wave_portfolio_refs_missing",
            field="previous_wave_refs.portfolio_design_refs",
        ),
        "evidence_line_refs": _required_previous_refs(
            value,
            ("evidence_line_refs", "line_refs", "portfolio_evidence_line_refs"),
            code="policy_design_multiverse_previous_wave_evidence_line_refs_missing",
            field="previous_wave_refs.evidence_line_refs",
        ),
        "independence_map_refs": _required_previous_refs(
            value,
            (
                "independence_map_refs",
                "evidence_independence_map_refs",
                "independence_refs",
            ),
            code="policy_design_multiverse_previous_wave_independence_refs_missing",
            field="previous_wave_refs.independence_map_refs",
        ),
    }
    _reject_wave18_phase_refs(normalized)
    _validate_refs_resolve(
        normalized["portfolio_design_refs"],
        rows=portfolio_designs,
        keys=(
            "portfolio_id",
            "portfolio_design_id",
            "design_id",
            "record_id",
            "id",
            "cas_ref",
            "evidence_ref",
        ),
        field="previous_wave_refs.portfolio_design_refs",
    )
    _validate_refs_resolve(
        normalized["evidence_line_refs"],
        rows=evidence_lines,
        keys=("line_id", "evidence_line_id", "record_id", "id", "cas_ref", "evidence_ref"),
        field="previous_wave_refs.evidence_line_refs",
    )
    _validate_refs_resolve(
        normalized["independence_map_refs"],
        rows=independence_maps,
        keys=("map_id", "independence_map_id", "record_id", "id", "cas_ref", "evidence_ref"),
        field="previous_wave_refs.independence_map_refs",
    )
    return normalized


def _required_previous_refs(
    mapping: Mapping[str, object],
    keys: Sequence[str],
    *,
    code: str,
    field: str,
) -> list[str]:
    refs: list[str] = []
    for key in keys:
        refs.extend(_text_values(mapping.get(key)))
    if not refs:
        raise MultiverseSpecificationCurveError(
            code,
            f"Multiverse specification curve must include {field}.",
            field,
        )
    return list(dict.fromkeys(refs))


def _reject_wave18_phase_refs(refs_by_field: Mapping[str, Sequence[str]]) -> None:
    wave18_tokens = ("multiverse", "specification_curve", "disconfirming")
    for field, refs in refs_by_field.items():
        for ref in refs:
            lowered = ref.casefold()
            if any(token in lowered for token in wave18_tokens):
                raise MultiverseSpecificationCurveError(
                    "policy_design_multiverse_wave18_phase_dependency",
                    "Wave 18 multiverse records cannot depend on Wave 18 phase refs.",
                    f"previous_wave_refs.{field}",
                )


def _validate_refs_resolve(
    refs: Sequence[str],
    *,
    rows: Sequence[Mapping[str, Any]],
    keys: Sequence[str],
    field: str,
) -> None:
    if not rows:
        return
    index = {ref for row in rows for ref in _row_refs(row, keys)}
    unresolved = [ref for ref in refs if ref not in index]
    if unresolved:
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_previous_wave_ref_unresolved",
            "Multiverse previous-wave refs must resolve to supplied previous-wave rows.",
            field,
        )


def _row_refs(row: Mapping[str, Any], keys: Sequence[str]) -> set[str]:
    refs: set[str] = set()
    for key in keys:
        refs.update(_text_values(row.get(key)))
    return refs


def _text_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = _text(value)
        return (text,) if text is not None else ()
    if isinstance(value, Mapping):
        values: list[str] = []
        for key in (
            "portfolio_id",
            "portfolio_design_id",
            "line_id",
            "evidence_line_id",
            "map_id",
            "independence_map_id",
            "claim_id",
            "major_claim_id",
            "id",
            "ref",
            "value",
        ):
            text = _text(value.get(key))
            if text is not None:
                values.append(text)
        return tuple(dict.fromkeys(values))
    if isinstance(value, Iterable):
        values: list[str] = []
        for item in value:
            values.extend(_text_values(item))
        return tuple(dict.fromkeys(values))
    return ()


def _require_surface(value: object, field: str, code: str) -> None:
    if value is None:
        raise MultiverseSpecificationCurveError(
            code,
            f"Multiverse specification-curve record must include {field}.",
            field,
        )
    if isinstance(value, Mapping) and not value:
        raise MultiverseSpecificationCurveError(
            code,
            f"Multiverse specification-curve record must include non-empty {field}.",
            field,
        )


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, Mapping):
            return dumped
    raise MultiverseSpecificationCurveError(
        "policy_design_multiverse_source_output_invalid",
        "Source outputs must be mappings or pydantic-style models.",
    )


def _first_present(mapping: Mapping[str, Any], *keys: str) -> object | None:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or any(char in text for char in "\r\n\t"):
        return None
    return text


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


def _required_text(value: object, field: str, code: str) -> str:
    text = _text(value)
    if text is None:
        raise MultiverseSpecificationCurveError(
            code,
            f"Multiverse specification-curve field {field} is required.",
            field,
        )
    return text


def _float(value: object, *, default: float) -> float:
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_number_invalid",
            "Numeric multiverse fields must be finite numbers.",
        ) from exc
    if not math.isfinite(number):
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_number_invalid",
            "Numeric multiverse fields must be finite numbers.",
        )
    return number


def _required_float(value: object, field: str, code: str) -> float:
    if value is None:
        raise MultiverseSpecificationCurveError(
            code,
            f"Multiverse specification-curve field {field} is required.",
            field,
        )
    return _float(value, default=0.0)


def _sequence_or_none(value: object) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_sequence_invalid",
            "Bundled multiverse fields must be sequences.",
        )
    return [
        _required_text(
            item,
            "specification_ids",
            "policy_design_multiverse_specification_id_missing",
        )
        for item in value
    ]


def _float_sequence_or_none(value: object) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise MultiverseSpecificationCurveError(
            "policy_design_multiverse_sequence_invalid",
            "Bundled multiverse fields must be sequences.",
        )
    return [
        _required_float(item, "estimate", "policy_design_multiverse_estimate_missing")
        for item in value
    ]


def _driver_values(value: object) -> list[str]:
    if isinstance(value, Sequence) and not isinstance(value, str):
        return sorted(str(item) for item in value if _text(item) is not None)
    text = _text(value)
    return [] if text is None else [text]


def _sign(value: float) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "zero"


def _significant(estimate: float, standard_error: float) -> bool:
    return standard_error > 0.0 and abs(estimate / standard_error) > 1.96


__all__ = [
    "MULTIVERSE_SPECIFICATION_CURVE_CONTRACT_ID",
    "MULTIVERSE_SPECIFICATION_CURVE_SCHEMA_VERSION",
    "REQUIRED_MULTIVERSE_SOURCE_KINDS",
    "MultiverseSpecificationCurveError",
    "build_multiverse_specification_curve_record",
    "validate_multiverse_specification_curve_record",
]
