---
case_id: "w11a_eu_temporary_protection_ukraine_2022"
case_title: "EU temporary protection for displaced persons from Ukraine"
corpus_phase: "W11.A"
sourcing_status: "sourced"
annotation_status: "annotated_w11b"
expert_adjudication_status: "adjudicated_w11c"
domain: "migration_displacement"
authority_level: "production"
jurisdiction_authority_level: "supranational"
jurisdiction: "European Union"
policy_time: "2022-03 to 2027-03"
policy_instrument:
  instrument_type: "temporary_protection_status"
  delivery_channel: "EU member-state registration and rights access"
  funding_channel: "EU and member-state protection and integration resources"
targeting:
  targeting_type: "displacement_status_and_residence_date"
  beneficiary_classes:
    - "Ukrainian_nationals_displaced_on_or_after_2022_02_24"
    - "eligible_stateless_and_third_country_nationals_from_Ukraine"
    - "family_members"
  affected_populations:
    - "host_municipalities"
    - "schools"
    - "health_systems"
    - "labour_markets"
expected_evidence_families:
  - "legal_activation_decision"
  - "registration_and_status_data"
  - "housing_access_monitoring"
  - "education_and_labour_market_access_data"
  - "local_implementation_challenge_reports"
raw_source_refs:
  - "https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=celex%3A32022D0382"
  - "https://commission.europa.eu/topics/eu-solidarity-ukraine/eu-assistance-ukraine/information-people-fleeing-war-ukraine/fleeing-ukraine-your-rights-eu_en"
  - "https://www.euaa.europa.eu/publications/providing-temporary-protection-displaced-persons-ukraine"
  - "https://fra.europa.eu/nl/publication/2023/fleeing-ukraine-temporary-protection"
redacted_source_hashes: []
known_failure_limitation_labels:
  - "member_state_implementation_variance"
  - "housing_capacity_pressure"
  - "long_term_status_transition_uncertainty"
  - "non_ukrainian_third_country_scope_contestation"
references:
  - ref_id: "text:case:summary"
    ref_type: "source"
    source_ref: "repo://docs/research/universal-policy-design/outcome-corpus/eu-temporary-protection-ukraine-2022-migration.md#summary"
    title: "Case summary"
  - ref_id: "legal:council-implementing-decision-2022-382"
    ref_type: "legal"
    source_ref: "https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=celex%3A32022D0382"
    title: "Council Implementing Decision (EU) 2022/382"
  - ref_id: "evidence:euaa-year-in-review"
    ref_type: "evidence"
    source_ref: "https://www.euaa.europa.eu/publications/providing-temporary-protection-displaced-persons-ukraine"
    title: "EUAA year in review on temporary protection implementation"
  - ref_id: "method:fra-local-implementation-review"
    ref_type: "method"
    source_ref: "https://fra.europa.eu/nl/publication/2023/fleeing-ukraine-temporary-protection"
    title: "FRA local-level implementation review"
  - ref_id: "participation:member-state-registration"
    ref_type: "participation"
    source_ref: "https://commission.europa.eu/topics/eu-solidarity-ukraine/eu-assistance-ukraine/information-people-fleeing-war-ukraine/fleeing-ukraine-your-rights-eu_en"
    title: "Commission public rights and registration guidance"
  - ref_id: "risk:housing-and-services-pressure"
    ref_type: "risk"
    source_ref: "https://fra.europa.eu/nl/publication/2023/fleeing-ukraine-temporary-protection"
    title: "Housing, education, employment, and healthcare implementation challenges"
  - ref_id: "tradeoff:immediate-protection-vs-long-term-transition"
    ref_type: "tradeoff"
    source_ref: "https://www.euaa.europa.eu/publications/providing-temporary-protection-displaced-persons-ukraine"
    title: "Immediate protection and later transition challenge"
  - ref_id: "limitation:country-implementation-variance"
    ref_type: "limitation"
    source_ref: "https://fra.europa.eu/nl/publication/2023/fleeing-ukraine-temporary-protection"
    title: "Local and member-state implementation variance"
  - ref_id: "outcome:rights-access-granted"
    ref_type: "outcome"
    source_ref: "https://commission.europa.eu/topics/eu-solidarity-ukraine/eu-assistance-ukraine/information-people-fleeing-war-ukraine/fleeing-ukraine-your-rights-eu_en"
    title: "Temporary protection rights access"
claims:
  - claim_id: "claim:temporary-protection-immediate-rights"
    claim_type: "legal_status_and_implementation"
    text_ref: "text:case:summary"
    scope:
      population:
        - "eligible_displaced_persons_from_Ukraine"
      geography:
        - "European_Union"
      time_period: "2022-03 to 2027-03"
      institution:
        - "Council_of_the_European_Union"
        - "European_Commission"
        - "EU_member_states"
    evidence_refs:
      - "evidence:euaa-year-in-review"
    method_refs:
      - "method:fra-local-implementation-review"
    legal_refs:
      - "legal:council-implementing-decision-2022-382"
    participation_refs:
      - "participation:member-state-registration"
    risks:
      - "risk:housing-and-services-pressure"
    tradeoffs:
      - "tradeoff:immediate-protection-vs-long-term-transition"
    admissibility_label: "publishable_with_limitation"
    limitation_refs:
      - "limitation:country-implementation-variance"
    contestability_status: "limited"
obligations:
  - obligation_id: "obligation:temporary-protection-rights-realization"
    generated_from_facets:
      - "facet:instrument.temporary_protection"
      - "facet:authority.supranational"
      - "facet:delivery.member_state_implementation"
    required_evidence_family: "rights_access_and_local_implementation_monitoring"
    status: "required_for_production_closeout"
    reviewer_notes: "Production authority must test whether formal rights were realized across housing, education, healthcare, and labour access."
known_outcomes_or_failures:
  - finding_id: "outcome:rights-access-granted"
    source_ref: "outcome:rights-access-granted"
    would_prior_obligation_have_flagged: false
annotation_provenance:
  reviewer_role: "policy_generalist"
  expertise_basis: "W11.A source triage from EU legal, Commission, EUAA, and FRA sources"
  conflicts: []
  reviewed_at: "2026-05-24"
---

# EU Temporary Protection For Ukraine

## Summary

This is a supranational production case where formal legal activation and
actual access to rights are both load-bearing. It exercises eligibility scope,
member-state implementation variance, and transition uncertainty.

## W11.B Handoff

Decompose legal eligibility, registration, housing, education, healthcare,
labour-market access, and transition-out rules. Formal protection should not
launder implementation gaps.
