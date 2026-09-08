"""Actual rich producer transport through signed admission to graph/conflict."""

import json

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.data_forge.domains.academic.batch._resolve_extract_transformers import _to_claim_row
from polisyos.data_forge.domains.academic.batch.admitted_claim_adjudications import (
    load_verified_claim_adjudication_rows,
)
from polisyos.data_forge.domains.academic.batch.article_extractor import _to_work_record
from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
    materialize_claim_adjudication_result,
    produce_claim_adjudication_input,
)
from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.conflict_resolve import run_conflict_resolve
from polisyos.data_forge.domains.academic.batch.graph_builder import build_graph
from polisyos.scientist.methods.autotune import ChampionRegistry
from polisyos.scientist.methods.autotune.claim_adjudication_runtime import ClaimAdjudicationRuntime
from tests.unit.data_forge.domains.academic.batch._claim_evidence import evidence_fixture
from tests.unit.data_forge.domains.academic.batch.test_admitted_claim_adjudication_consumers import (
    _fixture_article,
    _write_jsonl,
)
from tests.unit.scientist.methods.autotune.test_claim_adjudication_runtime import _FakeClient


@pytest.mark.asyncio
async def test_rich_producer_subject_survives_admission_and_both_consumers(tmp_path):
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snapshot")
    article = _fixture_article()
    _write_jsonl(config.article_extraction_results_path, [article.model_dump(mode="json")])
    store = FileSystemCAS(config.claim_adjudication_cas_root)
    raw_ref = produce_claim_adjudication_input(config, store=store)
    registry = ChampionRegistry(root=config.claim_adjudication_registry_root, store=store)
    f = evidence_fixture(store, registry, config.claim_adjudication_registry_root, raw_ref)
    runtime = ClaimAdjudicationRuntime(
        store=store,
        registry=registry,
        verifier=f.verifier,
        evaluation_receipt_ref=f.evaluation_receipt_ref,
        execution_receipt_ref=f.execution_receipt_ref,
    )
    outcome = await runtime.adjudicate(
        raw_ref, client=_FakeClient(f.client_payload), model="fixture"
    )
    assert outcome.status == "completed", outcome
    materialize_claim_adjudication_result(
        config, outcome.result_ref, store=store, verifier=f.verifier
    )
    rows = load_verified_claim_adjudication_rows(config, store=store, verifier=f.verifier)
    record = _to_work_record(
        result=article,
        raw_work={},
        topic_ids=[],
        topic_display_names=[],
        run_id="test",
        pass_name=config.pass_name,
    )
    stats = build_graph(
        records=iter([record]), db_path=config.db_path, admitted_claim_adjudications=rows
    )
    assert stats.claims == 1
    _write_jsonl(
        config.raw_claim_candidates_final_path,
        [_to_claim_row(article, article.causal_claims[0], topic_ids=[], topic_display_names=[])],
    )
    run_conflict_resolve(config, verifier=f.verifier)
    claim_set = json.loads(config.claim_sets_path.read_text().splitlines()[0])
    assert claim_set["publishable_claims"] == 1
