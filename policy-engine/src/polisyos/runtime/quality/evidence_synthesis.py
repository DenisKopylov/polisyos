"""Evidence synthesis reports for Policy Design Case evidence portfolios."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

EVIDENCE_SYNTHESIS_REPORT_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.evidence_synthesis_report.v1"
)
EVIDENCE_SYNTHESIS_REPORT_CONTRACT_ID = (
    "policy_design_case.evidence_synthesis_report.v1"
)

_VALID_DIRECTIONS = frozenset({"positive", "negative", "zero"})
_VALID_DIVERGENCE_STATUSES = frozenset({"convergent", "divergent", "blocked"})
_VALID_SATURATION_STATUSES = frozenset({"saturated", "not_saturated", "blocked"})


@dataclass(frozen=True)
class EvidenceSynthesisReportError(ValueError):
    """Fail-closed evidence-synthesis report contract violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def build_evidence_synthesis_report(
    *,
    report_id: str,
    portfolio_id: str,
    multiverse_curve: Mapping[str, Any],
    claim_id: str | None = None,
    claim_ids: Iterable[str] = (),
    disconfirming_ledgers: Iterable[Mapping[str, Any]] = (),
    primary_synthesis_rule: Mapping[str, Any],
    sensitivity_synthesis_rules: Iterable[Mapping[str, Any]],
    heterogeneity_model: Mapping[str, Any],
    certainty_framework: Mapping[str, Any],
    publication_bias_treatment: Mapping[str, Any],
    inclusion_policy: Mapping[str, Any],
    exclusion_policy: Mapping[str, Any],
    information_saturation: Mapping[str, Any],
    run_cost_proportionality: Mapping[str, Any],
    divergence_evidence: Iterable[Mapping[str, Any]] = (),
    blockers: Iterable[Mapping[str, Any]] = (),
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
    previous_wave_refs: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Build a synthesis report from multiverse records and synthesis rules."""

    curve = _as_mapping(multiverse_curve)
    records = _sequence_of_mappings(curve.get("specification_records"))
    if not records:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_specification_records_missing",
            "Evidence synthesis requires multiverse specification records.",
            "multiverse_curve.specification_records",
        )
    claims = _claim_ids(claim_id=claim_id, claim_ids=claim_ids or curve.get("claim_ids") or ())
    portfolio_id = _required_text(
        portfolio_id,
        "portfolio_id",
        "policy_design_synthesis_portfolio_id_missing",
    )
    primary = _apply_synthesis_rule(records, primary_synthesis_rule)
    sensitivity_rows = [
        {
            **_apply_synthesis_rule(records, rule),
            "reasonable": bool(rule.get("reasonable", True)),
        }
        for rule in sensitivity_synthesis_rules
    ]
    for row in sensitivity_rows:
        row["direction_changed"] = row["direction"] != primary["direction"]

    divergence_required = _sensitivity_direction_changed(sensitivity_rows) or _records_mixed_sign(
        records, claim_ids=claims
    )
    divergence_status = "divergent" if divergence_required else "convergent"
    ledger_rows = tuple(_as_mapping(row) for row in disconfirming_ledgers)
    normalized_previous_wave_refs = (
        _validate_previous_wave_refs(previous_wave_refs)
        if previous_wave_refs is not None
        else _previous_wave_refs_from_inputs(
            curve=curve,
            disconfirming_ledgers=ledger_rows,
        )
    )
    divergence_rows = tuple(_as_mapping(row) for row in divergence_evidence)
    saturation = dict(information_saturation)
    payload: dict[str, Any] = {
        "schema_version": EVIDENCE_SYNTHESIS_REPORT_SCHEMA_VERSION,
        "contract_id": EVIDENCE_SYNTHESIS_REPORT_CONTRACT_ID,
        "report_id": _required_text(
            report_id,
            "report_id",
            "policy_design_synthesis_report_id_missing",
        ),
        "claim_ids": claims,
        "portfolio_id": portfolio_id,
        "multiverse_curve_refs": _refs_for_rows(
            (curve,),
            ("curve_id", "multiverse_curve_id", "record_id", "id", "evidence_ref"),
        ),
        "disconfirming_ledger_refs": _refs_for_rows(
            ledger_rows,
            (
                "ledger_id",
                "disconfirming_ledger_id",
                "record_id",
                "id",
                "evidence_ref",
            ),
        ),
        "weighting_model": _weighting_model(primary_synthesis_rule),
        "heterogeneity_model": dict(heterogeneity_model),
        "certainty_framework": dict(certainty_framework),
        "publication_bias_treatment": dict(publication_bias_treatment),
        "inclusion_policy": dict(inclusion_policy),
        "exclusion_policy": dict(exclusion_policy),
        "synthesis_estimate": primary,
        "claim_direction": primary["direction"],
        "sensitivity_to_synthesis_rules": sensitivity_rows,
        "information_saturation": saturation,
        "effective_evidence_mass": _build_effective_evidence_mass(
            information_saturation=saturation,
            disconfirming_ledgers=ledger_rows,
        ),
        "run_cost_proportionality": dict(run_cost_proportionality),
        "divergence_assessment": {
            "status": divergence_status,
            "reason_codes": (
                ["synthesis_rule_direction_change"]
                if divergence_required
                else ["reasonable_synthesis_rules_preserve_direction"]
            ),
        },
        "divergence_evidence": [dict(row) for row in divergence_rows],
        "blockers": [dict(row) for row in blockers],
        "previous_wave_refs": normalized_previous_wave_refs,
    }
    if evidence_ref is not None:
        payload["evidence_ref"] = str(evidence_ref)
    if runtime_event_ref is not None:
        payload["runtime_event_ref"] = str(runtime_event_ref)
    return validate_evidence_synthesis_report_record(payload)


def validate_evidence_synthesis_report_record(
    record: Mapping[str, Any],
    *,
    multiverse_curves: Iterable[Mapping[str, Any]] = (),
    disconfirming_ledgers: Iterable[Mapping[str, Any]] = (),
    major_claim_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Validate and normalize one evidence-synthesis report record."""

    if not isinstance(record, Mapping):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_report_invalid",
            "Evidence synthesis report must be a mapping.",
        )

    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_synthesis_schema_version_missing",
    )
    if schema_version != EVIDENCE_SYNTHESIS_REPORT_SCHEMA_VERSION:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_schema_version_invalid",
            "Evidence synthesis report must use the runtime-quality synthesis schema.",
            "schema_version",
        )
    normalized["schema_version"] = EVIDENCE_SYNTHESIS_REPORT_SCHEMA_VERSION
    normalized["contract_id"] = (
        _text(record.get("contract_id")) or EVIDENCE_SYNTHESIS_REPORT_CONTRACT_ID
    )
    normalized["report_id"] = synthesis_report_record_id(record)
    normalized["portfolio_id"] = _required_text(
        record.get("portfolio_id") or record.get("portfolio_ref"),
        "portfolio_id",
        "policy_design_synthesis_portfolio_id_missing",
    )
    claim_ids = _claim_ids(
        claim_id=_text(record.get("claim_id") or record.get("major_claim_id")),
        claim_ids=record.get("claim_ids") or record.get("major_claim_ids") or (),
    )
    if not claim_ids:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_claim_ref_missing",
            "Evidence synthesis report must bind at least one major claim.",
            "claim_ids",
        )
    required_claims = set(_clean_texts(major_claim_ids))
    if required_claims and required_claims.isdisjoint(claim_ids):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_claim_ref_missing",
            "Evidence synthesis report does not bind the required major claim.",
            "claim_ids",
        )
    normalized["claim_ids"] = claim_ids

    for field, code in _REQUIRED_SURFACES.items():
        _require_surface(record.get(field), field, code)

    normalized["weighting_model"] = _validate_weighting_model(record.get("weighting_model"))
    normalized["heterogeneity_model"] = _validate_named_mapping(
        record.get("heterogeneity_model"),
        field="heterogeneity_model",
        name_key="model",
        code="policy_design_synthesis_heterogeneity_model_invalid",
    )
    normalized["certainty_framework"] = _validate_named_mapping(
        record.get("certainty_framework"),
        field="certainty_framework",
        name_key="framework",
        code="policy_design_synthesis_certainty_framework_invalid",
    )
    normalized["publication_bias_treatment"] = _validate_named_mapping(
        record.get("publication_bias_treatment"),
        field="publication_bias_treatment",
        name_key="status",
        code="policy_design_synthesis_publication_bias_treatment_invalid",
    )
    normalized["inclusion_policy"] = _validate_named_mapping(
        record.get("inclusion_policy"),
        field="inclusion_policy",
        name_key="policy_id",
        code="policy_design_synthesis_inclusion_policy_invalid",
    )
    normalized["exclusion_policy"] = _validate_named_mapping(
        record.get("exclusion_policy"),
        field="exclusion_policy",
        name_key="policy_id",
        code="policy_design_synthesis_exclusion_policy_invalid",
    )

    synthesis_estimate = _validate_synthesis_estimate(record.get("synthesis_estimate"))
    claim_direction = _required_text(
        record.get("claim_direction") or synthesis_estimate.get("direction"),
        "claim_direction",
        "policy_design_synthesis_claim_direction_missing",
    )
    if claim_direction not in _VALID_DIRECTIONS:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_claim_direction_invalid",
            "claim_direction must be positive, negative, or zero.",
            "claim_direction",
        )
    if synthesis_estimate["direction"] != claim_direction:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_claim_direction_mismatch",
            "claim_direction must match synthesis_estimate.direction.",
            "claim_direction",
        )
    normalized["synthesis_estimate"] = synthesis_estimate
    normalized["claim_direction"] = claim_direction
    normalized["sensitivity_to_synthesis_rules"] = _validate_sensitivity_rows(
        record.get("sensitivity_to_synthesis_rules"),
        claim_direction=claim_direction,
    )
    normalized["information_saturation"] = _validate_information_saturation(
        record.get("information_saturation")
    )
    normalized["effective_evidence_mass"] = _validate_effective_evidence_mass(
        record.get("effective_evidence_mass"),
        information_saturation=normalized["information_saturation"],
    )
    normalized["run_cost_proportionality"] = _validate_run_cost_proportionality(
        record.get("run_cost_proportionality")
    )
    normalized["previous_wave_refs"] = _validate_previous_wave_refs(
        record.get("previous_wave_refs")
    )

    evidence_ref = _required_text(
        record.get("evidence_ref") or record.get("cas_ref"),
        "evidence_ref",
        "policy_design_synthesis_evidence_ref_missing",
    )
    if not _runtime_artifact_ref(evidence_ref):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_evidence_ref_invalid",
            "Evidence synthesis report evidence_ref must be a runtime artifact ref.",
            "evidence_ref",
        )
    normalized["evidence_ref"] = evidence_ref
    runtime_event_ref = _required_text(
        record.get("runtime_event_ref"),
        "runtime_event_ref",
        "policy_design_synthesis_runtime_event_ref_missing",
    )
    if not _runtime_event_ref(runtime_event_ref):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_runtime_event_ref_invalid",
            "Evidence synthesis report must cite a runtime event ref.",
            "runtime_event_ref",
        )
    normalized["runtime_event_ref"] = runtime_event_ref

    normalized["multiverse_curve_refs"] = _text_values(
        record.get("multiverse_curve_refs")
        or record.get("multiverse_report_refs")
        or record.get("multiverse_curve_ref")
    )
    normalized["disconfirming_ledger_refs"] = _text_values(
        record.get("disconfirming_ledger_refs")
        or record.get("disconfirming_evidence_ledger_refs")
        or record.get("disconfirming_ledger_ref")
    )
    _validate_external_bindings(
        normalized,
        multiverse_curves=tuple(multiverse_curves),
        disconfirming_ledgers=tuple(disconfirming_ledgers),
    )

    normalized["divergence_assessment"] = _validate_divergence_assessment(
        record.get("divergence_assessment")
    )
    normalized["divergence_evidence"] = _validate_divergence_evidence(
        record.get("divergence_evidence") or ()
    )
    normalized["blockers"] = _validate_blockers(record.get("blockers") or ())
    if _divergence_must_be_represented(
        normalized,
        multiverse_curves=tuple(multiverse_curves),
    ):
        has_divergence_evidence = bool(normalized["divergence_evidence"])
        has_blocker = bool(normalized["blockers"])
        if (
            normalized["divergence_assessment"]["status"] == "convergent"
            or not (has_divergence_evidence or has_blocker)
        ):
            raise EvidenceSynthesisReportError(
                "policy_design_synthesis_divergence_evidence_missing",
                (
                    "Evidence disagreement or synthesis-rule direction changes must "
                    "be represented as divergence evidence or a blocker."
                ),
                "divergence_evidence",
            )
    return normalized


