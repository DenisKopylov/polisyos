"""Recognize legal subjects relative to independently addressed source tables.

This owner compares source identities; it does not mint legal identities or
institutional authority. Synthetic annotations and unverified real annotations
are useful candidate inputs, and neither can authorize a governed law mapping.
Runtime owns the current L6/L3 entity projection supplied in the request.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, model_validator

from polisyos.core import artifacts, canon

_SOURCE_EPOCH = "policyos.foundry.legal_subject_membership.v1"
_ANNOTATION_EPOCH = "policyos.foundry.legal_subject_annotations.v1"
_SPINE_EPOCH = "policyos.foundry.legal_subject_spine.v1"
_RESULT_EPOCH = "policyos.foundry.legal_correspondence.v1"
_SOURCE_KIND = "foundry.legal_subject_membership"
_ANNOTATION_KIND = "foundry.legal_subject_annotations"
_SPINE_KIND = "foundry.legal_subject_spine"
_RESULT_KIND = "foundry.legal_correspondence"
_PRODUCER = "polisyos.foundry.validation.legal_correspondence"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LegalSubjectIdentity(_StrictModel):
    """One subject identity in a versioned, temporally bounded namespace."""

    namespace: str = Field(min_length=1)
    namespace_version: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    valid_from: date
    valid_until: date | None = None

    @model_validator(mode="after")
    def _ordered_scope(self) -> LegalSubjectIdentity:
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("legal_subject_scope_invalid")
        return self


class LegalSubjectMembership(_StrictModel):
    """A source annotation bound to a specific entity's content."""

    entity_ref: str = Field(min_length=1)
    entity_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    subject: LegalSubjectIdentity | None = None


class _LegalSubjectAnnotation(_StrictModel):
    entity_ref: str = Field(min_length=1)
    subject: LegalSubjectIdentity | None = None


class LegalSubjectAnnotationSource(_StrictModel):
    """A dated source declaration independent of a proposed law/lever relation."""

    schema_version: Literal["policyos.foundry.legal_subject_annotations.v1"] = _ANNOTATION_EPOCH
    synthetic: bool = Field(strict=True)
    declared_at: date
    source_role: Literal["lever", "norm"]
    producer_ref: str = Field(min_length=1)
    annotations: tuple[_LegalSubjectAnnotation, ...]


class LegalSubjectMembershipSource(_StrictModel):
    """An independently addressed source, never a mapping proposal's answer."""

    schema_version: Literal["policyos.foundry.legal_subject_membership.v1"] = _SOURCE_EPOCH
    synthetic: bool = Field(strict=True)
    source_role: Literal["lever", "norm"]
    producer_ref: str = Field(min_length=1)
    memberships: tuple[LegalSubjectMembership, ...]
    source_authority_ref: artifacts.ArtifactRef | None = None


class _LegalSubjectSpine(_StrictModel):
    schema_version: Literal["policyos.foundry.legal_subject_spine.v1"] = _SPINE_EPOCH
    synthetic: bool = Field(strict=True)
    lever_source_ref: artifacts.ArtifactRef
    norm_source_ref: artifacts.ArtifactRef


class LegalCorrespondenceRequest(_StrictModel):
    """Current entity projections from their owner, relative to a source spine."""

    lever_ref: str = Field(min_length=1)
    lever_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    norm_ref: str = Field(min_length=1)
    norm_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    as_of: date
    proposal_producer_ref: str = Field(min_length=1)
    proposal_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LegalCorrespondenceResult(_StrictModel):
    """A content-bound comparison whose authority ceiling survives persistence."""

    schema_version: Literal["policyos.foundry.legal_correspondence.v1"] = _RESULT_EPOCH
    status: Literal["passed", "rejected", "ambiguous"]
    reason_code: str = Field(min_length=1)
    synthetic: bool | None = Field(strict=True)
    recognition_scope: Literal["source_relative"] = "source_relative"
    request: LegalCorrespondenceRequest
    submitted_source: dict[str, JsonValue] | None
    source_ref: artifacts.ArtifactRef | None = None
    comparison_predicate_provenance: Literal["recomputed", "not_established"]
    current_entity_binding_predicate_provenance: Literal["consumer_asserted"] = "consumer_asserted"
    legal_authority_predicate_provenance: Literal["not_established"] = "not_established"
    current_authority_status: Literal["blocked"] = "blocked"


