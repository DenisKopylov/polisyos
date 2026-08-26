"""Lex corpus ingest stage that wraps Fabric document ingestion with legal metadata semantics.

The stage stores raw bytes through ``fabric.docs.ingest_doc_bytes``, optionally chains normalize /
structure / chunk steps, then merges Lex-specific temporal and jurisdiction metadata into
``DocMeta.props['lex']`` and emits deterministic world facts for downstream version indexing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.legal.contracts import (
    LegalDocSource,
    LexIngestOptions,
    LexIngestResult,
    WorldEventRefLike,
)
from polisyos.data_forge.errors import LexError, LexIngestError, LexValidationError
from polisyos.data_forge.kernel.artifacts import load_doc_meta_artifact
from polisyos.fabric.docs import (
    DocSourceSpec,
    chunk_doc,
    ingest_doc_bytes,
    normalize_doc,
    structure_doc,
)
from polisyos.fabric.docs.errors import DocPipelineError, DocValidationError
from polisyos.fabric.world import (
    append_world_segment_index,
    emit_doc_meta_facts,
    persist_doc_meta,
    stable_world_provenance_v1,
    validate_doc_meta_ids,
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
from polisyos.ir.world.ids import doc_source_id

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts.store import FileSystemCAS

logger = get_logger(__name__)


def _to_doc_source_spec(source: LegalDocSource) -> DocSourceSpec:
    return DocSourceSpec(
        canonical_url=source.canonical_url,
        official_id=source.official_id,
        source_locator=None,
        license=source.license,
        retrieved_at=source.retrieved_at,
        jurisdiction=source.jurisdiction,
        language=source.language,
        source_type=source.source_type,
        title=source.title,
        publisher=source.publisher,
    )


def _merge_lex_props(
    *,
    source: LegalDocSource,
    current_props: dict[str, Any],
    policy: str,
) -> dict[str, Any]:
    merged = dict(current_props)

    existing_lex = merged.get("lex")
    current_lex = dict(existing_lex) if isinstance(existing_lex, dict) else {}

    lex_props = {} if policy == "overwrite_lex" else current_lex
    lex_props["schema_version"] = "1.0"
    lex_props["corpus"] = "lex.corpus"
    if source.source_url is not None:
        lex_props["source_url"] = source.source_url
    if source.published_at_iso is not None:
        lex_props["published_at"] = source.published_at_iso
    if source.effective_from_iso is not None:
        lex_props["effective_from"] = source.effective_from_iso
    if source.effective_to_iso is not None:
        lex_props["effective_to"] = source.effective_to_iso
    if source.jurisdiction is not None:
        lex_props["jurisdiction"] = source.jurisdiction
    if source.language is not None:
        lex_props["language"] = source.language
    lex_props["ingest"] = {"pipeline": "lex.corpus.ingest_v1"}

    merged["lex"] = lex_props
    return merged


def _safe_doc_source_id(source: LegalDocSource) -> str | None:
    try:
        return doc_source_id(
            canonical_url=source.canonical_url,
            official_id=source.official_id,
        )
    except Exception:
        logger.debug("Failed to compute doc_source_id for source %s", source.canonical_url)
        return None


def ingest_legal_doc_bytes(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    source: LegalDocSource,
    raw_bytes: bytes,
    mime: str,
    options: LexIngestOptions | None = None,
    segment_name: str | None = None,
) -> LexIngestResult:
    """Persist raw legal bytes and attach Lex provenance metadata.

    Args:
        cas: Artifact store for raw payloads, updated ``DocMeta``, and optional derived artifacts.
        fact_log_root: World fact-log root where document facts and validation events are appended.
        source: Legal source identity and temporal metadata; exactly one stable locator is required.
        raw_bytes: Original document payload to ingest.
        mime: MIME type used by Fabric normalization backends.
        options: Optional stage toggles and provenance/event settings.
        segment_name: Optional world segment name prefix.

    Returns:
        Document source/version ids, raw/normalized/structure/chunk artifact ids, updated
        ``DocMeta`` artifact id, emitted world events, and wrapped Fabric stage outputs.

    Raises:
        LexValidationError: If Fabric document contracts or Lex metadata invariants fail.
        LexIngestError: If persistence or world-event emission fails unexpectedly.
    """
    opts = options or LexIngestOptions()

    try:
        run_suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
        doc_source = _to_doc_source_spec(source)

        fabric_ingest = ingest_doc_bytes(
            cas=cas,
            fact_log_root=fact_log_root,
            source=doc_source,
            raw_bytes=raw_bytes,
            mime=mime,
            options=opts.docs_ingest,
            segment_name=f"{segment_name or 'lex_ingest_doc'}_{run_suffix}",
        )

        fabric_normalize = None
        fabric_structure = None
        fabric_chunk = None

        current_meta_artifact_id = fabric_ingest.doc_meta_artifact_id

        if opts.run_normalize:
            fabric_normalize = normalize_doc(
                cas=cas,
                fact_log_root=fact_log_root,
                doc_meta_artifact_id=current_meta_artifact_id,
                options=opts.docs_normalize,
                segment_name=f"{segment_name or 'lex_normalize_doc'}_{run_suffix}",
            )
            current_meta_artifact_id = fabric_normalize.doc_meta_artifact_id

        if opts.run_structure:
            fabric_structure = structure_doc(
                cas=cas,
                fact_log_root=fact_log_root,
                doc_meta_artifact_id=current_meta_artifact_id,
                options=opts.docs_structure,
                segment_name=f"{segment_name or 'lex_structure_doc'}_{run_suffix}",
            )
            current_meta_artifact_id = fabric_structure.doc_meta_artifact_id

        if opts.run_chunk:
            fabric_chunk = chunk_doc(
                cas=cas,
                fact_log_root=fact_log_root,
                doc_meta_artifact_id=current_meta_artifact_id,
                options=opts.docs_chunk,
                segment_name=f"{segment_name or 'lex_chunk_doc'}_{run_suffix}",
            )
            current_meta_artifact_id = fabric_chunk.doc_meta_artifact_id

        meta_before = load_doc_meta_artifact(
            cas,
            current_meta_artifact_id,
            validate_ids=True,
        )
        merged_props = _merge_lex_props(
            source=source,
            current_props=meta_before.props,
            policy=opts.doc_props_merge_policy,
        )

        meta_after = meta_before.model_copy(update={"props": merged_props})
        validate_doc_meta_ids(meta_after)

        meta_ref = persist_doc_meta(cas, meta_after)
        meta_artifact_id = str(meta_ref.artifact_id)

        stable_prov = stable_world_provenance_v1()
        facts = emit_doc_meta_facts(
            meta_after,
            meta_artifact_id=meta_artifact_id,
            provenance=stable_prov,
        )

        world_events: list[WorldEventRefLike] = [
            WorldEventRefLike(
                event_id=fabric_ingest.world_event_id,
                event_artifact_id=fabric_ingest.world_event_artifact_id,
                event_kind=EventKind.FETCH_DOC.value,
            )
        ]
        if fabric_normalize is not None:
            world_events.append(
                WorldEventRefLike(
                    event_id=fabric_normalize.world_event_id,
                    event_artifact_id=fabric_normalize.world_event_artifact_id,
                    event_kind=EventKind.NORMALIZE_DOC.value,
                )
            )
        if fabric_structure is not None:
            world_events.append(
                WorldEventRefLike(
                    event_id=fabric_structure.world_event_id,
                    event_artifact_id=fabric_structure.world_event_artifact_id,
                    event_kind=EventKind.STRUCTURE_DOC.value,
                )
            )
        if fabric_chunk is not None:
            world_events.append(
                WorldEventRefLike(
                    event_id=fabric_chunk.world_event_id,
                    event_artifact_id=fabric_chunk.world_event_artifact_id,
                    event_kind=EventKind.CHUNK_DOC.value,
                )
            )

        if opts.write_lex_meta_update_event:
            inputs = [
                WorldObjectRef(artifact_id=current_meta_artifact_id),
                WorldObjectRef(world_id=meta_after.doc_version_id),
            ]
            outputs = [WorldObjectRef(artifact_id=meta_artifact_id)]
            event = build_deterministic_world_event(
                event_kind=EventKind.VALIDATE,
                agent_id=opts.lex_agent_id,
                agent_type=ProvAgentType.SYSTEM,
                agent_label="Lex Corpus",
                activity_id=opts.lex_activity_id,
                activity_type=ProvActivityType.VALIDATE,
                activity_label="Lex ingest meta update",
                activity_parameters={
                    "pipeline": "lex.corpus.ingest_v1",
                    "doc_props_merge_policy": opts.doc_props_merge_policy,
                },
                inputs=inputs,
                outputs=outputs,
                props={"pipeline": "lex.corpus.ingest_v1"},
            )
            event_id = event.event_id
            event_artifact_id = persist_world_event_with_facts(cas=cas, event=event, facts=facts)
            world_events.append(
                WorldEventRefLike(
                    event_id=event_id,
                    event_artifact_id=event_artifact_id,
                    event_kind=EventKind.VALIDATE.value,
                )
            )

        manifest = write_world_fact_segment(
            facts,
            fact_log_root=fact_log_root,
            segment_name=f"{segment_name or 'lex_ingest'}_{run_suffix}",
        )
        append_world_segment_index(manifest, fact_log_root=fact_log_root)

        fabric_results: dict[str, Any] = {
            "ingest": fabric_ingest,
            "normalize": fabric_normalize,
            "structure": fabric_structure,
            "chunk": fabric_chunk,
        }

        return LexIngestResult(
            doc_source_id=meta_after.doc_source_id,
            doc_version_id=meta_after.doc_version_id,
            raw_ref=meta_after.raw_ref,
            normalized_ref=meta_after.normalized_ref,
            structure_ref=meta_after.structure_ref,
            chunks_ref=meta_after.chunks_ref,
            doc_meta_artifact_id=meta_artifact_id,
            world_events=world_events,
            world_segments=[manifest],
            fabric_results=fabric_results,
        )
    except LexError:
        raise
    except (DocValidationError, DocPipelineError) as exc:
        raise LexValidationError(
            f"failed to ingest legal document: {exc}",
            doc_source_id=_safe_doc_source_id(source),
            details={"mime": mime},
        ) from exc
    except Exception as exc:
        raise LexIngestError(
            f"failed to ingest legal document: {exc}",
            doc_source_id=_safe_doc_source_id(source),
            details={"mime": mime},
        ) from exc


__all__ = ["ingest_legal_doc_bytes"]