def synthesis_report_record_id(record: Mapping[str, Any]) -> str:
    """Return the stable identity for an evidence-synthesis report."""

    return _required_text(
        record.get("report_id")
        or record.get("synthesis_report_id")
        or record.get("record_id")
        or record.get("id"),
        "report_id",
        "policy_design_synthesis_report_id_missing",
    )


def evidence_synthesis_refs_by_claim(
    reports: Iterable[Mapping[str, Any]],
) -> dict[str, list[str]]:
    """Project synthesis report records onto the claim evidence-graph ref axis."""

    refs_by_claim: dict[str, list[str]] = {}
    for record in reports:
        if not isinstance(record, Mapping):
            continue
        try:
            report_id = synthesis_report_record_id(record)
        except EvidenceSynthesisReportError:
            continue
        for claim_id in _text_values(record.get("claim_ids") or record.get("claim_id")):
            refs = refs_by_claim.setdefault(claim_id, [])
            if report_id not in refs:
                refs.append(report_id)
    return refs_by_claim


_REQUIRED_SURFACES = {
    "effective_evidence_mass": "policy_design_synthesis_effective_mass_missing",
    "weighting_model": "policy_design_synthesis_weighting_model_missing",
    "heterogeneity_model": "policy_design_synthesis_heterogeneity_model_missing",
    "certainty_framework": "policy_design_synthesis_certainty_framework_missing",
    "publication_bias_treatment": (
        "policy_design_synthesis_publication_bias_treatment_missing"
    ),
    "inclusion_policy": "policy_design_synthesis_inclusion_policy_missing",
    "exclusion_policy": "policy_design_synthesis_exclusion_policy_missing",
    "sensitivity_to_synthesis_rules": (
        "policy_design_synthesis_rule_sensitivity_missing"
    ),
    "information_saturation": "policy_design_synthesis_information_saturation_missing",
    "run_cost_proportionality": "policy_design_synthesis_run_cost_missing",
    "divergence_assessment": "policy_design_synthesis_divergence_assessment_missing",
}


