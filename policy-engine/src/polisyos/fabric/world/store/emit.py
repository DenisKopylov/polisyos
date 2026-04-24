"""Translate world-domain records into fact-log rows that satisfy the world ABI."""

from __future__ import annotations

from enum import Enum

from polisyos.fabric.fact_writer import build_fact
from polisyos.ir.fact_log import Fact, FactLegal, FactProvenance
from polisyos.ir.world.abi import EdgeKind, NodeKind
from polisyos.ir.world.claim import Claim, ClaimSourceKind
from polisyos.ir.world.doc import DocFragment, DocMeta
from polisyos.ir.world.event import WorldEvent, WorldObjectRef
from polisyos.ir.world.ids import (
    artifact_id_to_world_id,
    doc_fragment_id,
    doc_version_id_from_raw_artifact,
)
from polisyos.ir.world.predicates import (
    WORLD_ARTIFACT_ID,
    WORLD_KIND,
    WORLD_LABEL,
    WORLD_PROPS_REF,
    rel,
)

from .errors import WorldFactError, WorldValidationError

_MAX_CLAIM_LABEL_LEN = 120


def _enum_value(value: EdgeKind | NodeKind | str) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def emit_attr_fact(
    *,
    subject_id: str,
    predicate_id: str,
    object_value: str | int | bool | None,
    provenance: FactProvenance,
    trust_policy_id: str | None = None,
    legal: FactLegal | None = None,
    valid_time: str | int | None = None,
) -> Fact:
    """Build one attribute fact for a world node before the segment is written."""
    if object_value is None:
        raise WorldFactError("attribute facts require object_value")
    return build_fact(
        subject_id=subject_id,
        predicate_id=predicate_id,
        object_value=object_value,
        target_id=None,
        valid_time=valid_time,
        provenance=provenance,
        trust_policy_id=trust_policy_id,
        legal=legal,
    )


def emit_edge_fact(
    *,
    src_id: str,
    edge_kind: EdgeKind | str,
    dst_id: str,
    provenance: FactProvenance,
    trust_policy_id: str | None = None,
    legal: FactLegal | None = None,
    valid_time: str | int | None = None,
) -> Fact:
    """Build one relationship fact linking two world objects in the fact log."""
    if not dst_id:
        raise WorldFactError("edge facts require dst_id")
    predicate_id = rel(edge_kind)
    return build_fact(
        subject_id=src_id,
        predicate_id=predicate_id,
        object_value=None,
        target_id=dst_id,
        valid_time=valid_time,
        provenance=provenance,
        trust_policy_id=trust_policy_id,
        legal=legal,
    )


def emit_world_node_facts(
    *,
    node_id: str,
    kind: NodeKind | str,
    label: str | None,
    artifact_id: str | None,
    props_ref: str | None,
    provenance: FactProvenance,
    trust_policy_id: str | None = None,
    legal: FactLegal | None = None,
) -> list[Fact]:
    """Emit the canonical attribute facts that define a world node envelope."""
    facts: list[Fact] = [
        emit_attr_fact(
            subject_id=node_id,
            predicate_id=WORLD_KIND,
            object_value=_enum_value(kind),
            provenance=provenance,
            trust_policy_id=trust_policy_id,
            legal=legal,
        )
    ]
    if label is not None:
        facts.append(
            emit_attr_fact(
                subject_id=node_id,
                predicate_id=WORLD_LABEL,
                object_value=label,
                provenance=provenance,
                trust_policy_id=trust_policy_id,
                legal=legal,
            )
        )
    if artifact_id is not None:
        facts.append(
            emit_attr_fact(
                subject_id=node_id,
                predicate_id=WORLD_ARTIFACT_ID,
                object_value=artifact_id,
                provenance=provenance,
                trust_policy_id=trust_policy_id,
                legal=legal,
            )
        )
    if props_ref is not None:
        facts.append(
            emit_attr_fact(
                subject_id=node_id,
                predicate_id=WORLD_PROPS_REF,
                object_value=props_ref,
                provenance=provenance,
                trust_policy_id=trust_policy_id,
                legal=legal,
            )
        )
    return facts


def emit_doc_meta_facts(
    meta: DocMeta,
    *,
    meta_artifact_id: str | None,
    provenance: FactProvenance,
    trust_policy_id: str | None = None,
    legal: FactLegal | None = None,
) -> list[Fact]:
    """Map document-source and document-version metadata into world facts."""
    label = meta.canonical_url if meta.canonical_url is not None else meta.official_id
    facts: list[Fact] = []
    facts.extend(
        emit_world_node_facts(
            node_id=meta.doc_source_id,
            kind=NodeKind.DOC_SOURCE,
            label=label,
            artifact_id=None,
            props_ref=None,
            provenance=provenance,
            trust_policy_id=trust_policy_id,
            legal=legal,
        )
    )
    facts.extend(
        emit_world_node_facts(
            node_id=meta.doc_version_id,
            kind=NodeKind.DOC_VERSION,
            label=None,
            artifact_id=meta_artifact_id,
            props_ref=None,
            provenance=provenance,
            trust_policy_id=trust_policy_id,
            legal=legal,
        )
    )
    facts.append(
        emit_edge_fact(
            src_id=meta.doc_source_id,
            edge_kind=EdgeKind.DOC_HAS_VERSION,
            dst_id=meta.doc_version_id,
            provenance=provenance,
            trust_policy_id=trust_policy_id,
            legal=legal,
        )
    )
    return facts


