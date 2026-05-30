---
case_id: "w11a_uk_work_programme_2011"
case_title: "United Kingdom Work Programme labour activation"
corpus_phase: "W11.A"
sourcing_status: "sourced"
annotation_status: "annotated_w11b"
expert_adjudication_status: "adjudicated_w11c"
domain: "labour_activation"
authority_level: "governed"
jurisdiction_authority_level: "national"
jurisdiction: "Great Britain"
policy_time: "2011-06 to 2017-03"
policy_instrument:
  instrument_type: "provider_led_employment_activation"
  delivery_channel: "contracted welfare-to-work providers"
  funding_channel: "payment_by_results_contracts"
targeting:
  targeting_type: "benefit_claimant_referral_by_group"
  beneficiary_classes:
    - "long_term_unemployed_claimants"
    - "harder_to_help_claimant_groups"
  affected_populations:
    - "employment_service_providers"
    - "jobcentre_plus_staff"
    - "claimants_with_disabilities_or_health_conditions"
expected_evidence_families:
  - "official_program_statistics"
  - "impact_assessment"
  - "provider_payment_data"
  - "subgroup_outcome_analysis"
  - "participant_experience_evidence"
raw_source_refs:
  - "https://www.gov.uk/government/publications/work-programme-official-statistics-background-information-note/new"
  - "https://www.gov.uk/government/publications/the-work-programme-impact-assessment"
  - "https://www.nao.org.uk/wp-content/uploads/2012/01/10121701.pdf"
redacted_source_hashes: []
known_failure_limitation_labels:
  - "hard_to_help_subgroup_underperformance"
  - "payment_by_results_incentive_risk"
  - "participant_experience_variance"
  - "deadweight_and_counterfactual_uncertainty"
references:
  - ref_id: "text:case:summary"
    ref_type: "source"
    source_ref: "repo://docs/research/universal-policy-design/outcome-corpus/uk-work-programme-2011-labour-activation.md#summary"
    title: "Case summary"
  - ref_id: "legal:work-programme-dwp"
    ref_type: "legal"
    source_ref: "https://www.gov.uk/government/publications/work-programme-official-statistics-background-information-note/new"
    title: "DWP Work Programme official statistics background"
  - ref_id: "evidence:work-programme-impact-assessment"
    ref_type: "evidence"
    source_ref: "https://www.gov.uk/government/publications/the-work-programme-impact-assessment"
    title: "DWP Work Programme impact assessment"
  - ref_id: "method:work-programme-impact-analysis"
    ref_type: "method"
    source_ref: "https://www.gov.uk/government/publications/the-work-programme-impact-assessment"
    title: "Employment and benefit outcome impact method"
  - ref_id: "participation:claimant-provider-delivery"
    ref_type: "participation"
    source_ref: "https://www.gov.uk/government/publications/work-programme-official-statistics-background-information-note/new"
    title: "Claimant referral and provider support pathway"
  - ref_id: "risk:payment-by-results-creaming"
    ref_type: "risk"
    source_ref: "https://www.nao.org.uk/wp-content/uploads/2012/01/10121701.pdf"
    title: "NAO Work Programme provider incentive and performance concerns"
  - ref_id: "tradeoff:provider-flexibility-vs-equity"
    ref_type: "tradeoff"
    source_ref: "https://www.nao.org.uk/wp-content/uploads/2012/01/10121701.pdf"
    title: "Provider flexibility and harder-to-help claimant equity tradeoff"
  - ref_id: "limitation:subgroup-effectiveness"
    ref_type: "limitation"
    source_ref: "https://www.gov.uk/government/publications/the-work-programme-impact-assessment"
    title: "Subgroup impact and cost-benefit limitation"
  - ref_id: "outcome:final-statistics-window"
    ref_type: "outcome"
    source_ref: "https://www.gov.uk/government/publications/work-programme-official-statistics-background-information-note/new"
    title: "Final Work Programme statistics window"
claims:
  - claim_id: "claim:work-programme-sustained-employment"
    claim_type: "causal_and_distributional"
    text_ref: "text:case:summary"
    scope:
      population:
        - "long_term_unemployed_claimants"
        - "harder_to_help_claimant_groups"
      geography:
        - "England"
        - "Scotland"
        - "Wales"
      time_period: "2011-06 to 2017-03"
      institution:
        - "Department_for_Work_and_Pensions"
        - "contracted_providers"
    evidence_refs:
      - "evidence:work-programme-impact-assessment"
    method_refs:
      - "method:work-programme-impact-analysis"
    legal_refs:
      - "legal:work-programme-dwp"
    participation_refs:
      - "participation:claimant-provider-delivery"
    risks:
      - "risk:payment-by-results-creaming"
    tradeoffs:
      - "tradeoff:provider-flexibility-vs-equity"
    admissibility_label: "limited"
    limitation_refs:
      - "limitation:subgroup-effectiveness"
    contestability_status: "contested"
obligations:
  - obligation_id: "obligation:work-programme-hard-to-help-effects"
    generated_from_facets:
      - "facet:instrument.provider_led_activation"
      - "facet:funding.payment_by_results"
      - "facet:population.harder_to_help"
    required_evidence_family: "subgroup_impact_and_incentive_analysis"
    status: "required_for_governed_closeout"
    reviewer_notes: "Useful design must prove outcomes for harder-to-help groups, not only aggregate job outcomes."
known_outcomes_or_failures:
  - finding_id: "outcome:final-statistics-window"
    source_ref: "outcome:final-statistics-window"
    would_prior_obligation_have_flagged: null
annotation_provenance:
  reviewer_role: "policy_generalist"
  expertise_basis: "W11.A source triage from DWP and NAO materials"
  conflicts: []
  reviewed_at: "2026-05-24"
---

# UK Work Programme

## Summary

The Work Programme is a labour activation case for payment-by-results design,
provider discretion, claimant heterogeneity, and distributional adequacy.

## W11.B Handoff

The case should force obligation compilation for subgroup effects, provider
incentives, and counterfactual employment outcomes. Aggregate job outcomes are
not enough for governed useful design.
