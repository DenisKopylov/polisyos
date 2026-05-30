from __future__ import annotations

from polisyos.data_requirement import DataRequirementSpec
from polisyos.fabric.catalog.data_requirement_adapter import (
    build_source_contract_requirement_bindings,
)


def test_selected_source_contract_without_matching_requirement_is_rejected() -> None:
    report = build_source_contract_requirement_bindings(
        data_requirement_specs=[
            _spec(
                requirement_id="data-requirement:claim-msme",
                claim_id="claim-msme",
                families=("production_msme_panel",),
            )
        ],
        source_contract_candidates=[
            {
                "candidate_ref": "production_data:curated:datasets:generic",
                "source_family": "datasets",
                "present_facets": [
                    "source_contract_ref",
                    "dictionary_ref",
                    "schema_ref",
                    "field_refs",
                    "unit_refs",
                    "geography_refs",
                    "time_coverage_refs",
                    "freshness_ref",
                    "lineage_refs",
                    "transformation_refs",
                    "quality_assertion_refs",
                    "missingness_refs",
                    "claim_bindability_refs",
                ],
                "source_contract_validation": {"status": "pass"},
            }
        ],
        selected_candidate_refs=("production_data:curated:datasets:generic",),
    )

    rejected = [
        binding
        for binding in report["source_contract_bindings"]
        if binding["binding_status"] == "rejected"
    ]
    blocked = [
        binding
        for binding in report["source_contract_bindings"]
        if binding["binding_status"] == "blocked"
    ]

    assert report["schema_version"] == "policyos.fabric.data_requirement_bindings.v1"
    assert rejected[0]["candidate_ref"] == "production_data:curated:datasets:generic"
    assert rejected[0]["reason_code"] == "no_matching_data_requirement_spec"
    assert rejected[0]["authority_surface"] == "context_inventory"
    assert blocked[0]["requirement_id"] == "data-requirement:claim-msme"
    assert blocked[0]["reason_code"] == "required_source_family_absent"


def test_unselected_extra_source_contract_is_context_only_and_matching_contract_selected() -> None:
    report = build_source_contract_requirement_bindings(
        data_requirement_specs=[
            _spec(
                requirement_id="data-requirement:claim-credit",
                claim_id="claim-credit",
                families=("credit_program_registry",),
            )
        ],
        source_contract_candidates=[
            {
                "candidate_ref": "production_data:curated:credit:contract.credit",
                "source_family": "credit_program_registry",
                "present_facets": list(_spec("r", "c", ("credit_program_registry",)).mandatory_facets),
                "source_contract_validation": {"status": "pass"},
            },
            {
                "candidate_ref": "production_data:curated:datasets:generic",
                "source_family": "datasets",
                "present_facets": ["source_contract_ref"],
                "source_contract_validation": {"status": "pass"},
            },
        ],
    )

    statuses = {
        binding["candidate_ref"]: binding["binding_status"]
        for binding in report["source_contract_bindings"]
        if binding.get("candidate_ref")
    }
    assert statuses["production_data:curated:credit:contract.credit"] == "selected"
    assert statuses["production_data:curated:datasets:generic"] == "context_only"
    assert report["summary"] == {
        "requirements": 1,
        "selected": 1,
        "rejected": 0,
        "blocked": 0,
        "context_only": 1,
    }


