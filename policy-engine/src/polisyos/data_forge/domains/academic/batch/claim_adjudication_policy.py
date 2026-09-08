"""Pure claim-adjudication arithmetic shared by evaluation and evidence replay.

These functions do not authenticate evidence or confer authority on their inputs.
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics import (
    CausalCredibility,
    ClaimAdjudicationInputItem,
    ClaimAdjudicationResult,
    ClaimType,
    DesignFamily,
    RiskOfBias,
    SourceBasis,
    SupportStatus,
)

STRONG_DESIGN_FAMILIES = {
    DesignFamily.RCT.value,
    DesignFamily.IV.value,
    DesignFamily.DID.value,
    DesignFamily.RDD.value,
    DesignFamily.SYNTHETIC_CONTROL.value,
}


class ClaimConsensusRule(str, Enum):
    """Supported deterministic aggregation rule."""

    MAJORITY_OR_HIGH_CONFIDENCE = "majority_or_high_confidence"


class ClaimAdjudicationRules(BaseModel):
    """Strict arithmetic inputs, without candidate-generation authority."""

    model_config = ConfigDict(extra="forbid")
    passes: int = Field(default=3, ge=1, le=9)
    consensus_rule: ClaimConsensusRule = ClaimConsensusRule.MAJORITY_OR_HIGH_CONFIDENCE
    majority_vote_floor: int = Field(default=2, ge=1, le=9)
    high_confidence_validity_threshold: float = Field(default=0.85, ge=0, le=1)
    high_confidence_confidence_threshold: float = Field(default=0.85, ge=0, le=1)
    publishable_credibility_allowlist: list[CausalCredibility] = Field(
        default_factory=lambda: [CausalCredibility.STRONG, CausalCredibility.MODERATE]
    )


def claim_promotion_policy() -> dict[str, Any]:
    """Return the canonical bounded claim-adjudication promotion policy."""
    return {
        "loop_id": "claim_adjudication",
        "primary_metric": "precision_publishable",
        "direction": "maximize",
        "compare_split": "holdout",
        "min_improvement": 0.0,
        "min_sample_count": 1,
        "required_guardrails": [
            "abstract_only_publishable_fp_rate_zero",
            "schema_valid_json_rate_one",
            "fulltext_strong_design_recall_within_2pp",
        ],
    }


def claim_guardrails(metrics: dict[str, float], incumbent_recall: float) -> dict[str, bool]:
    """Recompute every claim-promotion guardrail from measured counts."""
    return {
        "abstract_only_publishable_fp_rate_zero": metrics["abstract_only_publishable_fp_rate"] == 0,
        "schema_valid_json_rate_one": metrics["schema_valid_json_rate"] >= 1,
        "fulltext_strong_design_recall_within_2pp": (
            metrics["fulltext_strong_design_recall"] - incumbent_recall
        )
        * 100
        >= -2,
    }


def metric_is_improved(
    *, current: float, new: float, direction: str, min_improvement: float
) -> bool:
    """Compare metrics using the registry's strict improvement rule."""
    if direction == "minimize":
        return new < current - min_improvement
    if direction == "maximize":
        return new > current + min_improvement
    raise ValueError("unknown metric direction")


def aggregate_claim_rows(
    rows: list[ClaimAdjudicationResult],
    config: ClaimAdjudicationRules,
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


def claim_metrics(
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


def claim_policy_publishable(
    item: ClaimAdjudicationInputItem,
    result: ClaimAdjudicationResult,
    config: ClaimAdjudicationRules,
) -> bool:
    """Compute publication authority only from admitted evidence and Scientist policy."""
    return bool(
        item.source_basis == SourceBasis.FULLTEXT
        and not item.intra_paper_contradiction
        and bool(item.supporting_spans)
        and bool(item.method_spans)
        and result.design_family.value in STRONG_DESIGN_FAMILIES
        and result.causal_credibility in set(config.publishable_credibility_allowlist)
        and result.risk_of_bias in {RiskOfBias.LOW, RiskOfBias.MODERATE}
        and result.support_status == SupportStatus.SUPPORTED
        and result.claim_validity_score >= config.high_confidence_validity_threshold
        and result.adjudication_confidence >= config.high_confidence_confidence_threshold
    )
