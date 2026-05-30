"""Bridge Lex batch normative facts into CAS-backed claim sets.

This module lets the staged batch pipeline feed downstream ``normpack`` and
fabric conflict/trust flows without requiring a separate ``lex.corpus`` ingest.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import duckdb

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.fabric.claims import ClaimNormalizeOptions, normalize_claims
from polisyos.fabric.claims.canonicalize import (
    canonical_unit,
    canonicalize_id,
    parse_decimal_value_text,
)
from polisyos.fabric.claims.persist import persist_claim_set
from polisyos.fabric.claims.world_events import build_claims_world_event, persist_claims_world_event
from polisyos.fabric.world import (
    append_world_segment_index,
    emit_claim_facts,
    emit_doc_fragment_facts,
    emit_doc_meta_facts,
    persist_claim,
    persist_doc_fragment,
    persist_doc_meta,
    stable_world_provenance_v1,
    validate_claim_id,
    write_world_fact_segment,
)
from polisyos.ir.loading.citations import AnchorKind, CitationRef, DocumentRef, FragmentLocator
from polisyos.ir.world.claim import Claim, ClaimSourceKind
from polisyos.ir.world.doc import DocFragment, DocMeta
from polisyos.ir.world.event import EventKind, ProvActivityType, WorldObjectRef
from polisyos.ir.world.ids import (
    claim_id_from_payload,
    doc_fragment_id,
    doc_source_id,
    doc_version_id_from_raw_artifact,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.ir.loading.fact_log import FactSegmentManifest

logger = get_logger(__name__)

_TEXT_SCHEMA = SchemaInfo(name="polisyos.data_forge.domains.legal.batch.BridgeText", version="1.0")
_CHUNKS_SCHEMA = SchemaInfo(
    name="polisyos.data_forge.domains.legal.batch.BridgeChunks", version="1.0"
)
_THRESHOLD_KEY_PRIORITY = ("value_decimal", "value_text", "unit", "operator")


@dataclass(frozen=True)
class BatchClaimBridgeResult:
    """Batch claim bridge result data model."""

    raw_claim_set_artifact_ids: list[str]
    normalized_claim_set_artifact_ids: list[str]
    claim_ids: list[str]
    world_event_ids: list[str]
    world_event_artifact_ids: list[str]
    doc_meta_artifact_ids: list[str]
    world_segment_manifest: FactSegmentManifest | None
    warnings: list[str] = field(default_factory=list)


def _safe_id(value: str, *, prefix: str) -> str:
    candidate = canonicalize_id(value or "")
    if candidate:
        return candidate
    digest = hashlib.sha256(f"{prefix}|{value}".encode()).hexdigest()[:16]
    return f"{prefix}.{digest}"


def _to_datetime_utc(value: str | None) -> datetime | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        if len(raw) == 10 and raw.count("-") == 2:
            return datetime.fromisoformat(f"{raw}T00:00:00+00:00").astimezone(UTC)
        if len(raw) == 10 and raw.count(".") == 2:
            day, month, year = raw.split(".")
            if len(day) == 2 and len(month) == 2 and len(year) == 4:
                return datetime.fromisoformat(f"{year}-{month}-{day}T00:00:00+00:00").astimezone(
                    UTC
                )
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except Exception:
        logger.debug("Failed to parse bridge datetime {}", value)
        return None


def _anchor_kind(kind: str, struct_kind: str) -> AnchorKind:
    resolved = (struct_kind or kind or "").strip().lower()
    mapping = {
        "article": AnchorKind.ARTICLE,
        "part": AnchorKind.SECTION,
        "point": AnchorKind.CLAUSE,
        "subpoint": AnchorKind.CLAUSE,
        "enumeration_item": AnchorKind.CLAUSE,
        "paragraph": AnchorKind.PARAGRAPH,
        "table_row": AnchorKind.TABLE,
        "appendix": AnchorKind.OTHER,
        "fallback_unit": AnchorKind.CHUNK,
        "full_text": AnchorKind.CHUNK,
    }
    return mapping.get(resolved, AnchorKind.OTHER)


def _official_id(doc_row: dict[str, Any]) -> str:
    reestr_code = str(doc_row.get("doc_reestr_code") or "").strip()
    if reestr_code:
        return f"UA:{reestr_code}"
    return f"UA:BATCH:{doc_row['doc_id']}"


def _put_json_artifact(
    *,
    cas: FileSystemCAS,
    payload: dict[str, Any],
    kind: str,
    schema_name: str,
) -> str:
    ref = cas.put_json(
        payload,
        opts=PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version="1.0"),
        ),
    )
    return str(ref.artifact_id)


def _load_normative_rows(db_path: Path) -> list[dict[str, Any]]:
    with duckdb.connect(str(db_path), read_only=True) as con:
        table_exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'lex_normative_facts'"
        ).fetchone()[0]
        if not table_exists:
            return []
        provisions_table_exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'lex_provisions'"
        ).fetchone()[0]
        provision_join = (
            """
            LEFT JOIN lex_provisions p
                ON p.doc_id = f.doc_id AND p.anchor_path = f.provision_anchor
            """
            if provisions_table_exists
            else ""
        )
        provision_select = (
            """
                    p.kind,
                    p.struct_kind,
                    p.section_role,
                    p.provision_text
            """
            if provisions_table_exists
            else """
                    NULL AS kind,
                    NULL AS struct_kind,
                    NULL AS section_role,
                    NULL AS provision_text
            """
        )
        return [
            {
                "fact_id": row[0],
                "doc_id": row[1],
                "doc_name": row[2] or "",
                "doc_reestr_code": row[3] or "",
                "doc_type": row[4] or "",
                "doc_status": row[5] or "",
                "jurisdiction": row[6] or "UA",
                "top_domain": row[7] or "",
                "effective_from": row[8] or "",
                "effective_to": row[9] or "",
                "provision_anchor": row[10] or "",
                "provision_citation": row[11] or "",
                "subject_en": row[12] or "",
                "subject_uk": row[13] or "",
                "object_en": row[14] or "",
                "object_uk": row[15] or "",
                "predicate": row[16] or "",
                "action_canon": row[17] or "",
                "norm_type_canon": row[18] or "",
                "constraint_type_canon": row[19] or "",
                "fact_text": row[20] or "",
                "confidence": float(row[21] or 0.0),
                "thresholds_json": row[22] or "[]",
                "source_quote_uk": row[23] or "",
                "source_quote_start": row[24],
                "source_quote_end": row[25],
                "kind": row[26] or "",
                "struct_kind": row[27] or "",
                "section_role": row[28] or "",
                "provision_text": row[29] or "",
            }
            for row in con.execute(
                f"""
                SELECT
                    f.fact_id,
                    f.doc_id,
                    f.doc_name,
                    f.doc_reestr_code,
                    f.doc_type,
                    f.doc_status,
                    f.jurisdiction,
                    f.top_domain,
                    f.effective_from,
                    f.effective_to,
                    f.provision_anchor,
                    f.provision_citation,
                    f.subject_en,
                    f.subject_uk,
                    f.object_en,
                    f.object_uk,
                    f.predicate,
                    f.action_canon,
                    f.norm_type_canon,
                    f.constraint_type_canon,
                    f.fact_text,
                    f.confidence,
                    f.thresholds_json,
                    f.source_quote_uk,
                    f.source_quote_start,
                    f.source_quote_end,
                    {provision_select}
                FROM lex_normative_facts f
                {provision_join}
                ORDER BY f.doc_id, f.provision_anchor, f.fact_id
                """
            ).fetchall()
        ]


def _group_rows_by_doc(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["doc_id"])].append(row)
    return grouped


def _provision_rows(doc_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_anchor: dict[str, dict[str, Any]] = {}
    for row in doc_rows:
        anchor = str(row.get("provision_anchor") or "")
        current = by_anchor.get(anchor)
        if current is None:
            by_anchor[anchor] = {
                "anchor": anchor,
                "citation": str(row.get("provision_citation") or anchor or ""),
                "text": str(
                    row.get("provision_text")
                    or row.get("source_quote_uk")
                    or row.get("fact_text")
                    or ""
                ),
                "kind": str(row.get("kind") or ""),
                "struct_kind": str(row.get("struct_kind") or row.get("kind") or ""),
                "section_role": str(row.get("section_role") or ""),
            }
            continue
        if len(str(row.get("provision_text") or "")) > len(current["text"]):
            current["text"] = str(row.get("provision_text") or "")
    return [by_anchor[key] for key in sorted(by_anchor)]


def _build_doc_context(
    *,
    cas: FileSystemCAS,
    doc_rows: list[dict[str, Any]],
) -> tuple[DocMeta, str, str, str, list[dict[str, Any]]]:
    sample = doc_rows[0]
    provisions = _provision_rows(doc_rows)
    parts: list[str] = []
    chunk_rows: list[dict[str, Any]] = []
    raw_text = "\n\n".join(prov["text"] for prov in provisions)
    raw_ref = str(
        cas.put_bytes(
            raw_text.encode("utf-8"),
            opts=PutOptions(
                kind="lex.batch.raw_text",
                media_type="text/plain",
                schema=_TEXT_SCHEMA,
            ),
        ).artifact_id
    )
    doc_version_id = doc_version_id_from_raw_artifact(raw_artifact_id=raw_ref)
    source_id = doc_source_id(
        canonical_url=None,
        official_id=_official_id(sample),
    )

    offset = 0
    for idx, provision in enumerate(provisions, start=1):
        text = provision["text"]
        if not text:
            continue
        if parts:
            parts.append("\n\n")
            offset += 2
        start = offset
        parts.append(text)
        offset += len(text)
        end = offset
        text_ref = cas.put_bytes(
            text.encode("utf-8"),
            opts=PutOptions(
                kind="lex.batch.fragment_text",
                media_type="text/plain",
                schema=_TEXT_SCHEMA,
            ),
        )
        locator = FragmentLocator(
            anchor_kind=_anchor_kind(
                str(provision["kind"]),
                str(provision["struct_kind"]),
            ),
            anchor_path=str(provision["anchor"] or f"chunk:{idx}"),
            offset_start=start,
            offset_end=end,
        )
        fragment_id = doc_fragment_id(
            doc_version_id=doc_version_id,
            locator=locator,
            text_artifact_id=str(text_ref.artifact_id),
        )
        chunk_rows.append(
            {
                "fragment_id": fragment_id,
                "offset_start": start,
                "offset_end": end,
                "anchor_path": provision["anchor"],
                "citation_label": provision["citation"],
                "kind": provision["kind"],
                "struct_kind": provision["struct_kind"],
                "text_artifact_id": str(text_ref.artifact_id),
            }
        )

    normalized_text = "".join(parts)
    normalized_ref = _put_json_artifact(
        cas=cas,
        payload={"doc_version_id": doc_version_id, "text": normalized_text},
        kind="lex.batch.normalized_text",
        schema_name="polisyos.data_forge.domains.legal.batch.NormalizedText",
    )
    chunks_ref = _put_json_artifact(
        cas=cas,
        payload={
            "doc_version_id": doc_version_id,
            "chunks": chunk_rows,
        },
        kind="lex.batch.chunks",
        schema_name="polisyos.data_forge.domains.legal.batch.Chunks",
    )

    meta = DocMeta(
        doc_source_id=source_id,
        doc_version_id=doc_version_id,
        canonical_url=None,
        official_id=_official_id(sample),
        retrieved_at=datetime.now(UTC),
        mime="text/plain",
        license="public",
        jurisdiction=str(sample.get("jurisdiction") or "UA"),
        language="uk",
        raw_ref=raw_ref,
        normalized_ref=normalized_ref,
        structure_ref=None,
        chunks_ref=chunks_ref,
        props={
            "title": sample["doc_name"],
            "lex": {
                "corpus": "lex.batch",
                "source_mode": "lex.batch.claim_bridge_v1",
                "batch_doc_id": sample["doc_id"],
                "doc_name": sample["doc_name"],
                "doc_reestr_code": sample["doc_reestr_code"],
                "doc_type": sample["doc_type"],
                "doc_status": sample["doc_status"],
                "domain": sample["top_domain"],
                "jurisdiction": sample["jurisdiction"],
                "effective_from": sample["effective_from"],
                "effective_to": sample["effective_to"],
            },
        },
    )
    return meta, raw_ref, normalized_ref, chunks_ref, chunk_rows


def _predicate_id(row: dict[str, Any], threshold: dict[str, Any] | None) -> str:
    domain = _safe_id(str(row.get("top_domain") or "general"), prefix="domain")
    if threshold:
        metric = _safe_id(str(threshold.get("metric") or "threshold"), prefix="metric")
        return f"legal.{domain}.{metric}"
    if str(row.get("constraint_type_canon") or "").strip():
        return f"legal.{domain}.{_safe_id(str(row['constraint_type_canon']), prefix='constraint')}"
    if str(row.get("action_canon") or "").strip():
        return f"legal.{domain}.{_safe_id(str(row['action_canon']), prefix='action')}"
    return f"legal.{domain}.norm"


def _value_payload(
    row: dict[str, Any], threshold: dict[str, Any] | None
) -> tuple[str, Decimal | None, str | None, dict[str, str | int | bool]]:
    if threshold:
        raw_text = str(
            threshold.get("value_decimal")
            or threshold.get("value_text")
            or row.get("object_en")
            or row.get("fact_text")
            or ""
        )
        value_decimal = parse_decimal_value_text(raw_text)
        unit_id = (
            canonical_unit(str(threshold.get("unit") or "")) if threshold.get("unit") else None
        )
        qualifiers: dict[str, str | int | bool] = {}
        operator = str(threshold.get("operator") or "").strip()
        if operator:
            qualifiers["op"] = operator
        applies_to = str(threshold.get("applies_to") or "").strip()
        if applies_to:
            qualifiers["applies_to"] = applies_to
        return raw_text, value_decimal, unit_id, qualifiers

    value_text = str(
        row.get("object_en") or row.get("fact_text") or row.get("provision_citation") or "norm"
    )
    return value_text, None, None, {}


def _quote_hash(cas: FileSystemCAS, text: str) -> str | None:
    cleaned = text.strip()
    if not cleaned:
        return None
    ref = cas.put_bytes(
        cleaned.encode("utf-8"),
        opts=PutOptions(
            kind="lex.batch.quote",
            media_type="text/plain",
            schema=_TEXT_SCHEMA,
        ),
    )
    return str(ref.artifact_id)


def _claims_for_row(
    *,
    cas: FileSystemCAS,
    row: dict[str, Any],
    doc_meta: DocMeta,
    fragment_id: str,
) -> list[Claim]:
    try:
        thresholds = json.loads(str(row.get("thresholds_json") or "[]"))
        if not isinstance(thresholds, list):
            thresholds = []
    except json.JSONDecodeError:
        thresholds = []
    threshold_rows = [item for item in thresholds if isinstance(item, dict)]
    if not threshold_rows:
        threshold_rows = [None]

    claims: list[Claim] = []
    quote_hash = _quote_hash(cas, str(row.get("source_quote_uk") or ""))
    subject_text = str(row.get("subject_uk") or row.get("subject_en") or "").strip() or None
    subject_id = _safe_id(
        str(row.get("subject_en") or row.get("subject_uk") or "lex_norm"),
        prefix="subject",
    )
    for threshold in threshold_rows:
        predicate_id = _predicate_id(row, threshold)
        value_text, value_decimal, unit_id, qualifiers = _value_payload(row, threshold)
        if not value_text.strip():
            continue
        citations = [
            CitationRef(
                doc=DocumentRef(
                    doc_id=doc_meta.doc_source_id,
                    doc_version_id=doc_meta.doc_version_id,
                ),
                fragment_id=fragment_id,
                locator=FragmentLocator(
                    anchor_kind=_anchor_kind(
                        str(row.get("kind") or ""),
                        str(row.get("struct_kind") or ""),
                    ),
                    anchor_path=str(row.get("provision_anchor") or ""),
                    offset_start=(
                        int(row["source_quote_start"])
                        if row.get("source_quote_start") is not None
                        else None
                    ),
                    offset_end=(
                        int(row["source_quote_end"])
                        if row.get("source_quote_end") is not None
                        else None
                    ),
                ),
                quote_hash=quote_hash,
                notes=[str(row.get("provision_citation") or "")]
                if row.get("provision_citation")
                else [],
                props={"fact_id": str(row.get("fact_id") or "")},
            )
        ]
        claim_payload = {
            "predicate_id": predicate_id,
            "subject_id": subject_id,
            "subject_text": subject_text,
            "value_text": value_text,
            "value_decimal": value_decimal,
            "unit_id": unit_id,
            "source_kind": ClaimSourceKind.DOC,
            "citations": [citation.model_dump(mode="python") for citation in citations],
            "jurisdiction": str(row.get("jurisdiction") or "").casefold() or None,
            "domain": str(row.get("top_domain") or "").casefold() or None,
            "valid_from": _to_datetime_utc(str(row.get("effective_from") or "")),
            "valid_to": _to_datetime_utc(str(row.get("effective_to") or "")),
            "qualifiers": qualifiers,
        }
        claim = Claim(
            claim_id=claim_id_from_payload(claim_payload=claim_payload),
            predicate_id=predicate_id,
            subject_id=subject_id,
            subject_text=subject_text,
            value_text=value_text,
            value_decimal=value_decimal,
            unit_id=unit_id,
            confidence=Decimal(str(max(0.0, min(1.0, float(row.get("confidence") or 0.6))))),
            source_kind=ClaimSourceKind.DOC,
            citations=citations,
            jurisdiction=str(row.get("jurisdiction") or "").casefold() or None,
            domain=str(row.get("top_domain") or "").casefold() or None,
            valid_from=_to_datetime_utc(str(row.get("effective_from") or "")),
            valid_to=_to_datetime_utc(str(row.get("effective_to") or "")),
            qualifiers=qualifiers,
            props={
                "lex": {
                    "source_mode": "lex.batch.claim_bridge_v1",
                    "source_fact_id": str(row.get("fact_id") or ""),
                    "provision_anchor": str(row.get("provision_anchor") or ""),
                    "provision_citation": str(row.get("provision_citation") or ""),
                    "action_canon": str(row.get("action_canon") or ""),
                    "norm_type_canon": str(row.get("norm_type_canon") or ""),
                    "constraint_type_canon": str(row.get("constraint_type_canon") or ""),
                    "operator": qualifiers.get("op"),
                    "must_not": str(row.get("norm_type_canon") or "") == "prohibition",
                    "trust_tier": "normative_fact",
                    "structure_quality": str(row.get("struct_kind") or row.get("kind") or ""),
                }
            },
        )
        validate_claim_id(claim)
        claims.append(claim)
    return claims


def export_normative_claim_sets(
    *,
    db_path: Path,
    cas_root: Path,
    fact_log_root: Path,
    output_dir: Path,
    normalize_claim_sets: bool = True,
    segment_name: str = "lex_batch_export_claim_sets",
) -> BatchClaimBridgeResult:
    """Persist normative Lex batch facts as CAS-backed ``lex.norms.claim_set`` artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cas = FileSystemCAS(cas_root)
    rows = _load_normative_rows(db_path)
    if not rows:
        return BatchClaimBridgeResult(
            raw_claim_set_artifact_ids=[],
            normalized_claim_set_artifact_ids=[],
            claim_ids=[],
            world_event_ids=[],
            world_event_artifact_ids=[],
            doc_meta_artifact_ids=[],
            world_segment_manifest=None,
            warnings=["warning:no_normative_facts_available"],
        )

    provenance = stable_world_provenance_v1()
    grouped = _group_rows_by_doc(rows)
    all_facts: list[Any] = []
    raw_claim_set_artifact_ids: list[str] = []
    world_event_ids: list[str] = []
    world_event_artifact_ids: list[str] = []
    doc_meta_artifact_ids: list[str] = []
    claim_ids: list[str] = []
    warnings: list[str] = []

    for doc_id in sorted(grouped):
        doc_rows = grouped[doc_id]
        meta, _raw_ref, normalized_ref, chunks_ref, chunk_rows = _build_doc_context(
            cas=cas,
            doc_rows=doc_rows,
        )
        meta_ref = persist_doc_meta(cas, meta)
        doc_meta_artifact_id = str(meta_ref.artifact_id)
        doc_meta_artifact_ids.append(doc_meta_artifact_id)
        doc_facts: list[Any] = []
        doc_facts.extend(
            emit_doc_meta_facts(
                meta,
                meta_artifact_id=doc_meta_artifact_id,
                provenance=provenance,
            )
        )

        fragment_id_by_anchor = {row["anchor_path"]: row["fragment_id"] for row in chunk_rows}
        for chunk in chunk_rows:
            fragment = DocFragment(
                fragment_id=chunk["fragment_id"],
                doc_version_id=meta.doc_version_id,
                locator=FragmentLocator(
                    anchor_kind=_anchor_kind(
                        str(chunk.get("kind") or ""),
                        str(chunk.get("struct_kind") or ""),
                    ),
                    anchor_path=chunk["anchor_path"] or None,
                    offset_start=int(chunk["offset_start"]),
                    offset_end=int(chunk["offset_end"]),
                ),
                text_hash=str(chunk["text_artifact_id"]),
                quote_preview=chunk["citation_label"],
                props={"source_mode": "lex.batch.claim_bridge_v1"},
            )
            fragment_ref = persist_doc_fragment(cas, fragment)
            doc_facts.extend(
                emit_doc_fragment_facts(
                    fragment,
                    fragment_artifact_id=str(fragment_ref.artifact_id),
                    provenance=provenance,
                )
            )

        doc_claims: list[Claim] = []
        claim_rows: list[dict[str, str]] = []
        for row in doc_rows:
            anchor = str(row.get("provision_anchor") or "")
            fragment_id = fragment_id_by_anchor.get(anchor)
            if fragment_id is None:
                warnings.append(f"warning:missing_fragment_for_anchor:{doc_id}:{anchor}")
                continue
            for claim in _claims_for_row(cas=cas, row=row, doc_meta=meta, fragment_id=fragment_id):
                claim_ref = persist_claim(cas, claim)
                claim_artifact_id = str(claim_ref.artifact_id)
                doc_claims.append(claim)
                claim_ids.append(claim.claim_id)
                claim_rows.append(
                    {
                        "claim_id": claim.claim_id,
                        "claim_artifact_id": claim_artifact_id,
                        "source_fragment_id": fragment_id,
                    }
                )
                doc_facts.extend(
                    emit_claim_facts(
                        claim,
                        claim_artifact_id=claim_artifact_id,
                        provenance=provenance,
                    )
                )

        claim_rows.sort(key=lambda item: item["claim_id"])
        claim_set_payload = {
            "schema_version": "1.0",
            "stage": "lex_batch_export_v1",
            "extractor_id": "lex.batch.claim_bridge_v1",
            "doc_meta_artifact_id": doc_meta_artifact_id,
            "doc_source_id": meta.doc_source_id,
            "doc_version_id": meta.doc_version_id,
            "normalized_ref": normalized_ref,
            "chunks_ref": chunks_ref,
            "selected_fragment_ids": sorted({row["source_fragment_id"] for row in claim_rows}),
            "claims": claim_rows,
            "derived_from": [],
            "domain": str(doc_rows[0].get("top_domain") or "").casefold() or None,
            "stats": {
                "facts_seen": len(doc_rows),
                "claims_emitted": len(claim_rows),
            },
        }
        claim_set_artifact_id = persist_claim_set(
            cas=cas,
            payload=claim_set_payload,
            kind="lex.norms.claim_set",
            schema_name="lex.norms.claim_set",
            schema_version="1.0",
            inputs=[
                ("doc_meta", doc_meta_artifact_id),
                ("normalized_ref", normalized_ref),
                ("chunks_ref", chunks_ref),
                *[("claim", row["claim_artifact_id"]) for row in claim_rows],
            ],
        )
        raw_claim_set_artifact_ids.append(claim_set_artifact_id)

        event = build_claims_world_event(
            event_kind=EventKind.EXTRACT_CLAIMS,
            activity_type=ProvActivityType.EXTRACT_CLAIMS,
            activity_id="prov.activity.lex_batch.export_claims",
            activity_label="Export Lex batch claims",
            agent_id="prov.agent.lex_batch_claim_bridge",
            inputs=[
                WorldObjectRef(artifact_id=doc_meta_artifact_id),
                WorldObjectRef(artifact_id=normalized_ref),
                WorldObjectRef(artifact_id=chunks_ref),
            ],
            outputs=[WorldObjectRef(artifact_id=claim_set_artifact_id)]
            + [WorldObjectRef(world_id=claim.claim_id) for claim in doc_claims],
            props={"pipeline": "lex.batch.claim_bridge_v1"},
        )
        event_id = event.event_id
        event_artifact_id = persist_claims_world_event(
            cas=cas,
            event=event,
            facts=doc_facts,
        )
        world_event_ids.append(event_id)
        world_event_artifact_ids.append(event_artifact_id)
        all_facts.extend(doc_facts)

    manifest = write_world_fact_segment(
        all_facts,
        fact_log_root=fact_log_root,
        segment_name=segment_name,
    )
    append_world_segment_index(manifest, fact_log_root=fact_log_root)

    normalized_claim_set_artifact_ids: list[str] = []
    if normalize_claim_sets:
        for artifact_id in raw_claim_set_artifact_ids:
            suffix = artifact_id.split(":", 1)[-1][:12]
            normalized = normalize_claims(
                cas=cas,
                fact_log_root=fact_log_root,
                claim_set_artifact_id=artifact_id,
                options=ClaimNormalizeOptions(build_evidence=False),
                segment_name=f"{segment_name}_normalize_{suffix}",
            )
            normalized_claim_set_artifact_ids.append(normalized.claim_set_artifact_id)
    else:
        normalized_claim_set_artifact_ids = list(raw_claim_set_artifact_ids)

    summary_path = output_dir / "normative_claim_sets_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "raw_claim_set_artifact_ids": sorted(set(raw_claim_set_artifact_ids)),
                "normalized_claim_set_artifact_ids": sorted(set(normalized_claim_set_artifact_ids)),
                "claim_ids": sorted(set(claim_ids)),
                "world_event_ids": sorted(set(world_event_ids)),
                "world_event_artifact_ids": sorted(set(world_event_artifact_ids)),
                "doc_meta_artifact_ids": sorted(set(doc_meta_artifact_ids)),
                "world_segment_manifest": str(manifest.path),
                "cas_root": str(cas_root),
                "fact_log_root": str(fact_log_root),
                "warnings": sorted(set(warnings)),
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    return BatchClaimBridgeResult(
        raw_claim_set_artifact_ids=sorted(set(raw_claim_set_artifact_ids)),
        normalized_claim_set_artifact_ids=sorted(set(normalized_claim_set_artifact_ids)),
        claim_ids=sorted(set(claim_ids)),
        world_event_ids=sorted(set(world_event_ids)),
        world_event_artifact_ids=sorted(set(world_event_artifact_ids)),
        doc_meta_artifact_ids=sorted(set(doc_meta_artifact_ids)),
        world_segment_manifest=manifest,
        warnings=sorted(set(warnings)),
    )


__all__ = [
    "BatchClaimBridgeResult",
    "export_normative_claim_sets",
]
