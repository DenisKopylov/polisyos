"""Compile policy intent, facets, and obligations into typed claim seeds."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.participation_requirement import (
    ParticipationRequirementBundle,
    compile_participation_requirements,
)
from polisyos.scientist.evidence.claims.models import (
    AlternativeRecord,
    AlternativeRejectionReason,
    AlternativeStatus,
    BaselineRecord,
    BaselineType,
    ClaimFamily,
    ClaimFamilyAssignment,
    ClaimLedger,
    ClaimPublishability,
    ClaimRecord,
    ClaimSourceClass,
    ClaimSupportStatus,
    ClaimType,
    ClaimUse,
    MethodNeedPrecondition,
)
from polisyos.scientist.methods.search.readiness import DecisionReadiness

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


_LLM_SOURCE_CLASSES = {
    ClaimSourceClass.LLM_CANDIDATE,
    ClaimSourceClass.LLM_CRITIC,
    ClaimSourceClass.LLM_DRAFTER,
}


class ClaimDecompositionFacet(BaseModel):
    """Compiler input facet from the universal policy grammar layer."""

    model_config = ConfigDict(extra="forbid")

    facet_id: str = Field(min_length=1)
    facet_type: str = Field(min_length=1)
    value: str = Field(min_length=1)
    description: str | None = None
    concept_spine_refs: list[str] = Field(default_factory=list)
    authority_profile_refs: list[str] = Field(default_factory=list)
    source_class: ClaimSourceClass = ClaimSourceClass.DETERMINISTIC_COMPILER
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimDecompositionObligation(BaseModel):
    """Compiler input obligation from the obligation graph frontier."""

    model_config = ConfigDict(extra="forbid")

    obligation_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    description: str = Field(min_length=1)
    facet_refs: list[str] = Field(default_factory=list)
    concept_spine_refs: list[str] = Field(default_factory=list)
    authority_profile_refs: list[str] = Field(default_factory=list)
    source_class: ClaimSourceClass = ClaimSourceClass.DETERMINISTIC_COMPILER
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimDecompositionNamedAlternative(BaseModel):
    """Seed input for a named alternative before W8 comparison evidence exists."""

    model_config = ConfigDict(extra="forbid")

    alternative_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: AlternativeStatus = AlternativeStatus.SEED
    rejected_reasons: list[AlternativeRejectionReason] = Field(default_factory=list)
    facet_refs: list[str] = Field(default_factory=list)
    obligation_refs: list[str] = Field(default_factory=list)
    concept_spine_refs: list[str] = Field(default_factory=list)
    authority_profile_refs: list[str] = Field(default_factory=list)
    source_class: ClaimSourceClass = ClaimSourceClass.DETERMINISTIC_COMPILER
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_status_reason(self) -> ClaimDecompositionNamedAlternative:
        if self.status is AlternativeStatus.REJECTED and not self.rejected_reasons:
            raise ValueError("rejected named alternatives require rejected_reasons")
        if self.status is not AlternativeStatus.REJECTED and self.rejected_reasons:
            raise ValueError("only rejected named alternatives may carry rejected_reasons")
        return self


class ClaimDecompositionInput(BaseModel):
    """Input packet consumed by the W6.D deterministic compiler."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    facets: list[ClaimDecompositionFacet] = Field(min_length=1)
    obligations: list[ClaimDecompositionObligation] = Field(min_length=1)
    named_alternatives: list[ClaimDecompositionNamedAlternative] = Field(default_factory=list)
    concept_spine_refs: list[str] = Field(default_factory=list)
    authority_profile_refs: list[str] = Field(default_factory=list)
    created_by_node_id: str = (
        "polisyos.scientist.policy_design.claim_decomposition.ClaimDecompositionCompiler"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_unique_input_ids(self) -> ClaimDecompositionInput:
        _validate_unique([facet.facet_id for facet in self.facets], "facet_id")
        _validate_unique(
            [obligation.obligation_id for obligation in self.obligations],
            "obligation_id",
        )
        _validate_unique(
            [alternative.alternative_id for alternative in self.named_alternatives],
            "alternative_id",
        )
        facet_ids = {facet.facet_id for facet in self.facets}
        for obligation in self.obligations:
            missing = sorted(set(obligation.facet_refs) - facet_ids)
            if missing:
                raise ValueError(
                    f"obligation '{obligation.obligation_id}' references unknown facet_refs "
                    f"{missing}"
                )
        return self


class ClaimDecompositionCompiler:
    """Deterministic compiler for W6.D claim-family and comparator seed records."""

    def compile(self, payload: ClaimDecompositionInput | Mapping[str, Any]) -> ClaimLedger:
        """Compile a policy-design input packet into a claim ledger."""

        item = (
            payload
            if isinstance(payload, ClaimDecompositionInput)
            else ClaimDecompositionInput.model_validate(payload)
        )
        baseline_records = self._compile_baselines(item)
        alternative_records = self._compile_alternatives(item)
        claims: list[ClaimRecord] = []

        for facet in item.facets:
            claims.append(self._claim_for_facet(item, facet))
        for obligation in item.obligations:
            claims.append(self._claim_for_obligation(item, obligation))
        if alternative_records:
            claims.append(
                self._superiority_claim(
                    item,
                    baseline_records=baseline_records,
                    alternative_records=alternative_records,
                )
            )

        claims = _dedupe_claims(claims)
        assignments = [
            _assignment_for_claim(run_id=item.run_id, claim=claim)
            for claim in claims
            if claim.claim_family is not None and claim.claim_use is not None
        ]
        return ClaimLedger(
            run_id=item.run_id,
            claims=claims,
            family_assignments=assignments,
            baseline_records=baseline_records,
            alternative_records=alternative_records,
            created_by_node_id=item.created_by_node_id,
            metadata={
                "producer": "claim_decomposition_compiler",
                "capability_reality_label": "implemented",
                "pattern_guards": ["P02", "P15"],
                "intent_digest": _digest({"intent": item.intent}),
                **dict(item.metadata),
            },
        )

    def _claim_for_facet(
        self,
        item: ClaimDecompositionInput,
        facet: ClaimDecompositionFacet,
    ) -> ClaimRecord:
        family = _family_for_facet(facet)
        claim_use = _use_for_family(family)
        claim_type = _type_for_family(family)
        blocked_reasons: list[str] = []
        publishability = ClaimPublishability.DRAFT
        if facet.source_class in _LLM_SOURCE_CLASSES:
            family = ClaimFamily.CONTEXT_ONLY
            claim_type = ClaimType.FACTUAL
            claim_use = ClaimUse.CONTEXT_ONLY
            blocked_reasons.append("candidate_source_not_authority")
            publishability = ClaimPublishability.BLOCKED
        return _build_claim(
            run_id=item.run_id,
            family=family,
            claim_type=claim_type,
            claim_use=claim_use,
            text=f"Facet {facet.facet_type} requires claim coverage for {facet.value}.",
            source_label=f"claim_decomposition.facet.{facet.facet_id}",
            facet_refs=[facet.facet_id],
            obligation_refs=_related_obligation_refs(item, [facet.facet_id]),
            concept_spine_refs=_with_fallback(facet.concept_spine_refs, _all_concept_refs(item)),
            authority_profile_refs=_with_fallback(
                facet.authority_profile_refs,
                _all_authority_refs(item),
            ),
            source_class=facet.source_class,
            publishability=publishability,
            blocked_reasons=blocked_reasons,
        )

    def _claim_for_obligation(
        self,
        item: ClaimDecompositionInput,
        obligation: ClaimDecompositionObligation,
    ) -> ClaimRecord:
        family = _family_for_obligation(obligation)
        claim_use = _use_for_family(family)
        claim_type = _type_for_family(family)
        blocked_reasons: list[str] = []
        publishability = ClaimPublishability.DRAFT
        if obligation.source_class in _LLM_SOURCE_CLASSES:
            family = ClaimFamily.CONTEXT_ONLY
            claim_type = ClaimType.FACTUAL
            claim_use = ClaimUse.CONTEXT_ONLY
            blocked_reasons.append("candidate_source_not_authority")
            publishability = ClaimPublishability.BLOCKED
        facet_refs = _with_fallback(obligation.facet_refs, _all_facet_refs(item))
        return _build_claim(
            run_id=item.run_id,
            family=family,
            claim_type=claim_type,
            claim_use=claim_use,
            text=f"Obligation {obligation.obligation_id}: {obligation.description}",
            source_label=f"claim_decomposition.obligation.{obligation.obligation_id}",
            facet_refs=facet_refs,
            obligation_refs=[obligation.obligation_id],
            concept_spine_refs=_with_fallback(
                obligation.concept_spine_refs,
                _concept_refs_for_facets(item, facet_refs),
            ),
            authority_profile_refs=_with_fallback(
                obligation.authority_profile_refs,
                _authority_refs_for_facets(item, facet_refs),
            ),
            source_class=obligation.source_class,
            publishability=publishability,
            blocked_reasons=blocked_reasons,
        )

    def _superiority_claim(
        self,
        item: ClaimDecompositionInput,
        *,
        baseline_records: list[BaselineRecord],
        alternative_records: list[AlternativeRecord],
    ) -> ClaimRecord:
        return _build_claim(
            run_id=item.run_id,
            family=ClaimFamily.WELFARE,
            claim_type=ClaimType.WELFARE,
            claim_use=ClaimUse.SUPERIORITY,
            text=(
                "Selected policy option must be compared against no-action, status quo, "
                "business-as-usual, and named alternatives before superiority is claimed."
            ),
            source_label="claim_decomposition.superiority",
            facet_refs=_all_facet_refs(item),
            obligation_refs=_all_obligation_refs(item),
            concept_spine_refs=_all_concept_refs(item),
            authority_profile_refs=_all_authority_refs(item),
            source_class=ClaimSourceClass.DETERMINISTIC_COMPILER,
            baseline_refs=[record.baseline_id for record in baseline_records],
            alternative_refs=[record.alternative_id for record in alternative_records],
            extra_method_needs=["frontier_comparison"],
        )

    def _compile_baselines(self, item: ClaimDecompositionInput) -> list[BaselineRecord]:
        facet_refs = _all_facet_refs(item)
        obligation_refs = _all_obligation_refs(item)
        concept_refs = _all_concept_refs(item)
        authority_refs = _all_authority_refs(item)
        records = [
            _baseline(
                item,
                BaselineType.NO_ACTION,
                "No action",
                "No new policy intervention is implemented.",
                facet_refs,
                obligation_refs,
                concept_refs,
                authority_refs,
            ),
            _baseline(
                item,
                BaselineType.STATUS_QUO,
                "Status quo",
                "Current policy and administrative practice continue.",
                facet_refs,
                obligation_refs,
                concept_refs,
                authority_refs,
            ),
            _baseline(
                item,
                BaselineType.BUSINESS_AS_USUAL,
                "Business as usual",
                "Expected trajectory continues without the proposed design change.",
                facet_refs,
                obligation_refs,
                concept_refs,
                authority_refs,
            ),
        ]
        for alternative in item.named_alternatives:
            records.append(
                _baseline(
                    item,
                    BaselineType.NAMED_ALTERNATIVE,
                    alternative.label,
                    alternative.description,
                    _with_fallback(alternative.facet_refs, facet_refs),
                    _with_fallback(alternative.obligation_refs, obligation_refs),
                    _with_fallback(alternative.concept_spine_refs, concept_refs),
                    _with_fallback(alternative.authority_profile_refs, authority_refs),
                    stable_part=alternative.alternative_id,
                )
            )
        for facet in item.facets:
            if _is_fragility_or_scenario_facet(facet):
                records.append(
                    _baseline(
                        item,
                        BaselineType.FRAGILITY_SCENARIO,
                        f"Fragility scenario: {facet.value}",
                        f"Stress baseline seeded from facet '{facet.facet_type}'.",
                        [facet.facet_id],
                        _related_obligation_refs(item, [facet.facet_id]),
                        _with_fallback(facet.concept_spine_refs, concept_refs),
                        _with_fallback(facet.authority_profile_refs, authority_refs),
                        stable_part=facet.facet_id,
                    )
                )
        return _dedupe_baselines(records)

    def _compile_alternatives(self, item: ClaimDecompositionInput) -> list[AlternativeRecord]:
        records: list[AlternativeRecord] = []
        facet_refs = _all_facet_refs(item)
        obligation_refs = _all_obligation_refs(item)
        concept_refs = _all_concept_refs(item)
        authority_refs = _all_authority_refs(item)
        for alternative in item.named_alternatives:
            records.append(
                AlternativeRecord(
                    alternative_id=alternative.alternative_id,
                    run_id=item.run_id,
                    label=alternative.label,
                    description=alternative.description,
                    status=alternative.status,
                    rejected_reasons=list(alternative.rejected_reasons),
                    facet_refs=_with_fallback(alternative.facet_refs, facet_refs),
                    obligation_refs=_with_fallback(alternative.obligation_refs, obligation_refs),
                    concept_spine_refs=_with_fallback(
                        alternative.concept_spine_refs,
                        concept_refs,
                    ),
                    authority_profile_refs=_with_fallback(
                        alternative.authority_profile_refs,
                        authority_refs,
                    ),
                    source_class=alternative.source_class,
                    metadata=dict(alternative.metadata),
                )
            )
        return records


def compile_claim_decomposition(
    payload: ClaimDecompositionInput | Mapping[str, Any],
) -> ClaimLedger:
    """Compile W6.D claim decomposition using the default deterministic compiler."""

    return ClaimDecompositionCompiler().compile(payload)


def compile_participation_requirements_from_claim_ledger(
    ledger: ClaimLedger | Mapping[str, Any],
    *,
    authority_level: str = "governed",
    population_scope: str = "affected_population",
) -> ParticipationRequirementBundle:
    """Bridge claim decomposition output into W7.E participation requirements."""

    typed = ledger if isinstance(ledger, ClaimLedger) else ClaimLedger.model_validate(ledger)
    claims = []
    for claim in typed.claims:
        payload = claim.model_dump(mode="json")
        payload.setdefault("authority_level", authority_level)
        payload.setdefault("population_scope", population_scope)
        claims.append(payload)
    return compile_participation_requirements(
        {
            "run_id": typed.run_id,
            "claims": claims,
            "metadata": {
                "source": "claim_decomposition_ledger",
                "bridge": (
                    "scientist.policy_design."
                    "claim_decomposition_to_participation_requirement"
                ),
            },
        }
    )


def _build_claim(
    *,
    run_id: str,
    family: ClaimFamily,
    claim_type: ClaimType,
    claim_use: ClaimUse,
    text: str,
    source_label: str,
    facet_refs: list[str],
    obligation_refs: list[str],
    concept_spine_refs: list[str],
    authority_profile_refs: list[str],
    source_class: ClaimSourceClass,
    publishability: ClaimPublishability = ClaimPublishability.DRAFT,
    blocked_reasons: Iterable[str] = (),
    baseline_refs: Iterable[str] = (),
    alternative_refs: Iterable[str] = (),
    extra_method_needs: Iterable[str] = (),
) -> ClaimRecord:
    claim_id = _stable_id("claim", run_id, family.value, claim_use.value, text, source_label)
    method_needs = [*_method_needs_for(family, claim_type), *list(extra_method_needs)]
    preconditions = [
        MethodNeedPrecondition(
            precondition_id=_stable_id("method_need", claim_id, method_need),
            claim_id=claim_id,
            claim_type=claim_type,
            method_need=method_need,
            reason=f"{family.value} claims require {method_need} before method admission.",
            facet_refs=list(facet_refs),
            obligation_refs=list(obligation_refs),
        )
        for method_need in _dedupe_strings(method_needs)
    ]
    return ClaimRecord(
        claim_id=claim_id,
        run_id=run_id,
        claim_type=claim_type,
        claim_family=family,
        claim_use=claim_use,
        text=text,
        support_status=ClaimSupportStatus.UNSUPPORTED,
        publishability=publishability,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        facet_refs=list(facet_refs),
        obligation_refs=list(obligation_refs),
        concept_spine_refs=list(concept_spine_refs),
        authority_profile_refs=list(authority_profile_refs),
        baseline_refs=list(baseline_refs),
        alternative_refs=list(alternative_refs),
        method_need_preconditions=preconditions,
        decomposition_source_class=source_class,
        source_attribution=["claim_decomposition"],
        blocked_reasons=list(blocked_reasons),
        metadata={"source_label": source_label},
    )


def _assignment_for_claim(*, run_id: str, claim: ClaimRecord) -> ClaimFamilyAssignment:
    if claim.claim_family is None or claim.claim_use is None:
        raise ValueError("claim family assignments require claim_family and claim_use")
    return ClaimFamilyAssignment(
        assignment_id=_stable_id("claim_family_assignment", run_id, claim.claim_id),
        run_id=run_id,
        claim_id=claim.claim_id,
        claim_family=claim.claim_family,
        claim_type=claim.claim_type,
        claim_use=claim.claim_use,
        facet_refs=list(claim.facet_refs),
        obligation_refs=list(claim.obligation_refs),
        concept_spine_refs=list(claim.concept_spine_refs),
        authority_profile_refs=list(claim.authority_profile_refs),
        baseline_refs=list(claim.baseline_refs),
        alternative_refs=list(claim.alternative_refs),
        method_need_preconditions=list(claim.method_need_preconditions),
        source_class=claim.decomposition_source_class or ClaimSourceClass.DETERMINISTIC_COMPILER,
        metadata=dict(claim.metadata),
    )


def _baseline(
    item: ClaimDecompositionInput,
    baseline_type: BaselineType,
    label: str,
    description: str,
    facet_refs: list[str],
    obligation_refs: list[str],
    concept_refs: list[str],
    authority_refs: list[str],
    *,
    stable_part: str | None = None,
) -> BaselineRecord:
    baseline_id = _stable_id(
        "baseline",
        item.run_id,
        baseline_type.value,
        stable_part or label,
    )
    return BaselineRecord(
        baseline_id=baseline_id,
        run_id=item.run_id,
        baseline_type=baseline_type,
        label=label,
        description=description,
        facet_refs=list(facet_refs),
        obligation_refs=list(obligation_refs),
        concept_spine_refs=list(concept_refs),
        authority_profile_refs=list(authority_refs),
    )


def _family_for_facet(facet: ClaimDecompositionFacet) -> ClaimFamily:
    token = f"{facet.facet_type} {facet.value}".lower()
    if any(word in token for word in ("causal", "effect", "outcome")):
        return ClaimFamily.CAUSAL
    if any(word in token for word in ("equity", "distribution", "risk", "subgroup")):
        return ClaimFamily.DISTRIBUTIONAL
    if any(word in token for word in ("welfare", "value", "tradeoff", "benefit")):
        return ClaimFamily.WELFARE
    if any(word in token for word in ("forecast", "future", "time", "horizon")):
        return ClaimFamily.FORECAST
    if any(word in token for word in ("implementation", "delivery", "channel", "feasibility")):
        return ClaimFamily.IMPLEMENTATION_FEASIBILITY
    if any(word in token for word in ("authority", "legal", "competence", "jurisdiction")):
        return ClaimFamily.LEGITIMACY
    if any(word in token for word in ("population", "lived", "experience")):
        return ClaimFamily.LIVED_EXPERIENCE
    if any(word in token for word in ("participation", "acceptability", "consultation")):
        return ClaimFamily.ACCEPTABILITY
    if any(word in token for word in ("scenario", "baseline", "status quo")):
        return ClaimFamily.CONTEXT_ONLY
    if any(word in token for word in ("instrument", "targeting", "funding")):
        return ClaimFamily.PREFERENCE
    return ClaimFamily.CONTEXT_ONLY


def _family_for_obligation(obligation: ClaimDecompositionObligation) -> ClaimFamily:
    token = f"{obligation.family} {obligation.description}".lower()
    if any(word in token for word in ("legal", "authority", "competence", "jurisdiction")):
        return ClaimFamily.LEGITIMACY
    if any(word in token for word in ("participation", "acceptability", "consultation")):
        return ClaimFamily.ACCEPTABILITY
    if any(word in token for word in ("fair", "procedural", "due process")):
        return ClaimFamily.PROCEDURAL_FAIRNESS
    if any(word in token for word in ("implementation", "delivery", "feasib", "operation")):
        return ClaimFamily.IMPLEMENTATION_FEASIBILITY
    if any(word in token for word in ("equity", "distribution", "subgroup")):
        return ClaimFamily.DISTRIBUTIONAL
    if any(word in token for word in ("objection", "dissent", "contest")):
        return ClaimFamily.OBJECTION_DISSENT
    if any(word in token for word in ("welfare", "tradeoff", "value")):
        return ClaimFamily.WELFARE
    if any(word in token for word in ("causal", "effect", "outcome")):
        return ClaimFamily.CAUSAL
    return ClaimFamily.CONTEXT_ONLY


def _type_for_family(family: ClaimFamily) -> ClaimType:
    mapping = {
        ClaimFamily.PREFERENCE: ClaimType.NORMATIVE,
        ClaimFamily.LIVED_EXPERIENCE: ClaimType.FACTUAL,
        ClaimFamily.ACCEPTABILITY: ClaimType.NORMATIVE,
        ClaimFamily.LEGITIMACY: ClaimType.LEGAL,
        ClaimFamily.PROCEDURAL_FAIRNESS: ClaimType.NORMATIVE,
        ClaimFamily.IMPLEMENTATION_FEASIBILITY: ClaimType.IMPLEMENTATION,
        ClaimFamily.OBJECTION_DISSENT: ClaimType.NORMATIVE,
        ClaimFamily.CONTEXT_ONLY: ClaimType.FACTUAL,
        ClaimFamily.CAUSAL: ClaimType.CAUSAL,
        ClaimFamily.DISTRIBUTIONAL: ClaimType.DISTRIBUTIONAL,
        ClaimFamily.WELFARE: ClaimType.WELFARE,
        ClaimFamily.FORECAST: ClaimType.FORECAST,
        ClaimFamily.IMPLEMENTATION: ClaimType.IMPLEMENTATION,
    }
    return mapping[family]


def _use_for_family(family: ClaimFamily) -> ClaimUse:
    if family is ClaimFamily.ACCEPTABILITY:
        return ClaimUse.PARTICIPATION_LEGITIMACY
    if family in {ClaimFamily.LIVED_EXPERIENCE, ClaimFamily.OBJECTION_DISSENT}:
        return ClaimUse.PARTICIPATION_CONTEXT
    if family is ClaimFamily.CONTEXT_ONLY:
        return ClaimUse.CONTEXT_ONLY
    if family in {ClaimFamily.IMPLEMENTATION, ClaimFamily.IMPLEMENTATION_FEASIBILITY}:
        return ClaimUse.IMPLEMENTATION_READINESS
    return ClaimUse.DECISION_SUPPORT


def _method_needs_for(family: ClaimFamily, claim_type: ClaimType) -> list[str]:
    needs: list[str] = []
    if claim_type is ClaimType.CAUSAL:
        needs.append("causal_identification")
    if claim_type is ClaimType.DISTRIBUTIONAL:
        needs.append("distributional_decomposition")
    if claim_type is ClaimType.WELFARE:
        needs.append("welfare_weight_sensitivity")
    if claim_type is ClaimType.FORECAST:
        needs.append("forecast_validation")
    if claim_type is ClaimType.IMPLEMENTATION:
        needs.append("implementation_feasibility_assessment")
    if claim_type is ClaimType.LEGAL:
        needs.append("authority_competence_assessment")
    if family is ClaimFamily.PREFERENCE:
        needs.append("preference_elicitation_validity")
    if family in {
        ClaimFamily.ACCEPTABILITY,
        ClaimFamily.LIVED_EXPERIENCE,
        ClaimFamily.OBJECTION_DISSENT,
    }:
        needs.append("participation_sampling_validity")
    if family is ClaimFamily.PROCEDURAL_FAIRNESS:
        needs.append("procedural_fairness_assessment")
    return needs


def _related_obligation_refs(item: ClaimDecompositionInput, facet_refs: list[str]) -> list[str]:
    facet_set = set(facet_refs)
    related = [
        obligation.obligation_id
        for obligation in item.obligations
        if not obligation.facet_refs or facet_set.intersection(obligation.facet_refs)
    ]
    return related or _all_obligation_refs(item)


def _concept_refs_for_facets(item: ClaimDecompositionInput, facet_refs: list[str]) -> list[str]:
    facet_set = set(facet_refs)
    refs = [
        ref
        for facet in item.facets
        if facet.facet_id in facet_set
        for ref in facet.concept_spine_refs
    ]
    return _with_fallback(refs, _all_concept_refs(item))


def _authority_refs_for_facets(item: ClaimDecompositionInput, facet_refs: list[str]) -> list[str]:
    facet_set = set(facet_refs)
    refs = [
        ref
        for facet in item.facets
        if facet.facet_id in facet_set
        for ref in facet.authority_profile_refs
    ]
    return _with_fallback(refs, _all_authority_refs(item))


def _all_facet_refs(item: ClaimDecompositionInput) -> list[str]:
    return _dedupe_strings(facet.facet_id for facet in item.facets)


def _all_obligation_refs(item: ClaimDecompositionInput) -> list[str]:
    return _dedupe_strings(obligation.obligation_id for obligation in item.obligations)


def _all_concept_refs(item: ClaimDecompositionInput) -> list[str]:
    refs = [
        *item.concept_spine_refs,
        *(ref for facet in item.facets for ref in facet.concept_spine_refs),
        *(ref for obligation in item.obligations for ref in obligation.concept_spine_refs),
    ]
    return _dedupe_strings(refs) or ["concept_spine.unresolved"]


def _all_authority_refs(item: ClaimDecompositionInput) -> list[str]:
    refs = [
        *item.authority_profile_refs,
        *(ref for facet in item.facets for ref in facet.authority_profile_refs),
        *(ref for obligation in item.obligations for ref in obligation.authority_profile_refs),
    ]
    return _dedupe_strings(refs) or ["authority_profile.unresolved"]


def _is_fragility_or_scenario_facet(facet: ClaimDecompositionFacet) -> bool:
    token = f"{facet.facet_type} {facet.value}".lower()
    return any(word in token for word in ("fragility", "scenario", "shock", "stress"))


def _with_fallback(values: Iterable[str], fallback: Iterable[str]) -> list[str]:
    resolved = _dedupe_strings(values)
    return resolved if resolved else _dedupe_strings(fallback)


def _dedupe_claims(claims: Iterable[ClaimRecord]) -> list[ClaimRecord]:
    deduped: dict[str, ClaimRecord] = {}
    for claim in claims:
        deduped.setdefault(claim.claim_id, claim)
    return list(deduped.values())


def _dedupe_baselines(records: Iterable[BaselineRecord]) -> list[BaselineRecord]:
    deduped: dict[str, BaselineRecord] = {}
    for record in records:
        deduped.setdefault(record.baseline_id, record)
    return list(deduped.values())


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _validate_unique(values: Iterable[str], label: str) -> None:
    items = list(values)
    if len(items) != len(set(items)):
        raise ValueError(f"{label} values must be unique")


def _stable_id(prefix: str, *parts: str) -> str:
    digest = _digest({"parts": list(parts)})[:16]
    return f"{prefix}_{digest}"


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


__all__ = [
    "ClaimDecompositionCompiler",
    "ClaimDecompositionFacet",
    "ClaimDecompositionInput",
    "ClaimDecompositionNamedAlternative",
    "ClaimDecompositionObligation",
    "compile_claim_decomposition",
    "compile_participation_requirements_from_claim_ledger",
]
