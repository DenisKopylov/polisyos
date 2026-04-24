"""Document normalization stage for Fabric claim and legal pipelines.

Normalization decodes raw bytes, chooses a MIME-specific text extractor, applies deterministic
newline/whitespace cleanup, persists a normalized text artifact, updates ``DocMeta.normalized_ref``,
and records a ``NORMALIZE_DOC`` world event.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.backends import BackendDispatcher, BackendNotAvailableError
from polisyos.core.canon import from_canonical_bytes
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
from polisyos.ir.world.ids import world_event_id_from_payload

from .backends.text_html import normalize_html_visible_text_v1
from .backends.text_plain import normalize_plain_text_v1
from .errors import DocUnsupportedMimeError, DocValidationError
from .types import DocNormalizeOptions, DocNormalizeResult

_NORMALIZED_SCHEMA = SchemaInfo(name="fabric.doc.normalized", version="1.0")
DocTextNormalizer = Callable[[str], str]


def _resolve_text_normalizer(mime: str) -> DocTextNormalizer:
    if mime == "text/html":
        return normalize_html_visible_text_v1
    if mime == "text/plain" or mime.startswith("text/"):
        return normalize_plain_text_v1
    raise BackendNotAvailableError(mime, reason="unsupported mime")


_TEXT_NORMALIZER_DISPATCHER = BackendDispatcher[str, DocTextNormalizer](
    factory=_resolve_text_normalizer
)


def _decode_bytes(raw_bytes: bytes, options: DocNormalizeOptions) -> str:
    for enc in options.encoding_order:
        try:
            return raw_bytes.decode(enc, errors=options.errors)
        except Exception:  # pragma: no cover - exercised via fallback
            pass
    # Deterministic fallback
    try:
        return raw_bytes.decode(options.encoding_order[0], errors="replace")
    except Exception as exc:  # pragma: no cover - defensive
        raise DocValidationError(f"failed to decode bytes: {exc}") from exc


def _normalize_text(text: str, options: DocNormalizeOptions) -> str:
    if options.normalize_newlines:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    if options.strip_trailing_whitespace:
        lines = text.split("\n")
        lines = [line.rstrip(" \t") for line in lines]
        text = "\n".join(lines)
    if options.collapse_blank_lines:
        lines = text.split("\n")
        collapsed: list[str] = []
        prev_blank = False
        for line in lines:
            blank = line.strip() == ""
            if blank:
                if prev_blank:
                    continue
                prev_blank = True
                collapsed.append("")
            else:
                prev_blank = False
                collapsed.append(line)
        text = "\n".join(collapsed)
    return text


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


def normalize_doc(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    doc_meta_artifact_id: str,
    options: DocNormalizeOptions | None = None,
    segment_name: str | None = None,
) -> DocNormalizeResult:
    """Convert a raw document artifact into normalized text and updated ``DocMeta`` metadata.

    Args:
        cas: Artifact store containing the input ``DocMeta`` and raw artifact.
        fact_log_root: Fact-log root for emitted ``DocMeta`` and world-event facts.
        doc_meta_artifact_id: Artifact id of the document metadata row produced by ingest.
        options: Optional decoding order, whitespace policy, and output kind settings.
        segment_name: Optional world segment name.

    Returns:
        Updated document metadata references and the normalized text artifact id.

    Raises:
        DocUnsupportedMimeError: If no text extractor exists for ``DocMeta.mime``.
        DocValidationError: If the raw artifact cannot be decoded or persisted payloads are invalid.
    """
    opts = options or DocNormalizeOptions()

    meta = _load_doc_meta(cas, doc_meta_artifact_id)
    raw_bytes = cas.get_bytes(ArtifactID.model_validate(meta.raw_ref))

    decoded = _decode_bytes(raw_bytes, opts)
    try:
        normalizer = _TEXT_NORMALIZER_DISPATCHER.resolve(meta.mime)
    except BackendNotAvailableError as exc:
        raise DocUnsupportedMimeError(f"unsupported mime type: {meta.mime}") from exc
    extracted = normalizer(decoded)

    normalized_text = _normalize_text(extracted, opts)
    stats = {
        "char_count": len(normalized_text),
        "line_count": normalized_text.count("\n") + (1 if normalized_text else 0),
    }
    payload = {
        "schema_version": "1.0",
        "algorithm": "normalize_v1",
        "input_mime": meta.mime,
        "text": normalized_text,
        "stats": stats,
        "options": asdict(opts),
    }

    inputs = [InputRef(artifact_id=ArtifactID.model_validate(meta.raw_ref), role="raw_ref")]
    normalized_ref = cas.put_json(
        payload,
        opts=PutOptions(
            kind=opts.normalized_kind,
            media_type="application/json",
            schema=_NORMALIZED_SCHEMA,
            inputs=inputs,
        ),
    )
    normalized_artifact_id = str(normalized_ref.artifact_id)

    meta2 = meta.model_copy(update={"normalized_ref": normalized_artifact_id})
    meta_ref = persist_doc_meta(cas, meta2)
    meta_artifact_id = str(meta_ref.artifact_id)

    now = datetime.now(UTC)
    agent = ProvAgent(
        agent_id="prov.agent.fabric_docs",
        agent_type=ProvAgentType.SYSTEM,
        label="Fabric Docs",
    )
    activity = ProvActivity(
        activity_id="prov.activity.fabric_docs.normalize",
        activity_type=ProvActivityType.NORMALIZE_DOC,
        label="Normalize doc",
        started_at=now,
        ended_at=now,
    )
    inputs_refs = [
        WorldObjectRef(world_id=meta.doc_version_id),
        WorldObjectRef(artifact_id=meta.raw_ref),
    ]
    outputs = [
        WorldObjectRef(artifact_id=normalized_artifact_id),
        WorldObjectRef(artifact_id=meta_artifact_id),
    ]
    event_payload = {
        "event_kind": EventKind.NORMALIZE_DOC,
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
        event_kind=EventKind.NORMALIZE_DOC,
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

    stable_prov = stable_world_provenance_v1()
    event_prov = event_world_provenance_v1(event_id)
    facts = []
    facts.extend(
        emit_doc_meta_facts(
            meta2,
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
        segment_name=segment_name or "doc_normalize",
    )
    append_world_segment_index(manifest, fact_log_root=fact_log_root)

    return DocNormalizeResult(
        doc_source_id=meta2.doc_source_id,
        doc_version_id=meta2.doc_version_id,
        raw_ref=meta2.raw_ref,
        normalized_ref=normalized_artifact_id,
        structure_ref=meta2.structure_ref,
        chunks_ref=meta2.chunks_ref,
        doc_meta_artifact_id=meta_artifact_id,
        world_event_id=event_id,
        world_event_artifact_id=event_artifact_id,
        world_segment_manifest=manifest,
    )


__all__ = ["normalize_doc"]
