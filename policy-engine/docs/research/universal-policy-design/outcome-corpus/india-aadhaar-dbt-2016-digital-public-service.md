---
case_id: "w11a_india_aadhaar_dbt_2016"
case_title: "India Aadhaar-enabled Direct Benefit Transfer"
corpus_phase: "W11.A"
sourcing_status: "sourced"
annotation_status: "annotated_w11b"
expert_adjudication_status: "adjudicated_w11c"
domain: "digital_public_service"
authority_level: "production"
jurisdiction_authority_level: "national"
jurisdiction: "India"
policy_time: "2016-09 onward"
policy_instrument:
  instrument_type: "digital_identity_enabled_benefit_delivery"
  delivery_channel: "Aadhaar authentication and Direct Benefit Transfer systems"
  funding_channel: "consolidated_fund_benefit_and_subsidy_programmes"
targeting:
  targeting_type: "identity_linkage_for_eligible_beneficiaries"
  beneficiary_classes:
    - "benefit_and_subsidy_recipients"
    - "welfare_programme_administrators"
  affected_populations:
    - "residents_without_reliable_biometrics_or_documents"
    - "banks_and_payment_agents"
    - "state_and_central_departments"
expected_evidence_families:
  - "statutory_authority_and_court_limits"
  - "authentication_success_failure_data"
  - "benefit_delivery_and_exclusion_audit"
  - "privacy_and_data_protection_assessment"
  - "grievance_and_recourse_records"
raw_source_refs:
  - "https://www.uidai.gov.in/en/about-uidai/legal-framework/2033-aadhaar-targeted-delivery-of-financial-and-other-subsidies%2C-benefits-and-services-act%2C-2016.html"
  - "https://www.uidai.gov.in/en/309-faqs/direct-benefit-transfer-dbt/about-dbt.html"
  - "https://uidai.gov.in/en/about-uidai/legal-framework/judgements/13583-justice-k-s-puttaswamy-retd-and-anr-vs-uoi-and-ors-dated-26-09-2018-five-judges-constitutional-bench.html"
redacted_source_hashes: []
known_failure_limitation_labels:
  - "privacy_rights_contested"
  - "beneficiary_exclusion_risk"
  - "authentication_failure_risk"
  - "purpose_limitation_required"
references:
  - ref_id: "text:case:summary"
    ref_type: "source"
    source_ref: "repo://docs/research/universal-policy-design/outcome-corpus/india-aadhaar-dbt-2016-digital-public-service.md#summary"
    title: "Case summary"
  - ref_id: "legal:aadhaar-act-2016"
    ref_type: "legal"
    source_ref: "https://www.uidai.gov.in/en/about-uidai/legal-framework/2033-aadhaar-targeted-delivery-of-financial-and-other-subsidies%2C-benefits-and-services-act%2C-2016.html"
    title: "Aadhaar Act 2016"
  - ref_id: "legal:puttaswamy-aadhaar-judgment"
    ref_type: "legal"
    source_ref: "https://uidai.gov.in/en/about-uidai/legal-framework/judgements/13583-justice-k-s-puttaswamy-retd-and-anr-vs-uoi-and-ors-dated-26-09-2018-five-judges-constitutional-bench.html"
    title: "Justice K.S. Puttaswamy Aadhaar judgment"
  - ref_id: "evidence:uidai-dbt-faq"
    ref_type: "evidence"
    source_ref: "https://www.uidai.gov.in/en/309-faqs/direct-benefit-transfer-dbt/about-dbt.html"
    title: "UIDAI Aadhaar for Direct Benefit Transfer FAQ"
  - ref_id: "method:identity-authentication-delivery"
    ref_type: "method"
    source_ref: "https://www.uidai.gov.in/en/309-faqs/direct-benefit-transfer-dbt/about-dbt.html"
    title: "Aadhaar authentication and benefit delivery mechanism"
  - ref_id: "participation:beneficiary-authentication-channel"
    ref_type: "participation"
    source_ref: "https://www.uidai.gov.in/en/309-faqs/direct-benefit-transfer-dbt/about-dbt.html"
    title: "Beneficiary authentication and update pathway"
  - ref_id: "risk:privacy-and-exclusion"
    ref_type: "risk"
    source_ref: "https://uidai.gov.in/en/about-uidai/legal-framework/judgements/13583-justice-k-s-puttaswamy-retd-and-anr-vs-uoi-and-ors-dated-26-09-2018-five-judges-constitutional-bench.html"
    title: "Privacy, proportionality, and exclusion litigation risk"
  - ref_id: "tradeoff:leakage-control-vs-rights"
    ref_type: "tradeoff"
    source_ref: "https://uidai.gov.in/en/about-uidai/legal-framework/judgements/13583-justice-k-s-puttaswamy-retd-and-anr-vs-uoi-and-ors-dated-26-09-2018-five-judges-constitutional-bench.html"
    title: "Leakage reduction and rights limitation tradeoff"
  - ref_id: "limitation:section-7-purpose-boundary"
    ref_type: "limitation"
    source_ref: "https://www.uidai.gov.in/en/309-faqs/direct-benefit-transfer-dbt/about-dbt.html"
    title: "Aadhaar mandate tied to Section 7 benefit and subsidy purposes"
  - ref_id: "outcome:dbt-enabled-benefit-delivery"
    ref_type: "outcome"
    source_ref: "https://www.uidai.gov.in/en/309-faqs/direct-benefit-transfer-dbt/about-dbt.html"
    title: "Aadhaar-enabled benefit delivery"