def _persist(
    store: artifacts.ArtifactStore, record: BaseModel, *, kind: str, epoch: str,
    producer: str, inputs: list[artifacts.InputRef] | None = None,
) -> artifacts.ArtifactRef:
    return store.put_json(
        record.model_dump(mode="json"),
        artifacts.PutOptions(
            kind=kind, media_type="application/json",
            schema=artifacts.SchemaInfo(name=kind, version=epoch),
            producer=artifacts.ProducerInfo(component=producer, version=epoch), inputs=inputs,
        ),
    )


def persist_legal_subject_membership_source(
    store: artifacts.ArtifactStore, source: LegalSubjectMembershipSource,
    *, inputs: list[artifacts.InputRef] | None = None,
) -> artifacts.ArtifactRef:
    """Persist a source table separately, before any proposal is evaluated."""
    source = LegalSubjectMembershipSource.model_validate(source.model_dump(mode="json"))
    return _persist(store, source, kind=_SOURCE_KIND, epoch=_SOURCE_EPOCH,
                    producer=source.producer_ref, inputs=inputs)


def persist_legal_subject_annotations(
    store: artifacts.ArtifactStore, declaration: LegalSubjectAnnotationSource,
) -> artifacts.ArtifactRef:
    """Persist an independent annotation declaration before any proposal run."""
    declaration = LegalSubjectAnnotationSource.model_validate(declaration.model_dump(mode="json"))
    return _persist(store, declaration, kind=_ANNOTATION_KIND, epoch=_ANNOTATION_EPOCH,
                    producer=declaration.producer_ref)


def bind_legal_subject_annotations(
    store: artifacts.ArtifactStore, declaration_ref: artifacts.ArtifactRef,
    entity_content_hashes: Mapping[str, str],
) -> artifacts.ArtifactRef:
    """Bind declared membership to owner-projected content without reading a mapping."""
    declaration = _load(store, declaration_ref, kind=_ANNOTATION_KIND,
                        epoch=_ANNOTATION_EPOCH, model=LegalSubjectAnnotationSource)
    if any(row.entity_ref not in entity_content_hashes for row in declaration.annotations):
        raise ValueError("legal_subject_annotation_entity_unresolved")
    source = LegalSubjectMembershipSource(
        synthetic=declaration.synthetic, source_role=declaration.source_role,
        producer_ref=declaration.producer_ref,
        memberships=tuple(LegalSubjectMembership(
            entity_ref=row.entity_ref, entity_content_hash=entity_content_hashes[row.entity_ref],
            subject=row.subject) for row in declaration.annotations),
    )
    return persist_legal_subject_membership_source(store, source, inputs=[artifacts.InputRef(
        artifact_id=declaration_ref.artifact_id, role="subject_annotation_declaration")])


def _load(
    store: artifacts.ArtifactStore, ref: artifacts.ArtifactRef, *, kind: str,
    epoch: str, model: type[_StrictModel],
) -> Any:
    manifest = store.get_manifest(ref.artifact_id)
    if (ref.kind != kind or ref.media_type != "application/json" or manifest.kind != kind
            or manifest.artifact_schema is None or manifest.artifact_schema.version != epoch):
        raise ValueError("legal_subject_source_shape_invalid")
    payload = store.get_bytes(ref.artifact_id)
    # Do not trust an ArtifactStore implementation to validate a supplied ref.
    if canon.content_hash(payload, prefix=True) != str(ref.artifact_id):
        raise ValueError("legal_subject_source_content_mismatch")
    return model.model_validate(canon.from_canonical_bytes(payload))


