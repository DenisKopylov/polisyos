"""Claim normalization stage for canonical ids, units, numeric values, and provenance edges.

This stage loads an extracted claim set, rewrites predicates/units/value text into canonical form,
recomputes deterministic ``claim_id`` values, deduplicates equivalent claims, persists a new
claim-set artifact, and emits ``PROV_WAS_DERIVED_FROM`` edges when ids change.
"""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.data_plane.quarantine import (
    QuarantineRecord,
    persist_quarantine_record,
)
from polisyos.fabric.world import (
    emit_claim_facts,
    emit_edge_fact,
    persist_claim,
    stable_world_provenance_v1,
    validate_claim_id,
)
from polisyos.ir.world.abi import EdgeKind
from polisyos.ir.world.claim import Claim, ClaimSourceKind
from polisyos.ir.world.event import (
    EventKind,
    ProvActivityType,
    WorldObjectRef,
)
from polisyos.ir.world.ids import claim_id_from_payload

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
from .world_events import build_claims_world_event, persist_claims_world_event


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


def _quarantine_claim(
    *,
    cas: FileSystemCAS,
    claim_artifact_id: str,
    claim_set_artifact_id: str,
    claim: Claim,
    reason: str,
    message: str,
    options: ClaimNormalizeOptions,
    traceback_class: str | None = None,
) -> str:
    record = QuarantineRecord.new(
        reason=reason,
        severity="error",
        source="claims.normalize",
        raw_payload_ref=claim_artifact_id,
        schema_version=claim.schema_version,
        traceback_class=traceback_class,
        retry_policy=options.quarantine_retry_policy,
        downstream_impacts=("claims.normalize", "world.segment", "world.materialize"),
        context={
            "claim_id": claim.claim_id,
            "claim_set_artifact_id": claim_set_artifact_id,
            "message": message,
        },
    )
    ref = persist_quarantine_record(
        cas,
        record=record,
        input_artifact_ids=[claim_set_artifact_id, claim_artifact_id],
    )
    return str(ref.artifact_id)


def _primary_citation_fragment_id(
    claim: Claim,
    *,
    warnings: list[tuple[str, str]] | None = None,
) -> str:
    for citation in claim.citations:
        fragment_id = getattr(citation, "fragment_id", None)
        if isinstance(fragment_id, str) and fragment_id:
            return fragment_id
    if warnings is not None:
        warnings.append(
            (
                "missing_primary_citation",
                f"claim {claim.claim_id} is missing a usable primary citation",
            )
        )
    return ""


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
    """Normalize one extracted claim set and persist the canonicalized successor artifact.

    Args:
        cas: Artifact store containing the input claim-set artifact and individual claim payloads.
        fact_log_root: Fact-log root where normalized claim facts and the world segment are written.
        claim_set_artifact_id: Extracted claim-set artifact produced by ``extract_claims_from_doc``.
        options: Optional canonicalization and invalid-row handling policy.
        segment_name: Optional world segment name.

    Returns:
        Normalized claim-set artifact id, canonical claim ids, derived-id edges, optional evidence
        bundle reference, and provenance event/segment identifiers.

    Raises:
        ClaimValidationError: If the input claim-set payload is malformed, claim ids mismatch, or
            normalization produces invalid canonical values while ``drop_invalid`` is false.
    """
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
    quarantine_record_ids: list[str] = []

    for claim_artifact_id, claim in input_claims:
        if claim.source_kind == ClaimSourceKind.DOC and not claim.citations:
            invalid_drops += 1
            warnings.append(
                (
                    "missing_primary_citation",
                    f"quarantined claim {claim.claim_id} because it has no citations",
                )
            )
            if opts.quarantine_invalid:
                quarantine_record_ids.append(
                    _quarantine_claim(
                        cas=cas,
                        claim_artifact_id=claim_artifact_id,
                        claim_set_artifact_id=claim_set_artifact_id,
                        claim=claim,
                        reason="missing_primary_citation",
                        message="document claim has no citations",
                        options=opts,
                    )
                )
            continue
        try:
            normalized_claim = _build_normalized_claim(claim, options=opts)
        except ClaimValidationError as exc:
            if not opts.drop_invalid:
                raise
            invalid_drops += 1
            warnings.append(("normalize_error", str(exc)))
            if opts.quarantine_invalid:
                quarantine_record_ids.append(
                    _quarantine_claim(
                        cas=cas,
                        claim_artifact_id=claim_artifact_id,
                        claim_set_artifact_id=claim_set_artifact_id,
                        claim=claim,
                        reason="normalize_error",
                        message=str(exc),
                        options=opts,
                        traceback_class=type(exc).__name__,
                    )
                )
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
            _primary_citation_fragment_id(claim, warnings=warnings)
            if claim.source_kind == ClaimSourceKind.DOC
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
            "claims_quarantined": len(quarantine_record_ids),
        },
    }
    warning_rows = _warning_rows(warnings)
    if warning_rows:
        normalized_claim_set_payload["warnings"] = warning_rows
    if quarantine_record_ids:
        normalized_claim_set_payload["quarantine_record_ids"] = sorted(set(quarantine_record_ids))

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

    inputs_refs = [WorldObjectRef(artifact_id=claim_set_artifact_id)]
    outputs = [WorldObjectRef(artifact_id=normalized_claim_set_artifact_id)] + [
        WorldObjectRef(world_id=claim.claim_id) for claim in deduped_claims
    ]
    event = build_claims_world_event(
        event_kind=EventKind.NORMALIZE_CLAIMS,
        activity_type=ProvActivityType.NORMALIZE_CLAIMS,
        activity_id=opts.activity_id,
        activity_label="Normalize claims",
        agent_id=opts.agent_id,
        inputs=inputs_refs,
        outputs=outputs,
        evidence_ref=evidence_ref,
    )
    event_id = event.event_id
    event_artifact_id = persist_claims_world_event(cas=cas, event=event, facts=facts)

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
        quarantine_record_ids=sorted(set(quarantine_record_ids)),
    )


__all__ = ["normalize_claims"]
