---
case_id: "w11a_ghana_free_shs_2017"
case_title: "Ghana Free Senior High School access expansion"
corpus_phase: "W11.A"
sourcing_status: "sourced"
annotation_status: "annotated_w11b"
expert_adjudication_status: "adjudicated_w11c"
domain: "education_access"
authority_level: "research"
jurisdiction_authority_level: "national"
jurisdiction: "Ghana"
policy_time: "2017-09 onward"
policy_instrument:
  instrument_type: "fee_abolition_and_public_secondary_school_subsidy"
  delivery_channel: "public senior high schools"
  funding_channel: "national_budget"
targeting:
  targeting_type: "universal_access_by_school_level"
  beneficiary_classes:
    - "public_senior_high_school_students"
    - "lower_income_households"
  affected_populations:
    - "teachers"
    - "school_administrators"
    - "parents"
    - "taxpayers"
expected_evidence_families:
  - "education_budget_and_enrollment_data"
  - "infrastructure_capacity_assessment"
  - "learning_outcome_evaluation"
  - "household_cost_analysis"
  - "stakeholder_consultation_evidence"
raw_source_refs:
  - "https://moe.gov.gh/free-shs-intervention-project/"
  - "https://ndpc.gov.gh/media/Ministry_of_Education_APR_2019.pdf"
  - "https://www.uew.edu.gh/def/staff/sdansah/publications/28230/detail"
redacted_source_hashes: []
known_failure_limitation_labels:
  - "infrastructure_capacity_constraint"
  - "funding_sustainability_contested"
  - "quality_access_tradeoff"
  - "stakeholder_consensus_gap"
references:
  - ref_id: "text:case:summary"
    ref_type: "source"
    source_ref: "repo://docs/research/universal-policy-design/outcome-corpus/ghana-free-shs-2017-education-access.md#summary"
    title: "Case summary"
  - ref_id: "legal:free-shs-policy"
    ref_type: "legal"
    source_ref: "https://moe.gov.gh/free-shs-intervention-project/"
    title: "Ghana Ministry of Education Free SHS intervention project"
  - ref_id: "evidence:education-sector-apr-2019"
    ref_type: "evidence"
    source_ref: "https://ndpc.gov.gh/media/Ministry_of_Education_APR_2019.pdf"
    title: "Ghana Ministry of Education annual progress report 2019"
  - ref_id: "method:implementation-assessment"
    ref_type: "method"
    source_ref: "https://www.uew.edu.gh/def/staff/sdansah/publications/28230/detail"
    title: "Free SHS programme implementation assessment"
  - ref_id: "participation:stakeholder-consensus-recommendation"
    ref_type: "participation"
    source_ref: "https://www.uew.edu.gh/def/staff/sdansah/publications/28230/detail"
    title: "Recommendation for stakeholder engagement and national consensus"
  - ref_id: "risk:capacity-overcrowding"
    ref_type: "risk"
    source_ref: "https://moe.gov.gh/free-shs-intervention-project/"
    title: "Infrastructure need to accommodate extra students"
  - ref_id: "tradeoff:access-vs-quality"
    ref_type: "tradeoff"
    source_ref: "https://www.uew.edu.gh/def/staff/sdansah/publications/28230/detail"
    title: "Access expansion and implementation quality tradeoff"
  - ref_id: "limitation:infrastructure-and-funding"
    ref_type: "limitation"
    source_ref: "https://www.uew.edu.gh/def/staff/sdansah/publications/28230/detail"
    title: "Implementation challenges and funding/infrastructure limitations"
  - ref_id: "outcome:enrollment-surge-capacity-pressure"
    ref_type: "outcome"
    source_ref: "https://ndpc.gov.gh/media/Ministry_of_Education_APR_2019.pdf"
    title: "Enrollment increase and secondary education capacity pressure"
claims:
  - claim_id: "claim:free-shs-expands-access"
    claim_type: "access_and_implementation"
    text_ref: "text:case:summary"
    scope:
      population:
        - "public_senior_high_school_students"
      geography:
        - "Ghana"
      time_period: "2017-09 onward"
      institution:
        - "Ministry_of_Education_Ghana"
        - "Ghana_Education_Service"
    evidence_refs:
      - "evidence:education-sector-apr-2019"
    method_refs:
      - "method:implementation-assessment"
    legal_refs:
      - "legal:free-shs-policy"
    participation_refs:
      - "participation:stakeholder-consensus-recommendation"
    risks:
      - "risk:capacity-overcrowding"
    tradeoffs:
      - "tradeoff:access-vs-quality"
    admissibility_label: "limited"
    limitation_refs:
      - "limitation:infrastructure-and-funding"
    contestability_status: "contested"
obligations:
  - obligation_id: "obligation:free-shs-access-quality-split"
    generated_from_facets:
      - "facet:instrument.fee_abolition"
      - "facet:targeting.universal_school_level"
      - "facet:outcome.education_access"
    required_evidence_family: "enrollment_quality_and_capacity_evaluation"
    status: "required_for_research_closeout"
    reviewer_notes: "Research use may cite access expansion, but useful-design scoring should require separate quality and capacity evidence."
known_outcomes_or_failures:
  - finding_id: "outcome:enrollment-surge-capacity-pressure"
    source_ref: "outcome:enrollment-surge-capacity-pressure"
    would_prior_obligation_have_flagged: true
annotation_provenance:
  reviewer_role: "policy_generalist"
  expertise_basis: "W11.A source triage from Ghana MoE, NDPC, and implementation-assessment sources"
  conflicts: []
  reviewed_at: "2026-05-24"
---

# Ghana Free Senior High School

## Summary

Free SHS is a useful education-access case because the central claim is not
just "more students entered school"; it also carries capacity, quality,
financing, and consultation obligations.

## W11.B Handoff

Split access, fiscal sustainability, infrastructure capacity, and learning
quality into separate claims. The case should not pass as useful design if it
only proves enrollment expansion.
