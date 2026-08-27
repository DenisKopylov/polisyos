from __future__ import annotations

import json

import pytest

from polisyos.core.artifacts import ArtifactID, ArtifactRef
from polisyos.core.artifacts.manifest import InputRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon.canon_json import CanonSpec, from_canonical_bytes
from polisyos.data_forge.domains.academic.batch.admitted_claim_adjudications import (
    load_verified_claim_adjudication_rows,
)
from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
    materialize_claim_adjudication_result,
    produce_claim_adjudication_input,
)
from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.conflict_resolve import run_conflict_resolve
from polisyos.data_forge.domains.academic.batch.graph_builder import (
    build_graph,
    run_graph_load,
)
from polisyos.data_forge.domains.academic.knowledge.types import WorkRecord
from polisyos.ir.analytics.literature import (
    AdmittedClaimAdjudicationBatch,
    ArticleExtractionResult,
    CausalClaim,
    CausalCredibility,
    CausalDirection,
    ClaimAdjudicationResult,
    ClaimExplicitness,
    ClaimType,
    DesignFamily,
    EvidenceSpan,
    RiskOfBias,
    SourceBasis,
    SupportStatus,
)
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    persist_benchmark_evaluation,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.claim_adjudication import (
    ClaimAdjudicationSearchConfig,
)


