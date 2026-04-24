"""Builds and persists Scholar knowledge bundles plus their world-event side effects."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.contracts.scholar import (
    EnrichmentReportRef,
    FreshnessMetadata,
    KnowledgeBundleRef,
)
from polisyos.fabric.world import (
    append_world_segment_index,
    write_world_fact_segment,
)
from polisyos.fabric.world.events import (
    build_deterministic_world_event,
    persist_world_event_with_facts,
)
from polisyos.ir.world.event import (
    EventKind,
    ProvActivityType,
    ProvAgentType,
    WorldObjectRef,
)
from polisyos.ir.world.ids import stable_world_id_from_canon
from polisyos.scholar.types import EnrichmentReportV1, KnowledgeBundlePayloadV1

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts.protocol import ArtifactStore

_BUNDLE_SCHEMA = SchemaInfo(name="polisyos.scholar.KnowledgeBundlePayloadV1", version="1.0")
_REPORT_SCHEMA = SchemaInfo(name="polisyos.scholar.EnrichmentReportV1", version="1.0")


def compute_bundle_id(
    *,
    intent_core: dict[str, Any],
    doc_version_ids: list[str],
    claim_ids: list[str],
    policy_ids_used: dict[str, str],
) -> str:
    """Derive a deterministic bundle identifier from intent, documents, claims, and policies."""
    payload = {
        "intent_core": intent_core,
        "doc_version_ids": sorted(set(doc_version_ids)),
        "claim_ids": sorted(set(claim_ids)),
        "policy_ids_used": {key: policy_ids_used[key] for key in sorted(policy_ids_used)},
    }
    return cast("str", stable_world_id_from_canon(prefix="bundle", payload=payload))


def build_knowledge_bundle_payload(
    *,
    bundle_id: str,
    intent_payload: dict[str, Any],
    doc_meta_artifact_ids: list[str],
    doc_version_ids: list[str],
    doc_source_ids: list[str],
    claim_ids: list[str],
    claim_set_artifact_ids: list[str],
    conflict_set_ids: list[str],
    conflict_set_artifact_ids: list[str],
    conflict_resolution_artifact_ids: list[str],
    trust_assessment_ids: list[str],
    trust_assessment_artifact_ids_by_id: dict[str, str],
    quality_report_ids: list[str],
    quality_report_artifact_ids: list[str],
    web_evidence: dict[str, Any] | None,
    policy_ids_used: dict[str, str],
    created_by: dict[str, str],
    summary: dict[str, int | str | bool],
    freshness: FreshnessMetadata | None = None,
) -> KnowledgeBundlePayloadV1:
    """Build knowledge bundle payload."""
    sorted_trust_artifacts = {
        key: trust_assessment_artifact_ids_by_id[key]
        for key in sorted(trust_assessment_artifact_ids_by_id)
    }
    return KnowledgeBundlePayloadV1(
        bundle_id=bundle_id,
        intent=intent_payload,
        doc_meta_artifact_ids=sorted(set(doc_meta_artifact_ids)),
        doc_version_ids=sorted(set(doc_version_ids)),
        doc_source_ids=sorted(set(doc_source_ids)),
        claim_ids=sorted(set(claim_ids)),
        claim_set_artifact_ids=sorted(set(claim_set_artifact_ids)),
        conflict_set_ids=sorted(set(conflict_set_ids)),
        conflict_set_artifact_ids=sorted(set(conflict_set_artifact_ids)),
        conflict_resolution_artifact_ids=sorted(set(conflict_resolution_artifact_ids)),
        trust_assessment_ids=sorted(set(trust_assessment_ids)),
        trust_assessment_artifact_ids_by_id=sorted_trust_artifacts,
        quality_report_ids=sorted(set(quality_report_ids)),
        quality_report_artifact_ids=sorted(set(quality_report_artifact_ids)),
        web_evidence=web_evidence or {},
        policy_ids_used={key: policy_ids_used[key] for key in sorted(policy_ids_used)},
        created_by={key: created_by[key] for key in sorted(created_by)},
        summary={key: summary[key] for key in sorted(summary)},
        freshness=freshness or FreshnessMetadata(created_at=datetime(1970, 1, 1, tzinfo=UTC)),
    )


def _input_refs(artifact_ids: list[str]) -> list[InputRef]:
    refs: list[InputRef] = []
    for artifact_id in sorted(set(artifact_ids)):
        refs.append(InputRef(artifact_id=ArtifactID.model_validate(artifact_id), role="input"))
    return refs


def persist_bundle_and_event(
    *,
    cas: ArtifactStore,
    fact_log_root: Path,
    bundle_payload: KnowledgeBundlePayloadV1,
    report_payload: EnrichmentReportV1,
    doc_version_ids: list[str],
    claim_ids: list[str],
    conflict_set_ids: list[str],
    input_artifact_ids: list[str],
    segment_name: str | None = None,
    persist_report: bool = True,
) -> tuple[KnowledgeBundleRef, EnrichmentReportV1, EnrichmentReportRef | None]:
    """Write the knowledge bundle, optional report, and corresponding world event to storage."""
    bundle_ref = cas.put_json(
        bundle_payload.model_dump(mode="python"),
        opts=ArtifactWriteOptions(
            kind="scholar.knowledge_bundle",
            media_type="application/json",
            schema=_BUNDLE_SCHEMA,
            inputs=_input_refs(input_artifact_ids),
        ),
    )
    bundle_artifact_id = str(bundle_ref.artifact_id)

    report = report_payload.model_copy(update={"bundle_artifact_id": bundle_artifact_id})
    report_ref: EnrichmentReportRef | None = None
    if persist_report:
        report_artifact = cas.put_json(
            report.model_dump(mode="python"),
            opts=ArtifactWriteOptions(
                kind="scholar.enrichment_report",
                media_type="application/json",
                schema=_REPORT_SCHEMA,
                inputs=[
                    InputRef(
                        artifact_id=ArtifactID.model_validate(bundle_artifact_id),
                        role="knowledge_bundle",
                    )
                ],
            ),
        )
        report_ref = EnrichmentReportRef(artifact_id=report_artifact.artifact_id)

    inputs: list[WorldObjectRef] = [
        WorldObjectRef(world_id=world_id, artifact_id=None)
        for world_id in sorted(set(doc_version_ids))
    ]
    inputs.extend(
        WorldObjectRef(world_id=world_id, artifact_id=None) for world_id in sorted(set(claim_ids))
    )
    inputs.extend(
        WorldObjectRef(world_id=world_id, artifact_id=None)
        for world_id in sorted(set(conflict_set_ids))
    )
    inputs.extend(
        WorldObjectRef(world_id=None, artifact_id=artifact_id)
        for artifact_id in sorted(set(input_artifact_ids))
    )

    outputs: list[WorldObjectRef] = [
        WorldObjectRef(world_id=bundle_payload.bundle_id, artifact_id=None),
        WorldObjectRef(world_id=None, artifact_id=bundle_artifact_id),
    ]
    if report_ref is not None:
        outputs.append(WorldObjectRef(world_id=None, artifact_id=str(report_ref.artifact_id)))
    event = build_deterministic_world_event(
        event_kind=EventKind.KNOWLEDGE_BUNDLE_BUILD,
        agent_id="prov.agent.scholar",
        agent_type=ProvAgentType.SYSTEM,
        agent_label="Scholar",
        activity_id="prov.activity.scholar.knowledge_bundle_build",
        activity_type=ProvActivityType.KNOWLEDGE_BUNDLE_BUILD,
        activity_label="Build knowledge bundle",
        inputs=inputs,
        outputs=outputs,
        props={"bundle_id": bundle_payload.bundle_id},
    )
    facts: list[Any] = []
    persist_world_event_with_facts(cas=cas, event=event, facts=facts)
    manifest = write_world_fact_segment(
        facts,
        fact_log_root=fact_log_root,
        segment_name=segment_name or "scholar_bundle_build",
    )
    append_world_segment_index(manifest, fact_log_root=fact_log_root)

    return (
        KnowledgeBundleRef(artifact_id=bundle_ref.artifact_id),
        report,
        report_ref,
    )


__all__ = [
    "build_knowledge_bundle_payload",
    "compute_bundle_id",
    "persist_bundle_and_event",
]