def _apply_synthesis_rule(
    records: Sequence[Mapping[str, Any]],
    rule: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(rule, Mapping):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_rule_invalid",
            "Synthesis rules must be mappings.",
            "synthesis_rules",
        )
    rule_id = _required_text(
        rule.get("rule_id") or rule.get("id") or rule.get("name"),
        "rule_id",
        "policy_design_synthesis_rule_id_missing",
    )
    weighting = _required_text(
        rule.get("weighting") or rule.get("strategy") or "equal",
        "weighting",
        "policy_design_synthesis_weighting_missing",
    )
    included_decisions = set(_text_values(rule.get("included_decisions"))) or {"defensible"}
    significant_only = bool(rule.get("significant_only", False))
    source_kind_weights = (
        dict(rule.get("source_kind_weights"))
        if isinstance(rule.get("source_kind_weights"), Mapping)
        else {}
    )
    included: list[tuple[Mapping[str, Any], float]] = []
    for record in records:
        decision = _text(record.get("decision")) or "defensible"
        if decision not in included_decisions:
            continue
        if significant_only and not bool(record.get("significant")):
            continue
        weight = _record_weight(record, weighting=weighting)
        source_kind = _text(record.get("source_kind"))
        if source_kind and source_kind in source_kind_weights:
            weight *= _float(source_kind_weights[source_kind], field="source_kind_weights")
        if weight <= 0.0:
            continue
        included.append((record, weight))
    if not included:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_rule_no_included_records",
            "Synthesis rule must include at least one specification record.",
            "synthesis_rules",
        )
    total_weight = sum(weight for _, weight in included)
    estimate = sum(
        _float(record.get("estimate"), field="estimate") * weight
        for record, weight in included
    )
    estimate = estimate / total_weight
    return {
        "rule_id": rule_id,
        "weighting": weighting,
        "included_decisions": sorted(included_decisions),
        "estimate": estimate,
        "direction": _sign(estimate),
        "included_specification_ids": [
            _required_text(
                record.get("specification_id") or record.get("spec_id"),
                "specification_id",
                "policy_design_synthesis_specification_id_missing",
            )
            for record, _ in sorted(
                included,
                key=lambda item: str(
                    item[0].get("specification_id") or item[0].get("spec_id")
                ),
            )
        ],
        "total_weight": total_weight,
    }


