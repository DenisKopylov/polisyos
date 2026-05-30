---
case_id: "w11a_berlin_rent_cap_2020"
case_title: "Berlin rent cap and legal competence failure"
corpus_phase: "W11.A"
sourcing_status: "sourced"
annotation_status: "annotated_w11b"
expert_adjudication_status: "adjudicated_w11c"
domain: "housing_rent_control"
authority_level: "governed"
jurisdiction_authority_level: "subnational"
jurisdiction: "Berlin, Germany"
policy_time: "2020-02 to 2021-04"
policy_instrument:
  instrument_type: "rent_cap"
  delivery_channel: "state housing rent regulation and enforcement"
  funding_channel: null
targeting:
  targeting_type: "regulated_market_segment"
  beneficiary_classes:
    - "tenants_in_covered_existing_rental_units"
  affected_populations:
    - "landlords"
    - "prospective_renters"
    - "state_enforcement_authorities"
expected_evidence_families:
  - "legal_competence_analysis"
  - "rent_market_administrative_data"
  - "tenant_landlord_distributional_analysis"
  - "housing_supply_response"
  - "court_outcome_tracking"
raw_source_refs:
  - "https://www.berlin.de/gerichte/presse/pressemitteilungen-der-ordentlichen-gerichtsbarkeit/2020/pressemitteilung.967839.php"
  - "https://www.bundesverfassungsgericht.de/SharedDocs/Pressemitteilungen/EN/2021/bvg21-028.html"
  - "https://housingrightswatch.org/jurisprudence/german-constitutional-court-order-2-bvf-120-2-bvl-520-2-bvl-420-25032021"
redacted_source_hashes: []
known_failure_limitation_labels:
  - "legal_competence_block"
  - "housing_supply_response_uncertain"
  - "tenant_landlord_distributional_tradeoff"
  - "retroactive_reliance_risk"
references:
  - ref_id: "text:case:summary"
    ref_type: "source"
    source_ref: "repo://docs/research/universal-policy-design/outcome-corpus/berlin-rent-cap-2020-housing.md#summary"
    title: "Case summary"
  - ref_id: "legal:berlin-mietenwog-litigation"
    ref_type: "legal"
    source_ref: "https://www.berlin.de/gerichte/presse/pressemitteilungen-der-ordentlichen-gerichtsbarkeit/2020/pressemitteilung.967839.php"
    title: "Berlin court press release on MietenWoG Bln proceedings"
  - ref_id: "legal:bverfg-rent-cap-void"
    ref_type: "legal"
    source_ref: "https://www.bundesverfassungsgericht.de/SharedDocs/Pressemitteilungen/EN/2021/bvg21-028.html"
    title: "Federal Constitutional Court press release declaring Berlin rent cap void"
  - ref_id: "evidence:housing-rights-watch-case-note"
    ref_type: "evidence"
    source_ref: "https://housingrightswatch.org/jurisprudence/german-constitutional-court-order-2-bvf-120-2-bvl-520-2-bvl-420-25032021"
    title: "Housing Rights Watch case note on the Constitutional Court order"
  - ref_id: "method:competence-first-review"
    ref_type: "method"
    source_ref: "https://www.bundesverfassungsgericht.de/SharedDocs/Pressemitteilungen/EN/2021/bvg21-028.html"
    title: "Competence review before housing-market merits"
  - ref_id: "participation:tenant-landlord-litigation-channel"
    ref_type: "participation"
    source_ref: "https://www.berlin.de/gerichte/presse/pressemitteilungen-der-ordentlichen-gerichtsbarkeit/2020/pressemitteilung.967839.php"
    title: "Tenant-landlord dispute pathway"
  - ref_id: "risk:invalid-state-authority"
    ref_type: "risk"
    source_ref: "https://www.bundesverfassungsgericht.de/SharedDocs/Pressemitteilungen/EN/2021/bvg21-028.html"
    title: "State authority competence risk"
  - ref_id: "tradeoff:rent-relief-vs-supply"
    ref_type: "tradeoff"
    source_ref: "https://housingrightswatch.org/jurisprudence/german-constitutional-court-order-2-bvf-120-2-bvl-520-2-bvl-420-25032021"
    title: "Rent relief and housing-market response tradeoff"
  - ref_id: "limitation:legal-authority-blocker"
    ref_type: "limitation"
    source_ref: "https://www.bundesverfassungsgericht.de/SharedDocs/Pressemitteilungen/EN/2021/bvg21-028.html"
    title: "Legal authority blocker"
  - ref_id: "outcome:law-void"
    ref_type: "outcome"
    source_ref: "https://www.bundesverfassungsgericht.de/SharedDocs/Pressemitteilungen/EN/2021/bvg21-028.html"
    title: "Rent cap declared void"
claims:
  - claim_id: "claim:berlin-rent-cap-tenant-relief"
    claim_type: "legal_and_distributional"
    text_ref: "text:case:summary"
    scope:
      population:
        - "covered_tenants"
        - "landlords"
      geography:
        - "Berlin"
      time_period: "2020-02 to 2021-04"
      institution:
        - "Berlin_Senate"
        - "Federal_Constitutional_Court"
    evidence_refs:
      - "evidence:housing-rights-watch-case-note"
    method_refs:
      - "method:competence-first-review"
    legal_refs:
      - "legal:berlin-mietenwog-litigation"
      - "legal:bverfg-rent-cap-void"
    participation_refs:
      - "participation:tenant-landlord-litigation-channel"
    risks:
      - "risk:invalid-state-authority"
    tradeoffs:
      - "tradeoff:rent-relief-vs-supply"
    admissibility_label: "blocked"
    limitation_refs:
      - "limitation:legal-authority-blocker"
    contestability_status: "resolved_by_court"
obligations:
  - obligation_id: "obligation:rent-cap-competence-check"
    generated_from_facets:
      - "facet:instrument.rent_cap"
      - "facet:authority.subnational"
      - "facet:market.housing"
    required_evidence_family: "legal_competence_analysis"
    status: "closeout_block"
    reviewer_notes: "A governed recommendation should block before outcome modeling when the implementing authority lacks competence."
known_outcomes_or_failures:
  - finding_id: "outcome:law-void"
    source_ref: "outcome:law-void"
    would_prior_obligation_have_flagged: true
annotation_provenance:
  reviewer_role: "policy_generalist"
  expertise_basis: "W11.A source triage from Berlin court, BVerfG, and case-note sources"
  conflicts: []
  reviewed_at: "2026-05-24"
---

# Berlin Rent Cap

## Summary

Berlin's rent cap is a core negative case for authority semantics: a policy can
have a clear public problem and implementation machinery yet still be blocked
because the implementing authority lacks legal competence.

## W11.B Handoff

The compiler should generate a legal-competence obligation before compiling
method or welfare obligations. Projection must not convert the court-resolved
blocker into a mere policy limitation.
