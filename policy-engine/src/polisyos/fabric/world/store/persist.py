"""Persist world-domain artifacts so later stages can materialize and query them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.fabric.security import DataClassification, RetentionScope, resolve_artifact_governance
from polisyos.ir.world.claim import Claim, ClaimSourceKind

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.ir.world.conflict import ConflictSet
    from polisyos.ir.world.doc import DocFragment, DocMeta
    from polisyos.ir.world.event import WorldEvent
    from polisyos.ir.world.quality import QualityReport
    from polisyos.ir.world.trust import TrustAssessment

_DOC_META_KIND = "fabric.world.doc_meta"
_DOC_FRAGMENT_KIND = "fabric.world.doc_fragment"
_CLAIM_KIND = "fabric.world.claim"
_CONFLICT_SET_KIND = "fabric.world.conflict_set"
_TRUST_ASSESSMENT_KIND = "fabric.world.trust_assessment"
_QUALITY_REPORT_KIND = "fabric.world.quality_report"
_WORLD_EVENT_KIND = "fabric.world.event"

_DOC_META_SCHEMA = SchemaInfo(name="polisyos.ir.world.DocMeta", version="1.0")
_DOC_FRAGMENT_SCHEMA = SchemaInfo(name="polisyos.ir.world.DocFragment", version="1.0")
_CLAIM_SCHEMA = SchemaInfo(name="polisyos.ir.world.Claim", version="1.0")
_CONFLICT_SET_SCHEMA = SchemaInfo(name="polisyos.ir.world.ConflictSet", version="1.0")
_TRUST_ASSESSMENT_SCHEMA = SchemaInfo(name="polisyos.ir.world.TrustAssessment", version="1.0")
_QUALITY_REPORT_SCHEMA = SchemaInfo(name="polisyos.ir.world.QualityReport", version="1.0")
_WORLD_EVENT_SCHEMA = SchemaInfo(name="polisyos.ir.world.WorldEvent", version="1.0")


def _to_input_ref(artifact_id: str, *, role: str) -> InputRef:
    return InputRef(artifact_id=ArtifactID.model_validate(artifact_id), role=role)


def _world_write_options(
    *,
    kind: str,
    schema: SchemaInfo,
    inputs: list[InputRef] | None = None,
    classification: DataClassification | str | None = None,
    encrypted_at_rest: bool = False,
    field_level_encrypted: bool = False,
    encryption_key_reference: str | None = None,
) -> ArtifactWriteOptions:
    return ArtifactWriteOptions(
        kind=kind,
        media_type="application/json",
        schema=schema,
        inputs=inputs,
        governance=resolve_artifact_governance(
            scope=RetentionScope.CAS,
            classification=classification,
            encrypted_at_rest=encrypted_at_rest,
            field_level_encrypted=field_level_encrypted,
            encryption_key_reference=encryption_key_reference,
        ),
    )


def persist_doc_meta(
    store: ArtifactStore,
    meta: DocMeta,
    *,
    classification: DataClassification | str | None = None,
    encrypted_at_rest: bool = False,
    field_level_encrypted: bool = False,
    encryption_key_reference: str | None = None,
) -> ArtifactRef:
    """Persist `DocMeta` produced by ingest and structure stages with upstream artifact links."""
    inputs = [_to_input_ref(meta.raw_ref, role="raw_ref")]
    if meta.normalized_ref is not None:
        inputs.append(_to_input_ref(meta.normalized_ref, role="normalized_ref"))
    if meta.structure_ref is not None:
        inputs.append(_to_input_ref(meta.structure_ref, role="structure_ref"))
    if meta.chunks_ref is not None:
        inputs.append(_to_input_ref(meta.chunks_ref, role="chunks_ref"))
    return store.put_json(
        meta.model_dump(),
        opts=_world_write_options(
            kind=_DOC_META_KIND,
            schema=_DOC_META_SCHEMA,
            inputs=inputs,
            classification=classification,
            encrypted_at_rest=encrypted_at_rest,
            field_level_encrypted=field_level_encrypted,
            encryption_key_reference=encryption_key_reference,
        ),
    )


def persist_doc_fragment(
    store: ArtifactStore,
    fragment: DocFragment,
    *,
    classification: DataClassification | str | None = None,
    encrypted_at_rest: bool = False,
    field_level_encrypted: bool = False,
    encryption_key_reference: str | None = None,
) -> ArtifactRef:
    """Persist a structured document fragment so claims and corpus stages can cite it."""
    inputs = [_to_input_ref(fragment.text_hash, role="text_hash")]
    return store.put_json(
        fragment.model_dump(),
        opts=_world_write_options(
            kind=_DOC_FRAGMENT_KIND,
            schema=_DOC_FRAGMENT_SCHEMA,
            inputs=inputs,
            classification=classification,
            encrypted_at_rest=encrypted_at_rest,
            field_level_encrypted=field_level_encrypted,
            encryption_key_reference=encryption_key_reference,
        ),
    )


def persist_claim(
    store: ArtifactStore,
    claim: Claim,
    *,
    classification: DataClassification | str | None = None,
    encrypted_at_rest: bool = False,
    field_level_encrypted: bool = False,
    encryption_key_reference: str | None = None,
) -> ArtifactRef:
    """Persist a normalized claim with evidence inputs for later reloads."""
    inputs: list[InputRef] = []
    if claim.source_kind == ClaimSourceKind.DOC:
        seen: set[str] = set()
        for citation in claim.citations:
            for artifact_id, role in (
                (citation.text_hash, "citation_text"),
                (citation.quote_hash, "citation_quote"),
            ):
                if artifact_id and artifact_id not in seen:
                    seen.add(artifact_id)
                    inputs.append(_to_input_ref(artifact_id, role=role))
    else:
        for artifact_id in claim.source_artifacts:
            inputs.append(_to_input_ref(artifact_id, role="source_artifact"))
    return store.put_json(
        claim.model_dump(),
        opts=_world_write_options(
            kind=_CLAIM_KIND,
            schema=_CLAIM_SCHEMA,
            inputs=inputs or None,
            classification=classification,
            encrypted_at_rest=encrypted_at_rest,
            field_level_encrypted=field_level_encrypted,
            encryption_key_reference=encryption_key_reference,
        ),
    )


def persist_conflict_set(
    store: ArtifactStore,
    conflict_set: ConflictSet,
    *,
    classification: DataClassification | str | None = None,
    encrypted_at_rest: bool = False,
    field_level_encrypted: bool = False,
    encryption_key_reference: str | None = None,
) -> ArtifactRef:
    """Persist a detected conflict set before resolution and intervention mapping."""
    return store.put_json(
        conflict_set.model_dump(),
        opts=_world_write_options(
            kind=_CONFLICT_SET_KIND,
            schema=_CONFLICT_SET_SCHEMA,
            classification=classification,
            encrypted_at_rest=encrypted_at_rest,
            field_level_encrypted=field_level_encrypted,
            encryption_key_reference=encryption_key_reference,
        ),
    )


def persist_trust_assessment(
    store: ArtifactStore,
    assessment: TrustAssessment,
    *,
    classification: DataClassification | str | None = None,
    encrypted_at_rest: bool = False,
    field_level_encrypted: bool = False,
    encryption_key_reference: str | None = None,
) -> ArtifactRef:
    """Persist trust-scoring output for a world object or claim family."""
    return store.put_json(
        assessment.model_dump(),
        opts=_world_write_options(
            kind=_TRUST_ASSESSMENT_KIND,
            schema=_TRUST_ASSESSMENT_SCHEMA,
            classification=classification,
            encrypted_at_rest=encrypted_at_rest,
            field_level_encrypted=field_level_encrypted,
            encryption_key_reference=encryption_key_reference,
        ),
    )


def persist_quality_report(
    store: ArtifactStore,
    report: QualityReport,
    *,
    classification: DataClassification | str | None = None,
    encrypted_at_rest: bool = False,
    field_level_encrypted: bool = False,
    encryption_key_reference: str | None = None,
) -> ArtifactRef:
    """Persist fabric quality metrics that summarize ingestion or retrieval health."""
    return store.put_json(
        report.model_dump(),
        opts=_world_write_options(
            kind=_QUALITY_REPORT_KIND,
            schema=_QUALITY_REPORT_SCHEMA,
            classification=classification,
            encrypted_at_rest=encrypted_at_rest,
            field_level_encrypted=field_level_encrypted,
            encryption_key_reference=encryption_key_reference,
        ),
    )


def persist_world_event(
    store: ArtifactStore,
    event: WorldEvent,
    *,
    classification: DataClassification | str | None = None,
    encrypted_at_rest: bool = False,
    field_level_encrypted: bool = False,
    encryption_key_reference: str | None = None,
) -> ArtifactRef:
    """Persist a provenance event linking workflow inputs, outputs, and emitted artifacts."""
    inputs: list[InputRef] = []
    seen: set[str] = set()
    if event.evidence_ref is not None:
        seen.add(event.evidence_ref)
        inputs.append(_to_input_ref(event.evidence_ref, role="evidence_ref"))
    if event.provenance_ref is not None and event.provenance_ref not in seen:
        seen.add(event.provenance_ref)
        inputs.append(_to_input_ref(event.provenance_ref, role="provenance_ref"))

    for ref in list(event.inputs) + list(event.outputs):
        if ref.artifact_id and ref.artifact_id not in seen:
            seen.add(ref.artifact_id)
            inputs.append(_to_input_ref(ref.artifact_id, role="world_object"))

    return store.put_json(
        event.model_dump(),
        opts=_world_write_options(
            kind=_WORLD_EVENT_KIND,
            schema=_WORLD_EVENT_SCHEMA,
            inputs=inputs or None,
            classification=classification,
            encrypted_at_rest=encrypted_at_rest,
            field_level_encrypted=field_level_encrypted,
            encryption_key_reference=encryption_key_reference,
        ),
    )


__all__ = [
    "persist_claim",
    "persist_conflict_set",
    "persist_doc_fragment",
    "persist_doc_meta",
    "persist_quality_report",
    "persist_trust_assessment",
    "persist_world_event",
]
