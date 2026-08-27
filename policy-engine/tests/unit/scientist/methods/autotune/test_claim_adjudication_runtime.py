from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
    produce_claim_adjudication_input,
)
from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.ir.analytics.literature import (
    AdmittedClaimAdjudicationBatch,
    ArticleExtractionResult,
    CausalClaim,
    CausalDirection,
    ClaimExplicitness,
    ClaimType,
    DesignFamily,
    EvidenceSpan,
    EvidenceStrength,
    SourceBasis,
    TextQuality,
)
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    ChampionRegistry,
    persist_benchmark_evaluation,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.claim_adjudication import (
    ClaimAdjudicationSearchConfig,
    default_claim_adjudication_promotion_policy,
)
from polisyos.scientist.methods.autotune.claim_adjudication_cli import (
    run_claim_adjudication_command,
)
from polisyos.scientist.methods.autotune.claim_adjudication_runtime import (
    ClaimAdjudicationRuntime,
    assert_claim_adjudication_authority_purpose,
)


class _FakeClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0

    async def chat_json(self, **_: object) -> object:
        self.calls += 1
        return SimpleNamespace(http_status=200, parsed=dict(self.payload))


def _article(*, source_basis: SourceBasis = SourceBasis.FULLTEXT) -> ArticleExtractionResult:
    claim = CausalClaim(
        claim_id="claim-1",
        cause_variable="policy treatment",
        effect_variable="school attendance",
        direction=CausalDirection.POSITIVE,
        claim_text="The policy increased school attendance.",
        claim_type=ClaimType.CAUSAL_ASSERTION,
        claim_explicitness=ClaimExplicitness.EXPLICIT,
        design_family_hint=DesignFamily.RCT,
        evidence_strength=EvidenceStrength.RCT,
        source_basis=source_basis,
        supporting_spans=[EvidenceSpan(text="Attendance increased by eight percent.")],
        method_spans=[EvidenceSpan(text="Participants were randomly assigned.")],
        claim_extraction_confidence=0.95,
        publish_to_graph=True,
        strong_design_evidence=True,
    )
    return ArticleExtractionResult(
        openalex_id="W1",
        title="A randomized policy trial",
        methodology="randomized controlled trial",
        methodology_enum=EvidenceStrength.RCT,
        source_basis=source_basis,
        text_quality=(
            TextQuality.ABSTRACT_ONLY
            if source_basis == SourceBasis.ABSTRACT_ONLY
            else TextQuality.STRUCTURED_FULLTEXT
        ),
        causal_claims=[claim],
        extraction_model="extractor-v1",
        extraction_timestamp="2026-08-27T00:00:00+00:00",
        extraction_confidence=0.95,
    )


def _input_ref(
    tmp_path,
    store: FileSystemCAS,
    *,
    source_basis: SourceBasis = SourceBasis.FULLTEXT,
):
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snapshot")
    config.article_extraction_results_path.parent.mkdir(parents=True, exist_ok=True)
    config.article_extraction_results_path.write_text(
        _article(source_basis=source_basis).model_dump_json() + "\n",
        encoding="utf-8",
    )
    return config, produce_claim_adjudication_input(config, store=store)


def _promote_champion(
    store: FileSystemCAS,
    registry: ChampionRegistry,
) -> tuple[object, object]:
    candidate_ref = persist_mutation_artifact(
        store,
        ClaimAdjudicationSearchConfig(passes=1),
    )
    policy = default_claim_adjudication_promotion_policy()
    evaluation = BenchmarkEvaluation(
        loop_id="claim_adjudication",
        suite_id="claim_gold",
        suite_version="1.0",
        candidate_ref=candidate_ref,
        holdout_metrics={"precision_publishable": 1.0},
        sample_counts={BenchmarkSplit.HOLDOUT.value: 5},
        guardrails=dict.fromkeys(policy.required_guardrails, True),
        promotable=True,
        runtime_split_type=BenchmarkSplit.HOLDOUT,
    )
    evaluation_ref = persist_benchmark_evaluation(store, evaluation)
    decision = registry.consider_promotion(
        "claim_adjudication",
        candidate_ref,
        evaluation_ref,
        policy,
    )
    assert decision.promoted is True
    return candidate_ref, evaluation_ref


def _positive_candidate() -> dict[str, object]:
    return {
        "paper_asserts_causality_score": 0.95,
        "claim_type": "causal_assertion",
        "design_family": "rct",
        "causal_credibility": "strong",
        "risk_of_bias": "low",
        "support_status": "supported",
        "claim_validity_score": 0.95,
        "adjudication_confidence": 0.95,
        "publishable_edge": True,
        "adjudication_notes": "candidate assessment",
    }


