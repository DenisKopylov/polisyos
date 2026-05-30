"""Document chunking stage for claim extraction and retrieval workloads.

The stage slices normalized text into deterministic ranges, persists chunk fragments, stores a
chunk manifest artifact, updates ``DocMeta.chunks_ref``, and emits a ``CHUNK_DOC`` world event.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.fabric.world import (
    append_world_segment_index,
    emit_doc_fragment_facts,
    emit_doc_meta_facts,
    emit_world_event_facts,
    event_world_provenance_v1,
    persist_doc_fragment,
    persist_doc_meta,
    persist_world_event,
    stable_world_provenance_v1,
    validate_doc_meta_ids,
    write_world_fact_segment,
)
from polisyos.ir.loading.citations import AnchorKind, FragmentLocator
from polisyos.ir.world.doc import DocFragment, DocMeta
from polisyos.ir.world.event import (
    EventKind,
    ProvActivity,
    ProvActivityType,
    ProvAgent,
    ProvAgentType,
    WorldEvent,
    WorldObjectRef,
)
from polisyos.ir.world.ids import doc_fragment_id, world_event_id_from_payload

from .errors import DocNotReadyError, DocValidationError
from .types import DocChunkOptions, DocChunkResult

_CHUNKS_SCHEMA = SchemaInfo(name="fabric.doc.chunks", version="1.0")


def _load_json_artifact(cas: FileSystemCAS, artifact_id: str) -> dict:
    try:
        aid = ArtifactID.model_validate(artifact_id)
        payload = from_canonical_bytes(cas.get_bytes(aid))
    except Exception as exc:  # pragma: no cover - defensive
        raise DocValidationError(f"failed to load artifact {artifact_id}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DocValidationError(f"artifact {artifact_id} payload must be a JSON object")
    return payload


def _load_doc_meta(cas: FileSystemCAS, artifact_id: str) -> DocMeta:
    payload = _load_json_artifact(cas, artifact_id)
    meta = DocMeta.model_validate(payload)
    validate_doc_meta_ids(meta)
    return meta


def _preview(text: str, limit: int = 120) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    return cleaned[:limit]


def _adjust_paragraph_end(text: str, start: int, end: int, min_chars: int) -> int:
    window_start = min(start + min_chars, end)
    if window_start >= end:
        return end
    idx = text.rfind("\n\n", window_start, end)
    if idx == -1:
        return end
    return idx + 2


def _chunk_ranges(text: str, options: DocChunkOptions) -> list[tuple[int, int]]:
    if options.overlap_chars <= 0 or options.overlap_chars >= options.chunk_size_chars:
        raise DocValidationError("overlap_chars must be between 0 and chunk_size_chars")
    step = options.chunk_size_chars - options.overlap_chars
    ranges: list[tuple[int, int]] = []
    length = len(text)
    for start in range(0, length, step):
        end = min(start + options.chunk_size_chars, length)
        if options.boundary == "paragraph":
            end = _adjust_paragraph_end(text, start, end, options.min_chunk_chars)
        if end - start < options.min_chunk_chars:
            break
        ranges.append((start, end))
        if end == length:
            break
    return ranges


def chunk_doc(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    doc_meta_artifact_id: str,
    options: DocChunkOptions | None = None,
    segment_name: str | None = None,
) -> DocChunkResult:
    """Generate deterministic text chunks for a normalized document.

    Raises:
        DocNotReadyError: If ``DocMeta.normalized_ref`` is missing.
        DocValidationError: If chunk overlap/boundary settings are invalid or the normalized
            artifact payload is malformed.
    """
    opts = options or DocChunkOptions()

    meta = _load_doc_meta(cas, doc_meta_artifact_id)
    if meta.normalized_ref is None:
        raise DocNotReadyError("DocMeta.normalized_ref is required for chunking")

    normalized_payload = _load_json_artifact(cas, meta.normalized_ref)
    normalized_text = normalized_payload.get("text")
    if not isinstance(normalized_text, str):
        raise DocValidationError("normalized artifact missing text")

    ranges = _chunk_ranges(normalized_text, opts)

    chunk_entries: list[dict] = []
    fragment_ids: list[str] = []
    fragment_facts: list = []
    stable_prov = stable_world_provenance_v1()

    for start, end in ranges:
        locator = FragmentLocator(
            anchor_kind=AnchorKind.CHUNK,
            anchor_path=None,
            offset_start=start,
            offset_end=end,
        )
        fragment_text = normalized_text[start:end]
        fragment_id = doc_fragment_id(
            doc_version_id=meta.doc_version_id,
            locator=locator,
            text_artifact_id=meta.normalized_ref,
        )
        fragment = DocFragment(
            fragment_id=fragment_id,
            doc_version_id=meta.doc_version_id,
            locator=locator,
            text_hash=meta.normalized_ref,
            quote_preview=_preview(fragment_text, limit=240),
            props={},
        )
        fragment_ref = persist_doc_fragment(cas, fragment)
        fragment_artifact_id = str(fragment_ref.artifact_id)
        fragment_ids.append(fragment_id)
        fragment_facts.extend(
            emit_doc_fragment_facts(
                fragment,
                fragment_artifact_id=fragment_artifact_id,
                provenance=stable_prov,
            )
        )
        chunk_entries.append(
            {
                "offset_start": start,
                "offset_end": end,
                "fragment_id": fragment_id,
                "text_len": end - start,
                "text_preview": _preview(fragment_text, limit=120),
            }
        )

    payload = {
        "schema_version": "1.0",
        "algorithm": opts.algorithm,
        "range_semantics": "python_slice",
        "doc_version_id": meta.doc_version_id,
        "normalized_ref": meta.normalized_ref,
        "options": asdict(opts),
        "chunks": chunk_entries,
    }

    inputs = [
        InputRef(
            artifact_id=ArtifactID.model_validate(meta.normalized_ref),
            role="normalized_ref",
        )
    ]
    chunks_ref = cas.put_json(
        payload,
        opts=PutOptions(
            kind=opts.chunks_kind,
            media_type="application/json",
            schema=_CHUNKS_SCHEMA,
            inputs=inputs,
        ),
    )
    chunks_artifact_id = str(chunks_ref.artifact_id)

    meta2 = meta.model_copy(update={"chunks_ref": chunks_artifact_id})
    meta_ref = persist_doc_meta(cas, meta2)
    meta_artifact_id = str(meta_ref.artifact_id)

    now = datetime.now(UTC)
    agent = ProvAgent(
        agent_id="prov.agent.fabric_docs",
        agent_type=ProvAgentType.SYSTEM,
        label="Fabric Docs",
    )
    activity = ProvActivity(
        activity_id="prov.activity.fabric_docs.chunk",
        activity_type=ProvActivityType.CHUNK_DOC,
        label="Chunk doc",
        started_at=now,
        ended_at=now,
    )
    inputs_refs = [
        WorldObjectRef(world_id=meta.doc_version_id),
        WorldObjectRef(artifact_id=meta.normalized_ref),
    ]
    outputs = [
        WorldObjectRef(artifact_id=chunks_artifact_id),
        WorldObjectRef(artifact_id=meta_artifact_id),
    ] + [WorldObjectRef(world_id=frag_id) for frag_id in fragment_ids]

    event_payload = {
        "event_kind": EventKind.CHUNK_DOC,
        "agent": agent,
        "activity": activity,
        "inputs": inputs_refs,
        "outputs": outputs,
        "evidence_ref": None,
        "provenance_ref": None,
    }
    event_id = world_event_id_from_payload(event_payload=event_payload)
    event = WorldEvent(
        event_id=event_id,
        event_kind=EventKind.CHUNK_DOC,
        agent=agent,
        activity=activity,
        inputs=inputs_refs,
        outputs=outputs,
        evidence_ref=None,
        provenance_ref=None,
        props={},
    )
    event_ref = persist_world_event(cas, event)
    event_artifact_id = str(event_ref.artifact_id)

    event_prov = event_world_provenance_v1(event_id)
    facts = []
    facts.extend(
        emit_doc_meta_facts(
            meta2,
            meta_artifact_id=meta_artifact_id,
            provenance=stable_prov,
        )
    )
    facts.extend(fragment_facts)
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
        segment_name=segment_name or "doc_chunk",
    )
    append_world_segment_index(manifest, fact_log_root=fact_log_root)

    if meta2.normalized_ref is None:
        raise DocValidationError("document chunking did not persist normalized text")
    return DocChunkResult(
        doc_source_id=meta2.doc_source_id,
        doc_version_id=meta2.doc_version_id,
        raw_ref=meta2.raw_ref,
        normalized_ref=meta2.normalized_ref,
        structure_ref=meta2.structure_ref,
        chunks_ref=chunks_artifact_id,
        doc_meta_artifact_id=meta_artifact_id,
        world_event_id=event_id,
        world_event_artifact_id=event_artifact_id,
        world_segment_manifest=manifest,
        chunk_fragment_ids=fragment_ids,
    )


__all__ = ["chunk_doc"]
