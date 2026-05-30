---
case_id: "w11a_uk_levelling_up_fund_2021"
case_title: "United Kingdom Levelling Up Fund local infrastructure prioritisation"
corpus_phase: "W11.A"
sourcing_status: "sourced"
annotation_status: "annotated_w11b"
expert_adjudication_status: "adjudicated_w11c"
domain: "infrastructure_prioritisation"
authority_level: "governed"
jurisdiction_authority_level: "national"
jurisdiction: "United Kingdom"
policy_time: "2021-22 to 2025-26"
policy_instrument:
  instrument_type: "competitive_capital_grant_fund"
  delivery_channel: "local authority bids for transport, regeneration, culture, and heritage projects"
  funding_channel: "central_government_capital_grants"
targeting:
  targeting_type: "place_prioritisation_and_bid_assessment"
  beneficiary_classes:
    - "places_selected_for_local_infrastructure_projects"
    - "local_residents_and_businesses"
  affected_populations:
    - "unsuccessful_places"
    - "local_authorities"
    - "construction_supply_chain"
    - "taxpayers"
expected_evidence_families:
  - "place_prioritisation_methodology"
  - "bid_assessment_records"
  - "project_delivery_milestones"
  - "regional_distribution_analysis"
  - "monitoring_and_evaluation_plan"
raw_source_refs:
  - "https://www.gov.uk/government/publications/levelling-up-fund-round-2-prospectus/levelling-up-fund-round-2-prospectus"
  - "https://www.gov.uk/guidance/levelling-up-fund-round-3-explanatory-and-methodology-note-on-the-decision-making-process"
  - "https://www.nao.org.uk/press-releases/levelling-up-funding-to-local-government/"
redacted_source_hashes: []
known_failure_limitation_labels:
  - "competitive_bid_burden"
  - "delivery_delay"
  - "prioritisation_transparency_contested"
  - "local_capacity_constraint"
references:
  - ref_id: "text:case:summary"
    ref_type: "source"
    source_ref: "repo://docs/research/universal-policy-design/outcome-corpus/uk-levelling-up-fund-2021-infrastructure.md#summary"
    title: "Case summary"
  - ref_id: "legal:luf-round-2-prospectus"
    ref_type: "legal"
    source_ref: "https://www.gov.uk/government/publications/levelling-up-fund-round-2-prospectus/levelling-up-fund-round-2-prospectus"
    title: "Levelling Up Fund Round 2 prospectus"
  - ref_id: "evidence:nao-luf-delivery"
    ref_type: "evidence"
    source_ref: "https://www.nao.org.uk/press-releases/levelling-up-funding-to-local-government/"
    title: "NAO report on levelling up funding to local government"
  - ref_id: "method:luf-decision-methodology"
    ref_type: "method"
    source_ref: "https://www.gov.uk/guidance/levelling-up-fund-round-3-explanatory-and-methodology-note-on-the-decision-making-process"
    title: "Levelling Up Fund decision-making methodology note"
  - ref_id: "participation:local-authority-bids"
    ref_type: "participation"
    source_ref: "https://www.gov.uk/government/publications/levelling-up-fund-round-2-prospectus/levelling-up-fund-round-2-prospectus"
    title: "Local authority competitive bid process"
  - ref_id: "risk:delivery-delay-and-cost-pressure"
    ref_type: "risk"
    source_ref: "https://www.nao.org.uk/press-releases/levelling-up-funding-to-local-government/"
    title: "Delivery delay and cost pressure risk"
  - ref_id: "tradeoff:visible-projects-vs-evidence-based-need"
    ref_type: "tradeoff"
    source_ref: "https://www.gov.uk/government/publications/levelling-up-fund-round-2-prospectus/levelling-up-fund-round-2-prospectus"
    title: "Visible local infrastructure and need prioritisation tradeoff"
  - ref_id: "limitation:local-delivery-risk"
    ref_type: "limitation"
    source_ref: "https://www.nao.org.uk/press-releases/levelling-up-funding-to-local-government/"
    title: "Local project delivery and deadline limitation"
  - ref_id: "outcome:projects-behind-deadlines"
    ref_type: "outcome"
    source_ref: "https://www.nao.org.uk/press-releases/levelling-up-funding-to-local-government/"
    title: "Projects behind expected delivery deadlines"
claims:
  - claim_id: "claim:luf-prioritises-local-infrastructure"
    claim_type: "prioritisation_and_delivery"
    text_ref: "text:case:summary"
    scope:
      population:
        - "local_residents_and_businesses"
        - "local_authorities"
      geography:
        - "United_Kingdom"
      time_period: "2021-22 to 2025-26"
      institution:
        - "Department_for_Levelling_Up_Housing_and_Communities"
        - "HM_Treasury"
        - "local_authorities"
    evidence_refs:
      - "evidence:nao-luf-delivery"
    method_refs:
      - "method:luf-decision-methodology"
    legal_refs:
      - "legal:luf-round-2-prospectus"
    participation_refs:
      - "participation:local-authority-bids"
    risks:
      - "risk:delivery-delay-and-cost-pressure"
    tradeoffs:
      - "tradeoff:visible-projects-vs-evidence-based-need"
    admissibility_label: "limited"
    limitation_refs:
      - "limitation:local-delivery-risk"
    contestability_status: "contested"
obligations:
  - obligation_id: "obligation:luf-prioritisation-and-delivery"
    generated_from_facets:
      - "facet:instrument.competitive_capital_grant"
      - "facet:targeting.place_prioritisation"
      - "facet:delivery.local_authority_projects"
    required_evidence_family: "prioritisation_method_and_delivery_monitoring"
    status: "required_for_governed_closeout"
    reviewer_notes: "Governed closeout must surface bid burden, place-selection method, and delivery delay rather than only allocated funding totals."
known_outcomes_or_failures:
  - finding_id: "outcome:projects-behind-deadlines"
    source_ref: "outcome:projects-behind-deadlines"
    would_prior_obligation_have_flagged: true
annotation_provenance:
  reviewer_role: "policy_generalist"
  expertise_basis: "W11.A source triage from UK prospectus, methodology note, and NAO audit materials"
  conflicts: []
  reviewed_at: "2026-05-24"
---

# UK Levelling Up Fund

## Summary

The Levelling Up Fund is an infrastructure-prioritisation case that tests
whether PolicyOS can keep place-need methodology, competitive bidding, delivery
risk, and public value separate.

## W11.B Handoff

Do not allow allocated money or project count to stand in for useful design.
The annotation should require prioritisation transparency and delivery evidence.