def test_raw_input_excludes_producer_publish_authority_and_freezes_bytes(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    config, raw_ref = _input_ref(tmp_path, store)
    config.article_extraction_results_path.write_text("", encoding="utf-8")

    payload = store.get_bytes(raw_ref.artifact_id).decode("utf-8")

    assert "publishable_edge" not in payload
    assert "publish_to_graph" not in payload
    assert AdmittedClaimAdjudicationBatch.__name__ not in payload
    assert "claim-1" in payload


@pytest.mark.asyncio
async def test_missing_champion_blocks_without_emitting_result(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    _, raw_ref = _input_ref(tmp_path, store)

    outcome = await ClaimAdjudicationRuntime(store=store, registry=registry).adjudicate(
        raw_ref,
        client=_FakeClient(_positive_candidate()),
        model="fake-model",
    )

    assert outcome.status == "blocked"
    assert outcome.result_ref is None
    assert outcome.blockers == ("claim_adjudication_champion_missing",)


@pytest.mark.asyncio
async def test_promoted_champion_executes_and_publishes_strong_fulltext(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    _, raw_ref = _input_ref(tmp_path, store)
    _promote_champion(store, registry)

    outcome = await ClaimAdjudicationRuntime(store=store, registry=registry).adjudicate(
        raw_ref,
        client=_FakeClient(_positive_candidate()),
        model="fake-model",
    )

    assert outcome.status == "completed"
    assert outcome.result_ref is not None
    assert outcome.published_claims == 1
    admitted = AdmittedClaimAdjudicationBatch.model_validate(
        from_canonical_bytes(store.get_bytes(outcome.result_ref.artifact_id))
    )
    assert admitted.results[0].publishable_edge is True
    assert admitted.admission_predicate == "independently_reconciled"


@pytest.mark.asyncio
async def test_model_positive_cannot_publish_abstract_only_claim(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    _, raw_ref = _input_ref(tmp_path, store, source_basis=SourceBasis.ABSTRACT_ONLY)
    _promote_champion(store, registry)

    outcome = await ClaimAdjudicationRuntime(store=store, registry=registry).adjudicate(
        raw_ref,
        client=_FakeClient(_positive_candidate()),
        model="fake-model",
    )

    assert outcome.status == "completed"
    assert outcome.result_ref is not None
    admitted = AdmittedClaimAdjudicationBatch.model_validate(
        from_canonical_bytes(store.get_bytes(outcome.result_ref.artifact_id))
    )
    assert admitted.results[0].publishable_edge is False


@pytest.mark.asyncio
async def test_evaluation_candidate_mismatch_blocks_admission(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    _, raw_ref = _input_ref(tmp_path, store)
    _promote_champion(store, registry)
    pointer = registry.get("claim_adjudication")
    assert pointer is not None
    replacement = persist_mutation_artifact(
        store,
        ClaimAdjudicationSearchConfig(passes=2),
    )
    registry.write_pointer(
        "claim_adjudication",
        pointer.model_copy(update={"candidate_ref": replacement}),
    )

    outcome = await ClaimAdjudicationRuntime(store=store, registry=registry).adjudicate(
        raw_ref,
        client=_FakeClient(_positive_candidate()),
        model="fake-model",
    )

    assert outcome.status == "blocked"
    assert "mismatch" in outcome.blockers[0]


@pytest.mark.asyncio
async def test_required_guardrail_false_blocks_admission(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    _, raw_ref = _input_ref(tmp_path, store)
    _, evaluation_ref = _promote_champion(store, registry)
    pointer = registry.get("claim_adjudication")
    assert pointer is not None
    evaluation = BenchmarkEvaluation.model_validate(
        from_canonical_bytes(store.get_bytes(evaluation_ref.artifact_id))
    )
    guardrails = dict(evaluation.guardrails)
    guardrails["abstract_only_publishable_fp_rate_zero"] = False
    rejected_ref = persist_benchmark_evaluation(
        store,
        evaluation.model_copy(update={"guardrails": guardrails}),
    )
    registry.write_pointer(
        "claim_adjudication",
        pointer.model_copy(update={"evaluation_ref": rejected_ref}),
    )

    outcome = await ClaimAdjudicationRuntime(store=store, registry=registry).adjudicate(
        raw_ref,
        client=_FakeClient(_positive_candidate()),
        model="fake-model",
    )

    assert outcome.status == "blocked"
    assert outcome.blockers == (
        "claim_adjudication_guardrail_failed:abstract_only_publishable_fp_rate_zero",
    )


@pytest.mark.asyncio
async def test_tampered_raw_blob_is_rejected_before_execution(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    _, raw_ref = _input_ref(tmp_path, store)
    _promote_champion(store, registry)
    blob_path, _ = store.get_paths(raw_ref.artifact_id)
    blob_path.write_bytes(b"{}")
    client = _FakeClient(_positive_candidate())

    outcome = await ClaimAdjudicationRuntime(store=store, registry=registry).adjudicate(
        raw_ref,
        client=client,
        model="fake-model",
    )

    assert outcome.status == "blocked"
    assert outcome.result_ref is None
    assert client.calls == 0


@pytest.mark.asyncio
async def test_execution_result_cannot_be_presented_as_validity_evidence(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    _, raw_ref = _input_ref(tmp_path, store)
    _promote_champion(store, registry)
    outcome = await ClaimAdjudicationRuntime(store=store, registry=registry).adjudicate(
        raw_ref,
        client=_FakeClient(_positive_candidate()),
        model="fake-model",
    )
    assert outcome.result_ref is not None
    admitted = AdmittedClaimAdjudicationBatch.model_validate(
        from_canonical_bytes(store.get_bytes(outcome.result_ref.artifact_id))
    )

    with pytest.raises(ValueError, match="not authoritative for method_validity"):
        assert_claim_adjudication_authority_purpose(
            admitted,
            purpose="method_validity",
        )


@pytest.mark.asyncio
async def test_scientist_cli_route_executes_real_transport_and_materializes_receipt(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    config, _ = _input_ref(tmp_path, store)
    _promote_champion(store, registry)

    metrics = await run_claim_adjudication_command(
        config,
        client=_FakeClient(_positive_candidate()),
        store=store,
        registry=registry,
    )

    assert metrics == {"claims": 1, "published": 1}
    assert config.claim_adjudication_result_ref_path.exists()
    assert config.claim_adjudications_path.exists()