def _record_weight(record: Mapping[str, Any], *, weighting: str) -> float:
    if weighting == "equal":
        return 1.0
    if weighting == "inverse_variance":
        standard_error = _float(record.get("standard_error"), field="standard_error", default=0.0)
        return 1.0 / max(standard_error * standard_error, 1e-12) if standard_error > 0 else 1.0
    if weighting == "quality_weight":
        quality = _float(
            record.get("quality_weight") or record.get("weight") or 1.0,
            field="quality_weight",
            default=1.0,
        )
        return max(quality, 0.0)
    raise EvidenceSynthesisReportError(
        "policy_design_synthesis_weighting_strategy_invalid",
        "Synthesis weighting must be equal, inverse_variance, or quality_weight.",
        "weighting_model.strategy",
    )


def _weighting_model(rule: Mapping[str, Any]) -> dict[str, Any]:
    model = {
        "strategy": _text(rule.get("weighting") or rule.get("strategy")) or "equal",
        "rule_id": _text(rule.get("rule_id") or rule.get("id") or rule.get("name")),
        "included_decisions": _text_values(rule.get("included_decisions")) or ["defensible"],
    }
    if isinstance(rule.get("source_kind_weights"), Mapping):
        model["source_kind_weights"] = dict(rule["source_kind_weights"])
    return model


def _validate_weighting_model(value: object) -> dict[str, Any]:
    row = _validate_named_mapping(
        value,
        field="weighting_model",
        name_key="strategy",
        code="policy_design_synthesis_weighting_model_invalid",
    )
    strategy = str(row["strategy"])
    if strategy not in {"equal", "inverse_variance", "quality_weight"}:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_weighting_strategy_invalid",
            "Synthesis weighting must be equal, inverse_variance, or quality_weight.",
            "weighting_model.strategy",
        )
    return row


def _validate_named_mapping(
    value: object,
    *,
    field: str,
    name_key: str,
    code: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise EvidenceSynthesisReportError(
            code,
            f"Evidence synthesis report must include non-empty {field}.",
            field,
        )
    row = dict(value)
    if _text(row.get(name_key)) is None:
        raise EvidenceSynthesisReportError(
            code,
            f"Evidence synthesis {field} must include {name_key}.",
            f"{field}.{name_key}",
        )
    return row


def _validate_synthesis_estimate(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_estimate_missing",
            "Evidence synthesis report must include synthesis_estimate.",
            "synthesis_estimate",
        )
    row = dict(value)
    row["rule_id"] = _required_text(
        row.get("rule_id"),
        "rule_id",
        "policy_design_synthesis_rule_id_missing",
    )
    estimate = _float(row.get("estimate"), field="synthesis_estimate.estimate")
    row["estimate"] = estimate
    direction = _required_text(
        row.get("direction"),
        "direction",
        "policy_design_synthesis_direction_missing",
    )
    if direction not in _VALID_DIRECTIONS:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_direction_invalid",
            "Synthesis direction must be positive, negative, or zero.",
            "synthesis_estimate.direction",
        )
    if direction != _sign(estimate):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_direction_mismatch",
            "Synthesis estimate direction must match its numeric estimate.",
            "synthesis_estimate.direction",
        )
    included_ids = _text_values(row.get("included_specification_ids"))
    if not included_ids:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_included_specifications_missing",
            "Synthesis estimate must list included specification ids.",
            "synthesis_estimate.included_specification_ids",
        )
    row["included_specification_ids"] = included_ids
    row["total_weight"] = _float(row.get("total_weight"), field="total_weight", default=0.0)
    return row


def _validate_sensitivity_rows(value: object, *, claim_direction: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str) or not value:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_rule_sensitivity_missing",
            "Evidence synthesis report must include sensitivity_to_synthesis_rules.",
            "sensitivity_to_synthesis_rules",
        )
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise EvidenceSynthesisReportError(
                "policy_design_synthesis_rule_sensitivity_invalid",
                "Synthesis-rule sensitivity rows must be mappings.",
                f"sensitivity_to_synthesis_rules[{index}]",
            )
        row = _validate_synthesis_estimate(item)
        row["weighting"] = _required_text(
            item.get("weighting"),
            "weighting",
            "policy_design_synthesis_weighting_missing",
        )
        row["included_decisions"] = _text_values(item.get("included_decisions")) or [
            "defensible"
        ]
        row["reasonable"] = bool(item.get("reasonable", True))
        row["direction_changed"] = row["direction"] != claim_direction
        rows.append(row)
    return rows