def _ancestry(
    store: artifacts.ArtifactStore, ref: artifacts.ArtifactRef,
) -> tuple[set[str], set[str], bool]:
    seen: set[str] = set()
    producers: set[str] = set()
    active: set[str] = set()
    synthetic = False

    def inspect_json(value: Any) -> None:
        nonlocal synthetic
        if isinstance(value, Mapping):
            if "synthetic" in value:
                if not isinstance(value["synthetic"], bool):
                    raise ValueError("legal_subject_synthetic_marker_invalid")
                synthetic = synthetic or value["synthetic"]
            for child in value.values():
                inspect_json(child)
        elif isinstance(value, list):
            for child in value:
                inspect_json(child)

    def visit(artifact_id: artifacts.ArtifactID) -> None:
        key = str(artifact_id)
        if key in active:
            raise ValueError("legal_subject_source_circular")
        if key in seen:
            return
        active.add(key)
        manifest = store.get_manifest(artifact_id)
        raw = store.get_bytes(artifact_id)
        if canon.content_hash(raw, prefix=True) != key:
            raise ValueError("legal_subject_source_content_mismatch")
        if manifest.media_type == "application/json":
            inspect_json(canon.from_canonical_bytes(raw))
        if manifest.producer is not None:
            producers.add(str(manifest.producer.component))
        for item in manifest.inputs:
            visit(item.artifact_id)
        active.remove(key)
        seen.add(key)

    visit(ref.artifact_id)
    return seen, producers, synthetic


def _sources(
    store: artifacts.ArtifactStore, lever_ref: artifacts.ArtifactRef,
    norm_ref: artifacts.ArtifactRef,
) -> tuple[LegalSubjectMembershipSource, LegalSubjectMembershipSource, set[str], set[str]]:
    lever = _load(store, lever_ref, kind=_SOURCE_KIND, epoch=_SOURCE_EPOCH,
                  model=LegalSubjectMembershipSource)
    norm = _load(store, norm_ref, kind=_SOURCE_KIND, epoch=_SOURCE_EPOCH,
                 model=LegalSubjectMembershipSource)
    if lever.source_role != "lever" or norm.source_role != "norm":
        raise ValueError("legal_subject_source_role_mismatch")
    for ref, source in ((lever_ref, lever), (norm_ref, norm)):
        producer = store.get_manifest(ref.artifact_id).producer
        if producer is None or str(producer.component) != source.producer_ref:
            raise ValueError("legal_subject_source_producer_mismatch")
    lever_ids, lever_producers, lever_synthetic = _ancestry(store, lever_ref)
    norm_ids, norm_producers, norm_synthetic = _ancestry(store, norm_ref)
    if (lever_synthetic and not lever.synthetic) or (norm_synthetic and not norm.synthetic):
        raise ValueError("legal_subject_synthetic_lineage_mismatch")
    if lever_ids & norm_ids or lever_producers & norm_producers:
        raise ValueError("legal_subject_source_circular")
    return lever, norm, lever_ids | norm_ids, lever_producers | norm_producers


def produce_legal_subject_spine(
    store: artifacts.ArtifactStore, *, lever_source_ref: artifacts.ArtifactRef,
    norm_source_ref: artifacts.ArtifactRef,
) -> artifacts.ArtifactRef:
    """Resolve independent source tables and persist their binding, without a proposal."""
    lever, norm, _, _ = _sources(store, lever_source_ref, norm_source_ref)
    spine = _LegalSubjectSpine(synthetic=lever.synthetic or norm.synthetic,
                              lever_source_ref=lever_source_ref, norm_source_ref=norm_source_ref)
    return _persist(store, spine, kind=_SPINE_KIND, epoch=_SPINE_EPOCH, producer=_PRODUCER,
                    inputs=[artifacts.InputRef(artifact_id=lever_source_ref.artifact_id,
                                               role="lever_membership"),
                            artifacts.InputRef(artifact_id=norm_source_ref.artifact_id,
                                               role="norm_membership")])


def _membership(
    source: LegalSubjectMembershipSource, entity_ref: str, digest: str, as_of: date,
) -> tuple[LegalSubjectIdentity | None, str | None]:
    candidates = [row for row in source.memberships if row.entity_ref == entity_ref]
    if not candidates or any(row.subject is None for row in candidates):
        return None, "legal_subject_missing"
    if any(row.entity_content_hash != digest for row in candidates):
        return None, "legal_subject_entity_content_mismatch"
    applicable = [row.subject for row in candidates if row.subject is not None
                  and row.subject.valid_from <= as_of
                  and (row.subject.valid_until is None or as_of < row.subject.valid_until)]
    if not applicable:
        return None, "legal_subject_scope_unresolved"
    if len(applicable) != 1:
        return None, "legal_subject_ambiguous"
    return applicable[0], None


