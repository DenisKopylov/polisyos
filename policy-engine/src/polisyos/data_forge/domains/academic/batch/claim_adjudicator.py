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
    ArtifactRef,
    ArtifactWriteOptions,
    FileSystemCAS,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.canon import CanonSpec
from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
    ClaimAdjudicationVerifier,
    require_selected_artifact_ref,
    selected_artifact_ref_for_input,
)
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

    from polisyos.core.artifacts.protocol import CoreJSONArtifactStore
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
    ref = store.put_bytes(
        data,
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/x-ndjson",
            schema=SchemaInfo(name=schema_name, version="1.0"),
            producer=ProducerInfo(component=_INPUT_PRODUCER, version="1.0"),
        ),
        return_selected_profile=True,
    )
    return require_selected_artifact_ref(ref, field=kind)


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
            directions[(result.openalex_id, claim.cause_variable, claim.effect_variable)].add(
                claim.direction.value
            )

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


def _strict_selected_lineage(
    store: CoreJSONArtifactStore,
    inputs: tuple[InputRef, ...] | list[InputRef],
) -> dict[str, ArtifactRef]:
    """Resolve each unique result edge by the profile selected at production."""
    _strict_lineage(inputs)
    return {item.role: selected_artifact_ref_for_input(store, item) for item in inputs}


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
    inputs = [input_ref_from_artifact_ref(source_ref, role="extraction_source")]
    if retraction_ref is not None:
        inputs.append(input_ref_from_artifact_ref(retraction_ref, role="retraction_source"))
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
        return_selected_profile=True,
    )
    require_selected_artifact_ref(input_ref, field="raw_input")
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


def validate_claim_adjudication_input_batch(
    store: CoreJSONArtifactStore,
    ref: ArtifactRef,
) -> ClaimAdjudicationInputBatch:
    """Load one raw batch through its exact selected source lineage."""
    from polisyos.core.artifacts import load_core_json_artifact

    require_selected_artifact_ref(ref, field="raw_input")
    manifest = store.get_manifest(ref)
    if manifest.kind != _INPUT_KIND:
        raise ValueError(f"unexpected claim-adjudication input kind: {manifest.kind}")
    if manifest.media_type != "application/json":
        raise ValueError("claim-adjudication input media type mismatch")
    if (
        manifest.artifact_schema is None
        or manifest.artifact_schema.name != _INPUT_SCHEMA
        or manifest.artifact_schema.version != "1.0"
    ):
        raise ValueError("claim-adjudication input schema mismatch")
    if (
        manifest.producer is None
        or str(manifest.producer.component) != _INPUT_PRODUCER
        or manifest.producer.version != "1.0"
    ):
        raise ValueError("claim-adjudication input producer mismatch")
    batch = ClaimAdjudicationInputBatch.model_validate(load_core_json_artifact(store, ref))
    selected_lineage = _strict_selected_lineage(store, manifest.inputs)
    expected_ids = {"extraction_source": batch.source_artifact_ref}
    if batch.retraction_artifact_ref is not None:
        expected_ids["retraction_source"] = batch.retraction_artifact_ref
    if {
        role: str(source_ref.artifact_id) for role, source_ref in selected_lineage.items()
    } != expected_ids:
        raise ValueError("claim-adjudication input lineage mismatch")
    expected_sources = {
        "extraction_source": (
            _SOURCE_KIND,
            "application/x-ndjson",
            "polisyos.ir.analytics.literature.ArticleExtractionResult.ndjson",
            "1.0",
        ),
        "retraction_source": (
            _RETRACTION_KIND,
            "application/x-ndjson",
            "polisyos.data_forge.academic.MergedRecord.ndjson",
            "1.0",
        ),
    }
    for role, source_ref in selected_lineage.items():
        source_manifest = store.get_manifest(source_ref)
        expected_kind, expected_media_type, expected_schema, expected_version = expected_sources[
            role
        ]
        if (
            source_manifest.kind != expected_kind
            or source_manifest.media_type != expected_media_type
            or source_manifest.artifact_schema is None
            or source_manifest.artifact_schema.name != expected_schema
            or source_manifest.artifact_schema.version != expected_version
            or source_manifest.producer is None
            or str(source_manifest.producer.component) != _INPUT_PRODUCER
            or source_manifest.producer.version != "1.0"
        ):
            raise ValueError(f"claim-adjudication input source profile mismatch:{role}")
    return batch


