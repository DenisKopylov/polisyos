---
case_id: "w11a_uk_mtd_vat_2019"
case_title: "United Kingdom Making Tax Digital for VAT"
corpus_phase: "W11.A"
sourcing_status: "sourced"
annotation_status: "annotated_w11b"
expert_adjudication_status: "adjudicated_w11c"
domain: "tax_enforcement"
authority_level: "governed"
jurisdiction_authority_level: "national"
jurisdiction: "United Kingdom"
policy_time: "2019-04 onward"
policy_instrument:
  instrument_type: "digital_tax_recordkeeping_mandate"
  delivery_channel: "HMRC digital VAT submissions through compatible software"
  funding_channel: "tax_administration_programme_budget"
targeting:
  targeting_type: "taxpayer_obligation_by_vat_registration_status"
  beneficiary_classes:
    - "tax_administration"
    - "compliant_taxpayers"
  affected_populations:
    - "vat_registered_businesses"
    - "tax_agents"
    - "software_providers"
expected_evidence_families:
  - "statutory_guidance"
  - "tax_gap_and_revenue_estimate"
  - "business_compliance_cost_analysis"
  - "digital_service_uptake_metrics"
  - "value_for_money_audit"
raw_source_refs:
  - "https://www.gov.uk/government/collections/making-tax-digital-for-vat"
  - "https://www.gov.uk/government/publications/vat-notice-70022-making-tax-digital-for-vat/vat-notice-70022-making-tax-digital-for-vat"
  - "https://www.nao.org.uk/reports/progress-with-making-tax-digital/"
redacted_source_hashes: []
known_failure_limitation_labels:
  - "administrative_burden"
  - "programme_delay"
  - "business_case_cost_omission"
  - "digital_exclusion_risk"
references:
  - ref_id: "text:case:summary"
    ref_type: "source"
    source_ref: "repo://docs/research/universal-policy-design/outcome-corpus/uk-making-tax-digital-vat-2019-tax-enforcement.md#summary"
    title: "Case summary"
  - ref_id: "legal:vat-notice-700-22"
    ref_type: "legal"
    source_ref: "https://www.gov.uk/government/publications/vat-notice-70022-making-tax-digital-for-vat/vat-notice-70022-making-tax-digital-for-vat"
    title: "VAT Notice 700/22 Making Tax Digital for VAT"
  - ref_id: "evidence:nao-progress-mtd"
    ref_type: "evidence"
    source_ref: "https://www.nao.org.uk/reports/progress-with-making-tax-digital/"
    title: "NAO Progress with Making Tax Digital"
  - ref_id: "method:nao-value-for-money-review"
    ref_type: "method"
    source_ref: "https://www.nao.org.uk/reports/progress-with-making-tax-digital/"
    title: "NAO value-for-money review method"
  - ref_id: "participation:taxpayer-agent-software-channel"
    ref_type: "participation"
    source_ref: "https://www.gov.uk/government/collections/making-tax-digital-for-vat"
    title: "Business, agent, and software guidance collection"
  - ref_id: "risk:customer-cost-exclusion"
    ref_type: "risk"
    source_ref: "https://www.nao.org.uk/reports/progress-with-making-tax-digital/"
    title: "Customer cost and programme delay risk"
  - ref_id: "tradeoff:tax-revenue-vs-compliance-burden"
    ref_type: "tradeoff"
    source_ref: "https://www.nao.org.uk/reports/progress-with-making-tax-digital/"
    title: "Additional revenue versus compliance burden"
  - ref_id: "limitation:cost-benefit-incomplete"
    ref_type: "limitation"
    source_ref: "https://www.nao.org.uk/reports/progress-with-making-tax-digital/"
    title: "Business case cost-benefit limitation"
  - ref_id: "outcome:programme-delays-and-cost-growth"
    ref_type: "outcome"
    source_ref: "https://www.nao.org.uk/reports/progress-with-making-tax-digital/"
    title: "NAO finding on delays and cost growth"
claims:
  - claim_id: "claim:mtd-improves-tax-compliance"
    claim_type: "implementation_effectiveness"
    text_ref: "text:case:summary"
    scope:
      population:
        - "vat_registered_businesses"
      geography:
        - "United Kingdom"
      time_period: "2019-04 onward"
      institution:
        - "HM_Revenue_and_Customs"
    evidence_refs:
      - "evidence:nao-progress-mtd"
    method_refs:
      - "method:nao-value-for-money-review"
    legal_refs:
      - "legal:vat-notice-700-22"
    participation_refs:
      - "participation:taxpayer-agent-software-channel"
    risks:
      - "risk:customer-cost-exclusion"
    tradeoffs:
      - "tradeoff:tax-revenue-vs-compliance-burden"
    admissibility_label: "limited"
    limitation_refs:
      - "limitation:cost-benefit-incomplete"
    contestability_status: "contested"
obligations:
  - obligation_id: "obligation:mtd-compliance-burden-vfm"
    generated_from_facets:
      - "facet:instrument.digital_mandate"
      - "facet:targeting.taxpayer_obligation"
      - "facet:risk.administrative_burden"
    required_evidence_family: "value_for_money_and_compliance_cost_analysis"
    status: "required_for_governed_closeout"
    reviewer_notes: "Governed closeout must expose business compliance costs and delay risk, not only HMRC revenue estimates."
known_outcomes_or_failures:
  - finding_id: "outcome:programme-delays-and-cost-growth"
    source_ref: "outcome:programme-delays-and-cost-growth"
    would_prior_obligation_have_flagged: true
annotation_provenance:
  reviewer_role: "policy_generalist"
  expertise_basis: "W11.A source triage from HMRC and NAO materials"
  conflicts: []
  reviewed_at: "2026-05-24"
---

# UK Making Tax Digital For VAT

## Summary

Making Tax Digital for VAT is a digital public administration and tax
enforcement case where service modernization, taxpayer obligations, expected
revenue, and compliance burden need to be kept distinct.

## W11.B Handoff

Claims about extra tax revenue, cost savings, taxpayer experience, and software
market readiness should be decomposed separately. Public projection should show
the compliance-burden limitation when usefulness is claimed.
