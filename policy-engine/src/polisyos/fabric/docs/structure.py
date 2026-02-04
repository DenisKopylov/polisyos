from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.fabric.world.store import (
    append_world_segment_index,
    emit_doc_fragment_facts,
    emit_doc_meta_facts,
    emit_world_event_facts,
    event_world_provenance_v1,
    persist_doc_fragment,
    persist_doc_meta,
    persist_world_event,
    stable_world_provenance_v1,
    write_world_fact_segment,
)
from polisyos.fabric.world.store.validate import validate_doc_meta_ids
from polisyos.ir.citations import AnchorKind, FragmentLocator
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
from .types import DocStructureOptions, DocStructureResult

_STRUCTURE_SCHEMA = SchemaInfo(name="fabric.doc.structure", version="1.0")

_HEADING_NUMBERED_RE = re.compile(r"^\s*\d+(?:\.\d+)*[)\.]\s+\S")
_HEADING_HASH_RE = re.compile(r"^(#+)\s+(.*\S)")


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


def _iter_lines_with_offsets(text: str):
    offset = 0
    for line in text.splitlines(keepends=True):
        start = offset
        end = offset + len(line)
        yield line, start, end
        offset = end


def _uppercase_ratio(line: str) -> float:
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return 0.0
    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters)


def _detect_heading(line: str, *, max_len: int) -> tuple[str | None, str | None]:
    if len(line) > max_len:
        return None, None
    hash_match = _HEADING_HASH_RE.match(line)
    if hash_match:
        title = hash_match.group(2).strip()
        return "heading", title or None
    if _HEADING_NUMBERED_RE.match(line):
        return "heading", line.strip() or None
    stripped = line.strip()
    if not stripped:
        return None, None
    if _uppercase_ratio(stripped) >= 0.6:
        return "heading", stripped
    return None, None


def _preview(text: str, limit: int = 240) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    return cleaned[:limit]


def _build_anchors(text: str, *, options: DocStructureOptions) -> list[dict]:
    anchors: list[dict] = []
    text_len = len(text)
    if options.include_full_document_anchor and text_len:
        anchors.append(
            {
                "anchor_kind": "section",
                "anchor_path": None,
                "offset_start": 0,
                "offset_end": text_len,
                "title_hint": None,
                "_full_doc": True,
            }
        )

    for line, start, _end in _iter_lines_with_offsets(text):
        line_no_nl = line.rstrip("\n")
        if not line_no_nl.strip():
            continue
        anchor_kind, title = _detect_heading(
            line_no_nl,
            max_len=options.max_heading_len,
        )
        if anchor_kind is None:
            continue
        anchors.append(
            {
                "anchor_kind": anchor_kind,
                "anchor_path": None,
                "offset_start": start,
                "offset_end": start + len(line_no_nl),
                "title_hint": title,
                "_full_doc": False,
            }
        )

    filtered: list[dict] = []
    for anchor in anchors:
        if anchor["anchor_kind"] == "section" and not anchor.get("_full_doc"):
            if anchor["offset_end"] - anchor["offset_start"] < options.min_section_chars:
                continue
        filtered.append(anchor)
    return filtered


def structure_doc(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    doc_meta_artifact_id: str,
    options: DocStructureOptions | None = None,
    segment_name: str | None = None,
) -> DocStructureResult:
    opts = options or DocStructureOptions()

    meta = _load_doc_meta(cas, doc_meta_artifact_id)
    if meta.normalized_ref is None:
        raise DocNotReadyError("DocMeta.normalized_ref is required for structure")

    normalized_payload = _load_json_artifact(cas, meta.normalized_ref)
    normalized_text = normalized_payload.get("text")
    if not isinstance(normalized_text, str):
        raise DocValidationError("normalized artifact missing text")
    anchors = _build_anchors(normalized_text, options=opts)

    payload = {
        "schema_version": "1.0",
        "algorithm": opts.algorithm,
        "range_semantics": "python_slice",
        "doc_version_id": meta.doc_version_id,
        "normalized_ref": meta.normalized_ref,
        "options": asdict(opts),
        "anchors": [
            {
                k: v
                for k, v in anchor.items()
                if k in {
                    "anchor_kind",
                    "anchor_path",
                    "offset_start",
                    "offset_end",
                    "title_hint",
                }
            }
            for anchor in anchors
        ],
    }

    inputs = [
        InputRef(
            artifact_id=ArtifactID.model_validate(meta.normalized_ref),
            role="normalized_ref",
        )
    ]
    structure_ref = cas.put_json(
        payload,
        opts=PutOptions(
            kind=opts.structure_kind,
            media_type="application/json",
            schema=_STRUCTURE_SCHEMA,
            inputs=inputs,
        ),
    )
    structure_artifact_id = str(structure_ref.artifact_id)

    fragment_ids: list[str] = []
    fragment_facts: list = []
    stable_prov = stable_world_provenance_v1()

    for anchor in anchors:
        locator = FragmentLocator(
            anchor_kind=AnchorKind.HEADING
            if anchor["anchor_kind"] == "heading"
            else AnchorKind.SECTION,
            anchor_path=anchor.get("anchor_path"),
            offset_start=anchor.get("offset_start"),
            offset_end=anchor.get("offset_end"),
        )
        fragment_text = normalized_text[locator.offset_start : locator.offset_end]
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
            quote_preview=_preview(fragment_text),
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

    meta2 = meta.model_copy(update={"structure_ref": structure_artifact_id})
    meta_ref = persist_doc_meta(cas, meta2)
    meta_artifact_id = str(meta_ref.artifact_id)

    now = datetime.now(timezone.utc)
    agent = ProvAgent(
        agent_id="prov.agent.fabric_docs",
        agent_type=ProvAgentType.SYSTEM,
        label="Fabric Docs",
    )
    activity = ProvActivity(
        activity_id="prov.activity.fabric_docs.structure",
        activity_type=ProvActivityType.STRUCTURE_DOC,
        label="Structure doc",
        started_at=now,
        ended_at=now,
    )
    inputs_refs = [
        WorldObjectRef(world_id=meta.doc_version_id),
        WorldObjectRef(artifact_id=meta.normalized_ref),
    ]
    outputs = [
        WorldObjectRef(artifact_id=structure_artifact_id),
        WorldObjectRef(artifact_id=meta_artifact_id),
    ] + [WorldObjectRef(world_id=frag_id) for frag_id in fragment_ids]

    event_payload = {
        "event_kind": EventKind.STRUCTURE_DOC,
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
        event_kind=EventKind.STRUCTURE_DOC,
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
        segment_name=segment_name or "doc_structure",
    )
    append_world_segment_index(manifest, fact_log_root=fact_log_root)

    assert meta2.normalized_ref is not None
    return DocStructureResult(
        doc_source_id=meta2.doc_source_id,
        doc_version_id=meta2.doc_version_id,
        raw_ref=meta2.raw_ref,
        normalized_ref=meta2.normalized_ref,
        structure_ref=structure_artifact_id,
        chunks_ref=meta2.chunks_ref,
        doc_meta_artifact_id=meta_artifact_id,
        world_event_id=event_id,
        world_event_artifact_id=event_artifact_id,
        world_segment_manifest=manifest,
        fragment_ids=fragment_ids,
    )


__all__ = ["structure_doc"]
