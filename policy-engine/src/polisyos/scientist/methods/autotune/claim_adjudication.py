"""Public autotune claim adjudication module API."""

from __future__ import annotations

import json
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from polisyos.data_forge.read_api.academic import CLAIM_ADJUDICATION_PROMPT_VARIANTS
from polisyos.ir.analytics.literature import (
    CausalCredibility,
    ClaimAdjudicationResult,
    ClaimType,
    DesignFamily,
    RiskOfBias,
    SourceBasis,
    SupportStatus,
)

from .models import (
    BenchmarkedEvaluator,
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    load_model_artifact,
    read_split_manifest,
)
from .registry import ChampionRegistry
from .runtime import ChampionBackedRuntimeLoader, PydanticMutationCodec

CLAIM_ADJUDICATION_LOOP_ID = "claim_adjudication"
_POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_CLAIM_GOLD_PATH = _POLICY_ENGINE_ROOT / "data" / "academic_gold" / "claim_gold.jsonl"
DEFAULT_CLAIM_GOLD_SPLIT_PATH = (
    _POLICY_ENGINE_ROOT / "data" / "academic_gold" / "claim_gold_split.json"
)
STRONG_DESIGN_FAMILIES = {
    DesignFamily.RCT.value,
    DesignFamily.IV.value,
    DesignFamily.DID.value,
    DesignFamily.RDD.value,
    DesignFamily.SYNTHETIC_CONTROL.value,
}


class ClaimConsensusRule(str, Enum):
    """Claim consensus rule data model."""

    MAJORITY_OR_HIGH_CONFIDENCE = "majority_or_high_confidence"


