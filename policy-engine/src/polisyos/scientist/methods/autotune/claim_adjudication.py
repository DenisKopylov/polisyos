"""Public autotune claim adjudication module API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from polisyos.data_forge.read_api import academic
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

ClaimAdjudicationRules = academic.ClaimAdjudicationRules
ClaimConsensusRule = academic.ClaimConsensusRule
STRONG_DESIGN_FAMILIES = academic.STRONG_DESIGN_FAMILIES
_claim_metrics = academic.claim_metrics
aggregate_claim_rows = academic.aggregate_claim_rows
claim_guardrails = academic.claim_guardrails
claim_promotion_policy = academic.claim_promotion_policy

CLAIM_ADJUDICATION_LOOP_ID = "claim_adjudication"
_POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_CLAIM_GOLD_PATH = _POLICY_ENGINE_ROOT / "data" / "academic_gold" / "claim_gold.jsonl"
DEFAULT_CLAIM_GOLD_SPLIT_PATH = (
    _POLICY_ENGINE_ROOT / "data" / "academic_gold" / "claim_gold_split.json"
)
CLAIM_ADJUDICATION_SCHEMA_HINT = """
{
  "paper_asserts_causality_score": <number 0..1>,
  "claim_type": "causal_assertion|association|mechanism|descriptive|normative|review_summary",
  "design_family": "rct|iv|did|rdd|synthetic_control|panel_fe|ols|meta_analysis|review|theoretical|unclear",
  "causal_credibility": "strong|moderate|weak|not_causal|unclear",
  "risk_of_bias": "low|moderate|serious|critical|unclear",
  "support_status": "supported|mixed|counterevidence|insufficient",
  "claim_validity_score": <number 0..1>,
  "adjudication_confidence": <number 0..1>,
  "adjudication_notes": "short evidence assessment"
}

Return descriptive evidence assessment only. Publication authority is computed
by Scientist policy after schema validation; never propose a publication flag.
""".strip()

CLAIM_ADJUDICATION_PROMPT_VARIANTS = (
    "Be conservative. Do not upgrade observational language without explicit design support.",
    "Assess identification strategy and whether the cited spans support the stated causal claim.",
    "Prefer weak credibility when the text lacks identification or reports only association.",
)


class ClaimAdjudicationSearchConfig(MutationArtifact, ClaimAdjudicationRules):
    """Claim adjudication search config data model."""

    model_config = ConfigDict(extra="forbid")

    loop_id: str = CLAIM_ADJUDICATION_LOOP_ID
    prompt_variants: list[str] = Field(
        default_factory=lambda: list(CLAIM_ADJUDICATION_PROMPT_VARIANTS)
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
    return PromotionPolicy.model_validate(claim_promotion_policy())


def select_prompt_variant(config: ClaimAdjudicationSearchConfig, pass_index: int) -> str:
    """Select prompt variant helper."""
    variants = config.prompt_variants or list(CLAIM_ADJUDICATION_PROMPT_VARIANTS)
    return variants[pass_index % len(variants)]


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
        guardrails = claim_guardrails(holdout_metrics, current_recall)
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

    def load(self, context: dict[str, Any] | None = None) -> ClaimAdjudicationSearchConfig:
        """Return a baseline candidate without creating a champion transition."""
        if self._registry.get(CLAIM_ADJUDICATION_LOOP_ID) is None:
            return build_baseline_claim_adjudication_config(context or {})
        return super().load(context)


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
    "CLAIM_ADJUDICATION_PROMPT_VARIANTS",
    "CLAIM_ADJUDICATION_SCHEMA_HINT",
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
