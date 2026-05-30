"""Compile baseline and alternative seeds into comparison records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.evidence.claims.models import (
    AlternativeRecord,
    AlternativeRejectionReason,
    AlternativeStatus,
    BaselineComparisonRecord,
    BaselineComparisonStatus,
    BaselineRecord,
    ClaimLedger,
    ClaimRecord,
    ClaimUse,
    ComparisonEvidenceRef,
    ComparisonOptionKind,
    ComparisonOptionRecord,
    ComparisonOptionStatus,
    ComparisonProducerFamily,
    DominanceStatus,
    DominatedFrontierRecord,
    RejectedOptionReasonRecord,
    baseline_comparison_authority_boundary,
)

ObjectiveDirection = Literal["maximize", "minimize"]


class BaselineComparisonInput(BaseModel):
    """Input packet for W8.C baseline/alternative comparison compilation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    claim_ledger: ClaimLedger
    selected_option_ref: str = Field(min_length=1)
    selected_option_label: str = Field(min_length=1)
    selected_option_evidence_refs: set[str] = Field(default_factory=set)
    option_metric_values: dict[str, dict[str, float]] = Field(default_factory=dict)
    objective_directions: dict[str, ObjectiveDirection] = Field(default_factory=dict)
    fabric_source_bindings: dict[str, Any] = Field(default_factory=dict)
    foundry_method_report: dict[str, Any] = Field(default_factory=dict)
    ir_analytics_bridge: dict[str, Any] = Field(default_factory=dict)
    scholar_evidence_report: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaselineComparisonCompiler:
    """Deterministic compiler for W8.C superiority comparison records."""

    def compile(self, payload: BaselineComparisonInput | Mapping[str, Any]) -> ClaimLedger:
        """Compile comparison records and return an updated claim ledger.

        Args:
            payload: Typed input or mapping containing a W6.D claim ledger and
                producer reports from Fabric, Foundry, IR analytics, and Scholar.

        Returns:
            A new `ClaimLedger` with comparison records and claim-level
            `comparison_refs` bound to superiority claims.
        """

        item = (
            payload
            if isinstance(payload, BaselineComparisonInput)
            else BaselineComparisonInput.model_validate(dict(payload))
        )
        existing = {
            record.comparison_id: record
            for record in item.claim_ledger.comparison_records
        }
        new_records = [
            self._compile_claim_comparison(item, claim)
            for claim in item.claim_ledger.claims
            if claim.claim_use is ClaimUse.SUPERIORITY
        ]
        records_by_id = {**existing, **{record.comparison_id: record for record in new_records}}
        records_by_claim: dict[str, list[str]] = {}
        for record in records_by_id.values():
            records_by_claim.setdefault(record.claim_id, []).append(record.comparison_id)
        updated_claims = [
            claim.model_copy(
                update={
                    "comparison_refs": _dedupe_strings(
                        [*claim.comparison_refs, *records_by_claim.get(claim.claim_id, [])]
                    )
                }
            )
            for claim in item.claim_ledger.claims
        ]
        metadata = {
            **dict(item.claim_ledger.metadata),
            "baseline_comparison_compiler": {
                "producer": "baseline_comparison_compiler",
                "capability_reality_label": "implemented",
                "pattern_guards": ["P10", "P14"],
                "comparison_record_count": len(records_by_id),
            },
        }
        return item.claim_ledger.model_copy(
            update={
                "claims": updated_claims,
                "comparison_records": list(records_by_id.values()),
                "metadata": metadata,
            }
        )

    def _compile_claim_comparison(
        self,
        item: BaselineComparisonInput,
        claim: ClaimRecord,
    ) -> BaselineComparisonRecord:
        baseline_by_id = {
            record.baseline_id: record for record in item.claim_ledger.baseline_records
        }
        alternative_by_id = {
            record.alternative_id: record for record in item.claim_ledger.alternative_records
        }
        option_refs = _dedupe_strings(
            [
                item.selected_option_ref,
                *claim.baseline_refs,
                *claim.alternative_refs,
            ]
        )
        buckets = {option_ref: _OptionEvidence() for option_ref in option_refs}
        buckets[item.selected_option_ref].evidence_refs.update(item.selected_option_evidence_refs)

        comparison_evidence: list[ComparisonEvidenceRef] = []
        comparison_method_refs: set[str] = set()
        comparison_limitation_refs: set[str] = set()
        producer_refs: set[str] = set()

        self._collect_fabric_evidence(
            item,
            claim=claim,
            buckets=buckets,
            evidence=comparison_evidence,
            limitations=comparison_limitation_refs,
            producer_refs=producer_refs,
        )
        self._collect_scholar_evidence(
            item,
            claim=claim,
            buckets=buckets,
            evidence=comparison_evidence,
            producer_refs=producer_refs,
        )
        self._collect_foundry_evidence(
            item,
            claim=claim,
            buckets=buckets,
            evidence=comparison_evidence,
            method_refs=comparison_method_refs,
            limitations=comparison_limitation_refs,
            producer_refs=producer_refs,
        )
        self._collect_ir_evidence(
            item,
            claim=claim,
            buckets=buckets,
            evidence=comparison_evidence,
            method_refs=comparison_method_refs,
            limitations=comparison_limitation_refs,
            producer_refs=producer_refs,
        )

        for ref in item.selected_option_evidence_refs:
            comparison_evidence.append(
                _comparison_evidence(
                    ref,
                    producer_family=ComparisonProducerFamily.RUNTIME_COMPILER,
                    option_ref=item.selected_option_ref,
                    claim_id=claim.claim_id,
                    role="selected_option_support",
                )
            )

        if not buckets[item.selected_option_ref].evidence_refs:
            raise ValueError(
                f"superiority claim '{claim.claim_id}' has no selected option evidence"
            )
        if not comparison_method_refs:
            raise ValueError(
                f"superiority claim '{claim.claim_id}' has no comparison method refs"
            )

        dominated = self._dominated_frontier_records(
            item,
            claim=claim,
            option_refs=option_refs,
            buckets=buckets,
            method_refs=comparison_method_refs,
            limitations=comparison_limitation_refs,
        )
        rejected_reasons = self._rejected_option_reasons(
            claim=claim,
            alternatives=alternative_by_id,
            dominated=dominated,
        )
        rejected_reason_by_option: dict[str, set[AlternativeRejectionReason]] = {}
        for reason in rejected_reasons:
            rejected_reason_by_option.setdefault(reason.option_ref, set()).add(reason.reason)

        option_records = [
            self._option_record(
                item,
                claim=claim,
                option_ref=option_ref,
                bucket=buckets[option_ref],
                baseline=baseline_by_id.get(option_ref),
                alternative=alternative_by_id.get(option_ref),
                rejected_reasons=rejected_reason_by_option.get(option_ref, set()),
                dominated=dominated,
                limitations=comparison_limitation_refs,
            )
            for option_ref in option_refs
        ]

        if not comparison_limitation_refs:
            comparison_limitation_refs.add(
                _stable_ref("comparison-limitation-unresolved", claim.claim_id)
            )

        comparison_status = (
            BaselineComparisonStatus.LIMITED
            if comparison_limitation_refs
            or any(option.status is ComparisonOptionStatus.LIMITED for option in option_records)
            else BaselineComparisonStatus.COMPLETE
        )
        return BaselineComparisonRecord(
            comparison_id=_stable_id(
                "baseline_comparison",
                item.claim_ledger.run_id,
                claim.claim_id,
            ),
            run_id=item.claim_ledger.run_id,
            claim_id=claim.claim_id,
            selected_option_ref=item.selected_option_ref,
            selected_option_label=item.selected_option_label,
            baseline_refs=set(claim.baseline_refs),
            alternative_refs=set(claim.alternative_refs),
            baseline_types_covered={
                baseline.baseline_type
                for baseline_id in claim.baseline_refs
                if (baseline := baseline_by_id.get(baseline_id)) is not None
            },
            selected_option_evidence_refs=set(buckets[item.selected_option_ref].evidence_refs),
            option_comparisons=option_records,
            comparison_evidence=_dedupe_evidence(comparison_evidence),
            comparison_method_refs=set(comparison_method_refs),
            comparison_limitation_refs=set(comparison_limitation_refs),
            rejected_option_reasons=rejected_reasons,
            dominated_frontier_records=dominated,
            comparison_status=comparison_status,
            producer_refs=producer_refs,
            authority_boundary=baseline_comparison_authority_boundary(),
            metadata={
                "compiler": "polisyos.scientist.policy_design.baseline_compiler",
                "pattern_guards": ["P10", "P14"],
                "source_claim_use": claim.claim_use.value if claim.claim_use else None,
                **dict(item.metadata),
            },
        )

    def _collect_fabric_evidence(
        self,
        item: BaselineComparisonInput,
        *,
        claim: ClaimRecord,
        buckets: dict[str, _OptionEvidence],
        evidence: list[ComparisonEvidenceRef],
        limitations: set[str],
        producer_refs: set[str],
    ) -> None:
        for row in _rows(item.fabric_source_bindings, "source_contract_bindings", "bindings"):
            if not _claim_matches(row, claim.claim_id):
                continue
            option_ref = _option_ref(row, item.selected_option_ref)
            if option_ref not in buckets:
                continue
            candidate_ref = _text(row.get("candidate_ref") or row.get("source_contract_ref"))
            status = _text(row.get("binding_status") or row.get("status")).casefold()
            if candidate_ref:
                producer_refs.add("fabric_source_contract")
            if status == "selected" and candidate_ref:
                buckets[option_ref].data_refs.add(candidate_ref)
                buckets[option_ref].evidence_refs.add(candidate_ref)
                evidence.append(
                    _comparison_evidence(
                        candidate_ref,
                        producer_family=ComparisonProducerFamily.FABRIC_SOURCE_CONTRACT,
                        option_ref=option_ref,
                        claim_id=claim.claim_id,
                        role="source_contract_evidence",
                    )
                )
            elif candidate_ref:
                limitation_ref = _stable_ref("fabric-comparison-limitation", candidate_ref)
                buckets[option_ref].limitation_refs.add(limitation_ref)
                limitations.add(limitation_ref)

    def _collect_scholar_evidence(
        self,
        item: BaselineComparisonInput,
        *,
        claim: ClaimRecord,
        buckets: dict[str, _OptionEvidence],
        evidence: list[ComparisonEvidenceRef],
        producer_refs: set[str],
    ) -> None:
        for row in _rows(item.scholar_evidence_report, "support_links"):
            if not _claim_matches(row, claim.claim_id):
                continue
            option_ref = _option_ref(row, item.selected_option_ref)
            if option_ref not in buckets:
                continue
            ref = _text(row.get("support_ref") or row.get("source_id") or row.get("link_id"))
            if not ref:
                continue
            producer_refs.add("scholar_support")
            effective = _int(row.get("effective_support_count"))
            raw = _int(row.get("raw_support_count")) or (1 if ref else 0)
            buckets[option_ref].scholar_refs.add(ref)
            buckets[option_ref].evidence_refs.add(ref)
            buckets[option_ref].raw_support_count += raw
            buckets[option_ref].effective_support_count += effective or min(raw, 1)
            evidence.append(
                _comparison_evidence(
                    ref,
                    producer_family=ComparisonProducerFamily.SCHOLAR_SUPPORT,
                    option_ref=option_ref,
                    claim_id=claim.claim_id,
                    role="scholar_support",
                    effective_support_count=effective,
                    raw_support_count=raw,
                )
            )

    def _collect_foundry_evidence(
        self,
        item: BaselineComparisonInput,
        *,
        claim: ClaimRecord,
        buckets: dict[str, _OptionEvidence],
        evidence: list[ComparisonEvidenceRef],
        method_refs: set[str],
        limitations: set[str],
        producer_refs: set[str],
    ) -> None:
        for row in _rows(item.foundry_method_report, "selected_methods", "methods"):
            if not _claim_matches(row, claim.claim_id):
                continue
            output_refs = _refs_for_aliases(
                row,
                ("method_output_refs", "method_output_ref", "result_refs", "result_ref"),
            )
            method_id = _text(row.get("method_id"))
            if method_id:
                method_refs.add(method_id)
            method_refs.update(output_refs)
            limitation_refs = _refs_for_aliases(
                row,
                ("limitation_refs", "limitation_ref", "accepted_limitation_refs"),
            )
            limitations.update(limitation_refs)
            producer_refs.add("foundry_method")
            option_ref = _option_ref(row, item.selected_option_ref)
            target_refs = [option_ref] if option_ref in buckets else [item.selected_option_ref]
            for target_ref in target_refs:
                bucket = buckets[target_ref]
                bucket.method_refs.update(output_refs or ([method_id] if method_id else []))
                bucket.evidence_refs.update(output_refs)
                bucket.limitation_refs.update(limitation_refs)
                for ref in output_refs:
                    evidence.append(
                        _comparison_evidence(
                            ref,
                            producer_family=ComparisonProducerFamily.FOUNDRY_METHOD,
                            option_ref=target_ref,
                            claim_id=claim.claim_id,
                            role="method_output",
                        )
                    )

    def _collect_ir_evidence(
        self,
        item: BaselineComparisonInput,
        *,
        claim: ClaimRecord,
        buckets: dict[str, _OptionEvidence],
        evidence: list[ComparisonEvidenceRef],
        method_refs: set[str],
        limitations: set[str],
        producer_refs: set[str],
    ) -> None:
        for row in _rows(item.ir_analytics_bridge, "claim_bindings", "bindings"):
            if not _claim_matches(row, claim.claim_id):
                continue
            analytics_refs = _refs_for_aliases(row, ("ir_analytics_refs", "analytics_refs"))
            row_method_refs = _refs_for_aliases(
                row,
                (
                    "method_output_refs",
                    "ir_certificate_refs",
                    "negative_certificate_refs",
                    "certificate_refs",
                ),
            )
            limitation_refs = _refs_for_aliases(row, ("limitation_refs", "deficit_refs"))
            method_refs.update(row_method_refs)
            limitations.update(limitation_refs)
            producer_refs.add("ir_causal_analytics")
            option_ref = _option_ref(row, item.selected_option_ref)
            target_ref = option_ref if option_ref in buckets else item.selected_option_ref
            buckets[target_ref].ir_analytics_refs.update(analytics_refs)
            buckets[target_ref].method_refs.update(row_method_refs)
            buckets[target_ref].evidence_refs.update(analytics_refs)
            buckets[target_ref].limitation_refs.update(limitation_refs)
            for ref in [*analytics_refs, *row_method_refs]:
                evidence.append(
                    _comparison_evidence(
                        ref,
                        producer_family=ComparisonProducerFamily.IR_CAUSAL_ANALYTICS,
                        option_ref=target_ref,
                        claim_id=claim.claim_id,
                        role="ir_analytics_or_certificate",
                    )
                )

    def _dominated_frontier_records(
        self,
        item: BaselineComparisonInput,
        *,
        claim: ClaimRecord,
        option_refs: Sequence[str],
        buckets: Mapping[str, _OptionEvidence],
        method_refs: set[str],
        limitations: set[str],
    ) -> list[DominatedFrontierRecord]:
        records: list[DominatedFrontierRecord] = []
        selected_metrics = item.option_metric_values.get(item.selected_option_ref, {})
        for option_ref in option_refs:
            if option_ref == item.selected_option_ref:
                continue
            deltas = _selected_dominance_deltas(
                selected_metrics,
                item.option_metric_values.get(option_ref, {}),
                item.objective_directions,
            )
            if not deltas:
                continue
            bucket = buckets.get(option_ref, _OptionEvidence())
            records.append(
                DominatedFrontierRecord(
                    dominated_record_id=_stable_id(
                        "dominated_frontier",
                        claim.claim_id,
                        option_ref,
                        item.selected_option_ref,
                    ),
                    claim_id=claim.claim_id,
                    dominated_option_ref=option_ref,
                    dominating_option_ref=item.selected_option_ref,
                    dominance_status=DominanceStatus.SELECTED_DOMINATES,
                    metric_deltas=deltas,
                    evidence_refs=set(bucket.evidence_refs),
                    method_refs=set(method_refs),
                    limitation_refs=set(limitations | bucket.limitation_refs),
                )
            )
        return records

    def _rejected_option_reasons(
        self,
        *,
        claim: ClaimRecord,
        alternatives: Mapping[str, AlternativeRecord],
        dominated: Sequence[DominatedFrontierRecord],
    ) -> list[RejectedOptionReasonRecord]:
        reason_records: list[RejectedOptionReasonRecord] = []
        dominated_by_option = {record.dominated_option_ref: record for record in dominated}
        for alternative_id in claim.alternative_refs:
            alternative = alternatives.get(alternative_id)
            reasons: set[AlternativeRejectionReason] = set()
            source_refs: set[str] = set()
            if alternative is not None and alternative.status is AlternativeStatus.REJECTED:
                reasons.update(alternative.rejected_reasons)
                source_refs.add(alternative.alternative_id)
            if alternative_id in dominated_by_option:
                reasons.add(AlternativeRejectionReason.DOMINATED_FRONTIER)
                source_refs.add(dominated_by_option[alternative_id].dominated_record_id)
            for reason in sorted(reasons, key=lambda item: item.value):
                reason_records.append(
                    RejectedOptionReasonRecord(
                        reason_record_id=_stable_id(
                            "rejected_option_reason",
                            claim.claim_id,
                            alternative_id,
                            reason.value,
                        ),
                        claim_id=claim.claim_id,
                        option_ref=alternative_id,
                        reason=reason,
                        source_refs=set(source_refs),
                    )
                )
        return reason_records

    def _option_record(
        self,
        item: BaselineComparisonInput,
        *,
        claim: ClaimRecord,
        option_ref: str,
        bucket: _OptionEvidence,
        baseline: BaselineRecord | None,
        alternative: AlternativeRecord | None,
        rejected_reasons: set[AlternativeRejectionReason],
        dominated: Sequence[DominatedFrontierRecord],
        limitations: set[str],
    ) -> ComparisonOptionRecord:
        option_kind = _option_kind(
            option_ref,
            selected_option_ref=item.selected_option_ref,
            baseline=baseline,
            alternative=alternative,
        )
        limitation_refs = set(bucket.limitation_refs)
        if (
            option_kind is not ComparisonOptionKind.SELECTED_OPTION
            and not bucket.evidence_refs
            and not rejected_reasons
        ):
            limitation_refs.add(_stable_ref("comparison-option-evidence-missing", option_ref))
            limitations.update(limitation_refs)
        dominance_status = (
            DominanceStatus.SELECTED_DOMINATES
            if any(record.dominated_option_ref == option_ref for record in dominated)
            else DominanceStatus.UNKNOWN
        )
        status = _option_status(
            option_kind=option_kind,
            evidence_refs=bucket.evidence_refs,
            rejected_reasons=rejected_reasons,
            limitation_refs=limitation_refs,
        )
        label = (
            item.selected_option_label
            if option_kind is ComparisonOptionKind.SELECTED_OPTION
            else baseline.label
            if baseline is not None
            else alternative.label
            if alternative is not None
            else option_ref
        )
        return ComparisonOptionRecord(
            option_ref=option_ref,
            option_kind=option_kind,
            label=label,
            status=status,
            evidence_refs=set(bucket.evidence_refs),
            data_refs=set(bucket.data_refs),
            scholar_refs=set(bucket.scholar_refs),
            method_refs=set(bucket.method_refs),
            ir_analytics_refs=set(bucket.ir_analytics_refs),
            limitation_refs=limitation_refs,
            rejected_reasons=set(rejected_reasons),
            dominance_status=dominance_status,
            metric_values=dict(item.option_metric_values.get(option_ref, {})),
            effective_independent_support_count=bucket.effective_support_count,
            raw_support_count=bucket.raw_support_count,
            metadata={"claim_id": claim.claim_id},
        )


