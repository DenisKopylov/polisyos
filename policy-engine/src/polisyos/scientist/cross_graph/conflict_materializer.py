"""Materialize cross-graph conflicts into claim registry and portfolio records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from polisyos.evidence import (
    build_conflict_portfolio_index,
    build_conflict_record,
    validate_conflict_record,
)
from polisyos.scientist.cross_graph.conflict import (
    ConflictDetector,
    EvidenceConflict,
)

CONFLICT_MATERIALIZATION_CLOSEOUT_SCHEMA_VERSION = (
    "policyos.scientist.cross_graph.conflict_materialization.closeout.v1"
)
CONFLICT_MATERIALIZATION_READER_CONTRACT = (
    "polisyos.scientist.cross_graph.conflict_materializer#w8e"
)


class _EvidenceNeedAssessmentLike(Protocol):
    need: Any
    legal_status: object
    evidence_status: object
    observability_status: object
    transport_status: object
    provenance_refs: Sequence[object]


class _CrossGraphEvidenceProfileLike(Protocol):
    needs: Sequence[_EvidenceNeedAssessmentLike]


@dataclass(frozen=True)
class ConflictMaterializationResult:
    """Conflict materialization payload consumed by closeout and portfolio surfaces."""

    conflict_records: tuple[dict[str, Any], ...]
    claim_registry: dict[str, Any]
    portfolio_index: dict[str, Any]
    issues: tuple[dict[str, Any], ...]
    detector_conflicts: tuple[EvidenceConflict, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return the materialization result as a JSON-ready mapping."""

        return {
            "conflict_records": [dict(record) for record in self.conflict_records],
            "claim_registry": dict(self.claim_registry),
            "portfolio_index": dict(self.portfolio_index),
            "issues": [dict(issue) for issue in self.issues],
            "detector_conflicts": [
                {
                    "need_id": conflict.need_id,
                    "dimension": conflict.dimension,
                    "conflicting_sources": list(conflict.conflicting_sources),
                    "severity": conflict.severity.value,
                    "description": conflict.description,
                }
                for conflict in self.detector_conflicts
            ],
        }

    def to_closeout_record(self) -> dict[str, Any]:
        """Return the W8.E closeout-reader record for this materialization."""

        return build_conflict_materialization_closeout_record(self)


def materialize_cross_graph_conflicts(
    profile: _CrossGraphEvidenceProfileLike,
    *,
    run_id: str,
    claim_id_by_need_id: Mapping[str, str | Sequence[str]],
    claim_registry: Mapping[str, Any] | None = None,
    portfolio_designs: Iterable[Mapping[str, Any]] = (),
    detector: ConflictDetector | None = None,
    producer_handshake_refs: Iterable[str] = (),
    detection_phase: str = "post_hoc_backstop",
) -> ConflictMaterializationResult:
    """Run the ConflictDetector backstop and materialize first-class records."""

    active_detector = detector or ConflictDetector()
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    detector_conflicts: list[EvidenceConflict] = []

    for assessment in getattr(profile, "needs", []) or []:
        dimension_results = _dimension_results_for_assessment(assessment)
        conflicts = active_detector.detect(assessment.need, dimension_results)
        detector_conflicts.extend(conflicts)
        for conflict in conflicts:
            claim_ids = _claim_ids_for_need(conflict.need_id, claim_id_by_need_id)
            if not claim_ids:
                issues.append(_claim_binding_issue(conflict))
                continue
            record = build_conflict_record(
                run_id=run_id,
                claim_ids=claim_ids,
                conflict_type=_conflict_type_for(conflict, assessment),
                severity=conflict.severity.value,
                conflicting_source_refs=_source_refs_for_conflict(conflict, assessment),
                description=conflict.description,
                need_id=conflict.need_id,
                dimension=conflict.dimension,
                detected_by=(
                    "producer_handshake"
                    if detection_phase == "pre_emission_handshake"
                    else "conflict_detector"
                ),
                detection_phase=detection_phase,  # type: ignore[arg-type]
                producer_handshake_refs=producer_handshake_refs,
                source_conflict_signature=_detector_conflict_signature(conflict),
                metadata={
                    "detector": "polisyos.scientist.cross_graph.ConflictDetector",
                    "p14_guard": "conflict_records_do_not_increase_support_mass",
                },
            )
            records.append(record)

    issues.extend(
        validate_conflict_backstop_coverage(
            detector_conflicts,
            conflict_records=records,
        )
    )
    normalized_registry = _apply_conflict_records_to_claim_registry(
        claim_registry,
        conflict_records=records,
        run_id=run_id,
    )
    portfolio_index = build_conflict_portfolio_index(
        records,
        index_id=f"portfolio-conflicts.{run_id}",
        run_id=run_id,
        portfolio_designs=portfolio_designs,
        claim_registry=normalized_registry,
    )
    return ConflictMaterializationResult(
        conflict_records=tuple(records),
        claim_registry=normalized_registry,
        portfolio_index=portfolio_index,
        issues=tuple(issues),
        detector_conflicts=tuple(detector_conflicts),
    )