def emit_doc_fragment_facts(
    fragment: DocFragment,
    *,
    fragment_artifact_id: str | None,
    provenance: FactProvenance,
    trust_policy_id: str | None = None,
    legal: FactLegal | None = None,
) -> list[Fact]:
    """Map one structured document fragment into world facts and version links."""
    facts: list[Fact] = []
    facts.extend(
        emit_world_node_facts(
            node_id=fragment.fragment_id,
            kind=NodeKind.DOC_FRAGMENT,
            label=None,
            artifact_id=fragment_artifact_id,
            props_ref=None,
            provenance=provenance,
            trust_policy_id=trust_policy_id,
            legal=legal,
        )
    )
    facts.append(
        emit_edge_fact(
            src_id=fragment.doc_version_id,
            edge_kind=EdgeKind.DOC_HAS_FRAGMENT,
            dst_id=fragment.fragment_id,
            provenance=provenance,
            trust_policy_id=trust_policy_id,
            legal=legal,
        )
    )
    return facts


def _claim_label(claim: Claim) -> str:
    base = f"{claim.predicate_id}={claim.value_text}"
    if len(base) <= _MAX_CLAIM_LABEL_LEN:
        return base
    return base[: _MAX_CLAIM_LABEL_LEN - 3] + "..."


def _resolve_doc_version_id(citation) -> str | None:
    if citation.doc.doc_version_id is not None:
        return citation.doc.doc_version_id
    if citation.doc.doc_version_ref is not None:
        return doc_version_id_from_raw_artifact(raw_artifact_id=citation.doc.doc_version_ref)
    return None


def emit_claim_facts(
    claim: Claim,
    *,
    claim_artifact_id: str | None,
    provenance: FactProvenance,
    trust_policy_id: str | None = None,
    legal: FactLegal | None = None,
) -> list[Fact]:
    """Map a normalized claim plus its citations into world nodes and provenance edges."""
    facts: list[Fact] = []
    facts.extend(
        emit_world_node_facts(
            node_id=claim.claim_id,
            kind=NodeKind.CLAIM,
            label=_claim_label(claim),
            artifact_id=claim_artifact_id,
            props_ref=None,
            provenance=provenance,
            trust_policy_id=trust_policy_id,
            legal=legal,
        )
    )

    if claim.source_kind == ClaimSourceKind.DOC:
        for citation in claim.citations:
            if citation.fragment_id is not None:
                fragment_id = citation.fragment_id
            else:
                if citation.locator is None:
                    raise WorldValidationError("citation locator required for fragment derivation")
                if citation.text_hash is None:
                    raise WorldValidationError(
                        "citation text_hash required for fragment derivation"
                    )
                doc_version_id = _resolve_doc_version_id(citation)
                if doc_version_id is None:
                    raise WorldValidationError(
                        "citation requires doc_version_id or doc_version_ref"
                    )
                fragment_id = doc_fragment_id(
                    doc_version_id=doc_version_id,
                    locator=citation.locator,
                    text_artifact_id=citation.text_hash,
                )
            facts.append(
                emit_edge_fact(
                    src_id=claim.claim_id,
                    edge_kind=EdgeKind.CLAIM_CITES,
                    dst_id=fragment_id,
                    provenance=provenance,
                    trust_policy_id=trust_policy_id,
                    legal=legal,
                )
            )

        doc_version_ids = {
            citation.doc.doc_version_id
            for citation in claim.citations
            if citation.doc.doc_version_id is not None
        }
        if not doc_version_ids:
            doc_version_ids = {
                doc_version_id_from_raw_artifact(raw_artifact_id=citation.doc.doc_version_ref)
                for citation in claim.citations
                if citation.doc.doc_version_ref is not None
            }
        for doc_version_id in sorted(doc_version_ids):
            facts.append(
                emit_edge_fact(
                    src_id=claim.claim_id,
                    edge_kind=EdgeKind.CLAIM_DERIVED_FROM,
                    dst_id=doc_version_id,
                    provenance=provenance,
                    trust_policy_id=trust_policy_id,
                    legal=legal,
                )
            )
    else:
        for artifact_id in claim.source_artifacts:
            artifact_world_id = artifact_id_to_world_id(prefix="artifact", artifact_id=artifact_id)
            facts.append(
                emit_edge_fact(
                    src_id=claim.claim_id,
                    edge_kind=EdgeKind.CLAIM_DERIVED_FROM,
                    dst_id=artifact_world_id,
                    provenance=provenance,
                    trust_policy_id=trust_policy_id,
                    legal=legal,
                )
            )

    return facts


