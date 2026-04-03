"""Public normpack extract norm claims module API."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.claims import ClaimNormalizeOptions, normalize_claims
from polisyos.fabric.claims.backends import resolve_extractor
from polisyos.fabric.claims.canonicalize import canonical_unit, canonicalize_id
from polisyos.fabric.claims.citations import minimal_doc_citation
from polisyos.fabric.claims.persist import load_doc_meta, load_json_artifact, persist_claim_set
from polisyos.fabric.claims.types import ChunkContext, ClaimCandidate, ClaimExtractOptions
from polisyos.fabric.world import (
    append_world_segment_index,
    emit_claim_facts,
    persist_claim,
    stable_world_provenance_v1,
    validate_claim_id,
    write_world_fact_segment,
)
from polisyos.fabric.world.events import (
    build_deterministic_world_event,
    persist_world_event_with_facts,
)
from polisyos.ir.fact_log import FactSegmentManifest
from polisyos.ir.kernel.base import ID_PATTERN, reject_floats_deep
from polisyos.ir.world.claim import Claim, ClaimSourceKind
from polisyos.ir.world.doc import DocMeta
from polisyos.ir.world.event import (
    EventKind,
    ProvActivityType,
    ProvAgentType,
    WorldObjectRef,
)
from polisyos.ir.world.ids import claim_id_from_payload
from polisyos.lex.common import collapse_ws
from polisyos.lex.normpack.policies import NORM_CLAIM_EXTRACT_PIPELINE_ID, NORM_CLAIM_SET_KIND

logger = get_logger(__name__)

_ID_RE = re.compile(ID_PATTERN)


@dataclass(frozen=True)
class ProvisionSelection:
    """Provision selection public type."""
    fragment_id: str
    doc_source_id: str
    doc_version_id: str
    doc_meta_artifact_id: str
    provision_index_artifact_id: str
    provision_key: str
    anchor_path: str
    citation_label: str
    kind: str
    offset_start: int
    offset_end: int


@dataclass(frozen=True)
class NormClaimExtractResult:
    """Norm claim extract result data model."""
    raw_claim_set_artifact_ids: list[str]
    raw_claim_ids: list[str]
    normalized_claim_set_artifact_ids: list[str]
    normalized_claim_ids: list[str]
    claim_set_artifact_ids: list[str]
    claim_ids: list[str]
    world_event_ids: list[str]
    world_event_artifact_ids: list[str]
    world_segment_manifest: FactSegmentManifest | None
    warnings: list[str] = field(default_factory=list)


def _to_datetime_utc(value: str | None) -> datetime | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        if len(raw) == 10 and raw.count("-") == 2:
            parsed = datetime.fromisoformat(f"{raw}T00:00:00+00:00")
        else:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        logger.debug("Failed to parse datetime value: %r", value)
        return None


def _claim_tie_key(claim: Claim) -> tuple[str, str, str]:
    return (claim.predicate_id, claim.value_text, claim.unit_id or "")


def _candidate_to_norm_claim(
    candidate: ClaimCandidate,
    *,
    meta: DocMeta,
    provision: ProvisionSelection,
    jurisdiction_norm: str,
    domain_norm: str | None,
    extractor_id: str,
    warnings: list[str],
) -> Claim | None:
    predicate_id = canonicalize_id(candidate.predicate_id)
    if predicate_id is None:
        warnings.append(f"warning:invalid_predicate:{candidate.predicate_id}")
        return None

    subject_id: str | None = None
    if candidate.subject_id is not None:
        raw_subject_id = candidate.subject_id.strip()
        if raw_subject_id and _ID_RE.fullmatch(raw_subject_id) is not None:
            subject_id = raw_subject_id
        elif raw_subject_id:
            canonical_subject = canonicalize_id(raw_subject_id)
            if canonical_subject is not None:
                subject_id = canonical_subject
    if subject_id is None:
        subject_id = "lex.norm"

    subject_text = candidate.subject_text.strip() if candidate.subject_text else None

    value_text = candidate.value_text.strip()
    if not value_text:
        warnings.append(f"warning:empty_value:{predicate_id}")
        return None

    value_decimal = candidate.value_decimal
    if value_decimal is not None and not isinstance(value_decimal, Decimal):
        warnings.append(f"warning:invalid_value_decimal:{predicate_id}")
        return None

    unit_id = canonical_unit(candidate.unit_id) if candidate.unit_id else None

    confidence = candidate.confidence if candidate.confidence is not None else Decimal("0.6")
    if not isinstance(confidence, Decimal):
        warnings.append(f"warning:invalid_confidence:{predicate_id}")
        return None

    qualifiers: dict[str, str | int | bool] = dict(candidate.qualifiers)
    props: dict[str, Any] = dict(candidate.props)
    try:
        reject_floats_deep(qualifiers)
        reject_floats_deep(props)
    except Exception:
        logger.debug("Invalid candidate payload for predicate %s", predicate_id)
        warnings.append(f"warning:invalid_candidate_payload:{predicate_id}")
        return None

    lex_props = props.get("lex") if isinstance(props.get("lex"), dict) else {}
    lex_props = dict(lex_props)
    lex_props.update(
        {
            "provision_key": provision.provision_key,
            "anchor_path": provision.anchor_path,
            "extractor_id": extractor_id,
        }
    )
    props["lex"] = lex_props

    lex_meta = meta.props.get("lex") if isinstance(meta.props, dict) else None
    if not isinstance(lex_meta, dict):
        lex_meta = {}
    effective_from_raw = (
        lex_meta.get("effective_from")
        if isinstance(lex_meta.get("effective_from"), str)
        else None
    )
    effective_to_raw = (
        lex_meta.get("effective_to")
        if isinstance(lex_meta.get("effective_to"), str)
        else None
    )
    valid_from = _to_datetime_utc(effective_from_raw)
    valid_to = _to_datetime_utc(effective_to_raw)

    citation = minimal_doc_citation(meta, fragment_id=provision.fragment_id)
    claim_payload = {
        "predicate_id": predicate_id,
        "subject_id": subject_id,
        "subject_text": subject_text,
        "value_text": value_text,
        "value_decimal": value_decimal,
        "unit_id": unit_id,
        "source_kind": ClaimSourceKind.DOC,
        "citations": [citation.model_dump(mode="python")],
        "jurisdiction": jurisdiction_norm,
        "domain": domain_norm,
        "valid_from": valid_from,
        "valid_to": valid_to,
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
        citations=[citation],
        jurisdiction=jurisdiction_norm,
        domain=domain_norm,
        valid_from=valid_from,
        valid_to=valid_to,
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


def extract_norm_claims(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    jurisdiction_norm: str,
    domain_norm: str | None,
    extractor_id: str,
    provisions: list[ProvisionSelection],
    max_claims: int | None,
    normalize_claim_sets: bool = True,
    segment_name: str | None = None,
) -> NormClaimExtractResult:
    """Extract norm claims helper."""
    if max_claims is not None and max_claims < 0:
        raise ValueError("max_claims must be >= 0")

    if not provisions:
        return NormClaimExtractResult(
            raw_claim_set_artifact_ids=[],
            raw_claim_ids=[],
            normalized_claim_set_artifact_ids=[],
            normalized_claim_ids=[],
            claim_set_artifact_ids=[],
            claim_ids=[],
            world_event_ids=[],
            world_event_artifact_ids=[],
            world_segment_manifest=None,
            warnings=[],
        )

    resolved_extractor_id, extractor = resolve_extractor(extractor_id)
    extract_options = ClaimExtractOptions(require_chunks=False, build_evidence=False)

    provisions_sorted = sorted(
        provisions,
        key=lambda row: (
            row.doc_version_id,
            row.anchor_path,
            row.fragment_id,
        ),
    )
    provisions_by_doc: dict[str, list[ProvisionSelection]] = {}
    for provision in provisions_sorted:
        provisions_by_doc.setdefault(provision.doc_version_id, []).append(provision)

    warnings: list[str] = []
    parsed_claims: list[Claim] = []
    doc_meta_by_doc: dict[str, DocMeta] = {}

    for doc_version_id in sorted(provisions_by_doc):
        per_doc = provisions_by_doc[doc_version_id]
        doc_meta_artifact_id = per_doc[0].doc_meta_artifact_id
        meta = load_doc_meta(cas, doc_meta_artifact_id)
        doc_meta_by_doc[doc_version_id] = meta

        if meta.normalized_ref is None:
            warnings.append(f"warning:normalized_ref_missing:{doc_version_id}")
            continue

        normalized_payload = load_json_artifact(cas, meta.normalized_ref)
        normalized_text = normalized_payload.get("text")
        if not isinstance(normalized_text, str):
            warnings.append(f"warning:normalized_text_missing:{doc_version_id}")
            continue

        for provision in per_doc:
            chunk_text = normalized_text[provision.offset_start : provision.offset_end]
            ctx = ChunkContext(
                fragment_id=provision.fragment_id,
                doc_version_id=doc_version_id,
                offset_start=provision.offset_start,
                offset_end=provision.offset_end,
                text_preview=collapse_ws(chunk_text)[:240],
            )
            candidates = extractor(
                ctx=ctx,
                meta=meta,
                normalized_text=normalized_text,
                options=extract_options,
            )
            for candidate in candidates:
                claim = _candidate_to_norm_claim(
                    candidate,
                    meta=meta,
                    provision=provision,
                    jurisdiction_norm=jurisdiction_norm,
                    domain_norm=domain_norm,
                    extractor_id=resolved_extractor_id,
                    warnings=warnings,
                )
                if claim is not None:
                    parsed_claims.append(claim)

    deduped_claims, duplicates = _dedup_claims(parsed_claims)
    if duplicates > 0:
        warnings.append(f"warning:deduped_claims:{duplicates}")

    if max_claims is not None and len(deduped_claims) > max_claims:
        warnings.append(f"warning:max_claims_truncated:{max_claims}/{len(deduped_claims)}")
        deduped_claims = deduped_claims[:max_claims]

    stable_prov = stable_world_provenance_v1()
    facts = []
    claim_artifact_id_by_id: dict[str, str] = {}
    for claim in deduped_claims:
        claim_ref = persist_claim(cas, claim)
        claim_artifact_id = str(claim_ref.artifact_id)
        claim_artifact_id_by_id[claim.claim_id] = claim_artifact_id
        facts.extend(
            emit_claim_facts(
                claim,
                claim_artifact_id=claim_artifact_id,
                provenance=stable_prov,
            )
        )

    raw_claim_set_artifact_ids: list[str] = []
    world_event_ids: list[str] = []
    world_event_artifact_ids: list[str] = []

    for doc_version_id in sorted(provisions_by_doc):
        per_doc = provisions_by_doc[doc_version_id]
        meta = doc_meta_by_doc.get(doc_version_id)
        if meta is None or meta.normalized_ref is None:
            continue

        selected_fragment_ids = sorted({row.fragment_id for row in per_doc})
        doc_claims = [
            claim
            for claim in deduped_claims
            if claim.citations
            and claim.citations[0].doc.doc_version_id == doc_version_id
        ]
        doc_claims.sort(key=lambda row: row.claim_id)

        claim_rows = [
            {
                "claim_id": claim.claim_id,
                "claim_artifact_id": claim_artifact_id_by_id[claim.claim_id],
                "source_fragment_id": claim.citations[0].fragment_id or "",
            }
            for claim in doc_claims
        ]

        claim_set_payload: dict[str, Any] = {
            "schema_version": "1.0",
            "stage": "lex_norm_extract_v1",
            "extractor_id": extractor_id,
            "doc_meta_artifact_id": per_doc[0].doc_meta_artifact_id,
            "doc_source_id": per_doc[0].doc_source_id,
            "doc_version_id": doc_version_id,
            "normalized_ref": meta.normalized_ref,
            "chunks_ref": meta.chunks_ref or meta.normalized_ref,
            "provision_index_artifact_id": per_doc[0].provision_index_artifact_id,
            "selected_fragment_ids": selected_fragment_ids,
            "claims": claim_rows,
            "derived_from": [],
            "stats": {
                "provisions_seen": len(per_doc),
                "claims_emitted": len(doc_claims),
            },
        }
        claim_set_inputs = [
            ("doc_meta", per_doc[0].doc_meta_artifact_id),
            ("normalized_ref", meta.normalized_ref),
            ("provision_index", per_doc[0].provision_index_artifact_id),
        ] + [
            ("claim", claim_artifact_id_by_id[claim.claim_id])
            for claim in doc_claims
        ]
        claim_set_artifact_id = persist_claim_set(
            cas=cas,
            payload=claim_set_payload,
            kind=NORM_CLAIM_SET_KIND,
            schema_name="lex.norms.claim_set",
            schema_version="1.0",
            inputs=claim_set_inputs,
        )
        raw_claim_set_artifact_ids.append(claim_set_artifact_id)

        inputs = [
            WorldObjectRef(artifact_id=per_doc[0].doc_meta_artifact_id),
            WorldObjectRef(artifact_id=meta.normalized_ref),
            WorldObjectRef(artifact_id=per_doc[0].provision_index_artifact_id),
        ] + [WorldObjectRef(world_id=fragment_id) for fragment_id in selected_fragment_ids]
        outputs = [WorldObjectRef(artifact_id=claim_set_artifact_id)] + [
            WorldObjectRef(world_id=claim.claim_id) for claim in doc_claims
        ]
        event = build_deterministic_world_event(
            event_kind=EventKind.EXTRACT_CLAIMS,
            agent_id="prov.agent.lex_norms",
            agent_type=ProvAgentType.EXTRACTOR,
            agent_label="Lex Norm Claims",
            activity_id="prov.activity.lex_norms.extract",
            activity_type=ProvActivityType.EXTRACT_CLAIMS,
            activity_label="Extract norm claims",
            inputs=inputs,
            outputs=outputs,
            props={"pipeline": NORM_CLAIM_EXTRACT_PIPELINE_ID},
        )
        event_id = event.event_id
        event_artifact_id = persist_world_event_with_facts(cas=cas, event=event, facts=facts)
        world_event_ids.append(event_id)
        world_event_artifact_ids.append(event_artifact_id)

    manifest: FactSegmentManifest | None = None
    if facts:
        manifest = write_world_fact_segment(
            facts,
            fact_log_root=fact_log_root,
            segment_name=segment_name or "lex_normpack_extract_norm_claims",
        )
        append_world_segment_index(manifest, fact_log_root=fact_log_root)

    raw_claim_ids = sorted(claim_artifact_id_by_id)

    normalized_claim_set_artifact_ids: list[str] = []
    normalized_claim_ids: list[str] = []
    if normalize_claim_sets and raw_claim_set_artifact_ids:
        normalize_segment_base = (
            f"{segment_name or 'lex_normpack_extract_norm_claims'}_normalize"
        )
        for claim_set_artifact_id in sorted(set(raw_claim_set_artifact_ids)):
            suffix = claim_set_artifact_id.split(":", 1)[-1][:12]
            normalized = normalize_claims(
                cas=cas,
                fact_log_root=fact_log_root,
                claim_set_artifact_id=claim_set_artifact_id,
                options=ClaimNormalizeOptions(build_evidence=False),
                segment_name=f"{normalize_segment_base}_{suffix}",
            )
            normalized_claim_set_artifact_ids.append(normalized.claim_set_artifact_id)
            normalized_claim_ids.extend(normalized.claim_ids)
        normalized_claim_set_artifact_ids = sorted(set(normalized_claim_set_artifact_ids))
        normalized_claim_ids = sorted(set(normalized_claim_ids))
    else:
        normalized_claim_set_artifact_ids = sorted(set(raw_claim_set_artifact_ids))
        normalized_claim_ids = sorted(set(raw_claim_ids))

    return NormClaimExtractResult(
        raw_claim_set_artifact_ids=sorted(set(raw_claim_set_artifact_ids)),
        raw_claim_ids=raw_claim_ids,
        normalized_claim_set_artifact_ids=normalized_claim_set_artifact_ids,
        normalized_claim_ids=normalized_claim_ids,
        claim_set_artifact_ids=normalized_claim_set_artifact_ids,
        claim_ids=normalized_claim_ids,
        world_event_ids=sorted(set(world_event_ids)),
        world_event_artifact_ids=sorted(set(world_event_artifact_ids)),
        world_segment_manifest=manifest,
        warnings=sorted(set(warnings)),
    )


__all__ = [
    "NormClaimExtractResult",
    "ProvisionSelection",
    "extract_norm_claims",
]
