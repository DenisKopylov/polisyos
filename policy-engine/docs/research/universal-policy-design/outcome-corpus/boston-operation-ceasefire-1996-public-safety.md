---
case_id: "w11a_boston_operation_ceasefire_1996"
case_title: "Boston Operation Ceasefire focused deterrence intervention"
corpus_phase: "W11.A"
sourcing_status: "sourced"
annotation_status: "annotated_w11b"
expert_adjudication_status: "adjudicated_w11c"
domain: "public_safety"
authority_level: "research"
jurisdiction_authority_level: "local"
jurisdiction: "Boston, Massachusetts, United States"
policy_time: "1996-05 to 2000 evaluation window"
policy_instrument:
  instrument_type: "focused_deterrence_and_problem_oriented_policing"
  delivery_channel: "multi-agency law enforcement and community intervention"
  funding_channel: "local and federal criminal justice resources"
targeting:
  targeting_type: "high_risk_group_and_illicit_firearms_network_focus"
  beneficiary_classes:
    - "youth_at_risk_of_gun_violence"
    - "neighborhoods_exposed_to_youth_homicide"
  affected_populations:
    - "gang_involved_youth"
    - "police"
    - "community_organizations"
    - "prosecutors"
expected_evidence_families:
  - "crime_incident_time_series"
  - "implementation_fidelity_records"
  - "community_participation_evidence"
  - "deterrence_mechanism_evidence"
  - "replication_and_external_validity_review"
raw_source_refs:
  - "https://nij.ojp.gov/library/publications/problem-oriented-policing-deterrence-and-youth-violence-evaluation-bostons"
  - "https://nij.ojp.gov/library/publications/reducing-gun-violence-boston-gun-projects-operation-ceasefire"
  - "https://crimesolutions.ojp.gov/ratedprograms/operation-ceasefire-boston-mass"
redacted_source_hashes: []
known_failure_limitation_labels:
  - "one_group_time_series_limit"
  - "replication_context_dependency"
  - "community_legitimacy_requirement"
  - "enforcement_displacement_risk"
references:
  - ref_id: "text:case:summary"
    ref_type: "source"
    source_ref: "repo://docs/research/universal-policy-design/outcome-corpus/boston-operation-ceasefire-1996-public-safety.md#summary"
    title: "Case summary"
  - ref_id: "legal:operation-ceasefire-local-authority"
    ref_type: "legal"
    source_ref: "https://nij.ojp.gov/library/publications/reducing-gun-violence-boston-gun-projects-operation-ceasefire"
    title: "Boston Gun Project Operation Ceasefire report"
  - ref_id: "evidence:nij-ceasefire-evaluation"
    ref_type: "evidence"
    source_ref: "https://nij.ojp.gov/library/publications/problem-oriented-policing-deterrence-and-youth-violence-evaluation-bostons"
    title: "NIJ evaluation of Boston Operation Ceasefire"
  - ref_id: "method:one-group-time-series"
    ref_type: "method"
    source_ref: "https://nij.ojp.gov/library/publications/reducing-gun-violence-boston-gun-projects-operation-ceasefire"
    title: "One-group time-series evaluation design"
  - ref_id: "participation:community-and-agency-partnership"
    ref_type: "participation"
    source_ref: "https://nij.ojp.gov/library/publications/reducing-gun-violence-boston-gun-projects-operation-ceasefire"
    title: "Multi-agency and community partnership model"
  - ref_id: "risk:replication-fidelity"
    ref_type: "risk"
    source_ref: "https://crimesolutions.ojp.gov/ratedprograms/operation-ceasefire-boston-mass"
    title: "CrimeSolutions rated program profile and replication context"
  - ref_id: "tradeoff:focused-deterrence-vs-over-enforcement"
    ref_type: "tradeoff"
    source_ref: "https://nij.ojp.gov/library/publications/problem-oriented-policing-deterrence-and-youth-violence-evaluation-bostons"
    title: "Focused deterrence and enforcement-legitimacy tradeoff"
  - ref_id: "limitation:evaluation-design-limits"
    ref_type: "limitation"
    source_ref: "https://nij.ojp.gov/library/publications/reducing-gun-violence-boston-gun-projects-operation-ceasefire"
    title: "Evaluation design and external validity limitations"
  - ref_id: "outcome:youth-violence-reduction-claim"
    ref_type: "outcome"
    source_ref: "https://crimesolutions.ojp.gov/ratedprograms/operation-ceasefire-boston-mass"
    title: "CrimeSolutions outcome profile"
claims:
  - claim_id: "claim:ceasefire-reduced-youth-gun-violence"
    claim_type: "causal"
    text_ref: "text:case:summary"
    scope:
      population:
        - "youth_at_risk_of_gun_violence"
        - "gang_involved_youth"
      geography:
        - "Boston"
      time_period: "1996-05 to 2000 evaluation window"
      institution:
        - "Boston_Police_Department"
        - "National_Institute_of_Justice"
        - "community_partners"
    evidence_refs:
      - "evidence:nij-ceasefire-evaluation"
    method_refs:
      - "method:one-group-time-series"
    legal_refs:
      - "legal:operation-ceasefire-local-authority"
    participation_refs:
      - "participation:community-and-agency-partnership"
    risks:
      - "risk:replication-fidelity"
    tradeoffs:
      - "tradeoff:focused-deterrence-vs-over-enforcement"
    admissibility_label: "limited"
    limitation_refs:
      - "limitation:evaluation-design-limits"
    contestability_status: "contested"
obligations:
  - obligation_id: "obligation:ceasefire-fidelity-and-legitimacy"
    generated_from_facets:
      - "facet:instrument.focused_deterrence"
      - "facet:targeting.high_risk_group"
      - "facet:method.time_series"
    required_evidence_family: "implementation_fidelity_and_external_validity_review"
    status: "required_for_research_closeout"
    reviewer_notes: "Research use should preserve the evaluation-design limitation and require fidelity evidence before transfer to another city."
known_outcomes_or_failures:
  - finding_id: "outcome:youth-violence-reduction-claim"
    source_ref: "outcome:youth-violence-reduction-claim"
    would_prior_obligation_have_flagged: false
annotation_provenance:
  reviewer_role: "policy_generalist"
  expertise_basis: "W11.A source triage from NIJ and CrimeSolutions sources"
  conflicts: []
  reviewed_at: "2026-05-24"
---

# Boston Operation Ceasefire

## Summary

Operation Ceasefire is a public-safety case that should exercise causal
evidence, external validity, implementation fidelity, and participation or
legitimacy obligations.

## W11.B Handoff

The claim that violence fell under the intervention should remain research
authority unless the compiler also demands implementation fidelity,
community-legitimacy, and replication-context evidence.
