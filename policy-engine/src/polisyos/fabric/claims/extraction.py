from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.world import (
    emit_claim_facts,
    emit_world_event_facts,
    event_world_provenance_v1,
    persist_claim,
    persist_world_event,
    stable_world_provenance_v1,
    validate_claim_id,
)
from polisyos.ir.kernel.base import ID_PATTERN, reject_floats_deep
from polisyos.ir.world.claim import Claim, ClaimSourceKind
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
from polisyos.ir.world.ids import claim_id_from_payload, world_event_id_from_payload

from .backends import resolve_extractor
from .canonicalize import canonical_unit, canonicalize_id
from .citations import minimal_doc_citation
from .errors import ClaimNotReadyError, ClaimValidationError
from .persist import (
    canonical_json_text,
    load_doc_meta,
    load_json_artifact,
    persist_claim_set,
    persist_claims_evidence_bundle,
    write_claims_world_segment,
)
from .types import (
    ChunkContext,
    ClaimCandidate,
    ClaimExtractOptions,
    ClaimExtractResult,
)

_ID_RE = re.compile(ID_PATTERN)


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _add_warning(
    warnings: list[tuple[str, str]],
    *,
    code: str,
    msg: str,
) -> None:
    warnings.append((code, msg))


def _sorted_warnings(warnings: list[tuple[str, str]]) -> list[dict[str, str]]:
    unique = sorted(set(warnings), key=lambda item: (item[0], item[1]))
    return [{"code": code, "msg": msg} for code, msg in unique]


def _build_chunk_contexts(
    *,
    normalized_text: str,
    chunks_payload: dict[str, Any],
) -> list[ChunkContext]:
    chunks = chunks_payload.get("chunks")
    if not isinstance(chunks, list):
        raise ClaimValidationError("chunks artifact missing chunks[]")

    contexts: list[ChunkContext] = []
    text_len = len(normalized_text)
    for idx, entry in enumerate(chunks):
        if not isinstance(entry, dict):
            raise ClaimValidationError(f"chunk[{idx}] must be an object")
        fragment_id = entry.get("fragment_id")
        if not isinstance(fragment_id, str):
            raise ClaimValidationError(f"chunk[{idx}].fragment_id must be string")
        if _ID_RE.fullmatch(fragment_id) is None:
            raise ClaimValidationError(f"chunk[{idx}].fragment_id must match {ID_PATTERN}")
        start = entry.get("offset_start")
        end = entry.get("offset_end")
        if not isinstance(start, int) or not isinstance(end, int):
            raise ClaimValidationError(f"chunk[{idx}] offsets must be int")
        if not (0 <= start <= end <= text_len):
            raise ClaimValidationError(
                f"chunk[{idx}] offsets out of range: start={start}, end={end}, text_len={text_len}"
            )
        chunk_text = normalized_text[start:end]
        contexts.append(
            ChunkContext(
                fragment_id=fragment_id,
                doc_version_id=str(chunks_payload.get("doc_version_id", "")),
                offset_start=start,
                offset_end=end,
                text_preview=_collapse_ws(chunk_text)[:240],
            )
        )
    return contexts


def _claim_tie_key(claim: Claim) -> tuple[str, str, str]:
    return (claim.predicate_id, claim.value_text, claim.unit_id or "")