def _validate_information_saturation(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_information_saturation_missing",
            "Evidence synthesis report must include information_saturation.",
            "information_saturation",
        )
    row = dict(value)
    status = _required_text(
        row.get("status"),
        "status",
        "policy_design_synthesis_saturation_status_missing",
    )
    if status not in _VALID_SATURATION_STATUSES:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_saturation_status_invalid",
            "Information saturation status must be saturated, not_saturated, or blocked.",
            "information_saturation.status",
        )
    row["status"] = status
    row["effective_independent_evidence_count"] = _required_int(
        row.get("effective_independent_evidence_count"),
        "information_saturation.effective_independent_evidence_count",
        "policy_design_synthesis_saturation_effective_count_missing",
    )
    row["minimum_effective_independent_evidence_count"] = _required_int(
        row.get("minimum_effective_independent_evidence_count"),
        "information_saturation.minimum_effective_independent_evidence_count",
        "policy_design_synthesis_saturation_minimum_count_missing",
    )
    row["recent_direction_changes"] = _required_int(
        row.get("recent_direction_changes"),
        "information_saturation.recent_direction_changes",
        "policy_design_synthesis_saturation_direction_changes_missing",
    )
    row["stopping_decision"] = _required_text(
        row.get("stopping_decision") or row.get("decision"),
        "stopping_decision",
        "policy_design_synthesis_stopping_decision_missing",
    )
    if row["status"] == "saturated" and row["recent_direction_changes"] > 0:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_saturation_direction_change",
            "Saturation cannot be claimed while recent synthesis directions changed.",
            "information_saturation.recent_direction_changes",
        )
    return row


def _build_effective_evidence_mass(
    *,
    information_saturation: Mapping[str, Any],
    disconfirming_ledgers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    effective_support_mass = float(
        _required_int(
            information_saturation.get("effective_independent_evidence_count"),
            "information_saturation.effective_independent_evidence_count",
            "policy_design_synthesis_saturation_effective_count_missing",
        )
    )
    has_counterevidence = any(
        _ledger_preserves_counterevidence(row) for row in disconfirming_ledgers
    )
    effective_counter_mass = 1.0 if has_counterevidence else 0.0
    return {
        "effective_support_mass": effective_support_mass,
        "effective_counterevidence_mass": effective_counter_mass,
        "effective_context_mass": 0.0,
        "collapse_reasons": [],
        "counterevidence_preserved": effective_counter_mass > 0.0,
        "raw_count_display_policy": {
            "raw_count_authority": "diagnostic_only",
            "must_display_with": [
                "effective_support_mass",
                "effective_counterevidence_mass",
                "collapse_reasons",
            ],
        },
    }


def _validate_effective_evidence_mass(
    value: object,
    *,
    information_saturation: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_effective_mass_missing",
            "Evidence synthesis report must include effective_evidence_mass.",
            "effective_evidence_mass",
        )
    row = dict(value)
    row["effective_support_mass"] = _nonnegative_float(
        row.get("effective_support_mass"),
        "effective_evidence_mass.effective_support_mass",
        "policy_design_synthesis_effective_support_mass_missing",
    )
    row["effective_counterevidence_mass"] = _nonnegative_float(
        row.get("effective_counterevidence_mass"),
        "effective_evidence_mass.effective_counterevidence_mass",
        "policy_design_synthesis_effective_counter_mass_missing",
    )
    row["effective_context_mass"] = _nonnegative_float(
        row.get("effective_context_mass"),
        "effective_evidence_mass.effective_context_mass",
        "policy_design_synthesis_effective_context_mass_missing",
        default=0.0,
    )
    expected_support = float(
        information_saturation.get("effective_independent_evidence_count") or 0
    )
    if row["effective_support_mass"] > expected_support:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_effective_support_exceeds_independence",
            (
                "Synthesis effective support mass cannot exceed the effective "
                "independent evidence count."
            ),
            "effective_evidence_mass.effective_support_mass",
        )
    raw_count = _optional_int(row.get("raw_evidence_line_count"))
    if raw_count is not None:
        row["raw_evidence_line_count"] = raw_count
        effective_total = row["effective_support_mass"] + row["effective_counterevidence_mass"]
        collapse_reasons = _collapse_reason_rows(row.get("collapse_reasons"))
        if raw_count > effective_total and not collapse_reasons:
            raise EvidenceSynthesisReportError(
                "policy_design_synthesis_effective_mass_collapse_reasons_missing",
                (
                    "Raw evidence count in synthesis must be displayed beside "
                    "effective mass and collapse reasons."
                ),
                "effective_evidence_mass.collapse_reasons",
            )
        row["collapse_reasons"] = collapse_reasons
    else:
        row["collapse_reasons"] = _collapse_reason_rows(row.get("collapse_reasons"))
    display_policy = row.get("raw_count_display_policy")
    if not isinstance(display_policy, Mapping):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_raw_count_display_policy_missing",
            "Evidence synthesis must declare raw-count display policy.",
            "effective_evidence_mass.raw_count_display_policy",
        )
    row["raw_count_display_policy"] = dict(display_policy)
    row["counterevidence_preserved"] = bool(row.get("counterevidence_preserved", False))
    return row


