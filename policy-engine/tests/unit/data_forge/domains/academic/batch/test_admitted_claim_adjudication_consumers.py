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
    _input_items,
    materialize_claim_adjudication_result,
    produce_claim_adjudication_input,
)
from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.conflict_resolve import run_conflict_resolve
from polisyos.data_forge.domains.academic.batch.graph_builder import (
    build_graph,
    run_graph_load,
)
from polisyos.data_forge.domains.academic.knowledge.types import (
    WorkRecord,
)
from polisyos.ir.analytics.literature import (
    AdmittedClaimAdjudicationBatch,
    ArticleExtractionResult,
    CausalClaim,
    CausalDirection,
    ClaimExplicitness,
    ClaimType,
    DesignFamily,
    EvidenceSpan,
)
from polisyos.scientist.methods.autotune import (
    ChampionRegistry,
)

from ._claim_evidence import evidence_fixture, persist_batch


def _write_jsonl(path, rows) -> None:  # type: ignore[no-untyped-def]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _fixture_article() -> ArticleExtractionResult:
    return ArticleExtractionResult(
        openalex_id="W1",
        title="Policy trial",
        methodology="randomized trial",
        causal_claims=[
            CausalClaim(
                claim_id="c-1",
                source_basis="fulltext",
                claim_extraction_confidence=0.9,
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


def _current_subject() -> dict[str, object]:
    return _input_items([_fixture_article()], retracted_ids=set())[0].model_dump(mode="json")


def _receipt(
    config: AcademicBatchConfig,
    *,
    publishable: bool,
) -> tuple[FileSystemCAS, str, object]:
    article = _fixture_article()
    config.article_extraction_results_path.parent.mkdir(parents=True, exist_ok=True)
    config.article_extraction_results_path.write_text(
        article.model_dump_json() + "\n",
        encoding="utf-8",
    )
    store = FileSystemCAS(config.claim_adjudication_cas_root)
    raw_ref = produce_claim_adjudication_input(config, store=store)
    registry = ChampionRegistry(root=config.claim_adjudication_registry_root, store=store)
    evidence = evidence_fixture(
        store, registry, config.claim_adjudication_registry_root, raw_ref, positive=publishable
    )
    result_ref = persist_batch(evidence)
    materialize_claim_adjudication_result(
        config, result_ref, store=store, verifier=evidence.verifier
    )
    return store, str(result_ref.artifact_id), evidence.verifier


def _work_record() -> WorkRecord:
    from polisyos.data_forge.domains.academic.batch.article_extractor import _to_work_record

    return _to_work_record(
        result=_fixture_article(),
        raw_work={},
        topic_ids=[],
        topic_display_names=[],
        run_id="test",
        pass_name="fulltext",  # noqa: S106 - pipeline stage name, not a credential.
    )


def test_verified_receipt_drives_graph_and_conflict_consumers(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _, _, verifier = _receipt(config, publishable=True)
    admitted_rows = load_verified_claim_adjudication_rows(config, verifier=verifier)

    stats = build_graph(
        records=iter([_work_record()]),
        db_path=config.db_path,
        admitted_claim_adjudications=admitted_rows,
    )
    assert stats.claims == 1

    from polisyos.data_forge.domains.academic.batch._resolve_extract_transformers import (
        _to_claim_row,
    )

    article = _fixture_article()
    _write_jsonl(
        config.raw_claim_candidates_final_path,
        [_to_claim_row(article, article.causal_claims[0], topic_ids=[], topic_display_names=[])],
    )
    run_conflict_resolve(config, verifier=verifier)
    claim_set = json.loads(config.claim_sets_path.read_text(encoding="utf-8").splitlines()[0])
    assert claim_set["publishable_claims"] == 1


def test_constant_receipt_rejects_false_to_true_projection_flip_in_both_consumers(
    tmp_path,
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _, receipt_id, verifier = _receipt(config, publishable=False)
    rows = [
        json.loads(line)
        for line in config.claim_adjudications_path.read_text(encoding="utf-8").splitlines()
    ]
    assert rows[0]["publishable_edge"] is False
    rows[0]["publishable_edge"] = True
    _write_jsonl(config.claim_adjudications_path, rows)
    pointer_before = config.claim_adjudication_result_ref_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="projection differs from receipt"):
        run_conflict_resolve(config, verifier=verifier)
    with pytest.raises(ValueError, match="projection differs from receipt"):
        run_graph_load(config, verifier=verifier)

    pointer_after = config.claim_adjudication_result_ref_path.read_text(encoding="utf-8")
    assert pointer_after == pointer_before
    assert receipt_id in pointer_after


def test_invalid_replacement_receipt_cannot_erase_existing_admitted_pointer(
    tmp_path,
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    store, receipt_id, _verifier = _receipt(config, publishable=True)
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

    assert config.claim_adjudication_result_ref_path.read_text(encoding="utf-8") == pointer_before
    assert ArtifactRef.model_validate_json(pointer_before).artifact_id == ArtifactID(receipt_id)