def validate_conflict_backstop_coverage(
    detected_conflicts: Iterable[EvidenceConflict],
    *,
    conflict_records: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Return closeout-blocking issues for detector conflicts missing W8.E records."""

    materialized_signatures = {
        signature
        for record in conflict_records
        if (signature := _record_source_signature(record))
    }
    issues: list[dict[str, Any]] = []
    for conflict in detected_conflicts:
        signature = _detector_conflict_signature(conflict)
        if signature in materialized_signatures:
            continue
        issues.append(
            {
                "code": "policy_design_conflict_materialization_missing",
                "severity": "fail",
                "layer": "scientist_cross_graph",
                "phase": "w8e_conflict_materializer",
                "need_id": conflict.need_id,
                "missing_evidence_type": "conflict_record",
                "closeout_blocking": True,
                "message": (
                    f"ConflictDetector found conflict {conflict.dimension} for "
                    f"{conflict.need_id}, but no W8.E first-class conflict record "
                    "materialized it."
                ),
                "next_action": (
                    "Run materialize_cross_graph_conflicts and bind the emitted conflict "
                    "record into claim_registry conflict_refs and the portfolio index."
                ),
            }
        )
    return tuple(issues)


def build_conflict_materialization_closeout_record(
    result: ConflictMaterializationResult | Mapping[str, Any],
) -> dict[str, Any]:
    """Build a closeout-reader record from W8.E conflict materialization output."""

    payload = (
        result.to_dict()
        if isinstance(result, ConflictMaterializationResult)
        else dict(result)
    )
    issues = [dict(issue) for issue in _mapping_rows(payload.get("issues"))]
    conflict_records = [dict(record) for record in _mapping_rows(payload.get("conflict_records"))]
    detector_conflicts = [
        dict(conflict) for conflict in _mapping_rows(payload.get("detector_conflicts"))
    ]
    blocking = any(
        bool(issue.get("closeout_blocking"))
        or str(issue.get("severity") or "").casefold() in {"fail", "failed", "critical"}
        for issue in issues
    )
    return {
        "schema_version": CONFLICT_MATERIALIZATION_CLOSEOUT_SCHEMA_VERSION,
        "status": "blocked" if blocking else "pass",
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "producer": "polisyos.scientist.cross_graph.conflict_materializer",
        "reader_contract": CONFLICT_MATERIALIZATION_READER_CONTRACT,
        "conflict_records": conflict_records,
        "claim_registry": dict(payload.get("claim_registry") or {}),
        "portfolio_index": dict(payload.get("portfolio_index") or {}),
        "detector_conflicts": detector_conflicts,
        "issues": issues,
        "summary": {
            "conflict_record_count": len(conflict_records),
            "detector_conflict_count": len(detector_conflicts),
            "closeout_blocking_issue_count": sum(
                1 for issue in issues if bool(issue.get("closeout_blocking"))
            ),
        },
        "authoritative_for": ["conflict_materialization_closeout_reader"],
        "may_not_use_for": ["claim_authority", "support_strength"],
    }


def construct_conflict_markers_for_capability(
    capability: object,
    *,
    conflict_records: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Return W8.E same-construct conflict markers relevant to a capability."""

    capability_payload = _mapping(capability)
    capability_id = _text(
        capability_payload.get("capability_id") or capability_payload.get("id")
    )
    construct = _text(capability_payload.get("construct"))
    lineage_refs = set(_refs(capability_payload.get("lineage_refs")))
    markers: list[dict[str, Any]] = []
    for raw_record in conflict_records:
        record = _mapping(raw_record)
        if not record:
            continue
        metadata = _mapping(record.get("metadata"))
        record_construct = _text(record.get("construct") or metadata.get("construct"))
        if construct and record_construct and record_construct != construct:
            continue
        capability_refs = _refs(record.get("capability_refs") or metadata.get("capability_refs"))
        if capability_refs and capability_id not in capability_refs:
            continue
        source_refs = set(
            _refs(
                record.get("conflicting_source_refs")
                or record.get("evidence_refs")
                or metadata.get("lineage_refs")
            )
        )
        if not capability_refs and not record_construct and lineage_refs and not (
            lineage_refs & source_refs
        ):
            continue
        marker = {
            "conflict_id": _text(record.get("conflict_id") or record.get("id"))
            or f"conflict-marker:{len(markers) + 1}",
            "construct": record_construct or construct,
            "conflict_class": (
                _text(
                    record.get("conflict_class")
                    or metadata.get("conflict_class")
                    or record.get("conflict_type")
                )
                or "empirical"
            ),
            "conflict_resolution_route": (
                _text(
                    record.get("conflict_resolution_route")
                    or metadata.get("conflict_resolution_route")
                    or record.get("resolution_route")
                )
                or "persistent_contested_state"
            ),
            "capability_refs": capability_refs,
            "severity": _text(record.get("severity")) or "medium",
            "status": _text(record.get("status") or record.get("resolution_status"))
            or "contested",
        }
        markers.append(marker)
    return tuple(markers)


def _dimension_results_for_assessment(
    assessment: _EvidenceNeedAssessmentLike,
) -> dict[str, dict[str, str]]:
    return {
        "legal": {"status": _status_value(getattr(assessment, "legal_status", ""))},
        "academic": {"status": _status_value(getattr(assessment, "evidence_status", ""))},
        "dataset": {"status": _status_value(getattr(assessment, "observability_status", ""))},
        "transport": {"status": _status_value(getattr(assessment, "transport_status", ""))},
    }


def _conflict_type_for(
    conflict: EvidenceConflict,
    assessment: _EvidenceNeedAssessmentLike,
) -> str:
    dimension = conflict.dimension.casefold()
    legal_status = _status_value(getattr(assessment, "legal_status", ""))
    if "authority" in dimension or "provenance" in dimension:
        return "authority_provenance"
    if "method" in dimension:
        return "methodological"
    if "legal" in dimension or legal_status == "prohibited":
        return "legal"
    if "scope" in dimension or "transport" in dimension:
        return "scope"
    if "norm" in dimension or "value" in dimension:
        return "normative"
    if "participation" in dimension:
        return "participation"
    if "implementation" in dimension or "dataset" in dimension:
        return "empirical"
    return "empirical"


def _source_refs_for_conflict(
    conflict: EvidenceConflict,
    assessment: _EvidenceNeedAssessmentLike,
) -> list[str]:
    provenance_refs = _refs(getattr(assessment, "provenance_refs", ()))
    if provenance_refs:
        return provenance_refs
    return _refs(conflict.conflicting_sources)


def _claim_ids_for_need(
    need_id: str,
    claim_id_by_need_id: Mapping[str, str | Sequence[str]],
) -> list[str]:
    return _refs(claim_id_by_need_id.get(need_id))


def _apply_conflict_records_to_claim_registry(
    claim_registry: Mapping[str, Any] | None,
    *,
    conflict_records: Sequence[Mapping[str, Any]],
    run_id: str,
) -> dict[str, Any]:
    del run_id
    payload = dict(
        claim_registry
        or {
            "schema_version": "policyos.runtime.claim_registry.v1",
            "claims": [],
        }
    )
    rows = _claim_rows(payload)
    rows_by_claim = {str(row.get("claim_id")): row for row in rows if row.get("claim_id")}

    for raw_record in conflict_records:
        record = validate_conflict_record(raw_record)
        conflict_ref = str(record["conflict_id"])
        for claim_id in _refs(record.get("claim_ids")):
            row = rows_by_claim.get(claim_id)
            if row is None:
                row = {"claim_id": claim_id}
                rows.append(row)
                rows_by_claim[claim_id] = row
            row["conflict_refs"] = _dedupe([*_refs(row.get("conflict_refs")), conflict_ref])
            if record.get("claim_registry_effect") == "add_conflict_ref_and_counterevidence":
                row["counter_evidence_refs"] = _dedupe(
                    [*_refs(row.get("counter_evidence_refs")), conflict_ref]
                )

    payload["claims"] = rows
    return payload


def _claim_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    raw = payload.get("claims")
    if isinstance(raw, Mapping):
        for claim_id, row in raw.items():
            if not isinstance(row, Mapping):
                continue
            merged = dict(row)
            merged.setdefault("claim_id", str(claim_id))
            rows.append(merged)
        return rows
    if isinstance(raw, Sequence) and not isinstance(raw, str | bytes | bytearray):
        return [dict(row) for row in raw if isinstance(row, Mapping)]
    return rows


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [row for row in value.values() if isinstance(row, Mapping)]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [row for row in value if isinstance(row, Mapping)]
    return []


def _mapping(value: object) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _claim_binding_issue(conflict: EvidenceConflict) -> dict[str, Any]:
    return {
        "code": "policy_design_conflict_claim_binding_missing",
        "severity": "fail",
        "layer": "scientist_cross_graph",
        "phase": "w8e_conflict_materializer",
        "need_id": conflict.need_id,
        "missing_evidence_type": "claim_binding",
        "closeout_blocking": True,
        "message": (
            f"Conflict {conflict.dimension} for {conflict.need_id} cannot be "
            "materialized without a claim binding."
        ),
        "next_action": (
            "Provide claim_id_by_need_id from the compiled PDC graph or producer "
            "handshake before accepting the conflict record."
        ),
    }


def _record_source_signature(record: Mapping[str, Any]) -> str | None:
    try:
        normalized = validate_conflict_record(record)
    except Exception:
        return None
    signature = normalized.get("source_conflict_signature")
    return str(signature) if signature else None


def _detector_conflict_signature(conflict: EvidenceConflict) -> str:
    payload = {
        "need_id": conflict.need_id,
        "dimension": conflict.dimension,
        "conflicting_sources": list(conflict.conflicting_sources),
        "severity": conflict.severity.value,
        "description": conflict.description,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "conflict-detector:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _status_value(value: object) -> str:
    raw_value = getattr(value, "value", value)
    return str(raw_value or "").strip()


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _refs(value: object) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Mapping):
        refs: list[str] = []
        for key in (
            "ref",
            "id",
            "claim_id",
            "source_ref",
            "source_id",
            "artifact_ref",
            "evidence_ref",
        ):
            refs.extend(_refs(value.get(key)))
        return _dedupe(refs)
    if isinstance(value, Iterable):
        refs: list[str] = []
        for item in value:
            refs.extend(_refs(item))
        return _dedupe(refs)
    return []


def _dedupe(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


__all__ = [
    "CONFLICT_MATERIALIZATION_CLOSEOUT_SCHEMA_VERSION",
    "CONFLICT_MATERIALIZATION_READER_CONTRACT",
    "ConflictMaterializationResult",
    "build_conflict_materialization_closeout_record",
    "materialize_cross_graph_conflicts",
    "validate_conflict_backstop_coverage",
]
