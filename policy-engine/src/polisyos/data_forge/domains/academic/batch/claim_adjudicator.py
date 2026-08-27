"""Authority-neutral transport for academic claim adjudication.

Data Forge freezes extraction bytes and materializes a verified Scientist
receipt. It deliberately does not decide whether a claim is publishable.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    ArtifactWriteOptions,
    FileSystemCAS,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.data_forge.domains.academic.batch.claim_ids import stable_claim_id
from polisyos.data_forge.kernel.io import atomic_write_json, atomic_write_text
from polisyos.data_forge.kernel.pipeline.manifests import write_stage_manifest
from polisyos.ir.analytics.literature import (
    AdmittedClaimAdjudicationBatch,
    ArticleExtractionResult,
    CausalClaim,
    ClaimAdjudicationInputBatch,
    ClaimAdjudicationInputItem,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig

_INPUT_KIND = "data_forge.academic.claim_adjudication.input_batch"
_INPUT_SCHEMA = "polisyos.ir.analytics.literature.ClaimAdjudicationInputBatch"
_SOURCE_KIND = "data_forge.academic.claim_adjudication.extraction_source"
_RETRACTION_KIND = "data_forge.academic.claim_adjudication.retraction_source"
_RESULT_KIND = "scientist.claim_adjudication.admitted_batch"
_RESULT_SCHEMA = "polisyos.ir.analytics.literature.AdmittedClaimAdjudicationBatch"
_INPUT_PRODUCER = "polisyos.data_forge.domains.academic.batch.claim_adjudicator"
_RESULT_PRODUCER = "polisyos.scientist.methods.autotune.claim_adjudication_runtime"


def _active_store(
    config: AcademicBatchConfig,
    store: FileSystemCAS | None,
) -> FileSystemCAS:
    return store or FileSystemCAS(config.claim_adjudication_cas_root)


def _source_path(config: AcademicBatchConfig) -> Path:
    if config.resolve_extract_final_results_path.exists():
        return config.resolve_extract_final_results_path
    return config.article_extraction_results_path


def _put_bytes(
    store: FileSystemCAS,
    data: bytes,
    *,
    kind: str,
    schema_name: str,
) -> ArtifactRef:
    return store.put_bytes(
        data,
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/x-ndjson",
            schema=SchemaInfo(name=schema_name, version="1.0"),
            producer=ProducerInfo(component=_INPUT_PRODUCER, version="1.0"),
        ),
    )


def _parse_article_results(data: bytes) -> list[ArticleExtractionResult]:
    rows: list[ArticleExtractionResult] = []
    for line_number, raw_line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            rows.append(ArticleExtractionResult.model_validate_json(raw_line))
        except Exception as exc:
            raise ValueError(f"invalid article extraction at line {line_number}") from exc
    return rows


def _parse_retracted_ids(data: bytes) -> set[str]:
    retracted: set[str] = set()
    for line_number, raw_line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid merged record at line {line_number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"merged record at line {line_number} must be an object")
        metadata = row.get("metadata")
        metadata_retracted = isinstance(metadata, dict) and bool(metadata.get("is_retracted"))
        if bool(row.get("is_retracted")) or metadata_retracted:
            work_id = str(row.get("id") or row.get("openalex_id") or "").strip()
            if work_id:
                retracted.add(work_id)
    return retracted


def _claim_id(result: ArticleExtractionResult, claim: CausalClaim) -> str:
    return claim.claim_id or stable_claim_id(
        work_id=result.openalex_id,
        cause=claim.cause_variable,
        effect=claim.effect_variable,
        claim_text=claim.claim_text,
        direction=claim.direction.value,
        supporting_span_ids=tuple(claim.supporting_span_ids),
    )


def _input_items(
    rows: list[ArticleExtractionResult],
    *,
    retracted_ids: set[str],
) -> list[ClaimAdjudicationInputItem]:
    claims: list[tuple[ArticleExtractionResult, CausalClaim, str]] = []
    directions: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for result in rows:
        if result.openalex_id in retracted_ids:
            continue
        for claim in result.causal_claims:
            claim_id = _claim_id(result, claim)
            claims.append((result, claim, claim_id))
            directions[
                (result.openalex_id, claim.cause_variable, claim.effect_variable)
            ].add(claim.direction.value)

    items: list[ClaimAdjudicationInputItem] = []
    for result, claim, claim_id in claims:
        direction_set = directions[
            (result.openalex_id, claim.cause_variable, claim.effect_variable)
        ]
        items.append(
            ClaimAdjudicationInputItem(
                claim_id=claim_id,
                openalex_id=result.openalex_id,
                title=result.title,
                methodology=result.methodology,
                methodology_enum=result.methodology_enum,
                source_basis=claim.source_basis,
                text_quality=result.text_quality,
                claim_text=claim.claim_text,
                cause_variable=claim.cause_variable,
                effect_variable=claim.effect_variable,
                direction=claim.direction,
                claim_type_hint=claim.claim_type,
                claim_explicitness=claim.claim_explicitness,
                design_family_hint=claim.design_family_hint,
                effect_size=claim.effect_size,
                scope_conditions=claim.scope_conditions,
                supporting_spans=claim.supporting_spans,
                method_spans=claim.method_spans,
                extraction_model=result.extraction_model,
                extraction_timestamp=result.extraction_timestamp,
                extraction_confidence=float(
                    claim.claim_extraction_confidence
                    if claim.claim_extraction_confidence is not None
                    else result.extraction_confidence
                ),
                intra_paper_contradiction=(
                    "positive" in direction_set and "negative" in direction_set
                ),
            )
        )
    return items


def _write_ref(path: Path, ref: ArtifactRef) -> None:
    atomic_write_json(path, ref.model_dump(mode="json"))


def _read_ref(path: Path) -> ArtifactRef:
    if not path.exists():
        raise FileNotFoundError(f"missing claim-adjudication receipt pointer: {path}")
    return ArtifactRef.model_validate_json(path.read_text(encoding="utf-8"))


def _strict_lineage(inputs: tuple[InputRef, ...] | list[InputRef]) -> dict[str, str]:
    """Return lineage only when every role occurs exactly once."""
    lineage = {item.role: str(item.artifact_id) for item in inputs}
    if len(lineage) != len(inputs):
        raise ValueError("claim-adjudication lineage contains duplicate roles")
    return lineage


def produce_claim_adjudication_input(
    config: AcademicBatchConfig,
    *,
    store: FileSystemCAS | None = None,
) -> ArtifactRef:
    """Freeze producer bytes and persist an authority-neutral input batch."""
    started_at = datetime.now(UTC).isoformat()
    active_store = _active_store(config, store)
    source_path = _source_path(config)
    source_bytes = source_path.read_bytes() if source_path.exists() else b""
    source_ref = _put_bytes(
        active_store,
        source_bytes,
        kind=_SOURCE_KIND,
        schema_name="polisyos.ir.analytics.literature.ArticleExtractionResult.ndjson",
    )

    retraction_ref: ArtifactRef | None = None
    retraction_bytes = b""
    if config.merged_records_path.exists():
        retraction_bytes = config.merged_records_path.read_bytes()
        retraction_ref = _put_bytes(
            active_store,
            retraction_bytes,
            kind=_RETRACTION_KIND,
            schema_name="polisyos.data_forge.academic.MergedRecord.ndjson",
        )

    input_batch = ClaimAdjudicationInputBatch(
        source_artifact_ref=str(source_ref.artifact_id),
        retraction_artifact_ref=(
            str(retraction_ref.artifact_id) if retraction_ref is not None else None
        ),
        items=_input_items(
            _parse_article_results(source_bytes),
            retracted_ids=_parse_retracted_ids(retraction_bytes),
        ),
    )
    inputs = [InputRef(artifact_id=source_ref.artifact_id, role="extraction_source")]
    if retraction_ref is not None:
        inputs.append(InputRef(artifact_id=retraction_ref.artifact_id, role="retraction_source"))
    input_ref = active_store.put_json(
        input_batch,
        ArtifactWriteOptions(
            kind=_INPUT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_INPUT_SCHEMA, version=input_batch.schema_version),
            producer=ProducerInfo(component=_INPUT_PRODUCER, version="1.0"),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    _write_ref(config.claim_adjudication_input_ref_path, input_ref)
    write_stage_manifest(
        manifest_path=config.manifests_dir / "claim_adjudicate.json",
        stage="claim_adjudicate",
        status="input_ready",
        metrics={"claims": len(input_batch.items)},
        artifacts=[config.claim_adjudication_input_ref_path],
        started_at=started_at,
    )
    return input_ref


def _validate_input_batch(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> ClaimAdjudicationInputBatch:
    manifest = store.get_manifest(ref.artifact_id)
    if manifest.kind != _INPUT_KIND:
        raise ValueError(f"unexpected claim-adjudication input kind: {manifest.kind}")
    if manifest.artifact_schema is None or manifest.artifact_schema.name != _INPUT_SCHEMA:
        raise ValueError("claim-adjudication input schema mismatch")
    if manifest.producer is None or str(manifest.producer.component) != _INPUT_PRODUCER:
        raise ValueError("claim-adjudication input producer mismatch")
    batch = ClaimAdjudicationInputBatch.model_validate(
        from_canonical_bytes(store.get_bytes(ref.artifact_id))
    )
    expected_inputs = {"extraction_source": batch.source_artifact_ref}
    if batch.retraction_artifact_ref is not None:
        expected_inputs["retraction_source"] = batch.retraction_artifact_ref
    if _strict_lineage(manifest.inputs) != expected_inputs:
        raise ValueError("claim-adjudication input lineage mismatch")
    return batch


def load_admitted_claim_adjudication_batch(
    config: AcademicBatchConfig,
    *,
    result_ref: ArtifactRef | None = None,
    store: FileSystemCAS | None = None,
) -> tuple[AdmittedClaimAdjudicationBatch, ArtifactRef]:
    """Resolve and verify the sole authority-bearing adjudication receipt."""
    active_store = _active_store(config, store)
    resolved_ref = result_ref or _read_ref(config.claim_adjudication_result_ref_path)
    manifest = active_store.get_manifest(resolved_ref.artifact_id)
    if manifest.kind != _RESULT_KIND:
        raise ValueError(f"unexpected claim-adjudication result kind: {manifest.kind}")
    if manifest.artifact_schema is None or manifest.artifact_schema.name != _RESULT_SCHEMA:
        raise ValueError("claim-adjudication result schema mismatch")
    if manifest.producer is None or str(manifest.producer.component) != _RESULT_PRODUCER:
        raise ValueError("claim-adjudication result producer mismatch")
    batch = AdmittedClaimAdjudicationBatch.model_validate(
        from_canonical_bytes(active_store.get_bytes(resolved_ref.artifact_id))
    )
    expected_inputs = {
        "raw_input": batch.raw_input_ref,
        "candidate": batch.candidate_ref,
        "evaluation": batch.evaluation_ref,
    }
    actual_inputs = _strict_lineage(manifest.inputs)
    if actual_inputs != expected_inputs:
        raise ValueError("claim-adjudication result lineage mismatch")
    input_ref = ArtifactRef(
        artifact_id=ArtifactID(batch.raw_input_ref),
        kind=_INPUT_KIND,
        media_type="application/json",
    )
    input_batch = _validate_input_batch(active_store, input_ref)
    if batch.input_claim_ids != [item.claim_id for item in input_batch.items]:
        raise ValueError("claim-adjudication result denominator mismatch")
    return batch, resolved_ref


def materialize_claim_adjudication_result(
    config: AcademicBatchConfig,
    result_ref: ArtifactRef,
    *,
    store: FileSystemCAS | None = None,
) -> dict[str, int | float]:
    """Materialize a verified Scientist receipt for compatibility consumers."""
    started_at = datetime.now(UTC).isoformat()
    active_store = _active_store(config, store)
    batch, verified_ref = load_admitted_claim_adjudication_batch(
        config,
        result_ref=result_ref,
        store=active_store,
    )
    _write_ref(config.claim_adjudication_result_ref_path, verified_ref)

    receipt_id = str(verified_ref.artifact_id)
    lines = [
        json.dumps(
            {
                **result.model_dump(mode="json"),
                "adjudication_receipt_id": receipt_id,
                "authority_rule_version": batch.rule_version,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        for result in batch.results
    ]
    atomic_write_text(
        config.claim_adjudications_path,
        "".join(f"{line}\n" for line in lines),
    )
    report = {
        "schema_version": "1.0",
        "authority_source": receipt_id,
        "rule_version": batch.rule_version,
        "claims": len(batch.results),
        "published": sum(result.publishable_edge for result in batch.results),
        "authoritative_for": list(batch.authoritative_for),
        "may_not_use_for": list(batch.may_not_use_for),
    }
    atomic_write_json(config.claim_consensus_report_path, report)
    metrics: dict[str, int | float] = {
        "claims": len(batch.results),
        "published": int(report["published"]),
    }
    write_stage_manifest(
        manifest_path=config.manifests_dir / "claim_adjudicate.json",
        stage="claim_adjudicate",
        status="ok",
        metrics=metrics,
        artifacts=[
            config.claim_adjudication_input_ref_path,
            config.claim_adjudication_result_ref_path,
            config.claim_adjudications_path,
            config.claim_consensus_report_path,
        ],
        started_at=started_at,
    )
    return metrics


__all__ = [
    "load_admitted_claim_adjudication_batch",
    "materialize_claim_adjudication_result",
    "produce_claim_adjudication_input",
]