def _emit_artifact_node_facts(
    *,
    artifact_id: str,
    provenance: FactProvenance,
    trust_policy_id: str | None,
    legal: FactLegal | None,
) -> tuple[str, list[Fact]]:
    artifact_world_id = artifact_id_to_world_id(prefix="artifact", artifact_id=artifact_id)
    facts = emit_world_node_facts(
        node_id=artifact_world_id,
        kind=NodeKind.ARTIFACT,
        label=None,
        artifact_id=artifact_id,
        props_ref=None,
        provenance=provenance,
        trust_policy_id=trust_policy_id,
        legal=legal,
    )
    return artifact_world_id, facts


def _resolve_world_ref(
    ref: WorldObjectRef,
    *,
    provenance: FactProvenance,
    trust_policy_id: str | None,
    legal: FactLegal | None,
    emitted_artifacts: set[str],
) -> tuple[str, list[Fact]]:
    if ref.world_id is not None:
        return ref.world_id, []
    if ref.artifact_id is None:
        raise WorldValidationError("WorldObjectRef requires world_id or artifact_id")
    if ref.artifact_id in emitted_artifacts:
        artifact_world_id = artifact_id_to_world_id(prefix="artifact", artifact_id=ref.artifact_id)
        return artifact_world_id, []
    emitted_artifacts.add(ref.artifact_id)
    return _emit_artifact_node_facts(
        artifact_id=ref.artifact_id,
        provenance=provenance,
        trust_policy_id=trust_policy_id,
        legal=legal,
    )


def emit_world_event_facts(
    event: WorldEvent,
    *,
    event_artifact_id: str | None,
    provenance: FactProvenance,
    trust_policy_id: str | None = None,
    legal: FactLegal | None = None,
) -> list[Fact]:
    """Emit provenance facts for a workflow event that consumed or produced world objects."""
    facts: list[Fact] = []
    facts.extend(
        emit_world_node_facts(
            node_id=event.event_id,
            kind=NodeKind.WORLD_EVENT,
            label=event.event_kind.value,
            artifact_id=event_artifact_id,
            props_ref=None,
            provenance=provenance,
            trust_policy_id=trust_policy_id,
            legal=legal,
        )
    )
    facts.extend(
        emit_world_node_facts(
            node_id=event.agent.agent_id,
            kind=NodeKind.PROV_AGENT,
            label=event.agent.label,
            artifact_id=None,
            props_ref=None,
            provenance=provenance,
            trust_policy_id=trust_policy_id,
            legal=legal,
        )
    )
    if event.activity is not None:
        facts.extend(
            emit_world_node_facts(
                node_id=event.activity.activity_id,
                kind=NodeKind.PROV_ACTIVITY,
                label=event.activity.label,
                artifact_id=None,
                props_ref=None,
                provenance=provenance,
                trust_policy_id=trust_policy_id,
                legal=legal,
            )
        )
        facts.append(
            emit_edge_fact(
                src_id=event.event_id,
                edge_kind=EdgeKind.PROV_WAS_GENERATED_BY,
                dst_id=event.activity.activity_id,
                provenance=provenance,
                trust_policy_id=trust_policy_id,
                legal=legal,
            )
        )

    facts.append(
        emit_edge_fact(
            src_id=event.event_id,
            edge_kind=EdgeKind.PROV_WAS_ASSOCIATED_WITH,
            dst_id=event.agent.agent_id,
            provenance=provenance,
            trust_policy_id=trust_policy_id,
            legal=legal,
        )
    )

    emitted_artifacts: set[str] = set()

    for ref in event.inputs:
        entity_id, extra_facts = _resolve_world_ref(
            ref,
            provenance=provenance,
            trust_policy_id=trust_policy_id,
            legal=legal,
            emitted_artifacts=emitted_artifacts,
        )
        facts.extend(extra_facts)
        facts.append(
            emit_edge_fact(
                src_id=event.event_id,
                edge_kind=EdgeKind.PROV_USED,
                dst_id=entity_id,
                provenance=provenance,
                trust_policy_id=trust_policy_id,
                legal=legal,
            )
        )

    for ref in event.outputs:
        entity_id, extra_facts = _resolve_world_ref(
            ref,
            provenance=provenance,
            trust_policy_id=trust_policy_id,
            legal=legal,
            emitted_artifacts=emitted_artifacts,
        )
        facts.extend(extra_facts)
        facts.append(
            emit_edge_fact(
                src_id=entity_id,
                edge_kind=EdgeKind.PROV_WAS_GENERATED_BY,
                dst_id=event.event_id,
                provenance=provenance,
                trust_policy_id=trust_policy_id,
                legal=legal,
            )
        )
        facts.append(
            emit_edge_fact(
                src_id=entity_id,
                edge_kind=EdgeKind.PROV_WAS_ATTRIBUTED_TO,
                dst_id=event.agent.agent_id,
                provenance=provenance,
                trust_policy_id=trust_policy_id,
                legal=legal,
            )
        )

    return facts


__all__ = [
    "emit_attr_fact",
    "emit_claim_facts",
    "emit_doc_fragment_facts",
    "emit_doc_meta_facts",
    "emit_edge_fact",
    "emit_world_event_facts",
    "emit_world_node_facts",
]
