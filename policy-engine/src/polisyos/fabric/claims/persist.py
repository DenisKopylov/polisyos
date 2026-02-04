from __future__ import annotations

from pathlib import Path

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import EvidenceStep
from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle
from polisyos.fabric.world import (
    append_world_segment_index,
    validate_claim_id,
    validate_doc_meta_ids,
    write_world_fact_segment,
)
from polisyos.ir.canon import to_canonical_bytes
from polisyos.ir.fact_log import Fact, FactSegmentManifest
from polisyos.ir.world.claim import Claim
from polisyos.ir.world.doc import DocMeta

from .errors import ClaimValidationError


def load_json_artifact(cas: FileSystemCAS, artifact_id: str) -> dict:
    try:
        aid = ArtifactID.model_validate(artifact_id)
        payload = from_canonical_bytes(cas.get_bytes(aid))
    except Exception as exc:  # pragma: no cover - defensive
        raise ClaimValidationError(f"failed to load artifact {artifact_id}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ClaimValidationError(f"artifact {artifact_id} payload must be a JSON object")
    return payload


def load_doc_meta(cas: FileSystemCAS, artifact_id: str) -> DocMeta:
    payload = load_json_artifact(cas, artifact_id)
    meta = DocMeta.model_validate(payload)
    validate_doc_meta_ids(meta)
    return meta


def load_claim(cas: FileSystemCAS, artifact_id: str) -> Claim:
    payload = load_json_artifact(cas, artifact_id)
    claim = Claim.model_validate(payload)
    validate_claim_id(claim)
    return claim


def persist_claim_set(
    *,
    cas: FileSystemCAS,
    payload: dict,
    kind: str,
    schema_name: str,
    schema_version: str,
    inputs: list[tuple[str, str]] | None = None,
) -> str:
    input_refs: list[InputRef] = []
    for role, artifact_id in inputs or []:
        input_refs.append(
            InputRef(artifact_id=ArtifactID.model_validate(artifact_id), role=role)
        )
    ref = cas.put_json(
        payload,
        opts=PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
            inputs=input_refs or None,
        ),
    )
    return str(ref.artifact_id)


def manifest_artifact_ref(cas: FileSystemCAS, artifact_id: str) -> ArtifactRef:
    aid = ArtifactID.model_validate(artifact_id)
    manifest = cas.get_manifest(aid)
    return ArtifactRef(
        artifact_id=aid,
        kind=manifest.kind,
        media_type=manifest.media_type,
    )


def persist_claims_evidence_bundle(
    *,
    cas: FileSystemCAS,
    source_artifact_ids: list[str],
    transform_op: str,
    transform_details: dict[str, str | int | bool],
    schema_name: str,
    schema_version: str,
) -> str:
    unique_sources = sorted(set(source_artifact_ids))
    sources = [manifest_artifact_ref(cas, artifact_id) for artifact_id in unique_sources]
    bundle = build_evidence_bundle(
        sources=sources,
        transforms=[
            EvidenceStep(
                op=transform_op,
                details=transform_details,
            )
        ],
        notes=[],
    )
    evidence_ref = persist_evidence_bundle(
        cas,
        bundle,
        schema_name=schema_name,
        schema_version=schema_version,
    )
    return str(evidence_ref.artifact_id)


def write_claims_world_segment(
    *,
    facts: list[Fact],
    fact_log_root: Path,
    segment_name: str,
) -> FactSegmentManifest:
    manifest = write_world_fact_segment(
        facts,
        fact_log_root=fact_log_root,
        segment_name=segment_name,
    )
    append_world_segment_index(manifest, fact_log_root=fact_log_root)
    return manifest


def canonical_json_text(value: object) -> str:
    return to_canonical_bytes(value).decode("utf-8")


__all__ = [
    "canonical_json_text",
    "load_claim",
    "load_doc_meta",
    "load_json_artifact",
    "persist_claim_set",
    "persist_claims_evidence_bundle",
    "write_claims_world_segment",
]