def _validate_run_cost_proportionality(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_run_cost_missing",
            "Evidence synthesis report must include run_cost_proportionality.",
            "run_cost_proportionality",
        )
    row = dict(value)
    row["status"] = _required_text(
        row.get("status"),
        "status",
        "policy_design_synthesis_run_cost_status_missing",
    )
    row["budget_tier"] = _required_text(
        row.get("budget_tier"),
        "budget_tier",
        "policy_design_synthesis_run_cost_budget_tier_missing",
    )
    row["marginal_cost_usd"] = _float(
        row.get("marginal_cost_usd"),
        field="run_cost_proportionality.marginal_cost_usd",
    )
    row["marginal_information_gain"] = _float(
        row.get("marginal_information_gain"),
        field="run_cost_proportionality.marginal_information_gain",
    )
    cost_ref = _required_text(
        row.get("cost_evidence_ref") or row.get("evidence_ref") or row.get("cas_ref"),
        "cost_evidence_ref",
        "policy_design_synthesis_run_cost_ref_missing",
    )
    if not _runtime_artifact_ref(cost_ref):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_run_cost_ref_invalid",
            "Run-cost proportionality evidence must cite a runtime artifact ref.",
            "run_cost_proportionality.cost_evidence_ref",
        )
    row["cost_evidence_ref"] = cost_ref
    row["proportionality_rationale"] = _required_text(
        row.get("proportionality_rationale") or row.get("rationale"),
        "proportionality_rationale",
        "policy_design_synthesis_run_cost_rationale_missing",
    )
    return row


def _validate_previous_wave_refs(value: object) -> dict[str, list[str]]:
    if not isinstance(value, Mapping):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_previous_wave_refs_missing",
            (
                "Evidence synthesis report must cite portfolio, evidence-line, "
                "independence-map, multiverse, and disconfirming refs."
            ),
            "previous_wave_refs",
        )
    return {
        "portfolio_design_refs": _required_previous_refs(
            value,
            ("portfolio_design_refs", "portfolio_refs", "evidence_portfolio_refs"),
            field="previous_wave_refs.portfolio_design_refs",
        ),
        "evidence_line_refs": _required_previous_refs(
            value,
            ("evidence_line_refs", "line_refs", "portfolio_evidence_line_refs"),
            field="previous_wave_refs.evidence_line_refs",
        ),
        "independence_map_refs": _required_previous_refs(
            value,
            ("independence_map_refs", "evidence_independence_map_refs"),
            field="previous_wave_refs.independence_map_refs",
        ),
        "multiverse_curve_refs": _required_previous_refs(
            value,
            (
                "multiverse_curve_refs",
                "multiverse_report_refs",
                "specification_curve_refs",
            ),
            field="previous_wave_refs.multiverse_curve_refs",
        ),
        "disconfirming_ledger_refs": _required_previous_refs(
            value,
            (
                "disconfirming_ledger_refs",
                "disconfirming_evidence_ledger_refs",
                "disconfirming_refs",
            ),
            field="previous_wave_refs.disconfirming_ledger_refs",
        ),
    }


def _required_previous_refs(
    mapping: Mapping[str, object],
    keys: Sequence[str],
    *,
    field: str,
) -> list[str]:
    refs: list[str] = []
    for key in keys:
        refs.extend(_text_values(mapping.get(key)))
    if not refs:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_previous_wave_refs_missing",
            f"Evidence synthesis report must include {field}.",
            field,
        )
    return list(dict.fromkeys(refs))


def _previous_wave_refs_from_inputs(
    *,
    curve: Mapping[str, Any],
    disconfirming_ledgers: Sequence[Mapping[str, Any]],
) -> dict[str, list[str]]:
    curve_previous = curve.get("previous_wave_refs")
    refs = dict(curve_previous) if isinstance(curve_previous, Mapping) else {}
    refs["multiverse_curve_refs"] = _refs_for_rows(
        (curve,), ("curve_id", "multiverse_curve_id", "record_id", "id", "evidence_ref")
    )
    refs["disconfirming_ledger_refs"] = _refs_for_rows(
        disconfirming_ledgers,
        ("ledger_id", "disconfirming_ledger_id", "record_id", "id", "evidence_ref"),
    )
    return _validate_previous_wave_refs(refs)


def _validate_divergence_assessment(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_divergence_assessment_missing",
            "Evidence synthesis report must include divergence_assessment.",
            "divergence_assessment",
        )
    row = dict(value)
    status = _required_text(
        row.get("status"),
        "status",
        "policy_design_synthesis_divergence_status_missing",
    )
    if status not in _VALID_DIVERGENCE_STATUSES:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_divergence_status_invalid",
            "Divergence status must be convergent, divergent, or blocked.",
            "divergence_assessment.status",
        )
    row["status"] = status
    row["reason_codes"] = _text_values(row.get("reason_codes"))
    return row


def _validate_divergence_evidence(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_divergence_evidence_invalid",
            "divergence_evidence must be a sequence.",
            "divergence_evidence",
        )
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise EvidenceSynthesisReportError(
                "policy_design_synthesis_divergence_evidence_invalid",
                "Every divergence evidence row must be a mapping.",
                f"divergence_evidence[{index}]",
            )
        row = dict(item)
        row["evidence_id"] = _required_text(
            row.get("evidence_id") or row.get("id"),
            "evidence_id",
            "policy_design_synthesis_divergence_evidence_id_missing",
        )
        row["kind"] = _required_text(
            row.get("kind"),
            "kind",
            "policy_design_synthesis_divergence_evidence_kind_missing",
        )
        evidence_ref = _required_text(
            row.get("evidence_ref") or row.get("cas_ref"),
            "evidence_ref",
            "policy_design_synthesis_divergence_evidence_ref_missing",
        )
        if not _runtime_artifact_ref(evidence_ref):
            raise EvidenceSynthesisReportError(
                "policy_design_synthesis_divergence_evidence_ref_invalid",
                "Divergence evidence must cite a runtime artifact ref.",
                f"divergence_evidence[{index}].evidence_ref",
            )
        row["evidence_ref"] = evidence_ref
        rows.append(row)
    return rows


