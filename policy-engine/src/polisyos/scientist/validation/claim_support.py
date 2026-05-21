"""Semantic support rules for final-policy claims.

This module intentionally separates evidence support from publication state:
support strength answers "does the evidence predicate set fit this claim?",
while publishability answers "may this claim leave the current boundary now?"
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from polisyos.scientist.evidence.claims.models import ClaimPublishability
from polisyos.scientist.methods.search.readiness import DecisionReadiness

SCHEMA_VERSION = "policyos.scientist.claim_support_semantics.v1"


class ClaimFamily(str, Enum):
    """Claim families with explicit production support predicates."""

    FACTUAL = "factual"
    LEGAL = "legal"
    CAUSAL = "causal"
    NUMERICAL = "numerical"
    FORECAST = "forecast"
    DISTRIBUTIONAL = "distributional"
    WELFARE = "welfare"
    IMPLEMENTATION = "implementation"


class SupportPredicate(str, Enum):
    """Atomic predicates used to judge semantic support."""

    DATA_REF = "data_ref"
    SOURCE_ATTRIBUTION = "source_attribution"
    NORM_REF = "norm_ref"
    LEGAL_SCOPE = "legal_scope"
    METHOD_REF = "method_ref"
    IDENTIFICATION_STRATEGY = "identification_strategy"
    METHOD_OUTPUT_REF = "method_output_ref"
    NUMERIC_VALUE = "numeric_value"
    UNCERTAINTY_REF = "uncertainty_ref"
    FORECAST_HORIZON = "forecast_horizon"
    SUBGROUP_REF = "subgroup_ref"
    WELFARE_METRIC = "welfare_metric"
    IMPLEMENTATION_PLAN_REF = "implementation_plan_ref"
    FEASIBILITY_REF = "feasibility_ref"


class SupportStrength(str, Enum):
    """Evidence-support strength independent of publication state."""

    UNSUPPORTED = "unsupported"
    WEAK = "weak"
    SUPPORTED = "supported"
    STRONG = "strong"


class CounterevidenceAction(str, Enum):
    """Allowed counterevidence effects for a supported claim."""

    BLOCK = "block"
    WARN = "warn"
    LOWER_READINESS = "lower_readiness"
    REQUIRE_REVIEW = "require_review"


class LifecycleTransition(str, Enum):
    """Lifecycle transition implied by support and counterevidence."""

    READY_TO_PUBLISH = "ready_to_publish"
    REMAIN_INTERNAL = "remain_internal"
    REQUIRE_REVIEW = "require_review"
    BLOCK_PUBLICATION = "block_publication"
    LOWER_READINESS = "lower_readiness"
    WARN = "warn"


@dataclass(frozen=True)
class ClaimSupportRule:
    """Support contract for one claim family."""

    family: ClaimFamily
    required_predicates: tuple[SupportPredicate, ...]
    grounding_matrix_family: str
    grounding_matrix_checks: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class ClaimSupportAssessment:
    """Machine-readable support decision for one claim."""

    schema_version: str
    claim_id: str
    claim_family: ClaimFamily
    support_strength: SupportStrength
    publishability: ClaimPublishability
    readiness_level: DecisionReadiness
    satisfied_predicates: tuple[SupportPredicate, ...]
    missing_predicates: list[SupportPredicate]
    required_predicates: tuple[SupportPredicate, ...]
    counterevidence_actions: tuple[CounterevidenceAction, ...]
    lifecycle_transition: LifecycleTransition
    grounding_matrix_family: str
    grounding_matrix_checks: tuple[str, ...]
    issues: tuple[dict[str, Any], ...]


_READINESS_ORDER: tuple[DecisionReadiness, ...] = (
    DecisionReadiness.RESEARCH_ARTIFACT,
    DecisionReadiness.ANALYST_ADVISORY,
    DecisionReadiness.EXTERNAL_BRIEFING,
    DecisionReadiness.SIMULATION_READY,
    DecisionReadiness.RECOMMENDATION_READY,
    DecisionReadiness.DEPLOYMENT_READY,
)

_FAMILY_ALIASES = {
    "claim": ClaimFamily.FACTUAL,
    "empirical": ClaimFamily.FACTUAL,
    "evidence": ClaimFamily.FACTUAL,
    "fact": ClaimFamily.FACTUAL,
    "factual": ClaimFamily.FACTUAL,
    "legal": ClaimFamily.LEGAL,
    "normative": ClaimFamily.LEGAL,
    "compliance": ClaimFamily.LEGAL,
    "causal": ClaimFamily.CAUSAL,
    "impact": ClaimFamily.CAUSAL,
    "numeric": ClaimFamily.NUMERICAL,
    "number": ClaimFamily.NUMERICAL,
    "numerical": ClaimFamily.NUMERICAL,
    "quantitative": ClaimFamily.NUMERICAL,
    "forecast": ClaimFamily.FORECAST,
    "projection": ClaimFamily.FORECAST,
    "scenario": ClaimFamily.FORECAST,
    "distribution": ClaimFamily.DISTRIBUTIONAL,
    "distributional": ClaimFamily.DISTRIBUTIONAL,
    "equity": ClaimFamily.DISTRIBUTIONAL,
    "welfare": ClaimFamily.WELFARE,
    "cost_benefit": ClaimFamily.WELFARE,
    "implementation": ClaimFamily.IMPLEMENTATION,
    "operational": ClaimFamily.IMPLEMENTATION,
    "feasibility": ClaimFamily.IMPLEMENTATION,
}

_RULES: dict[ClaimFamily, ClaimSupportRule] = {
    ClaimFamily.FACTUAL: ClaimSupportRule(
        family=ClaimFamily.FACTUAL,
        required_predicates=(
            SupportPredicate.DATA_REF,
            SupportPredicate.SOURCE_ATTRIBUTION,
        ),
        grounding_matrix_family="empirical",
        grounding_matrix_checks=(
            "claim_family_missing_required_grounding",
            "data_claim_refs_not_selected",
        ),
        description="Factual claims require selected data/source evidence.",
    ),
    ClaimFamily.LEGAL: ClaimSupportRule(
        family=ClaimFamily.LEGAL,
        required_predicates=(
            SupportPredicate.NORM_REF,
            SupportPredicate.LEGAL_SCOPE,
        ),
        grounding_matrix_family="normative",
        grounding_matrix_checks=(
            "normative_claim_missing_applicable_norm",
            "normative_claim_refs_not_applicable",
        ),
        description="Legal claims require applicable norms plus scope facts.",
    ),
    ClaimFamily.CAUSAL: ClaimSupportRule(
        family=ClaimFamily.CAUSAL,
        required_predicates=(
            SupportPredicate.DATA_REF,
            SupportPredicate.METHOD_REF,
            SupportPredicate.IDENTIFICATION_STRATEGY,
        ),
        grounding_matrix_family="causal",
        grounding_matrix_checks=(
            "claim_family_missing_required_grounding",
            "data_claim_refs_not_selected",
            "method_claim_refs_not_selected",
        ),
        description="Causal claims require data, method output, and design.",
    ),
    ClaimFamily.NUMERICAL: ClaimSupportRule(
        family=ClaimFamily.NUMERICAL,
        required_predicates=(
            SupportPredicate.METHOD_REF,
            SupportPredicate.METHOD_OUTPUT_REF,
            SupportPredicate.NUMERIC_VALUE,
        ),
        grounding_matrix_family="numerical",
        grounding_matrix_checks=(
            "numeric_claim_unreadable",
            "numeric_claim_missing_method_output",
            "numeric_claim_mismatch",
            "method_claim_refs_not_selected",
        ),
        description="Numerical claims must be traceable to method outputs.",
    ),
    ClaimFamily.FORECAST: ClaimSupportRule(
        family=ClaimFamily.FORECAST,
        required_predicates=(
            SupportPredicate.METHOD_REF,
            SupportPredicate.UNCERTAINTY_REF,
            SupportPredicate.FORECAST_HORIZON,
        ),
        grounding_matrix_family="forecast",
        grounding_matrix_checks=(
            "claim_family_missing_required_grounding",
            "method_claim_refs_not_selected",
        ),
        description="Forecast claims require model evidence, horizon, and uncertainty.",
    ),
    ClaimFamily.DISTRIBUTIONAL: ClaimSupportRule(
        family=ClaimFamily.DISTRIBUTIONAL,
        required_predicates=(
            SupportPredicate.METHOD_REF,
            SupportPredicate.SUBGROUP_REF,
        ),
        grounding_matrix_family="distributional",
        grounding_matrix_checks=(
            "claim_family_missing_required_grounding",
            "method_claim_refs_not_selected",
        ),
        description="Distributional claims require subgroup-level method evidence.",
    ),
    ClaimFamily.WELFARE: ClaimSupportRule(
        family=ClaimFamily.WELFARE,
        required_predicates=(
            SupportPredicate.METHOD_REF,
            SupportPredicate.WELFARE_METRIC,
        ),
        grounding_matrix_family="causal",
        grounding_matrix_checks=(
            "claim_family_missing_required_grounding",
            "method_claim_refs_not_selected",
        ),
        description="Welfare claims require welfare metrics grounded in methods.",
    ),
    ClaimFamily.IMPLEMENTATION: ClaimSupportRule(
        family=ClaimFamily.IMPLEMENTATION,
        required_predicates=(
            SupportPredicate.IMPLEMENTATION_PLAN_REF,
            SupportPredicate.FEASIBILITY_REF,
        ),
        grounding_matrix_family="implementation",
        grounding_matrix_checks=(
            "major_claim_missing_grounding_rationale",
            "minor_claim_missing_grounding_rationale",
        ),
        description="Implementation claims require rollout and feasibility evidence.",
    ),
}


def claim_support_rules() -> dict[ClaimFamily, ClaimSupportRule]:
    """Return the production support rules keyed by claim family."""

    return dict(_RULES)


def grounding_matrix_family_for_claim_family(family: ClaimFamily | str) -> str:
    """Return the final policy-grounding family used for this support family."""

    return _rule_for_family(family).grounding_matrix_family


def grounding_matrix_checks_for_family(family: ClaimFamily | str) -> tuple[str, ...]:
    """Return policy-grounding matrix issue codes relevant to this family."""

    return _rule_for_family(family).grounding_matrix_checks


def evaluate_claim_support(
    claim: Mapping[str, Any],
    *,
    base_readiness: DecisionReadiness | str = DecisionReadiness.RESEARCH_ARTIFACT,
    counterevidence: Sequence[Mapping[str, Any]] | None = None,
) -> ClaimSupportAssessment:
    """Evaluate semantic support, publication state, and lifecycle transition."""

    family = _claim_family(claim)
    rule = _RULES[family]
    readiness = _readiness(base_readiness)
    claim_id = _text(claim.get("claim_id") or claim.get("id") or family.value)
    satisfied = _satisfied_predicates(claim)
    missing = [
        predicate
        for predicate in rule.required_predicates
        if predicate not in satisfied
    ]
    support_strength = _support_strength(rule=rule, satisfied=satisfied, missing=missing)
    issues: list[dict[str, Any]] = []
    counter_actions: list[CounterevidenceAction] = []

    if missing:
        issues.append(
            _issue(
                code="claim_support_missing_required_predicates",
                severity="warn" if support_strength is SupportStrength.WEAK else "fail",
                claim_id=claim_id,
                claim_family=family,
                message=(
                    f"{family.value} claim {claim_id} is missing required support "
                    f"predicates: {', '.join(item.value for item in missing)}."
                ),
                missing_predicates=[item.value for item in missing],
                grounding_matrix_checks=list(rule.grounding_matrix_checks),
                next_action=(
                    "Attach the semantic evidence predicates required for this "
                    "claim family before treating it as publication-ready."
                ),
            )
        )

    publishability = _publishability_for_support(
        support_strength=support_strength,
        readiness=readiness,
    )

    for item in counterevidence or ():
        action = _counterevidence_action(item)
        counter_actions.append(action)
        if action is CounterevidenceAction.LOWER_READINESS:
            readiness = _lowered_readiness(readiness, item)
        issues.append(_counterevidence_issue(claim_id, family, item, action))

    publishability = _publishability_after_counterevidence(
        publishability,
        counter_actions=counter_actions,
        support_strength=support_strength,
        readiness=readiness,
    )
    lifecycle_transition = _lifecycle_transition(
        publishability=publishability,
        counter_actions=counter_actions,
    )

    return ClaimSupportAssessment(
        schema_version=SCHEMA_VERSION,
        claim_id=claim_id,
        claim_family=family,
        support_strength=support_strength,
        publishability=publishability,
        readiness_level=readiness,
        satisfied_predicates=tuple(
            predicate
            for predicate in SupportPredicate
            if predicate in satisfied
        ),
        missing_predicates=missing,
        required_predicates=rule.required_predicates,
        counterevidence_actions=tuple(counter_actions),
        lifecycle_transition=lifecycle_transition,
        grounding_matrix_family=rule.grounding_matrix_family,
        grounding_matrix_checks=rule.grounding_matrix_checks,
        issues=tuple(issues),
    )


def _rule_for_family(family: ClaimFamily | str) -> ClaimSupportRule:
    return _RULES[_normalize_family(family)]


def _claim_family(claim: Mapping[str, Any]) -> ClaimFamily:
    raw_family = (
        claim.get("claim_family")
        or claim.get("family")
        or claim.get("claim_type")
        or claim.get("type")
    )
    if raw_family:
        return _normalize_family(raw_family)
    if _has_numeric_value(claim):
        return ClaimFamily.NUMERICAL
    return ClaimFamily.FACTUAL


def _normalize_family(value: ClaimFamily | str) -> ClaimFamily:
    if isinstance(value, ClaimFamily):
        return value
    token = _text(value).casefold().replace("-", "_").replace(" ", "_")
    token = "_".join(part for part in token.split("_") if part)
    if token in _FAMILY_ALIASES:
        return _FAMILY_ALIASES[token]
    try:
        return ClaimFamily(token)
    except ValueError as exc:
        raise ValueError(f"unsupported claim family: {value!r}") from exc


def _text(value: object) -> str:
    return str(value or "").strip()


def _as_sequence(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if _text(value) else []
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [item for item in value if _text(item)]
    return [value] if _text(value) else []


def _has_any(claim: Mapping[str, Any], *keys: str) -> bool:
    return any(_as_sequence(claim.get(key)) for key in keys)


def _has_numeric_value(claim: Mapping[str, Any]) -> bool:
    nested = claim.get("numeric_claim")
    nested_mapping = nested if isinstance(nested, Mapping) else {}
    metric = _text(claim.get("metric") or nested_mapping.get("metric"))
    value = (
        claim.get("value")
        if "value" in claim
        else claim.get("numeric_value")
        if "numeric_value" in claim
        else nested_mapping.get("value")
    )
    return bool(metric and value is not None and not isinstance(value, bool))


def _has_legal_scope(claim: Mapping[str, Any]) -> bool:
    if _has_any(claim, "legal_scope", "scope_refs", "jurisdiction_refs"):
        return True
    jurisdiction = _text(claim.get("jurisdiction") or claim.get("legal_jurisdiction"))
    effective_date = _text(
        claim.get("effective_date")
        or claim.get("as_of_date")
        or claim.get("norm_date")
        or claim.get("legal_date")
    )
    return bool(jurisdiction and effective_date)


def _satisfied_predicates(claim: Mapping[str, Any]) -> set[SupportPredicate]:
    satisfied: set[SupportPredicate] = set()
    if _has_any(
        claim,
        "data_refs",
        "data_source_refs",
        "source_refs",
        "fabric_refs",
        "data_snapshot_refs",
    ):
        satisfied.add(SupportPredicate.DATA_REF)
    if _has_any(claim, "source_attribution", "citation_refs", "source_ids"):
        satisfied.add(SupportPredicate.SOURCE_ATTRIBUTION)
    if _has_any(claim, "norm_refs", "normative_refs", "norm_ids", "legal_refs"):
        satisfied.add(SupportPredicate.NORM_REF)
    if _has_legal_scope(claim):
        satisfied.add(SupportPredicate.LEGAL_SCOPE)
    if _has_any(claim, "method_refs", "foundry_method_refs", "analysis_refs"):
        satisfied.add(SupportPredicate.METHOD_REF)
    if _has_any(
        claim,
        "identification_strategy",
        "identification_refs",
        "causal_design",
        "design_refs",
    ):
        satisfied.add(SupportPredicate.IDENTIFICATION_STRATEGY)
    if _has_any(
        claim,
        "method_output_refs",
        "output_refs",
        "result_refs",
        "analysis_output_refs",
    ):
        satisfied.add(SupportPredicate.METHOD_OUTPUT_REF)
    if _has_numeric_value(claim):
        satisfied.add(SupportPredicate.NUMERIC_VALUE)
    if _has_any(
        claim,
        "uncertainty_refs",
        "uncertainty_profile_ref",
        "interval_refs",
        "prediction_interval_refs",
    ):
        satisfied.add(SupportPredicate.UNCERTAINTY_REF)
    if _has_any(claim, "forecast_horizon", "horizon", "time_horizon"):
        satisfied.add(SupportPredicate.FORECAST_HORIZON)
    if _has_any(
        claim,
        "subgroup_refs",
        "cohort_refs",
        "population_refs",
        "distributional_refs",
    ):
        satisfied.add(SupportPredicate.SUBGROUP_REF)
    if _has_any(
        claim,
        "welfare_metric",
        "welfare_metrics",
        "welfare_analysis_refs",
        "social_welfare_function",
    ):
        satisfied.add(SupportPredicate.WELFARE_METRIC)
    if _has_any(
        claim,
        "implementation_plan_refs",
        "implementation_refs",
        "rollout_plan_refs",
    ):
        satisfied.add(SupportPredicate.IMPLEMENTATION_PLAN_REF)
    if _has_any(
        claim,
        "feasibility_refs",
        "capacity_refs",
        "budget_refs",
        "delivery_risk_refs",
    ):
        satisfied.add(SupportPredicate.FEASIBILITY_REF)
    return satisfied


def _support_strength(
    *,
    rule: ClaimSupportRule,
    satisfied: set[SupportPredicate],
    missing: Sequence[SupportPredicate],
) -> SupportStrength:
    if not missing:
        if _has_strong_support(rule, satisfied):
            return SupportStrength.STRONG
        return SupportStrength.SUPPORTED
    if len(missing) < len(rule.required_predicates):
        return SupportStrength.WEAK
    return SupportStrength.UNSUPPORTED


def _has_strong_support(
    rule: ClaimSupportRule,
    satisfied: set[SupportPredicate],
) -> bool:
    if rule.family in {ClaimFamily.CAUSAL, ClaimFamily.WELFARE}:
        return {
            SupportPredicate.DATA_REF,
            SupportPredicate.METHOD_REF,
            SupportPredicate.UNCERTAINTY_REF,
        }.issubset(satisfied)
    if rule.family is ClaimFamily.FORECAST:
        return {
            SupportPredicate.METHOD_REF,
            SupportPredicate.UNCERTAINTY_REF,
            SupportPredicate.DATA_REF,
        }.issubset(satisfied)
    return False


def _readiness(value: DecisionReadiness | str) -> DecisionReadiness:
    if isinstance(value, DecisionReadiness):
        return value
    return DecisionReadiness(_text(value))


def _readiness_rank(level: DecisionReadiness) -> int:
    return _READINESS_ORDER.index(level)


def _readiness_at_least(level: DecisionReadiness, minimum: DecisionReadiness) -> bool:
    return _readiness_rank(level) >= _readiness_rank(minimum)


def _publishability_for_support(
    *,
    support_strength: SupportStrength,
    readiness: DecisionReadiness,
) -> ClaimPublishability:
    if support_strength in {SupportStrength.UNSUPPORTED, SupportStrength.WEAK}:
        return ClaimPublishability.REVIEW_REQUIRED
    if _readiness_at_least(readiness, DecisionReadiness.ANALYST_ADVISORY):
        return ClaimPublishability.PUBLISHABLE
    return ClaimPublishability.INTERNAL_ONLY


def _counterevidence_action(item: Mapping[str, Any]) -> CounterevidenceAction:
    raw = _text(item.get("action") or item.get("effect") or item.get("disposition"))
    token = raw.casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "blocked": CounterevidenceAction.BLOCK,
        "blocking": CounterevidenceAction.BLOCK,
        "fail": CounterevidenceAction.BLOCK,
        "warning": CounterevidenceAction.WARN,
        "lower": CounterevidenceAction.LOWER_READINESS,
        "downgrade": CounterevidenceAction.LOWER_READINESS,
        "review": CounterevidenceAction.REQUIRE_REVIEW,
        "requires_review": CounterevidenceAction.REQUIRE_REVIEW,
    }
    if token in aliases:
        return aliases[token]
    return CounterevidenceAction(token or CounterevidenceAction.REQUIRE_REVIEW.value)


def _lowered_readiness(
    readiness: DecisionReadiness,
    item: Mapping[str, Any],
) -> DecisionReadiness:
    explicit_floor = item.get("readiness_floor") or item.get("max_readiness")
    if explicit_floor:
        floor = _readiness(str(explicit_floor))
        return floor if _readiness_rank(readiness) > _readiness_rank(floor) else readiness
    rank = max(0, _readiness_rank(readiness) - 1)
    return _READINESS_ORDER[rank]


def _publishability_after_counterevidence(
    publishability: ClaimPublishability,
    *,
    counter_actions: Sequence[CounterevidenceAction],
    support_strength: SupportStrength,
    readiness: DecisionReadiness,
) -> ClaimPublishability:
    if CounterevidenceAction.BLOCK in counter_actions:
        return ClaimPublishability.BLOCKED
    if CounterevidenceAction.REQUIRE_REVIEW in counter_actions:
        return ClaimPublishability.REVIEW_REQUIRED
    if publishability is ClaimPublishability.PUBLISHABLE and not _readiness_at_least(
        readiness,
        DecisionReadiness.ANALYST_ADVISORY,
    ):
        return ClaimPublishability.INTERNAL_ONLY
    if support_strength in {SupportStrength.UNSUPPORTED, SupportStrength.WEAK}:
        return ClaimPublishability.REVIEW_REQUIRED
    return publishability


def _lifecycle_transition(
    *,
    publishability: ClaimPublishability,
    counter_actions: Sequence[CounterevidenceAction],
) -> LifecycleTransition:
    if publishability is ClaimPublishability.BLOCKED:
        return LifecycleTransition.BLOCK_PUBLICATION
    if publishability is ClaimPublishability.REVIEW_REQUIRED:
        return LifecycleTransition.REQUIRE_REVIEW
    if CounterevidenceAction.LOWER_READINESS in counter_actions:
        return LifecycleTransition.LOWER_READINESS
    if CounterevidenceAction.WARN in counter_actions:
        return LifecycleTransition.WARN
    if publishability is ClaimPublishability.PUBLISHABLE:
        return LifecycleTransition.READY_TO_PUBLISH
    return LifecycleTransition.REMAIN_INTERNAL


def _counterevidence_issue(
    claim_id: str,
    family: ClaimFamily,
    item: Mapping[str, Any],
    action: CounterevidenceAction,
) -> dict[str, Any]:
    code_by_action = {
        CounterevidenceAction.BLOCK: "counterevidence_blocks_claim",
        CounterevidenceAction.WARN: "counterevidence_warns_claim",
        CounterevidenceAction.LOWER_READINESS: "counterevidence_lowers_readiness",
        CounterevidenceAction.REQUIRE_REVIEW: "counterevidence_requires_review",
    }
    severity_by_action = {
        CounterevidenceAction.BLOCK: "fail",
        CounterevidenceAction.WARN: "warn",
        CounterevidenceAction.LOWER_READINESS: "warn",
        CounterevidenceAction.REQUIRE_REVIEW: "review",
    }
    return _issue(
        code=code_by_action[action],
        severity=severity_by_action[action],
        claim_id=claim_id,
        claim_family=family,
        message=_text(item.get("reason") or item.get("message"))
        or f"Counterevidence action {action.value} applies to claim {claim_id}.",
        counterevidence_id=_text(
            item.get("counterevidence_id")
            or item.get("id")
            or item.get("evidence_ref")
        )
        or None,
        counterevidence_action=action.value,
        next_action=_counterevidence_next_action(action),
    )


def _counterevidence_next_action(action: CounterevidenceAction) -> str:
    if action is CounterevidenceAction.BLOCK:
        return "Do not publish the claim until the contradiction is resolved."
    if action is CounterevidenceAction.WARN:
        return "Surface the limitation next to the claim and keep monitoring it."
    if action is CounterevidenceAction.LOWER_READINESS:
        return "Downgrade readiness and withhold stronger deployment claims."
    return "Route the claim to a human reviewer before external publication."


def _issue(
    *,
    code: str,
    severity: str,
    claim_id: str,
    claim_family: ClaimFamily,
    message: str,
    next_action: str,
    **extra: object,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "layer": "scientist_policy_artifacts",
        "phase": "claim_support_semantics",
        "claim_id": claim_id,
        "claim_family": claim_family.value,
        "message": message,
        "next_action": next_action,
        **extra,
    }


__all__ = [
    "SCHEMA_VERSION",
    "ClaimFamily",
    "ClaimPublishability",
    "ClaimSupportAssessment",
    "ClaimSupportRule",
    "CounterevidenceAction",
    "LifecycleTransition",
    "SupportPredicate",
    "SupportStrength",
    "claim_support_rules",
    "evaluate_claim_support",
    "grounding_matrix_checks_for_family",
    "grounding_matrix_family_for_claim_family",
]
