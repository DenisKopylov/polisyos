"""Facet derivation for the W6.A universal policy grammar compiler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.core import contracts
from polisyos.ir.governance import NormativeOutcomeChannel, PolicyLayerLevel
from polisyos.ir.observation import (
    IDENTIFICATION_MODE_DEFAULT_POINT_DERIVATION_RULE_REF,
    IDENTIFICATION_MODE_EXPLICIT_POLICY_SPEC_DERIVATION_RULE_REF,
    IDENTIFICATION_MODE_INFERRED_SEQUENTIAL_DERIVATION_RULE_REF,
    IdentificationMode,
    identification_mode_origin_for_rule,
)

if TYPE_CHECKING:
    from pydantic import JsonValue

    from .normalizer import NormalizedPolicyIntent
    from .schema import PolicyGrammarConceptSpineRefs

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
_INSTRUMENT_RULES: tuple[tuple[UniversalPolicyInstrumentType, tuple[str, ...]], ...] = (
    ("subsidy", ("subsidy", "voucher", "rent")),
    ("service", ("service", "clinic", "vaccination", "vaccine")),
    ("credit", ("credit", "loan", "guarantee", "msme")),
    ("tax", ("tax",)),
    ("regulation", ("regulation", "license", "compliance")),
    ("procurement", ("procurement",)),
    ("infrastructure", ("infrastructure", "construction")),
    ("information", ("information", "campaign")),
)
_DELIVERY_RULES: tuple[tuple[UniversalPolicyDeliveryChannel, tuple[str, ...]], ...] = (
    ("credit_registry", ("credit", "loan", "bank", "registry")),
    ("voucher", ("voucher",)),
    ("public_service", ("service", "clinic", "vaccination", "centre", "center")),
    ("tax_expenditure", ("tax",)),
    ("procurement", ("procurement",)),
    ("grant_program", ("grant",)),
    ("regulatory_enforcement", ("regulation", "compliance", "enforcement")),
    ("information_campaign", ("information", "campaign")),
)
# These are the existing population rules, with their inferential terms named.
# An outcome/qualifier such as employment, low_income, or all does not establish
# a second literal population alongside a more explicit controlled token.
_POPULATION_RULES: tuple[
    tuple[UniversalPopulationPredicate, tuple[str, ...], tuple[str, ...]], ...
] = (
    ("msmes", ("msme", "msmes"), ()),
    ("low_income_renters", ("low_income", "renters"), ("low_income",)),
    ("children", ("children",), ()),
    ("patients", ("patients",), ()),
    ("students", ("students",), ()),
    ("firms", ("firms",), ()),
    ("households", ("households",), ()),
    ("workers", ("workers", "employment"), ("employment",)),
    ("all_residents", ("all", "residents"), ("all",)),
)


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

    identification_modes = tuple(dict.fromkeys(normalized.identification_modes))
    if len(identification_modes) > 1:
        return FacetDerivationResult(
            facets=None,
            blockers=(
                UniversalPolicyGrammarBlocker(
                    code="policy_grammar_identification_modes_conflict",
                    message=(
                        "W6.A cannot represent distinct intervention identification modes "
                        "in its scalar method_need facet: "
                        + ", ".join(mode.value for mode in identification_modes)
                    ),
                    facet_name="method_need",
                    pattern_refs=("P10", "P33"),
                    missing_capability_label="bridge_missing",
                ),
            ),
        )

    disclosures = _selector_disclosures(normalized)
    explicit_populations = {
        record["candidate_value"]
        for record in disclosures
        if record["facet_name"] == "population_predicate"
        and record["evidence_role"] == "explicit_controlled_token"
    }
    if len(explicit_populations) > 1:
        return FacetDerivationResult(
            facets=None,
            blockers=(
                UniversalPolicyGrammarBlocker(
                    code="policy_grammar_population_composition_unsupported",
                    message=(
                        "The scalar grammar cannot bind competing controlled population "
                        "choices to one scope. Supply explicit intervention components."
                    ),
                    facet_name="population_predicate",
                    pattern_refs=("P10", "P31", "P33"),
                    missing_capability_label="bridge_missing",
                    details={
                        "selector_candidates": list(disclosures),
                        "semantic_scope_provenance": "not_established",
                        "supported_envelope": "explicit_component_or_single_population",
                    },
                ),
            ),
        )
    warnings = _ambiguity_warnings(disclosures)
    instrument = _instrument_type(normalized)
    targeting = _targeting_type(normalized)
    delivery = _delivery_channel(normalized)
    funding = _funding_channel(normalized)
    risk = _risk_facet(normalized)
    population = _population_predicate(normalized)
    geography = _geography_predicate(normalized, authority_type)
    time_predicate = _time_predicate(normalized)
    method_need, method_rule_ref = _method_need(normalized)
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
                value=method_need,
                concept_spine_refs=concept_spine_refs.refs_for("method_need"),
                source_vocabulary_refs=(_IR_METHOD_REF, _IR_TEMPORAL_REF),
                derivation_rule_ref=method_rule_ref,
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
        ),
        blockers=warnings,
    )


def _instrument_type(normalized: NormalizedPolicyIntent) -> UniversalPolicyInstrumentType | None:
    for value, terms in _INSTRUMENT_RULES:
        if normalized.has_any(*terms) or (
            value == "service" and "service" in normalized.intervention_kinds
        ):
            return value
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
    for value, terms in _DELIVERY_RULES:
        if normalized.has_any(*terms):
            return value
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


def _method_need(normalized: NormalizedPolicyIntent) -> tuple[IdentificationMode, str]:
    if normalized.identification_modes:
        return normalized.identification_modes[0], (
            IDENTIFICATION_MODE_EXPLICIT_POLICY_SPEC_DERIVATION_RULE_REF
        )
    if normalized.has_any("phase", "phased", "rollout", "sequence"):
        return IdentificationMode.SEQUENTIAL, (
            IDENTIFICATION_MODE_INFERRED_SEQUENTIAL_DERIVATION_RULE_REF
        )
    return IdentificationMode.POINT_IDENTIFIED, (
        IDENTIFICATION_MODE_DEFAULT_POINT_DERIVATION_RULE_REF
    )


def _population_predicate(
    normalized: NormalizedPolicyIntent,
) -> UniversalPopulationPredicate | None:
    for value, terms, _fallbacks in _POPULATION_RULES:
        if normalized.has_any(*terms):
            return value
    return None


def _selector_disclosures(
    normalized: NormalizedPolicyIntent,
) -> tuple[dict[str, JsonValue], ...]:
    """Retain every applicable existing exclusive-axis selector and its role."""
    rule_rows = (
        *(("instrument_type", value, terms, ()) for value, terms in _INSTRUMENT_RULES),
        *(("delivery_channel", value, terms, ()) for value, terms in _DELIVERY_RULES),
        *(("population_predicate", *row) for row in _POPULATION_RULES),
    )
    disclosures: list[dict[str, JsonValue]] = []
    for facet_name, value, terms, fallbacks in rule_rows:
        matched_terms = [term for term in terms if normalized.has_any(term)]
        if (
            facet_name == "instrument_type"
            and value == "service"
            and "service" in normalized.intervention_kinds
            and "service" not in matched_terms
        ):
            matched_terms.append("InterventionSpec.kind:service")
        if not matched_terms:
            continue
        role = (
            "inferential_fallback"
            if all(term in fallbacks for term in matched_terms)
            else "explicit_controlled_token"
        )
        disclosures.append(
            {
                "facet_name": facet_name,
                "candidate_value": value,
                "matched_terms": matched_terms,
                "rule_ref": f"{_FACET_RULE_VERSION}:{facet_name}:{value}",
                "evidence_role": role,
            }
        )
    return tuple(disclosures)


def _ambiguity_warnings(
    disclosures: tuple[dict[str, JsonValue], ...],
) -> tuple[UniversalPolicyGrammarBlocker, ...]:
    warnings: list[UniversalPolicyGrammarBlocker] = []
    for facet_name in ("instrument_type", "delivery_channel", "population_predicate"):
        choices = [record for record in disclosures if record["facet_name"] == facet_name]
        if len(choices) <= 1 and not any(
            record["evidence_role"] == "inferential_fallback" for record in choices
        ):
            continue
        warnings.append(
            UniversalPolicyGrammarBlocker(
                code="policy_grammar_facet_choice_not_scoped",
                severity="warning",
                message=(
                    f"The {facet_name} projection uses controlled selector precedence or "
                    "an inferential fallback. These candidate choices do not establish "
                    "component scope or complete interpretation of the unstructured intent."
                ),
                facet_name=facet_name,
                pattern_refs=("P10", "P33", "P37"),
                missing_capability_label="semantic_test_missing",
                details={
                    "selector_candidates": choices,
                    "semantic_scope_provenance": "not_established",
                    "supported_envelope": "controlled_selector_candidate_only",
                },
            )
        )
    return tuple(warnings)


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


__all__ = [
    "FACET_NAMES",
    "FacetDerivationResult",
    "derive_facets",
    "identification_mode_origin_for_rule",
]
