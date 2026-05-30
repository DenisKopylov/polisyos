"""Deterministic intent normalization for W6.A grammar compilation."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir import governance, observation

from .schema import PolicyGrammarIntent

IdentificationMode = observation.IdentificationMode
ProblemDomain = governance.ProblemDomain

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


class NormalizedPolicyIntent(BaseModel):
    """Normalized, non-authoritative view of a policy intent."""

    model_config = ConfigDict(extra="forbid")

    intent_id: str = Field(min_length=1)
    tokens: tuple[str, ...] = Field(default=())
    domain: ProblemDomain | None = None
    intervention_kinds: tuple[str, ...] = Field(default=())
    target_population_terms: tuple[str, ...] = Field(default=())
    target_region_terms: tuple[str, ...] = Field(default=())
    identification_modes: tuple[IdentificationMode, ...] = Field(default=())
    source_contract_refs: tuple[str, ...] = Field(default=())

    def has_any(self, *needles: str) -> bool:
        """Return whether any normalized token contains one of the provided needles."""
        haystack = " ".join(self.tokens)
        return any(needle in haystack for needle in needles)


def normalise_intent(intent: PolicyGrammarIntent) -> NormalizedPolicyIntent:
    """Normalize free-text and existing policy-design contracts into compiler tokens."""
    text_parts: list[str] = []
    if intent.text:
        text_parts.append(intent.text)
    if intent.problem_frame is not None:
        text_parts.extend(
            [
                intent.problem_frame.problem_id,
                intent.problem_frame.domain.value,
                intent.problem_frame.narrative or "",
                " ".join(intent.problem_frame.labels),
                " ".join(objective.metric_id for objective in intent.problem_frame.objectives),
                " ".join(kpi.metric_id for kpi in intent.problem_frame.kpis),
            ]
        )
    intervention_kinds: list[str] = []
    target_population_terms: list[str] = []
    target_region_terms: list[str] = []
    identification_modes: list[IdentificationMode] = []
    if intent.policy_spec is not None:
        text_parts.extend([intent.policy_spec.policy_id, intent.policy_spec.description or ""])
        for intervention in intent.policy_spec.interventions:
            intervention_kinds.append(intervention.kind)
            text_parts.append(intervention.kind)
            if intervention.target_population_type:
                target_population_terms.append(intervention.target_population_type)
                text_parts.append(intervention.target_population_type)
            target_region_terms.extend(intervention.target_region_ids)
            text_parts.extend(intervention.target_region_ids)
            text_parts.extend(intervention.params.keys())
            if any("budget" in key for key in intervention.params):
                text_parts.append("budget")
            duration_steps = getattr(intervention.schedule, "duration_steps", None)
            if isinstance(duration_steps, int) and duration_steps >= 12:
                text_parts.append("annual")
            if intervention.identification_mode is not None:
                identification_modes.append(intervention.identification_mode)
    if intent.candidate is not None:
        target_population_terms.append(intent.candidate.target_population.population_id)
        text_parts.append(intent.candidate.target_population.population_id)
        text_parts.append(intent.candidate.target_population.description)
        if intent.candidate.target_population.geography:
            target_region_terms.append(intent.candidate.target_population.geography)
            text_parts.append(intent.candidate.target_population.geography)

    tokens = tuple(_TOKEN_RE.findall(" ".join(text_parts).lower().replace("-", "_")))
    return NormalizedPolicyIntent(
        intent_id=intent.intent_id,
        tokens=tokens,
        domain=intent.domain or (intent.problem_frame.domain if intent.problem_frame else None),
        intervention_kinds=tuple(_dedupe(intervention_kinds)),
        target_population_terms=tuple(_dedupe(target_population_terms)),
        target_region_terms=tuple(_dedupe(target_region_terms)),
        identification_modes=tuple(_dedupe(identification_modes)),
        source_contract_refs=_source_contract_refs(intent),
    )


def _source_contract_refs(intent: PolicyGrammarIntent) -> tuple[str, ...]:
    refs = [
        "polisyos.ir.governance.problem_frame.ProblemFrame",
        "polisyos.ir.governance.problem_frame.ProblemDomain",
        "polisyos.ir.governance.policy_spec.PolicySpec",
        "polisyos.scientist.policy_design.schema.PolicyCandidateSchema",
        "polisyos.scientist.policy_design.critic.ConstraintCritic",
        "polisyos.scientist.evals.challenge_factory.ChallengeClass",
        "polisyos.ir.governance.temporal_logic.TemporalPolicyConstraint",
    ]
    if intent.problem_frame is None:
        refs.append("ProblemFrame:not_provided")
    if intent.policy_spec is None:
        refs.append("PolicySpec:not_provided")
    if intent.candidate is None:
        refs.append("PolicyCandidateSchema:not_provided")
    return tuple(refs)


def _dedupe[T](values: list[T]) -> list[T]:
    deduped: list[T] = []
    for value in values:
        if value in deduped:
            continue
        deduped.append(value)
    return deduped


__all__ = ["NormalizedPolicyIntent", "normalise_intent"]