class ClaimAdjudicationSearchConfig(MutationArtifact):
    """Claim adjudication search config data model."""

    model_config = ConfigDict(extra="forbid")

    loop_id: str = CLAIM_ADJUDICATION_LOOP_ID
    prompt_variants: list[str] = Field(
        default_factory=lambda: list(CLAIM_ADJUDICATION_PROMPT_VARIANTS)
    )
    passes: int = Field(default=3, ge=1, le=9)
    consensus_rule: ClaimConsensusRule = ClaimConsensusRule.MAJORITY_OR_HIGH_CONFIDENCE
    majority_vote_floor: int = Field(default=2, ge=1, le=9)
    high_confidence_validity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    high_confidence_confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    publishable_credibility_allowlist: list[CausalCredibility] = Field(
        default_factory=lambda: [CausalCredibility.STRONG, CausalCredibility.MODERATE]
    )

    @field_validator("prompt_variants")
    @classmethod
    def _validate_variants(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if not cleaned:
            raise ValueError("prompt_variants must contain at least one non-empty variant")
        return cleaned


def build_baseline_claim_adjudication_config(
    _context: dict[str, Any] | None = None,
) -> ClaimAdjudicationSearchConfig:
    """Build baseline claim adjudication config."""
    return ClaimAdjudicationSearchConfig()


def default_claim_gold_suite() -> BenchmarkSuite:
    """Default claim gold suite helper."""
    return BenchmarkSuite(
        suite_id="claim_gold",
        suite_version="1.0",
        kind="claim_adjudication",
        dataset_path=str(DEFAULT_CLAIM_GOLD_PATH),
        split_manifest_path=str(DEFAULT_CLAIM_GOLD_SPLIT_PATH),
        metadata={"task": "claim_adjudication"},
    )


def default_claim_adjudication_promotion_policy() -> PromotionPolicy:
    """Default claim adjudication promotion policy helper."""
    return PromotionPolicy(
        loop_id=CLAIM_ADJUDICATION_LOOP_ID,
        primary_metric="precision_publishable",
        direction=MetricDirection.MAXIMIZE,
        compare_split=BenchmarkSplit.HOLDOUT,
        min_improvement=0.0,
        min_sample_count=1,
        required_guardrails=[
            "abstract_only_publishable_fp_rate_zero",
            "schema_valid_json_rate_one",
            "fulltext_strong_design_recall_within_2pp",
        ],
    )


def select_prompt_variant(config: ClaimAdjudicationSearchConfig, pass_index: int) -> str:
    """Select prompt variant helper."""
    variants = config.prompt_variants or list(CLAIM_ADJUDICATION_PROMPT_VARIANTS)
    return variants[pass_index % len(variants)]


def aggregate_claim_rows(
    rows: list[ClaimAdjudicationResult],
    config: ClaimAdjudicationSearchConfig,
) -> ClaimAdjudicationResult:
    """Aggregate claim rows helper."""
    total = len(rows)
    claim_id = rows[0].claim_id
    openalex_id = rows[0].openalex_id
    cause = rows[0].cause_variable
    effect = rows[0].effect_variable
    source_basis, _ = _weighted_mode(
        [(row.source_basis.value, row.adjudication_confidence) for row in rows],
        SourceBasis.FULLTEXT.value,
    )
    claim_type, claim_type_confidence = _weighted_mode(
        [(row.claim_type.value, row.adjudication_confidence) for row in rows],
        ClaimType.ASSOCIATION.value,
    )
    design_family, design_family_confidence = _weighted_mode(
        [(row.design_family.value, row.adjudication_confidence) for row in rows],
        DesignFamily.UNCLEAR.value,
    )
    credibility, _ = _weighted_mode(
        [(row.causal_credibility.value, row.adjudication_confidence) for row in rows],
        CausalCredibility.UNCLEAR.value,
    )
    bias, _ = _weighted_mode(
        [(row.risk_of_bias.value, row.adjudication_confidence) for row in rows],
        RiskOfBias.UNCLEAR.value,
    )
    support, _ = _weighted_mode(
        [(row.support_status.value, row.adjudication_confidence) for row in rows],
        SupportStatus.INSUFFICIENT.value,
    )
    publish_weight = sum(row.adjudication_confidence for row in rows if row.publishable_edge)
    total_weight = sum(max(0.0001, row.adjudication_confidence) for row in rows)
    weighted_publish_ratio = publish_weight / total_weight if total_weight else 0.0
    stability = (
        weighted_publish_ratio if weighted_publish_ratio >= 0.5 else (1.0 - weighted_publish_ratio)
    )
    avg_asserts = sum(row.paper_asserts_causality_score for row in rows) / max(1, total)
    avg_validity = sum(row.claim_validity_score for row in rows) / max(1, total)
    avg_conf = sum(row.adjudication_confidence for row in rows) / max(1, total)
    majority_threshold = max(
        int(config.majority_vote_floor),
        (total + 1) // 2,
    )
    publishable = bool(
        sum(1 for row in rows if row.publishable_edge) >= majority_threshold
        or (
            config.consensus_rule == ClaimConsensusRule.MAJORITY_OR_HIGH_CONFIDENCE
            and avg_validity >= config.high_confidence_validity_threshold
            and avg_conf >= config.high_confidence_confidence_threshold
            and source_basis == SourceBasis.FULLTEXT.value
            and credibility in {item.value for item in config.publishable_credibility_allowlist}
        )
    )
    if weighted_publish_ratio >= 0.60:
        publishable = True
    elif weighted_publish_ratio <= 0.40:
        publishable = False
    if source_basis == SourceBasis.ABSTRACT_ONLY.value:
        publishable = False
    return ClaimAdjudicationResult(
        claim_id=claim_id,
        openalex_id=openalex_id,
        cause_variable=cause,
        effect_variable=effect,
        source_basis=SourceBasis(source_basis),
        paper_asserts_causality_score=avg_asserts,
        claim_type=ClaimType(claim_type),
        design_family=DesignFamily(design_family),
        causal_credibility=CausalCredibility(credibility),
        risk_of_bias=RiskOfBias(bias),
        support_status=SupportStatus(support),
        claim_validity_score=avg_validity,
        adjudication_confidence=avg_conf,
        publishable_edge=publishable,
        adjudication_notes=" | ".join(
            sorted({row.adjudication_notes for row in rows if row.adjudication_notes})
        )[:800],
        consensus_passes=total,
        consensus_stability=stability,
        claim_type_confidence=claim_type_confidence,
        design_family_confidence=design_family_confidence,
        direction_confidence=1.0,
    )


def _weighted_mode(items: list[tuple[str, float]], fallback: str) -> tuple[str, float]:
    votes: dict[str, float] = defaultdict(float)
    total = 0.0
    for value, weight in items:
        clean_value = str(value or "").strip() or fallback
        clean_weight = max(0.0001, float(weight))
        votes[clean_value] += clean_weight
        total += clean_weight
    if not votes:
        return fallback, 0.0
    winner, winner_weight = max(votes.items(), key=lambda item: (item[1], item[0]))
    return winner, (winner_weight / total if total else 0.0)


def load_claim_adjudication_config(
    *,
    context: dict[str, Any] | None = None,
    loader: ChampionBackedRuntimeLoader[ClaimAdjudicationSearchConfig] | None = None,
) -> ClaimAdjudicationSearchConfig:
    """Load claim adjudication config."""
    active_loader = loader or ClaimAdjudicationRuntimeLoader()
    return active_loader.load(context)


class ClaimGoldEvaluator(BenchmarkedEvaluator):
    """Claim gold evaluator public type."""

    def __init__(
        self,
        *,
        store: Any | None = None,
        registry: ChampionRegistry | None = None,
    ) -> None:
        self._store = store
        self._registry = registry

    def evaluate(
        self,
        candidate_ref,
        suite_ref,
        context: dict[str, Any],
    ) -> BenchmarkEvaluation:
        store = context.get("store") or self._store
        if store is None:
            raise ValueError("ClaimGoldEvaluator requires a CAS store")
        suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
        config = load_model_artifact(store, candidate_ref, ClaimAdjudicationSearchConfig)
        if suite.dataset_path is None or suite.split_manifest_path is None:
            raise ValueError("ClaimGoldEvaluator requires dataset_path and split_manifest_path")
        predictor = context.get("claim_predictor")
        if not callable(predictor):
            raise ValueError(
                "context['claim_predictor'] must be callable for claim adjudication benchmark evaluation"
            )
        rows = _read_jsonl(Path(suite.dataset_path))
        split_manifest = read_split_manifest(Path(suite.split_manifest_path))
        per_item, invalid_count, total_cost = self._predict_dataset(
            rows=rows,
            config=config,
            predictor=predictor,
            context=context,
        )
        current_recall = self._champion_recall(
            candidate_ref=candidate_ref,
            suite=suite,
            rows=rows,
            predictor=predictor,
            context=context,
        )
        selection_metrics = _claim_metrics(
            [
                item
                for item in per_item
                if split_manifest.split_for(item["item_id"]) == BenchmarkSplit.SELECTION
            ],
            total_cost=total_cost,
            invalid_count=invalid_count,
        )
        holdout_metrics = _claim_metrics(
            [
                item
                for item in per_item
                if split_manifest.split_for(item["item_id"]) == BenchmarkSplit.HOLDOUT
            ],
            total_cost=total_cost,
            invalid_count=invalid_count,
        )
        holdout_recall = float(holdout_metrics.get("fulltext_strong_design_recall", 0.0))
        recall_delta_pp = (holdout_recall - current_recall) * 100.0
        guardrails = {
            "abstract_only_publishable_fp_rate_zero": float(
                holdout_metrics.get("abstract_only_publishable_fp_rate", 1.0)
            )
            == 0.0,
            "schema_valid_json_rate_one": float(holdout_metrics.get("schema_valid_json_rate", 0.0))
            >= 1.0,
            "fulltext_strong_design_recall_within_2pp": recall_delta_pp >= -2.0,
        }
        sample_counts = {
            BenchmarkSplit.SELECTION.value: int(selection_metrics.get("sample_count", 0)),
            BenchmarkSplit.HOLDOUT.value: int(holdout_metrics.get("sample_count", 0)),
        }
        return BenchmarkEvaluation(
            loop_id=CLAIM_ADJUDICATION_LOOP_ID,
            suite_id=suite.suite_id,
            suite_version=suite.suite_version,
            candidate_ref=candidate_ref,
            selection_metrics=selection_metrics,
            holdout_metrics=holdout_metrics,
            sample_counts=sample_counts,
            guardrails=guardrails,
            promotable=all(guardrails.values()),
            notes=[f"holdout_recall_delta_pp:{recall_delta_pp:.3f}"],
            metadata={"invalid_predictions": invalid_count, "total_cost": total_cost},
        )

    def _champion_recall(
        self,
        *,
        candidate_ref,
        suite: BenchmarkSuite,
        rows: list[dict[str, Any]],
        predictor: Any,
        context: dict[str, Any],
    ) -> float:
        registry = context.get("registry") or self._registry
        store = context.get("store") or self._store
        if registry is None or store is None:
            return 0.0
        champion = registry.get(CLAIM_ADJUDICATION_LOOP_ID)
        if champion is None or champion.candidate_ref.artifact_id == candidate_ref.artifact_id:
            return 0.0
        champion_cfg = load_model_artifact(
            store, champion.candidate_ref, ClaimAdjudicationSearchConfig
        )
        split_manifest = read_split_manifest(
            Path(suite.split_manifest_path or DEFAULT_CLAIM_GOLD_SPLIT_PATH)
        )
        champion_items, invalid_count, total_cost = self._predict_dataset(
            rows=rows,
            config=champion_cfg,
            predictor=predictor,
            context=context,
        )
        del invalid_count, total_cost
        holdout_metrics = _claim_metrics(
            [
                item
                for item in champion_items
                if split_manifest.split_for(item["item_id"]) == BenchmarkSplit.HOLDOUT
            ],
            total_cost=0.0,
            invalid_count=0,
        )
        return float(holdout_metrics.get("fulltext_strong_design_recall", 0.0))

    def _predict_dataset(
        self,
        *,
        rows: list[dict[str, Any]],
        config: ClaimAdjudicationSearchConfig,
        predictor: Any,
        context: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], int, float]:
        items: list[dict[str, Any]] = []
        invalid_count = 0
        total_cost = 0.0
        for row in rows:
            passes: list[ClaimAdjudicationResult] = []
            for pass_index in range(config.passes):
                try:
                    prediction, cost = _coerce_prediction(
                        predictor(
                            row,
                            config,
                            pass_index,
                            context,
                        ),
                        fallback_item_id=str(row.get("paper_id") or row.get("claim_id") or ""),
                        fallback_openalex_id=str(row.get("paper_id") or row.get("claim_id") or ""),
                        fallback_claim_text=str(row.get("claim_text") or ""),
                        fallback_cause=str(
                            row.get("cause_text") or row.get("cause_variable") or ""
                        ),
                        fallback_effect=str(
                            row.get("effect_text") or row.get("effect_variable") or ""
                        ),
                    )
                except Exception:
                    invalid_count += 1
                    continue
                passes.append(prediction)
                total_cost += cost
            if not passes:
                continue
            aggregated = aggregate_claim_rows(passes, config)
            items.append(
                {
                    "item_id": str(
                        row.get("paper_id") or row.get("claim_id") or aggregated.claim_id
                    ),
                    "gold": row,
                    "prediction": aggregated,
                }
            )
        return items, invalid_count, total_cost


