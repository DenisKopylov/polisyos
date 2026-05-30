---
case_id: "w11a_pakistan_ehsaas_cash_2020"
case_title: "Pakistan Ehsaas Emergency Cash COVID-19 social protection response"
corpus_phase: "W11.A"
sourcing_status: "sourced"
annotation_status: "annotated_w11b"
expert_adjudication_status: "adjudicated_w11c"
domain: "social_protection_targeting"
authority_level: "production"
jurisdiction_authority_level: "national"
jurisdiction: "Pakistan"
policy_time: "2020-04 to 2020-10"
policy_instrument:
  instrument_type: "emergency_cash_transfer"
  delivery_channel: "digital eligibility screening and cash disbursement points"
  funding_channel: "national social protection response with development partner support"
targeting:
  targeting_type: "poverty_registry_and_emergency_vulnerability_screening"
  beneficiary_classes:
    - "low_income_households"
    - "informal_workers_affected_by_covid_19"
    - "women_payment_recipients"
  affected_populations:
    - "households_without_digital_access"
    - "payment_agents"
    - "provincial_administrations"
expected_evidence_families:
  - "social_registry_targeting_data"
  - "payment_delivery_records"
  - "coverage_and_exclusion_analysis"
  - "gender_and_accessibility_analysis"
  - "shock_response_evaluation"
raw_source_refs:
  - "https://www.ehsaas2047.com/emergency-cash"
  - "https://www.worldbank.org/en/results/2020/12/09/responsive-social-protection-program-and-systems-to-serve-pakistans-poorest-people"
  - "https://www.worldbank.org/en/news/press-release/2021/03/25/pakistan-expands-ehsaas-social-protection-programs-to-increase-household-resilience-to-economic-shocks-with-world-bank-s"
redacted_source_hashes: []
known_failure_limitation_labels:
  - "digital_access_exclusion_risk"
  - "registry_freshness_gap"
  - "coverage_vs_targeting_tradeoff"
  - "payment_site_access_and_safety_risk"
references:
  - ref_id: "text:case:summary"
    ref_type: "source"
    source_ref: "repo://docs/research/universal-policy-design/outcome-corpus/pakistan-ehsaas-emergency-cash-2020-social-protection.md#summary"
    title: "Case summary"
  - ref_id: "legal:ehsaas-emergency-cash"
    ref_type: "legal"
    source_ref: "https://www.ehsaas2047.com/emergency-cash"
    title: "Ehsaas Emergency Cash programme page"
  - ref_id: "evidence:worldbank-responsive-social-protection"
    ref_type: "evidence"
    source_ref: "https://www.worldbank.org/en/results/2020/12/09/responsive-social-protection-program-and-systems-to-serve-pakistans-poorest-people"
    title: "World Bank results brief on Pakistan responsive social protection"
  - ref_id: "method:social-registry-emergency-targeting"
    ref_type: "method"
    source_ref: "https://www.worldbank.org/en/results/2020/12/09/responsive-social-protection-program-and-systems-to-serve-pakistans-poorest-people"
    title: "Emergency cash transfer targeting and delivery systems"
  - ref_id: "participation:cash-disbursement-access"
    ref_type: "participation"
    source_ref: "https://www.ehsaas2047.com/emergency-cash"
    title: "Cash disbursement access and recipient pathway"
  - ref_id: "risk:digital-and-registry-exclusion"
    ref_type: "risk"
    source_ref: "https://www.worldbank.org/en/results/2020/12/09/responsive-social-protection-program-and-systems-to-serve-pakistans-poorest-people"
    title: "Fragmented coverage and shock responsiveness limitation"
  - ref_id: "tradeoff:rapid-scale-vs-targeting-precision"
    ref_type: "tradeoff"
    source_ref: "https://www.worldbank.org/en/results/2020/12/09/responsive-social-protection-program-and-systems-to-serve-pakistans-poorest-people"
    title: "Rapid emergency scale and targeting precision tradeoff"
  - ref_id: "limitation:registry-and-access-gap"
    ref_type: "limitation"
    source_ref: "https://www.worldbank.org/en/results/2020/12/09/responsive-social-protection-program-and-systems-to-serve-pakistans-poorest-people"
    title: "Coverage, administration, and targeting efficiency limitation"
  - ref_id: "outcome:cash-transfers-delivered"
    ref_type: "outcome"
    source_ref: "https://www.ehsaas2047.com/emergency-cash"
    title: "Emergency cash disbursement to eligible families"
claims:
  - claim_id: "claim:ehsaas-rapid-social-protection"
    claim_type: "targeting_and_delivery"
    text_ref: "text:case:summary"
    scope:
      population:
        - "low_income_households"
        - "informal_workers_affected_by_covid_19"
      geography:
        - "Pakistan"
      time_period: "2020-04 to 2020-10"
      institution:
        - "Government_of_Pakistan"
        - "Ehsaas_programme"
        - "World_Bank"
    evidence_refs:
      - "evidence:worldbank-responsive-social-protection"
    method_refs:
      - "method:social-registry-emergency-targeting"
    legal_refs:
      - "legal:ehsaas-emergency-cash"
    participation_refs:
      - "participation:cash-disbursement-access"
    risks:
      - "risk:digital-and-registry-exclusion"
    tradeoffs:
      - "tradeoff:rapid-scale-vs-targeting-precision"
    admissibility_label: "publishable_with_limitation"
    limitation_refs:
      - "limitation:registry-and-access-gap"
    contestability_status: "limited"
obligations:
  - obligation_id: "obligation:ehsaas-targeting-exclusion-audit"
    generated_from_facets:
      - "facet:instrument.emergency_cash_transfer"
      - "facet:targeting.social_registry"
      - "facet:delivery.digital_screening_cash_points"
    required_evidence_family: "coverage_exclusion_and_payment_access_analysis"
    status: "required_for_production_closeout"
    reviewer_notes: "Production closeout must expose exclusion and payment access risks, not only headline coverage."
known_outcomes_or_failures:
  - finding_id: "outcome:cash-transfers-delivered"
    source_ref: "outcome:cash-transfers-delivered"
    would_prior_obligation_have_flagged: false
annotation_provenance:
  reviewer_role: "policy_generalist"
  expertise_basis: "W11.A source triage from Ehsaas and World Bank materials"
  conflicts: []
  reviewed_at: "2026-05-24"
---

# Pakistan Ehsaas Emergency Cash

## Summary

Ehsaas Emergency Cash is a social protection targeting case where rapid scale,
registry quality, digital access, payment logistics, and exclusion risk are all
load-bearing.

## W11.B Handoff

Decompose coverage, targeting accuracy, payment delivery, gendered access, and
registry freshness. The case should pass with limitation only if exclusion and
delivery constraints remain visible.