def compile_baseline_comparisons(
    payload: BaselineComparisonInput | Mapping[str, Any],
) -> ClaimLedger:
    """Compile W8.C comparison records with the default compiler."""

    return BaselineComparisonCompiler().compile(payload)


def baseline_comparison_audit_surface(
    ledger: ClaimLedger | Mapping[str, Any],
) -> dict[str, Any]:
    """Return a machine-readable inspection surface for W8.C comparison records."""

    model = ledger if isinstance(ledger, ClaimLedger) else ClaimLedger.model_validate(dict(ledger))
    records = list(model.comparison_records)
    return {
        "schema_version": "policyos.scientist.policy_design.baseline_comparison.audit.v1",
        "run_id": model.run_id,
        "surface": "baseline_comparison.audit_surface",
        "comparison_record_count": len(records),
        "comparison_refs_by_claim": {
            claim.claim_id: list(claim.comparison_refs)
            for claim in model.claims
            if claim.claim_use is ClaimUse.SUPERIORITY
        },
        "records": [record.model_dump(mode="json") for record in records],
        "authority_boundary": baseline_comparison_authority_boundary(),
    }


@dataclass
class _OptionEvidence:
    evidence_refs: set[str] = field(default_factory=set)
    data_refs: set[str] = field(default_factory=set)
    scholar_refs: set[str] = field(default_factory=set)
    method_refs: set[str] = field(default_factory=set)
    ir_analytics_refs: set[str] = field(default_factory=set)
    limitation_refs: set[str] = field(default_factory=set)
    raw_support_count: int = 0
    effective_support_count: int = 0


