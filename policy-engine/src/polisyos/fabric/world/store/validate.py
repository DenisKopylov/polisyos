"""Public store validate module API."""

from __future__ import annotations

import re
from enum import Enum

from polisyos.ir.fact_log import Fact
from polisyos.ir.kernel.base import ARTIFACT_ID_PATTERN, ID_PATTERN
from polisyos.ir.world.abi import EdgeKind, NodeKind
from polisyos.ir.world.claim import Claim
from polisyos.ir.world.conflict import ConflictSet
from polisyos.ir.world.doc import DocFragment, DocMeta
from polisyos.ir.world.event import WorldEvent
from polisyos.ir.world.ids import (
    claim_id_from_payload,
    conflict_set_id_from_key,
    doc_fragment_id,
    doc_source_id,
    doc_version_id_from_raw_artifact,
    quality_report_id_from_payload,
    trust_assessment_id_from_payload,
    world_event_id_from_payload,
)
from polisyos.ir.world.predicates import (
    WORLD_ARTIFACT_ID,
    WORLD_KIND,
    WORLD_LABEL,
    WORLD_PROPS_REF,
    WORLD_REL_PREFIX,
)
from polisyos.ir.world.quality import QualityReport
from polisyos.ir.world.trust import TrustAssessment

from .errors import WorldFactError, WorldIDError

_ID_RE = re.compile(ID_PATTERN)
_ARTIFACT_RE = re.compile(ARTIFACT_ID_PATTERN)

_ALLOWED_WORLD_ATTRS = {
    WORLD_KIND,
    WORLD_LABEL,
    WORLD_ARTIFACT_ID,
    WORLD_PROPS_REF,
}


def _enum_value(value) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def validate_doc_meta_ids(meta: DocMeta) -> None:
    """Validate doc meta ids."""
    expected_source = doc_source_id(
        canonical_url=meta.canonical_url,
        official_id=meta.official_id,
    )
    if meta.doc_source_id != expected_source:
        raise WorldIDError(f"doc_source_id mismatch: {meta.doc_source_id} != {expected_source}")
    expected_version = doc_version_id_from_raw_artifact(raw_artifact_id=meta.raw_ref)
    if meta.doc_version_id != expected_version:
        raise WorldIDError(f"doc_version_id mismatch: {meta.doc_version_id} != {expected_version}")


def validate_doc_fragment_ids(fragment: DocFragment) -> None:
    """Validate doc fragment ids."""
    expected_fragment = doc_fragment_id(
        doc_version_id=fragment.doc_version_id,
        locator=fragment.locator,
        text_artifact_id=fragment.text_hash,
    )
    if fragment.fragment_id != expected_fragment:
        raise WorldIDError(f"fragment_id mismatch: {fragment.fragment_id} != {expected_fragment}")


def validate_claim_id(claim: Claim) -> None:
    """Validate claim id."""
    expected = claim_id_from_payload(claim_payload=claim.model_dump())
    if claim.claim_id != expected:
        raise WorldIDError(f"claim_id mismatch: {claim.claim_id} != {expected}")


def validate_world_event_id(event: WorldEvent) -> None:
    """Validate world event id."""
    expected = world_event_id_from_payload(event_payload=event.model_dump())
    if event.event_id != expected:
        raise WorldIDError(f"event_id mismatch: {event.event_id} != {expected}")


def validate_conflict_set_id(conflict_set: ConflictSet) -> None:
    """Validate conflict set id."""
    expected = conflict_set_id_from_key(conflict_key=conflict_set.conflict_key)
    if conflict_set.conflict_set_id != expected:
        raise WorldIDError(
            f"conflict_set_id mismatch: {conflict_set.conflict_set_id} != {expected}"
        )


def validate_trust_assessment_id(assessment: TrustAssessment) -> None:
    """Validate trust assessment id."""
    payload = assessment.model_dump()
    payload.pop("schema_version", None)
    payload.pop("trust_assessment_id", None)
    expected = trust_assessment_id_from_payload(payload=payload)
    if assessment.trust_assessment_id != expected:
        raise WorldIDError(
            f"trust_assessment_id mismatch: {assessment.trust_assessment_id} != {expected}"
        )


def validate_quality_report_id(report: QualityReport) -> None:
    """Validate quality report id."""
    payload = report.model_dump()
    payload.pop("schema_version", None)
    payload.pop("quality_report_id", None)
    expected = quality_report_id_from_payload(payload=payload)
    if report.quality_report_id != expected:
        raise WorldIDError(f"quality_report_id mismatch: {report.quality_report_id} != {expected}")


def validate_fact_is_world_abi(fact: Fact, *, strict_edge_kinds: bool = False) -> None:
    """Validate fact is world abi."""
    if _ID_RE.fullmatch(fact.subject_id) is None:
        raise WorldFactError(f"subject_id '{fact.subject_id}' does not match {ID_PATTERN}")
    if _ID_RE.fullmatch(fact.predicate_id) is None:
        raise WorldFactError(f"predicate_id '{fact.predicate_id}' does not match {ID_PATTERN}")

    if fact.predicate_id.startswith(WORLD_REL_PREFIX):
        if fact.target_id is None:
            raise WorldFactError("world.rel.* facts require target_id")
        if fact.object_value is not None:
            raise WorldFactError("world.rel.* facts require object_value=None")
        edge_kind = fact.predicate_id[len(WORLD_REL_PREFIX) :]
        if _ID_RE.fullmatch(edge_kind) is None:
            raise WorldFactError(f"edge kind '{edge_kind}' does not match {ID_PATTERN}")
        if strict_edge_kinds:
            allowed = {kind.value for kind in EdgeKind}
            if edge_kind not in allowed:
                raise WorldFactError(f"edge kind '{edge_kind}' not in EdgeKind")
    else:
        if fact.target_id is not None:
            raise WorldFactError("world attribute facts must not set target_id")
        if fact.object_value is None:
            raise WorldFactError("world attribute facts require object_value")
        if fact.predicate_id.startswith("world."):
            if fact.predicate_id not in _ALLOWED_WORLD_ATTRS:
                raise WorldFactError(f"unsupported world attribute predicate '{fact.predicate_id}'")
        if fact.predicate_id == WORLD_KIND:
            value = _enum_value(fact.object_value)
            if value not in {kind.value for kind in NodeKind}:
                raise WorldFactError(f"world.kind value '{fact.object_value}' not in NodeKind")
        if fact.predicate_id in {WORLD_ARTIFACT_ID, WORLD_PROPS_REF} and (
            not isinstance(fact.object_value, str)
            or _ARTIFACT_RE.fullmatch(fact.object_value) is None
        ):
            raise WorldFactError(f"{fact.predicate_id} must match {ARTIFACT_ID_PATTERN}")


def validate_world_facts(facts: list[Fact]) -> None:
    """Validate world facts."""
    for fact in facts:
        validate_fact_is_world_abi(fact)


__all__ = [
    "validate_claim_id",
    "validate_conflict_set_id",
    "validate_doc_fragment_ids",
    "validate_doc_meta_ids",
    "validate_fact_is_world_abi",
    "validate_quality_report_id",
    "validate_trust_assessment_id",
    "validate_world_event_id",
    "validate_world_facts",
]