def test_fabric_consumes_capability_binding_result_with_source_assets_and_rejections() -> None:
    report = build_source_contract_requirement_bindings(
        data_requirement_specs=[
            _spec(
                requirement_id="data-requirement:claim-msme",
                claim_id="claim-msme",
                families=("production_msme_panel",),
            )
        ],
        source_contract_candidates=[],
        capability_bindings=[
            {
                "requirement_id": "data-requirement:claim-msme",
                "status": "selected_proxy_with_limitation",
                "selected_capability_ref": "capability:firm_survival_signal__ua__wartime_2022",
                "construct_ref": "construct:firm_survival",
                "capability_index_ref": "capability-index:phase5",
                "construct_registry_ref": "construct-registry:v1",
                "authority_composition_rule_ref": "capability-authority-v1.0",
                "source_assets": [
                    {
                        "ref": "parquet:dps_financials/firm_fundamentals_annual",
                        "fields": ["revenue", "assets", "employees"],
                    },
                    {
                        "ref": "parquet:distress_events/distress_events_panel_monthly",
                        "fields": ["event_flag", "event_count"],
                    },
                    {
                        "ref": "parquet:dps_tax_risk/compliance_distress_signals_monthly",
                        "fields": ["tax_debt", "risk_score"],
                    },
                ],
                "rights_envelope": {
                    "access_class": "government_administrative",
                    "public_export_allowed": "aggregate_only",
                },
                "quality_score": {"composite": 0.78},
                "limitations": ["Derived survival event; excludes informal firms."],
                "rejected_alternatives": [
                    {
                        "capability_ref": "capability:firm_survival_signal__ua__prewar",
                        "rejection_reason": "time_window_outside_claim",
                        "rejection_severity": "hard",
                    }
                ],
            }
        ],
    )

    selected = [
        row for row in report["source_contract_bindings"] if row["binding_status"] == "selected"
    ][0]
    rejected = [
        row for row in report["source_contract_bindings"] if row["binding_status"] == "rejected"
    ][0]

    assert selected["capability_ref"] == "capability:firm_survival_signal__ua__wartime_2022"
    assert selected["construct_ref"] == "construct:firm_survival"
    assert selected["capability_index_ref"] == "capability-index:phase5"
    assert selected["construct_registry_ref"] == "construct-registry:v1"
    assert selected["authority_composition_rule_ref"] == "capability-authority-v1.0"
    assert selected["source_asset_refs"] == [
        "parquet:dps_financials/firm_fundamentals_annual",
        "parquet:distress_events/distress_events_panel_monthly",
        "parquet:dps_tax_risk/compliance_distress_signals_monthly",
    ]
    assert selected["field_refs"] == [
        "assets",
        "employees",
        "event_count",
        "event_flag",
        "revenue",
        "risk_score",
        "tax_debt",
    ]
    assert selected["rights_envelope"]["public_export_allowed"] == "aggregate_only"
    assert selected["quality_score"]["composite"] == 0.78
    assert rejected["capability_ref"] == "capability:firm_survival_signal__ua__prewar"
    assert rejected["reason_code"] == "time_window_outside_claim"
    assert report["summary"]["capability_binding_count"] == 2


def _spec(
    requirement_id: str,
    claim_id: str,
    families: tuple[str, ...],
) -> DataRequirementSpec:
    return DataRequirementSpec(
        requirement_id=requirement_id,
        claim_id=claim_id,
        claim_family="causal",
        claim_type="causal",
        claim_use="decision_support",
        required_data_families=families,
        scope={
            "population": "msmes",
            "geography": "state_or_region",
            "time": "annual",
            "time_role": "observation_time",
        },
        recency_horizon="P90D",
        lineage_strictness="strict",
        quality_minima={"min_quality_score": 0.8, "min_completeness": 0.95},
        missingness_tolerance=0.05,
        transformation_tolerance="traceable",
        admissibility_predicates=(
            "source_family_matches_compiled_requirement",
            "source_contract_active",
        ),
        mandatory_facets=(
            "source_contract_ref",
            "dictionary_ref",
            "schema_ref",
            "field_refs",
            "unit_refs",
            "geography_refs",
            "time_coverage_refs",
            "freshness_ref",
            "lineage_refs",
            "transformation_refs",
            "quality_assertion_refs",
            "missingness_refs",
            "claim_bindability_refs",
        ),
        facet_refs=("facet:instrument",),
        obligation_refs=("obl:data",),
        concept_spine_refs=("concept:msme",),
        authority_profile_refs=("authority:production",),
    )