def _write_jsonl(path, rows) -> None:  # type: ignore[no-untyped-def]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _receipt(
    config: AcademicBatchConfig,
    *,
    publishable: bool,
) -> tuple[FileSystemCAS, str]:
    article = ArticleExtractionResult(
        openalex_id="W1",
        title="Policy trial",
        methodology="randomized trial",
        causal_claims=[
            CausalClaim(
                claim_id="c-1",
                cause_variable="tax_rate",
                effect_variable="employment",
                direction=CausalDirection.NEGATIVE,
                claim_text="Higher tax rates reduce employment.",
                claim_type=ClaimType.CAUSAL_ASSERTION,
                claim_explicitness=ClaimExplicitness.EXPLICIT,
                design_family_hint=DesignFamily.RCT,
                supporting_spans=[EvidenceSpan(text="Employment fell.")],
                method_spans=[EvidenceSpan(text="Random assignment was used.")],
            )
        ],
        extraction_model="extractor-v1",
        extraction_timestamp="2026-08-27T00:00:00+00:00",
        extraction_confidence=0.9,
    )
    config.article_extraction_results_path.parent.mkdir(parents=True, exist_ok=True)
    config.article_extraction_results_path.write_text(
        article.model_dump_json() + "\n",
        encoding="utf-8",
    )
    store = FileSystemCAS(config.claim_adjudication_cas_root)
    raw_ref = produce_claim_adjudication_input(config, store=store)
    candidate_ref = persist_mutation_artifact(store, ClaimAdjudicationSearchConfig(passes=1))
    evaluation_ref = persist_benchmark_evaluation(
        store,
        BenchmarkEvaluation(
            loop_id="claim_adjudication",
            suite_id="claim_gold",
            candidate_ref=candidate_ref,
            promotable=True,
        ),
    )
    result = ClaimAdjudicationResult(
        claim_id="c-1",
        openalex_id="W1",
        cause_variable="tax_rate",
        effect_variable="employment",
        source_basis=SourceBasis.FULLTEXT,
        paper_asserts_causality_score=0.9,
        claim_type=ClaimType.CAUSAL_ASSERTION,
        design_family=DesignFamily.RCT,
        causal_credibility=CausalCredibility.STRONG,
        risk_of_bias=RiskOfBias.LOW,
        support_status=SupportStatus.SUPPORTED,
        claim_validity_score=0.95,
        adjudication_confidence=0.95,
        publishable_edge=publishable,
    )
    batch = AdmittedClaimAdjudicationBatch(
        raw_input_ref=str(raw_ref.artifact_id),
        candidate_ref=str(candidate_ref.artifact_id),
        evaluation_ref=str(evaluation_ref.artifact_id),
        champion_pointer_sha256="a" * 64,
        input_claim_ids=["c-1"],
        results=[result],
    )
    result_ref = store.put_json(
        batch,
        ArtifactWriteOptions(
            kind="scientist.claim_adjudication.admitted_batch",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.analytics.literature.AdmittedClaimAdjudicationBatch",
                version="1.0",
            ),
            producer=ProducerInfo(
                component="polisyos.scientist.methods.autotune.claim_adjudication_runtime",
                version="1.0",
            ),
            inputs=[
                InputRef(artifact_id=raw_ref.artifact_id, role="raw_input"),
                InputRef(artifact_id=candidate_ref.artifact_id, role="candidate"),
                InputRef(artifact_id=evaluation_ref.artifact_id, role="evaluation"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    materialize_claim_adjudication_result(config, result_ref, store=store)
    return store, str(result_ref.artifact_id)


def _work_record() -> WorkRecord:
    return WorkRecord(
        id="W1",
        title="Policy trial",
        abstract="effects of tax policy",
        year=2021,
        cited_by_count=30,
        study_design="rct",
        trust_score=0.7,
        causal_claims=[
            {
                "claim_id": "c-1",
                "cause": "tax_rate",
                "effect": "employment",
                "direction": "negative",
                "claim_text": "Higher tax rates reduce employment.",
                "source_basis": "fulltext",
                "claim_extraction_confidence": 0.82,
                "publish_to_graph": False,
            }
        ],
        context_profile={"context_id": "US"},
    )


def test_verified_receipt_drives_graph_and_conflict_consumers(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _receipt(config, publishable=True)
    admitted_rows = load_verified_claim_adjudication_rows(config)

    stats = build_graph(
        records=iter([_work_record()]),
        db_path=config.db_path,
        admitted_claim_adjudications=admitted_rows,
    )
    assert stats.claims == 1

    _write_jsonl(
        config.raw_claim_candidates_final_path,
        [
            {
                "claim_id": "c-1",
                "work_id": "W1",
                "cause_text": "tax_rate",
                "effect_text": "employment",
                "direction": "negative",
                "publish_to_graph": False,
            }
        ],
    )
    run_conflict_resolve(config)
    claim_set = json.loads(config.claim_sets_path.read_text(encoding="utf-8").splitlines()[0])
    assert claim_set["publishable_claims"] == 1


def test_constant_receipt_rejects_false_to_true_projection_flip_in_both_consumers(
    tmp_path,
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _, receipt_id = _receipt(config, publishable=False)
    rows = [
        json.loads(line)
        for line in config.claim_adjudications_path.read_text(encoding="utf-8").splitlines()
    ]
    assert rows[0]["publishable_edge"] is False
    rows[0]["publishable_edge"] = True
    _write_jsonl(config.claim_adjudications_path, rows)
    pointer_before = config.claim_adjudication_result_ref_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="projection differs from receipt"):
        run_conflict_resolve(config)
    with pytest.raises(ValueError, match="projection differs from receipt"):
        run_graph_load(config)

    pointer_after = config.claim_adjudication_result_ref_path.read_text(encoding="utf-8")
    assert pointer_after == pointer_before
    assert receipt_id in pointer_after


def test_invalid_replacement_receipt_cannot_erase_existing_admitted_pointer(
    tmp_path,
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    store, receipt_id = _receipt(config, publishable=True)
    pointer_before = config.claim_adjudication_result_ref_path.read_text(encoding="utf-8")
    batch = AdmittedClaimAdjudicationBatch.model_validate(
        from_canonical_bytes(store.get_bytes(ArtifactID(receipt_id)))
    )
    invalid_ref = store.put_json(
        batch.model_copy(update={"champion_pointer_sha256": "b" * 64}),
        ArtifactWriteOptions(
            kind="scientist.claim_adjudication.admitted_batch",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.analytics.literature.AdmittedClaimAdjudicationBatch",
                version="1.0",
            ),
            producer=ProducerInfo(
                component="polisyos.scientist.methods.autotune.claim_adjudication_runtime",
                version="1.0",
            ),
            inputs=[
                InputRef(artifact_id=ArtifactID(batch.raw_input_ref), role="raw_input"),
                InputRef(artifact_id=ArtifactID(batch.candidate_ref), role="candidate"),
                InputRef(artifact_id=ArtifactID(batch.candidate_ref), role="candidate"),
                InputRef(artifact_id=ArtifactID(batch.evaluation_ref), role="evaluation"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    with pytest.raises(ValueError, match="duplicate roles"):
        materialize_claim_adjudication_result(config, invalid_ref, store=store)

    assert config.claim_adjudication_result_ref_path.read_text(
        encoding="utf-8"
    ) == pointer_before
    assert ArtifactRef.model_validate_json(pointer_before).artifact_id == ArtifactID(receipt_id)