def _option_kind(
    option_ref: str,
    *,
    selected_option_ref: str,
    baseline: BaselineRecord | None,
    alternative: AlternativeRecord | None,
) -> ComparisonOptionKind:
    if option_ref == selected_option_ref:
        return ComparisonOptionKind.SELECTED_OPTION
    if alternative is not None:
        return ComparisonOptionKind.ALTERNATIVE
    if baseline is not None:
        return ComparisonOptionKind.BASELINE
    return ComparisonOptionKind.ALTERNATIVE


def _option_status(
    *,
    option_kind: ComparisonOptionKind,
    evidence_refs: Iterable[str],
    rejected_reasons: Iterable[AlternativeRejectionReason],
    limitation_refs: Iterable[str],
) -> ComparisonOptionStatus:
    if set(rejected_reasons):
        return ComparisonOptionStatus.REJECTED
    if option_kind is ComparisonOptionKind.SELECTED_OPTION and not set(evidence_refs):
        return ComparisonOptionStatus.BLOCKED
    if set(limitation_refs) and not set(evidence_refs):
        return ComparisonOptionStatus.LIMITED
    return ComparisonOptionStatus.COMPARED


def _comparison_evidence(
    evidence_ref: str,
    *,
    producer_family: ComparisonProducerFamily,
    option_ref: str,
    claim_id: str,
    role: str,
    effective_support_count: int | None = None,
    raw_support_count: int | None = None,
) -> ComparisonEvidenceRef:
    return ComparisonEvidenceRef(
        evidence_ref=evidence_ref,
        producer_family=producer_family,
        option_ref=option_ref,
        claim_id=claim_id,
        role=role,
        effective_support_count=effective_support_count,
        raw_support_count=raw_support_count,
    )