def _candidate_to_claim(
    candidate: ClaimCandidate,
    *,
    doc_source_id: str,
    meta: DocMeta,
    warnings: list[tuple[str, str]],
) -> Claim | None:
    predicate_id = canonicalize_id(candidate.predicate_id)
    if predicate_id is None:
        _add_warning(
            warnings,
            code="invalid_predicate",
            msg=f"dropped candidate with invalid predicate: {candidate.predicate_id!r}",
        )
        return None

    subject_id = candidate.subject_id
    if subject_id is not None:
        subject_id = subject_id.strip()
        if subject_id and _ID_RE.fullmatch(subject_id) is None:
            subject_id = canonicalize_id(subject_id)
    if not subject_id:
        subject_id = doc_source_id

    subject_text = candidate.subject_text.strip() if candidate.subject_text else None
    value_text = candidate.value_text.strip()
    if not value_text:
        _add_warning(
            warnings,
            code="empty_value",
            msg=f"dropped candidate with empty value for predicate {predicate_id}",
        )
        return None

    value_decimal = candidate.value_decimal
    if value_decimal is not None and not isinstance(value_decimal, Decimal):
        _add_warning(
            warnings,
            code="invalid_value_decimal",
            msg=f"dropped candidate with non-decimal value for predicate {predicate_id}",
        )
        return None

    unit_id = canonical_unit(candidate.unit_id) if candidate.unit_id else None

    confidence = candidate.confidence if candidate.confidence is not None else Decimal("1")
    if not isinstance(confidence, Decimal):
        _add_warning(
            warnings,
            code="invalid_confidence",
            msg=f"dropped candidate with non-decimal confidence for predicate {predicate_id}",
        )
        return None

    if _ID_RE.fullmatch(candidate.citation_fragment_id) is None:
        _add_warning(
            warnings,
            code="invalid_citation_fragment",
            msg=f"dropped candidate with invalid fragment_id: {candidate.citation_fragment_id!r}",
        )
        return None

    qualifiers = dict(candidate.qualifiers)
    props = dict(candidate.props)
    try:
        reject_floats_deep(qualifiers)
        reject_floats_deep(props)
    except Exception:
        _add_warning(
            warnings,
            code="invalid_candidate_payload",
            msg=f"dropped candidate with float payload for predicate {predicate_id}",
        )
        return None

    citations = [
        minimal_doc_citation(
            meta,
            fragment_id=candidate.citation_fragment_id,
        )
    ]
    citations_payload = [citation.model_dump() for citation in citations]
    claim_payload = {
        "predicate_id": predicate_id,
        "subject_id": subject_id,
        "subject_text": subject_text,
        "value_text": value_text,
        "value_decimal": value_decimal,
        "unit_id": unit_id,
        "source_kind": ClaimSourceKind.DOC,
        "citations": citations_payload,
        "jurisdiction": None,
        "domain": None,
        "valid_from": None,
        "valid_to": None,
        "qualifiers": qualifiers,
    }
    claim_id = claim_id_from_payload(claim_payload=claim_payload)
    claim = Claim(
        claim_id=claim_id,
        predicate_id=predicate_id,
        subject_id=subject_id,
        subject_text=subject_text,
        value_text=value_text,
        value_decimal=value_decimal,
        unit_id=unit_id,
        confidence=confidence,
        source_kind=ClaimSourceKind.DOC,
        citations=citations,
        jurisdiction=None,
        domain=None,
        valid_from=None,
        valid_to=None,
        qualifiers=qualifiers,
        props=props,
    )
    validate_claim_id(claim)
    return claim


def _dedup_claims(claims: list[Claim]) -> tuple[list[Claim], int]:
    by_id: dict[str, Claim] = {}
    duplicates = 0
    for claim in claims:
        current = by_id.get(claim.claim_id)
        if current is None:
            by_id[claim.claim_id] = claim
            continue
        duplicates += 1
        if claim.confidence > current.confidence:
            by_id[claim.claim_id] = claim
            continue
        if claim.confidence == current.confidence and _claim_tie_key(claim) < _claim_tie_key(
            current
        ):
            by_id[claim.claim_id] = claim
    deduped = [by_id[claim_id] for claim_id in sorted(by_id)]
    return deduped, duplicates


