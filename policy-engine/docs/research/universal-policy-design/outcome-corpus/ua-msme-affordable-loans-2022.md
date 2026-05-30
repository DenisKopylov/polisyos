---
case_id: ua-msme-affordable-loans-2022
case_title: "Ukraine Affordable Loans 5-7-9 wartime MSME credit support"
corpus_phase: "W11.A"
sourcing_status: "sourced"
annotation_status: "annotated_w11b"
expert_adjudication_status: "adjudicated_w11c"
domain: "msme_credit_grant"
authority_level: "governed"
jurisdiction_authority_level: "national"
jurisdiction: Ukraine
policy_time: "2022-2024"
policy_instrument:
  instrument_type: subsidized_credit_and_partial_guarantee
  delivery_channel: authorized_banks
  funding_channel: state_budget_and_partner_support
targeting:
  targeting_type: enterprise_size_sector_and_wartime-need_rules
  beneficiary_classes:
    - micro_small_and_medium_enterprises
    - agricultural_producers
    - enterprises_in_military_risk_areas
  affected_populations:
    - msme_workers
    - lenders
    - taxpayers
    - displaced_or_war-affected_communities
expected_evidence_families:
  - program_administration_rules
  - bank_portfolio_and_credit_additionality_data
  - fiscal_risk_and_contingent_liability_monitoring
  - wartime_geography_and_sector_targeting_analysis
  - participation_or_institutional_consultation_records
raw_source_refs:
  - https://ukraineinvest.gov.ua/en/news/22-11-22/
  - https://bank.gov.ua/en/news/all/rozvitok--derjavnoyi-programi-dostupni-krediti-5-7-9--u-fokusi-uvagi-zasidannya-radi-z-finansovoyi-stabilnosti
  - https://www.imf.org/en/-/media/files/publications/cr/2023/english/1ukrea2023002.pdf
redacted_source_hashes:
  - sha256:5979a23d573a65d5a3b64a9c4b33f5ce2de6c844b2efb50b94f9d24bb7d84354
known_failure_limitation_labels:
  - credit_additionality_not_established
  - contingent_liability_risk
  - bank_client_channel_bias
  - wartime_portfolio_quality_uncertainty
references:
  - ref_id: text:case:summary
    ref_type: source
    source_ref: repo://docs/research/universal-policy-design/outcome-corpus/ua-msme-affordable-loans-2022.md#case-summary
    title: Case summary
  - ref_id: evidence:ukraineinvest-2022-results
    ref_type: evidence
    source_ref: https://ukraineinvest.gov.ua/en/news/22-11-22/
    title: UkraineInvest programme results as of November 2022
  - ref_id: legal:nbu-financial-stability-council-2022
    ref_type: legal
    source_ref: https://bank.gov.ua/en/news/all/rozvitok--derjavnoyi-programi-dostupni-krediti-5-7-9--u-fokusi-uvagi-zasidannya-radi-z-finansovoyi-stabilnosti
    title: NBU Financial Stability Council discussion of the Affordable Loans programme
  - ref_id: method:imf-emerging-risks-review
    ref_type: method
    source_ref: https://www.imf.org/en/-/media/files/publications/cr/2023/english/1ukrea2023002.pdf
    title: IMF discussion of 5-7-9 role and emerging risks
  - ref_id: participation:fsc-institutional-consultation
    ref_type: participation
    source_ref: https://bank.gov.ua/en/news/all/rozvitok--derjavnoyi-programi-dostupni-krediti-5-7-9--u-fokusi-uvagi-zasidannya-radi-z-finansovoyi-stabilnosti
    title: Financial Stability Council institutional consultation record
  - ref_id: risk:fiscal-and-credit-risk
    ref_type: risk
    source_ref: https://www.imf.org/en/-/media/files/publications/cr/2023/english/1ukrea2023002.pdf
    title: Fiscal and credit-risk warning
  - ref_id: tradeoff:credit-access-vs-contingent-liability
    ref_type: tradeoff
    source_ref: https://www.imf.org/en/-/media/files/publications/cr/2023/english/1ukrea2023002.pdf
    title: Tradeoff between wartime credit access and contingent public risk
  - ref_id: limitation:no-claim-level-counterfactual
    ref_type: limitation
    source_ref: https://www.imf.org/en/-/media/files/publications/cr/2023/english/1ukrea2023002.pdf
    title: Limitation that programme scale-up is not claim-level causal identification
  - ref_id: outcome:wartime-credit-scaleup-with-risk
    ref_type: outcome
    source_ref: https://ukraineinvest.gov.ua/en/news/22-11-22/
    title: Wartime programme scale-up with unresolved risk and targeting questions
  - ref_id: source:redacted-reviewer-notes
    ref_type: source
    redacted_source_hash: sha256:5979a23d573a65d5a3b64a9c4b33f5ce2de6c844b2efb50b94f9d24bb7d84354
    title: Redacted reviewer notes for annotation calibration