def _selected_dominance_deltas(
    selected: Mapping[str, float],
    option: Mapping[str, float],
    directions: Mapping[str, ObjectiveDirection],
) -> dict[str, float]:
    common_metrics = sorted(set(selected) & set(option))
    if not common_metrics:
        return {}
    deltas: dict[str, float] = {}
    strictly_better = False
    for metric in common_metrics:
        direction = directions.get(metric, "maximize")
        selected_value = float(selected[metric])
        option_value = float(option[metric])
        delta = selected_value - option_value
        if direction == "minimize":
            delta = option_value - selected_value
        if delta < 0:
            return {}
        if delta > 0:
            strictly_better = True
        deltas[metric] = delta
    return deltas if strictly_better else {}


def _rows(payload: Mapping[str, Any], *keys: str) -> list[Mapping[str, Any]]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _claim_matches(row: Mapping[str, Any], claim_id: str) -> bool:
    row_claim_id = _text(row.get("claim_id"))
    return not row_claim_id or row_claim_id == claim_id


def _option_ref(row: Mapping[str, Any], default: str) -> str:
    return (
        _text(
            row.get("option_ref")
            or row.get("selected_option_ref")
            or row.get("baseline_ref")
            or row.get("alternative_ref")
        )
        or default
    )


def _refs_for_aliases(row: Mapping[str, Any], aliases: Sequence[str]) -> set[str]:
    refs: set[str] = set()
    for alias in aliases:
        refs.update(_refs_from_value(row.get(alias)))
    return refs


def _refs_from_value(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value} if value else set()
    if isinstance(value, Mapping):
        return {
            text
            for item in value.values()
            for text in _refs_from_value(item)
        }
    if isinstance(value, Iterable):
        return {
            text
            for item in value
            for text in _refs_from_value(item)
        }
    text = _text(value)
    return {text} if text else set()


def _dedupe_evidence(records: Sequence[ComparisonEvidenceRef]) -> list[ComparisonEvidenceRef]:
    deduped: dict[tuple[str, str, str], ComparisonEvidenceRef] = {}
    for record in records:
        deduped.setdefault((record.claim_id, record.option_ref, record.evidence_ref), record)
    return list(deduped.values())


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _stable_id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{_digest({'parts': list(parts)})[:16]}"


def _stable_ref(prefix: str, *parts: str) -> str:
    return f"{prefix}:{_digest({'parts': list(parts)})[:16]}"


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _text(value: object) -> str:
    return str(value or "").strip()


def _int(value: object) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "BaselineComparisonCompiler",
    "BaselineComparisonInput",
    "baseline_comparison_audit_surface",
    "compile_baseline_comparisons",
]
