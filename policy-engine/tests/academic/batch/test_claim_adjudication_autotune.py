from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.literature import (
    CausalCredibility,
    ClaimAdjudicationResult,
    ClaimType,
    DesignFamily,
    RiskOfBias,
    SourceBasis,
    SupportStatus,
)
from polisyos.scientist.autotune import (
    ChampionRegistry,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.autotune.claim_adjudication import (
    ClaimAdjudicationRuntimeLoader,
    ClaimAdjudicationSearchConfig,
    ClaimGoldEvaluator,
    aggregate_claim_rows,
    default_claim_adjudication_promotion_policy,
    default_claim_gold_suite,
    select_prompt_variant,
)


def _claim_result(
    *,
    publishable: bool,
    source_basis: SourceBasis = SourceBasis.FULLTEXT,
    credibility: CausalCredibility = CausalCredibility.MODERATE,
    validity: float = 0.9,
    confidence: float = 0.9,
) -> ClaimAdjudicationResult:
    return ClaimAdjudicationResult(
        claim_id="c1",
        openalex_id="oa1",
        cause_variable="tax audit",
        effect_variable="tax compliance",
        source_basis=source_basis,
        paper_asserts_causality_score=0.9,
        claim_type=ClaimType.CAUSAL_ASSERTION,
        design_family=DesignFamily.RCT,
        causal_credibility=credibility,
        risk_of_bias=RiskOfBias.LOW,
        support_status=SupportStatus.SUPPORTED,
        claim_validity_score=validity,
        adjudication_confidence=confidence,
        publishable_edge=publishable,
        adjudication_notes="test",
    )


def test_baseline_claim_adjudication_config_preserves_current_consensus_behavior(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    loader = ClaimAdjudicationRuntimeLoader(store=store, registry=registry)

    cfg = loader.load()
    aggregated = aggregate_claim_rows(
        [
            _claim_result(publishable=False),
            _claim_result(publishable=True),
            _claim_result(publishable=True),
        ],
        cfg,
    )

    assert cfg.passes == 3
    assert aggregated.publishable_edge is True
    assert select_prompt_variant(cfg, 4) == cfg.prompt_variants[1]


def test_confidence_weighted_claim_consensus_prefers_high_confidence_votes(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    loader = ClaimAdjudicationRuntimeLoader(store=store, registry=registry)

    cfg = loader.load()
    aggregated = aggregate_claim_rows(
        [
            _claim_result(publishable=False, confidence=0.95, validity=0.85),
            _claim_result(publishable=True, confidence=0.20, validity=0.95),
            _claim_result(publishable=True, confidence=0.20, validity=0.95),
        ],
        cfg,
    )

    assert aggregated.publishable_edge is False
    assert aggregated.claim_type_confidence is not None
    assert aggregated.design_family_confidence is not None


def test_claim_promotion_is_blocked_on_abstract_only_overcall(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(store, default_claim_gold_suite())
    candidate_ref = persist_mutation_artifact(
        store, ClaimAdjudicationSearchConfig(prompt_variants=["bad-variant"])
    )
    evaluator = ClaimGoldEvaluator(store=store, registry=registry)

    def predictor(row, config, pass_index, context):
        del config, pass_index, context
        publishable = str(row["paper_id"]) == "seed_claim_002"
        return {
            "claim_id": row["paper_id"],
            "openalex_id": row["paper_id"],
            "cause_variable": row["cause_text"],
            "effect_variable": row["effect_text"],
            "source_basis": "fulltext" if publishable else row["source_basis"],
            "claim_type": row["claim_type"],
            "design_family": row["design_family"],
            "causal_credibility": row["causal_credibility"],
            "risk_of_bias": row["risk_of_bias"],
            "support_status": row["support_status"],
            "paper_asserts_causality_score": 0.9,
            "claim_validity_score": 0.9 if publishable else 0.2,
            "adjudication_confidence": 0.95,
            "publishable_edge": publishable,
        }

    evaluation = evaluator.evaluate(
        candidate_ref,
        suite_ref,
        {"store": store, "registry": registry, "claim_predictor": predictor},
    )
    evaluation_ref = persist_benchmark_evaluation(store, evaluation)
    decision = registry.consider_promotion(
        "claim_adjudication",
        candidate_ref,
        evaluation_ref,
        default_claim_adjudication_promotion_policy(),
    )

    assert evaluation.guardrails["abstract_only_publishable_fp_rate_zero"] is False
    assert decision.promoted is False
    assert decision.reason == "guardrail_failed:abstract_only_publishable_fp_rate_zero"


def test_successful_claim_promotion_changes_runtime_selection(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(store, default_claim_gold_suite())
    loader = ClaimAdjudicationRuntimeLoader(store=store, registry=registry)
    baseline = loader.load()
    assert baseline.prompt_variants[0] != "promoted-variant"

    promoted_config = ClaimAdjudicationSearchConfig(prompt_variants=["promoted-variant"], passes=1)
    candidate_ref = persist_mutation_artifact(store, promoted_config)
    evaluator = ClaimGoldEvaluator(store=store, registry=registry)

    def predictor(row, config, pass_index, context):
        del pass_index, context
        is_positive = str(row["publish_to_graph"]).lower() == "yes"
        publishable = is_positive and config.prompt_variants[0] == "promoted-variant"
        return {
            "claim_id": row["paper_id"],
            "openalex_id": row["paper_id"],
            "cause_variable": row["cause_text"],
            "effect_variable": row["effect_text"],
            "source_basis": row["source_basis"],
            "claim_type": row["claim_type"],
            "design_family": row["design_family"],
            "causal_credibility": row["causal_credibility"],
            "risk_of_bias": row["risk_of_bias"],
            "support_status": row["support_status"],
            "paper_asserts_causality_score": 0.9,
            "claim_validity_score": 0.9 if publishable else 0.1,
            "adjudication_confidence": 0.95,
            "publishable_edge": publishable,
        }

    evaluation = evaluator.evaluate(
        candidate_ref,
        suite_ref,
        {"store": store, "registry": registry, "claim_predictor": predictor},
    )
    evaluation_ref = persist_benchmark_evaluation(store, evaluation)
    decision = registry.consider_promotion(
        "claim_adjudication",
        candidate_ref,
        evaluation_ref,
        default_claim_adjudication_promotion_policy(),
    )

    assert decision.promoted is True
    reloaded = loader.load()
    assert reloaded.prompt_variants == ["promoted-variant"]
