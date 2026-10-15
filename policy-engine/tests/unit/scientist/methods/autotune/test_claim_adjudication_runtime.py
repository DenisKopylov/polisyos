from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import (
    ArtifactWriteOptions,
    ProducerInfo,
    artifact_ref_for_manifest,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.data_forge.domains.academic.batch.claim_adjudication_policy import (
    claim_promotion_policy,
)
from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
    produce_claim_adjudication_input,
)
from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.read_api.academic import (
    validate_claim_adjudication_input_batch,
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
    EvidenceStrength,
    SourceBasis,
    TextQuality,
)
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    ChampionRegistry,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.claim_adjudication import (
    ClaimAdjudicationSearchConfig,
    default_claim_adjudication_promotion_policy,
    default_claim_gold_suite,
)
from polisyos.scientist.methods.autotune.claim_adjudication_cli import (
    run_claim_adjudication_command,
)
from polisyos.scientist.methods.autotune.claim_adjudication_runtime import (
    ClaimAdjudicationRuntime,
    assert_claim_adjudication_authority_purpose,
)
from tests.unit.data_forge.domains.academic.batch._claim_evidence import (
    evidence_fixture,
    tamper_pointer,
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
    suite_ref = persist_benchmark_suite(
        store, default_claim_gold_suite(), return_selected_profile=True
    )
    candidate_ref = persist_mutation_artifact(
        store,
        ClaimAdjudicationSearchConfig(passes=1),
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
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
    evaluation_ref = persist_benchmark_evaluation(
        store,
        evaluation,
        inputs=[
            input_ref_from_artifact_ref(candidate_ref, role="candidate"),
            input_ref_from_artifact_ref(suite_ref, role="benchmark_suite"),
        ],
        return_selected_profile=True,
    )
    decision = registry.consider_promotion(
        "claim_adjudication",
        candidate_ref,
        evaluation_ref,
        policy,
        suite_ref=suite_ref,
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


def test_raw_input_excludes_producer_publish_authority_and_freezes_bytes(
    tmp_path,
) -> None:
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
async def test_promoted_champion_executes_and_publishes_strong_fulltext(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    _, raw_ref = _input_ref(tmp_path, store)
    evidence = evidence_fixture(store, registry, tmp_path / "registry", raw_ref)
    pointer = registry.get("claim_adjudication")
    assert pointer is not None
    assert pointer.metadata["promoted_by_policy"] == claim_promotion_policy()
    assert "unit" not in pointer.metadata["promoted_by_policy"]

    outcome = await ClaimAdjudicationRuntime(
        store=store,
        registry=registry,
        verifier=evidence.verifier,
        evaluation_receipt_ref=evidence.evaluation_receipt_ref,
        execution_receipt_ref=evidence.execution_receipt_ref,
    ).adjudicate(
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
    evidence = evidence_fixture(store, registry, tmp_path / "registry", raw_ref)

    outcome = await ClaimAdjudicationRuntime(
        store=store,
        registry=registry,
        verifier=evidence.verifier,
        evaluation_receipt_ref=evidence.evaluation_receipt_ref,
        execution_receipt_ref=evidence.execution_receipt_ref,
    ).adjudicate(
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
    evidence = evidence_fixture(store, registry, tmp_path / "registry", raw_ref)
    pointer = registry.get("claim_adjudication")
    assert pointer is not None
    replacement = persist_mutation_artifact(
        store,
        ClaimAdjudicationSearchConfig(passes=2),
    )
    tamper_pointer(
        tmp_path / "registry",
        "claim_adjudication",
        pointer.model_copy(update={"candidate_ref": replacement}),
    )

    outcome = await ClaimAdjudicationRuntime(
        store=store,
        registry=registry,
        verifier=evidence.verifier,
        evaluation_receipt_ref=evidence.evaluation_receipt_ref,
        execution_receipt_ref=evidence.execution_receipt_ref,
    ).adjudicate(
        raw_ref,
        client=_FakeClient(_positive_candidate()),
        model="fake-model",
    )

    assert outcome.status == "blocked"
    assert "mismatch" in outcome.blockers[0]


@pytest.mark.asyncio
async def test_unbound_false_guardrail_pointer_is_refused(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    _, raw_ref = _input_ref(tmp_path, store)
    evidence = evidence_fixture(store, registry, tmp_path / "registry", raw_ref)
    evaluation_ref = evidence.evaluation_ref
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
        inputs=[input_ref_from_artifact_ref(evidence.suite_ref, role="benchmark_suite")],
    )
    # The candidate evaluation fails a guardrail, but this pointer is not the
    # evaluation committed by the promotion basis. Refuse it before consuming
    # the candidate's guardrail result.
    tamper_pointer(
        tmp_path / "registry",
        "claim_adjudication",
        pointer.model_copy(update={"evaluation_ref": rejected_ref}),
    )
    client = _FakeClient(_positive_candidate())

    outcome = await ClaimAdjudicationRuntime(
        store=store,
        registry=registry,
        verifier=evidence.verifier,
        evaluation_receipt_ref=evidence.evaluation_receipt_ref,
        execution_receipt_ref=evidence.execution_receipt_ref,
    ).adjudicate(
        raw_ref,
        client=client,
        model="fake-model",
    )

    assert outcome.status == "blocked"
    assert outcome.blockers == ("claim_adjudication_promotion_basis_pointer_mismatch",)
    assert client.calls == 0


@pytest.mark.asyncio
async def test_tampered_raw_blob_is_rejected_before_execution(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    _, raw_ref = _input_ref(tmp_path, store)
    evidence = evidence_fixture(store, registry, tmp_path / "registry", raw_ref)
    blob_path, _ = store._paths(raw_ref.artifact_id)
    blob_path.write_bytes(b"{}")
    client = _FakeClient(_positive_candidate())

    outcome = await ClaimAdjudicationRuntime(
        store=store,
        registry=registry,
        verifier=evidence.verifier,
        evaluation_receipt_ref=evidence.evaluation_receipt_ref,
        execution_receipt_ref=evidence.execution_receipt_ref,
    ).adjudicate(
        raw_ref,
        client=client,
        model="fake-model",
    )

    assert outcome.status == "blocked"
    assert outcome.result_ref is None
    assert client.calls == 0


@pytest.mark.asyncio
async def test_execution_result_cannot_be_presented_as_validity_evidence(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    _, raw_ref = _input_ref(tmp_path, store)
    evidence = evidence_fixture(store, registry, tmp_path / "registry", raw_ref)
    outcome = await ClaimAdjudicationRuntime(
        store=store,
        registry=registry,
        verifier=evidence.verifier,
        evaluation_receipt_ref=evidence.evaluation_receipt_ref,
        execution_receipt_ref=evidence.execution_receipt_ref,
    ).adjudicate(
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
    config, raw_ref = _input_ref(tmp_path, store)
    evidence = evidence_fixture(store, registry, tmp_path / "registry", raw_ref)

    metrics = await run_claim_adjudication_command(
        config,
        client=_FakeClient(_positive_candidate()),
        store=store,
        registry=registry,
        verifier=evidence.verifier,
        evaluation_receipt_ref=evidence.evaluation_receipt_ref,
        execution_receipt_ref=evidence.execution_receipt_ref,
    )

    assert metrics == {"claims": 1, "published": 1}
    assert config.claim_adjudication_result_ref_path.exists()
    assert config.claim_adjudications_path.exists()


@pytest.mark.asyncio
async def test_runtime_result_manifest_preserves_all_selected_claim_refs(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    config, raw_ref = _input_ref(tmp_path, store)
    registry = ChampionRegistry(root=config.claim_adjudication_registry_root, store=store)
    fixture = evidence_fixture(store, registry, config.claim_adjudication_registry_root, raw_ref)
    outcome = await ClaimAdjudicationRuntime(
        store=store,
        registry=registry,
        verifier=fixture.verifier,
        evaluation_receipt_ref=fixture.evaluation_receipt_ref,
        execution_receipt_ref=fixture.execution_receipt_ref,
    ).adjudicate(raw_ref, client=_FakeClient(fixture.client_payload), model="fixture")
    assert outcome.status == "completed", outcome
    assert outcome.result_ref is not None
    result_manifest = store.get_manifest(outcome.result_ref)
    inputs = {item.role: item for item in result_manifest.inputs}
    expected = {
        "raw_input": raw_ref,
        "candidate": fixture.candidate_ref,
        "evaluation": fixture.evaluation_ref,
        "evaluation_receipt": fixture.evaluation_receipt_ref,
        "execution_receipt": fixture.execution_receipt_ref,
        "benchmark_suite": fixture.suite_ref,
    }
    assert len(inputs) == len(result_manifest.inputs)
    assert set(inputs) == set(expected)
    for role, ref in expected.items():
        edge = inputs[role]
        assert edge.role == role
        assert edge.artifact_id == ref.artifact_id
        assert edge.manifest_profile_sha256 is not None
        assert edge.manifest_profile_sha256 == ref.manifest_profile_sha256
        selected_manifest = store.get_manifest_by_profile(
            edge.artifact_id, edge.manifest_profile_sha256
        )
        selected_ref = artifact_ref_for_manifest(selected_manifest)
        assert selected_ref.artifact_id == ref.artifact_id
        assert selected_ref.kind == ref.kind
        assert selected_ref.media_type == ref.media_type
        assert selected_ref.manifest_profile_sha256 == ref.manifest_profile_sha256


def test_raw_batch_binds_complete_extraction_and_retraction_source_profiles(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snapshot")
    config.article_extraction_results_path.parent.mkdir(parents=True, exist_ok=True)
    config.article_extraction_results_path.write_text(
        _article().model_dump_json() + "\n", encoding="utf-8"
    )
    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.write_text('{"id":"W2","is_retracted":true}\n', encoding="utf-8")

    raw_ref = produce_claim_adjudication_input(config, store=store)
    fresh_reader = FileSystemCAS(tmp_path / "cas")
    raw_manifest = fresh_reader.get_manifest(raw_ref)
    assert raw_ref.manifest_profile_sha256 is not None
    assert raw_manifest.kind == "data_forge.academic.claim_adjudication.input_batch"
    assert raw_manifest.media_type == "application/json"
    assert raw_manifest.artifact_schema is not None
    assert (
        raw_manifest.artifact_schema.name
        == "polisyos.ir.analytics.literature.ClaimAdjudicationInputBatch"
    )
    assert raw_manifest.artifact_schema.version == "1.0"
    assert raw_manifest.producer is not None
    assert (
        str(raw_manifest.producer.component)
        == "polisyos.data_forge.domains.academic.batch.claim_adjudicator"
    )
    assert raw_manifest.producer.version == "1.0"

    edges = {item.role: item for item in raw_manifest.inputs}
    assert set(edges) == {"extraction_source", "retraction_source"}
    expected_sources = {
        "extraction_source": (
            "data_forge.academic.claim_adjudication.extraction_source",
            "polisyos.ir.analytics.literature.ArticleExtractionResult.ndjson",
        ),
        "retraction_source": (
            "data_forge.academic.claim_adjudication.retraction_source",
            "polisyos.data_forge.academic.MergedRecord.ndjson",
        ),
    }
    for role, edge in edges.items():
        assert edge.manifest_profile_sha256 is not None
        source_manifest = fresh_reader.get_manifest_by_profile(
            edge.artifact_id, edge.manifest_profile_sha256
        )
        expected_kind, expected_schema = expected_sources[role]
        assert source_manifest.kind == expected_kind
        assert source_manifest.media_type == "application/x-ndjson"
        assert source_manifest.artifact_schema is not None
        assert source_manifest.artifact_schema.name == expected_schema
        assert source_manifest.artifact_schema.version == "1.0"
        assert source_manifest.producer is not None
        assert (
            str(source_manifest.producer.component)
            == "polisyos.data_forge.domains.academic.batch.claim_adjudicator"
        )
        assert source_manifest.producer.version == "1.0"
    validate_claim_adjudication_input_batch(fresh_reader, raw_ref)

    body = from_canonical_bytes(fresh_reader.get_bytes(raw_ref.artifact_id))
    for role, edge in edges.items():
        profileless_inputs = [
            item.model_copy(update={"manifest_profile_sha256": None}) if item.role == role else item
            for item in raw_manifest.inputs
        ]
        profileless_ref = fresh_reader.put_json(
            body,
            ArtifactWriteOptions(
                kind=raw_manifest.kind,
                media_type=raw_manifest.media_type,
                schema=raw_manifest.artifact_schema,
                producer=raw_manifest.producer,
                inputs=profileless_inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(ValueError):
            validate_claim_adjudication_input_batch(fresh_reader, profileless_ref)

        source_manifest = fresh_reader.get_manifest_by_profile(
            edge.artifact_id, edge.manifest_profile_sha256
        )
        alternate_source_ref = fresh_reader.put_bytes(
            fresh_reader.get_bytes(edge.artifact_id),
            ArtifactWriteOptions(
                kind=source_manifest.kind,
                media_type=source_manifest.media_type,
                schema=source_manifest.artifact_schema,
                producer=ProducerInfo(
                    component=str(source_manifest.producer.component),
                    version="2.0",
                ),
                inputs=list(source_manifest.inputs),
            ),
            return_selected_profile=True,
        )
        assert alternate_source_ref.artifact_id == edge.artifact_id
        assert alternate_source_ref.manifest_profile_sha256 != edge.manifest_profile_sha256
        alternate_inputs = [
            input_ref_from_artifact_ref(alternate_source_ref, role=role)
            if item.role == role
            else item
            for item in raw_manifest.inputs
        ]
        alternate_ref = fresh_reader.put_json(
            body,
            ArtifactWriteOptions(
                kind=raw_manifest.kind,
                media_type=raw_manifest.media_type,
                schema=raw_manifest.artifact_schema,
                producer=raw_manifest.producer,
                inputs=alternate_inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(ValueError, match=f"source profile mismatch:{role}"):
            validate_claim_adjudication_input_batch(fresh_reader, alternate_ref)