claims:
  - claim_id: claim:wartime-credit-access-support
    claim_type: causal_and_implementation
    text_ref: text:case:summary
    scope:
      population:
        - micro_small_and_medium_enterprises
      geography:
        - Ukraine
        - war-affected_regions
      time_period: "2022-2024"
      institution:
        - Cabinet_of_Ministers
        - National_Bank_of_Ukraine
        - authorized_banks
    evidence_refs:
      - evidence:ukraineinvest-2022-results
    method_refs:
      - method:imf-emerging-risks-review
    legal_refs:
      - legal:nbu-financial-stability-council-2022
    participation_refs:
      - participation:fsc-institutional-consultation
    risks:
      - risk:fiscal-and-credit-risk
    tradeoffs:
      - tradeoff:credit-access-vs-contingent-liability
    admissibility_label: limited
    limitation_refs:
      - limitation:no-claim-level-counterfactual
    contestability_status: contested
obligations:
  - obligation_id: obligation:claim-level-credit-additionality
    generated_from_facets:
      - facet:instrument.subsidized_credit
      - facet:delivery.authorized_banks
      - facet:targeting.msme_wartime_need
    required_evidence_family: program_evaluation_or_counterfactual_credit_additionality
    status: limitation_required
    reviewer_notes: >
      A universal compiler should require claim-level evidence separating
      additional credit access for eligible MSMEs from programme volume routed
      through existing bank-client channels.
  - obligation_id: obligation:contingent-liability-and-portfolio-risk
    generated_from_facets:
      - facet:instrument.partial_guarantee
      - facet:authority.public_fiscal_risk
    required_evidence_family: fiscal_risk_and_portfolio_quality_monitoring
    status: review_required
    reviewer_notes: >
      The case should not close as publishable without a limitation or review
      path for contingent liabilities, bank portfolio concentration, and
      wartime credit-risk deterioration.
known_outcomes_or_failures:
  - finding_id: outcome:wartime-credit-scaleup-with-risk
    source_ref: outcome:wartime-credit-scaleup-with-risk
    would_prior_obligation_have_flagged: true
annotation_provenance:
  reviewer_role: policy_generalist
  expertise_basis: public-finance and MSME-credit programme annotation
  conflicts: []
  reviewed_at: "2026-05-24"
authority_boundary:
  authoritative_for:
    - corpus_annotation
    - compilation_truthfulness_reference
  may_not_use_for:
    - claim_authority
    - producer_evidence_authority
    - legal_authority
    - method_validity
    - participation_legitimacy
    - projection_authority
  may_not_be_used_for:
    - claim_authority
    - producer_evidence_authority
    - legal_authority
    - method_validity
    - participation_legitimacy
    - projection_authority
capability_reality_label: implemented
pattern_refs:
  - P01
  - P02
  - P03
  - P05
  - P10
  - P13
  - P14
  - P15
---

# Case Summary

Ukraine's "Affordable Loans 5-7-9%" programme is treated here as a wartime
subsidized-credit and partial-guarantee case. The annotation does not conclude
that the programme caused MSME survival or credit additionality. It records the
minimum claim/evidence decomposition expected from a universal compiler before
Wave 12 compares compiled obligations against reviewer annotations.