def load_admitted_claim_adjudication_batch(
    config: AcademicBatchConfig,
    *,
    result_ref: ArtifactRef | None = None,
    store: FileSystemCAS | None = None,
    verifier: ClaimAdjudicationVerifier | None = None,
) -> tuple[AdmittedClaimAdjudicationBatch, ArtifactRef]:
    """Resolve and verify the authority receipt from its exact selected lineage."""
    from polisyos.core.artifacts import load_core_json_artifact

    active_store = _active_store(config, store)
    resolved_ref = result_ref or _read_ref(config.claim_adjudication_result_ref_path)
    if resolved_ref.manifest_profile_sha256 is None:
        raise ValueError("claim_adjudication_result_profile_missing")
    manifest = active_store.get_manifest(resolved_ref)
    if manifest.kind != _RESULT_KIND:
        raise ValueError(f"unexpected claim-adjudication result kind: {manifest.kind}")
    if manifest.artifact_schema is None or manifest.artifact_schema.name != _RESULT_SCHEMA:
        raise ValueError("claim-adjudication result schema mismatch")
    if manifest.producer is None or str(manifest.producer.component) != _RESULT_PRODUCER:
        raise ValueError("claim-adjudication result producer mismatch")
    batch = AdmittedClaimAdjudicationBatch.model_validate(
        load_core_json_artifact(active_store, resolved_ref)
    )
    actual_inputs = _strict_selected_lineage(active_store, manifest.inputs)
    expected_roles = {
        "raw_input",
        "candidate",
        "evaluation",
        "evaluation_receipt",
        "execution_receipt",
        "benchmark_suite",
    }
    if set(actual_inputs) != expected_roles:
        raise ValueError("claim_adjudication_independent_verification_receipts_missing")
    if (
        str(actual_inputs["raw_input"].artifact_id) != batch.raw_input_ref
        or str(actual_inputs["candidate"].artifact_id) != batch.candidate_ref
        or str(actual_inputs["evaluation"].artifact_id) != batch.evaluation_ref
    ):
        raise ValueError("claim-adjudication result lineage mismatch")
    input_batch = validate_claim_adjudication_input_batch(active_store, actual_inputs["raw_input"])
    if batch.input_claim_ids != [item.claim_id for item in input_batch.items]:
        raise ValueError("claim-adjudication result denominator mismatch")
    active_verifier = verifier or ClaimAdjudicationVerifier(
        store=active_store,
        registry_root=config.claim_adjudication_registry_root,
    )
    if type(active_verifier) is not ClaimAdjudicationVerifier:
        raise ValueError("claim_adjudication_verifier_type_invalid")
    active_verifier.verify_batch(
        batch,
        evaluation_receipt_ref=actual_inputs["evaluation_receipt"],
        execution_receipt_ref=actual_inputs["execution_receipt"],
        raw_input_ref=actual_inputs["raw_input"],
        candidate_ref=actual_inputs["candidate"],
        evaluation_ref=actual_inputs["evaluation"],
        benchmark_suite_ref=actual_inputs["benchmark_suite"],
    )
    return batch, resolved_ref


def materialize_claim_adjudication_result(
    config: AcademicBatchConfig,
    result_ref: ArtifactRef,
    *,
    store: FileSystemCAS | None = None,
    verifier: ClaimAdjudicationVerifier | None = None,
) -> dict[str, int | float]:
    """Materialize a verified Scientist receipt for compatibility consumers."""
    started_at = datetime.now(UTC).isoformat()
    active_store = _active_store(config, store)
    batch, verified_ref = load_admitted_claim_adjudication_batch(
        config,
        result_ref=result_ref,
        store=active_store,
        verifier=verifier,
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
    published_count = sum(result.publishable_edge for result in batch.results)
    report = {
        "schema_version": "1.0",
        "authority_source": receipt_id,
        "rule_version": batch.rule_version,
        "claims": len(batch.results),
        "published": published_count,
        "authoritative_for": list(batch.authoritative_for),
        "may_not_use_for": list(batch.may_not_use_for),
    }
    atomic_write_json(config.claim_consensus_report_path, report)
    metrics: dict[str, int | float] = {
        "claims": len(batch.results),
        "published": published_count,
    }
    manifest_metrics: dict[str, object] = {}
    manifest_metrics.update(metrics)
    write_stage_manifest(
        manifest_path=config.manifests_dir / "claim_adjudicate.json",
        stage="claim_adjudicate",
        status="ok",
        metrics=manifest_metrics,
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