def _validate_blockers(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_blockers_invalid",
            "blockers must be a sequence.",
            "blockers",
        )
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise EvidenceSynthesisReportError(
                "policy_design_synthesis_blocker_invalid",
                "Every synthesis blocker must be a mapping.",
                f"blockers[{index}]",
            )
        row = dict(item)
        if _text(row.get("status") or row.get("decision")) != "blocked":
            raise EvidenceSynthesisReportError(
                "policy_design_synthesis_blocker_status_invalid",
                "Synthesis blockers must have blocked status.",
                f"blockers[{index}].status",
            )
        for key, code in (
            ("code", "policy_design_synthesis_blocker_code_missing"),
            ("message", "policy_design_synthesis_blocker_message_missing"),
        ):
            _required_text(row.get(key), key, code)
        evidence_ref = _required_text(
            row.get("evidence_ref") or row.get("cas_ref"),
            "evidence_ref",
            "policy_design_synthesis_blocker_evidence_ref_missing",
        )
        if not _runtime_artifact_ref(evidence_ref):
            raise EvidenceSynthesisReportError(
                "policy_design_synthesis_blocker_evidence_ref_invalid",
                "Synthesis blockers must cite runtime artifact refs.",
                f"blockers[{index}].evidence_ref",
            )
        runtime_event_ref = _required_text(
            row.get("runtime_event_ref"),
            "runtime_event_ref",
            "policy_design_synthesis_blocker_runtime_event_ref_missing",
        )
        if not _runtime_event_ref(runtime_event_ref):
            raise EvidenceSynthesisReportError(
                "policy_design_synthesis_blocker_runtime_event_ref_invalid",
                "Synthesis blockers must cite runtime event refs.",
                f"blockers[{index}].runtime_event_ref",
            )
        row["evidence_ref"] = evidence_ref
        row["runtime_event_ref"] = runtime_event_ref
        rows.append(row)
    return rows


def _validate_external_bindings(
    report: Mapping[str, Any],
    *,
    multiverse_curves: Sequence[Mapping[str, Any]],
    disconfirming_ledgers: Sequence[Mapping[str, Any]],
) -> None:
    if multiverse_curves and not any(
        _row_matches_claim_and_portfolio(
            row,
            claim_ids=set(report["claim_ids"]),
            portfolio_id=str(report["portfolio_id"]),
            portfolio_keys=("portfolio_id", "portfolio_ref"),
        )
        for row in multiverse_curves
    ):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_multiverse_curve_missing",
            "Evidence synthesis report must bind a supplied multiverse curve.",
            "multiverse_curve_refs",
        )
    if disconfirming_ledgers and not any(
        _row_matches_claim_and_portfolio(
            row,
            claim_ids=set(report["claim_ids"]),
            portfolio_id=str(report["portfolio_id"]),
            portfolio_keys=("portfolio_id", "portfolio_ref"),
        )
        for row in disconfirming_ledgers
    ):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_disconfirming_ledger_missing",
            "Evidence synthesis report must bind a supplied disconfirming ledger.",
            "disconfirming_ledger_refs",
        )


def _row_matches_claim_and_portfolio(
    row: Mapping[str, Any],
    *,
    claim_ids: set[str],
    portfolio_id: str,
    portfolio_keys: Sequence[str],
) -> bool:
    row_claims = set(
        _text_values(row.get("claim_ids") or row.get("major_claim_ids") or row.get("claim_id"))
    )
    if row_claims and row_claims.isdisjoint(claim_ids):
        return False
    row_portfolios: set[str] = set()
    for key in portfolio_keys:
        row_portfolios.update(_text_values(row.get(key)))
    return not row_portfolios or portfolio_id in row_portfolios


def _divergence_must_be_represented(
    report: Mapping[str, Any],
    *,
    multiverse_curves: Sequence[Mapping[str, Any]],
) -> bool:
    if _sensitivity_direction_changed(report.get("sensitivity_to_synthesis_rules") or ()):
        return True
    heterogeneity = report.get("heterogeneity_model")
    if isinstance(heterogeneity, Mapping):
        i_squared = _optional_float(heterogeneity.get("i_squared"))
        if i_squared is not None and i_squared >= 0.5:
            return True
        interpretation = (_text(heterogeneity.get("interpretation")) or "").casefold()
        if interpretation in {"high", "substantial", "severe"}:
            return True
    for curve in multiverse_curves:
        records = _sequence_of_mappings(curve.get("specification_records"))
        if _records_mixed_sign(records, claim_ids=list(report.get("claim_ids") or ())):
            return True
    return False


def _sensitivity_direction_changed(rows: Iterable[Mapping[str, Any]]) -> bool:
    return any(
        row.get("direction_changed") and bool(row.get("reasonable", True))
        for row in rows
    )


def _records_mixed_sign(
    records: Sequence[Mapping[str, Any]],
    *,
    claim_ids: Sequence[str],
) -> bool:
    claim_set = set(claim_ids)
    signs: set[str] = set()
    for record in records:
        record_claims = set(_text_values(record.get("claim_ids") or record.get("claim_id")))
        if claim_set and record_claims and record_claims.isdisjoint(claim_set):
            continue
        sign = _text(record.get("sign")) or _sign(_float(record.get("estimate"), field="estimate"))
        if sign != "zero":
            signs.add(sign)
    return len(signs) > 1


