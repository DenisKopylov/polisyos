"""Facet derivation for the W6.A universal policy grammar compiler."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core import contracts
from polisyos.ir import governance, observation

from .normalizer import NormalizedPolicyIntent
from .schema import PolicyGrammarConceptSpineRefs

IdentificationMode = observation.IdentificationMode
NormativeOutcomeChannel = governance.NormativeOutcomeChannel
PolicyLayerLevel = governance.PolicyLayerLevel
UniversalGeographyPredicate = contracts.UniversalGeographyPredicate
UniversalPolicyAuthorityTypeFacet = contracts.UniversalPolicyAuthorityTypeFacet
UniversalPolicyDeliveryChannel = contracts.UniversalPolicyDeliveryChannel
UniversalPolicyDeliveryChannelFacet = contracts.UniversalPolicyDeliveryChannelFacet
UniversalPolicyFacetName = contracts.UniversalPolicyFacetName
UniversalPolicyFacets = contracts.UniversalPolicyFacets
UniversalPolicyFundingChannel = contracts.UniversalPolicyFundingChannel
UniversalPolicyFundingChannelFacet = contracts.UniversalPolicyFundingChannelFacet
UniversalPolicyGeographyPredicateFacet = contracts.UniversalPolicyGeographyPredicateFacet
UniversalPolicyGrammarBlocker = contracts.UniversalPolicyGrammarBlocker
UniversalPolicyInstrumentType = contracts.UniversalPolicyInstrumentType
UniversalPolicyInstrumentTypeFacet = contracts.UniversalPolicyInstrumentTypeFacet
UniversalPolicyMethodNeedFacet = contracts.UniversalPolicyMethodNeedFacet
UniversalPolicyOutcomeChannelFacet = contracts.UniversalPolicyOutcomeChannelFacet
UniversalPolicyPopulationPredicateFacet = contracts.UniversalPolicyPopulationPredicateFacet
UniversalPolicyRiskFacet = contracts.UniversalPolicyRiskFacet
UniversalPolicyRiskFacetRecord = contracts.UniversalPolicyRiskFacetRecord
UniversalPolicyTargetingType = contracts.UniversalPolicyTargetingType
UniversalPolicyTargetingTypeFacet = contracts.UniversalPolicyTargetingTypeFacet
UniversalPolicyTimePredicateFacet = contracts.UniversalPolicyTimePredicateFacet
UniversalPopulationPredicate = contracts.UniversalPopulationPredicate
UniversalTimePredicate = contracts.UniversalTimePredicate

FACET_NAMES: tuple[UniversalPolicyFacetName, ...] = (
    "instrument_type",
    "targeting_type",
    "delivery_channel",
    "funding_channel",
    "authority_type",
    "outcome_channel",
    "risk_facet",
    "method_need",
    "population_predicate",
    "geography_predicate",
    "time_predicate",
)
_FACET_RULE_VERSION = "policyos.policy_grammar.facet_derivation.v1"
_IR_OUTCOME_REF = "polisyos.ir.governance.problem_frame.NormativeOutcomeChannel"
_IR_AUTHORITY_REF = "polisyos.ir.governance.policy_composition.PolicyLayerLevel"
_IR_METHOD_REF = "polisyos.ir.observation.contracts.IdentificationMode"
_IR_TEMPORAL_REF = "polisyos.ir.governance.temporal_logic.TemporalPolicyConstraint"
_POLICY_SPEC_REF = "polisyos.ir.governance.policy_spec.PolicySpec"
_CANDIDATE_REF = "polisyos.scientist.policy_design.schema.PolicyCandidateSchema"
_CRITIC_REF = "polisyos.scientist.policy_design.critic.ConstraintCritic"
_CHALLENGE_REF = "polisyos.scientist.evals.challenge_factory.ChallengeClass"


@dataclass(frozen=True)
class FacetDerivationResult:
    """Facet derivation result with typed blockers for fail-closed compilation."""

    facets: UniversalPolicyFacets | None
    blockers: tuple[UniversalPolicyGrammarBlocker, ...] = ()


def derive_facets(
    *,
    normalized: NormalizedPolicyIntent,
    authority_type: PolicyLayerLevel,
    concept_spine_refs: PolicyGrammarConceptSpineRefs,
) -> FacetDerivationResult:
    """Derive typed facets from normalized intent and concept-spine refs."""
    missing_refs = [
        facet_name for facet_name in FACET_NAMES if not concept_spine_refs.refs_for(facet_name)
    ]
    if missing_refs:
        return FacetDerivationResult(
            facets=None,
            blockers=(
                UniversalPolicyGrammarBlocker(
                    code="policy_grammar_concept_refs_missing",
                    message=(
                        "Universal policy grammar facets require concept-spine refs for: "
                        + ", ".join(missing_refs)
                    ),
                    pattern_refs=("P02", "P10"),
                    missing_capability_label="bridge_missing",
                ),
            ),
        )

    instrument = _instrument_type(normalized)
    targeting = _targeting_type(normalized)
    delivery = _delivery_channel(normalized)
    funding = _funding_channel(normalized)
    risk = _risk_facet(normalized)
    population = _population_predicate(normalized)
    geography = _geography_predicate(normalized, authority_type)
    time_predicate = _time_predicate(normalized)
    if None in {
        instrument,
        targeting,
        delivery,
        funding,
        risk,
        population,
        geography,
        time_predicate,
    }:
        return FacetDerivationResult(
            facets=None,
            blockers=(
                UniversalPolicyGrammarBlocker(
                    code="policy_grammar_facet_derivation_missing",
                    message="Intent did not contain enough governed signals to derive W6.A facets.",
                    pattern_refs=("P10", "P15"),
                    missing_capability_label="semantic_test_missing",
                ),
            ),
        )

    return FacetDerivationResult(
        facets=UniversalPolicyFacets(
            instrument_type=UniversalPolicyInstrumentTypeFacet(
                value=instrument,
                concept_spine_refs=concept_spine_refs.refs_for("instrument_type"),
                source_vocabulary_refs=(_POLICY_SPEC_REF, _CANDIDATE_REF),
                derivation_rule_ref=f"{_FACET_RULE_VERSION}:instrument_type",
            ),
            targeting_type=UniversalPolicyTargetingTypeFacet(
                value=targeting,
                concept_spine_refs=concept_spine_refs.refs_for("targeting_type"),
                source_vocabulary_refs=(_POLICY_SPEC_REF, _CANDIDATE_REF),
                derivation_rule_ref=f"{_FACET_RULE_VERSION}:targeting_type",
            ),
            delivery_channel=UniversalPolicyDeliveryChannelFacet(
                value=delivery,
                concept_spine_refs=concept_spine_refs.refs_for("delivery_channel"),
                source_vocabulary_refs=(_POLICY_SPEC_REF, _CANDIDATE_REF),
                derivation_rule_ref=f"{_FACET_RULE_VERSION}:delivery_channel",
            ),
            funding_channel=UniversalPolicyFundingChannelFacet(
                value=funding,
                concept_spine_refs=concept_spine_refs.refs_for("funding_channel"),
                source_vocabulary_refs=(_POLICY_SPEC_REF, _CANDIDATE_REF),
                derivation_rule_ref=f"{_FACET_RULE_VERSION}:funding_channel",
            ),
            authority_type=UniversalPolicyAuthorityTypeFacet(
                value=authority_type,
                concept_spine_refs=concept_spine_refs.refs_for("authority_type"),
                source_vocabulary_refs=(_IR_AUTHORITY_REF,),
                derivation_rule_ref=f"{_FACET_RULE_VERSION}:authority_type",
            ),
            outcome_channel=UniversalPolicyOutcomeChannelFacet(
                value=NormativeOutcomeChannel.SIMULATION_METRIC,
                concept_spine_refs=concept_spine_refs.refs_for("outcome_channel"),
                source_vocabulary_refs=(_IR_OUTCOME_REF,),
                derivation_rule_ref=f"{_FACET_RULE_VERSION}:outcome_channel",
            ),
            risk_facet=UniversalPolicyRiskFacetRecord(
                value=risk,
                concept_spine_refs=concept_spine_refs.refs_for("risk_facet"),
                source_vocabulary_refs=(_CRITIC_REF, _CHALLENGE_REF),
                derivation_rule_ref=f"{_FACET_RULE_VERSION}:risk_facet",
            ),
            method_need=UniversalPolicyMethodNeedFacet(
                value=_method_need(normalized),
                concept_spine_refs=concept_spine_refs.refs_for("method_need"),
                source_vocabulary_refs=(_IR_METHOD_REF, _IR_TEMPORAL_REF),
                derivation_rule_ref=f"{_FACET_RULE_VERSION}:method_need",
            ),
            population_predicate=UniversalPolicyPopulationPredicateFacet(
                value=population,
                concept_spine_refs=concept_spine_refs.refs_for("population_predicate"),
                source_vocabulary_refs=(_POLICY_SPEC_REF, _CANDIDATE_REF),
                derivation_rule_ref=f"{_FACET_RULE_VERSION}:population_predicate",
            ),
            geography_predicate=UniversalPolicyGeographyPredicateFacet(
                value=geography,
                concept_spine_refs=concept_spine_refs.refs_for("geography_predicate"),
                source_vocabulary_refs=(_POLICY_SPEC_REF, _IR_TEMPORAL_REF),
                derivation_rule_ref=f"{_FACET_RULE_VERSION}:geography_predicate",
            ),
            time_predicate=UniversalPolicyTimePredicateFacet(
                value=time_predicate,
                concept_spine_refs=concept_spine_refs.refs_for("time_predicate"),
                source_vocabulary_refs=(_IR_TEMPORAL_REF,),
                derivation_rule_ref=f"{_FACET_RULE_VERSION}:time_predicate",
            ),
        )
    )


def _instrument_type(normalized: NormalizedPolicyIntent) -> UniversalPolicyInstrumentType | None:
    kinds = set(normalized.intervention_kinds)
    if normalized.has_any("subsidy", "voucher", "rent"):
        return "subsidy"
    if "service" in kinds or normalized.has_any("service", "clinic", "vaccination", "vaccine"):
        return "service"
    if normalized.has_any("credit", "loan", "guarantee", "msme"):
        return "credit"
    if normalized.has_any("tax"):
        return "tax"
    if normalized.has_any("regulation", "license", "compliance"):
        return "regulation"
    if normalized.has_any("procurement"):
        return "procurement"
    if normalized.has_any("infrastructure", "construction"):
        return "infrastructure"
    if normalized.has_any("information", "campaign"):
        return "information"
    return None


def _targeting_type(normalized: NormalizedPolicyIntent) -> UniversalPolicyTargetingType | None:
    if normalized.has_any("means_tested", "low_income", "poverty"):
        return "means_tested"
    if normalized.has_any("msme", "msmes", "children", "renters", "patients", "students"):
        return "categorical"
    if normalized.has_any("region", "oblast", "rural", "urban", "municipal"):
        return "geographic"
    if normalized.has_any("sector", "industry"):
        return "sectoral"
    if normalized.has_any("risk"):
        return "risk_based"
    if normalized.has_any("all", "universal"):
        return "universal"
    return None


def _delivery_channel(normalized: NormalizedPolicyIntent) -> UniversalPolicyDeliveryChannel | None:
    if normalized.has_any("credit", "loan", "bank", "registry"):
        return "credit_registry"
    if normalized.has_any("voucher"):
        return "voucher"
    if normalized.has_any("service", "clinic", "vaccination", "centre", "center"):
        return "public_service"
    if normalized.has_any("tax"):
        return "tax_expenditure"
    if normalized.has_any("procurement"):
        return "procurement"
    if normalized.has_any("grant"):
        return "grant_program"
    if normalized.has_any("regulation", "compliance", "enforcement"):
        return "regulatory_enforcement"
    if normalized.has_any("information", "campaign"):
        return "information_campaign"
    return None


def _funding_channel(normalized: NormalizedPolicyIntent) -> UniversalPolicyFundingChannel | None:
    if normalized.has_any("concessional"):
        return "concessional_credit"
    if normalized.has_any("budget", "appropriation", "municipal"):
        return "budget_appropriation"
    if normalized.has_any("tax", "earmarked"):
        return "earmarked_tax"
    if normalized.has_any("donor", "grant"):
        return "donor_grant"
    if normalized.has_any("fee"):
        return "user_fee"
    if normalized.has_any("mandate"):
        return "regulatory_mandate"
    return None


def _risk_facet(normalized: NormalizedPolicyIntent) -> UniversalPolicyRiskFacet | None:
    if normalized.has_any("means_tested", "low_income", "threshold"):
        return "fairness_threshold_reversal"
    if normalized.has_any("children", "rural", "equity", "coverage"):
        return "equity_harm"
    if normalized.has_any("credit", "budget", "appropriation", "guarantee"):
        return "budget_feasibility"
    if normalized.has_any("privacy", "pii", "patient"):
        return "privacy_pii"
    if normalized.has_any("transport", "external_validity"):
        return "transportability"
    if normalized.has_any("gaming", "strategic"):
        return "strategic_gaming"
    return None


def _method_need(normalized: NormalizedPolicyIntent) -> IdentificationMode:
    if IdentificationMode.SEQUENTIAL in normalized.identification_modes:
        return IdentificationMode.SEQUENTIAL
    if normalized.has_any("phase", "phased", "rollout", "sequence"):
        return IdentificationMode.SEQUENTIAL
    return IdentificationMode.POINT_IDENTIFIED


def _population_predicate(
    normalized: NormalizedPolicyIntent,
) -> UniversalPopulationPredicate | None:
    if normalized.has_any("msme", "msmes"):
        return "msmes"
    if normalized.has_any("low_income", "renters"):
        return "low_income_renters"
    if normalized.has_any("children"):
        return "children"
    if normalized.has_any("patients"):
        return "patients"
    if normalized.has_any("students"):
        return "students"
    if normalized.has_any("firms"):
        return "firms"
    if normalized.has_any("households"):
        return "households"
    if normalized.has_any("workers", "employment"):
        return "workers"
    if normalized.has_any("all", "residents"):
        return "all_residents"
    return None


def _geography_predicate(
    normalized: NormalizedPolicyIntent,
    authority_type: PolicyLayerLevel,
) -> UniversalGeographyPredicate | None:
    if normalized.has_any("rural"):
        return "rural"
    if normalized.has_any("urban"):
        return "urban"
    if normalized.has_any("municipal", "city"):
        return "municipal"
    if normalized.has_any("oblast", "region", "regions", "northern", "state"):
        return "state_or_region"
    if normalized.has_any("displaced", "displacement"):
        return "displacement_affected"
    if normalized.has_any("national", "federal"):
        return "national"
    if authority_type is PolicyLayerLevel.FEDERAL:
        return "national"
    if authority_type is PolicyLayerLevel.LOCAL:
        return "municipal"
    if authority_type is PolicyLayerLevel.STATE:
        return "state_or_region"
    return None


def _time_predicate(normalized: NormalizedPolicyIntent) -> UniversalTimePredicate | None:
    if normalized.has_any("phase", "phased", "rollout"):
        return "phased_rollout"
    if normalized.has_any("annual", "2026"):
        return "annual"
    if normalized.has_any("multi_year", "multi", "years"):
        return "multi_year"
    if normalized.has_any("trigger"):
        return "event_triggered"
    if normalized.has_any("retroactive"):
        return "retroactive"
    return None


__all__ = ["FACET_NAMES", "FacetDerivationResult", "derive_facets"]
