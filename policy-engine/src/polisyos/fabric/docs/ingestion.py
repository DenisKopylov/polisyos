"""Public docs ingestion module API."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.fabric.world import (
    append_world_segment_index,
    emit_doc_meta_facts,
    emit_world_event_facts,
    event_world_provenance_v1,
    persist_doc_meta,
    persist_world_event,
    stable_world_provenance_v1,
    validate_doc_meta_ids,
    write_world_fact_segment,
)
from polisyos.ir.world.doc import DocMeta
from polisyos.ir.world.event import (
    EventKind,
    ProvActivity,
    ProvActivityType,
    ProvAgent,
    ProvAgentType,
    WorldEvent,
    WorldObjectRef,
)
from polisyos.ir.world.ids import (
    doc_source_id,
    doc_version_id_from_raw_artifact,
    world_event_id_from_payload,
)

from .errors import DocValidationError
from .types import DocIngestOptions, DocIngestResult, DocSourceSpec

_RAW_SCHEMA = SchemaInfo(name="fabric.doc.raw", version="1.0")


def _coerce_retrieved_at(value: datetime | None) -> datetime:
    if value is None:
        value = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def _build_props(source: DocSourceSpec) -> dict[str, str]:
    props: dict[str, str] = {}
    if source.source_type:
        props["source_type"] = source.source_type
    if source.title:
        props["title"] = source.title
    if source.publisher:
        props["publisher"] = source.publisher
    if source.source_locator:
        props["source_locator"] = source.source_locator
    return props


def ingest_doc_bytes(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    source: DocSourceSpec,
    raw_bytes: bytes,
    mime: str,
    options: DocIngestOptions | None = None,
    segment_name: str | None = None,
) -> DocIngestResult:
    """Ingest doc bytes helper."""
    opts = options or DocIngestOptions()

    if opts.enforce_max_bytes is not None and len(raw_bytes) > opts.enforce_max_bytes:
        raise DocValidationError(
            f"raw_bytes length {len(raw_bytes)} exceeds limit {opts.enforce_max_bytes}"
        )

    raw_ref = cas.put_bytes(
        raw_bytes,
        opts=PutOptions(kind=opts.raw_kind, media_type=mime, schema=_RAW_SCHEMA),
    )
    raw_artifact_id = str(raw_ref.artifact_id)

    if source.canonical_url:
        canonical_url = source.canonical_url
        official_id = None
    elif source.official_id:
        canonical_url = None
        official_id = source.official_id
    else:
        canonical_url = None
        official_id = source.source_locator

    doc_source = doc_source_id(canonical_url=canonical_url, official_id=official_id)
    doc_version = doc_version_id_from_raw_artifact(raw_artifact_id=raw_artifact_id)

    meta = DocMeta(
        doc_source_id=doc_source,
        doc_version_id=doc_version,
        canonical_url=canonical_url,
        official_id=official_id,
        retrieved_at=_coerce_retrieved_at(source.retrieved_at),
        mime=mime,
        license=source.license or "",
        jurisdiction=source.jurisdiction,
        language=source.language,
        raw_ref=raw_artifact_id,
        normalized_ref=None,
        structure_ref=None,
        chunks_ref=None,
        props=_build_props(source),
    )
    validate_doc_meta_ids(meta)

    meta_ref = persist_doc_meta(cas, meta)
    meta_artifact_id = str(meta_ref.artifact_id)

    now = datetime.now(timezone.utc)
    agent = ProvAgent(
        agent_id=opts.agent_id,
        agent_type=ProvAgentType.SYSTEM,
        label="Fabric Docs",
    )
    activity = ProvActivity(
        activity_id=opts.activity_id,
        activity_type=ProvActivityType.FETCH_DOC,
        label="Ingest doc bytes",
        started_at=now,
        ended_at=now,
    )
    outputs = [
        WorldObjectRef(artifact_id=raw_artifact_id),
        WorldObjectRef(artifact_id=meta_artifact_id),
        WorldObjectRef(world_id=doc_source),
        WorldObjectRef(world_id=doc_version),
    ]
    payload = {
        "event_kind": EventKind.FETCH_DOC,
        "agent": agent,
        "activity": activity,
        "inputs": [],
        "outputs": outputs,
        "evidence_ref": None,
        "provenance_ref": None,
    }
    event_id = world_event_id_from_payload(event_payload=payload)
    event = WorldEvent(
        event_id=event_id,
        event_kind=EventKind.FETCH_DOC,
        agent=agent,
        activity=activity,
        inputs=[],
        outputs=outputs,
        evidence_ref=None,
        provenance_ref=None,
        props={},
    )
    event_ref = persist_world_event(cas, event)
    event_artifact_id = str(event_ref.artifact_id)

    stable_prov = stable_world_provenance_v1()
    event_prov = event_world_provenance_v1(event_id)
    facts = []
    facts.extend(
        emit_doc_meta_facts(
            meta,
            meta_artifact_id=meta_artifact_id,
            provenance=stable_prov,
        )
    )
    facts.extend(
        emit_world_event_facts(
            event,
            event_artifact_id=event_artifact_id,
            provenance=event_prov,
        )
    )

    manifest = write_world_fact_segment(
        facts,
        fact_log_root=fact_log_root,
        segment_name=segment_name or "doc_ingest",
    )
    append_world_segment_index(manifest, fact_log_root=fact_log_root)

    return DocIngestResult(
        doc_source_id=doc_source,
        doc_version_id=doc_version,
        raw_ref=raw_artifact_id,
        normalized_ref=None,
        structure_ref=None,
        chunks_ref=None,
        doc_meta_artifact_id=meta_artifact_id,
        world_event_id=event_id,
        world_event_artifact_id=event_artifact_id,
        world_segment_manifest=manifest,
    )


__all__ = ["ingest_doc_bytes"]