def extract_claims_from_doc(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    doc_meta_artifact_id: str,
    extractor_id: str,
    options: ClaimExtractOptions | None = None,
    segment_name: str | None = None,
) -> ClaimExtractResult:
    opts = options or ClaimExtractOptions()

    if opts.max_chunks is not None and opts.max_chunks < 0:
        raise ClaimValidationError("max_chunks must be >= 0")
    if opts.max_claims_total is not None and opts.max_claims_total < 0:
        raise ClaimValidationError("max_claims_total must be >= 0")
    if opts.max_claims_per_chunk is not None and opts.max_claims_per_chunk < 0:
        raise ClaimValidationError("max_claims_per_chunk must be >= 0")

    meta = load_doc_meta(cas, doc_meta_artifact_id)
    if meta.normalized_ref is None:
        raise ClaimNotReadyError("call normalize_doc first")
    if meta.chunks_ref is None and opts.require_chunks:
        raise ClaimNotReadyError("call chunk_doc first")
    if meta.chunks_ref is None:
        raise ClaimValidationError("DocMeta.chunks_ref is required for claim extraction")

    normalized_payload = load_json_artifact(cas, meta.normalized_ref)
    normalized_text = normalized_payload.get("text")
    if not isinstance(normalized_text, str):
        raise ClaimValidationError("normalized artifact missing text")

    chunks_payload = load_json_artifact(cas, meta.chunks_ref)
    contexts = _build_chunk_contexts(
        normalized_text=normalized_text,
        chunks_payload=chunks_payload,
    )
    if opts.max_chunks is not None:
        contexts = contexts[: opts.max_chunks]

    resolved_extractor_id, extractor = resolve_extractor(extractor_id)

    warnings: list[tuple[str, str]] = []
    candidates: list[ClaimCandidate] = []
    max_total = opts.max_claims_total
    for ctx in contexts:
        chunk_candidates = extractor(
            ctx=ctx,
            meta=meta,
            normalized_text=normalized_text,
            options=opts,
        )
        if opts.max_claims_per_chunk is not None:
            chunk_candidates = chunk_candidates[: opts.max_claims_per_chunk]
        for candidate in chunk_candidates:
            candidates.append(candidate)
            if max_total is not None and len(candidates) >= max_total:
                break
        if max_total is not None and len(candidates) >= max_total:
            break

    parsed_claims: list[Claim] = []
    for candidate in candidates:
        claim = _candidate_to_claim(
            candidate,
            doc_source_id=meta.doc_source_id,
            meta=meta,
            warnings=warnings,
        )
        if claim is not None:
            parsed_claims.append(claim)

    deduped_claims, dedup_count = _dedup_claims(parsed_claims)
    claims_dropped = len(candidates) - len(parsed_claims) + dedup_count

    stable_prov = stable_world_provenance_v1()
    facts = []
    claim_entries: list[dict[str, str]] = []
    claim_artifact_ids: list[str] = []

    for claim in deduped_claims:
        claim_ref = persist_claim(cas, claim)
        claim_artifact_id = str(claim_ref.artifact_id)
        claim_artifact_ids.append(claim_artifact_id)
        source_fragment_id = claim.citations[0].fragment_id
        claim_entries.append(
            {
                "claim_id": claim.claim_id,
                "claim_artifact_id": claim_artifact_id,
                "source_fragment_id": source_fragment_id or "",
            }
        )
        facts.extend(
            emit_claim_facts(
                claim,
                claim_artifact_id=claim_artifact_id,
                provenance=stable_prov,
            )
        )

    claim_entries.sort(key=lambda row: row["claim_id"])
    claim_set_payload: dict[str, Any] = {
        "schema_version": "1.0",
        "stage": "extract_v1",
        "extractor_id": resolved_extractor_id,
        "doc_meta_artifact_id": doc_meta_artifact_id,
        "doc_source_id": meta.doc_source_id,
        "doc_version_id": meta.doc_version_id,
        "normalized_ref": meta.normalized_ref,
        "chunks_ref": meta.chunks_ref,
        "options": asdict(opts),
        "claims": claim_entries,
        "derived_from": [],
        "stats": {
            "chunks_seen": len(contexts),
            "claims_emitted": len(deduped_claims),
            "claims_dropped": claims_dropped,
        },
    }
    warning_rows = _sorted_warnings(warnings)
    if warning_rows:
        claim_set_payload["warnings"] = warning_rows

    claim_set_inputs = [
        ("doc_meta", doc_meta_artifact_id),
        ("normalized_ref", meta.normalized_ref),
        ("chunks_ref", meta.chunks_ref),
    ] + [("claim", artifact_id) for artifact_id in sorted(claim_artifact_ids)]
    claim_set_artifact_id = persist_claim_set(
        cas=cas,
        payload=claim_set_payload,
        kind=opts.claim_set_kind,
        schema_name=opts.claim_set_schema_name,
        schema_version=opts.claim_set_schema_version,
        inputs=claim_set_inputs,
    )

    evidence_ref: str | None = None
    if opts.build_evidence:
        evidence_ref = persist_claims_evidence_bundle(
            cas=cas,
            source_artifact_ids=[
                doc_meta_artifact_id,
                meta.normalized_ref,
                meta.chunks_ref,
            ],
            transform_op="fabric.claims.extract",
            transform_details={
                "extractor_id": extractor_id,
                "extract_mode": opts.extract_mode,
                "options": canonical_json_text(asdict(opts)),
            },
            schema_name=opts.evidence_schema_name,
            schema_version=opts.evidence_schema_version,
        )

    now = datetime.now(timezone.utc)
    agent = ProvAgent(
        agent_id=opts.agent_id,
        agent_type=ProvAgentType.EXTRACTOR,
        label="Fabric Claims",
    )
    activity = ProvActivity(
        activity_id=opts.activity_id,
        activity_type=ProvActivityType.EXTRACT_CLAIMS,
        label="Extract claims",
        started_at=now,
        ended_at=now,
    )
    inputs_refs = [
        WorldObjectRef(artifact_id=doc_meta_artifact_id),
        WorldObjectRef(artifact_id=meta.normalized_ref),
        WorldObjectRef(artifact_id=meta.chunks_ref),
    ]
    outputs = [WorldObjectRef(artifact_id=claim_set_artifact_id)] + [
        WorldObjectRef(world_id=claim.claim_id) for claim in deduped_claims
    ]
    event_payload = {
        "event_kind": EventKind.EXTRACT_CLAIMS,
        "agent": agent,
        "activity": activity,
        "inputs": inputs_refs,
        "outputs": outputs,
        "evidence_ref": evidence_ref,
        "provenance_ref": None,
    }
    event_id = world_event_id_from_payload(event_payload=event_payload)
    event = WorldEvent(
        event_id=event_id,
        event_kind=EventKind.EXTRACT_CLAIMS,
        agent=agent,
        activity=activity,
        inputs=inputs_refs,
        outputs=outputs,
        evidence_ref=evidence_ref,
        provenance_ref=None,
        props={},
    )
    event_ref = persist_world_event(cas, event)
    event_artifact_id = str(event_ref.artifact_id)

    facts.extend(
        emit_world_event_facts(
            event,
            event_artifact_id=event_artifact_id,
            provenance=event_world_provenance_v1(event_id),
        )
    )

    manifest = write_claims_world_segment(
        facts=facts,
        fact_log_root=fact_log_root,
        segment_name=segment_name or "claims_extract",
    )

    return ClaimExtractResult(
        doc_source_id=meta.doc_source_id,
        doc_version_id=meta.doc_version_id,
        doc_meta_artifact_id=doc_meta_artifact_id,
        normalized_ref=meta.normalized_ref,
        chunks_ref=meta.chunks_ref,
        claim_set_artifact_id=claim_set_artifact_id,
        claim_ids=[claim.claim_id for claim in deduped_claims],
        world_event_id=event_id,
        world_event_artifact_id=event_artifact_id,
        evidence_ref=evidence_ref,
        world_segment_manifest=manifest,
    )


__all__ = ["extract_claims_from_doc"]