class ClaimAdjudicationRuntimeLoader(ChampionBackedRuntimeLoader[ClaimAdjudicationSearchConfig]):
    """Claim adjudication runtime loader implementation."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            loop_id=CLAIM_ADJUDICATION_LOOP_ID,
            model_cls=ClaimAdjudicationSearchConfig,
            baseline_factory=build_baseline_claim_adjudication_config,
            suite_version="1.0",
            **kwargs,
        )


def claim_adjudication_search_loop_spec(
    *,
    candidate_generator: Any | None = None,
    store: Any | None = None,
    registry: ChampionRegistry | None = None,
) -> SearchLoopSpec:
    """Claim adjudication search loop spec helper."""
    return SearchLoopSpec(
        loop_id=CLAIM_ADJUDICATION_LOOP_ID,
        mutation_codec=PydanticMutationCodec(ClaimAdjudicationSearchConfig),
        candidate_generator=candidate_generator,
        benchmark_evaluator=ClaimGoldEvaluator(store=store, registry=registry),
        promotion_policy=default_claim_adjudication_promotion_policy(),
        runtime_loader=ClaimAdjudicationRuntimeLoader(store=store, registry=registry),
    )


def _mode(items: list[str], default: str) -> str:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    if not counts:
        return default
    return max(counts.items(), key=lambda pair: (pair[1], pair[0]))[0]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _binary_precision(tp: int, predicted_positive: int) -> float:
    if predicted_positive <= 0:
        return 1.0 if tp == 0 else 0.0
    return tp / predicted_positive


def _binary_recall(tp: int, actual_positive: int) -> float:
    if actual_positive <= 0:
        return 1.0
    return tp / actual_positive


def _binary_f1(precision: float, recall: float) -> float:
    if precision + recall <= 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def _claim_metrics(
    items: list[dict[str, Any]],
    *,
    total_cost: float,
    invalid_count: int,
) -> dict[str, float]:
    if not items:
        return {
            "sample_count": 0.0,
            "precision_publishable": 0.0,
            "f1_publishable": 0.0,
            "brier_score": 1.0,
            "cost_per_correct": total_cost,
            "abstract_only_publishable_fp_rate": 0.0,
            "schema_valid_json_rate": 0.0,
            "fulltext_strong_design_recall": 0.0,
        }
    tp = fp = fn = correct = 0
    brier_total = 0.0
    abstract_only_total = 0
    abstract_only_fp = 0
    fulltext_strong_total = 0
    fulltext_strong_tp = 0
    for item in items:
        gold = item["gold"]
        prediction: ClaimAdjudicationResult = item["prediction"]
        actual_publishable = str(gold.get("publish_to_graph") or "no").strip().lower() == "yes"
        predicted_publishable = bool(prediction.publishable_edge)
        if predicted_publishable and actual_publishable:
            tp += 1
        if predicted_publishable and not actual_publishable:
            fp += 1
        if (not predicted_publishable) and actual_publishable:
            fn += 1
        if predicted_publishable == actual_publishable:
            correct += 1
        brier_total += (
            float(prediction.claim_validity_score) - (1.0 if actual_publishable else 0.0)
        ) ** 2
        if str(gold.get("source_basis") or "").strip().lower() == SourceBasis.ABSTRACT_ONLY.value:
            abstract_only_total += 1
            if predicted_publishable and not actual_publishable:
                abstract_only_fp += 1
        if (
            actual_publishable
            and str(gold.get("source_basis") or "").strip().lower() == SourceBasis.FULLTEXT.value
            and str(gold.get("design_family") or "").strip().lower() in STRONG_DESIGN_FAMILIES
        ):
            fulltext_strong_total += 1
            if predicted_publishable:
                fulltext_strong_tp += 1
    precision = _binary_precision(tp, tp + fp)
    recall = _binary_recall(tp, tp + fn)
    return {
        "sample_count": float(len(items)),
        "precision_publishable": precision,
        "f1_publishable": _binary_f1(precision, recall),
        "brier_score": brier_total / len(items),
        "cost_per_correct": total_cost / max(1, correct),
        "abstract_only_publishable_fp_rate": abstract_only_fp / max(1, abstract_only_total),
        "schema_valid_json_rate": max(0.0, 1.0 - (invalid_count / max(1, len(items)))),
        "fulltext_strong_design_recall": _binary_recall(fulltext_strong_tp, fulltext_strong_total),
    }


def _coerce_prediction(
    raw: Any,
    *,
    fallback_item_id: str,
    fallback_openalex_id: str,
    fallback_claim_text: str,
    fallback_cause: str,
    fallback_effect: str,
) -> tuple[ClaimAdjudicationResult, float]:
    payload = raw
    cost = 0.0
    if isinstance(raw, tuple) and len(raw) == 2:
        payload, meta = raw
        if isinstance(meta, (int, float)):
            cost = float(meta)
        elif isinstance(meta, dict):
            cost = float(meta.get("cost", 0.0) or 0.0)
    if isinstance(payload, ClaimAdjudicationResult):
        return payload, cost
    if not isinstance(payload, dict):
        raise TypeError(
            "Claim predictor must return ClaimAdjudicationResult, dict, or (payload, meta)"
        )
    normalized = {
        "claim_id": str(payload.get("claim_id") or fallback_item_id),
        "openalex_id": str(payload.get("openalex_id") or fallback_openalex_id),
        "cause_variable": str(
            payload.get("cause_variable") or payload.get("cause_text") or fallback_cause
        ),
        "effect_variable": str(
            payload.get("effect_variable") or payload.get("effect_text") or fallback_effect
        ),
        "source_basis": payload.get("source_basis") or SourceBasis.FULLTEXT.value,
        "paper_asserts_causality_score": payload.get("paper_asserts_causality_score", 0.0),
        "claim_type": payload.get("claim_type", ClaimType.ASSOCIATION.value),
        "design_family": payload.get("design_family", DesignFamily.UNCLEAR.value),
        "causal_credibility": payload.get("causal_credibility", CausalCredibility.UNCLEAR.value),
        "risk_of_bias": payload.get("risk_of_bias", RiskOfBias.UNCLEAR.value),
        "support_status": payload.get("support_status", SupportStatus.INSUFFICIENT.value),
        "claim_validity_score": payload.get("claim_validity_score", 0.0),
        "adjudication_confidence": payload.get("adjudication_confidence", 0.0),
        "publishable_edge": bool(payload.get("publishable_edge", False)),
        "adjudication_notes": str(payload.get("adjudication_notes") or fallback_claim_text or ""),
        "consensus_passes": int(payload.get("consensus_passes", 1) or 1),
        "consensus_stability": float(payload.get("consensus_stability", 1.0) or 1.0),
    }
    return ClaimAdjudicationResult.model_validate(normalized), cost


__all__ = [
    "CLAIM_ADJUDICATION_LOOP_ID",
    "ClaimAdjudicationRuntimeLoader",
    "ClaimAdjudicationSearchConfig",
    "ClaimConsensusRule",
    "ClaimGoldEvaluator",
    "aggregate_claim_rows",
    "build_baseline_claim_adjudication_config",
    "claim_adjudication_search_loop_spec",
    "default_claim_adjudication_promotion_policy",
    "default_claim_gold_suite",
    "load_claim_adjudication_config",
    "select_prompt_variant",
]