claims:
  - claim_id: "claim:aadhaar-dbt-targets-benefits"
    claim_type: "implementation_and_rights"
    text_ref: "text:case:summary"
    scope:
      population:
        - "benefit_and_subsidy_recipients"
      geography:
        - "India"
      time_period: "2016-09 onward"
      institution:
        - "UIDAI"
        - "central_and_state_governments"
        - "Supreme_Court_of_India"
    evidence_refs:
      - "evidence:uidai-dbt-faq"
    method_refs:
      - "method:identity-authentication-delivery"
    legal_refs:
      - "legal:aadhaar-act-2016"
      - "legal:puttaswamy-aadhaar-judgment"
    participation_refs:
      - "participation:beneficiary-authentication-channel"
    risks:
      - "risk:privacy-and-exclusion"
    tradeoffs:
      - "tradeoff:leakage-control-vs-rights"
    admissibility_label: "publishable_with_limitation"
    limitation_refs:
      - "limitation:section-7-purpose-boundary"
    contestability_status: "contested"
obligations:
  - obligation_id: "obligation:aadhaar-exclusion-and-purpose-limits"
    generated_from_facets:
      - "facet:instrument.digital_identity"
      - "facet:delivery.direct_benefit_transfer"
      - "facet:risk.privacy_exclusion"
    required_evidence_family: "rights_exclusion_and_recourse_audit"
    status: "required_for_production_closeout"
    reviewer_notes: "Production useful design must carry purpose limitation, exclusion-risk, and recourse evidence alongside delivery-efficiency claims."
known_outcomes_or_failures:
  - finding_id: "outcome:dbt-enabled-benefit-delivery"
    source_ref: "outcome:dbt-enabled-benefit-delivery"
    would_prior_obligation_have_flagged: null
annotation_provenance:
  reviewer_role: "policy_generalist"
  expertise_basis: "W11.A source triage from UIDAI legal and DBT materials"
  conflicts: []
  reviewed_at: "2026-05-24"
---

# India Aadhaar-Enabled Direct Benefit Transfer

## Summary

Aadhaar-enabled DBT is a production digital public service case where the same
policy claim touches identity, subsidy authority, privacy, exclusion, and
recourse. It is a strong P05/P15 firewall case because technical delivery
cannot become rights authority.

## W11.B Handoff

Separate targeting accuracy, leakage reduction, authentication failure,
privacy, statutory purpose, and recourse claims. Claims outside Section 7 style
benefit/subsidy purposes should be capped or blocked.
