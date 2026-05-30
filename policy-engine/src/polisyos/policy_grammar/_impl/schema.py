"""Input and artifact models for the universal policy grammar compiler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import artifacts, contracts
from polisyos.ir import governance
from polisyos.scientist import policy_design

ArtifactRef = artifacts.ArtifactRef
PolicyCandidateSchema = policy_design.PolicyCandidateSchema
PolicySpec = governance.PolicySpec
ProblemDomain = governance.ProblemDomain
ProblemFrame = governance.ProblemFrame
UniversalAuthorityProfile = contracts.UniversalAuthorityProfile
UniversalPolicyDesignCase = contracts.UniversalPolicyDesignCase
UniversalPolicyFacetName = contracts.UniversalPolicyFacetName


class PolicyGrammarIntent(BaseModel):
    """Policy intent accepted by the deterministic W6.A compiler."""

    model_config = ConfigDict(extra="forbid")

    intent_id: str = Field(min_length=1)
    text: str | None = Field(default=None, min_length=1)
    domain: ProblemDomain | None = None
    problem_frame: ProblemFrame | None = None
    policy_spec: PolicySpec | None = None
    candidate: PolicyCandidateSchema | None = None

    @classmethod
    def from_problem_policy(
        cls,
        *,
        intent_id: str,
        problem_frame: ProblemFrame,
        policy_spec: PolicySpec,
        candidate: PolicyCandidateSchema | None = None,
    ) -> PolicyGrammarIntent:
        """Build an intent from existing Trinity policy-design contracts."""
        text_parts = [
            problem_frame.narrative or "",
            policy_spec.description or "",
            " ".join(policy_spec.labels),
            " ".join(intervention.kind for intervention in policy_spec.interventions),
            " ".join(
                intervention.target_population_type or ""
                for intervention in policy_spec.interventions
            ),
            " ".join(
                region
                for intervention in policy_spec.interventions
                for region in intervention.target_region_ids
            ),
        ]
        text = " ".join(part for part in text_parts if part).strip() or None
        return cls(
            intent_id=intent_id,
            text=text,
            domain=problem_frame.domain,
            problem_frame=problem_frame,
            policy_spec=policy_spec,
            candidate=candidate,
        )

    @model_validator(mode="after")
    def _validate_source(self) -> PolicyGrammarIntent:
        if self.text is None and self.problem_frame is None and self.policy_spec is None:
            raise ValueError("policy grammar intent requires text, ProblemFrame, or PolicySpec")
        return self


class PolicyGrammarConceptSpineRefs(BaseModel):
    """Concept-spine and jurisdiction refs consumed by the compiler."""

    model_config = ConfigDict(extra="forbid")

    concept_spine_ref: str = Field(min_length=1)
    jurisdiction_spine_ref: str = Field(min_length=1)
    canonical_concept_refs: tuple[str, ...] = Field(default=())
    facet_concept_refs: Mapping[UniversalPolicyFacetName, tuple[str, ...]] = Field(
        default_factory=dict
    )

    @field_validator("canonical_concept_refs")
    @classmethod
    def _validate_canonical_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_ref_tuple(values)

    @field_validator("facet_concept_refs")
    @classmethod
    def _validate_facet_refs(
        cls,
        values: Mapping[UniversalPolicyFacetName, tuple[str, ...]],
    ) -> Mapping[UniversalPolicyFacetName, tuple[str, ...]]:
        return {key: _clean_ref_tuple(refs) for key, refs in values.items()}

    def refs_for(self, facet_name: UniversalPolicyFacetName) -> tuple[str, ...]:
        """Return concept refs for one facet, falling back to canonical refs."""
        return tuple(self.facet_concept_refs.get(facet_name, ())) or self.canonical_concept_refs


class CompiledUniversalPolicyDesignCaseArtifact(BaseModel):
    """Persisted W6.A artifact handle and validated compiled case."""

    model_config = ConfigDict(extra="forbid")

    case: UniversalPolicyDesignCase
    artifact_ref: ArtifactRef


def authority_profile_from_mapping(payload: Mapping[str, Any]) -> UniversalAuthorityProfile:
    """Validate a mapping as a universal authority profile."""
    return UniversalAuthorityProfile.model_validate(dict(payload))


def _clean_ref_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return tuple(cleaned)


__all__ = [
    "CompiledUniversalPolicyDesignCaseArtifact",
    "PolicyGrammarConceptSpineRefs",
    "PolicyGrammarIntent",
    "authority_profile_from_mapping",
]