def _refs_for_rows(rows: Iterable[Mapping[str, Any]], keys: Sequence[str]) -> list[str]:
    refs: list[str] = []
    for row in rows:
        for key in keys:
            refs.extend(_text_values(row.get(key)))
    return list(dict.fromkeys(refs))


def _sequence_of_mappings(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _ledger_preserves_counterevidence(row: Mapping[str, Any]) -> bool:
    if _sequence_of_mappings(row.get("disconfirming_lines")):
        return True
    if _text_values(row.get("disconfirming_lines")):
        return True
    for severe_test in _sequence_of_mappings(row.get("severe_tests")):
        result = (_text(severe_test.get("result")) or "").lower()
        if result in {"failed", "blocked", "counterevidence", "disconfirming"}:
            return True
    for report in _sequence_of_mappings(row.get("ir_falsification_reports")):
        if report.get("overall_passed") is False:
            return True
    return False


def _collapse_reason_rows(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_effective_mass_collapse_reasons_invalid",
            "Synthesis collapse reasons must be a sequence.",
            "effective_evidence_mass.collapse_reasons",
        )
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise EvidenceSynthesisReportError(
                "policy_design_synthesis_effective_mass_collapse_reason_invalid",
                "Synthesis collapse reason rows must be mappings.",
                f"effective_evidence_mass.collapse_reasons[{index}]",
            )
        row = dict(item)
        row["reason_code"] = _required_text(
            row.get("reason_code") or row.get("code"),
            "reason_code",
            "policy_design_synthesis_effective_mass_collapse_reason_code_missing",
        )
        rows.append(row)
    return rows


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, Mapping):
            return dumped
    raise EvidenceSynthesisReportError(
        "policy_design_synthesis_source_invalid",
        "Synthesis source inputs must be mappings or pydantic-style models.",
    )


def _require_surface(value: object, field: str, code: str) -> None:
    if value is None:
        raise EvidenceSynthesisReportError(
            code,
            f"Evidence synthesis report must include {field}.",
            field,
        )
    if isinstance(value, Mapping) and not value:
        raise EvidenceSynthesisReportError(
            code,
            f"Evidence synthesis report must include non-empty {field}.",
            field,
        )
    if isinstance(value, Sequence) and not isinstance(value, str) and not value:
        raise EvidenceSynthesisReportError(
            code,
            f"Evidence synthesis report must include non-empty {field}.",
            field,
        )


def _claim_ids(*, claim_id: str | None, claim_ids: object) -> list[str]:
    values: list[str] = []
    if claim_id is not None:
        values.append(claim_id)
    values.extend(_text_values(claim_ids))
    return list(dict.fromkeys(value for value in values if _text(value) is not None))


def _clean_texts(values: Iterable[object]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = _text(value)
        if text is not None:
            cleaned.append(text)
    return list(dict.fromkeys(cleaned))


def _text_values(value: object) -> list[str]:
    if isinstance(value, str):
        text = _text(value)
        return [text] if text is not None else []
    if isinstance(value, Mapping):
        values: list[str] = []
        for key in (
            "claim_id",
            "major_claim_id",
            "portfolio_id",
            "curve_id",
            "ledger_id",
            "report_id",
            "line_id",
            "map_id",
            "id",
            "ref",
            "value",
        ):
            text = _text(value.get(key))
            if text is not None:
                values.append(text)
        return list(dict.fromkeys(values))
    if isinstance(value, Iterable):
        values: list[str] = []
        for item in value:
            values.extend(_text_values(item))
        return list(dict.fromkeys(values))
    return []


def _required_text(value: object, field: str, code: str) -> str:
    text = _text(value)
    if text is None:
        raise EvidenceSynthesisReportError(
            code,
            f"Evidence synthesis report must include {field}.",
            field,
        )
    return text


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or any(char in text for char in "\r\n\t"):
        return None
    return text


def _float(value: object, *, field: str, default: float | None = None) -> float:
    if value is None:
        if default is not None:
            return default
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_number_missing",
            f"Numeric synthesis field {field} is required.",
            field,
        )
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_number_invalid",
            "Numeric synthesis fields must be finite numbers.",
            field,
        ) from exc
    if not math.isfinite(number):
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_number_invalid",
            "Numeric synthesis fields must be finite numbers.",
            field,
        )
    return number


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return _float(value, field="optional_float")


def _nonnegative_float(
    value: object,
    field: str,
    code: str,
    *,
    default: float | None = None,
) -> float:
    number = _float(value, field=field, default=default)
    if number < 0.0:
        raise EvidenceSynthesisReportError(
            code,
            f"Evidence synthesis {field} cannot be negative.",
            field,
        )
    return number


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    number = _float(value, field="optional_int")
    if number < 0 or int(number) != number:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_integer_invalid",
            "Synthesis count fields must be non-negative integers.",
            "optional_int",
        )
    return int(number)


def _required_int(value: object, field: str, code: str) -> int:
    number = _float(value, field=field)
    if number < 0 or int(number) != number:
        raise EvidenceSynthesisReportError(
            "policy_design_synthesis_integer_invalid",
            "Synthesis count fields must be non-negative integers.",
            field,
        )
    return int(number)


def _sign(value: float) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "zero"


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
    "EVIDENCE_SYNTHESIS_REPORT_CONTRACT_ID",
    "EVIDENCE_SYNTHESIS_REPORT_SCHEMA_VERSION",
    "EvidenceSynthesisReportError",
    "build_evidence_synthesis_report",
    "evidence_synthesis_refs_by_claim",
    "synthesis_report_record_id",
    "validate_evidence_synthesis_report_record",
]
