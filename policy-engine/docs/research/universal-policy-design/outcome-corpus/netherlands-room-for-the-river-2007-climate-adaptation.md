---
case_id: "w11a_netherlands_room_for_river_2007"
case_title: "Netherlands Room for the River flood-risk adaptation programme"
corpus_phase: "W11.A"
sourcing_status: "sourced"
annotation_status: "annotated_w11b"
expert_adjudication_status: "adjudicated_w11c"
domain: "climate_adaptation"
authority_level: "research"
jurisdiction_authority_level: "national"
jurisdiction: "Netherlands"
policy_time: "2007-01 to 2019-01"
policy_instrument:
  instrument_type: "spatial_flood_risk_adaptation_programme"
  delivery_channel: "national and regional water-management works"
  funding_channel: "national infrastructure and water-management budget"
targeting:
  targeting_type: "risk_geography_and_hydrological_exposure"
  beneficiary_classes:
    - "residents_in_river_flood_risk_areas"
    - "national_water_safety_system"
  affected_populations:
    - "farmers_and_landowners"
    - "municipalities"
    - "water_boards"
    - "river_ecosystem_users"
expected_evidence_families:
  - "hydrological_modeling"
  - "spatial_planning_authority"
  - "project_delivery_and_cost_data"
  - "resident_participation_records"
  - "climate_risk_scenario_analysis"
raw_source_refs:
  - "https://www.rijkswaterstaat.nl/en/projects/iconic-structures/room-for-the-river"
  - "https://www.rijkswaterstaat.nl/water/waterbeheer/bescherming-tegen-het-water/maatregelen-om-overstromingen-te-voorkomen/ruimte-voor-de-rivieren"
  - "https://www.government.nl/topics/water-management/documents/policy-notes/2015/12/14/national-water-plan-2016-2021"
redacted_source_hashes: []
known_failure_limitation_labels:
  - "land_use_displacement_burden"
  - "future_climate_scenario_uncertainty"
  - "maintenance_and_monitoring_dependency"
  - "localized_distributional_burden"
references:
  - ref_id: "text:case:summary"
    ref_type: "source"
    source_ref: "repo://docs/research/universal-policy-design/outcome-corpus/netherlands-room-for-the-river-2007-climate-adaptation.md#summary"
    title: "Case summary"
  - ref_id: "legal:room-for-river-programme"
    ref_type: "legal"
    source_ref: "https://www.rijkswaterstaat.nl/water/waterbeheer/bescherming-tegen-het-water/maatregelen-om-overstromingen-te-voorkomen/ruimte-voor-de-rivieren"
    title: "Rijkswaterstaat Room for the River programme"
  - ref_id: "evidence:room-for-river-project-description"
    ref_type: "evidence"
    source_ref: "https://www.rijkswaterstaat.nl/en/projects/iconic-structures/room-for-the-river"
    title: "Rijkswaterstaat Room for the River project description"
  - ref_id: "method:hydrological-spatial-adaptation"
    ref_type: "method"
    source_ref: "https://www.rijkswaterstaat.nl/en/projects/iconic-structures/room-for-the-river"
    title: "River-capacity and flood-channel adaptation method"
  - ref_id: "participation:regional-resident-coordination"
    ref_type: "participation"
    source_ref: "https://www.rijkswaterstaat.nl/water/waterbeheer/bescherming-tegen-het-water/maatregelen-om-overstromingen-te-voorkomen/ruimte-voor-de-rivieren"
    title: "Regional coordination with residents and authorities"
  - ref_id: "risk:future-water-level-uncertainty"
    ref_type: "risk"
    source_ref: "https://www.government.nl/topics/water-management/documents/policy-notes/2015/12/14/national-water-plan-2016-2021"
    title: "National Water Plan climate and water-management uncertainty"
  - ref_id: "tradeoff:flood-safety-vs-land-use"
    ref_type: "tradeoff"
    source_ref: "https://www.rijkswaterstaat.nl/en/projects/iconic-structures/room-for-the-river"
    title: "Flood safety through giving rivers more room"
  - ref_id: "limitation:adaptation-not-final"
    ref_type: "limitation"
    source_ref: "https://www.government.nl/topics/water-management/documents/policy-notes/2015/12/14/national-water-plan-2016-2021"
    title: "Ongoing adaptation and monitoring needs"
  - ref_id: "outcome:programme-officially-completed"
    ref_type: "outcome"
    source_ref: "https://www.rijkswaterstaat.nl/water/waterbeheer/bescherming-tegen-het-water/maatregelen-om-overstromingen-te-voorkomen/ruimte-voor-de-rivieren"
    title: "Programme officially completed after Reevediep opening"
claims:
  - claim_id: "claim:room-for-river-reduces-flood-risk"
    claim_type: "risk_reduction"
    text_ref: "text:case:summary"
    scope:
      population:
        - "residents_in_river_flood_risk_areas"
      geography:
        - "Netherlands_river_regions"
      time_period: "2007-01 to 2019-01"
      institution:
        - "Rijkswaterstaat"
        - "regional_water_authorities"
    evidence_refs:
      - "evidence:room-for-river-project-description"
    method_refs:
      - "method:hydrological-spatial-adaptation"
    legal_refs:
      - "legal:room-for-river-programme"
    participation_refs:
      - "participation:regional-resident-coordination"
    risks:
      - "risk:future-water-level-uncertainty"
    tradeoffs:
      - "tradeoff:flood-safety-vs-land-use"
    admissibility_label: "limited"
    limitation_refs:
      - "limitation:adaptation-not-final"
    contestability_status: "review_required"
obligations:
  - obligation_id: "obligation:room-for-river-scenario-monitoring"
    generated_from_facets:
      - "facet:instrument.spatial_adaptation"
      - "facet:outcome.flood_risk_reduction"
      - "facet:time.future_climate_scenarios"
    required_evidence_family: "hydrological_modeling_and_lifecycle_monitoring"
    status: "required_for_research_closeout"
    reviewer_notes: "Research authority should preserve future-scenario uncertainty and land-use burden rather than treating completion as permanent adequacy."
known_outcomes_or_failures:
  - finding_id: "outcome:programme-officially-completed"
    source_ref: "outcome:programme-officially-completed"
    would_prior_obligation_have_flagged: false
annotation_provenance:
  reviewer_role: "policy_generalist"
  expertise_basis: "W11.A source triage from Rijkswaterstaat and Dutch national water policy materials"
  conflicts: []
  reviewed_at: "2026-05-24"
---

# Netherlands Room For The River

## Summary

Room for the River is a climate-adaptation case where policy design must
compose hydrological modeling, spatial planning, local burdens, and lifecycle
monitoring. It is not a simple infrastructure completion record.

## W11.B Handoff

Expected decomposition should distinguish completed works, flood-risk
reduction, spatial quality, affected land users, and future climate uncertainty.
