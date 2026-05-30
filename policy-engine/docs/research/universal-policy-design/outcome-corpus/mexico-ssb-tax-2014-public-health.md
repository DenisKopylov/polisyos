---
case_id: "w11a_mexico_ssb_tax_2014"
case_title: "Mexico sugar-sweetened beverage excise tax"
corpus_phase: "W11.A"
sourcing_status: "sourced"
annotation_status: "annotated_w11b"
expert_adjudication_status: "adjudicated_w11c"
domain: "public_health_intervention"
authority_level: "research"
jurisdiction_authority_level: "national"
jurisdiction: "Mexico"
policy_time: "2014-01 onward"
policy_instrument:
  instrument_type: "excise_tax"
  delivery_channel: "producer_and_importer_tax_on_sugar_sweetened_beverages"
  funding_channel: "national_tax_revenue"
targeting:
  targeting_type: "population_wide_price_signal"
  beneficiary_classes:
    - "population_at_risk_of_obesity_and_diabetes"
    - "low_income_households_exposed_to_high_ssb_consumption"
  affected_populations:
    - "beverage_consumers"
    - "beverage_producers"
    - "retailers"
expected_evidence_families:
  - "tax_law_and_rate_design"
  - "household_purchase_panel"
  - "price_pass_through_analysis"
  - "public_health_outcome_model"
  - "substitution_and_equity_analysis"
raw_source_refs:
  - "https://www.dof.gob.mx/nota_detalle.php?codigo=5378141&fecha=07/01/2015"
  - "https://www.bmj.com/content/352/bmj.h6704"
  - "https://www.paho.org/en/node/78468"
redacted_source_hashes: []
known_failure_limitation_labels:
  - "observational_causal_identification_limit"
  - "tax_rate_sufficiency_contested"
  - "substitution_risk"
  - "health_outcome_lag"
references:
  - ref_id: "text:case:summary"
    ref_type: "source"
    source_ref: "repo://docs/research/universal-policy-design/outcome-corpus/mexico-ssb-tax-2014-public-health.md#summary"
    title: "Case summary"
  - ref_id: "legal:ieps-ssb-rate"
    ref_type: "legal"
    source_ref: "https://www.dof.gob.mx/nota_detalle.php?codigo=5378141&fecha=07/01/2015"
    title: "Diario Oficial de la Federacion IEPS flavored beverages rate"
  - ref_id: "evidence:bmj-purchase-panel"
    ref_type: "evidence"
    source_ref: "https://www.bmj.com/content/352/bmj.h6704"
    title: "BMJ observational study of beverage purchases under the tax"
  - ref_id: "method:counterfactual-purchase-trend"
    ref_type: "method"
    source_ref: "https://www.bmj.com/content/352/bmj.h6704"
    title: "Observed purchases compared with predicted counterfactual volumes"
  - ref_id: "participation:public-health-tax-framing"
    ref_type: "participation"
    source_ref: "https://www.paho.org/en/node/78468"
    title: "PAHO regional framing of sugar-sweetened beverage taxation"
  - ref_id: "risk:substitution-and-package-pricing"
    ref_type: "risk"
    source_ref: "https://www.bmj.com/content/352/bmj.h6704"
    title: "Substitution and package-size pass-through concern"
  - ref_id: "tradeoff:revenue-vs-regressivity"
    ref_type: "tradeoff"
    source_ref: "https://www.paho.org/en/node/78468"
    title: "Excise tax public health rationale and economic impacts"
  - ref_id: "limitation:observational-health-effect"
    ref_type: "limitation"
    source_ref: "https://www.bmj.com/content/352/bmj.h6704"
    title: "Short-run observational purchase outcome limitation"
  - ref_id: "outcome:purchases-declined-first-year"
    ref_type: "outcome"
    source_ref: "https://www.bmj.com/content/352/bmj.h6704"
    title: "Lower observed taxed beverage purchases in 2014"
claims:
  - claim_id: "claim:ssb-tax-reduces-purchases"
    claim_type: "causal"
    text_ref: "text:case:summary"
    scope:
      population:
        - "beverage_consumers"
      geography:
        - "Mexico"
      time_period: "2014"
      institution:
        - "Mexican_tax_authority"
        - "public_health_researchers"
    evidence_refs:
      - "evidence:bmj-purchase-panel"
    method_refs:
      - "method:counterfactual-purchase-trend"
    legal_refs:
      - "legal:ieps-ssb-rate"
    participation_refs:
      - "participation:public-health-tax-framing"
    risks:
      - "risk:substitution-and-package-pricing"
    tradeoffs:
      - "tradeoff:revenue-vs-regressivity"
    admissibility_label: "limited"
    limitation_refs:
      - "limitation:observational-health-effect"
    contestability_status: "contested"
obligations:
  - obligation_id: "obligation:ssb-tax-health-linkage"
    generated_from_facets:
      - "facet:instrument.excise_tax"
      - "facet:outcome.public_health_behavior"
      - "facet:method.observational_panel"
    required_evidence_family: "causal_or_quasi_experimental_public_health_evaluation"
    status: "limitation_required"
    reviewer_notes: "Research authority may use purchase evidence, but production claims about health outcomes need longer-run health and substitution evidence."
known_outcomes_or_failures:
  - finding_id: "outcome:purchases-declined-first-year"
    source_ref: "outcome:purchases-declined-first-year"
    would_prior_obligation_have_flagged: false
annotation_provenance:
  reviewer_role: "policy_generalist"
  expertise_basis: "W11.A source triage from DOF, BMJ, and PAHO materials"
  conflicts: []
  reviewed_at: "2026-05-24"
---

# Mexico Sugar-Sweetened Beverage Excise Tax

## Summary

Mexico introduced a national excise tax on sugar-sweetened beverages in 2014.
The case is useful for universal compilation because the same instrument is
simultaneously legal/tax, public-health, distributional, and behavioral.

## W11.B Handoff

Separate the legal tax-rate claim, the behavioral purchase claim, and the
health-outcome claim. The first has statutory authority; the second has
observational support; the third should remain limited unless later health
evidence is supplied.