def _same_subject(lever: LegalSubjectIdentity, norm: LegalSubjectIdentity) -> bool:
    return ((lever.namespace, lever.namespace_version, lever.subject_id)
            == (norm.namespace, norm.namespace_version, norm.subject_id))


def recognize_legal_correspondence(
    store: artifacts.ArtifactStore | None,
    source_ref: artifacts.ArtifactRef | Mapping[str, Any] | None,
    request: LegalCorrespondenceRequest,
) -> LegalCorrespondenceResult:
    """Recompute source-relative correspondence without granting legal authority."""
    request = LegalCorrespondenceRequest.model_validate(request.model_dump(mode="json"))
    submitted = (source_ref.model_dump(mode="json")
                 if isinstance(source_ref, artifacts.ArtifactRef) else source_ref)
    submitted = TypeAdapter(dict[str, JsonValue] | None).validate_python(submitted)

    def result(status: str, reason: str, *, ref=None, synthetic=None, recomputed=False):
        return LegalCorrespondenceResult(
            status=status, reason_code=reason, request=request,
            submitted_source=submitted, source_ref=ref,
            synthetic=synthetic,
            comparison_predicate_provenance="recomputed" if recomputed else "not_established",
        )

    if source_ref is None:
        return result("ambiguous", "legal_subject_source_missing")
    try:
        ref = artifacts.ArtifactRef.model_validate(source_ref)
        if store is None:
            raise ValueError("legal_subject_store_missing")
        spine = _load(store, ref, kind=_SPINE_KIND, epoch=_SPINE_EPOCH, model=_LegalSubjectSpine)
        lever, norm, ids, producers = _sources(store, spine.lever_source_ref, spine.norm_source_ref)
        manifest = store.get_manifest(ref.artifact_id)
        if {(str(item.artifact_id), item.role) for item in manifest.inputs} != {
            (str(spine.lever_source_ref.artifact_id), "lever_membership"),
            (str(spine.norm_source_ref.artifact_id), "norm_membership"),
        } or spine.synthetic != (lever.synthetic or norm.synthetic):
            raise ValueError("legal_subject_spine_binding_mismatch")
        if request.proposal_content_hash in ids or request.proposal_producer_ref in producers:
            return result("rejected", "legal_subject_source_circular", ref=ref,
                          synthetic=spine.synthetic, recomputed=True)
    except (ValueError, OSError, KeyError) as exc:
        reason = ("legal_subject_source_circular" if "legal_subject_source_circular" in str(exc)
                  else "legal_subject_source_invalid")
        return result("ambiguous", reason)
    left, left_error = _membership(lever, request.lever_ref, request.lever_content_hash, request.as_of)
    right, right_error = _membership(norm, request.norm_ref, request.norm_content_hash, request.as_of)
    if left_error or right_error:
        return result("ambiguous", left_error or right_error, ref=ref,
                      synthetic=spine.synthetic, recomputed=True)
    assert left is not None
    assert right is not None
    matched = _same_subject(left, right)
    return result("passed" if matched else "rejected",
                  "legal_subject_correspondence_recognized" if matched else "legal_subject_mismatch",
                  ref=ref, synthetic=spine.synthetic, recomputed=True)


def persist_legal_correspondence_result(
    store: artifacts.ArtifactStore, result: LegalCorrespondenceResult,
) -> artifacts.ArtifactRef:
    """Persist the comparison and its non-authority ceiling for downstream audit."""
    result = LegalCorrespondenceResult.model_validate(result.model_dump(mode="json"))
    recomputed = recognize_legal_correspondence(store, result.submitted_source, result.request)
    if result != recomputed:
        raise ValueError("legal_subject_result_recomputation_mismatch")
    inputs = ([] if result.source_ref is None else [artifacts.InputRef(
        artifact_id=result.source_ref.artifact_id, role="legal_subject_source")])
    return _persist(store, result, kind=_RESULT_KIND, epoch=_RESULT_EPOCH,
                    producer=_PRODUCER, inputs=inputs)
