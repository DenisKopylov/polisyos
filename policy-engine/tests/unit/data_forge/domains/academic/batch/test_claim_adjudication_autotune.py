from __future__ import annotations

import json

from pydantic import BaseModel

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.data_forge.domains.academic.batch.claim_adjudication_policy import (
    claim_promotion_policy,
)
from polisyos.ir.analytics.literature import (
    CausalCredibility,
    ClaimAdjudicationResult,
    ClaimType,
    DesignFamily,
    RiskOfBias,
    SourceBasis,
    SupportStatus,
)
from polisyos.scientist.methods.autotune import (
    ChampionRegistry,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.claim_adjudication import (
    ClaimAdjudicationRuntimeLoader,
    ClaimAdjudicationSearchConfig,
    ClaimGoldEvaluator,
    aggregate_claim_rows,
    default_claim_adjudication_promotion_policy,
    default_claim_gold_suite,
    select_prompt_variant,
)
from polisyos.scientist.methods.autotune.models import PromotionPolicy


class _ClaimPolicyEnvelope(BaseModel):
    policy: PromotionPolicy


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


def test_default_claim_policy_projection_preserves_historical_absent_unit_shape() -> None:
    """Null optional fields must not alter the canonical claim-policy bytes."""
    # Catches the production mutation that emits unit=null from PromotionPolicy.model_dump().
    policy = default_claim_adjudication_promotion_policy()

    assert policy.model_dump(mode="json") == claim_promotion_policy()
    assert "unit" not in policy.model_dump(mode="json")


def test_explicit_claim_policy_unit_survives_canonical_serialization() -> None:
    """A real unit remains part of a generic policy artifact."""
    # Catches an over-broad null-exclusion fix that drops explicit non-null units.
    policy = default_claim_adjudication_promotion_policy().model_copy(update={"unit": "ratio"})

    assert policy.model_dump(mode="json")["unit"] == "ratio"


def test_claim_policy_serializer_characterization_across_json_and_nesting() -> None:
    """Policy serialization keeps null omission and explicit units at each boundary."""
    # Catches a serializer mutation that handles one dump API but leaks nulls
    # through explicit exclude_none=False or a nested Pydantic model.
    default_policy = default_claim_adjudication_promotion_policy()
    default_json = json.loads(default_policy.model_dump_json())
    default_dump = default_policy.model_dump(mode="json", exclude_none=False)
    nested_default = _ClaimPolicyEnvelope(policy=default_policy).model_dump(
        mode="json", exclude_none=False
    )["policy"]

    assert "unit" not in default_json
    assert "unit" not in default_dump
    assert "unit" not in nested_default

    explicit_policy = default_policy.model_copy(update={"unit": "ratio"})
    explicit_json = json.loads(explicit_policy.model_dump_json())
    explicit_dump = explicit_policy.model_dump(mode="json", exclude_none=False)
    nested_explicit = _ClaimPolicyEnvelope(policy=explicit_policy).model_dump(
        mode="json", exclude_none=False
    )["policy"]

    assert explicit_json["unit"] == "ratio"
    assert explicit_dump["unit"] == "ratio"
    assert nested_explicit["unit"] == "ratio"


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
    assert registry.get("claim_adjudication") is None
    assert not (tmp_path / ".polisyos" / "search_registry" / "claim_adjudication").exists()

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
    pointer = registry.get("claim_adjudication")
    assert pointer is not None
    assert pointer.metadata["promoted_by_policy"] == claim_promotion_policy()
    assert "unit" not in pointer.metadata["promoted_by_policy"]

    mismatch = registry.consider_promotion(
        "claim_adjudication",
        candidate_ref,
        evaluation_ref,
        default_claim_adjudication_promotion_policy().model_copy(update={"unit": "ratio"}),
    )
    # Catches a canonicalization change that accidentally makes explicit policy mismatches
    # admissible after omitting null fields from the default policy.
    assert mismatch.promoted is False
    assert mismatch.reason == "claim_promotion_policy_mismatch"
    reloaded = loader.load()
    assert reloaded.prompt_variants == ["promoted-variant"]
