from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.world import (
    emit_claim_facts,
    emit_edge_fact,
    emit_world_event_facts,
    event_world_provenance_v1,
    persist_claim,
    persist_world_event,
    stable_world_provenance_v1,
    validate_claim_id,
)
from polisyos.ir.world.abi import EdgeKind
from polisyos.ir.world.claim import Claim, ClaimSourceKind
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

from .canonicalize import (
    canonical_decimal_text,
    canonical_unit,
    canonicalize_id,
    parse_decimal_value_text,
)
from .errors import ClaimValidationError
from .persist import (
    canonical_json_text,
    load_claim,
    load_json_artifact,
    persist_claim_set,
    persist_claims_evidence_bundle,
    write_claims_world_segment,
)
from .types import ClaimNormalizeOptions, ClaimNormalizeResult


def _warning_rows(warnings: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [
        {"code": code, "msg": msg}
        for code, msg in sorted(set(warnings), key=lambda item: (item[0], item[1]))
    ]


def _require_str(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ClaimValidationError(f"claim_set missing required field: {field}")
    return value


def _claim_tie_key(claim: Claim) -> tuple[str, str, str]:
    return (claim.predicate_id, claim.value_text, claim.unit_id or "")


def _build_normalized_claim(claim: Claim, *, options: ClaimNormalizeOptions) -> Claim:
    predicate_id = claim.predicate_id
    if options.normalize_predicates:
        normalized_predicate = canonicalize_id(predicate_id)
        if normalized_predicate is None:
            raise ClaimValidationError(f"invalid predicate_id after normalization: {predicate_id}")
        predicate_id = normalized_predicate

    unit_id = claim.unit_id
    if options.normalize_units and unit_id is not None:
        normalized_unit = canonical_unit(unit_id)
        if normalized_unit is None:
            raise ClaimValidationError(f"invalid unit_id after normalization: {unit_id}")
        unit_id = normalized_unit

    value_text = claim.value_text
    value_decimal = claim.value_decimal
    parsed_decimal: Decimal | None = value_decimal
    if options.parse_numeric:
        if parsed_decimal is None:
            parsed_decimal = parse_decimal_value_text(value_text)
        if parsed_decimal is not None:
            value_decimal = parsed_decimal
            if options.canonicalize_numeric_value_text:
                value_text = canonical_decimal_text(parsed_decimal)

    claim_payload: dict[str, Any] = {
        "predicate_id": predicate_id,
        "subject_id": claim.subject_id,
        "subject_text": claim.subject_text,
        "value_text": value_text,
        "value_decimal": value_decimal,
        "unit_id": unit_id,
        "source_kind": claim.source_kind,
        "jurisdiction": claim.jurisdiction,
        "domain": claim.domain,
        "valid_from": claim.valid_from,
        "valid_to": claim.valid_to,
        "qualifiers": claim.qualifiers,
    }
    if claim.source_kind == ClaimSourceKind.DOC:
        claim_payload["citations"] = [citation.model_dump() for citation in claim.citations]
    else:
        claim_payload["source_artifacts"] = claim.source_artifacts

    claim_id = claim_id_from_payload(claim_payload=claim_payload)
    normalized_claim = Claim(
        claim_id=claim_id,
        predicate_id=predicate_id,
        subject_id=claim.subject_id,
        subject_text=claim.subject_text,
        value_text=value_text,
        value_decimal=value_decimal,
        unit_id=unit_id,
        confidence=claim.confidence,
        source_kind=claim.source_kind,
        citations=claim.citations,
        source_artifacts=claim.source_artifacts,
        jurisdiction=claim.jurisdiction,
        domain=claim.domain,
        valid_from=claim.valid_from,
        valid_to=claim.valid_to,
        qualifiers=claim.qualifiers,
        props=claim.props,
    )
    validate_claim_id(normalized_claim)
    return normalized_claim


def _dedup_claims(pairs: list[tuple[str, Claim]]) -> tuple[list[Claim], int]:
    selected: dict[str, Claim] = {}
    duplicates = 0
    for _, claim in pairs:
        current = selected.get(claim.claim_id)
        if current is None:
            selected[claim.claim_id] = claim
            continue
        duplicates += 1
        if claim.confidence > current.confidence:
            selected[claim.claim_id] = claim
            continue
        if claim.confidence == current.confidence and _claim_tie_key(claim) < _claim_tie_key(
            current
        ):
            selected[claim.claim_id] = claim
    return [selected[claim_id] for claim_id in sorted(selected)], duplicates


def normalize_claims(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    claim_set_artifact_id: str,
    options: ClaimNormalizeOptions | None = None,
    segment_name: str | None = None,
) -> ClaimNormalizeResult:
    opts = options or ClaimNormalizeOptions()

    claim_set_payload = load_json_artifact(cas, claim_set_artifact_id)
    doc_meta_artifact_id = _require_str(claim_set_payload, "doc_meta_artifact_id")
    doc_source_id = _require_str(claim_set_payload, "doc_source_id")
    doc_version_id = _require_str(claim_set_payload, "doc_version_id")
    normalized_ref = _require_str(claim_set_payload, "normalized_ref")
    chunks_ref = _require_str(claim_set_payload, "chunks_ref")

    claim_rows = claim_set_payload.get("claims")
    if not isinstance(claim_rows, list):
        raise ClaimValidationError("claim_set payload missing claims[]")

    input_claim_refs: list[tuple[str, str]] = []
    for idx, row in enumerate(claim_rows):
        if not isinstance(row, dict):
            raise ClaimValidationError(f"claims[{idx}] must be an object")
        claim_id = row.get("claim_id")
        claim_artifact_id = row.get("claim_artifact_id")
        if not isinstance(claim_id, str) or not isinstance(claim_artifact_id, str):
            raise ClaimValidationError(f"claims[{idx}] missing claim_id/claim_artifact_id")
        input_claim_refs.append((claim_id, claim_artifact_id))
    input_claim_refs.sort(key=lambda item: (item[0], item[1]))

    input_claims: list[tuple[str, Claim]] = []
    for expected_claim_id, artifact_id in input_claim_refs:
        claim = load_claim(cas, artifact_id)
        if claim.claim_id != expected_claim_id:
            raise ClaimValidationError(
                f"claim_set claim_id mismatch: expected {expected_claim_id}, got {claim.claim_id}"
            )
        input_claims.append((artifact_id, claim))
    input_claims.sort(key=lambda item: item[1].claim_id)

    warnings: list[tuple[str, str]] = []
    normalized_pairs: list[tuple[str, Claim]] = []
    derived_pairs: list[tuple[str, str]] = []
    invalid_drops = 0

    for _, claim in input_claims:
        try:
            normalized_claim = _build_normalized_claim(claim, options=opts)
        except ClaimValidationError as exc:
            if not opts.drop_invalid:
                raise
            invalid_drops += 1
            warnings.append(("normalize_error", str(exc)))
            continue
        normalized_pairs.append((claim.claim_id, normalized_claim))
        if normalized_claim.claim_id != claim.claim_id:
            derived_pairs.append((claim.claim_id, normalized_claim.claim_id))

    deduped_claims, dedup_drops = _dedup_claims(normalized_pairs)
    claims_dropped = invalid_drops + dedup_drops

    stable_prov = stable_world_provenance_v1()
    facts = []
    output_claim_entries: list[dict[str, str]] = []
    output_claim_artifact_ids: list[str] = []

    for claim in deduped_claims:
        claim_ref = persist_claim(cas, claim)
        claim_artifact_id = str(claim_ref.artifact_id)
        output_claim_artifact_ids.append(claim_artifact_id)
        source_fragment_id = (
            claim.citations[0].fragment_id
            if claim.source_kind == ClaimSourceKind.DOC and claim.citations
            else ""
        )
        output_claim_entries.append(
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

    derived_pairs = sorted(set(derived_pairs), key=lambda item: (item[0], item[1]))
    for old_claim_id, new_claim_id in derived_pairs:
        facts.append(
            emit_edge_fact(
                src_id=new_claim_id,
                edge_kind=EdgeKind.PROV_WAS_DERIVED_FROM,
                dst_id=old_claim_id,
                provenance=stable_prov,
            )
        )

    output_claim_entries.sort(key=lambda row: row["claim_id"])
    derived_rows = [
        {"input_claim_id": old_claim_id, "output_claim_id": new_claim_id}
        for old_claim_id, new_claim_id in derived_pairs
    ]
    normalized_claim_set_payload: dict[str, Any] = {
        "schema_version": "1.0",
        "stage": "normalize_v1",
        "extractor_id": claim_set_payload.get("extractor_id"),
        "doc_meta_artifact_id": doc_meta_artifact_id,
        "doc_source_id": doc_source_id,
        "doc_version_id": doc_version_id,
        "normalized_ref": normalized_ref,
        "chunks_ref": chunks_ref,
        "input_claim_set_artifact_id": claim_set_artifact_id,
        "options": asdict(opts),
        "claims": output_claim_entries,
        "derived_from": derived_rows,
        "stats": {
            "input_claims": len(input_claims),
            "claims_emitted": len(deduped_claims),
            "claims_dropped": claims_dropped,
        },
    }
    warning_rows = _warning_rows(warnings)
    if warning_rows:
        normalized_claim_set_payload["warnings"] = warning_rows

    claim_set_inputs = [("input_claim_set", claim_set_artifact_id)]
    claim_set_inputs.extend(
        ("input_claim", artifact_id) for _, artifact_id in sorted(set(input_claim_refs))
    )
    claim_set_inputs.extend(
        ("claim", artifact_id) for artifact_id in sorted(set(output_claim_artifact_ids))
    )
    normalized_claim_set_artifact_id = persist_claim_set(
        cas=cas,
        payload=normalized_claim_set_payload,
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
                claim_set_artifact_id,
                *[artifact_id for _, artifact_id in sorted(set(input_claim_refs))],
            ],
            transform_op="fabric.claims.normalize",
            transform_details={
                "stage": "normalize_v1",
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
        activity_type=ProvActivityType.NORMALIZE_CLAIMS,
        label="Normalize claims",
        started_at=now,
        ended_at=now,
    )
    inputs_refs = [WorldObjectRef(artifact_id=claim_set_artifact_id)]
    outputs = [WorldObjectRef(artifact_id=normalized_claim_set_artifact_id)] + [
        WorldObjectRef(world_id=claim.claim_id) for claim in deduped_claims
    ]
    event_payload = {
        "event_kind": EventKind.NORMALIZE_CLAIMS,
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
        event_kind=EventKind.NORMALIZE_CLAIMS,
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
        segment_name=segment_name or "claims_normalize",
    )

    return ClaimNormalizeResult(
        doc_source_id=doc_source_id,
        doc_version_id=doc_version_id,
        doc_meta_artifact_id=doc_meta_artifact_id,
        normalized_ref=normalized_ref,
        chunks_ref=chunks_ref,
        input_claim_set_artifact_id=claim_set_artifact_id,
        claim_set_artifact_id=normalized_claim_set_artifact_id,
        claim_ids=[claim.claim_id for claim in deduped_claims],
        world_event_id=event_id,
        world_event_artifact_id=event_artifact_id,
        evidence_ref=evidence_ref,
        world_segment_manifest=manifest,
        derived_edges=derived_pairs,
    )


__all__ = ["normalize_claims"]
