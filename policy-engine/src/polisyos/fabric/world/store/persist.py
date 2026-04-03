"""Public store persist module API."""
from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir.world.claim import Claim, ClaimSourceKind
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
_TRUST_ASSESSMENT_SCHEMA = SchemaInfo(
    name="polisyos.ir.world.TrustAssessment", version="1.0"
)
_QUALITY_REPORT_SCHEMA = SchemaInfo(name="polisyos.ir.world.QualityReport", version="1.0")
_WORLD_EVENT_SCHEMA = SchemaInfo(name="polisyos.ir.world.WorldEvent", version="1.0")


def _to_input_ref(artifact_id: str, *, role: str) -> InputRef:
    return InputRef(artifact_id=ArtifactID.model_validate(artifact_id), role=role)


def persist_doc_meta(store: FileSystemCAS, meta: DocMeta) -> ArtifactRef:
    """Persist doc meta helper."""
    inputs = [_to_input_ref(meta.raw_ref, role="raw_ref")]
    if meta.normalized_ref is not None:
        inputs.append(_to_input_ref(meta.normalized_ref, role="normalized_ref"))
    if meta.structure_ref is not None:
        inputs.append(_to_input_ref(meta.structure_ref, role="structure_ref"))
    if meta.chunks_ref is not None:
        inputs.append(_to_input_ref(meta.chunks_ref, role="chunks_ref"))
    return store.put_json(
        meta.model_dump(),
        opts=PutOptions(
            kind=_DOC_META_KIND,
            media_type="application/json",
            schema=_DOC_META_SCHEMA,
            inputs=inputs,
        ),
    )


def persist_doc_fragment(store: FileSystemCAS, fragment: DocFragment) -> ArtifactRef:
    """Persist doc fragment helper."""
    inputs = [_to_input_ref(fragment.text_hash, role="text_hash")]
    return store.put_json(
        fragment.model_dump(),
        opts=PutOptions(
            kind=_DOC_FRAGMENT_KIND,
            media_type="application/json",
            schema=_DOC_FRAGMENT_SCHEMA,
            inputs=inputs,
        ),
    )


def persist_claim(store: FileSystemCAS, claim: Claim) -> ArtifactRef:
    """Persist claim helper."""
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
        opts=PutOptions(
            kind=_CLAIM_KIND,
            media_type="application/json",
            schema=_CLAIM_SCHEMA,
            inputs=inputs or None,
        ),
    )


def persist_conflict_set(store: FileSystemCAS, conflict_set: ConflictSet) -> ArtifactRef:
    """Persist conflict set helper."""
    return store.put_json(
        conflict_set.model_dump(),
        opts=PutOptions(
            kind=_CONFLICT_SET_KIND,
            media_type="application/json",
            schema=_CONFLICT_SET_SCHEMA,
        ),
    )


def persist_trust_assessment(
    store: FileSystemCAS, assessment: TrustAssessment
) -> ArtifactRef:
    """Persist trust assessment helper."""
    return store.put_json(
        assessment.model_dump(),
        opts=PutOptions(
            kind=_TRUST_ASSESSMENT_KIND,
            media_type="application/json",
            schema=_TRUST_ASSESSMENT_SCHEMA,
        ),
    )


def persist_quality_report(store: FileSystemCAS, report: QualityReport) -> ArtifactRef:
    """Persist quality report helper."""
    return store.put_json(
        report.model_dump(),
        opts=PutOptions(
            kind=_QUALITY_REPORT_KIND,
            media_type="application/json",
            schema=_QUALITY_REPORT_SCHEMA,
        ),
    )


def persist_world_event(store: FileSystemCAS, event: WorldEvent) -> ArtifactRef:
    """Persist world event helper."""
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
        opts=PutOptions(
            kind=_WORLD_EVENT_KIND,
            media_type="application/json",
            schema=_WORLD_EVENT_SCHEMA,
            inputs=inputs or None,
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
